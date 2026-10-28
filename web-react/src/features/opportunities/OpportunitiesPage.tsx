import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Search, SlidersHorizontal, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { usePortfolio, type PortfolioFilters } from '@/app/queries';
import { PageHeader } from '@/components/layout/page-header';
import { Badge } from '@/components/ui/badge';
import { Button, LinkButton } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { EmptyState, ErrorState, SkeletonRows } from '@/components/ui/states';
import {
  documentalLabels,
  indigenousLabels,
  indigenousShort,
  indigenousTones,
  readinessLabels,
  readinessTones,
  siLabels,
  siShort,
  siTones,
  urgencyLabels,
} from '@/lib/domain';
import { nextOperationalDeadline } from '@/lib/deadlines';
import { integer, relativeDays, shortDate } from '@/lib/format';
import type { Deadline, Opportunity } from '@/lib/types';

const PAGE_SIZE = 20;
const UFS = [
  'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG', 'PA',
  'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO',
];

type SortKey = 'prioridade' | 'prazo' | 'atualizacao' | 'concurso';

const sortLabels: Record<SortKey, string> = {
  prioridade: 'Prioridade (servidor)',
  prazo: 'Prazo (página)',
  atualizacao: 'Atualização (página)',
  concurso: 'Concurso (página)',
};

// Só prazo que exige ação: recurso/resultado de isenção não é o prazo da oportunidade.
const nextDeadline = (item: Opportunity): Deadline | null =>
  nextOperationalDeadline(item.prazos);

function dossierLink(item: Opportunity): string {
  const params = new URLSearchParams();
  if (item.scope) params.set('scope', item.scope);
  params.set('from', 'oportunidades');
  return `/dossie/${item.contest_id}${params.size ? `?${params}` : ''}`;
}

function locationText(item: Opportunity): string {
  const prova = item.localizacao?.prova;
  if (prova?.text) return prova.text;
  if (prova?.uf) return prova.uf;
  if (prova?.state === 'a_divulgar') return 'A divulgar';
  return 'Não informado';
}

