import { Menu, Search, Settings2 } from 'lucide-react';
import { Link, useLocation, useMatches } from 'react-router-dom';
import { cn } from '@/lib/cn';

interface TopbarProps {
  onOpenMobile: () => void;
  onOpenPalette: () => void;
}

interface RouteHandle {
  title?: string;
  crumb?: string;
}

export function Topbar({ onOpenMobile, onOpenPalette }: TopbarProps) {
  const matches = useMatches();
  const location = useLocation();
  const handle = [...matches].reverse().find((match) => (match.handle as RouteHandle)?.title)
    ?.handle as RouteHandle | undefined;
  const title = handle?.title ?? 'GSN Concursos';
  const crumb = handle?.crumb ?? title;
  const isHome = location.pathname === '/';

  return (
    <header className="sticky top-0 z-30 flex h-[60px] shrink-0 items-center gap-3 border-b border-line bg-bg/85 px-4 backdrop-blur-md lg:px-6">
      <button
        type="button"
        onClick={onOpenMobile}
        className="grid size-9 place-items-center rounded-sm text-fg-2 hover:bg-white/[0.06] hover:text-fg lg:hidden"
        aria-label="Abrir menu"
        aria-controls="sidebar"
      >
        <Menu size={18} />
      </button>

      <div className="min-w-0">
        <nav aria-label="Trilha de navegação" className="flex items-center gap-1.5 text-[10px] text-fg-3">
          <Link to="/" className="transition-colors hover:text-fg-2">
            GSN
          </Link>
          {!isHome && (
            <>
              <span aria-hidden className="text-fg-3/50">
                /
              </span>
              <span className="truncate">{crumb}</span>
            </>
          )}
        </nav>
        <p className="truncate font-display text-[13px] font-semibold text-fg">{title}</p>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <button
          type="button"
          onClick={onOpenPalette}
          className={cn(
            'hidden h-8 items-center gap-2 rounded-sm border border-line bg-surface px-2.5 text-xs text-fg-3',
            'transition-colors hover:border-line-strong hover:text-fg-2 sm:flex',
          )}
          aria-label="Abrir busca global"
        >
          <Search size={14} />
          <span className="hidden md:inline">Buscar</span>
          <kbd className="ml-1 hidden rounded-[3px] border border-line bg-surface-2 px-1 py-0.5 font-mono text-[9px] text-fg-3 md:inline">
            ⌘K
          </kbd>
        </button>

        <Link
          to="/configuracoes"
          className="grid size-9 place-items-center rounded-sm text-fg-2 transition-colors hover:bg-white/[0.06] hover:text-fg"
          aria-label="Abrir configurações"
        >
          <Settings2 size={16} />
        </Link>
      </div>
    </header>
  );
}
