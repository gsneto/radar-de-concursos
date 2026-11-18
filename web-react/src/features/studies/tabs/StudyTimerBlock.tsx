import { useEffect, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Pause, Play, Square, X } from 'lucide-react';
import { keys, useDisciplines } from '@/app/queries';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { formatTitleCase } from '@/lib/domain';
import { clock } from '@/lib/format';
import type { StudyPanel } from '@/lib/types';

export function StudyTimerBlock({ panel }: { panel: StudyPanel }) {
  const queryClient = useQueryClient();
  const disciplines = useDisciplines();
  const session = panel.sessao_aberta;
  const [selected, setSelected] = useState('');
  const [elapsed, setElapsed] = useState(session?.elapsed_seconds ?? 0);

  useEffect(() => {
    setElapsed(session?.elapsed_seconds ?? 0);
    if (!session || session.estado !== 'em_andamento') return;
    const started = Date.now();
    const base = session.elapsed_seconds ?? 0;
    const timer = window.setInterval(() => setElapsed(base + (Date.now() - started) / 1000), 1000);
    return () => window.clearInterval(timer);
  }, [session]);

  const action = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post('/api/estudos/sessoes', body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keys.study() });
      void queryClient.invalidateQueries({ queryKey: keys.sessions() });
    },
  });

  const rawDisciplineName = session?.disciplina_id
    ? disciplines.data?.find((item) => item.id === session.disciplina_id)?.nome
    : null;
  const disciplineName = rawDisciplineName ? formatTitleCase(rawDisciplineName) : null;

  return (
    <div className="flex flex-wrap items-center gap-4">
      <div className="min-w-[132px]">
        <p className="font-mono text-[2rem] leading-none font-semibold tabular text-fg">{clock(elapsed)}</p>
        <p className="mt-1.5 text-2xs text-fg-3">
          {session
            ? `${session.estado === 'pausada' ? 'Sessão pausada' : 'Sessão em andamento'}${disciplineName ? ` · ${disciplineName}` : ''}`
            : 'Nenhuma sessão aberta'}
        </p>
      </div>

      <div className="flex flex-1 flex-wrap items-center gap-2">
        {!session ? (
          <>
            <select
              value={selected}
              onChange={(event) => setSelected(event.target.value)}
              aria-label="Disciplina da sessão"
              className="h-9 min-w-[150px] rounded-sm border border-line-strong bg-surface-2 px-2.5 text-xs text-fg outline-none focus:border-accent/60"
            >
              <option value="">Sem disciplina</option>
              {disciplines.data?.map((item) => (
                <option key={item.id} value={item.id}>
                  {formatTitleCase(item.nome)}
                </option>
              ))}
            </select>
            <Button
              variant="primary"
              size="md"
              disabled={action.isPending}
              onClick={() => action.mutate({ action: 'start', disciplina_id: selected || null, modo: 'livre' })}
            >
              <Play size={14} /> Iniciar sessão
            </Button>
          </>
        ) : (
          <>
            {session.estado === 'pausada' ? (
              <Button variant="secondary" size="md" onClick={() => action.mutate({ action: 'resume', id: session.id })}>
                <Play size={14} /> Retomar
              </Button>
            ) : (
              <Button variant="secondary" size="md" onClick={() => action.mutate({ action: 'pause', id: session.id })}>
                <Pause size={14} /> Pausar
              </Button>
            )}
            <Button variant="primary" size="md" onClick={() => action.mutate({ action: 'finish', id: session.id })}>
              <Square size={13} /> Concluir
            </Button>
            <Button variant="ghost" size="md" onClick={() => action.mutate({ action: 'discard', id: session.id })}>
              <X size={14} /> Descartar
            </Button>
          </>
        )}
      </div>

      {action.isError && (
        <p className="w-full text-2xs text-risk-ink" role="alert">
          {(action.error as Error).message}
        </p>
      )}
    </div>
  );
}
