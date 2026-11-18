import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { keys, useAuthMe, useLesson, useLessons, useQuestions, useStudyPanel } from '@/app/queries';
import { api } from '@/lib/api';
import { useWorkspaceMode } from '@/lib/auth';
import type { LessonFlashcard, LessonQuestionDetail } from '@/lib/types';
import {
  STAGE_LABELS,
  useLessonStageProgress,
  useStudentActivityLog,
} from '@/lib/lesson-progress';
import { useUserStorage } from '@/lib/user-storage';
import { LessonCatalogView, type CreateCustomLessonInput } from './lessons/LessonCatalogView';
import { LessonFlashcardsStage } from './lessons/LessonFlashcardsStage';
import { LessonPracticeStage } from './lessons/LessonPracticeStage';
import { LessonTheoryStage } from './lessons/LessonTheoryStage';
import { LessonVideoStage, type SyncedVideoNote } from './lessons/LessonVideoStage';
import { LessonVisualStage } from './lessons/LessonVisualStage';
import { LessonWorkspaceShell, type LessonStageKey } from './lessons/LessonWorkspaceShell';

export function LessonsView() {
  const queryClient = useQueryClient();
  const authMe = useAuthMe();
  const userId = authMe.data?.user?.id ?? null;
  const [workspaceMode] = useWorkspaceMode(authMe.data?.user?.role);
  const [searchParams, setSearchParams] = useSearchParams();
  const aulaParam = searchParams.get('aula');

  const [selectedDisciplina, setSelectedDisciplina] = useState('');
  const [activeLessonId, setActiveLessonId] = useState<string | null>(aulaParam);
  const [activeTab, setActiveTab] = useState<LessonStageKey>('resumo');
  const [tutorOpen, setTutorOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const authReady = !authMe.isLoading;
  const [completedLessons, setCompletedLessons] = useUserStorage<string[]>(
    'completed_lessons',
    [],
    userId,
    'radar_completed_lessons',
    authReady,
  );
  const [completedChapters, setCompletedChapters] = useUserStorage<Record<string, boolean>>(
    'completed_video_chapters',
    {},
    userId,
    'radar_completed_video_chapters',
    authReady,
  );
  const [lessonNotes, setLessonNotes] = useUserStorage<Record<string, SyncedVideoNote[]>>(
    'lesson_synced_notes',
    {},
    userId,
    'radar_lesson_synced_notes',
    authReady,
  );
  const [favoriteFlashcards, setFavoriteFlashcards] = useUserStorage<Record<string, boolean>>(
    'favorite_flashcards',
    {},
    userId,
    'radar_favorite_flashcards',
    authReady,
  );
  const stageProgress = useLessonStageProgress(userId, authReady);
  const activityLog = useStudentActivityLog(userId, authReady);

  const [savedFlashcards, setSavedFlashcards] = useState<Record<string, boolean>>({});
  const [cardDifficultyRatings, setCardDifficultyRatings] = useState<Record<string, string>>({});
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, string>>({});
  const [revealedQuestions, setRevealedQuestions] = useState<Record<string, boolean>>({});
  const [questionConvertedToCard, setQuestionConvertedToCard] = useState<Record<string, boolean>>({});

  const studyPanel = useStudyPanel();
  const openSession = studyPanel.data?.sessao_aberta ?? null;
  const [localSeconds, setLocalSeconds] = useState(0);
  const [localRunning, setLocalRunning] = useState(false);
  const [serverElapsed, setServerElapsed] = useState(openSession?.elapsed_seconds ?? 0);

  useEffect(() => {
    if (aulaParam !== activeLessonId) {
      setActiveLessonId(aulaParam);
      setActiveTab('resumo');
    }
  }, [aulaParam, activeLessonId]);

  useEffect(() => {
    setServerElapsed(openSession?.elapsed_seconds ?? 0);
    if (!openSession || openSession.estado !== 'em_andamento') return;
    const started = Date.now();
    const base = openSession.elapsed_seconds ?? 0;
    const id = window.setInterval(() => setServerElapsed(base + (Date.now() - started) / 1000), 1000);
    return () => window.clearInterval(id);
  }, [openSession]);

  useEffect(() => {
    if (openSession || !localRunning) return;
    const id = window.setInterval(() => setLocalSeconds((s) => s + 1), 1000);
    return () => window.clearInterval(id);
  }, [openSession, localRunning]);

  const handleToggleTimer = async () => {
    try {
      if (!openSession) await api.post('/api/estudos/sessoes', { action: 'start', disciplina_id: null, modo: 'aula' });
      else if (openSession.estado === 'pausada') await api.post('/api/estudos/sessoes', { action: 'resume', id: openSession.id });
      else await api.post('/api/estudos/sessoes', { action: 'pause', id: openSession.id });
      await queryClient.invalidateQueries({ queryKey: keys.study() });
      await queryClient.invalidateQueries({ queryKey: keys.sessions() });
    } catch {
      setLocalRunning((r) => !r);
    }
  };

  const handleResetTimer = async () => {
    if (openSession) {
      try {
        await api.post('/api/estudos/sessoes', { action: 'finish', id: openSession.id });
        await queryClient.invalidateQueries({ queryKey: keys.study() });
        await queryClient.invalidateQueries({ queryKey: keys.sessions() });
        return;
      } catch {
        // fallback local
      }
    }
    setLocalSeconds(0);
  };

  const handleSelectLesson = (id: string | null) => {
    setActiveLessonId(id);
    setLocalSeconds(0);
    setActiveTab('resumo');
    const next = new URLSearchParams(searchParams);
    if (id) next.set('aula', id);
    else next.delete('aula');
    setSearchParams(next);
  };

  const { data: lessonsData, isLoading: lessonsLoading } = useLessons(selectedDisciplina || undefined);
  const { data: lessonData, isLoading: lessonLoading } = useLesson(activeLessonId);
  const { data: allQuestions } = useQuestions();

  const lessons = lessonsData?.aulas ?? [];
  const activeLesson = lessonData?.aula;
  const completedCount = lessons.filter((l) => completedLessons.includes(l.id)).length;
  const totalEarnedXp = useMemo(
    () =>
      completedCount * 120 +
      Object.keys(revealedQuestions).length * 25 +
      Object.keys(savedFlashcards).length * 15 +
      Object.keys(cardDifficultyRatings).length * 10 +
      Object.values(completedChapters).filter(Boolean).length * 20,
    [completedCount, revealedQuestions, savedFlashcards, cardDifficultyRatings, completedChapters],
  );

  const activeLessonQuestions: LessonQuestionDetail[] = useMemo(() => {
    if (!activeLesson) return [];
    if (activeLesson.questoes_detalhadas?.length) return activeLesson.questoes_detalhadas;
    const ids = activeLesson.questoes_ids ?? [];
    return (allQuestions ?? [])
      .filter((q) => ids.includes(q.id))
      .map((q) => ({
        id: q.id,
        tipo: q.tipo || 'escolha_unica',
        disciplina: q.disciplina || activeLesson.disciplina,
        topico: q.topico || activeLesson.titulo,
        dificuldade: q.dificuldade || 'media',
        fonte: 'Prova Oficial de Concurso',
        enunciado: q.enunciado,
        gabarito: q.gabarito || 'A',
        comentario: q.comentario || 'Questão validada do acervo.',
        alternativas_formatadas: Array.isArray(q.alternativas)
          ? q.alternativas.map((a) => ({
              letra: a.letra,
              texto: a.texto,
              correta: a.letra === (q.gabarito || 'A'),
              justificativa: q.comentario || '',
            }))
          : [],
      }));
  }, [activeLesson, allQuestions]);

  const currentLessonIndex = lessons.findIndex((l) => l.id === activeLessonId);
  const prevLesson = currentLessonIndex > 0 ? lessons[currentLessonIndex - 1] : null;
  const nextLesson =
    currentLessonIndex >= 0 && currentLessonIndex < lessons.length - 1 ? lessons[currentLessonIndex + 1] : null;

  const handleCompleteAndAdvance = (fromStage: LessonStageKey, toStage: LessonStageKey) => {
    if (activeLesson) {
      const alreadyDone = stageProgress.isStageCompleted(activeLesson.id, fromStage);
      const nextPct = stageProgress.markStageCompleted(activeLesson.id, fromStage);
      if (!alreadyDone) {
        activityLog.logActivity({
          type: 'etapa_concluida',
          title: `Concluiu ${STAGE_LABELS[fromStage]} (${nextPct}%)`,
          subtitle: activeLesson.titulo,
          disciplina: activeLesson.disciplina,
          lessonId: activeLesson.id,
          stage: fromStage,
          pct: nextPct,
        });
      }
      if (nextPct === 100 && !completedLessons.includes(activeLesson.id)) {
        setCompletedLessons((prev) => (prev.includes(activeLesson.id) ? prev : [...prev, activeLesson.id]));
        activityLog.logActivity({
          type: 'aula_concluida',
          title: `Aula 100% concluída: ${activeLesson.titulo}`,
          disciplina: activeLesson.disciplina,
          lessonId: activeLesson.id,
          pct: 100,
        });
      }
    }
    setActiveTab(toStage);
  };

  const handleToggleStageCompleted = (stage: LessonStageKey) => {
    if (!activeLesson) return;
    const { completed, pct } = stageProgress.toggleStageCompleted(activeLesson.id, stage);
    if (completed) {
      activityLog.logActivity({
        type: 'etapa_concluida',
        title: `Concluiu ${STAGE_LABELS[stage]} (${pct}%)`,
        subtitle: activeLesson.titulo,
        disciplina: activeLesson.disciplina,
        lessonId: activeLesson.id,
        stage,
        pct,
      });
      if (pct === 100 && !completedLessons.includes(activeLesson.id)) {
        setCompletedLessons((prev) => (prev.includes(activeLesson.id) ? prev : [...prev, activeLesson.id]));
        activityLog.logActivity({
          type: 'aula_concluida',
          title: `Aula 100% concluída: ${activeLesson.titulo}`,
          disciplina: activeLesson.disciplina,
          lessonId: activeLesson.id,
          pct: 100,
        });
      }
    } else if (completedLessons.includes(activeLesson.id)) {
      setCompletedLessons((prev) => prev.filter((id) => id !== activeLesson.id));
    }
  };

  const handleToggleLessonCompleted = () => {
    if (!activeLesson) return;
    const wasDone = completedLessons.includes(activeLesson.id);
    if (wasDone) {
      setCompletedLessons((prev) => prev.filter((id) => id !== activeLesson.id));
      stageProgress.clearLessonStages(activeLesson.id);
    } else {
      stageProgress.markAllStagesCompleted(activeLesson.id);
      setCompletedLessons((prev) => (prev.includes(activeLesson.id) ? prev : [...prev, activeLesson.id]));
      activityLog.logActivity({
        type: 'aula_concluida',
        title: `Aula marcada como 100% concluída: ${activeLesson.titulo}`,
        disciplina: activeLesson.disciplina,
        lessonId: activeLesson.id,
        pct: 100,
      });
    }
  };

  const handleSaveFlashcard = async (fc: LessonFlashcard, customQualityLabel?: string) => {
    if (customQualityLabel) setCardDifficultyRatings((prev) => ({ ...prev, [fc.id]: customQualityLabel }));
    setActionError(null);
    try {
      await api.post('/api/estudos/flashcards', {
        frente: fc.frente,
        verso: `${fc.verso}${fc.mnemonico ? `\n\n💡 Mnemônico: ${fc.mnemonico}` : ''}`,
        tags: [fc.tag, fc.tipo || 'visual'].filter(Boolean),
        fonte: activeLesson?.titulo || 'Aula GSN',
      });
      setSavedFlashcards((prev) => ({ ...prev, [fc.id]: true }));
      activityLog.logActivity({
        type: 'flashcard_salvo',
        title: `Salvou flashcard na fila SM-2: ${fc.frente.slice(0, 64)}`,
        subtitle: activeLesson?.titulo,
        disciplina: activeLesson?.disciplina,
        lessonId: activeLesson?.id,
      });
      void queryClient.invalidateQueries({ queryKey: keys.flashQueue() });
      void queryClient.invalidateQueries({ queryKey: keys.flashStats() });
    } catch (err) {
      setActionError((err as Error).message || 'Não foi possível salvar o flashcard na fila SM-2.');
    }
  };

  const handleSelectOption = (questionId: string, optionKey: string) => {
    if (revealedQuestions[questionId]) return;
    setSelectedAnswers((prev) => ({ ...prev, [questionId]: optionKey }));
    setRevealedQuestions((prev) => ({ ...prev, [questionId]: true }));
    const qObj = activeLessonQuestions.find((q) => q.id === questionId);
    const isCorrect = qObj ? optionKey === qObj.gabarito : undefined;
    activityLog.logActivity({
      type: 'questao_respondida',
      title: `Respondeu questão (${isCorrect ? 'Acerto ✓' : 'Revisar'}): ${(qObj?.topico || activeLesson?.titulo || 'Prática').slice(0, 56)}`,
      subtitle: activeLesson?.titulo,
      disciplina: qObj?.disciplina || activeLesson?.disciplina,
      lessonId: activeLesson?.id,
      correct: isCorrect,
    });
    if (activeLesson && !stageProgress.isStageCompleted(activeLesson.id, 'questoes')) {
      const answeredAfter = Object.keys(revealedQuestions).length + 1;
      if (answeredAfter >= Math.max(1, activeLessonQuestions.length)) {
        const nextPct = stageProgress.markStageCompleted(activeLesson.id, 'questoes');
        activityLog.logActivity({
          type: 'etapa_concluida',
          title: `Concluiu ${STAGE_LABELS.questoes} (${nextPct}%)`,
          subtitle: activeLesson.titulo,
          disciplina: activeLesson.disciplina,
          lessonId: activeLesson.id,
          stage: 'questoes',
          pct: nextPct,
        });
      }
    }
    void api
      .post('/api/estudos/tentativas', { questao_id: questionId, resposta: optionKey, modo: 'aula' })
      .then(() => {
        void queryClient.invalidateQueries({ queryKey: keys.performance() });
        void queryClient.invalidateQueries({ queryKey: keys.study() });
      })
      .catch(() => {});
  };

  const handleConvertQuestionToFlashcard = async (q: LessonQuestionDetail) => {
    setActionError(null);
    try {
      await api.post('/api/estudos/flashcards', {
        frente: `[Questão de Prova - ${q.banca_sigla || 'Oficial'}] ${q.enunciado}`,
        verso: `Gabarito: ${q.gabarito}\n\nFundamentação: ${q.comentario}`,
        tags: [q.disciplina, q.banca_sigla || 'Prova'].filter(Boolean),
        fonte: q.fonte || activeLesson?.titulo || 'Caderno da Aula',
      });
      setQuestionConvertedToCard((prev) => ({ ...prev, [q.id]: true }));
      void queryClient.invalidateQueries({ queryKey: keys.flashQueue() });
      void queryClient.invalidateQueries({ queryKey: keys.flashStats() });
    } catch (err) {
      setActionError((err as Error).message || 'Não foi possível converter a questão em flashcard.');
    }
  };

  const handleCreateCustomLesson = async (payload: CreateCustomLessonInput) => {
    const res = await api.post<{ ok: boolean; aula: { id: string } }>('/api/estudos/aulas', payload);
    await queryClient.invalidateQueries({ queryKey: ['study', 'lessons'] });
    if (res?.aula?.id) handleSelectLesson(res.aula.id);
  };

  const isActiveCompleted = Boolean(activeLesson && completedLessons.includes(activeLesson.id));
  const activeCompletedStages = activeLesson ? stageProgress.getCompletedStages(activeLesson.id) : [];
  const activeLessonPct = activeLesson ? stageProgress.getLessonPercent(activeLesson.id, isActiveCompleted) : 0;

  return (
    <div className="space-y-6">
      {actionError && (
        <div
          role="alert"
          className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-2.5 text-xs font-medium text-risk-ink flex items-center justify-between gap-2"
        >
          <span>{actionError}</span>
          <button type="button" onClick={() => setActionError(null)} className="text-risk-ink hover:text-fg">
            <X size={14} />
          </button>
        </div>
      )}

      {!activeLessonId ? (
        <LessonCatalogView
          lessons={lessons}
          lessonsLoading={lessonsLoading}
          completedLessons={completedLessons}
          getLessonPercent={stageProgress.getLessonPercent}
          totalEarnedXp={totalEarnedXp}
          selectedDisciplina={selectedDisciplina}
          onSelectDisciplina={setSelectedDisciplina}
          onSelectLesson={handleSelectLesson}
          isAdmin={workspaceMode === 'admin'}
          onCreateLesson={handleCreateCustomLesson}
        />
      ) : (
        <LessonWorkspaceShell
          lessonLoading={lessonLoading}
          lesson={activeLesson}
          questionsCount={activeLessonQuestions.length}
          activeTab={activeTab}
          onSelectTab={setActiveTab}
          completedStages={activeCompletedStages}
          lessonPercent={activeLessonPct}
          onToggleStageCompleted={handleToggleStageCompleted}
          studySeconds={openSession ? serverElapsed : localSeconds}
          timerRunning={openSession ? openSession.estado === 'em_andamento' : localRunning}
          hasSession={Boolean(openSession || localRunning || localSeconds > 0)}
          onToggleTimer={() => void handleToggleTimer()}
          onResetTimer={() => void handleResetTimer()}
          tutorOpen={tutorOpen}
          onToggleTutor={() => setTutorOpen((o) => !o)}
          isCompleted={isActiveCompleted}
          onToggleCompleted={handleToggleLessonCompleted}
          prevLesson={prevLesson}
          nextLesson={nextLesson}
          onSelectLesson={handleSelectLesson}
        >
          {activeLesson && activeTab === 'resumo' && (
            <LessonTheoryStage
              lesson={activeLesson}
              onNextStage={() => handleCompleteAndAdvance('resumo', 'visual')}
            />
          )}
          {activeLesson && activeTab === 'visual' && (
            <LessonVisualStage
              key={activeLesson.id}
              lesson={activeLesson}
              onNextStage={() => handleCompleteAndAdvance('visual', 'video')}
            />
          )}
          {activeLesson && activeTab === 'video' && (
            <LessonVideoStage
              key={activeLesson.id}
              lesson={activeLesson}
              notes={lessonNotes[activeLesson.id] ?? []}
              onMarkChapterCompleted={(chapterId) => setCompletedChapters((prev) => ({ ...prev, [chapterId]: true }))}
              onAddNote={(note) => {
                setLessonNotes((prev) => ({
                  ...prev,
                  [activeLesson.id]: [note, ...(prev[activeLesson.id] ?? [])],
                }));
                activityLog.logActivity({
                  type: 'anotacao_video',
                  title: `Registrou anotação na videoaula (${note.timestampLabel})`,
                  subtitle: activeLesson.titulo,
                  disciplina: activeLesson.disciplina,
                  lessonId: activeLesson.id,
                });
              }}
              onNextStage={() => handleCompleteAndAdvance('video', 'flashcards')}
            />
          )}
          {activeLesson && activeTab === 'flashcards' && (
            <LessonFlashcardsStage
              lesson={activeLesson}
              savedFlashcards={savedFlashcards}
              favoriteFlashcards={favoriteFlashcards}
              cardDifficultyRatings={cardDifficultyRatings}
              onSaveCard={(fc, rating) => void handleSaveFlashcard(fc, rating)}
              onToggleFavorite={(cardId) => setFavoriteFlashcards((prev) => ({ ...prev, [cardId]: !prev[cardId] }))}
              onNextStage={() => handleCompleteAndAdvance('flashcards', 'questoes')}
            />
          )}
          {activeLesson && activeTab === 'questoes' && (
            <LessonPracticeStage
              key={activeLesson.id}
              lesson={activeLesson}
              questions={activeLessonQuestions}
              selectedAnswers={selectedAnswers}
              revealedQuestions={revealedQuestions}
              questionConvertedToCard={questionConvertedToCard}
              onSelectOption={handleSelectOption}
              onConvertQuestionToFlashcard={(q) => void handleConvertQuestionToFlashcard(q)}
            />
          )}
        </LessonWorkspaceShell>
      )}
    </div>
  );
}
