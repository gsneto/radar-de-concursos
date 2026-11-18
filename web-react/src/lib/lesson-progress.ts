import { useCallback } from 'react';
import { useUserStorage } from './user-storage';

export type LessonStageKey = 'resumo' | 'visual' | 'video' | 'flashcards' | 'questoes';

export const LESSON_STAGES: readonly {
  key: LessonStageKey;
  number: number;
  shortLabel: string;
}[] = [
  { key: 'resumo', number: 1, shortLabel: 'Resumo & Teoria' },
  { key: 'visual', number: 2, shortLabel: 'Quadro Digital' },
  { key: 'video', number: 3, shortLabel: 'Videoaula' },
  { key: 'flashcards', number: 4, shortLabel: 'Flashcards' },
  { key: 'questoes', number: 5, shortLabel: 'Questões' },
] as const;

export const STAGE_LABELS: Record<LessonStageKey, string> = {
  resumo: '1. Resumo & Teoria',
  visual: '2. Quadro Digital & Mapa Mental',
  video: '3. Videoaula Recomendada',
  flashcards: '4. Flashcards Visuais',
  questoes: '5. Questões & Avaliação',
};

export type LessonStagesRecord = Partial<Record<LessonStageKey, string>>;
export type AllLessonsStageMap = Record<string, LessonStagesRecord>;

export function computeLessonPercent(
  stages?: LessonStagesRecord,
  isCompleted = false,
): number {
  if (isCompleted) return 100;
  if (!stages) return 0;
  let count = 0;
  for (const s of LESSON_STAGES) {
    if (stages[s.key]) count += 1;
  }
  return Math.min(100, Math.round((count / LESSON_STAGES.length) * 100));
}

export function useLessonStageProgress(userId?: string | null, ready = true) {
  const [stageProgressMap, setStageProgressMap] = useUserStorage<AllLessonsStageMap>(
    'lesson_stage_progress',
    {},
    userId,
    undefined,
    ready,
  );

  const getCompletedStages = useCallback(
    (lessonId: string): LessonStageKey[] => {
      const rec = stageProgressMap[lessonId];
      if (!rec) return [];
      return LESSON_STAGES.filter((s) => Boolean(rec[s.key])).map((s) => s.key);
    },
    [stageProgressMap],
  );

  const isStageCompleted = useCallback(
    (lessonId: string, stage: LessonStageKey): boolean =>
      Boolean(stageProgressMap[lessonId]?.[stage]),
    [stageProgressMap],
  );

  const getLessonPercent = useCallback(
    (lessonId: string, isCompleted = false): number =>
      computeLessonPercent(stageProgressMap[lessonId], isCompleted),
    [stageProgressMap],
  );

  const markStageCompleted = useCallback(
    (lessonId: string, stage: LessonStageKey): number => {
      const now = new Date().toISOString();
      const nextForLesson: LessonStagesRecord = {
        ...(stageProgressMap[lessonId] ?? {}),
        [stage]: stageProgressMap[lessonId]?.[stage] ?? now,
      };
      const nextPct = computeLessonPercent(nextForLesson);
      setStageProgressMap((prev) => ({
        ...prev,
        [lessonId]: {
          ...(prev[lessonId] ?? {}),
          [stage]: prev[lessonId]?.[stage] ?? now,
        },
      }));
      return nextPct;
    },
    [stageProgressMap, setStageProgressMap],
  );

  const toggleStageCompleted = useCallback(
    (lessonId: string, stage: LessonStageKey): { completed: boolean; pct: number } => {
      const currentlyDone = Boolean(stageProgressMap[lessonId]?.[stage]);
      const now = new Date().toISOString();
      const nextLessonRecord: LessonStagesRecord = { ...(stageProgressMap[lessonId] ?? {}) };
      if (currentlyDone) {
        delete nextLessonRecord[stage];
      } else {
        nextLessonRecord[stage] = now;
      }
      const pct = computeLessonPercent(nextLessonRecord);
      setStageProgressMap((prev) => {
        const copy: LessonStagesRecord = { ...(prev[lessonId] ?? {}) };
        if (currentlyDone) delete copy[stage];
        else copy[stage] = now;
        return { ...prev, [lessonId]: copy };
      });
      return { completed: !currentlyDone, pct };
    },
    [stageProgressMap, setStageProgressMap],
  );

  const markAllStagesCompleted = useCallback(
    (lessonId: string) => {
      const now = new Date().toISOString();
      setStageProgressMap((prev) => {
        const existing = prev[lessonId] ?? {};
        const full: LessonStagesRecord = {};
        for (const s of LESSON_STAGES) {
          full[s.key] = existing[s.key] ?? now;
        }
        return { ...prev, [lessonId]: full };
      });
    },
    [setStageProgressMap],
  );

  const clearLessonStages = useCallback(
    (lessonId: string) => {
      setStageProgressMap((prev) => {
        const next = { ...prev };
        delete next[lessonId];
        return next;
      });
    },
    [setStageProgressMap],
  );

  return {
    stageProgressMap,
    getCompletedStages,
    isStageCompleted,
    getLessonPercent,
    markStageCompleted,
    toggleStageCompleted,
    markAllStagesCompleted,
    clearLessonStages,
  };
}

export type StudentActivityType =
  | 'etapa_concluida'
  | 'aula_concluida'
  | 'questao_respondida'
  | 'flashcard_salvo'
  | 'anotacao_video';

export interface StudentActivityItem {
  id: string;
  type: StudentActivityType;
  title: string;
  subtitle?: string;
  disciplina?: string;
  lessonId?: string;
  stage?: LessonStageKey;
  pct?: number;
  correct?: boolean;
  timestamp: string;
}

const MAX_ACTIVITY_ITEMS = 300;

export function useStudentActivityLog(userId?: string | null, ready = true) {
  const [activities, setActivities, clearActivities] = useUserStorage<StudentActivityItem[]>(
    'student_activity_log',
    [],
    userId,
    undefined,
    ready,
  );

  const logActivity = useCallback(
    (
      entry: Omit<StudentActivityItem, 'id' | 'timestamp'> & {
        timestamp?: string;
      },
    ) => {
      const item: StudentActivityItem = {
        ...entry,
        id: `act-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        timestamp: entry.timestamp ?? new Date().toISOString(),
      };
      setActivities((prev) => [item, ...prev].slice(0, MAX_ACTIVITY_ITEMS));
    },
    [setActivities],
  );

  return {
    activities,
    logActivity,
    clearActivities,
  };
}
