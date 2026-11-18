import { renderHook, act } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import {
  LESSON_STAGES,
  computeLessonPercent,
  useLessonStageProgress,
  useStudentActivityLog,
} from './lesson-progress';

beforeEach(() => {
  localStorage.clear();
});

describe('lesson-progress & activity log', () => {
  it('calcula 0%, 20%, 40%, 60%, 80% e 100% conforme as 5 etapas da aula', () => {
    expect(LESSON_STAGES).toHaveLength(5);
    expect(computeLessonPercent({})).toBe(0);
    expect(computeLessonPercent({ resumo: '2026-11-18T00:00:00Z' })).toBe(20);
    expect(
      computeLessonPercent({
        resumo: '2026-11-18T00:00:00Z',
        visual: '2026-11-18T00:01:00Z',
      }),
    ).toBe(40);
    expect(
      computeLessonPercent({
        resumo: '1',
        visual: '1',
        video: '1',
        flashcards: '1',
        questoes: '1',
      }),
    ).toBe(100);
    expect(computeLessonPercent({}, true)).toBe(100);
  });

  it('persiste etapas e histórico de atividades isolados por usuário (radar:u:<uid>:*)', () => {
    const { result: anaProgress } = renderHook(() => useLessonStageProgress('usr-ana', true));
    const { result: anaLog } = renderHook(() => useStudentActivityLog('usr-ana', true));

    act(() => {
      const nextPct = anaProgress.current.markStageCompleted('bd-01', 'resumo');
      anaLog.current.logActivity({
        type: 'etapa_concluida',
        title: 'Etapa 1 concluída: Resumo & Teoria',
        subtitle: 'Aula 01: Modelagem',
        disciplina: 'Banco de Dados',
        lessonId: 'bd-01',
        stage: 'resumo',
        pct: nextPct,
      });
    });

    expect(anaProgress.current.getLessonPercent('bd-01')).toBe(20);
    expect(anaLog.current.activities).toHaveLength(1);
    expect(anaLog.current.activities[0].pct).toBe(20);

    // Outro estudante não herda etapas nem histórico de Ana
    const { result: brunoProgress } = renderHook(() => useLessonStageProgress('usr-bruno', true));
    const { result: brunoLog } = renderHook(() => useStudentActivityLog('usr-bruno', true));
    expect(brunoProgress.current.getLessonPercent('bd-01')).toBe(0);
    expect(brunoLog.current.activities).toHaveLength(0);
  });
});
