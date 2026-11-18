import { Building2, ExternalLink, FileText, Radar, Search, Sparkles } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useOrganizers } from '@/app/queries';
import { EmptyState, SkeletonRows } from '@/components/ui/states';
import { cn } from '@/lib/cn';

const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');

const GROUPS = [
  { id: '', label: 'Todas as Categorias' },
  { id: 'nacional', label: 'Nacionais & Tradicionais' },
  { id: 'federal_if_uf', label: 'IFs, CEFETs & Universidades' },
  { id: 'regional_municipal', label: 'Regionais, Estaduais & Municipais' },
  { id: 'raio_x', label: '★ Com Raio-X Estratégico TI' },
] as const;

export function OrganizersDirectorySection({
  onOpenRaioX,
}: {
  onOpenRaioX: (raioXId: string) => void;
}) {
  const [selectedLetter, setSelectedLetter] = useState<string>('');
  const [selectedGroup, setSelectedGroup] = useState<string>('');
  const [search, setSearch] = useState<string>('');

  const query = useOrganizers({
    letra: selectedLetter || undefined,
    grupo: selectedGroup && selectedGroup !== 'raio_x' ? selectedGroup : undefined,
    com_raio_x: selectedGroup === 'raio_x' ? true : undefined,
    q: search.trim() || undefined,
    limit: 500,
  });

  const data = query.data;
  const items = data?.itens ?? [];
  const letterCounts = data?.letras ?? {};

  return (
    <div className="space-y-4">
      {/* Painel de Filtros A-Z + Categorias + Busca */}
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-xs space-y-3.5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="font-display text-base font-bold text-fg flex items-center gap-2">
              <Building2 size={16} className="text-accent-ink" />
              Lista Completa de Organizadoras (A–Z)
            </h3>
            <p className="text-xs text-fg-3">
              Catálogo unificado estilo PCI Concursos com reconciliação de siglas, editais no Radar e provas vinculadas.
            </p>
          </div>

          <div className="relative w-full sm:w-72">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-fg-3" />
            <input
              type="search"
              aria-label="Buscar organizadora no diretório A-Z"
              placeholder="Filtrar organizadora (ex: FGV, UNIVASF, AOCP)..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-lg border border-line bg-surface-2 pl-8 pr-3 py-1.5 text-xs text-fg placeholder:text-fg-3 focus:border-accent focus:outline-none"
            />
          </div>
        </div>

        {/* Barra A-Z estilo PCI */}
        <div className="flex flex-wrap items-center gap-1 border-t border-line/60 pt-3">
          <button
            type="button"
            onClick={() => setSelectedLetter('')}
            className={cn(
              'rounded px-2.5 py-1 text-2xs font-bold border transition-colors',
              selectedLetter === ''
                ? 'border-accent bg-accent text-white'
                : 'border-line bg-surface-2 text-fg-2 hover:text-fg',
            )}
          >
            Todas
          </button>
          {ALPHABET.map((letter) => {
            const count = letterCounts[letter] ?? 0;
            const active = selectedLetter === letter;
            return (
              <button
                key={letter}
                type="button"
                disabled={count === 0 && !selectedLetter}
                onClick={() => setSelectedLetter(active ? '' : letter)}
                className={cn(
                  'min-w-[26px] rounded px-1.5 py-1 font-mono text-2xs font-bold border transition-colors',
                  active
                    ? 'border-accent bg-accent text-white'
                    : count > 0
                      ? 'border-line/70 bg-surface-2/60 text-fg-2 hover:border-accent/50 hover:text-accent-ink'
                      : 'border-line/30 bg-surface-2/20 text-fg-3/40 cursor-not-allowed',
                )}
                title={`${letter}: ${count} organizadoras`}
              >
                {letter}
              </button>
            );
          })}
        </div>

        {/* Filtro por porte/natureza */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line/60 pt-3">
          <div className="flex flex-wrap gap-1.5">
            {GROUPS.map((grp) => (
              <button
                key={grp.id || 'all'}
                type="button"
                onClick={() => setSelectedGroup(grp.id)}
                className={cn(
                  'rounded-lg px-2.5 py-1 text-2xs font-semibold border transition-colors',
                  selectedGroup === grp.id
                    ? 'border-accent/50 bg-accent/15 text-accent-ink font-bold'
                    : 'border-line/70 bg-surface-2/50 text-fg-3 hover:text-fg',
                )}
              >
                {grp.label}
              </button>
            ))}
          </div>

          <span className="text-2xs text-fg-3 font-medium">
            Exibindo <strong className="text-fg">{items.length}</strong> organizadoras
          </span>
        </div>
      </div>

      {/* Listagem em Colunas Limpas */}
      {query.isLoading ? (
        <SkeletonRows rows={6} />
      ) : items.length === 0 ? (
        <EmptyState
          title="Nenhuma organizadora encontrada"
          description="Ajuste a letra inicial, a categoria ou o termo pesquisado."
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2.5">
          {items.map((org) => (
            <div
              key={org.slug}
              className="flex flex-col justify-between rounded-xl border border-line bg-surface p-3 hover:border-line-strong transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="font-semibold text-xs text-fg truncate">{org.nome}</span>
                    {org.tem_raio_x_ti && (
                      <span className="inline-flex items-center gap-0.5 rounded bg-emerald-500/15 border border-emerald-500/30 px-1.5 py-0.5 text-[9px] font-bold uppercase text-ok-ink">
                        <Sparkles size={9} /> Raio-X TI
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 text-[11px] text-fg-3">{org.grupo_label}</p>
                </div>

                <a
                  href={org.pci_url}
                  target="_blank"
                  rel="noreferrer"
                  className="shrink-0 inline-flex items-center gap-1 rounded border border-line/70 bg-surface-2 px-1.5 py-0.5 text-[10px] font-medium text-fg-3 hover:text-accent-ink hover:border-accent/40"
                  title={`Página de referência PCI: ${org.nome}`}
                >
                  PCI <ExternalLink size={10} />
                </a>
              </div>

              <div className="mt-2.5 pt-2 border-t border-line/50 flex flex-wrap items-center justify-between gap-2 text-2xs">
                <div className="flex items-center gap-2 text-fg-3">
                  <span>{org.provas_count} provas</span>
                  <span>·</span>
                  <span>{org.questoes_count} questões</span>
                  {org.concursos_count > 0 && (
                    <>
                      <span>·</span>
                      <span className="text-ok-ink font-semibold">{org.concursos_count} no radar</span>
                    </>
                  )}
                </div>

                <div className="flex items-center gap-1.5">
                  {org.tem_raio_x_ti && org.raio_x_id && (
                    <button
                      type="button"
                      onClick={() => onOpenRaioX(org.raio_x_id!)}
                      className="rounded border border-accent/40 bg-accent/10 px-2 py-0.5 text-[10px] font-bold text-accent-ink hover:bg-accent hover:text-white transition-colors"
                    >
                      DNA TI
                    </button>
                  )}
                  <Link
                    to={`/estudos/provas?banca=${encodeURIComponent(org.slug)}`}
                    className="inline-flex items-center gap-1 rounded border border-line bg-surface-2 px-2 py-0.5 text-[10px] font-semibold text-fg-2 hover:text-fg"
                  >
                    <FileText size={10} /> Provas
                  </Link>
                  <Link
                    to={`/oportunidades?q=${encodeURIComponent(org.nome)}`}
                    className="inline-flex items-center gap-1 rounded border border-line bg-surface-2 px-2 py-0.5 text-[10px] font-semibold text-fg-2 hover:text-fg"
                  >
                    <Radar size={10} /> Radar
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
