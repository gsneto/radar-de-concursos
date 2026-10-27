import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { Link, type LinkProps } from 'react-router-dom';
import { cn } from '@/lib/cn';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size = 'sm' | 'md' | 'icon';

const variants: Record<Variant, string> = {
  primary:
    'bg-accent text-fg-inverse hover:bg-accent-hover shadow-[0_1px_0_rgb(255_255_255/0.2)_inset,0_8px_20px_-12px_rgb(245_165_36/0.7)]',
  secondary:
    'bg-surface-2 text-fg border border-line-strong hover:bg-surface-3 hover:border-white/20',
  ghost: 'bg-transparent text-fg-2 hover:bg-white/[0.06] hover:text-fg',
  danger: 'bg-risk-soft text-risk border border-risk/30 hover:bg-risk/20',
};

const sizes: Record<Size, string> = {
  sm: 'h-8 px-3 text-xs gap-1.5',
  md: 'h-9 px-4 text-sm gap-2',
  icon: 'h-9 w-9 p-0',
};

export function buttonStyles(variant: Variant = 'secondary', size: Size = 'md', className?: string) {
  return cn(
    'inline-flex items-center justify-center rounded-sm font-medium whitespace-nowrap',
    'transition-colors duration-150 disabled:pointer-events-none disabled:opacity-45',
    variants[variant],
    sizes[size],
    className,
  );
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  children?: ReactNode;
}

export function Button({
  variant = 'secondary',
  size = 'md',
  className,
  children,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button type={type} className={buttonStyles(variant, size, className)} {...rest}>
      {children}
    </button>
  );
}

interface LinkButtonProps extends LinkProps {
  variant?: Variant;
  size?: Size;
  children?: ReactNode;
}

export function LinkButton({
  variant = 'secondary',
  size = 'md',
  className,
  children,
  ...rest
}: LinkButtonProps) {
  return (
    <Link className={buttonStyles(variant, size, className)} {...rest}>
      {children}
    </Link>
  );
}
