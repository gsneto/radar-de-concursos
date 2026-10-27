import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

export type Tone = 'neutral' | 'accent' | 'verified' | 'ok' | 'warn' | 'risk' | 'unknown';

const tones: Record<Tone, string> = {
  neutral: 'bg-white/[0.06] text-fg-2 border-line',
  accent: 'bg-accent-soft text-accent border-accent/25',
  verified: 'bg-verified-soft text-verified border-verified/25',
  ok: 'bg-ok-soft text-ok border-ok/25',
  warn: 'bg-warn-soft text-warn border-warn/25',
  risk: 'bg-risk-soft text-risk border-risk/25',
  unknown: 'bg-unknown-soft text-unknown border-line',
};

interface BadgeProps {
  tone?: Tone;
  dot?: boolean;
  children: ReactNode;
  className?: string;
  title?: string;
}

export function Badge({ tone = 'neutral', dot, children, className, title }: BadgeProps) {
  return (
    <span
      title={title}
      className={cn(
        'inline-flex max-w-full items-center gap-1.5 truncate rounded-xs border px-2 py-[2px]',
        'text-2xs font-medium leading-[1.6] whitespace-nowrap',
        tones[tone],
        className,
      )}
    >
      {dot && <span className="size-1.5 shrink-0 rounded-full bg-current" aria-hidden />}
      {children}
    </span>
  );
}
