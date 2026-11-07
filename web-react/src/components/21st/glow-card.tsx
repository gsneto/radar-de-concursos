import { useState } from 'react';
import type { MouseEvent, ReactNode, TouchEvent } from 'react';
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
  children,
}: {
  accent?: Accent;
  className?: string;
  children: ReactNode;
}) {
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const [active, setActive] = useState(false);
  const rgb = ACCENTS[accent] ?? ACCENTS.indigo;

  const moveTo = (clientX: number, clientY: number, el: HTMLElement) => {
    const rect = el.getBoundingClientRect();
    setPos({ x: clientX - rect.left, y: clientY - rect.top });
  };

  const handleMouseMove = (e: MouseEvent<HTMLDivElement>) =>
    moveTo(e.clientX, e.clientY, e.currentTarget);

  const handleTouch = (e: TouchEvent<HTMLDivElement>) => {
    const touch = e.touches[0];
    if (touch) {
      moveTo(touch.clientX, touch.clientY, e.currentTarget);
      setActive(true);
    }
  };

  const gridMask = `radial-gradient(220px circle at ${pos.x}px ${pos.y}px, black, transparent 75%)`;

  return (
    <div
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setActive(true)}
      onMouseLeave={() => setActive(false)}
      onTouchStart={handleTouch}
      onTouchMove={handleTouch}
      onTouchEnd={() => setActive(false)}
      onFocus={() => setActive(true)}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setActive(false);
      }}
      className={cn('relative rounded-2xl transition-all', className)}
    >
      {/* Camada 1: borda sutil translúcida */}
      <div aria-hidden="true" className="absolute inset-0 rounded-2xl bg-line" />

      {/* Camada 2: borda viva que segue o cursor */}
      <div
        aria-hidden="true"
        className={cn(
          'absolute inset-0 rounded-2xl transition-opacity duration-500 pointer-events-none',
          active ? 'opacity-100' : 'opacity-0',
        )}
        style={{
          background: `radial-gradient(240px circle at ${pos.x}px ${pos.y}px, rgba(${rgb}, 0.95), transparent 70%)`,
        }}
      />

      {/* Camada 3: corpo do card com spotlight e grid */}
      <div aria-hidden="true" className="absolute inset-px overflow-hidden rounded-[15px] bg-surface">
        <div
          className={cn(
            'absolute inset-0 transition-opacity duration-500',
            active ? 'opacity-100' : 'opacity-0',
          )}
          style={{
            background: `radial-gradient(380px circle at ${pos.x}px ${pos.y}px, rgba(${rgb}, 0.12), transparent 65%)`,
          }}
        />
        <div
          className={cn(
            'absolute inset-0 transition-opacity duration-500',
            active ? 'opacity-100' : 'opacity-0',
          )}
          style={{
            backgroundImage: GRID_IMAGE,
            backgroundSize: '24px 24px',
            maskImage: gridMask,
            WebkitMaskImage: gridMask,
          }}
        />
      </div>

      {/* Conteúdo */}
      <div className="relative z-10 flex h-full flex-col p-5">{children}</div>
    </div>
  );
}
