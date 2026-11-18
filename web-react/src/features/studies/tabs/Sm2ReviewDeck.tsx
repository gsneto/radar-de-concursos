import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { BookOpen, ChevronLeft, ChevronRight, RotateCcw, Sparkles, Trophy } from 'lucide-react';
import { keys, type Flashcard } from '@/app/queries';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { api } from '@/lib/api';

interface Sm2ReviewDeckProps {
  cards: Flashcard[];
  futureCount: number;
  onSwitchToVisual: () => void;
}

export function Sm2ReviewDeck({ cards, futureCount, onSwitchToVisual }: Sm2ReviewDeckProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [currentIndex, setCurrentIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);

  const totalCards = cards.length;
  const safeIndex = totalCards > 0 ? Math.min(currentIndex, totalCards - 1) : 0;
  const currentCard = cards[safeIndex];

  const review = useMutation({
    mutationFn: (qualidade: number) =>
      api.post('/api/estudos/flashcards', { action: 'review', id: currentCard.id, qualidade }),
    onSuccess: () => {
      setRevealed(false);
      if (safeIndex >= cards.length - 1) setCurrentIndex(0);
      void queryClient.invalidateQueries({ queryKey: keys.flashQueue() });
      void queryClient.invalidateQueries({ queryKey: keys.flashStats() });
    },
  });

  if (!cards.length) {
    return (
      <Card>
        <div className="py-10 text-center space-y-3">
          <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-emerald-500/10 text-ok-ink border border-emerald-500/20">
            <Trophy size={24} />
          </div>
          <h3 className="text-sm font-bold text-fg">Fila de Revisão SM-2 em Dia!</h3>
          <p className="text-xs text-fg-3 max-w-md mx-auto">
            {futureCount > 0
              ? `${futureCount} cartão(ões) agendado(s) para os próximos ciclos de repetição espaçada.`
              : 'Você revisou todos os cartões pendentes de hoje. Alterne para "Mapas & Flashcards Visuais (Estilo Jotta)" acima para explorar ou salvar novos esquemas.'}
          </p>
          <div className="pt-2 flex justify-center gap-2">
            <Button variant="primary" size="sm" onClick={onSwitchToVisual} className="gap-2 text-xs font-bold">
              <Sparkles size={14} /> Ver Mapas Visuais Estilo Jotta
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => navigate('/estudos/aulas')}
              className="gap-2 text-xs font-semibold"
            >
              <BookOpen size={14} /> Ir para Aulas
            </Button>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="relative overflow-hidden rounded-2xl border border-line bg-surface shadow-md">
        <div className="flex items-center justify-between border-b border-line px-5 py-3 text-xs bg-surface-2/40">
          <span className="font-mono text-2xs font-semibold text-fg-3">
            Cartão {safeIndex + 1} de {totalCards} na fila SM-2
          </span>
          <div className="flex items-center gap-1.5">
            {((currentCard.tags ?? []) as string[]).slice(0, 3).map((tag: string) => (
              <Badge key={tag} tone="neutral" className="text-[10px]">
                {tag.toUpperCase()}
              </Badge>
            ))}
          </div>
        </div>

        <div
          onClick={() => setRevealed(!revealed)}
          className="p-6 sm:p-8 cursor-pointer select-none transition-colors hover:bg-surface-2/30 min-h-[200px] flex flex-col justify-between"
        >
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-accent-ink">
              {revealed ? 'Resposta (Verso)' : 'Pergunta (Frente)'}
            </span>
            <p className="mt-3 text-base sm:text-lg font-bold text-fg leading-relaxed">{currentCard.frente}</p>
            {revealed && (
              <div className="mt-5 border-t border-line/80 pt-4 text-sm text-fg-2 leading-relaxed whitespace-pre-line font-medium">
                {currentCard.verso}
              </div>
            )}
          </div>
          {!revealed && (
            <p className="mt-6 text-2xs text-fg-3 flex items-center gap-1.5">
              <RotateCcw size={12} className="text-accent-ink" />
              Clique em qualquer lugar do cartão para virar e conferir a resposta
            </p>
          )}
        </div>

        <div className="border-t border-line bg-surface-2/60 p-4">
          {!revealed ? (
            <div className="flex justify-center">
              <Button
                variant="primary"
                size="md"
                onClick={() => setRevealed(true)}
                className="w-full sm:w-auto px-8 gap-2 font-bold"
              >
                Mostrar Resposta
              </Button>
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-center text-2xs font-semibold text-fg-3 uppercase tracking-wider">
                Como foi a sua recordação? (Algoritmo SM-2)
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 max-w-xl mx-auto">
                {(
                  [
                    { q: 1, sub: '1 dia', label: 'Errei (1)', cls: 'border-rose-500/30 bg-rose-500/10 text-risk-ink hover:bg-rose-500/20' },
                    { q: 2, sub: 'Difícil', label: 'Difícil (2)', cls: 'border-amber-500/30 bg-amber-500/10 text-accent-ink hover:bg-amber-500/20' },
                    { q: 3, sub: 'Normal', label: 'Bom (3)', cls: 'border-cyan-500/30 bg-cyan-500/10 text-info-ink hover:bg-cyan-500/20' },
                    { q: 5, sub: 'Fácil', label: 'Fácil (5)', cls: 'border-emerald-500/30 bg-emerald-500/10 text-ok-ink hover:bg-emerald-500/20' },
                  ] as const
                ).map((btn) => (
                  <button
                    key={btn.q}
                    type="button"
                    disabled={review.isPending}
                    onClick={() => review.mutate(btn.q)}
                    className={`rounded-xl border p-2.5 text-center text-xs font-bold transition-all ${btn.cls}`}
                  >
                    <span className="block text-2xs font-normal opacity-90">{btn.sub}</span>
                    {btn.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between text-xs text-fg-3 px-1">
        <button
          type="button"
          disabled={safeIndex <= 0}
          onClick={() => {
            setRevealed(false);
            setCurrentIndex(Math.max(0, safeIndex - 1));
          }}
          className="flex items-center gap-1 hover:text-fg disabled:opacity-30 disabled:pointer-events-none"
        >
          <ChevronLeft size={14} /> Cartão Anterior
        </button>
        <button
          type="button"
          disabled={safeIndex >= totalCards - 1}
          onClick={() => {
            setRevealed(false);
            setCurrentIndex(Math.min(totalCards - 1, safeIndex + 1));
          }}
          className="flex items-center gap-1 hover:text-fg disabled:opacity-30 disabled:pointer-events-none"
        >
          Próximo Cartão <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}
