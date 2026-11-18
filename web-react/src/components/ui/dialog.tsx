import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

export interface ModalDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  eyebrow?: string;
  description?: string;
  headerActions?: ReactNode;
  footer?: ReactNode;
  maxWidthClass?: string;
  bodyClassName?: string;
  children: ReactNode;
}

export function ModalDialog({
  open,
  onOpenChange,
  title,
  eyebrow,
  description,
  headerActions,
  footer,
  maxWidthClass = 'max-w-xl',
  bodyClassName = 'p-5',
  children,
}: ModalDialogProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm" />
        <Dialog.Content
          className={cn(
            'fixed top-1/2 left-1/2 z-50 flex max-h-[92vh] w-[min(94vw,100%)] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-2xl border border-line-strong bg-surface shadow-float focus:outline-none',
            maxWidthClass,
          )}
        >
          <div className="flex items-center justify-between gap-3 border-b border-line bg-surface-2 px-5 py-3.5">
            <div className="min-w-0">
              {eyebrow && (
                <span className="block text-[10px] font-black tracking-widest text-accent uppercase">
                  {eyebrow}
                </span>
              )}
              <Dialog.Title className="truncate font-display text-sm font-extrabold text-fg sm:text-base">
                {title}
              </Dialog.Title>
              <Dialog.Description className={description ? 'mt-0.5 text-xs text-fg-3' : 'sr-only'}>
                {description || title}
              </Dialog.Description>
            </div>

            <div className="flex shrink-0 items-center gap-2">
              {headerActions}
              <Dialog.Close
                aria-label="Fechar janela"
                className="rounded-xl border border-line-strong bg-surface p-2 text-fg-2 transition-colors hover:text-fg focus-visible:ring-2 focus-visible:ring-accent"
              >
                <X size={16} />
              </Dialog.Close>
            </div>
          </div>

          <div className={cn('flex-1 overflow-y-auto', bodyClassName)}>{children}</div>

          {footer && <div className="border-t border-line bg-surface-2 px-5 py-3">{footer}</div>}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
