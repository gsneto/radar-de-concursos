import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useDeadlines } from '@/app/queries';
import { PageHeader } from '@/components/layout/page-header';
import { Badge } from '@/components/ui/badge';
import { Button, LinkButton } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Kpi, NumberTicker } from '@/components/ui/kpi';
import { EmptyState, ErrorState, SkeletonRows } from '@/components/ui/states';
import { OPERATIONAL_GROUPS } from '@/lib/deadlines';
import { deadlineGroups } from '@/lib/domain';
import { date, integer, relativeDays } from '@/lib/format';

const PAGE_SIZE = 25;

/**
 * Situações mostradas em abas. Antes eram 119 linhas numa lista só, com 81 prazos
 * vencidos empurrando o único prazo futuro para fora da primeira tela.
 */
const TABS = [
  { id: 'proximos', label: 'Próximos', urgencies: ['hoje', 'ate_7_dias', 'ate_30_dias'] },
  { id: 'futuro', label: 'Mais adiante', urgencies: ['futuro'] },
  { id: 'vencidos', label: 'Vencidos', urgencies: ['vencido'] },
  { id: 'sem_data', label: 'Sem data', urgencies: ['sem_data'] },
] as const;

type TabId = (typeof TABS)[number]['id'];

const tabOf = (value: string | null): TabId =>
  TABS.some((tab) => tab.id === value) ? (value as TabId) : 'proximos';

function urgencyTone(urgencia: string): 'risk' | 'warn' | 'neutral' {
  if (urgencia === 'vencido') return 'neutral';
  if (urgencia === 'ate_7_dias' || urgencia === 'hoje') return 'risk';
  return 'warn';
}

