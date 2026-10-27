import { ArrowRight, CalendarDays, Clock3, Compass, Layers, Target } from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  useCoverage,
  useDeadlines,
  usePortfolio,
  useStudyPanel,
  useTimeline,
} from '@/app/queries';
import { AreaChart, BarList, DataTableFallback, Legend, Meter, StackedBar } from '@/components/charts';
import { PageHeader } from '@/components/layout/page-header';
import { Badge } from '@/components/ui/badge';
import { LinkButton } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Kpi, NumberTicker } from '@/components/ui/kpi';
import { EmptyState, ErrorState, SkeletonCards, SkeletonRows } from '@/components/ui/states';
import {
  indigenousShort,
  indigenousTones,
  readinessColors,
  readinessLabels,
  readinessTones,
  siShort,
  siTones,
} from '@/lib/domain';
import { duration, integer, longToday, percent, percentOf, relativeDays, shortDate, truncate } from '@/lib/format';
import type { Deadline, Opportunity } from '@/lib/types';

const funnelLabels: Record<string, string> = {
  concursos: 'Concursos',
  com_documento: 'Com documento',
  com_edital_oficial: 'Com edital oficial',
  com_edital_analisado: 'Edital analisado',
  com_propostas: 'Com propostas',
  com_campo_confirmado: 'Com campo confirmado',
};

const causeLabels: Record<string, string> = {
  apenas_agregador: 'Apenas agregador',
  documento_oficial_sem_edital: 'Documento oficial sem edital',
  edital_sem_campos: 'Edital sem campos',
  sem_documento: 'Sem documento',
  extraido_ambiguo: 'Extração ambígua',
};

function nextDeadline(item: Opportunity): Deadline | null {
  const future = item.prazos
    .filter((d) => d.estado_temporal === 'futuro' && d.dias_restantes !== null)
    .sort((a, b) => (a.dias_restantes ?? 9999) - (b.dias_restantes ?? 9999));
  return future[0] ?? null;
}

function dossierLink(item: Opportunity): string {
  const params = new URLSearchParams();
  if (item.scope) params.set('scope', item.scope);
  return `/dossie/${item.contest_id}${params.size ? `?${params}` : ''}`;
}

