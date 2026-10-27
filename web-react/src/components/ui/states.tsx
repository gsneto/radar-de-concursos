import { AlertTriangle, Inbox, Loader2, RefreshCw, WifiOff } from 'lucide-react';
import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';
import { Button } from './button';

interface StateProps {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  hint?: ReactNode;
  action?: ReactNode;
  className?: string;
}

function Shell({ icon, title, description, hint, action, className }: StateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-2 px-6 py-12 text-center',
        className,
      )}
    >
      <div className="mb-1 grid size-11 place-items-center rounded-md border border-line bg-surface-2 text-fg-3">
        {icon}
      </div>
      <p className="font-display text-sm font-semibold text-fg">{title}</p>
      {description && <p className="max-w-[52ch] text-xs leading-relaxed text-fg-3">{description}</p>}
      {hint && <p className="max-w-[52ch] text-2xs text-fg-3/80">{hint}</p>}
      {action && <div className="mt-2 flex flex-wrap justify-center gap-2">{action}</div>}
    </div>
  );
}

export function EmptyState(props: StateProps) {
  return <Shell icon={<Inbox size={20} strokeWidth={1.6} />} {...props} />;
}

export function ErrorState({
  message,
  onRetry,
  title = 'Não foi possível carregar',
  hint = 'Verifique o servidor local e tente novamente.',
}: {
  message: string;
  onRetry?: () => void;
  title?: string;
  hint?: string;
}) {
  return (
    <Shell
      icon={<AlertTriangle size={20} strokeWidth={1.6} className="text-risk" />}
      title={title}
      description={message}
      hint={hint}
      action={
        onRetry && (
          <Button size="sm" onClick={onRetry}>
            <RefreshCw size={13} /> Tentar novamente
          </Button>
        )
      }
    />
  );
}

export function OfflineState({ onRetry }: { onRetry?: () => void }) {
  return (
    <Shell
      icon={<WifiOff size={20} strokeWidth={1.6} />}
      title="Servidor local indisponível"
      description="O Radar roda no seu computador. Inicie com python -m radar serve."
      action={
        onRetry && (
          <Button size="sm" onClick={onRetry}>
            <RefreshCw size={13} /> Tentar novamente
          </Button>
        )
      }
    />
  );
}

export function LoadingBlock({ label = 'Carregando' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-xs text-fg-3" role="status">
      <Loader2 size={15} className="animate-spin" />
      {label}
    </div>
  );
}

export function SkeletonRows({ rows = 4, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn('space-y-2', className)} aria-hidden>
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="h-11 rounded-sm shimmer" />
      ))}
    </div>
  );
}

export function SkeletonCards({ count = 4, className }: { count?: number; className?: string }) {
  return (
    <div className={cn('grid gap-3 sm:grid-cols-2 lg:grid-cols-4', className)} aria-hidden>
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="h-28 rounded-md shimmer" />
      ))}
    </div>
  );
}