export function DeadlinesPage() {
  const [params, setParams] = useSearchParams();
  // Sem escolha explícita, a página abre no recorte que exige ação (inscrição,
  // isenção e prova). "Todos os eventos" continua a um clique, com os resultados.
  const group = params.get('group') ?? 'operacionais';
  const tab = tabOf(params.get('aba'));
  const page = Math.max(1, Number(params.get('pagina') ?? 1) || 1);
  const [advanced, setAdvanced] = useState(false);
  const groups = group === 'operacionais' ? OPERATIONAL_GROUPS : undefined;
  const query = useDeadlines({
    group: group && group !== 'operacionais' ? group : undefined,
    groups,
    limit: 500,
  });
  const data = query.data;

  const update = (changes: Record<string, string | undefined>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (!value) next.delete(key);
      else next.set(key, value);
    }
    setParams(next, { replace: true });
  };

  const urgencyCounts = data?.por_urgencia ?? {};
  const allItems = data?.itens ?? [];
  const activeTab = TABS.find((item) => item.id === tab) ?? TABS[0];

  const tabItems = useMemo(() => {
    const wanted = new Set<string>(activeTab.urgencies);
    return allItems.filter((item) => wanted.has(item.urgencia));
  }, [allItems, activeTab]);

  const pages = Math.max(1, Math.ceil(tabItems.length / PAGE_SIZE));
  const current = Math.min(page, pages);
  const items = tabItems.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);

  const countFor = (entry: (typeof TABS)[number]) =>
    entry.urgencies.reduce((sum, key) => sum + (urgencyCounts[key] ?? 0), 0);

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
          (params.get('group') || params.get('aba')) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setParams(new URLSearchParams(), { replace: true })}
            >
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
              value={
                <NumberTicker
                  value={
                    (urgencyCounts.hoje ?? 0) +
                    (urgencyCounts.ate_7_dias ?? 0) +
                    (urgencyCounts.ate_30_dias ?? 0)
                  }
                />
              }
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
                <span className="text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase">
                  Evento
                </span>
                <select
                  name="grupo"
                  autoComplete="off"
                  value={group}
                  onChange={(event) => update({ group: event.target.value, pagina: undefined })}
                  className="h-8 min-w-[170px] rounded-sm border border-line-strong bg-surface-2 px-2.5 text-xs text-fg outline-none focus:border-accent/60"
                >
                  <option value="operacionais">Inscrição, isenção e prova</option>
                  <option value="">Todos os eventos</option>
                  {Object.entries(deadlineGroups).map(([value, text]) => (
                    <option key={value} value={value}>{text}</option>
                  ))}
                </select>
              </label>
              <div className="ml-auto">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setAdvanced((open) => !open)}
                  aria-expanded={advanced}
                >
                  {advanced ? 'Menos detalhes' : 'Mais detalhes'}
                </Button>
              </div>
            </div>

            <div role="tablist" aria-label="Situação dos prazos" className="flex flex-wrap gap-1 border-b border-line px-2 pt-2">
              {TABS.map((entry) => {
                const selected = entry.id === tab;
                return (
                  <button
                    key={entry.id}
                    type="button"
                    role="tab"
                    aria-selected={selected}
                    aria-controls="prazos-lista"
                    onClick={() => update({ aba: entry.id === 'proximos' ? undefined : entry.id, pagina: undefined })}
                    className={`shrink-0 rounded-t-xs border-b-2 px-3 py-2 text-xs font-medium transition-colors ${
                      selected
                        ? 'border-accent text-fg'
                        : 'border-transparent text-fg-3 hover:text-fg-2'
                    }`}
                  >
                    {entry.label}
                    <span className="ml-1.5 tabular text-2xs text-fg-3">{integer(countFor(entry))}</span>
                  </button>
                );
              })}
            </div>

            <div id="prazos-lista" role="tabpanel">
              {!items.length ? (
                <EmptyState
                  title={tabItems.length ? 'Nada nesta página' : `Nenhum prazo em "${activeTab.label}"`}
                  description="Ajuste o evento ou a situação. A ausência de prazo não significa inexistência."
                  action={
                    <Button
                      size="sm"
                      onClick={() => setParams(new URLSearchParams(), { replace: true })}
                    >
                      Limpar filtros
                    </Button>
                  }
                />
              ) : (
                <>
                  {/* Abaixo de 768px: cartões, sem rolagem lateral (spec §9). */}
                  <ul className="divide-y divide-line/70 md:hidden">
                    {items.map((item, index) => (
                      <li key={`${item.contest_id}-${item.grupo}-${index}`} className="p-3">
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="truncate text-[13px] font-medium text-fg">{item.grupo_label}</p>
                            {item.escopo_rotulo && (
                              <p className="truncate text-2xs text-fg-3">{item.escopo_rotulo}</p>
                            )}
                          </div>
                          <LinkButton
                            to={`/dossie/${item.contest_id}?tab=prazos`}
                            variant="ghost"
                            size="sm"
                          >
                            Abrir
                          </LinkButton>
                        </div>
                        <div className="mt-2 flex flex-wrap items-center gap-1.5">
                          <span className="text-[13px] font-medium tabular text-fg">
                            {item.valor ? date(item.valor) : '—'}
                          </span>
                          {item.dias_restantes !== null && (
                            <span className="text-2xs text-fg-3">
                              {relativeDays(item.dias_restantes)}
                            </span>
                          )}
                          <Badge tone={urgencyTone(item.urgencia)}>{item.urgencia_label}</Badge>
                        </div>
                        <p className="mt-1 text-2xs text-fg-3">
                          {item.estado_operacional_label}
                          {item.documento ? ` · ${item.documento}` : ''}
                          {item.pagina ? ` · p. ${item.pagina}` : ''}
                        </p>
                        {advanced && item.proxima_acao && (
                          <p className="mt-1 text-2xs text-fg-3">{item.proxima_acao}</p>
                        )}
                        {advanced && item.trecho && (
                          <p className="mt-1 text-2xs text-fg-2">{item.trecho}</p>
                        )}
                      </li>
                    ))}
                  </ul>

                  <div className="hidden overflow-x-auto md:block">
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
                          <tr
                            key={`${item.contest_id}-${item.grupo}-${index}`}
                            className="border-b border-line/70 last:border-0 hover:bg-white/[0.025]"
                          >
                            <td className="px-3 py-2.5 align-top">
                              <span className="block text-[13px] font-medium text-fg">{item.grupo_label}</span>
                              {item.escopo_rotulo && (
                                <span className="text-2xs text-fg-3">{item.escopo_rotulo}</span>
                              )}
                            </td>
                            <td className="px-3 py-2.5 align-top">
                              <span className="block text-[13px] font-medium tabular text-fg">
                                {item.valor ? date(item.valor) : '—'}
                              </span>
                              {item.dias_restantes !== null && (
                                <span className="text-2xs text-fg-3">
                                  {relativeDays(item.dias_restantes)}
                                </span>
                              )}
                            </td>
                            <td className="px-3 py-2.5 align-top">
                              <Badge tone={urgencyTone(item.urgencia)}>{item.urgencia_label}</Badge>
                            </td>
                            <td className="max-w-[26ch] px-3 py-2.5 align-top text-2xs text-fg-3">
                              {item.estado_operacional_label}
                              {advanced && item.proxima_acao && (
                                <span className="mt-1 block text-fg-3">{item.proxima_acao}</span>
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
                </>
              )}
            </div>

            {pages > 1 && (
              <nav
                aria-label="Paginação de prazos"
                className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-3 py-2 text-2xs text-fg-3"
              >
                <span className="tabular">
                  Página {current} de {pages} · {integer(tabItems.length)} prazo(s)
                </span>
                <div className="flex items-center gap-1.5">
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={current <= 1}
                    onClick={() => update({ pagina: String(current - 1) })}
                  >
                    Anterior
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={current >= pages}
                    onClick={() => update({ pagina: String(current + 1) })}
                  >
                    Próxima
                  </Button>
                </div>
              </nav>
            )}
          </Card>

          {data?.has_more && (
            <p className="mt-2 text-2xs text-fg-3">
              Mostrando os primeiros {integer(data.limit)} prazos; refine o evento para ver o resto.
            </p>
          )}
          {data?.limitacao && <p className="mt-2 text-2xs text-fg-3">{data.limitacao}</p>}
        </>
      )}
    </>
  );
}
