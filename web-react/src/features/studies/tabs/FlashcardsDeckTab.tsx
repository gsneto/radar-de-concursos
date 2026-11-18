import { lazy, Suspense, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Sparkles, Zap } from 'lucide-react';
import { keys, useAuthMe, useFlashQueue, useFlashStats, useVisualFlashcards } from '@/app/queries';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Kpi, NumberTicker } from '@/components/ui/kpi';
import { SkeletonRows } from '@/components/ui/states';
import { api } from '@/lib/api';
import { integer } from '@/lib/format';
import type { LessonFlashcard } from '@/lib/types';
import { useUserStorage } from '@/lib/user-storage';
import { Sm2ReviewDeck } from './Sm2ReviewDeck';

const JottaFlashcardGrid = lazy(() =>
  import('../JottaFlashcardView').then((m) => ({ default: m.JottaFlashcardGrid })),
);

const AVAILABLE_DISCIPLINES = [
  'Banco de Dados',
  'Engenharia de Software',
  'Redes de Computadores',
  'Segurança da Informação',
  'Língua Portuguesa',
  'Direito Constitucional',
] as const;

export function FlashcardsDeckTab() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const authMe = useAuthMe();
  const userId = authMe.data?.user?.id ?? null;
  const stats = useFlashStats();
  const queue = useFlashQueue();
  const [selectedDiscipline, setSelectedDiscipline] = useState('');
  const visualDeck = useVisualFlashcards(selectedDiscipline || undefined);
  const [viewMode, setViewMode] = useState<'visuais' | 'sm2'>('visuais');
  const [savedIds, setSavedIds] = useState<Record<string, boolean>>({});
  const [favoriteIds, setFavoriteIds] = useUserStorage<Record<string, boolean>>(
    'favorite_flashcards',
    {},
    userId,
    'radar_favorite_flashcards',
    !authMe.isLoading,
  );
  const [difficultyRatings, setDifficultyRatings] = useState<Record<string, string>>({});
  const [showCreate, setShowCreate] = useState(false);
  const [newFront, setNewFront] = useState('');
  const [newBack, setNewBack] = useState('');
  const [newTags, setNewTags] = useState('');

  const cards = useMemo(
    () => (queue.data ? [...(queue.data.novos ?? []), ...(queue.data.vencidos ?? [])] : []),
    [queue.data],
  );

  const createCard = useMutation({
    mutationFn: (body: { action: string; frente: string; verso: string; tags: string[] }) =>
      api.post('/api/estudos/flashcards', body),
    onSuccess: () => {
      setShowCreate(false);
      setNewFront('');
      setNewBack('');
      setNewTags('');
      void queryClient.invalidateQueries({ queryKey: keys.flashQueue() });
      void queryClient.invalidateQueries({ queryKey: keys.flashStats() });
    },
  });

  const saveVisualCardToDeck = useMutation({
    mutationFn: (fc: LessonFlashcard) =>
      api.post('/api/estudos/flashcards', {
        action: 'create',
        frente: fc.frente,
        verso: `${fc.verso}${fc.mnemonico ? `\n\n💡 Mnemônico: ${fc.mnemonico}` : ''}`,
        tags: [fc.disciplina ?? 'Geral', fc.aula_titulo ?? 'Conceito', 'flashcard-visual-jotta'],
      }),
    onSuccess: (_, fc) => {
      setSavedIds((prev) => ({ ...prev, [fc.id]: true }));
      void queryClient.invalidateQueries({ queryKey: keys.flashQueue() });
      void queryClient.invalidateQueries({ queryKey: keys.flashStats() });
    },
  });

  if (stats.isLoading || queue.isLoading) return <SkeletonRows rows={4} />;
  const visualCards = visualDeck.data?.flashcards ?? [];

  return (
    <div className="space-y-5">
      <section aria-label="Indicadores de flashcards" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <Kpi
          feature
          tone="accent"
          label="Mapas Visuais Estilo Jotta"
          value={<NumberTicker value={visualCards.length} />}
          context="Esquemas gráficos prontos de todas as aulas"
        />
        <Kpi
          label="Cartões na Fila SM-2"
          value={<NumberTicker value={stats.data?.ativos ?? 0} />}
          context={`${integer(stats.data?.novos ?? 0)} novos · ${integer(stats.data?.pendentes ?? 0)} para revisar hoje`}
        />
        <Kpi
          label="Revisões Registradas"
          value={<NumberTicker value={stats.data?.revisoes ?? 0} />}
          context={stats.data?.basis ?? 'Repetição espaçada SM-2 ativa'}
        />
      </section>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-surface p-3 shadow-sm">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setViewMode('visuais')}
            className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs font-extrabold transition-all ${
              viewMode === 'visuais'
                ? 'bg-amber-400 text-slate-950 shadow-sm'
                : 'bg-surface-2 text-fg-2 hover:text-fg border border-line'
            }`}
          >
            <Sparkles size={15} />
            Mapas & Flashcards Visuais (Estilo Jotta) ({visualCards.length})
          </button>
          <button
            type="button"
            onClick={() => setViewMode('sm2')}
            className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs font-extrabold transition-all ${
              viewMode === 'sm2'
                ? 'bg-amber-400 text-slate-950 shadow-sm'
                : 'bg-surface-2 text-fg-2 hover:text-fg border border-line'
            }`}
          >
            <Zap size={15} />
            Fila de Revisão Espaçada SM-2 ({cards.length})
          </button>
        </div>

        <Button variant="secondary" size="sm" onClick={() => setShowCreate(!showCreate)} className="gap-1.5">
          <Plus size={14} /> Criar Cartão Próprio
        </Button>
      </div>

      {showCreate && (
        <Card title="Criar Novo Flashcard" subtitle="Adicione uma pergunta ou conceito para memorização ativa.">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!newFront.trim() || !newBack.trim()) return;
              createCard.mutate({
                action: 'create',
                frente: newFront.trim(),
                verso: newBack.trim(),
                tags: newTags.split(',').map((t) => t.trim()).filter(Boolean),
              });
            }}
            className="space-y-3"
          >
            <div>
              <label className="text-2xs font-semibold uppercase tracking-wider text-fg-3">
                Frente (Pergunta / Conceito)
              </label>
              <textarea
                value={newFront}
                onChange={(e) => setNewFront(e.target.value)}
                placeholder="Ex: O que é o Teorema CAP em bancos NoSQL?"
                required
                className="mt-1 w-full rounded-xl border border-line bg-surface-2 p-3 text-xs text-fg placeholder:text-fg-3/60 focus:border-amber-400 focus:outline-none"
                rows={2}
              />
            </div>
            <div>
              <label className="text-2xs font-semibold uppercase tracking-wider text-fg-3">
                Verso (Resposta / Explicação)
              </label>
              <textarea
                value={newBack}
                onChange={(e) => setNewBack(e.target.value)}
                placeholder="Ex: Em sistemas distribuídos, só é possível garantir 2 de 3 propriedades: Consistência, Disponibilidade e Tolerância a Partições."
                required
                className="mt-1 w-full rounded-xl border border-line bg-surface-2 p-3 text-xs text-fg placeholder:text-fg-3/60 focus:border-amber-400 focus:outline-none"
                rows={3}
              />
            </div>
            <div>
              <label className="text-2xs font-semibold uppercase tracking-wider text-fg-3">
                Tags (separadas por vírgula)
              </label>
              <input
                type="text"
                value={newTags}
                onChange={(e) => setNewTags(e.target.value)}
                placeholder="banco-de-dados, nosql, ti"
                className="mt-1 w-full rounded-xl border border-line bg-surface-2 px-3 py-2 text-xs text-fg placeholder:text-fg-3/60 focus:border-amber-400 focus:outline-none"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" size="sm" onClick={() => setShowCreate(false)}>
                Cancelar
              </Button>
              <Button variant="primary" size="sm" type="submit" disabled={createCard.isPending}>
                Salvar Flashcard
              </Button>
            </div>
          </form>
        </Card>
      )}

      {viewMode === 'visuais' ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setSelectedDiscipline('')}
              className={`rounded-xl px-3.5 py-2 text-xs font-bold transition-all ${
                selectedDiscipline === ''
                  ? 'bg-fg text-bg shadow-xs'
                  : 'border border-line bg-surface text-fg-2 hover:text-fg'
              }`}
            >
              Todas as Matérias
            </button>
            {AVAILABLE_DISCIPLINES.map((disc) => (
              <button
                key={disc}
                type="button"
                onClick={() => setSelectedDiscipline(disc)}
                className={`rounded-xl px-3.5 py-2 text-xs font-bold transition-all ${
                  selectedDiscipline === disc
                    ? 'bg-fg text-bg shadow-xs'
                    : 'border border-line bg-surface text-fg-2 hover:text-fg'
                }`}
              >
                {disc}
              </button>
            ))}
          </div>

          {visualDeck.isLoading ? (
            <SkeletonRows rows={4} />
          ) : (
            <Suspense fallback={<SkeletonRows rows={4} />}>
              <JottaFlashcardGrid
                cards={visualCards}
                savedFlashcards={savedIds}
                favoriteFlashcards={favoriteIds}
                cardDifficultyRatings={difficultyRatings}
                onSaveCard={(fc: LessonFlashcard, ratingLabel?: string) => {
                  if (ratingLabel) setDifficultyRatings((prev) => ({ ...prev, [fc.id]: ratingLabel }));
                  if (!savedIds[fc.id]) saveVisualCardToDeck.mutate(fc);
                }}
                onToggleFavorite={(cardId: string) =>
                  setFavoriteIds((prev) => ({ ...prev, [cardId]: !prev[cardId] }))
                }
                showLessonBadge
                onSelectLesson={(lessonId: string) => {
                  navigate(`/estudos/aulas?aula=${encodeURIComponent(lessonId)}`);
                }}
              />
            </Suspense>
          )}
        </div>
      ) : (
        <Sm2ReviewDeck
          cards={cards}
          futureCount={queue.data?.futuros.length ?? 0}
          onSwitchToVisual={() => setViewMode('visuais')}
        />
      )}
    </div>
  );
}
