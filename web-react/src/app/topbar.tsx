import { useState } from 'react';
import { Bot, Check, Loader2, Menu, Search, Settings2 } from 'lucide-react';
import { Link, useLocation, useMatches } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { cn } from '@/lib/cn';
import { executeCuradoria } from '@/lib/api';

interface TopbarProps {
  onOpenMobile: () => void;
  onOpenPalette: () => void;
}

interface RouteHandle {
  title?: string;
  crumb?: string;
}

export function CuradoriaButton() {
  const [running, setRunning] = useState(false);
  const [resultMsg, setResultMsg] = useState<string | null>(null);
  const queryClient = useQueryClient();

  async function handleCurar() {
    if (running) return;
    setRunning(true);
    setResultMsg(null);
    try {
      const res = await executeCuradoria(false);
      const total = (res.novas_revisoes ?? 0) + (res.novas_reconciliacoes ?? 0);
      setResultMsg(total > 0 ? `+${total} curados` : 'Base em dia');
      await queryClient.invalidateQueries();
    } catch {
      setResultMsg('Falha ao curar');
    } finally {
      setRunning(false);
      setTimeout(() => setResultMsg(null), 4000);
    }
  }

  return (
    <button
      type="button"
      onClick={handleCurar}
      disabled={running}
      aria-label="Executar Curadoria Autônoma"
      title="Executar Curadoria Autônoma de Dados"
      className={cn(
        'flex h-8 items-center gap-1.5 rounded-sm border px-2.5 text-xs font-medium transition-all',
        running
          ? 'border-amber-500/40 bg-amber-500/10 text-amber-300 cursor-wait'
          : resultMsg
          ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
          : 'border-line hover:border-line-strong bg-surface hover:bg-surface-2 text-fg-2 hover:text-fg',
      )}
    >
      {running ? (
        <>
          <Loader2 size={13} className="animate-spin text-amber-400" />
          <span className="hidden sm:inline">Curando...</span>
        </>
      ) : resultMsg ? (
        <>
          <Check size={13} className="text-emerald-400" />
          <span>{resultMsg}</span>
        </>
      ) : (
        <>
          <Bot size={13} className="text-fg-3" />
          <span className="hidden sm:inline">Curar Dados</span>
        </>
      )}
    </button>
  );
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
        <CuradoriaButton />

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
