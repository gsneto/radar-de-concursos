import { animate, useReducedMotion } from 'motion/react';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { cn } from '@/lib/cn';

/**
 * Contagem animada apenas para números inteiros. Se o valor não for numérico,
 * renderiza o texto como veio (nunca inventa um número).
 */
export function NumberTicker({
  value,
  duration = 0.9,
  className,
  format,
}: {
  value: number | string | null | undefined;
  duration?: number;
  className?: string;
  format?: (n: number) => string;
}) {
  const reduce = useReducedMotion();
  const numeric = typeof value === 'number' ? value : Number(value);
  const isNumeric = value !== null && value !== undefined && value !== '' && Number.isFinite(numeric);
  const [display, setDisplay] = useState(isNumeric && !reduce ? 0 : numeric || 0);
  const previous = useRef(0);

  useEffect(() => {
    if (!isNumeric) return;
    if (reduce) {
      setDisplay(numeric);
      previous.current = numeric;
      return;
    }
    const controls = animate(previous.current, numeric, {
      duration,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (latest) => setDisplay(latest),
    });
    previous.current = numeric;
    return () => controls.stop();
  }, [numeric, isNumeric, reduce, duration]);

  if (!isNumeric) {
    return <span className={className}>{value === null || value === undefined ? '—' : String(value)}</span>;
  }
  return <span className={className}>{format ? format(display) : Math.round(display).toLocaleString('pt-BR')}</span>;
}

interface KpiProps {
  label: string;
  value: ReactNode;
  unit?: string;
  context?: ReactNode;
  icon?: ReactNode;
  feature?: boolean;
  footer?: ReactNode;
  className?: string;
  tone?: 'default' | 'accent';
}

export function Kpi({
  label,
  value,
  unit,
  context,
  icon,
  feature,
  footer,
  className,
  tone = 'default',
}: KpiProps) {
  return (
    <article
      className={cn(
        'relative flex min-w-0 flex-col gap-1.5 overflow-hidden rounded-md border border-line bg-surface px-4 py-3.5 shadow-panel',
        feature && 'bg-[radial-gradient(130%_130%_at_100%_0%,rgb(245_165_36/0.09),transparent_58%)]',
        className,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-2xs font-medium tracking-[0.02em] text-fg-3">{label}</span>
        {icon && (
          <span
            className={cn(
              'grid size-7 shrink-0 place-items-center rounded-xs border border-line',
              tone === 'accent' ? 'bg-accent-soft text-accent' : 'bg-surface-2 text-fg-3',
            )}
          >
            {icon}
          </span>
        )}
      </div>
      <p
        className={cn(
          'font-display font-semibold tabular tracking-[-0.03em] text-fg',
          feature ? 'text-[2.15rem] leading-none' : 'text-[1.6rem] leading-none',
        )}
      >
        {value}
        {unit && <span className="ml-1 text-sm font-medium tracking-normal text-fg-3">{unit}</span>}
      </p>
      {context && <p className="mt-0.5 text-xs leading-snug text-fg-3">{context}</p>}
      {footer && <div className="mt-auto pt-2">{footer}</div>}
    </article>
  );
}
