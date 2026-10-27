import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

interface CardProps {
  title?: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  children?: ReactNode;
  className?: string;
  bodyClassName?: string;
  flush?: boolean;
  as?: 'section' | 'article' | 'div';
  id?: string;
}

export function Card({
  title,
  subtitle,
  action,
  children,
  className,
  bodyClassName,
  flush,
  as: Tag = 'section',
  id,
}: CardProps) {
  return (
    <Tag
      id={id}
      className={cn(
        'relative min-w-0 rounded-md border border-line bg-surface shadow-panel',
        className,
      )}
    >
      {(title || action) && (
        <header className="flex items-start justify-between gap-4 border-b border-line px-4 py-3">
          <div className="min-w-0">
            {title && (
              <h3 className="font-display text-sm font-semibold tracking-[-0.01em] text-fg">
                {title}
              </h3>
            )}
            {subtitle && <p className="mt-0.5 text-xs text-fg-3">{subtitle}</p>}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </header>
      )}
      <div className={cn(flush ? '' : 'p-4', bodyClassName)}>{children}</div>
    </Tag>
  );
}
