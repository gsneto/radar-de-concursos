import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Check, Plus, X } from 'lucide-react';
import { keys, useDisciplines, useSessions } from '@/app/queries';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { EmptyState, SkeletonRows } from '@/components/ui/states';
import { api } from '@/lib/api';
import { formatTitleCase } from '@/lib/domain';
import { dateTime, duration } from '@/lib/format';
import { SyncEditalCard } from './SyncEditalCard';

export function SessionsTimerTab() {
  const queryClient = useQueryClient();
  const disciplines = useDisciplines();
  const sessions = useSessions();
  const [name, setName] = useState('');

  const create = useMutation({
    mutationFn: (nome: string) => api.post('/api/estudos/disciplinas', { nome }),
    onSuccess: () => {
      setName('');
      void queryClient.invalidateQueries({ queryKey: keys.disciplines() });
      void queryClient.invalidateQueries({ queryKey: keys.study() });
    },
  });

  return (
    <div className="space-y-3">
      <SyncEditalCard />

      <Card title="Disciplinas" subtitle="A base do plano de estudos. Tudo fica no banco local.">
        <form
          className="flex flex-wrap gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (name.trim()) create.mutate(name.trim());
          }}
        >
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Nome da disciplina"
            aria-label="Nome da disciplina"
            className="h-9 flex-1 rounded-sm border border-line-strong bg-surface-2 px-3 text-sm text-fg outline-none placeholder:text-fg-3 focus:border-accent/60"
          />
          <Button type="submit" variant="primary" disabled={create.isPending || !name.trim()}>
            <Plus size={14} /> Criar
          </Button>
        </form>
        {create.isError && <p className="mt-2 text-2xs text-risk-ink">{(create.error as Error).message}</p>}

        {disciplines.isLoading ? (
          <SkeletonRows rows={2} className="mt-3" />
        ) : !disciplines.data?.length ? (
          <EmptyState
            title="Nenhuma disciplina criada"
            description="Crie a primeira disciplina para registrar sessões e tópicos."
          />
        ) : (
          <ul className="mt-3 divide-y divide-line">
            {disciplines.data.map((discipline) => (
              <li key={discipline.id} className="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0">
                <span className="truncate text-xs text-fg">{formatTitleCase(discipline.nome)}</span>
                <AddTopic disciplineId={discipline.id} />
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Histórico de sessões" subtitle="Duração e estado calculados pelo servidor.">
        {sessions.isLoading ? (
          <SkeletonRows rows={4} />
        ) : !sessions.data?.length ? (
          <EmptyState title="Nenhuma sessão registrada" description="Inicie o cronômetro na visão geral." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] border-collapse text-xs">
              <caption className="sr-only">Histórico de sessões</caption>
              <thead>
                <tr className="border-b border-line">
                  {['Início', 'Duração', 'Estado', 'Modo'].map((text) => (
                    <th
                      key={text}
                      scope="col"
                      className="px-2 py-1.5 text-left text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase"
                    >
                      {text}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sessions.data.slice(0, 30).map((session) => (
                  <tr key={session.id} className="border-b border-line/60 last:border-0">
                    <td className="px-2 py-2 text-2xs text-fg-2">{dateTime(session.inicio ?? session.created_at)}</td>
                    <td className="px-2 py-2 text-2xs tabular text-fg">{duration(session.duracao_segundos)}</td>
                    <td className="px-2 py-2">
                      <Badge tone={session.estado === 'concluida' ? 'ok' : 'neutral'}>{session.estado}</Badge>
                    </td>
                    <td className="px-2 py-2 text-2xs text-fg-3">{session.modo}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function AddTopic({ disciplineId }: { disciplineId: string }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const create = useMutation({
    mutationFn: (nome: string) => api.post('/api/estudos/topicos', { disciplina_id: disciplineId, nome }),
    onSuccess: () => {
      setName('');
      setOpen(false);
      void queryClient.invalidateQueries({ queryKey: keys.study() });
    },
  });

  if (!open) {
    return (
      <Button size="sm" variant="ghost" onClick={() => setOpen(true)}>
        <Plus size={12} /> Tópico
      </Button>
    );
  }

  return (
    <form
      className="flex items-center gap-1.5"
      onSubmit={(event) => {
        event.preventDefault();
        if (name.trim()) create.mutate(name.trim());
      }}
    >
      <input
        value={name}
        onChange={(event) => setName(event.target.value)}
        placeholder="Tópico"
        aria-label="Nome do tópico"
        autoFocus
        className="h-7 w-32 rounded-xs border border-line-strong bg-surface-2 px-2 text-2xs text-fg outline-none focus:border-accent/60"
      />
      <Button type="submit" size="sm" variant="primary" disabled={create.isPending}>
        <Check size={12} />
      </Button>
      <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
        <X size={12} />
      </Button>
    </form>
  );
}
