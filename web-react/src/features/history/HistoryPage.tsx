import { useTimeline } from '@/app/queries';
import { BarList, DataTableFallback } from '@/components/charts';
import { PageHeader } from '@/components/layout/page-header';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { Kpi, NumberTicker } from '@/components/ui/kpi';
import { EmptyState, ErrorState, SkeletonRows } from '@/components/ui/states';
import { cycleLabels, cycleTones } from '@/lib/domain';
import { dateTime, integer, safeUrl } from '@/lib/format';

const eventLabels: Record<string, string> = {
  descoberta: 'Descoberta',
  analise: 'Análise',
  download: 'Download',
  falha: 'Falha',
};

const sourceLabels: Record<string, string> = {
  concluido: 'Concluído',
  parcial: 'Parcial',
  falhou: 'Falhou',
  nao_verificada: 'Não verificada',
};

export function HistoryPage() {
  const timeline = useTimeline();

  if (timeline.isLoading) {
    return (
      <>
        <PageHeader eyebrow="Rastreabilidade" title="Histórico" />
        <SkeletonRows rows={6} />
      </>
    );
  }

  if (timeline.isError || !timeline.data) {
    return (
      <>
        <PageHeader eyebrow="Rastreabilidade" title="Histórico" />
        <Card>
          <ErrorState message={timeline.error?.message ?? 'Histórico indisponível.'} onRetry={() => timeline.refetch()} />
        </Card>
      </>
    );
  }

  const data = timeline.data;
  const events = Object.entries(data.eventos).sort((a, b) => b[1] - a[1]);

  return (
    <>
      <PageHeader
        eyebrow="Rastreabilidade"
        title="Histórico"
        description="O que mudou na base nas últimas 24 horas, ciclo a ciclo, com documentos, versões e eventos."
        meta={
          <span>
            Janela: {dateTime(data.referencia.desde)} → {dateTime(data.referencia.ate)}
          </span>
        }
      />

      <section aria-label="Mudanças nas últimas 24 horas" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi
          feature
          tone="accent"
          label="Documentos novos (24h)"
          value={<NumberTicker value={data.novos.documentos} />}
          context={`Base anterior: ${integer(data.snapshot_anterior.documentos)} documentos`}
        />
        <Kpi
          label="Versões novas"
          value={<NumberTicker value={data.novos.versoes} />}
          context="Conteúdo novo ou alterado identificado"
        />
        <Kpi
          label="Propostas novas"
          value={<NumberTicker value={data.novos.propostas} />}
          context="Extrações candidatas, sem confirmação automática"
        />
        <Kpi
          label="Revisões"
          value={<NumberTicker value={data.novos.revisoes} />}
          context="Decisões humanas registradas no período"
        />
      </section>

      <div className="mt-3 grid gap-3 xl:grid-cols-[1.4fr_1fr]">
        <Card title="Eventos por tipo" subtitle="Contagem real no período de referência.">
          {!events.length ? (
            <EmptyState
              title="Nenhum evento no período"
              description="A base não registrou descobertas, downloads, análises ou falhas nas últimas 24 horas."
            />
          ) : (
            <>
              <BarList
                ariaLabel="Eventos documentais por tipo"
                data={events.map(([key, value]) => ({
                  label: eventLabels[key] ?? key,
                  value,
                  color: key === 'falha' ? 'var(--color-risk)' : 'var(--color-accent)',
                }))}
              />
              <DataTableFallback
                summary="Ver eventos em tabela"
                columns={['Evento', 'Total']}
                rows={events.map(([key, value]) => [eventLabels[key] ?? key, integer(value)])}
              />
            </>
          )}
        </Card>

        <Card title="Comparação com o snapshot anterior" subtitle="Base antes e depois da janela.">
          <dl className="grid grid-cols-[1fr_auto] gap-y-2 text-xs">
            {[
              ['Documentos', data.snapshot_anterior.documentos, data.novos.documentos],
              ['Versões', data.snapshot_anterior.versoes, data.novos.versoes],
              ['Propostas', data.snapshot_anterior.propostas, data.novos.propostas],
              ['Revisões', data.snapshot_anterior.revisoes, data.novos.revisoes],
            ].map(([label, before, added]) => (
              <div key={String(label)} className="col-span-2 grid grid-cols-[1fr_auto_auto] items-center gap-2 border-b border-line/60 pb-1.5 last:border-0">
                <dt className="text-fg-3">{label}</dt>
                <dd className="tabular text-fg-2">{integer(before)}</dd>
                <dd className="tabular text-xs font-medium text-accent">+{integer(added)}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </div>

      <Card title="Ciclos de monitoramento" subtitle="Estado final, duração e resultado por fonte." className="mt-3">
        {!data.ciclos.length ? (
          <EmptyState
            title="Nenhum ciclo registrado"
            description="Execute um ciclo na Operação para começar o histórico."
          />
        ) : (
          <ul className="space-y-2.5">
            {[...data.ciclos].reverse().map((cycle) => (
              <li key={cycle.cycle_id} className="rounded-sm border border-line bg-surface-2 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs font-medium text-fg">Ciclo de {dateTime(cycle.started_at)}</p>
                  <Badge tone={cycleTones[cycle.state] ?? 'neutral'}>
                    {cycleLabels[cycle.state] ?? cycle.state}
                  </Badge>
                </div>
                <p className="mt-1 text-2xs text-fg-3">
                  {integer(cycle.documents_found)} documento(s) encontrado(s) ·{' '}
                  {integer(cycle.documents_new)} novo(s) · {integer(cycle.versions_new)} versão(ões) nova(s)
                </p>
                {cycle.fontes.length > 0 && (
                  <details className="mt-1.5">
                    <summary className="cursor-pointer text-2xs text-fg-3 hover:text-fg-2">
                      Fontes do ciclo ({cycle.fontes.length})
                    </summary>
                    <ul className="mt-1 space-y-1">
                      {cycle.fontes.map((source) => (
                        <li key={source.source_url} className="flex flex-wrap items-center gap-2 text-2xs">
                          <span className="min-w-0 flex-1 truncate text-fg-3">
                            {safeUrl(source.source_url) ?? source.source_url}
                          </span>
                          <Badge tone={source.state === 'falhou' ? 'risk' : source.state === 'parcial' ? 'warn' : 'ok'}>
                            {sourceLabels[source.state] ?? source.state}
                          </Badge>
                          {source.error_code && <span className="text-fg-3">{source.error_code}</span>}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
