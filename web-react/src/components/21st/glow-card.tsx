import { useRef } from 'react';
import type { CSSProperties, MouseEvent, ReactNode, TouchEvent } from 'react';
import { cn } from '@/lib/cn';

export type Accent = 'indigo' | 'cyan' | 'emerald' | 'fuchsia' | 'amber';

export const ACCENTS: Record<Accent, string> = {
  indigo: '129, 140, 248',
  cyan: '34, 211, 238',
  emerald: '52, 211, 153',
  fuchsia: '232, 121, 249',
  amber: '251, 191, 36',
};

const GRID_IMAGE =
  'linear-gradient(rgba(128,128,128,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(128,128,128,0.06) 1px, transparent 1px)';

export function GlowCard({
  accent = 'indigo',
  className = '',
  contentClassName = 'p-5',
  children,
}: {
  accent?: Accent;
  className?: string;
  contentClassName?: string;
  children: ReactNode;
}) {
  const rootRef = useRef<HTMLDivElement>(null);
  const rgb = ACCENTS[accent] ?? ACCENTS.indigo;

  const moveTo = (clientX: number, clientY: number) => {
    const el = rootRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    el.style.setProperty('--glow-x', `${Math.round(clientX - rect.left)}px`);
    el.style.setProperty('--glow-y', `${Math.round(clientY - rect.top)}px`);
  };

  const handleMouseMove = (e: MouseEvent<HTMLDivElement>) => moveTo(e.clientX, e.clientY);

  const handleTouch = (e: TouchEvent<HTMLDivElement>) => {
    const touch = e.touches[0];
    if (touch) {
      moveTo(touch.clientX, touch.clientY);
      rootRef.current?.setAttribute('data-touch', 'true');
    }
  };

  const handleTouchEnd = () => {
    rootRef.current?.removeAttribute('data-touch');
  };

  const gridMask =
    'radial-gradient(220px circle at var(--glow-x, 0px) var(--glow-y, 0px), black, transparent 75%)';

  return (
    <div
      ref={rootRef}
      onMouseMove={handleMouseMove}
      onTouchStart={handleTouch}
      onTouchMove={handleTouch}
      onTouchEnd={handleTouchEnd}
      style={{ '--glow-x': '0px', '--glow-y': '0px' } as CSSProperties}
      className={cn('group/glow relative rounded-2xl transition-all', className)}
    >
      {/* Camada 1: borda sutil translúcida */}
      <div aria-hidden="true" className="absolute inset-0 rounded-2xl bg-line" />

      {/* Camada 2: borda viva que segue o cursor via CSS vars */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 rounded-2xl opacity-0 transition-opacity duration-500 group-hover/glow:opacity-100 group-focus-within/glow:opacity-100 group-data-[touch=true]/glow:opacity-100"
        style={{
          background: `radial-gradient(240px circle at var(--glow-x, 0px) var(--glow-y, 0px), rgba(${rgb}, 0.95), transparent 70%)`,
        }}
      />

      {/* Camada 3: corpo do card com spotlight e grid */}
      <div aria-hidden="true" className="absolute inset-px overflow-hidden rounded-[15px] bg-surface">
        <div
          className="absolute inset-0 opacity-0 transition-opacity duration-500 group-hover/glow:opacity-100 group-focus-within/glow:opacity-100 group-data-[touch=true]/glow:opacity-100"
          style={{
            background: `radial-gradient(380px circle at var(--glow-x, 0px) var(--glow-y, 0px), rgba(${rgb}, 0.12), transparent 65%)`,
          }}
        />
        <div
          className="absolute inset-0 opacity-0 transition-opacity duration-500 group-hover/glow:opacity-100 group-focus-within/glow:opacity-100 group-data-[touch=true]/glow:opacity-100"
          style={{
            backgroundImage: GRID_IMAGE,
            backgroundSize: '24px 24px',
            maskImage: gridMask,
            WebkitMaskImage: gridMask,
          }}
        />
      </div>

      {/* Conteúdo */}
      <div className={cn('relative z-10 flex h-full flex-col', contentClassName)}>{children}</div>
    </div>
  );
}