export function OpportunitiesPage() {
  const [params, setParams] = useSearchParams();
  const [searchDraft, setSearchDraft] = useState(params.get('q') ?? '');
  const [advanced, setAdvanced] = useState(
    Boolean(params.get('documental') || params.get('conflito')),
  );

  const filters: PortfolioFilters = useMemo(
    () => ({
      q: params.get('q') ?? undefined,
      uf: params.get('uf') ?? undefined,
      prontidao: params.get('prontidao') ?? undefined,
      si: params.get('si') ?? undefined,
      indigena: params.get('indigena') ?? undefined,
      prazo: params.get('prazo') ?? undefined,
      documental: params.get('documental') ?? undefined,
      conflito: params.get('conflito') ?? undefined,
      offset: Number(params.get('offset') ?? 0) || 0,
      limit: PAGE_SIZE,
    }),
    [params],
  );

  const sort = (params.get('sort') as SortKey) ?? 'prioridade';
  const query = usePortfolio(filters);
  const total = query.data?.total ?? 0;
  const offset = filters.offset ?? 0;

  const items = useMemo(() => {
    const list = [...(query.data?.itens ?? [])];
    if (sort === 'prazo') {
      list.sort((a, b) => {
        const da = nextDeadline(a)?.dias_restantes ?? 9999;
        const db = nextDeadline(b)?.dias_restantes ?? 9999;
        return da - db;
      });
    } else if (sort === 'atualizacao') {
      list.sort((a, b) => String(b.ultima_atualizacao ?? '').localeCompare(String(a.ultima_atualizacao ?? '')));
    } else if (sort === 'concurso') {
      list.sort((a, b) => String(a.contest_label ?? '').localeCompare(String(b.contest_label ?? '')));
    }
    return list;
  }, [query.data, sort]);

  const update = (changes: Record<string, string | undefined>, resetOffset = true) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (!value) next.delete(key);
      else next.set(key, value);
    }
    if (resetOffset) next.delete('offset');
    if (sort !== 'prioridade') next.set('sort', sort);
    setParams(next, { replace: true });
  };

  const clearAll = () => {
    setSearchDraft('');
    setParams(new URLSearchParams(), { replace: true });
  };

  const activeChips = useMemo(() => {
    const chips: { key: string; label: string; value: string }[] = [];
    if (filters.q) chips.push({ key: 'q', label: `Busca: ${filters.q}`, value: filters.q });
    if (filters.uf) chips.push({ key: 'uf', label: `UF: ${filters.uf}`, value: filters.uf });
    if (filters.prontidao)
      chips.push({ key: 'prontidao', label: readinessLabels[filters.prontidao] ?? filters.prontidao, value: filters.prontidao });
    if (filters.si) chips.push({ key: 'si', label: `SI: ${siShort[filters.si] ?? filters.si}`, value: filters.si });
    if (filters.indigena)
      chips.push({ key: 'indigena', label: `Indígena: ${indigenousShort[filters.indigena] ?? filters.indigena}`, value: filters.indigena });
    if (filters.prazo) chips.push({ key: 'prazo', label: `Prazo: ${urgencyLabels[filters.prazo] ?? filters.prazo}`, value: filters.prazo });
    if (filters.documental)
      chips.push({ key: 'documental', label: documentalLabels[filters.documental] ?? filters.documental, value: filters.documental });
    if (filters.conflito)
      chips.push({ key: 'conflito', label: filters.conflito === 'sim' ? 'Com conflito' : 'Sem conflito', value: filters.conflito });
    return chips;
  }, [filters]);

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const page = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <>
      <PageHeader
        eyebrow="Busca"
        title="Oportunidades"
        description="Cada linha é um concurso e cargo com documento oficial, lacunas explícitas e próxima ação. A busca nacional não é limitada pelas preferências regionais."
        actions={
          activeChips.length > 0 ? (
            <Button variant="ghost" size="sm" onClick={clearAll}>
              <X size={13} /> Limpar filtros
            </Button>
          ) : null
        }
      />

      <Card flush className="mb-3">
        <div className="border-b border-line p-3">
          <form
            className="relative"
            onSubmit={(event) => {
              event.preventDefault();
              update({ q: searchDraft.trim() || undefined });
            }}
          >
            <Search size={15} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-fg-3" />
            <input
              type="search"
              name="busca"
              autoComplete="off"
              spellCheck={false}
              value={searchDraft}
              onChange={(event) => setSearchDraft(event.target.value)}
              placeholder="Buscar por concurso, órgão, cargo ou especialidade"
              aria-label="Buscar oportunidades"
              className="h-10 w-full rounded-sm border border-line-strong bg-surface-2 pr-3 pl-9 text-sm text-fg outline-none transition-colors placeholder:text-fg-3 focus:border-accent/60"
            />
          </form>
        </div>

        <div className="flex flex-wrap items-end gap-2 p-3">
          <Filter label="UF" value={filters.uf ?? ''} onChange={(value) => update({ uf: value })}>
            <option value="">Todas</option>
            {UFS.map((uf) => (
              <option key={uf} value={uf}>{uf}</option>
            ))}
          </Filter>
          <Filter label="Prontidão" value={filters.prontidao ?? ''} onChange={(value) => update({ prontidao: value })}>
            <option value="">Todas</option>
            {Object.entries(readinessLabels).map(([value, text]) => (
              <option key={value} value={value}>{text}</option>
            ))}
          </Filter>
          <Filter label="Sistemas de Informação" value={filters.si ?? ''} onChange={(value) => update({ si: value })}>
            <option value="">Todas</option>
            {Object.entries(siLabels).map(([value, text]) => (
              <option key={value} value={value}>{text}</option>
            ))}
          </Filter>
          <Filter label="Reserva indígena" value={filters.indigena ?? ''} onChange={(value) => update({ indigena: value })}>
            <option value="">Todas</option>
            {Object.entries(indigenousLabels).map(([value, text]) => (
              <option key={value} value={value}>{text}</option>
            ))}
          </Filter>
          <Filter label="Prazo" value={filters.prazo ?? ''} onChange={(value) => update({ prazo: value })}>
            <option value="">Todos</option>
            {Object.entries(urgencyLabels).map(([value, text]) => (
              <option key={value} value={value}>{text}</option>
            ))}
          </Filter>

          <div className="ml-auto flex items-end gap-2">
            <Filter label="Ordenar" value={sort} onChange={(value) => update({ sort: value === 'prioridade' ? undefined : value }, false)}>
              {Object.entries(sortLabels).map(([value, text]) => (
                <option key={value} value={value}>{text}</option>
              ))}
            </Filter>
            <Button variant="ghost" size="sm" onClick={() => setAdvanced((open) => !open)} aria-expanded={advanced}>
              <SlidersHorizontal size={13} /> Avançados
            </Button>
          </div>
        </div>

        {advanced && (
          <div className="flex flex-wrap items-end gap-2 border-t border-line p-3">
            <Filter label="Situação documental" value={filters.documental ?? ''} onChange={(value) => update({ documental: value })}>
              <option value="">Todas</option>
              {Object.entries(documentalLabels).map(([value, text]) => (
                <option key={value} value={value}>{text}</option>
              ))}
            </Filter>
            <Filter label="Conflito" value={filters.conflito ?? ''} onChange={(value) => update({ conflito: value })}>
              <option value="">Todos</option>
              <option value="sim">Com conflito</option>
              <option value="nao">Sem conflito</option>
            </Filter>
          </div>
        )}

        {activeChips.length > 0 && (
          <div className="flex flex-wrap gap-1.5 border-t border-line px-3 py-2">
            {activeChips.map((chip) => (
              <span
                key={chip.key}
                className="inline-flex items-center gap-1.5 rounded-full border border-accent/25 bg-accent-soft py-0.5 pr-1 pl-2.5 text-2xs font-medium text-accent"
              >
                {chip.label}
                <button
                  type="button"
                  onClick={() => {
                    if (chip.key === 'q') setSearchDraft('');
                    update({ [chip.key]: undefined });
                  }}
                  aria-label={`Remover filtro ${chip.label}`}
                  className="grid size-4 place-items-center rounded-full hover:bg-accent/20"
                >
                  <X size={10} />
                </button>
              </span>
            ))}
          </div>
        )}
      </Card>

      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-2xs text-fg-3">
        <span>
          <strong className="font-medium tabular text-fg">
            {query.isLoading ? '…' : integer(total)}
          </strong>{' '}
          {total === 1 ? 'oportunidade' : 'oportunidades'}
          {activeChips.length > 0 ? ' com os filtros aplicados' : ''}
        </span>
        <span>Prioridade segue a ordem determinística do servidor.</span>
      </div>

      {query.isLoading ? (
        <Card>
          <SkeletonRows rows={8} />
        </Card>
      ) : query.isError ? (
        <Card>
          <ErrorState message={query.error.message} onRetry={() => query.refetch()} />
        </Card>
      ) : !items.length ? (
        <Card>
          <EmptyState
            title="Nenhuma oportunidade com esses filtros"
            description="Ajuste a busca ou remova filtros. A ausência de resultado não significa ausência de concursos."
            action={<Button size="sm" onClick={clearAll}>Limpar filtros</Button>}
          />
        </Card>
      ) : (
        <>
          <Card flush>
            {/* Abaixo de 768px a tabela vira lista de cartões (spec §9): sem rolagem lateral. */}
            <ul className="divide-y divide-line/70 md:hidden">
              {items.map((item) => {
                const deadline = nextDeadline(item);
                return (
                  <li key={`${item.contest_id}-${item.scope}`} className="p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <Link
                          to={dossierLink(item)}
                          className="block truncate text-[13px] font-medium text-fg hover:text-accent"
                        >
                          {item.contest_label ?? item.competition_id ?? 'Concurso'}
                        </Link>
                        <span className="mt-0.5 block truncate text-2xs text-fg-3">
                          {item.role_name ?? 'Cargo não reconciliado'}
                        </span>
                      </div>
                      <LinkButton to={dossierLink(item)} variant="ghost" size="sm">
                        Abrir
                      </LinkButton>
                    </div>

                    <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1.5 text-2xs">
                      <div className="col-span-2">
                        <dt className="text-fg-3">Local</dt>
                        <dd className="text-fg-2">{locationText(item)}</dd>
                      </div>
                      <div className="col-span-2">
                        <dt className="text-fg-3">Prazo</dt>
                        <dd className="text-fg">
                          {deadline ? (
                            <>
                              {deadline.grupo_label}{' '}
                              <span className="text-fg-3">
                                {shortDate(deadline.valor)} · {relativeDays(deadline.dias_restantes)}
                              </span>
                            </>
                          ) : (
                            <span className="text-fg-3">Sem prazo futuro</span>
                          )}
                        </dd>
                      </div>
                    </dl>

                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <Badge tone={siTones[item.si.estado] ?? 'neutral'}>
                        {siShort[item.si.estado] ?? item.si.estado}
                      </Badge>
                      <Badge tone={indigenousTones[item.indigenas.estado] ?? 'neutral'}>
                        {indigenousShort[item.indigenas.estado] ?? item.indigenas.estado}
                      </Badge>
                      <Badge tone={readinessTones[item.prontidao.estado] ?? 'unknown'}>
                        {item.prontidao.estado_label}
                      </Badge>
                    </div>
                  </li>
                );
              })}
            </ul>

            <div className="hidden overflow-x-auto md:block">
              <table className="w-full min-w-[760px] border-collapse text-xs">
                <caption className="sr-only">Lista de oportunidades</caption>
                <thead>
                  <tr className="border-b border-line bg-surface-2">
                    {[
                      ['Oportunidade', 'concurso'],
                      ['Local', null],
                      ['Prazo', 'prazo'],
                      ['Formação', null],
                      ['Reserva', null],
                      ['Situação', null],
                      ['', null],
                    ].map(([text, key]) => (
                      <th
                        key={String(text)}
                        scope="col"
                        aria-sort={key && sort === key ? 'ascending' : undefined}
                        className="px-3 py-2 text-left text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase whitespace-nowrap"
                      >
                        {key ? (
                          <button
                            type="button"
                            onClick={() => update({ sort: sort === key ? undefined : key }, false)}
                            className="inline-flex items-center gap-1 uppercase hover:text-fg-2"
                          >
                            {text}
                            {sort === key ? (
                              <ArrowUp size={10} />
                            ) : (
                              <ArrowDown size={10} className="opacity-30" />
                            )}
                          </button>
                        ) : (
                          text
                        )}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => {
                    const deadline = nextDeadline(item);
                    return (
                      <tr
                        key={`${item.contest_id}-${item.scope}`}
                        className="border-b border-line/70 transition-colors last:border-0 hover:bg-white/[0.025]"
                      >
                        <td className="px-3 py-2.5 align-top">
                          <Link
                            to={dossierLink(item)}
                            className="block max-w-[34ch] truncate text-[13px] font-medium text-fg hover:text-accent"
                          >
                            {item.contest_label ?? item.competition_id ?? 'Concurso'}
                          </Link>
                          <span className="mt-0.5 block max-w-[38ch] truncate text-2xs text-fg-3">
                            {item.role_name ?? 'Cargo não reconciliado'}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 align-top text-2xs text-fg-2">{locationText(item)}</td>
                        <td className="px-3 py-2.5 align-top">
                          {deadline ? (
                            <>
                              <span className="block text-[13px] font-medium text-fg">
                                {deadline.grupo_label}
                              </span>
                              <span className="mt-0.5 block text-2xs text-fg-3">
                                {shortDate(deadline.valor)} · {relativeDays(deadline.dias_restantes)}
                              </span>
                            </>
                          ) : (
                            <span className="text-2xs text-fg-3">Sem prazo futuro</span>
                          )}
                        </td>
                        <td className="px-3 py-2.5 align-top">
                          <Badge tone={siTones[item.si.estado] ?? 'neutral'}>
                            {siShort[item.si.estado] ?? item.si.estado}
                          </Badge>
                        </td>
                        <td className="px-3 py-2.5 align-top">
                          <Badge tone={indigenousTones[item.indigenas.estado] ?? 'neutral'}>
                            {indigenousShort[item.indigenas.estado] ?? item.indigenas.estado}
                          </Badge>
                        </td>
                        <td className="px-3 py-2.5 align-top">
                          <Badge tone={readinessTones[item.prontidao.estado] ?? 'unknown'}>
                            {item.prontidao.estado_label}
                          </Badge>
                        </td>
                        <td className="px-3 py-2.5 text-right align-top">
                          <LinkButton to={dossierLink(item)} variant="ghost" size="sm">
                            Abrir
                          </LinkButton>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>

          <nav
            aria-label="Paginação de oportunidades"
            className="mt-3 flex flex-wrap items-center justify-between gap-2 text-2xs text-fg-3"
          >
            <span className="tabular">
              Página {page} de {pages} · {integer(total)} resultado(s)
            </span>
            <div className="flex items-center gap-1.5">
              <Button
                variant="ghost"
                size="sm"
                disabled={offset === 0}
                onClick={() => update({ offset: String(Math.max(0, offset - PAGE_SIZE)) }, false)}
              >
                <ChevronLeft size={13} /> Anterior
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={offset + PAGE_SIZE >= total}
                onClick={() => update({ offset: String(offset + PAGE_SIZE) }, false)}
              >
                Próxima <ChevronRight size={13} />
              </Button>
            </div>
          </nav>
        </>
      )}
    </>
  );
}

function Filter({
  label,
  value,
  onChange,
  children,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: React.ReactNode;
}) {
  return (
    <label className="flex min-w-0 flex-col gap-1">
      <span className="text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase">{label}</span>
      <select
        name={label.toLowerCase().replace(/\s+/g, '-')}
        autoComplete="off"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-8 min-w-[124px] appearance-none rounded-sm border border-line-strong bg-surface-2 bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20width%3D%2210%22%20height%3D%2210%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%2366738a%22%20stroke-width%3D%222%22%3E%3Cpath%20d%3D%22M6%209l6%206%206-6%22/%3E%3C/svg%3E')] bg-[position:right_8px_center] bg-no-repeat pr-7 pl-2.5 text-xs text-fg outline-none transition-colors focus:border-accent/60"
      >
        {children}
      </select>
    </label>
  );
}
