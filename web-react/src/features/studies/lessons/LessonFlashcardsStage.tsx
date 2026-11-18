import { ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { LessonDetail, LessonFlashcard } from '@/lib/types';
import { JottaFlashcardGrid } from '../JottaFlashcardView';

interface LessonFlashcardsStageProps {
  lesson: LessonDetail;
  savedFlashcards: Record<string, boolean>;
  favoriteFlashcards: Record<string, boolean>;
  cardDifficultyRatings: Record<string, string>;
  onSaveCard: (card: LessonFlashcard, ratingLabel?: string) => void;
  onToggleFavorite: (cardId: string) => void;
  onNextStage: () => void;
}

export function LessonFlashcardsStage({
  lesson,
  savedFlashcards,
  favoriteFlashcards,
  cardDifficultyRatings,
  onSaveCard,
  onToggleFavorite,
  onNextStage,
}: LessonFlashcardsStageProps) {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border-l-4 border-l-amber-400 border border-line-strong bg-surface p-5">
        <div>
          <span className="text-xs font-black uppercase tracking-widest text-accent-ink">
            ETAPA 4 DE 5 · FLASHCARDS VISUAIS ESQUEMATIZADOS
          </span>
          <h2 className="mt-1 font-display text-xl font-extrabold text-fg">
            Fichas de Memorização Visual da Aula
          </h2>
        </div>
        <Button variant="primary" size="sm" onClick={onNextStage} className="gap-1.5 font-extrabold">
          <span>Ir para Etapa 5: Questões & Domínio</span>
          <ArrowRight size={14} />
        </Button>
      </div>

      <JottaFlashcardGrid
        cards={lesson.flashcards ?? []}
        savedFlashcards={savedFlashcards}
        favoriteFlashcards={favoriteFlashcards}
        cardDifficultyRatings={cardDifficultyRatings}
        onSaveCard={onSaveCard}
        onToggleFavorite={onToggleFavorite}
      />
    </div>
  );
}
