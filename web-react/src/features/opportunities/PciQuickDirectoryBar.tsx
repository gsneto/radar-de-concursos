import { Building2, Compass, FileText, GraduationCap, MapPin, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/cn';

export type RegionKey = 'nacional' | 'nordeste' | 'sudeste' | 'sul' | 'norte' | 'centro_oeste' | 'meu_raio';

export const REGION_UFS: Record<Exclude<RegionKey, 'nacional'>, string[]> = {
  meu_raio: ['BA', 'PE', 'AL', 'SE'],
  nordeste: ['AL', 'BA', 'CE', 'MA', 'PB', 'PE', 'PI', 'RN', 'SE'],
  sudeste: ['ES', 'MG', 'RJ', 'SP'],
  sul: ['PR', 'RS', 'SC'],
  norte: ['AC', 'AM', 'AP', 'PA', 'RO', 'RR', 'TO'],
  centro_oeste: ['DF', 'GO', 'MS', 'MT'],
};

export const REGION_LABELS: Record<RegionKey, string> = {
  nacional: 'Nacional',
  meu_raio: 'Meu Raio (BA/PE/AL/SE)',
  nordeste: 'Nordeste',
  sudeste: 'Sudeste',
  sul: 'Sul',
  norte: 'Norte',
  centro_oeste: 'Centro-Oeste',
};

const CAREER_SHORTCUTS = [
  { id: 'ti', label: 'TI & SI', core: true, query: undefined },
  { id: 'administrativa', label: 'Administrativa', core: false, query: 'administrativo' },
  { id: 'fiscal', label: 'Fiscal & Controle', core: false, query: 'auditor' },
  { id: 'tribunais', label: 'Tribunais', core: false, query: 'judiciario' },
  { id: 'policial', label: 'Policial', core: false, query: 'policia' },
  { id: 'educacao', label: 'Educação & IFs', core: false, query: 'professor' },
] as const;

interface PciQuickDirectoryBarProps {
  activeRegion: RegionKey;
  activeUf?: string;
  activeSi?: string;
  activeQuery?: string;
  onSelectRegion: (region: RegionKey) => void;
  onSelectUf: (uf: string | undefined) => void;
  onSelectCareer: (career: { id: string; core: boolean; query?: string }) => void;
}

export function PciQuickDirectoryBar({
  activeRegion,
  activeUf,
  activeSi,
  activeQuery,
  onSelectRegion,
  onSelectUf,
  onSelectCareer,
}: PciQuickDirectoryBarProps) {
  const regionStates = activeRegion !== 'nacional' ? REGION_UFS[activeRegion] : null;
  const isTiActive = activeSi === 'explicito' || activeSi === 'categoria_inclui_curso';

  return (
    <section
      aria-label="Diretório rápido por região e carreira"
      className="mb-4 rounded-xl border border-line bg-surface p-3 shadow-xs space-y-2.5"
    >
      {/* Linha 1: Regiões estilo PCI + Atalhos diretos de Provas e Organizadoras */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="inline-flex items-center gap-1 pr-1 text-2xs font-bold uppercase tracking-wider text-fg-3">
            <MapPin size={12} className="text-accent-ink" /> Região:
          </span>
          {(Object.keys(REGION_LABELS) as RegionKey[]).map((key) => {
            const selected = activeRegion === key && !activeUf;
            const selectedWithUf = activeRegion === key && Boolean(activeUf);
            return (
              <button
                key={key}
                type="button"
                onClick={() => onSelectRegion(key)}
                className={cn(
                  'rounded-md px-2.5 py-1 text-xs font-medium transition-colors border',
                  selected || selectedWithUf
                    ? 'border-accent/50 bg-accent/15 text-accent-ink font-semibold'
                    : 'border-line/70 bg-surface-2/60 text-fg-2 hover:border-line-strong hover:text-fg',
                )}
              >
                {key === 'meu_raio' ? (
                  <span className="inline-flex items-center gap-1">
                    <Compass size={11} /> {REGION_LABELS[key]}
                  </span>
                ) : (
                  REGION_LABELS[key]
                )}
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-1.5 text-2xs">
          <Link
            to="/estudos/provas"
            className="inline-flex items-center gap-1 rounded-md border border-line bg-surface-2 px-2.5 py-1 font-semibold text-fg-2 hover:border-accent/40 hover:text-accent-ink transition-colors"
          >
            <FileText size={12} /> Provas Anteriores
          </Link>
          <Link
            to="/estudos/bancas?modo=diretorio"
            className="inline-flex items-center gap-1 rounded-md border border-line bg-surface-2 px-2.5 py-1 font-semibold text-fg-2 hover:border-accent/40 hover:text-accent-ink transition-colors"
          >
            <Building2 size={12} /> 348 Organizadoras
          </Link>
        </div>
      </div>

      {/* Sub-barra de UFs quando uma região específica está ativa */}
      {regionStates && (
        <div className="flex flex-wrap items-center gap-1.5 border-t border-line/60 pt-2">
          <span className="text-2xs font-semibold text-fg-3 pr-1">
            Estados ({REGION_LABELS[activeRegion]}):
          </span>
          <button
            type="button"
            onClick={() => onSelectUf(undefined)}
            className={cn(
              'rounded px-2 py-0.5 text-2xs font-semibold border transition-colors',
              !activeUf
                ? 'border-accent/50 bg-accent/15 text-accent-ink'
                : 'border-line/60 bg-surface-2/40 text-fg-3 hover:text-fg',
            )}
          >
            Toda a região
          </button>
          {regionStates.map((uf) => (
            <button
              key={uf}
              type="button"
              onClick={() => onSelectUf(activeUf === uf ? undefined : uf)}
              className={cn(
                'rounded px-2 py-0.5 font-mono text-2xs font-bold border transition-colors',
                activeUf === uf
                  ? 'border-accent bg-accent text-white'
                  : 'border-line/60 bg-surface-2/50 text-fg-2 hover:border-line-strong hover:text-fg',
              )}
            >
              {uf}
            </button>
          ))}
        </div>
      )}

      {/* Linha 2: Carreiras (TI como núcleo profundo + demais áreas catalogadas para expansão) */}
      <div className="flex flex-wrap items-center gap-1.5 border-t border-line/60 pt-2">
        <span className="inline-flex items-center gap-1 pr-1 text-2xs font-bold uppercase tracking-wider text-fg-3">
          <GraduationCap size={12} className="text-ok-ink" /> Carreira:
        </span>
        {CAREER_SHORTCUTS.map((career) => {
          const active = career.core
            ? isTiActive
            : Boolean(career.query && activeQuery?.toLowerCase() === career.query);
          return (
            <button
              key={career.id}
              type="button"
              onClick={() => onSelectCareer(career)}
              className={cn(
                'inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-2xs font-medium border transition-colors',
                active
                  ? career.core
                    ? 'border-emerald-500/50 bg-emerald-500/15 text-ok-ink font-bold'
                    : 'border-accent/50 bg-accent/15 text-accent-ink font-bold'
                  : 'border-line/60 bg-surface-2/40 text-fg-3 hover:border-line hover:text-fg',
              )}
            >
              {career.core && <Sparkles size={11} className="text-ok-ink" />}
              <span>{career.label}</span>
              {career.core ? (
                <span className="rounded bg-emerald-500/15 px-1 text-[9px] font-bold uppercase text-ok-ink">
                  Foco
                </span>
              ) : (
                <span className="text-[9px] opacity-70">expansão</span>
              )}
            </button>
          );
        })}
      </div>
    </section>
  );
}
