import { Command } from 'cmdk';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, CornerDownLeft, Search } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { api, qs } from '@/lib/api';
import type { Portfolio } from '@/lib/types';
import { flatNav } from './nav';

export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');

  useEffect(() => {
    if (!open) setSearch('');
  }, [open]);

  const term = search.trim();
  const results = useQuery({
    queryKey: ['palette', term],
    queryFn: () => api.get<Portfolio>(`/api/carteira${qs({ search: term, limit: 6 })}`),
    enabled: open && term.length >= 2,
    staleTime: 30_000,
  });

  const go = (path: string) => {
    onOpenChange(false);
    navigate(path);
  };

  return (
    <Command.Dialog
      open={open}
      onOpenChange={onOpenChange}
      label="Busca global"
      shouldFilter={false}
      className="fixed inset-x-0 top-[12vh] z-[90] mx-auto w-[min(94vw,620px)] overflow-hidden rounded-md border border-line-strong bg-surface shadow-float"
    >
      <div className="flex items-center gap-2 border-b border-line px-3">
        <Search size={15} className="shrink-0 text-fg-3" />
        <Command.Input
          value={search}
          onValueChange={setSearch}
          placeholder="Ir para uma tela ou buscar concurso, órgão, cargo…"
          className="h-12 w-full bg-transparent text-sm text-fg outline-none placeholder:text-fg-3"
        />
        <kbd className="rounded-[3px] border border-line bg-surface-2 px-1.5 py-0.5 font-mono text-[9px] text-fg-3">
          ESC
        </kbd>
      </div>

      <Command.List className="max-h-[52vh] overflow-y-auto p-2">
        <Command.Empty className="px-3 py-6 text-center text-xs text-fg-3">
          {term.length >= 2 && results.isFetching
            ? 'Buscando…'
            : term.length >= 2
              ? 'Nenhum concurso encontrado.'
              : 'Digite ao menos 2 caracteres para buscar oportunidades.'}
        </Command.Empty>

        <Command.Group
          heading="Navegar"
          className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[9px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:tracking-[0.12em] [&_[cmdk-group-heading]]:text-fg-3 [&_[cmdk-group-heading]]:uppercase"
        >
          {flatNav.map((item) => {
            const Icon = item.icon;
            return (
              <Command.Item
                key={item.to}
                value={`nav ${item.label}`}
                onSelect={() => go(item.to)}
                className="flex cursor-pointer items-center gap-2.5 rounded-sm px-2 py-2 text-xs text-fg-2 data-[selected=true]:bg-accent-soft data-[selected=true]:text-fg"
              >
                <Icon size={14} className="text-fg-3" />
                {item.label}
                <ArrowRight size={12} className="ml-auto text-fg-3/50" />
              </Command.Item>
            );
          })}
        </Command.Group>

        {term.length >= 2 && (results.data?.itens.length ?? 0) > 0 && (
          <Command.Group
            heading="Oportunidades"
            className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[9px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:tracking-[0.12em] [&_[cmdk-group-heading]]:text-fg-3 [&_[cmdk-group-heading]]:uppercase"
          >
            {results.data?.itens.map((item) => (
              <Command.Item
                key={`${item.contest_id}-${item.scope}`}
                value={`op ${item.contest_label} ${item.role_name ?? ''}`}
                onSelect={() => {
                  const params = new URLSearchParams();
                  if (item.scope) params.set('scope', item.scope);
                  go(`/dossie/${item.contest_id}${params.size ? `?${params}` : ''}`);
                }}
                className="flex cursor-pointer items-center gap-2.5 rounded-sm px-2 py-2 text-xs data-[selected=true]:bg-accent-soft"
              >
                <CornerDownLeft size={13} className="shrink-0 text-fg-3" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-fg">{item.contest_label ?? item.competition_id}</span>
                  <span className="block truncate text-2xs text-fg-3">
                    {item.role_name ?? 'Cargo não reconciliado'}
                  </span>
                </span>
              </Command.Item>
            ))}
          </Command.Group>
        )}
      </Command.List>
    </Command.Dialog>
  );
}
