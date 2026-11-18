import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Check, ChevronRight, Compass } from 'lucide-react';
import {
  keys,
  useFlashStats,
  usePerformance,
  useRevisions,
  useSessions,
  useStudyPanel,
} from '@/app/queries';
import { AreaChart, BarList, DataTableFallback, Meter } from '@/components/charts';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Kpi, NumberTicker } from '@/components/ui/kpi';
import { EmptyState, ErrorState, SkeletonRows } from '@/components/ui/states';
import { api } from '@/lib/api';
import { formatTitleCase } from '@/lib/domain';
import { duration, integer, percent, shortDate } from '@/lib/format';
import type { StudySession } from '@/lib/types';
import { StudyTimerBlock } from './StudyTimerBlock';
import { SyncEditalCard } from './SyncEditalCard';

export function StudyOverviewTab() {
  const navigate = useNavigate();
  const panel = useStudyPanel();
  const sessions = useSessions();
  const revisions = useRevisions();
  const performance = usePerformance();
  const flash = useFlashStats();

  if (panel.isLoading) return <SkeletonRows rows={5} />;
  if (panel.isError)
    return (
      <Card>
        <ErrorState message={panel.error.message} onRetry={() => panel.refetch()} />
      </Card>
    );

  const data = panel.data!;
  const geral = performance.data?.geral;
  const topics = data.conteudo?.topics ?? { done: 0, total: 0, pct: 0 };
  const activity = buildActivity(sessions.data ?? []);
  const empty =
    data.total_segundos === 0 &&
    data.sessoes_concluidas === 0 &&
    topics.total === 0 &&
    data.disciplinas === 0;

  return (
    <div className="space-y-3">
      <section aria-label="Indicadores de estudo" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi
          feature
          tone="accent"
          label="Tempo estudado"
          value={<span className="tabular">{duration(data.total_segundos)}</span>}
          context={`${duration(data.semana_segundos)} nos últimos 7 dias`}
        />
        <Kpi
          label="Sessões concluídas"
          value={<NumberTicker value={data.sessoes_concluidas} />}
          context={data.sessao_aberta ? 'Uma sessão está aberta' : 'Nenhuma sessão aberta'}
        />
        <Kpi
          label="Revisões pendentes"
          value={<NumberTicker value={data.revisoes_pendentes} />}
          context={data.revisoes_pendentes ? 'Agenda de revisão espaçada' : 'Nada vencido'}
        />
        <Kpi
          label="Questões respondidas"
          value={<NumberTicker value={geral?.respondidas ?? 0} />}
          context={
            geral?.pct === null || geral?.pct === undefined
              ? 'Percentual não calculável'
              : `${percent(geral.pct)} de acerto · ${geral.basis}`
          }
        />
      </section>

      <div className="rounded-xl border border-amber-400/30 bg-gradient-to-r from-amber-400/10 via-surface to-surface-2 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-amber-400/15 border border-amber-400/30 flex items-center justify-center text-accent-ink shrink-0">
            <Compass size={20} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-fg">Ciclo Semanal de Estudos Ativo</span>
              <span className="px-1.5 py-0.2 rounded-full text-[9px] font-bold bg-amber-400/20 text-accent-ink border border-amber-400/30 uppercase">
                Recomendado pela IA
              </span>
            </div>
            <p className="text-2xs text-fg-3 mt-0.5">
              Grade intercalada de alta retenção calibrada para a banca do seu concurso foco.
            </p>
          </div>
        </div>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => navigate('/estudos/cronograma')}
          className="gap-1.5 shrink-0 text-xs font-semibold"
        >
          <span>Abrir Ciclo Completo</span>
          <ChevronRight size={13} />
        </Button>
      </div>

      <div className="grid gap-3 xl:grid-cols-[1.3fr_1fr]">
        <Card title="Sessão de estudo" subtitle="O cronômetro roda no servidor; fechar a aba não apaga a sessão.">
          <StudyTimerBlock panel={data} />
        </Card>

        <Card title="Tempo por disciplina" subtitle="Somente sessões concluídas.">
          {!data.minutos_por_disciplina.length ? (
            <EmptyState
              title="Sem tempo registrado"
              description="Conclua uma sessão para ver a distribuição por disciplina."
            />
          ) : (
            <BarList
              ariaLabel="Minutos estudados por disciplina"
              data={data.minutos_por_disciplina.map((item) => ({
                label: formatTitleCase(item.nome),
                value: item.minutos,
                title: `${formatTitleCase(item.nome)}: ${item.minutos} min`,
              }))}
            />
          )}
        </Card>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <Card title="Atividade recente" subtitle="Minutos concluídos por dia nos últimos 14 dias.">
          {activity.every((point) => point.value === 0) ? (
            <EmptyState
              title="Sem atividade registrada"
              description="Conclua uma sessão para alimentar o gráfico."
            />
          ) : (
            <>
              <AreaChart
                data={activity}
                height={186}
                unit="min"
                color="var(--color-verified)"
                ariaLabel="Minutos estudados por dia"
                description="Série temporal com minutos concluídos nos últimos 14 dias."
              />
              <DataTableFallback
                summary="Ver dias em tabela"
                columns={['Dia', 'Minutos']}
                rows={activity.map((point) => [point.label, point.value])}
              />
            </>
          )}
        </Card>

        <Card title="Revisões de hoje" subtitle="Agenda persistida, sem sequência inventada.">
          <RevisionList revisions={revisions.data ?? []} pending={data.revisoes_pendentes} />
        </Card>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <Card title="Progresso do conteúdo" subtitle="Tópicos concluídos sobre o total cadastrado.">
          {topics.total === 0 ? (
            <EmptyState
              title="Nenhum tópico cadastrado"
              description="Crie disciplinas e tópicos na aba Sessões para medir progresso."
            />
          ) : (
            <div className="space-y-3">
              <Meter label="Tópicos" value={topics.done} total={topics.total} />
              <Meter
                label="Geral"
                value={data.conteudo.overall.done}
                total={data.conteudo.overall.total}
                color="var(--color-verified)"
              />
            </div>
          )}
        </Card>

        <Card title="Práticas" subtitle="Estado real do banco de questões e flashcards.">
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-sm border border-line bg-surface-2 p-2.5">
              <p className="text-[9px] font-semibold tracking-[0.1em] text-fg-3 uppercase">Flashcards ativos</p>
              <p className="mt-1 font-display text-lg font-semibold tabular text-fg">
                {integer(flash.data?.ativos ?? 0)}
              </p>
              <p className="mt-0.5 text-2xs text-fg-3">{flash.data?.basis ?? '—'}</p>
            </div>
            <div className="rounded-sm border border-line bg-surface-2 p-2.5">
              <p className="text-[9px] font-semibold tracking-[0.1em] text-fg-3 uppercase">Acerto em questões</p>
              <p className="mt-1 font-display text-lg font-semibold tabular text-fg">
                {geral?.pct === null || geral?.pct === undefined ? '—' : percent(geral.pct)}
              </p>
              <p className="mt-0.5 text-2xs text-fg-3">{geral?.basis ?? 'Sem tentativas'}</p>
            </div>
          </div>
          {empty && (
            <p className="mt-2 text-2xs text-fg-3">
              Comece criando uma disciplina ou importando o conteúdo programático do edital.
            </p>
          )}
        </Card>
      </div>

      <SyncEditalCard />
    </div>
  );
}

