import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  meta,
  className,
}: {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  meta?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cn('mb-5 flex flex-wrap items-start justify-between gap-4', className)}>
      <div className="min-w-0">
        {eyebrow && (
          <p className="mb-1 text-[9px] font-semibold tracking-[0.16em] text-accent uppercase">
            {eyebrow}
          </p>
        )}
        <h1 className="font-display text-[1.65rem] font-semibold tracking-[-0.03em] text-fg">
          {title}
        </h1>
        {description && (
          <p className="mt-1.5 max-w-[72ch] text-xs leading-relaxed text-fg-3">{description}</p>
        )}
        {meta && <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-2xs text-fg-3">{meta}</div>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export function SectionTitle({
  title,
  hint,
  action,
}: {
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-2.5 flex items-end justify-between gap-3">
      <div>
        <h2 className="font-display text-sm font-semibold tracking-[-0.01em] text-fg">{title}</h2>
        {hint && <p className="mt-0.5 text-2xs text-fg-3">{hint}</p>}
      </div>
      {action}
    </div>
  );
}
