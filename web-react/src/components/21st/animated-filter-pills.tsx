import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

export interface FilterPill {
  id: string;
  label: string;
  icon: ReactNode;
  active: boolean;
  count?: number;
  onClick: () => void;
}

export function AnimatedFilterPills({
  pills,
  className = '',
}: {
  pills: FilterPill[];
  className?: string;
}) {
  return (
    <div className={cn('flex flex-wrap items-center gap-2 overflow-x-auto pb-1', className)}>
      {pills.map((pill) => (
        <button
          key={pill.id}
          type="button"
          onClick={pill.onClick}
          className={cn(
            'group relative flex h-8 items-center gap-1.5 rounded-full px-3 text-xs font-medium transition-all duration-300',
            pill.active
              ? 'bg-accent/15 text-accent border border-accent/40 shadow-[0_0_12px_rgba(245,165,36,0.2)]'
              : 'border border-white/10 bg-[#0f1420]/80 text-fg-3 hover:border-white/20 hover:text-fg hover:bg-[#161c2c]',
          )}
        >
          <span className={cn('shrink-0 transition-colors', pill.active ? 'text-accent' : 'text-slate-400 group-hover:text-slate-200')}>
            {pill.icon}
          </span>
          <span>{pill.label}</span>
          {typeof pill.count === 'number' && (
            <span
              className={cn(
                'ml-1 rounded-full px-1.5 py-0.2 font-mono text-[10px]',
                pill.active ? 'bg-accent/25 text-accent' : 'bg-white/10 text-fg-3',
              )}
            >
              {pill.count}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
