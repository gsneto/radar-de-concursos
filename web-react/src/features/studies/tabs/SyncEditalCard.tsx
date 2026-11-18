import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { DownloadCloud, Sparkles } from 'lucide-react';
import { keys, usePortfolio } from '@/app/queries';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { syncProgramToStudy } from '@/lib/api';

export function SyncEditalCard({ className = '' }: { className?: string }) {
  const queryClient = useQueryClient();
  const portfolio = usePortfolio({ limit: 40 });
  const [selectedContest, setSelectedContest] = useState('');
  const [feedback, setFeedback] = useState<{ type: 'ok' | 'err'; text: string } | null>(null);

  const sync = useMutation({
    mutationFn: (contestId: string) => syncProgramToStudy(contestId),
    onSuccess: (data) => {
      if (data.ok) {
        setFeedback({
          type: 'ok',
          text: `Sucesso: ${data.disciplinas_importadas} nova(s) disciplina(s) e ${data.topicos_importados} tópico(s) importados para o plano de estudos!`,
        });
        void queryClient.invalidateQueries({ queryKey: keys.disciplines() });
        void queryClient.invalidateQueries({ queryKey: keys.study() });
      } else {
        setFeedback({
          type: 'err',
          text: data.mensagem || 'Nenhum conteúdo programático localizado para este concurso.',
        });
      }
    },
    onError: (err) => {
      setFeedback({ type: 'err', text: (err as Error).message });
    },
  });

  const contests = (portfolio.data?.itens ?? []).filter((c) => c.contest_id);

  return (
    <Card
      title="Sincronizar com Edital"
      subtitle="Importe automaticamente disciplinas e tópicos de um concurso analisado para o seu plano de estudos."
      className={className}
    >
      <div className="flex flex-col gap-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={selectedContest}
            onChange={(e) => {
              setSelectedContest(e.target.value);
              setFeedback(null);
            }}
            aria-label="Concurso para importar matérias"
            className="h-9 flex-1 min-w-[220px] rounded-sm border border-line-strong bg-surface-2 px-3 text-xs text-fg outline-none focus:border-accent/60"
          >
            <option value="">Selecione um concurso analisado...</option>
            {contests.map((item) => (
              <option key={item.contest_id} value={item.contest_id}>
                {item.contest_label ?? item.competition_id ?? item.contest_id}
              </option>
            ))}
          </select>
          <Button
            variant="secondary"
            size="md"
            disabled={!selectedContest || sync.isPending}
            onClick={() => {
              if (selectedContest) sync.mutate(selectedContest);
            }}
          >
            <DownloadCloud size={14} /> {sync.isPending ? 'Sincronizando...' : 'Importar Matérias'}
          </Button>
        </div>

        {feedback && (
          <div
            role="alert"
            className={`flex items-center gap-2 rounded-xs border p-2 text-xs ${
              feedback.type === 'ok'
                ? 'border-emerald-500/30 bg-emerald-500/10 text-ok-ink'
                : 'border-amber-500/30 bg-amber-500/10 text-accent-ink'
            }`}
          >
            <Sparkles size={14} className="shrink-0" />
            <span>{feedback.text}</span>
          </div>
        )}
      </div>
    </Card>
  );
}