function buildActivity(sessions: StudySession[]) {
  const byDay = new Map<string, number>();
  for (const session of sessions) {
    if (session.estado !== 'concluida' || !session.fim) continue;
    const key = session.fim.slice(0, 10);
    byDay.set(key, (byDay.get(key) ?? 0) + Math.round(session.duracao_segundos / 60));
  }
  const points: { label: string; value: number; title: string }[] = [];
  const today = new Date();
  for (let i = 13; i >= 0; i -= 1) {
    const day = new Date(today.getFullYear(), today.getMonth(), today.getDate() - i);
    const key = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`;
    const value = byDay.get(key) ?? 0;
    points.push({
      label: day.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }),
      value,
      title: `${day.toLocaleDateString('pt-BR')}: ${value} min`,
    });
  }
  return points;
}

function RevisionList({
  revisions,
  pending,
}: {
  revisions: { revisao_id: string; progresso_id: string; data: string; topico_id: string }[];
  pending: number;
}) {
  const queryClient = useQueryClient();
  const mark = useMutation({
    mutationFn: (progressoId: string) =>
      api.post('/api/estudos/revisoes', { progresso_id: progressoId, resultado: 'concluida' }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keys.study() });
      void queryClient.invalidateQueries({ queryKey: keys.revisions() });
    },
  });

  if (!revisions.length) {
    return (
      <EmptyState
        title={pending ? 'Revisões em processamento' : 'Nenhuma revisão pendente'}
        description="A agenda aparece quando um tópico é concluído e entra na revisão espaçada."
      />
    );
  }

  return (
    <ul className="divide-y divide-line">
      {revisions.slice(0, 6).map((revision) => (
        <li key={revision.revisao_id} className="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0">
          <div className="min-w-0">
            <p className="truncate text-xs font-medium text-fg">Revisão de {shortDate(revision.data)}</p>
            <p className="mt-0.5 text-2xs text-fg-3">Tópico {revision.topico_id.slice(0, 8)}</p>
          </div>
          <Button
            size="sm"
            variant="ghost"
            disabled={mark.isPending}
            onClick={() => mark.mutate(revision.progresso_id)}
          >
            <Check size={12} /> Revisada
          </Button>
        </li>
      ))}
    </ul>
  );
}
