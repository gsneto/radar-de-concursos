import { type ReactNode } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Bot,
  CheckCircle2,
  Clock,
  Layers,
  Network,
  Pause,
  Play,
  RotateCcw,
  Target,
  Trophy,
  Video,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SkeletonRows } from '@/components/ui/states';
import { clock } from '@/lib/format';
import type { LessonDetail, LessonSummary } from '@/lib/types';
import { LessonTutorDrawer } from './LessonTutorDrawer';

export type LessonStageKey = 'resumo' | 'visual' | 'video' | 'flashcards' | 'questoes';

interface LessonWorkspaceShellProps {
  lessonLoading: boolean;
  lesson?: LessonDetail;
  questionsCount: number;
  activeTab: LessonStageKey;
  onSelectTab: (tab: LessonStageKey) => void;
  studySeconds: number;
  timerRunning: boolean;
  onToggleTimer: () => void;
  onResetTimer: () => void;
  tutorOpen: boolean;
  onToggleTutor: () => void;
  isCompleted: boolean;
  onToggleCompleted: () => void;
  prevLesson: LessonSummary | null;
  nextLesson: LessonSummary | null;
  onSelectLesson: (id: string | null) => void;
  children: ReactNode;
}

export function LessonWorkspaceShell({
  lessonLoading,
  lesson,
  questionsCount,
  activeTab,
  onSelectTab,
  studySeconds,
  timerRunning,
  onToggleTimer,
  onResetTimer,
  tutorOpen,
  onToggleTutor,
  isCompleted,
  onToggleCompleted,
  prevLesson,
  nextLesson,
  onSelectLesson,
  children,
}: LessonWorkspaceShellProps) {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line-strong bg-surface px-5 py-3.5 shadow-md">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onSelectLesson(null)}
          className="gap-2 text-xs font-extrabold"
        >
          <ArrowLeft size={15} /> Voltar para Todas as Aulas
        </Button>

        <div className="flex flex-wrap items-center gap-2.5">
          <div className="flex items-center gap-2 rounded-xl border border-line-strong bg-surface-2 px-3.5 py-1.5">
            <Clock size={14} className="text-amber-400" />
            <span className="font-mono text-xs font-extrabold tabular text-fg">{clock(studySeconds)}</span>
            <button
              type="button"
              onClick={onToggleTimer}
              className="rounded p-1 text-fg-2 hover:text-fg"
              title={timerRunning ? 'Pausar' : 'Retomar'}
            >
              {timerRunning ? <Pause size={13} /> : <Play size={13} />}
            </button>
            <button
              type="button"
              onClick={onResetTimer}
              className="rounded p-1 text-fg-2 hover:text-fg"
              title="Zerar ou concluir sessão"
            >
              <RotateCcw size={12} />
            </button>
          </div>

          <button
            type="button"
            onClick={onToggleTutor}
            className={`flex items-center gap-1.5 rounded-xl border px-3.5 py-2 text-xs font-extrabold transition-all ${
              tutorOpen
                ? 'border-amber-400 bg-amber-400 text-slate-950'
                : 'border-amber-400/50 bg-amber-400/15 text-accent-ink hover:bg-amber-400/25'
            }`}
          >
            <Bot size={15} /> Professor Virtual
          </button>

          {lesson && (
            <button
              type="button"
              onClick={onToggleCompleted}
              className={`flex items-center gap-1.5 rounded-xl border px-3.5 py-2 text-xs font-extrabold transition-all ${
                isCompleted
                  ? 'border-emerald-500/50 bg-emerald-500/20 text-ok-ink'
                  : 'border-line-strong bg-surface-2 text-fg hover:border-amber-400'
              }`}
            >
              <CheckCircle2 size={15} />
              {isCompleted ? 'Aula Concluída' : 'Marcar Concluída'}
            </button>
          )}
        </div>
      </div>

      {lessonLoading || !lesson ? (
        <SkeletonRows rows={6} />
      ) : (
        <>
          <LessonTutorDrawer open={tutorOpen} onClose={onToggleTutor} tutor={lesson.tutor_contextual} />

          <div className="rounded-2xl border border-line-strong bg-surface p-6 shadow-md space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-md bg-amber-400 px-2.5 py-1 text-xs font-black uppercase tracking-wider text-slate-950">
                {lesson.disciplina}
              </span>
              <span className="rounded-md border border-line-strong bg-surface-2 px-2.5 py-1 text-xs font-bold text-fg-2">
                {lesson.modulo || 'Módulo Principal'}
              </span>
              <span className="rounded-md border border-line-strong bg-surface-2 px-2.5 py-1 text-xs font-bold text-fg-2">
                ⏱ {lesson.tempo_estimado_min || 45} min
              </span>
            </div>
            <h1 className="font-display text-2xl sm:text-3xl font-extrabold text-fg leading-tight">
              {lesson.titulo}
            </h1>
            <div className="grid gap-2.5 sm:grid-cols-3 pt-1">
              {lesson.objetivos.map((obj, idx) => (
                <div
                  key={idx}
                  className="flex items-start gap-2.5 rounded-xl border border-line-strong bg-surface-2/70 p-3"
                >
                  <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-amber-400/20 text-xs font-black text-accent-ink">
                    {idx + 1}
                  </span>
                  <span className="text-xs font-medium text-fg leading-relaxed">{obj}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 rounded-2xl border border-line-strong bg-surface-2 p-2 shadow-sm">
            {(
              [
                { key: 'resumo', icon: BookOpen, label: '1. Resumo & Teoria' },
                { key: 'visual', icon: Network, label: '2. Quadro Digital & Mapa Mental' },
                { key: 'video', icon: Video, label: `3. Videoaula Recomendada (${(lesson.videoaulas ?? []).length})` },
                { key: 'flashcards', icon: Layers, label: `4. Flashcards Visuais (${(lesson.flashcards ?? []).length})` },
                { key: 'questoes', icon: Target, label: `5. Questões & Avaliação de Domínio (${questionsCount})` },
              ] as const
            ).map((stage) => {
              const Icon = stage.icon;
              return (
                <button
                  key={stage.key}
                  type="button"
                  onClick={() => onSelectTab(stage.key)}
                  className={`flex items-center justify-center gap-2 rounded-xl px-3 py-3 text-xs font-extrabold transition-all ${
                    activeTab === stage.key
                      ? 'bg-amber-400 text-slate-950 shadow-sm'
                      : 'bg-surface text-fg-2 hover:text-fg'
                  }`}
                >
                  <Icon size={15} />
                  <span>{stage.label}</span>
                </button>
              );
            })}
          </div>

          {children}

          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 rounded-2xl border border-line-strong bg-surface p-5">
            {prevLesson ? (
              <Button variant="secondary" size="sm" onClick={() => onSelectLesson(prevLesson.id)} className="gap-2">
                <ArrowLeft size={14} /> Aula Anterior
              </Button>
            ) : (
              <div />
            )}

            {nextLesson ? (
              <Button
                variant="primary"
                size="sm"
                onClick={() => onSelectLesson(nextLesson.id)}
                className="gap-2 font-extrabold"
              >
                Próxima Aula: {nextLesson.titulo.slice(0, 38)}... <ArrowRight size={14} />
              </Button>
            ) : (
              <Button
                variant="primary"
                size="sm"
                onClick={() => onSelectLesson(null)}
                className="gap-2 font-extrabold"
              >
                <Trophy size={14} /> Concluir Trilha
              </Button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
