import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useDeadlines } from '@/app/queries';
import { PageHeader } from '@/components/layout/page-header';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Kpi, NumberTicker } from '@/components/ui/kpi';
import { EmptyState, ErrorState, SkeletonRows } from '@/components/ui/states';
import { deadlineGroups, urgencyLabels } from '@/lib/domain';
import { date, integer, relativeDays } from '@/lib/format';

export function DeadlinesPage() {
  const [params, setParams] = useSearchParams();
  const group = params.get('group') ?? '';
  const urgency = params.get('urgency') ?? '';
  const [advanced, setAdvanced] = useState(false);
  const query = useDeadlines({ group: group || undefined, urgency: urgency || undefined });
  const data = query.data;

  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (!value) next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
  };

  const urgencyCounts = data?.por_urgencia ?? {};
  const items = data?.itens ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Calendário"
        title="Prazos"
        description="Cada evento pertence a um grupo e a um documento. Data candidata não é prazo confirmado; datas passadas permanecem como histórico."
        meta={
          data ? (
            <span>
              Referência {data.referencia.hoje_local} ({data.referencia.fuso})
            </span>
          ) : null
        }
        actions={
          (group || urgency) && (
            <Button variant="ghost" size="sm" onClick={() => setParams(new URLSearchParams(), { replace: true })}>
              Limpar filtros
            </Button>
          )
        }
      />

      {query.isLoading ? (
        <SkeletonRows rows={4} />
      ) : query.isError ? (
        <Card>
          <ErrorState message={query.error.message} onRetry={() => query.refetch()} />
        </Card>
      ) : (
        <>
          <section aria-label="Resumo de prazos" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Kpi
              feature
              tone="accent"
              label="Prazos futuros"
              value={<NumberTicker value={(urgencyCounts.ate_7_dias ?? 0) + (urgencyCounts.ate_30_dias ?? 0)} />}
              context={`${integer(urgencyCounts.ate_7_dias ?? 0)} em até 7 dias · ${integer(urgencyCounts.hoje ?? 0)} hoje`}
            />
            <Kpi
              label="Vencidos preservados"
              value={<NumberTicker value={urgencyCounts.vencido ?? 0} />}
              context="Histórico com evidência; não são prazo vigente"
            />
            <Kpi
              label="Sem data"
              value={<NumberTicker value={urgencyCounts.sem_data ?? 0} />}
              context="Campo não localizado ou sem data documental"
            />
            <Kpi
              label="Com conflito"
              value={<NumberTicker value={data?.por_conflito?.conflito ?? 0} />}
              context="Documentos ou versões divergentes"
            />
          </section>

          <Card flush className="mt-3">
            <div className="flex flex-wrap items-end gap-2 border-b border-line p-3">
              <label className="flex flex-col gap-1">
                <span className="text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase">Evento</span>
                <select
                  value={group}
                  onChange={(event) => update('group', event.target.value)}
                  className="h-8 min-w-[170px] rounded-sm border border-line-strong bg-surface-2 px-2.5 text-xs text-fg outline-none focus:border-accent/60"
                >
                  <option value="">Todos os eventos</option>
                  {Object.entries(deadlineGroups).map(([value, text]) => (
                    <option key={value} value={value}>{text}</option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase">Urgência</span>
                <select
                  value={urgency}
                  onChange={(event) => update('urgency', event.target.value)}
                  className="h-8 min-w-[140px] rounded-sm border border-line-strong bg-surface-2 px-2.5 text-xs text-fg outline-none focus:border-accent/60"
                >
                  <option value="">Todas</option>
                  {Object.entries(urgencyLabels).map(([value, text]) => (
                    <option key={value} value={value}>{text}</option>
                  ))}
                </select>
              </label>
              <div className="ml-auto">
                <Button variant="ghost" size="sm" onClick={() => setAdvanced((open) => !open)} aria-expanded={advanced}>
                  {advanced ? 'Menos detalhes' : 'Mais detalhes'}
                </Button>
              </div>
            </div>

            {!items.length ? (
              <EmptyState
                title="Nenhum prazo com esses filtros"
                description="Ajuste o evento ou a urgência. A ausência de prazo não significa inexistência."
                action={
                  <Button size="sm" onClick={() => setParams(new URLSearchParams(), { replace: true })}>
                    Limpar filtros
                  </Button>
                }
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] border-collapse text-xs">
                  <caption className="sr-only">Prazos por evento e urgência</caption>
                  <thead>
                    <tr className="border-b border-line bg-surface-2">
                      {['Evento', 'Data', 'Urgência', 'Situação', 'Documento', ''].map((text) => (
                        <th
                          key={text}
                          scope="col"
                          className="px-3 py-2 text-left text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase"
                        >
                          {text}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item, index) => (
                      <tr key={`${item.contest_id}-${item.grupo}-${index}`} className="border-b border-line/70 last:border-0 hover:bg-white/[0.025]">
                        <td className="px-3 py-2.5 align-top">
                          <span className="block text-[13px] font-medium text-fg">{item.grupo_label}</span>
                          {item.escopo_rotulo && <span className="text-2xs text-fg-3">{item.escopo_rotulo}</span>}
                        </td>
                        <td className="px-3 py-2.5 align-top">
                          <span className="block text-[13px] font-medium tabular text-fg">
                            {item.valor ? date(item.valor) : '—'}
                          </span>
                          {item.dias_restantes !== null && (
                            <span className="text-2xs text-fg-3">{relativeDays(item.dias_restantes)}</span>
                          )}
                        </td>
                        <td className="px-3 py-2.5 align-top">
                          <Badge tone={item.urgencia === 'vencido' ? 'neutral' : item.urgencia === 'ate_7_dias' ? 'risk' : 'warn'}>
                            {item.urgencia_label}
                          </Badge>
                        </td>
                        <td className="max-w-[26ch] px-3 py-2.5 align-top text-2xs text-fg-3">
                          {item.estado_operacional_label}
                          {advanced && item.proxima_acao && (
                            <span className="mt-1 block text-fg-3/80">{item.proxima_acao}</span>
                          )}
                        </td>
                        <td className="px-3 py-2.5 align-top text-2xs text-fg-2">
                          {item.documento ?? 'Não identificado'}
                          {item.pagina ? ` · p. ${item.pagina}` : ''}
                          {advanced && item.trecho && (
                            <span className="mt-1 block text-fg-3">{item.trecho}</span>
                          )}
                        </td>
                        <td className="px-3 py-2.5 text-right align-top">
                          <Link
                            to={`/dossie/${item.contest_id}?tab=prazos`}
                            className="text-2xs font-medium text-accent hover:underline"
                          >
                            Abrir
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
          {data?.limitacao && <p className="mt-2 text-2xs text-fg-3">{data.limitacao}</p>}
        </>
      )}
    </>
  );
}