export function OverviewPage() {
  const portfolio = usePortfolio({ limit: 6 });
  const coverage = useCoverage();
  const timeline = useTimeline();
  const study = useStudyPanel();
  const deadlines = useDeadlines({ urgency: 'ate_7_dias', limit: 6 });

  const items = portfolio.data?.itens ?? [];
  const total = portfolio.data?.total ?? 0;
  const urgency = portfolio.data?.por_urgencia ?? {};
  const urgent = (urgency.ate_7_dias ?? 0) + (urgency.ate_30_dias ?? 0);
  const readiness = portfolio.data?.por_prontidao ?? {};
  const readinessSegments = Object.entries(readiness)
    .sort((a, b) => b[1] - a[1])
    .map(([key, value]) => ({
      label: readinessLabels[key] ?? key,
      value,
      color: readinessColors[key] ?? 'var(--color-unknown)',
    }));

  const escopo = coverage.data?.escopo;
  const studyData = study.data;
  const cycles = (timeline.data?.ciclos ?? []).slice(-8);
  const activityData = cycles.map((cycle) => {
    const parsed = new Date(cycle.started_at);
    const label = Number.isNaN(parsed.getTime())
      ? '—'
      : `${shortDate(cycle.started_at)} ${String(parsed.getHours()).padStart(2, '0')}h`;
    return {
      label,
      value: cycle.versions_new ?? 0,
      title: `${label}: ${integer(cycle.versions_new ?? 0)} versões · ${integer(cycle.documents_new ?? 0)} documentos · ${cycle.state}`,
    };
  });

  const funil = coverage.data?.funil ?? [];
  const base = funil[0]?.de ?? 0;
  const causas = Object.entries(coverage.data?.causas ?? {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3);

  const upcoming = (deadlines.data?.itens ?? []).filter(
    (deadline, index, all) =>
      all.findIndex(
        (other) =>
          other.grupo === deadline.grupo &&
          other.valor === deadline.valor &&
          other.contest_id === deadline.contest_id,
      ) === index,
  );

  return (
    <>
      <PageHeader
        eyebrow="Painel"
        title="Visão geral"
        description="Oportunidades monitoradas, prazos que merecem atenção e o retrato real da cobertura documental. Nenhum campo é confirmado automaticamente."
        meta={
          <>
            <span className="inline-flex items-center gap-1.5">
              <CalendarDays size={12} /> {longToday()}
            </span>
            <span className="text-fg-3/70">
              Referência da carteira:{' '}
              {portfolio.data?.referencia.hoje_local ?? '—'}
            </span>
          </>
        }
        actions={
          <LinkButton to="/oportunidades" variant="primary">
            Explorar oportunidades <ArrowRight size={14} />
          </LinkButton>
        }
      />

      {portfolio.isLoading ? (
        <SkeletonCards count={4} />
      ) : portfolio.isError ? (
        <Card>
          <ErrorState message={portfolio.error.message} onRetry={() => portfolio.refetch()} />
        </Card>
      ) : (
        <section aria-label="Indicadores" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-[1.45fr_1fr_1fr_1fr]">
          <Kpi
            feature
            label="Oportunidades na carteira"
            value={<NumberTicker value={total} />}
            icon={<Target size={14} />}
            tone="accent"
            context={
              urgent > 0
                ? `${integer(urgent)} com prazo nos próximos 30 dias · ${integer(urgency.ate_7_dias ?? 0)} em até 7 dias`
                : 'Nenhum prazo futuro registrado para as oportunidades atuais.'
            }
            footer={readinessSegments.length ? <StackedBar segments={readinessSegments} ariaLabel="Prontidão da carteira" /> : null}
          />
          <Kpi
            label="Concursos monitorados"
            value={<NumberTicker value={escopo?.concursos ?? 0} />}
            icon={<Layers size={14} />}
            context={
              coverage.isLoading
                ? 'Carregando cobertura…'
                : `${integer(escopo?.com_edital_analisado ?? 0)} com edital analisado · ${integer(escopo?.com_documento ?? 0)} com algum documento`
            }
          />
          <Kpi
            label="Prazos em até 30 dias"
            value={<NumberTicker value={urgent} />}
            icon={<CalendarDays size={14} />}
            context={`${integer(urgency.ate_7_dias ?? 0)} em até 7 dias · ${integer(urgency.vencido ?? 0)} vencidos preservados como histórico`}
          />
          <Kpi
            label="Tempo estudado"
            value={<span className="tabular">{duration(studyData?.total_segundos ?? 0)}</span>}
            icon={<Clock3 size={14} />}
            context={`${integer(studyData?.sessoes_concluidas ?? 0)} sessões concluídas · ${integer(studyData?.revisoes_pendentes ?? 0)} revisões pendentes`}
          />
        </section>
      )}

      <div className="mt-3 grid gap-3 xl:grid-cols-[1.55fr_1fr]">
        <Card
          title="Atividade documental"
          subtitle="Novas versões identificadas em cada ciclo de monitoramento."
          action={
            <Link to="/historico" className="text-2xs font-medium text-accent hover:underline">
              Histórico
            </Link>
          }
        >
          {timeline.isLoading ? (
            <SkeletonRows rows={4} />
          ) : timeline.isError ? (
            <ErrorState message={timeline.error.message} onRetry={() => timeline.refetch()} />
          ) : !activityData.length ? (
            <EmptyState
              title="Nenhum ciclo registrado"
              description="A atividade aparece depois do primeiro ciclo de monitoramento."
            />
          ) : (
            <>
              <AreaChart
                data={activityData}
                height={210}
                unit="versões"
                ariaLabel="Novas versões por ciclo de monitoramento"
                description="Série temporal com o número de versões novas em cada um dos últimos ciclos."
              />
              <DataTableFallback
                summary="Ver ciclos em tabela"
                caption="Versões e documentos novos por ciclo"
                columns={['Ciclo', 'Versões', 'Documentos', 'Estado']}
                rows={cycles.map((cycle, index) => [
                  activityData[index]?.label ?? '—',
                  integer(cycle.versions_new ?? 0),
                  integer(cycle.documents_new ?? 0),
                  cycle.state,
                ])}
              />
            </>
          )}
        </Card>

        <Card
          title="Cobertura documental"
          subtitle="Do universo de concursos até o primeiro campo confirmado."
          action={
            <Link to="/operacao" className="text-2xs font-medium text-accent hover:underline">
              Operação
            </Link>
          }
        >
          {coverage.isLoading ? (
            <SkeletonRows rows={5} />
          ) : coverage.isError ? (
            <ErrorState message={coverage.error.message} onRetry={() => coverage.refetch()} />
          ) : !funil.length ? (
            <EmptyState
              title="Sem dados de cobertura"
              description="A cobertura é calculada a partir dos documentos coletados."
            />
          ) : (
            <>
              <BarList
                ariaLabel="Funil de cobertura documental"
                data={funil.map((stage) => ({
                  label: funnelLabels[stage.etapa] ?? stage.etapa,
                  value: stage.quantidade,
                  color:
                    stage.etapa === 'com_campo_confirmado'
                      ? 'var(--color-verified)'
                      : 'var(--color-accent)',
                  title: `${integer(stage.quantidade)} de ${integer(stage.de)} (${percent(percentOf(stage.quantidade, base))})`,
                }))}
              />
              <p className="mt-3 text-2xs text-fg-3">
                Base: {integer(base)} concursos. Etapas não são somadas entre si.
              </p>
              {causas.length > 0 && (
                <ul className="mt-3 space-y-1.5 border-t border-line pt-3">
                  {causas.map(([key, value]) => (
                    <li key={key} className="flex items-center justify-between gap-2 text-2xs">
                      <span className="truncate text-fg-3">{causeLabels[key] ?? key}</span>
                      <span className="tabular font-medium text-fg-2">{integer(value)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </Card>
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-2">
        <Card
          title="Oportunidades prioritárias"
          subtitle="Ordenadas pela política operacional do servidor, com o motivo em destaque."
          action={
            <Link to="/oportunidades" className="text-2xs font-medium text-accent hover:underline">
              Ver todas
            </Link>
          }
        >
          {portfolio.isLoading ? (
            <SkeletonRows rows={5} />
          ) : !items.length ? (
            <EmptyState
              title="Nenhuma oportunidade na carteira"
              description="A carteira é montada a partir de documentos oficiais analisados."
            />
          ) : (
            <ul className="divide-y divide-line">
              {items.slice(0, 5).map((item) => {
                const deadline = nextDeadline(item);
                return (
                  <li key={`${item.contest_id}-${item.scope}`} className="flex items-start gap-3 py-2.5 first:pt-0 last:pb-0">
                    <div className="min-w-0 flex-1">
                      <Link
                        to={dossierLink(item)}
                        className="block truncate text-[13px] font-medium text-fg transition-colors hover:text-accent"
                      >
                        {item.contest_label ?? item.competition_id ?? 'Concurso'}
                      </Link>
                      <p className="mt-0.5 truncate text-2xs text-fg-3">
                        {item.role_name ?? 'Cargo não reconciliado'}
                        {item.localizacao.prova.text ? ` · ${item.localizacao.prova.text}` : ''}
                      </p>
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        <Badge tone={readinessTones[item.prontidao.estado] ?? 'unknown'}>
                          {item.prontidao.estado_label}
                        </Badge>
                        {deadline && (
                          <Badge tone={deadline.urgencia === 'ate_7_dias' ? 'risk' : 'warn'}>
                            {relativeDays(deadline.dias_restantes)}
                          </Badge>
                        )}
                        {item.si.estado !== 'nao_informado' && (
                          <Badge tone={siTones[item.si.estado] ?? 'neutral'}>
                            SI: {siShort[item.si.estado] ?? item.si.estado}
                          </Badge>
                        )}
                        {item.indigenas.estado === 'explicito_imediato' && (
                          <Badge tone={indigenousTones[item.indigenas.estado]}>
                            {indigenousShort[item.indigenas.estado]}
                          </Badge>
                        )}
                      </div>
                    </div>
                    <Link
                      to={dossierLink(item)}
                      className="shrink-0 text-2xs font-medium text-accent hover:underline"
                    >
                      Dossiê
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <Card
          title="Prazos próximos"
          subtitle="Somente datas futuras com documento e estado de verificação."
          action={
            <Link to="/prazos" className="text-2xs font-medium text-accent hover:underline">
              Calendário
            </Link>
          }
        >
          {deadlines.isLoading ? (
            <SkeletonRows rows={4} />
          ) : deadlines.isError ? (
            <ErrorState message={deadlines.error.message} onRetry={() => deadlines.refetch()} />
          ) : !upcoming.length ? (
            <EmptyState
              title="Nenhum prazo em até 7 dias"
              description="Datas passadas continuam no histórico; datas candidatas não viram prazo confirmado."
            />
          ) : (
            <ul className="divide-y divide-line">
              {upcoming.slice(0, 5).map((deadline, index) => {
                const parsed = deadline.valor ? new Date(`${deadline.valor}T12:00:00`) : null;
                return (
                  <li key={`${deadline.contest_id}-${deadline.grupo}-${index}`} className="flex items-start gap-3 py-2.5 first:pt-0 last:pb-0">
                    <div className="grid w-10 shrink-0 place-items-center rounded-xs border border-line bg-surface-2 py-1 leading-none">
                      <span className="font-display text-sm font-semibold tabular text-fg">
                        {parsed && !Number.isNaN(parsed.getTime())
                          ? String(parsed.getDate()).padStart(2, '0')
                          : '—'}
                      </span>
                      <span className="mt-0.5 text-[8px] font-semibold tracking-[0.08em] text-fg-3 uppercase">
                        {parsed && !Number.isNaN(parsed.getTime())
                          ? parsed.toLocaleDateString('pt-BR', { month: 'short' }).replace('.', '')
                          : ''}
                      </span>
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[13px] font-medium text-fg">{deadline.grupo_label}</p>
                      <p className="mt-0.5 truncate text-2xs text-fg-3">
                        {deadline.documento ?? 'Documento não identificado'}
                        {deadline.pagina ? ` · p. ${deadline.pagina}` : ''}
                      </p>
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        <Badge tone={deadline.urgencia === 'ate_7_dias' ? 'risk' : 'warn'}>
                          {relativeDays(deadline.dias_restantes)}
                        </Badge>
                        <Badge tone="neutral">{truncate(deadline.estado_operacional_label, 34)}</Badge>
                      </div>
                    </div>
                    <Link
                      to={`/dossie/${deadline.contest_id}`}
                      className="shrink-0 text-2xs font-medium text-accent hover:underline"
                    >
                      Abrir
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-2">
        <Card title="Carteira por prontidão" subtitle="Cada oportunidade tem um estado determinístico e explicado.">
          {portfolio.isLoading ? (
            <SkeletonRows rows={3} />
          ) : !readinessSegments.length ? (
            <EmptyState
              title="Sem oportunidades classificadas"
              description="A prontidão aparece quando houver documentos analisados."
            />
          ) : (
            <>
              <StackedBar segments={readinessSegments} ariaLabel="Distribuição por prontidão" />
              <Legend segments={readinessSegments} />
              <p className="mt-3 text-2xs text-fg-3">
                Total: {integer(total)} oportunidades. Estados não são probabilidade de aprovação.
              </p>
            </>
          )}
        </Card>

        <Card
          title="Estudos"
          subtitle="Tempo, sessões e revisões registrados por você."
          action={
            <Link to="/estudos" className="text-2xs font-medium text-accent hover:underline">
              Abrir estudos
            </Link>
          }
        >
          {study.isLoading ? (
            <SkeletonRows rows={3} />
          ) : study.isError ? (
            <ErrorState message={study.error.message} onRetry={() => study.refetch()} />
          ) : !studyData ||
            ((studyData.total_segundos ?? 0) === 0 &&
              (studyData.sessoes_concluidas ?? 0) === 0 &&
              (studyData.conteudo?.topics.total ?? 0) === 0 &&
              (studyData.disciplinas ?? 0) === 0) ? (
            <EmptyState
              icon={<Compass size={20} strokeWidth={1.6} />}
              title="Seu estudo começa aqui"
              description="Nenhuma disciplina, sessão ou revisão registrada. Crie uma disciplina e inicie o cronômetro."
              action={
                <LinkButton to="/estudos" size="sm">
                  Abrir estudos
                </LinkButton>
              }
            />
          ) : (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-sm border border-line bg-surface-2 p-2.5">
                  <p className="text-[9px] font-semibold tracking-[0.1em] text-fg-3 uppercase">Tempo total</p>
                  <p className="mt-1 font-display text-lg font-semibold tabular text-fg">
                    {duration(studyData.total_segundos)}
                  </p>
                </div>
                <div className="rounded-sm border border-line bg-surface-2 p-2.5">
                  <p className="text-[9px] font-semibold tracking-[0.1em] text-fg-3 uppercase">Sessões</p>
                  <p className="mt-1 font-display text-lg font-semibold tabular text-fg">
                    {integer(studyData.sessoes_concluidas)}
                  </p>
                </div>
              </div>
              {(studyData.conteudo?.topics.total ?? 0) > 0 && (
                <Meter
                  label="Tópicos concluídos"
                  value={studyData.conteudo.topics.done}
                  total={studyData.conteudo.topics.total}
                />
              )}
              <p className="text-2xs text-fg-3">
                {integer(studyData.revisoes_pendentes)} revisões pendentes ·{' '}
                {duration(studyData.semana_segundos)} nos últimos 7 dias
              </p>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
