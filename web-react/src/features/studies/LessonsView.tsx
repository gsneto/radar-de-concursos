import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'motion/react';
import { keys, useLesson, useLessons, useQuestions } from '@/app/queries';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { SkeletonRows } from '@/components/ui/states';
import { api } from '@/lib/api';
import { clock } from '@/lib/format';
import type {
  LessonFlashcard,
  LessonInteractiveExercise,
  LessonQuestionDetail,
} from '@/lib/types';
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Award,
  BookOpen,
  Bot,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock,
  ExternalLink,
  Flame,
  GraduationCap,
  Layers,
  LayoutGrid,
  ListTree,
  Network,
  Pause,
  Play,
  Plus,
  RotateCcw,
  Search,
  Sparkles,
  Star,
  Target,
  Trophy,
  Video,
  X,
  XCircle,
  Zap,
} from 'lucide-react';

interface SyncedVideoNote {
  id: string;
  chapterTitle: string;
  timestampLabel: string;
  timestampSec: number;
  text: string;
  createdAt: string;
}

export function LessonsView() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const aulaParam = searchParams.get('aula');

  const [selectedDisciplina, setSelectedDisciplina] = useState<string>('');
  const [activeLessonId, setActiveLessonId] = useState<string | null>(aulaParam);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'todas' | 'pendentes' | 'concluidas'>('todas');
  const [catalogViewMode, setCatalogViewMode] = useState<'modulos' | 'grade'>('modulos');

  // 7 Etapas Conectadas da Jornada de Aprendizagem
  const [activeTab, setActiveTab] = useState<
    'resumo' | 'visual' | 'video' | 'flashcards' | 'bancas' | 'questoes' | 'avaliacao'
  >('resumo');

  // Professor Virtual (Assistente Contextual da Aula)
  const [tutorOpen, setTutorOpen] = useState<boolean>(false);
  const [activeTutorMode, setActiveTutorMode] = useState<
    'explicar_simples' | 'exemplo_pratico' | 'comparar_conceitos' | 'resumo_1_minuto'
  >('explicar_simples');
  const [tutorCustomFeedback, setTutorCustomFeedback] = useState<string | null>(null);

  // Studio de Produção de Conteúdo (Admin / Criação de Aula)
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [newLessonTitle, setNewLessonTitle] = useState<string>('');
  const [newLessonDisc, setNewLessonDisc] = useState<string>('Banco de Dados');
  const [newLessonMod, setNewLessonMod] = useState<string>('Módulo 1: Tópicos Especiais');
  const [newLessonSummary, setNewLessonSummary] = useState<string>('');
  const [newLessonObjective, setNewLessonObjective] = useState<string>('');
  const [creatingLesson, setCreatingLesson] = useState<boolean>(false);

  // Videoaula: player híbrido, capítulos, velocidade, checkpoints e notas sincronizadas
  const [selectedVideoIndex, setSelectedVideoIndex] = useState<number>(0);
  const [videoPresentationMode, setVideoPresentationMode] = useState<'video' | 'slides'>('video');
  const [activeSlideIdx, setActiveSlideIdx] = useState<number>(0);
  const [videoStartSec, setVideoStartSec] = useState<number>(0);
  const [activeChapterId, setActiveChapterId] = useState<string>('');
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);
  const [completedChapters, setCompletedChapters] = useState<Record<string, boolean>>(() => {
    try {
      const saved = localStorage.getItem('radar_completed_video_chapters');
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });
  const [checkpointAnswers, setCheckpointAnswers] = useState<Record<string, number>>({});
  const [noteInput, setNoteInput] = useState<string>('');
  const [lessonNotes, setLessonNotes] = useState<Record<string, SyncedVideoNote[]>>(() => {
    try {
      const saved = localStorage.getItem('radar_lesson_synced_notes');
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });

  // Quadro Visual e Mapa Mental Interativo
  const [activeVisualStep, setActiveVisualStep] = useState<number>(0);
  const [selectedMindMapNodeId, setSelectedMindMapNodeId] = useState<string | null>(null);

  // Flashcards Multiformato e Autoavaliação SM-2
  const [flashcardTypeFilter, setFlashcardTypeFilter] = useState<string>('todos');
  const [flippedCards, setFlippedCards] = useState<Record<string, boolean>>({});
  const [savedFlashcards, setSavedFlashcards] = useState<Record<string, boolean>>({});
  const [favoriteFlashcards, setFavoriteFlashcards] = useState<Record<string, boolean>>(() => {
    try {
      const saved = localStorage.getItem('radar_favorite_flashcards');
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });
  const [cardDifficultyRatings, setCardDifficultyRatings] = useState<Record<string, string>>({});
  const [cardInteractiveGuess, setCardInteractiveGuess] = useState<Record<string, string>>({});

  // Laboratório de Questões e Exercícios Interativos
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, string>>({});
  const [revealedQuestions, setRevealedQuestions] = useState<Record<string, boolean>>({});
  const [questionConvertedToCard, setQuestionConvertedToCard] = useState<Record<string, boolean>>({});
  const [labExerciseState, setLabExerciseState] = useState<Record<string, string>>({});
  const [labExerciseRevealed, setLabExerciseRevealed] = useState<Record<string, boolean>>({});

  // Sincroniza URL ?aula=...
  useEffect(() => {
    if (aulaParam && aulaParam !== activeLessonId) {
      setActiveLessonId(aulaParam);
    }
  }, [aulaParam, activeLessonId]);

  const handleSelectLesson = (id: string | null) => {
    setActiveLessonId(id);
    setSelectedVideoIndex(0);
    setVideoStartSec(0);
    setActiveSlideIdx(0);
    setActiveVisualStep(0);
    setSelectedMindMapNodeId(null);
    setActiveTab('resumo');
    if (id) {
      setSearchParams({ aula: id });
    } else {
      setSearchParams({});
    }
  };

  // Aulas concluídas persistidas
  const [completedLessons, setCompletedLessons] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem('radar_completed_lessons');
      return raw ? (JSON.parse(raw) as string[]) : [];
    } catch {
      return [];
    }
  });

  const toggleLessonCompletion = (lessonId: string) => {
    setCompletedLessons((prev) => {
      const next = prev.includes(lessonId) ? prev.filter((id) => id !== lessonId) : [...prev, lessonId];
      try {
        localStorage.setItem('radar_completed_lessons', JSON.stringify(next));
      } catch {
        // ignore
      }
      return next;
    });
  };

  // Cronômetro de estudo integrado na aula
  const [studySeconds, setStudySeconds] = useState<number>(0);
  const [timerRunning, setTimerRunning] = useState<boolean>(false);

  useEffect(() => {
    if (!timerRunning) return;
    const id = window.setInterval(() => {
      setStudySeconds((s) => s + 1);
    }, 1000);
    return () => window.clearInterval(id);
  }, [timerRunning]);

  useEffect(() => {
    if (activeLessonId) {
      setTimerRunning(true);
    } else {
      setTimerRunning(false);
    }
  }, [activeLessonId]);

  const { data: lessonsData, isLoading: lessonsLoading } = useLessons(selectedDisciplina || undefined);
  const { data: lessonData, isLoading: lessonLoading } = useLesson(activeLessonId);
  const { data: allQuestions } = useQuestions();

  const lessons = lessonsData?.aulas ?? [];
  const activeLesson = lessonData?.aula;

  const disciplinas = [
    { key: '', label: 'Todas as Disciplinas' },
    { key: 'Banco de Dados', label: 'Banco de Dados' },
    { key: 'Engenharia de Software', label: 'Engenharia de Software' },
    { key: 'Redes de Computadores', label: 'Redes de Computadores' },
    { key: 'Segurança da Informação', label: 'Segurança da Informação' },
    { key: 'Língua Portuguesa', label: 'Língua Portuguesa' },
    { key: 'Direito Constitucional', label: 'Direito Constitucional' },
  ];

  // Filtragem de catálogo
  const filteredLessons = useMemo(() => {
    return lessons.filter((lesson) => {
      const isCompleted = completedLessons.includes(lesson.id);
      if (statusFilter === 'pendentes' && isCompleted) return false;
      if (statusFilter === 'concluidas' && !isCompleted) return false;

      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchTitle = lesson.titulo.toLowerCase().includes(q);
        const matchDisc = lesson.disciplina.toLowerCase().includes(q);
        const matchMod = (lesson.modulo || '').toLowerCase().includes(q);
        const matchObj = lesson.objetivos.some((o) => o.toLowerCase().includes(q));
        return matchTitle || matchDisc || matchMod || matchObj;
      }
      return true;
    });
  }, [lessons, completedLessons, statusFilter, searchQuery]);

  // Agrupamento Hierárquico: Disciplina -> Módulo -> Aulas
  const groupedByModule = useMemo(() => {
    const groups: Record<string, { disciplina: string; modulo: string; aulas: typeof filteredLessons }> = {};
    for (const l of filteredLessons) {
      const mod = l.modulo || `Módulo Essencial: ${l.disciplina}`;
      const key = `${l.disciplina}::${mod}`;
      if (!groups[key]) {
        groups[key] = { disciplina: l.disciplina, modulo: mod, aulas: [] };
      }
      groups[key].aulas.push(l);
    }
    return Object.values(groups);
  }, [filteredLessons]);

  const totalLessonsCount = lessons.length;
  const completedCount = lessons.filter((l) => completedLessons.includes(l.id)).length;
  const completionPercentage = totalLessonsCount > 0 ? Math.round((completedCount / totalLessonsCount) * 100) : 0;

  // Cálculo real de XP baseado em atividades efetivas de aprendizagem
  const totalEarnedXp = useMemo(() => {
    const lessonsXp = completedCount * 120;
    const questionsXp = Object.keys(revealedQuestions).length * 25;
    const flashcardsXp = Object.keys(savedFlashcards).length * 15 + Object.keys(cardDifficultyRatings).length * 10;
    const chaptersXp = Object.values(completedChapters).filter(Boolean).length * 20;
    return lessonsXp + questionsXp + flashcardsXp + chaptersXp;
  }, [completedCount, revealedQuestions, savedFlashcards, cardDifficultyRatings, completedChapters]);

  // Questões resolvidas da aula ativa (prioriza questoes_detalhadas do backend + fallback para allQuestions)
  const activeLessonQuestions: LessonQuestionDetail[] = useMemo(() => {
    if (!activeLesson) return [];
    if (activeLesson.questoes_detalhadas && activeLesson.questoes_detalhadas.length > 0) {
      return activeLesson.questoes_detalhadas;
    }
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

  // Navegação sequencial
  const currentLessonIndex = lessons.findIndex((l) => l.id === activeLessonId);
  const prevLesson = currentLessonIndex > 0 ? lessons[currentLessonIndex - 1] : null;
  const nextLesson =
    currentLessonIndex >= 0 && currentLessonIndex < lessons.length - 1 ? lessons[currentLessonIndex + 1] : null;

  // Virar flashcard
  const toggleCardFlip = (cardId: string) => {
    setFlippedCards((prev) => ({ ...prev, [cardId]: !prev[cardId] }));
  };

  // Favoritar flashcard
  const toggleFavoriteCard = (cardId: string) => {
    setFavoriteFlashcards((prev) => {
      const updated = { ...prev, [cardId]: !prev[cardId] };
      try {
        localStorage.setItem('radar_favorite_flashcards', JSON.stringify(updated));
      } catch {
        // ignore
      }
      return updated;
    });
  };

  // Salvar flashcard no deck SM-2 real
  const handleSaveFlashcard = async (fc: LessonFlashcard, customQualityLabel?: string) => {
    if (customQualityLabel) {
      setCardDifficultyRatings((prev) => ({ ...prev, [fc.id]: customQualityLabel }));
    }
    try {
      await api.post('/api/estudos/flashcards', {
        frente: fc.frente,
        verso: `${fc.verso}${fc.mnemonico ? `\n\n💡 Mnemônico: ${fc.mnemonico}` : ''}`,
        tags: [fc.tag, fc.tipo || 'conceito'].filter(Boolean),
        fonte: activeLesson?.titulo || 'Aula GSN',
      });
      setSavedFlashcards((prev) => ({ ...prev, [fc.id]: true }));
      void queryClient.invalidateQueries({ queryKey: keys.flashQueue() });
      void queryClient.invalidateQueries({ queryKey: keys.flashStats() });
    } catch {
      setSavedFlashcards((prev) => ({ ...prev, [fc.id]: true }));
    }
  };

  // Responder questão no Laboratório e persistir tentativa real no backend
  const handleSelectOption = (questionId: string, optionKey: string) => {
    if (revealedQuestions[questionId]) return;
    setSelectedAnswers((prev) => ({ ...prev, [questionId]: optionKey }));
  };

  const handleConfirmQuestion = async (q: LessonQuestionDetail) => {
    const chosen = selectedAnswers[q.id];
    if (!chosen) return;
    setRevealedQuestions((prev) => ({ ...prev, [q.id]: true }));
    try {
      await api.post('/api/estudos/tentativas', {
        questao_id: q.id_ref || q.id,
        resposta: chosen,
        duracao_segundos: 45,
      });
      void queryClient.invalidateQueries({ queryKey: keys.performance() });
    } catch {
      // fallback gracioso quando em ambiente de teste isolado
    }
  };

  // Converter questão errada/estudada em Flashcard de Revisão SM-2 com 1 clique
  const handleCreateFlashcardFromQuestion = async (q: LessonQuestionDetail) => {
    try {
      await api.post('/api/estudos/flashcards', {
        frente: `[Questão ${q.banca_sigla || 'Concurso'}] ${q.enunciado}`,
        verso: `Gabarito Oficial: ${q.gabarito}\n\nExplicação Didática: ${q.comentario}`,
        tags: [q.disciplina, q.banca_sigla || 'prova', 'caderno_erros'].filter(Boolean),
        fonte: q.fonte,
      });
      setQuestionConvertedToCard((prev) => ({ ...prev, [q.id]: true }));
      void queryClient.invalidateQueries({ queryKey: keys.flashQueue() });
      void queryClient.invalidateQueries({ queryKey: keys.flashStats() });
    } catch {
      setQuestionConvertedToCard((prev) => ({ ...prev, [q.id]: true }));
    }
  };

  // Marcar capítulo de vídeo e saltar para o minuto
  const handleJumpToChapter = (chapterId: string, tempoSeg: number) => {
    setActiveChapterId(chapterId);
    setVideoStartSec(tempoSeg);
    setVideoPresentationMode('video');
    setCompletedChapters((prev) => {
      const updated = { ...prev, [chapterId]: true };
      try {
        localStorage.setItem('radar_completed_video_chapters', JSON.stringify(updated));
      } catch {
        // ignore
      }
      return updated;
    });
  };

  // Adicionar anotação sincronizada ao minuto do vídeo
  const handleAddSyncedNote = (currentVideoTitle: string) => {
    if (!noteInput.trim() || !activeLessonId) return;
    const mins = Math.floor(videoStartSec / 60);
    const secs = videoStartSec % 60;
    const label = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    const newNote: SyncedVideoNote = {
      id: `note-${Date.now()}`,
      chapterTitle: currentVideoTitle,
      timestampLabel: label,
      timestampSec: videoStartSec,
      text: noteInput.trim(),
      createdAt: new Date().toLocaleDateString('pt-BR'),
    };
    setLessonNotes((prev) => {
      const currentList = prev[activeLessonId] ?? [];
      const updated = { ...prev, [activeLessonId]: [newNote, ...currentList] };
      try {
        localStorage.setItem('radar_lesson_synced_notes', JSON.stringify(updated));
      } catch {
        // ignore
      }
      return updated;
    });
    setNoteInput('');
  };

  // Criar nova aula pelo Studio de Conteúdo
  const handleCreateCustomLesson = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newLessonTitle.trim() || !newLessonDisc.trim()) return;
    setCreatingLesson(true);
    try {
      const res = await api.post<{ ok: boolean; aula: { id: string } }>('/api/estudos/aulas', {
        titulo: newLessonTitle.trim(),
        disciplina: newLessonDisc.trim(),
        modulo: newLessonMod.trim() || `Módulo 1: ${newLessonDisc.trim()}`,
        objetivos: [
          newLessonObjective.trim() || `Dominar os conceitos essenciais de ${newLessonTitle.trim()}.`,
          'Resolver questões reais aplicadas pelas bancas examinadoras.',
        ],
        teoria_resumida:
          newLessonSummary.trim() ||
          `Conteúdo estruturado de preparação para concursos sobre ${newLessonTitle.trim()}.`,
      });
      await queryClient.invalidateQueries({ queryKey: ['study', 'lessons'] });
      setShowCreateModal(false);
      setNewLessonTitle('');
      setNewLessonSummary('');
      setNewLessonObjective('');
      if (res?.aula?.id) {
        handleSelectLesson(res.aula.id);
      }
    } catch {
      setShowCreateModal(false);
    } finally {
      setCreatingLesson(false);
    }
  };

  // Métricas reais da Avaliação de Domínio (Mastery Check)
  const masteryEvaluation = useMemo(() => {
    const total = activeLessonQuestions.length;
    if (total === 0) {
      return {
        total: 0,
        answered: 0,
        correct: 0,
        wrong: 0,
        pct: 0,
        byCompetence: [] as { nome: string; total: number; acertos: number; pct: number }[],
      };
    }
    let answered = 0;
    let correct = 0;
    const compMap: Record<string, { total: number; acertos: number }> = {};

    for (const q of activeLessonQuestions) {
      const sub = q.subtopico || q.topico || activeLesson?.disciplina || 'Geral';
      if (!compMap[sub]) compMap[sub] = { total: 0, acertos: 0 };
      compMap[sub].total += 1;

      const userAns = selectedAnswers[q.id];
      if (userAns) {
        answered += 1;
        if (userAns === q.gabarito) {
          correct += 1;
          compMap[sub].acertos += 1;
        }
      }
    }

    const wrong = Math.max(0, answered - correct);
    const pct = total > 0 ? Math.round((correct / total) * 100) : 0;
    const byCompetence = Object.entries(compMap).map(([nome, st]) => ({
      nome,
      total: st.total,
      acertos: st.acertos,
      pct: st.total > 0 ? Math.round((st.acertos / st.total) * 100) : 0,
    }));

    return { total, answered, correct, wrong, pct, byCompetence };
  }, [activeLessonQuestions, selectedAnswers, activeLesson]);

  return (
    <div className="space-y-5">
      {/* ====================================================================
          MODAL: STUDIO DE PRODUÇÃO DE CONTEÚDO (ADMIN / NOVA AULA)
         ==================================================================== */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
          <div className="w-full max-w-xl rounded-2xl border border-line bg-surface p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-line pb-3">
              <div className="flex items-center gap-2">
                <span className="flex size-7 items-center justify-center rounded-lg bg-amber-400/20 text-amber-400">
                  <Plus size={15} />
                </span>
                <div>
                  <h3 className="text-sm font-bold text-fg">Studio GSN — Publicar Nova Aula</h3>
                  <p className="text-2xs text-fg-3">
                    Adicione uma nova aula estruturada com módulo, objetivos e resumo didático.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="rounded-lg p-1.5 text-fg-3 hover:bg-surface-2 hover:text-fg"
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleCreateCustomLesson} className="space-y-3.5 text-xs">
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="space-y-1">
                  <span className="font-semibold text-fg-2">Disciplina *</span>
                  <input
                    type="text"
                    required
                    value={newLessonDisc}
                    onChange={(e) => setNewLessonDisc(e.target.value)}
                    placeholder="Ex: Banco de Dados"
                    className="w-full rounded-xl border border-line bg-surface-2 px-3 py-2 text-xs text-fg focus:border-amber-400 focus:outline-none"
                  />
                </label>
                <label className="space-y-1">
                  <span className="font-semibold text-fg-2">Módulo Curricular</span>
                  <input
                    type="text"
                    value={newLessonMod}
                    onChange={(e) => setNewLessonMod(e.target.value)}
                    placeholder="Ex: Módulo 2: Tópicos Avançados"
                    className="w-full rounded-xl border border-line bg-surface-2 px-3 py-2 text-xs text-fg focus:border-amber-400 focus:outline-none"
                  />
                </label>
              </div>

              <label className="block space-y-1">
                <span className="font-semibold text-fg-2">Título da Aula *</span>
                <input
                  type="text"
                  required
                  value={newLessonTitle}
                  onChange={(e) => setNewLessonTitle(e.target.value)}
                  placeholder="Ex: Aula 03: Indexação B-Tree, Hash e Otimização de Consultas"
                  className="w-full rounded-xl border border-line bg-surface-2 px-3 py-2 text-xs text-fg focus:border-amber-400 focus:outline-none"
                />
              </label>

              <label className="block space-y-1">
                <span className="font-semibold text-fg-2">Objetivo Principal de Aprendizagem</span>
                <input
                  type="text"
                  value={newLessonObjective}
                  onChange={(e) => setNewLessonObjective(e.target.value)}
                  placeholder="Ex: Compreender quando criar índices B-Tree compostos em tabelas de alta cardinalidade."
                  className="w-full rounded-xl border border-line bg-surface-2 px-3 py-2 text-xs text-fg focus:border-amber-400 focus:outline-none"
                />
              </label>

              <label className="block space-y-1">
                <span className="font-semibold text-fg-2">Resumo e Teoria Explicada</span>
                <textarea
                  rows={4}
                  value={newLessonSummary}
                  onChange={(e) => setNewLessonSummary(e.target.value)}
                  placeholder="Escreva a explicação central, regras de ouro e alertas de prova..."
                  className="w-full rounded-xl border border-line bg-surface-2 p-3 text-xs text-fg focus:border-amber-400 focus:outline-none"
                />
              </label>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-line">
                <Button variant="ghost" size="sm" type="button" onClick={() => setShowCreateModal(false)}>
                  Cancelar
                </Button>
                <Button variant="primary" size="sm" type="submit" disabled={creatingLesson}>
                  {creatingLesson ? 'Publicando...' : 'Publicar Aula no Catálogo'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ====================================================================
          VISÃO 1: CATÁLOGO CURRICULAR (DISCIPLINA -> MÓDULO -> AULA)
         ==================================================================== */}
      {!activeLessonId ? (
        <div className="space-y-5">
          {/* Cockpit de Domínio, Gamificação Profissional & Progresso */}
          <div className="relative overflow-hidden rounded-2xl border border-line bg-gradient-to-br from-surface via-surface-2 to-surface p-5 sm:p-6 shadow-md">
            <div
              aria-hidden="true"
              className="pointer-events-none absolute -right-20 -top-20 size-72 rounded-full bg-amber-500/10 blur-3xl"
            />
            <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
              <div className="space-y-1.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="flex size-6 items-center justify-center rounded-lg bg-amber-400/20 text-amber-400">
                    <Sparkles size={14} />
                  </span>
                  <span className="text-xs font-bold uppercase tracking-wider text-amber-400">
                    Ambiente Completo de Ensino Interativo
                  </span>
                  <Badge tone="verified">Jornada em 7 Etapas</Badge>
                </div>
                <h2 className="font-display text-xl font-bold tracking-tight text-fg sm:text-2xl">
                  Aulas, Quadros Visuais, Videoaulas & Laboratório
                </h2>
                <p className="text-xs text-fg-3 max-w-2xl leading-relaxed">
                  Progrida por disciplina e módulo com teoria esquematizada, mapas mentais interativos, videoaulas com
                  capítulos e checkpoints, flashcards multiformato e avaliação real de domínio.
                </p>
              </div>

              {/* Painel de Gamificação Sóbria & Domínio Real */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 shrink-0">
                <div className="rounded-xl border border-line bg-surface/80 px-3.5 py-2.5">
                  <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-amber-400">
                    <Zap size={12} /> Domínio Acumulado
                  </div>
                  <p className="mt-1 font-mono text-base font-bold text-fg">{totalEarnedXp} XP</p>
                  <p className="text-[10px] text-fg-3">Atividades reais concluídas</p>
                </div>

                <div className="rounded-xl border border-line bg-surface/80 px-3.5 py-2.5">
                  <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-emerald-400">
                    <CheckCircle2 size={12} /> Progresso Edital
                  </div>
                  <p className="mt-1 font-mono text-base font-bold text-fg">
                    {completedCount}/{totalLessonsCount}{' '}
                    <span className="text-xs text-emerald-400">({completionPercentage}%)</span>
                  </p>
                  <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-amber-400 to-emerald-400 transition-all duration-500"
                      style={{ width: `${completionPercentage}%` }}
                    />
                  </div>
                </div>

                <div className="col-span-2 sm:col-span-1 rounded-xl border border-line bg-surface/80 px-3.5 py-2.5 flex flex-col justify-between">
                  <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-sky-400">
                    <Flame size={12} /> Ritmo & Produção
                  </div>
                  <div className="mt-1.5 flex items-center justify-between gap-2">
                    <span className="text-2xs text-fg-2 font-medium">Studio de Aulas</span>
                    <button
                      type="button"
                      onClick={() => setShowCreateModal(true)}
                      className="inline-flex items-center gap-1 rounded-lg bg-amber-400/15 border border-amber-400/30 px-2 py-1 text-[10px] font-bold text-amber-300 hover:bg-amber-400/25 transition-colors"
                    >
                      <Plus size={11} /> Nova Aula
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Barra de Pesquisa, Visão por Módulos vs Grade e Filtro de Status */}
            <div className="mt-5 flex flex-col gap-3 border-t border-line/80 pt-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="relative flex-1 max-w-md">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-fg-3" />
                <input
                  type="text"
                  placeholder="Pesquisar por disciplina, módulo ou conceito (ex: 3FN, SQL, Scrum, Concessão, RSA)..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full rounded-xl border border-line bg-surface/90 py-2 pl-9 pr-3 text-xs text-fg placeholder:text-fg-3/60 focus:border-amber-400/60 focus:outline-none focus:ring-1 focus:ring-amber-400/40"
                />
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {/* Alternador Módulos vs Grade */}
                <div className="flex items-center gap-1 rounded-xl border border-line bg-surface/80 p-1">
                  <button
                    type="button"
                    onClick={() => setCatalogViewMode('modulos')}
                    className={`flex items-center gap-1 rounded-lg px-2.5 py-1 text-2xs font-medium transition-all ${
                      catalogViewMode === 'modulos'
                        ? 'bg-amber-400/20 text-amber-300 border border-amber-400/30'
                        : 'text-fg-3 hover:text-fg'
                    }`}
                  >
                    <ListTree size={12} /> Módulos
                  </button>
                  <button
                    type="button"
                    onClick={() => setCatalogViewMode('grade')}
                    className={`flex items-center gap-1 rounded-lg px-2.5 py-1 text-2xs font-medium transition-all ${
                      catalogViewMode === 'grade'
                        ? 'bg-amber-400/20 text-amber-300 border border-amber-400/30'
                        : 'text-fg-3 hover:text-fg'
                    }`}
                  >
                    <LayoutGrid size={12} /> Grade
                  </button>
                </div>

                {/* Filtro por Estado */}
                <div className="flex items-center gap-1 rounded-xl border border-line bg-surface/80 p-1">
                  {(['todas', 'pendentes', 'concluidas'] as const).map((filterKey) => {
                    const labels = {
                      todas: `Todas (${totalLessonsCount})`,
                      pendentes: `Pendentes (${totalLessonsCount - completedCount})`,
                      concluidas: `Concluídas (${completedCount})`,
                    };
                    const active = statusFilter === filterKey;
                    return (
                      <button
                        key={filterKey}
                        type="button"
                        onClick={() => setStatusFilter(filterKey)}
                        className={`rounded-lg px-2.5 py-1 text-2xs font-medium transition-all ${
                          active
                            ? 'bg-amber-400 text-slate-950 font-semibold shadow-xs'
                            : 'text-fg-3 hover:text-fg'
                        }`}
                      >
                        {labels[filterKey]}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>

          {/* Filtro Horizontal de Disciplinas */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
            {disciplinas.map((d) => (
              <button
                key={d.key}
                type="button"
                onClick={() => setSelectedDisciplina(d.key)}
                className={`rounded-full px-3.5 py-1.5 text-xs font-medium whitespace-nowrap transition-all ${
                  selectedDisciplina === d.key
                    ? 'bg-amber-400 text-slate-950 font-bold shadow-sm'
                    : 'bg-surface border border-line text-fg-2 hover:bg-surface-2 hover:text-fg'
                }`}
              >
                {d.label}
              </button>
            ))}
          </div>

          {/* Listagem de Aulas */}
          {lessonsLoading ? (
            <Card>
              <SkeletonRows rows={5} />
            </Card>
          ) : filteredLessons.length === 0 ? (
            <Card>
              <div className="py-12 text-center space-y-2">
                <BookOpen size={32} className="mx-auto text-fg-3/40" />
                <h3 className="text-sm font-bold text-fg">Nenhuma aula encontrada</h3>
                <p className="text-xs text-fg-3 max-w-sm mx-auto">
                  Altere os termos de busca, mude a disciplina selecionada ou publique uma nova aula no Studio.
                </p>
              </div>
            </Card>
          ) : catalogViewMode === 'modulos' ? (
            <div className="space-y-5">
              {groupedByModule.map((group) => {
                const doneInGroup = group.aulas.filter((a) => completedLessons.includes(a.id)).length;
                return (
                  <div
                    key={`${group.disciplina}-${group.modulo}`}
                    className="overflow-hidden rounded-2xl border border-line bg-surface shadow-sm"
                  >
                    {/* Cabeçalho do Módulo Curricular */}
                    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-surface-2/60 px-5 py-3.5">
                      <div className="flex items-center gap-2.5">
                        <span className="flex size-7 items-center justify-center rounded-lg bg-amber-400/15 text-amber-400 border border-amber-400/30">
                          <GraduationCap size={15} />
                        </span>
                        <div>
                          <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400">
                            {group.disciplina}
                          </span>
                          <h3 className="text-sm font-bold text-fg">{group.modulo}</h3>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 text-2xs text-fg-3">
                        <span className="font-mono font-semibold text-fg">
                          {doneInGroup}/{group.aulas.length} concluídas
                        </span>
                      </div>
                    </div>

                    {/* Aulas dentro do Módulo */}
                    <div className="divide-y divide-line/60">
                      {group.aulas.map((lesson) => {
                        const isCompleted = completedLessons.includes(lesson.id);
                        return (
                          <div
                            key={lesson.id}
                            onClick={() => handleSelectLesson(lesson.id)}
                            className="group flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between cursor-pointer transition-colors hover:bg-surface-2/50"
                          >
                            <div className="space-y-1.5 flex-1 min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <Badge tone={isCompleted ? 'verified' : 'neutral'}>
                                  {lesson.nivel || 'Essencial'}
                                </Badge>
                                <span className="inline-flex items-center gap-1 text-[11px] text-fg-3 font-mono">
                                  <Clock size={11} /> {lesson.tempo_estimado_min || 45} min
                                </span>
                                <span className="inline-flex items-center gap-1 text-[11px] text-amber-400 font-mono font-semibold">
                                  <Zap size={11} /> +{lesson.xp_recompensa || 120} XP
                                </span>
                                <Badge tone="verified">{lesson.questoes_count} questões</Badge>
                              </div>

                              <h4 className="text-sm font-bold text-fg group-hover:text-amber-400 transition-colors">
                                {lesson.titulo}
                              </h4>

                              <p className="text-xs text-fg-3 line-clamp-1">
                                🎯 {lesson.objetivos[0]}
                              </p>

                              {/* Pílulas de Recursos da Jornada */}
                              <div className="flex flex-wrap gap-1.5 pt-1 text-[10px] font-medium text-fg-3">
                                <span className="inline-flex items-center gap-1 rounded bg-surface-2 px-2 py-0.5 border border-line">
                                  <Video size={10} className="text-rose-400" /> Videoaula + Capítulos
                                </span>
                                <span className="inline-flex items-center gap-1 rounded bg-surface-2 px-2 py-0.5 border border-line">
                                  <Network size={10} className="text-sky-400" /> Quadro Visual & Mapa Mental
                                </span>
                                <span className="inline-flex items-center gap-1 rounded bg-surface-2 px-2 py-0.5 border border-line">
                                  <Layers size={10} className="text-purple-400" /> Flashcards Multiformato
                                </span>
                                <span className="inline-flex items-center gap-1 rounded bg-surface-2 px-2 py-0.5 border border-line">
                                  <Trophy size={10} className="text-amber-400" /> Avaliação de Domínio
                                </span>
                              </div>
                            </div>

                            <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  toggleLessonCompletion(lesson.id);
                                }}
                                className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-semibold transition-colors ${
                                  isCompleted
                                    ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                                    : 'bg-surface-2 text-fg-3 border border-line hover:text-fg'
                                }`}
                              >
                                {isCompleted ? (
                                  <>
                                    <Check size={11} /> Concluída
                                  </>
                                ) : (
                                  <span>Pendente</span>
                                )}
                              </button>

                              <span className="inline-flex items-center gap-1 rounded-xl bg-amber-400 px-3 py-1.5 text-xs font-bold text-slate-950 shadow-xs group-hover:bg-amber-300 transition-colors">
                                Iniciar Aula <ChevronRight size={14} />
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            /* Visão em Grade de Cards */
            <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
              {filteredLessons.map((lesson) => {
                const isCompleted = completedLessons.includes(lesson.id);
                return (
                  <div
                    key={lesson.id}
                    onClick={() => handleSelectLesson(lesson.id)}
                    className="group relative flex cursor-pointer flex-col justify-between rounded-2xl border border-line bg-surface p-4 transition-all hover:-translate-y-0.5 hover:border-amber-400/40 hover:shadow-lg"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400">
                          {lesson.disciplina}
                        </span>
                        <div className="flex items-center gap-1.5">
                          <Badge tone="verified">{lesson.questoes_count} questões</Badge>
                        </div>
                      </div>

                      <h3 className="mt-2.5 text-sm font-bold text-fg group-hover:text-amber-400 transition-colors leading-snug">
                        {lesson.titulo}
                      </h3>

                      <div className="mt-3 flex flex-wrap gap-1 text-[10px] font-medium text-fg-3">
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-surface-2 border border-line">
                          <Video size={11} className="text-rose-400" /> Videoaula
                        </span>
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-surface-2 border border-line">
                          <Network size={11} className="text-sky-400" /> Quadro Visual
                        </span>
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-surface-2 border border-line">
                          <Layers size={11} className="text-purple-400" /> Flashcards
                        </span>
                      </div>

                      <ul className="mt-3 space-y-1 text-2xs text-fg-3">
                        {lesson.objetivos.slice(0, 2).map((obj, i) => (
                          <li key={i} className="flex items-start gap-1.5 line-clamp-1">
                            <span className="text-amber-400">•</span>
                            <span>{obj}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="mt-4 flex items-center justify-between border-t border-line/60 pt-3 text-xs font-bold text-amber-400">
                      <span>{isCompleted ? '✓ Aula Concluída' : 'Estudar Aula Completa'}</span>
                      <ChevronRight size={15} className="transition-transform group-hover:translate-x-1" />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ) : (
        /* ====================================================================
           VISÃO 2: SALA DE AULA INTERATIVA EM 7 ETAPAS + PROFESSOR VIRTUAL
           ==================================================================== */
        <div className="space-y-4">
          {/* Topbar de Comando da Aula */}
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-surface/95 p-3 backdrop-blur-md shadow-md">
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => handleSelectLesson(null)}
                className="gap-1.5 text-xs font-semibold"
              >
                <ArrowLeft size={14} /> Voltar ao Catálogo
              </Button>

              {activeLesson && (
                <div className="hidden md:flex items-center gap-1.5 text-2xs text-fg-3 pl-2 border-l border-line">
                  <span className="font-semibold text-amber-400">{activeLesson.disciplina}</span>
                  <ChevronRight size={12} />
                  <span className="truncate max-w-[220px]">{activeLesson.modulo || 'Módulo Principal'}</span>
                </div>
              )}
            </div>

            {/* Cronômetro de Estudo Ativo */}
            <div className="flex items-center gap-2 rounded-xl border border-line bg-surface-2 px-3 py-1.5">
              <Clock size={13} className="text-amber-400" />
              <span className="font-mono text-xs font-bold tabular text-fg">{clock(studySeconds)}</span>
              <button
                type="button"
                onClick={() => setTimerRunning((r) => !r)}
                className="ml-1 rounded p-1 text-fg-3 hover:text-fg hover:bg-surface transition-colors"
                title={timerRunning ? 'Pausar cronômetro' : 'Iniciar foco'}
              >
                {timerRunning ? <Pause size={12} /> : <Play size={12} />}
              </button>
              <button
                type="button"
                onClick={() => {
                  setTimerRunning(false);
                  setStudySeconds(0);
                }}
                className="rounded p-1 text-fg-3 hover:text-fg hover:bg-surface transition-colors"
                title="Zerar cronômetro"
              >
                <RotateCcw size={11} />
              </button>
            </div>

            {/* Ações Rápidas: Professor Virtual + Concluir Aula */}
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setTutorOpen((o) => !o)}
                className={`gap-1.5 text-[11px] font-bold border ${
                  tutorOpen
                    ? 'border-amber-400 bg-amber-400/15 text-amber-300'
                    : 'border-amber-400/30 text-amber-400 hover:bg-amber-400/10'
                }`}
              >
                <Bot size={14} /> Professor Virtual
              </Button>

              {activeLessonId && (
                <Button
                  variant={completedLessons.includes(activeLessonId) ? 'secondary' : 'primary'}
                  size="sm"
                  onClick={() => toggleLessonCompletion(activeLessonId)}
                  className="gap-1.5 text-[11px]"
                >
                  <Check size={14} />
                  <span>
                    {completedLessons.includes(activeLessonId) ? 'Aula Concluída' : 'Concluir Aula'}
                  </span>
                </Button>
              )}
            </div>
          </div>

          {lessonLoading || !activeLesson ? (
            <Card>
              <SkeletonRows rows={6} />
            </Card>
          ) : (
            <div className="space-y-5">
              {/* Painel Expansível do Professor Virtual Contextual */}
              <AnimatePresence>
                {tutorOpen && activeLesson.tutor_contextual && (
                  <motion.div
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    className="rounded-2xl border border-amber-400/40 bg-gradient-to-r from-amber-500/10 via-surface to-surface p-5 shadow-lg space-y-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2.5">
                        <span className="flex size-8 items-center justify-center rounded-xl bg-amber-400 text-slate-950 font-bold">
                          <Bot size={18} />
                        </span>
                        <div>
                          <h3 className="text-sm font-bold text-fg">
                            Professor Virtual GSN — Assistente Contextual da Aula
                          </h3>
                          <p className="text-2xs text-fg-3">
                            Baseado estritamente nos conceitos validados de{' '}
                            <strong className="text-fg-2">{activeLesson.titulo}</strong> (sem invenções).
                          </p>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setTutorOpen(false)}
                        className="rounded-lg p-1 text-fg-3 hover:text-fg"
                      >
                        <X size={16} />
                      </button>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      {[
                        { id: 'explicar_simples', label: '💡 Simplifique com uma analogia' },
                        { id: 'exemplo_pratico', label: '🎯 Mostre outro exemplo de prova' },
                        { id: 'comparar_conceitos', label: '⚖️ Compare os conceitos da aula' },
                        { id: 'resumo_1_minuto', label: '⚡ Resumo de 1 minuto (Checklist)' },
                      ].map((btn) => (
                        <button
                          key={btn.id}
                          type="button"
                          onClick={() => {
                            setActiveTutorMode(btn.id as typeof activeTutorMode);
                            setTutorCustomFeedback(null);
                          }}
                          className={`rounded-xl px-3 py-1.5 text-xs font-semibold transition-all ${
                            activeTutorMode === btn.id && !tutorCustomFeedback
                              ? 'bg-amber-400 text-slate-950 font-bold'
                              : 'bg-surface-2 border border-line text-fg-2 hover:text-fg'
                          }`}
                        >
                          {btn.label}
                        </button>
                      ))}
                      <button
                        type="button"
                        onClick={async () => {
                          for (const fc of (activeLesson.flashcards ?? []).slice(0, 3)) {
                            await handleSaveFlashcard(fc);
                          }
                          setTutorCustomFeedback(
                            `✓ 3 Flashcards essenciais de "${activeLesson.titulo}" foram gerados e adicionados diretamente à sua fila de revisão espaçada (SM-2)!`
                          );
                        }}
                        className="rounded-xl bg-emerald-500/15 border border-emerald-500/30 px-3 py-1.5 text-xs font-bold text-emerald-300 hover:bg-emerald-500/25 transition-all"
                      >
                        🗂️ Gerar Flashcards desta Aula no Meu Deck
                      </button>
                    </div>

                    <div className="rounded-xl border border-line bg-surface/90 p-4 text-xs leading-relaxed text-fg whitespace-pre-line">
                      {tutorCustomFeedback || activeLesson.tutor_contextual[activeTutorMode]}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Cabeçalho Didático da Aula */}
              <div className="rounded-2xl border border-line bg-gradient-to-br from-surface via-surface-2 to-surface p-5 sm:p-6 shadow-md">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-md bg-amber-400/15 px-2.5 py-1 text-2xs font-bold uppercase tracking-wider text-amber-400 border border-amber-400/30">
                      {activeLesson.disciplina}
                    </span>
                    <Badge tone="neutral">{activeLesson.nivel || 'Essencial'}</Badge>
                    <span className="text-2xs font-mono text-fg-3 flex items-center gap-1">
                      <Clock size={12} /> {activeLesson.tempo_estimado_min || 45} min estimados
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {activeLesson.videoaulas && activeLesson.videoaulas.length > 0 && (
                      <Badge tone="verified" className="gap-1">
                        <Video size={11} /> {activeLesson.videoaulas.length} Videoaula(s)
                      </Badge>
                    )}
                    {activeLesson.flashcards && activeLesson.flashcards.length > 0 && (
                      <Badge tone="neutral" className="gap-1">
                        <Layers size={11} /> {activeLesson.flashcards.length} Flashcards
                      </Badge>
                    )}
                    <Badge tone="neutral" className="gap-1">
                      <Target size={11} /> {activeLessonQuestions.length} Questões
                    </Badge>
                  </div>
                </div>

                <h1 className="mt-3 text-xl font-bold tracking-tight text-fg sm:text-2xl leading-snug">
                  {activeLesson.titulo}
                </h1>

                {/* Objetivos de Aprendizagem */}
                <div className="mt-4 rounded-xl border border-amber-400/20 bg-amber-400/5 p-3.5">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-amber-400">
                    O que você vai dominar nesta aula
                  </p>
                  <ul className="mt-2 space-y-1.5 text-xs text-fg-2">
                    {activeLesson.objetivos.map((obj, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <CheckCircle2 size={14} className="mt-0.5 text-amber-400 shrink-0" />
                        <span>{obj}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* ================================================================
                  BARRA DE JORNADA DE APRENDIZAGEM (7 ETAPAS INTEGRADAS)
                 ================================================================ */}
              <div className="flex items-center gap-1.5 overflow-x-auto rounded-xl border border-line bg-surface-2 p-1.5 scrollbar-none">
                {[
                  { id: 'resumo', label: 'Resumo & Teoria Explicada', icon: BookOpen },
                  { id: 'visual', label: 'Quadro Digital & Mapa Mental', icon: Network },
                  {
                    id: 'video',
                    label: 'Videoaula Recomendada',
                    icon: Video,
                    badge: activeLesson.videoaulas?.length,
                  },
                  {
                    id: 'flashcards',
                    label: 'Flashcards Visuais (3D)',
                    icon: Layers,
                    badge: activeLesson.flashcards?.length,
                  },
                  { id: 'bancas', label: 'Raio-X das Bancas', icon: Award },
                  {
                    id: 'questoes',
                    label: 'Caderno de Questões',
                    icon: Target,
                    badge: activeLessonQuestions.length,
                  },
                  { id: 'avaliacao', label: 'Avaliação de Domínio', icon: Trophy },
                ].map((tab) => {
                  const Icon = tab.icon;
                  const isCurrent = activeTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setActiveTab(tab.id as typeof activeTab)}
                      className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-semibold whitespace-nowrap transition-all ${
                        isCurrent
                          ? 'bg-amber-400 text-slate-950 font-bold shadow-sm'
                          : 'text-fg-3 hover:text-fg hover:bg-surface'
                      }`}
                    >
                      <Icon size={14} />
                      <span>{tab.label}</span>
                      {tab.badge !== undefined && tab.badge > 0 && (
                        <span
                          className={`rounded-full px-1.5 py-0.2 text-[10px] font-bold ${
                            isCurrent ? 'bg-slate-950/20 text-slate-950' : 'bg-surface-3 text-fg-2'
                          }`}
                        >
                          {tab.badge}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>

              {/* ================================================================
                  ETAPA 1: RESUMO & TEORIA EXPLICADA
                 ================================================================ */}
              {activeTab === 'resumo' && (
                <div className="space-y-4">
                  {/* Tabela Comparativa Visual */}
                  {activeLesson.tabela_resumo && (
                    <Card
                      title={activeLesson.tabela_resumo.titulo}
                      subtitle="Quadro comparativo direto para memorização rápida antes da prova."
                    >
                      <div className="overflow-x-auto -mx-2 sm:mx-0">
                        <table className="w-full text-left text-xs">
                          <thead>
                            <tr className="border-b border-line bg-surface-3/50 text-[11px] font-bold uppercase tracking-wider text-fg-3">
                              {activeLesson.tabela_resumo.colunas.map((col, idx) => (
                                <th key={idx} className="px-3.5 py-2.5">
                                  {col}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-line/60">
                            {activeLesson.tabela_resumo.linhas.map((row, rIdx) => (
                              <tr key={rIdx} className="hover:bg-surface-2 transition-colors">
                                {row.map((cell, cIdx) => (
                                  <td
                                    key={cIdx}
                                    className={`px-3.5 py-3 leading-relaxed ${
                                      cIdx === 0 ? 'font-bold text-amber-400 whitespace-nowrap' : 'text-fg-2'
                                    }`}
                                  >
                                    {cell}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </Card>
                  )}

                  {/* Explicação Teórica Didática */}
                  <Card
                    title="Conceitos Essenciais da Matéria"
                    subtitle="Leitura estruturada sem enrolação, focada nos pontos de maior incidência."
                  >
                    <div className="prose prose-invert max-w-none space-y-3 text-xs leading-relaxed text-fg-2 whitespace-pre-line">
                      {activeLesson.teoria_resumida}
                    </div>

                    <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-line pt-4">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setActiveTab('visual')}
                        className="gap-1.5 text-xs text-sky-400 border-sky-400/30"
                      >
                        <Network size={14} /> Explorar no Quadro Digital & Mapa Mental
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setActiveTab('video')}
                        className="gap-1.5 text-xs text-rose-400 border-rose-400/30"
                      >
                        <Video size={14} /> Assistir Videoaula com Capítulos
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setActiveTab('questoes')}
                        className="gap-1.5 text-xs text-emerald-400 border-emerald-400/30"
                      >
                        <Target size={14} /> Praticar no Laboratório de Questões
                      </Button>
                    </div>
                  </Card>

                  {/* Pontos Críticos e Alertas de Armadilha */}
                  {activeLesson.pontos_criticos && activeLesson.pontos_criticos.length > 0 && (
                    <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-5 space-y-3">
                      <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-amber-300">
                        <AlertCircle size={17} /> Pontos Críticos & Pegadinhas Clássicas
                      </div>
                      <ul className="space-y-2 text-xs text-amber-100/90">
                        {activeLesson.pontos_criticos.map((ponto, i) => (
                          <li key={i} className="flex items-start gap-2.5">
                            <span className="text-amber-400 font-bold text-base leading-none">›</span>
                            <span className="leading-relaxed">{ponto}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {/* ================================================================
                  ETAPA 2: QUADRO DIGITAL INTERATIVO & MAPA MENTAL (BRILLIANT STYLE)
                 ================================================================ */}
              {activeTab === 'visual' && (
                <div className="space-y-5">
                  {/* Quadro Digital de Relações e Esquemas */}
                  {activeLesson.quadro_visual && (
                    <Card
                      title={activeLesson.quadro_visual.titulo}
                      subtitle={activeLesson.quadro_visual.subtitulo}
                    >
                      <div className="grid gap-4 md:grid-cols-2">
                        {activeLesson.quadro_visual.relacoes_conceituais.map((rel) => (
                          <div
                            key={rel.id}
                            className="rounded-2xl border border-line bg-surface-2/60 p-4 space-y-3 hover:border-amber-400/40 transition-all"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="rounded-md bg-amber-400/15 border border-amber-400/30 px-2.5 py-1 text-xs font-black uppercase tracking-wider text-amber-300">
                                {rel.categoria}
                              </span>
                              <span className="text-[10px] font-mono text-fg-3">Esquema Visual</span>
                            </div>

                            <p className="text-xs font-medium text-fg leading-relaxed">{rel.regra_ouro}</p>

                            {/* Fluxo Visual com Setas */}
                            <div className="rounded-xl border border-amber-400/20 bg-surface p-3 font-mono text-xs font-bold text-amber-400">
                              {rel.fluxo_visual}
                            </div>

                            {/* Chips de Conectivos / Elementos */}
                            <div className="flex flex-wrap gap-1.5">
                              {rel.conectivos.map((c, idx) => (
                                <span
                                  key={idx}
                                  className="rounded-lg bg-surface-3 px-2 py-0.5 text-[11px] font-semibold text-fg-2 border border-line"
                                >
                                  {c}
                                </span>
                              ))}
                            </div>

                            <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-2.5 text-2xs text-emerald-200">
                              <strong>Exemplo Aplicado:</strong> {rel.exemplo_destacado}
                            </div>

                            <div className="rounded-xl bg-rose-500/10 border border-rose-500/20 p-2.5 text-2xs text-rose-200">
                              <strong>⚠️ Armadilha de Prova:</strong> {rel.armadilha_banca}
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Passos Animados Interativos (Walkthrough Passo a Passo) */}
                      {activeLesson.quadro_visual.passos_animados.length > 0 && (
                        <div className="mt-6 rounded-2xl border border-line bg-surface-2 p-5 space-y-4">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div>
                              <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400">
                                Decomposição Progressiva Interativa
                              </span>
                              <h4 className="text-sm font-bold text-fg">
                                Passo a Passo do Raciocínio de Prova
                              </h4>
                            </div>
                            <div className="flex items-center gap-1.5">
                              {activeLesson.quadro_visual.passos_animados.map((st, idx) => (
                                <button
                                  key={st.passo}
                                  type="button"
                                  onClick={() => setActiveVisualStep(idx)}
                                  className={`rounded-lg px-3 py-1 text-xs font-bold transition-all ${
                                    activeVisualStep === idx
                                      ? 'bg-amber-400 text-slate-950'
                                      : 'bg-surface border border-line text-fg-3 hover:text-fg'
                                  }`}
                                >
                                  Passo {st.passo}
                                </button>
                              ))}
                            </div>
                          </div>

                          {(() => {
                            const step =
                              activeLesson.quadro_visual.passos_animados[activeVisualStep] ??
                              activeLesson.quadro_visual.passos_animados[0];
                            if (!step) return null;
                            return (
                              <motion.div
                                key={step.passo}
                                initial={{ opacity: 0, x: 10 }}
                                animate={{ opacity: 1, x: 0 }}
                                className="rounded-xl border border-amber-400/30 bg-surface p-4 space-y-2.5"
                              >
                                <h5 className="text-sm font-bold text-amber-400">{step.titulo}</h5>
                                <p className="text-xs text-fg-2 leading-relaxed">{step.detalhe}</p>
                                <div className="rounded-lg bg-surface-2 border border-line p-3 font-mono text-xs text-emerald-400">
                                  {step.destaque_codigo}
                                </div>
                              </motion.div>
                            );
                          })()}
                        </div>
                      )}
                    </Card>
                  )}

                  {/* Mapa Mental Interativo com Nós Clicáveis */}
                  {activeLesson.mapa_mental && (
                    <Card
                      title={`Mapa Mental Interativo: ${activeLesson.mapa_mental.no_central}`}
                      subtitle="Clique em qualquer nó conceitual abaixo para expandir exemplos, sub-ramos e dicas de prova."
                    >
                      <div className="grid gap-4 lg:grid-cols-12">
                        {/* Árvore de Nós */}
                        <div className="lg:col-span-7 space-y-3">
                          <div className="rounded-xl border border-amber-400/40 bg-amber-400/10 p-3 text-center">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-amber-300">
                              Núcleo Central da Aula
                            </span>
                            <p className="text-sm font-bold text-fg mt-0.5">
                              {activeLesson.mapa_mental.no_central}
                            </p>
                          </div>

                          <div className="grid gap-2.5 sm:grid-cols-2">
                            {activeLesson.mapa_mental.nos.map((node) => {
                              const isSelected =
                                (selectedMindMapNodeId || activeLesson.mapa_mental?.nos[0]?.id) === node.id;
                              return (
                                <button
                                  key={node.id}
                                  type="button"
                                  onClick={() => setSelectedMindMapNodeId(node.id)}
                                  className={`text-left rounded-xl border p-3.5 transition-all ${
                                    isSelected
                                      ? 'border-amber-400 bg-amber-400/15 shadow-md'
                                      : 'border-line bg-surface-2/60 hover:border-line-strong hover:bg-surface-2'
                                  }`}
                                >
                                  <div className="flex items-center justify-between gap-2">
                                    <span className="text-xs font-bold text-fg">{node.titulo}</span>
                                    <ChevronRight
                                      size={14}
                                      className={isSelected ? 'text-amber-400' : 'text-fg-3'}
                                    />
                                  </div>
                                  <p className="mt-1 text-2xs text-fg-3 line-clamp-2">{node.descricao}</p>
                                </button>
                              );
                            })}
                          </div>
                        </div>

                        {/* Painel de Inspeção do Nó Selecionado */}
                        <div className="lg:col-span-5">
                          {(() => {
                            const activeNode =
                              activeLesson.mapa_mental.nos.find((n) => n.id === selectedMindMapNodeId) ??
                              activeLesson.mapa_mental.nos[0];
                            if (!activeNode) return null;
                            return (
                              <div className="h-full rounded-2xl border border-amber-400/30 bg-surface-2 p-4 space-y-3">
                                <Badge tone="verified">{activeNode.categoria}</Badge>
                                <h4 className="text-base font-bold text-fg">{activeNode.titulo}</h4>
                                <p className="text-xs text-fg-2 leading-relaxed">{activeNode.descricao}</p>

                                <div className="rounded-xl border border-line bg-surface p-3 space-y-1">
                                  <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">
                                    Aplicação / Exemplo
                                  </span>
                                  <p className="text-xs text-fg-2">{activeNode.exemplo}</p>
                                </div>

                                <div className="rounded-xl border border-amber-400/20 bg-amber-400/5 p-3 space-y-1">
                                  <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400">
                                    Como a Banca Cobra
                                  </span>
                                  <p className="text-xs text-fg-2">{activeNode.dica_banca}</p>
                                </div>

                                <div className="space-y-1 pt-1">
                                  <span className="text-[10px] font-bold uppercase tracking-wider text-fg-3">
                                    Ramificações Diretas
                                  </span>
                                  {activeNode.subnos.map((sub) => (
                                    <div
                                      key={sub.id}
                                      className="rounded-lg bg-surface px-2.5 py-1.5 text-2xs text-fg-2 border border-line"
                                    >
                                      • {sub.label}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            );
                          })()}
                        </div>
                      </div>
                    </Card>
                  )}
                </div>
              )}

              {/* ================================================================
                  ETAPA 3: VIDEOAULAS PROFISSIONAIS (CAPÍTULOS, SLIDES & CHECKPOINTS)
                 ================================================================ */}
              {activeTab === 'video' && (
                <div className="space-y-4">
                  {activeLesson.videoaulas && activeLesson.videoaulas.length > 0 ? (
                    <div className="grid gap-4 lg:grid-cols-12">
                      {/* Coluna Principal: Player Híbrido (Vídeo + Apresentação Guiada de Contingência) */}
                      <div className="lg:col-span-8 space-y-4">
                        {(() => {
                          const currentVideo =
                            activeLesson.videoaulas[selectedVideoIndex] ?? activeLesson.videoaulas[0];
                          const slides = currentVideo.slides_guiados ?? [];
                          const currentSlide = slides[activeSlideIdx] ?? slides[0];

                          return (
                            <>
                              <div className="overflow-hidden rounded-2xl border border-line bg-surface shadow-lg">
                                {/* Barra Superior do Player: Alternador Vídeo vs Apresentação Guiada + Velocidade */}
                                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-surface-2 px-4 py-2.5">
                                  <div className="flex items-center gap-1.5">
                                    <button
                                      type="button"
                                      onClick={() => setVideoPresentationMode('video')}
                                      className={`flex items-center gap-1.5 rounded-lg px-3 py-1 text-2xs font-bold transition-all ${
                                        videoPresentationMode === 'video'
                                          ? 'bg-amber-400 text-slate-950'
                                          : 'text-fg-3 hover:text-fg bg-surface'
                                      }`}
                                    >
                                      <Video size={12} /> Player de Vídeo
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => setVideoPresentationMode('slides')}
                                      className={`flex items-center gap-1.5 rounded-lg px-3 py-1 text-2xs font-bold transition-all ${
                                        videoPresentationMode === 'slides'
                                          ? 'bg-amber-400 text-slate-950'
                                          : 'text-fg-3 hover:text-fg bg-surface'
                                      }`}
                                    >
                                      <Sparkles size={12} /> Apresentação Visual Guiada (Modo Offline/Interativo)
                                    </button>
                                  </div>

                                  <div className="flex items-center gap-1.5 text-2xs">
                                    <span className="text-fg-3">Velocidade:</span>
                                    {[1, 1.25, 1.5, 2].map((spd) => (
                                      <button
                                        key={spd}
                                        type="button"
                                        onClick={() => setPlaybackSpeed(spd)}
                                        className={`rounded px-1.5 py-0.5 font-mono font-bold ${
                                          playbackSpeed === spd
                                            ? 'bg-amber-400/20 text-amber-300 border border-amber-400/40'
                                            : 'text-fg-3 hover:text-fg'
                                        }`}
                                      >
                                        {spd}x
                                      </button>
                                    ))}
                                  </div>
                                </div>

                                {/* Corpo do Player */}
                                {videoPresentationMode === 'video' ? (
                                  <div>
                                    <div className="relative aspect-video w-full bg-slate-950">
                                      <iframe
                                        key={`${currentVideo.youtube_id}-${videoStartSec}`}
                                        className="h-full w-full"
                                        src={`https://www.youtube-nocookie.com/embed/${currentVideo.youtube_id}?rel=0&start=${videoStartSec}`}
                                        title={currentVideo.titulo}
                                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                        allowFullScreen
                                      />
                                    </div>
                                    {/* Barra de Contingência Inteligente contra vídeo externo bloqueado/indisponível */}
                                    <div className="flex flex-wrap items-center justify-between gap-2 bg-surface-2/90 px-4 py-2 text-2xs text-fg-3 border-t border-line">
                                      <span>
                                        Vídeo externo indisponível na sua rede ou bloqueado? Use a Apresentação Visual
                                        Guiada da aula sem perder nenhum conteúdo.
                                      </span>
                                      <button
                                        type="button"
                                        onClick={() => setVideoPresentationMode('slides')}
                                        className="font-bold text-amber-400 hover:underline"
                                      >
                                        Abrir Quadro Animado da Videoaula →
                                      </button>
                                    </div>
                                  </div>
                                ) : (
                                  /* Apresentação Guiada em Slides Animados (Nunca deixa retângulo vazio!) */
                                  <div className="p-6 sm:p-8 bg-gradient-to-br from-slate-950 via-surface to-surface-2 min-h-[320px] flex flex-col justify-between space-y-6">
                                    {currentSlide ? (
                                      <motion.div
                                        key={currentSlide.ordem}
                                        initial={{ opacity: 0, y: 8 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        className="space-y-4"
                                      >
                                        <div className="flex items-center justify-between">
                                          <Badge tone="verified">{currentSlide.tag}</Badge>
                                          <span className="font-mono text-xs text-fg-3">
                                            Quadro {activeSlideIdx + 1} de {slides.length}
                                          </span>
                                        </div>
                                        <h3 className="text-lg sm:text-xl font-bold text-fg">
                                          {currentSlide.titulo}
                                        </h3>
                                        <p className="text-sm text-fg-2 leading-relaxed">
                                          {currentSlide.conteudo}
                                        </p>
                                        {currentSlide.destaque && (
                                          <div className="rounded-xl border border-amber-400/30 bg-amber-400/10 p-3.5 text-xs font-semibold text-amber-200">
                                            💡 {currentSlide.destaque}
                                          </div>
                                        )}
                                      </motion.div>
                                    ) : null}

                                    <div className="flex items-center justify-between border-t border-line pt-4">
                                      <Button
                                        variant="secondary"
                                        size="sm"
                                        disabled={activeSlideIdx === 0}
                                        onClick={() => setActiveSlideIdx((i) => Math.max(0, i - 1))}
                                      >
                                        <ArrowLeft size={13} /> Quadro Anterior
                                      </Button>
                                      <div className="flex items-center gap-2">
                                        <Button
                                          variant="ghost"
                                          size="sm"
                                          onClick={() => setActiveTab('resumo')}
                                        >
                                          Ver Teoria Completa
                                        </Button>
                                        <Button
                                          variant="primary"
                                          size="sm"
                                          disabled={activeSlideIdx >= slides.length - 1}
                                          onClick={() =>
                                            setActiveSlideIdx((i) => Math.min(slides.length - 1, i + 1))
                                          }
                                        >
                                          Próximo Quadro <ArrowRight size={13} />
                                        </Button>
                                      </div>
                                    </div>
                                  </div>
                                )}

                                {/* Rodapé de Metadados do Vídeo */}
                                <div className="p-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-t border-line">
                                  <div>
                                    <div className="flex items-center gap-2">
                                      <Badge tone="verified">{currentVideo.canal}</Badge>
                                      <span className="text-2xs font-mono text-fg-3">
                                        ⏱ {currentVideo.duracao}
                                      </span>
                                    </div>
                                    <h3 className="mt-1.5 text-sm font-bold text-fg">{currentVideo.titulo}</h3>
                                    {currentVideo.descricao && (
                                      <p className="mt-1 text-xs text-fg-3">{currentVideo.descricao}</p>
                                    )}
                                  </div>

                                  <a
                                    href={`https://www.youtube.com/watch?v=${currentVideo.youtube_id}&t=${videoStartSec}s`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1.5 rounded-xl border border-line bg-surface-2 px-3 py-2 text-xs font-semibold text-fg hover:border-amber-400/50 hover:text-amber-400 transition-colors shrink-0"
                                  >
                                    <span>Abrir no YouTube</span>
                                    <ExternalLink size={13} />
                                  </a>
                                </div>
                              </div>

                              {/* Perguntas Interativas Durante a Videoaula (Checkpoints de Vídeo) */}
                              {currentVideo.perguntas_video && currentVideo.perguntas_video.length > 0 && (
                                <Card
                                  title="Checkpoint Interativo da Videoaula"
                                  subtitle="Verifique se você compreendeu o conceito explicado neste momento do vídeo."
                                >
                                  <div className="space-y-3">
                                    {currentVideo.perguntas_video.map((pv) => {
                                      const answeredIdx = checkpointAnswers[pv.id];
                                      const isAnswered = answeredIdx !== undefined;
                                      return (
                                        <div
                                          key={pv.id}
                                          className="rounded-xl border border-line bg-surface-2/60 p-4 space-y-3"
                                        >
                                          <div className="flex items-center justify-between">
                                            <span className="rounded bg-amber-400/20 px-2 py-0.5 font-mono text-2xs font-bold text-amber-300">
                                              ⏱ Momento {pv.momento_label} — {pv.capitulo_ref}
                                            </span>
                                            <button
                                              type="button"
                                              onClick={() => handleJumpToChapter(pv.id, pv.momento_seg)}
                                              className="text-2xs font-semibold text-amber-400 hover:underline"
                                            >
                                              Ir para {pv.momento_label} no vídeo
                                            </button>
                                          </div>

                                          <p className="text-xs font-bold text-fg">{pv.pergunta}</p>

                                          <div className="space-y-1.5">
                                            {pv.alternativas.map((alt, idx) => {
                                              const isCorr = idx === pv.correta_idx;
                                              const isChosen = answeredIdx === idx;
                                              return (
                                                <button
                                                  key={idx}
                                                  type="button"
                                                  onClick={() =>
                                                    setCheckpointAnswers((prev) => ({ ...prev, [pv.id]: idx }))
                                                  }
                                                  className={`w-full text-left rounded-lg border px-3 py-2 text-xs transition-all ${
                                                    isAnswered
                                                      ? isCorr
                                                        ? 'border-emerald-500/50 bg-emerald-500/15 text-emerald-200 font-semibold'
                                                        : isChosen
                                                          ? 'border-rose-500/50 bg-rose-500/15 text-rose-200'
                                                          : 'border-line/50 bg-surface/50 text-fg-3'
                                                      : 'border-line bg-surface hover:border-amber-400/40 text-fg-2'
                                                  }`}
                                                >
                                                  {alt}
                                                </button>
                                              );
                                            })}
                                          </div>

                                          {isAnswered && (
                                            <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/30 p-3 text-2xs text-emerald-200">
                                              <strong>Correção Comentada:</strong> {pv.explicacao}
                                            </div>
                                          )}
                                        </div>
                                      );
                                    })}
                                  </div>
                                </Card>
                              )}
                            </>
                          );
                        })()}
                      </div>

                      {/* Coluna Lateral: Playlist, Capítulos Clicáveis e Anotações Sincronizadas */}
                      <div className="lg:col-span-4 space-y-4">
                        <Card
                          title="Playlist & Capítulos da Aula"
                          subtitle="Clique em um capítulo para avançar diretamente ao minuto correspondente."
                        >
                          <div className="space-y-2.5">
                            {activeLesson.videoaulas.map((video, idx) => {
                              const isSelected = selectedVideoIndex === idx;
                              return (
                                <div key={idx} className="space-y-2">
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setSelectedVideoIndex(idx);
                                      setVideoStartSec(0);
                                      setActiveSlideIdx(0);
                                    }}
                                    className={`flex w-full items-start gap-3 rounded-xl border p-3 text-left transition-all ${
                                      isSelected
                                        ? 'border-amber-400 bg-amber-400/10 shadow-sm'
                                        : 'border-line bg-surface-2 hover:bg-surface-3'
                                    }`}
                                  >
                                    <div
                                      className={`flex size-7 shrink-0 items-center justify-center rounded-lg font-bold text-xs ${
                                        isSelected ? 'bg-amber-400 text-slate-950' : 'bg-surface-3 text-fg-3'
                                      }`}
                                    >
                                      {idx + 1}
                                    </div>
                                    <div className="min-w-0 flex-1">
                                      <p
                                        className={`text-xs font-bold leading-snug ${
                                          isSelected ? 'text-amber-400' : 'text-fg'
                                        }`}
                                      >
                                        {video.titulo}
                                      </p>
                                      <p className="mt-1 text-[10px] text-fg-3">
                                        {video.canal} • {video.duracao}
                                      </p>
                                    </div>
                                  </button>

                                  {/* Lista de Capítulos do Vídeo Ativo */}
                                  {isSelected && video.capitulos && video.capitulos.length > 0 && (
                                    <div className="pl-3 space-y-1.5 border-l-2 border-amber-400/30 ml-3">
                                      {video.capitulos.map((cap) => {
                                        const isCapDone = !!completedChapters[cap.id];
                                        const isCapActive = activeChapterId === cap.id;
                                        return (
                                          <button
                                            key={cap.id}
                                            type="button"
                                            onClick={() => handleJumpToChapter(cap.id, cap.tempo_seg)}
                                            className={`w-full text-left rounded-lg border p-2 text-2xs transition-all ${
                                              isCapActive
                                                ? 'border-amber-400/60 bg-amber-400/15 text-fg'
                                                : 'border-line/60 bg-surface hover:bg-surface-2 text-fg-2'
                                            }`}
                                          >
                                            <div className="flex items-center justify-between gap-1">
                                              <span className="font-bold text-fg">{cap.titulo}</span>
                                              <span className="font-mono text-[10px] text-amber-400 shrink-0">
                                                {isCapDone ? '✓ ' : ''}
                                                {cap.tempo_label}
                                              </span>
                                            </div>
                                            <p className="mt-0.5 text-[10px] text-fg-3 line-clamp-1">
                                              {cap.resumo}
                                            </p>
                                          </button>
                                        );
                                      })}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </Card>

                        {/* Bloco de Anotações Sincronizadas */}
                        <Card
                          title="Anotações Sincronizadas"
                          subtitle="Registre insights vinculados ao minuto atual da videoaula."
                        >
                          <div className="space-y-3">
                            <div className="flex gap-1.5">
                              <input
                                type="text"
                                value={noteInput}
                                onChange={(e) => setNoteInput(e.target.value)}
                                placeholder="Anotar conceito neste momento..."
                                className="flex-1 rounded-xl border border-line bg-surface-2 px-3 py-1.5 text-xs text-fg focus:border-amber-400 focus:outline-none"
                              />
                              <Button
                                variant="primary"
                                size="sm"
                                onClick={() =>
                                  handleAddSyncedNote(
                                    activeLesson.videoaulas?.[selectedVideoIndex]?.titulo || activeLesson.titulo
                                  )
                                }
                              >
                                Salvar
                              </Button>
                            </div>

                            <div className="space-y-2 max-h-52 overflow-y-auto">
                              {(lessonNotes[activeLesson.id] ?? []).length === 0 ? (
                                <p className="text-2xs text-fg-3 text-center py-2">
                                  Nenhuma anotação registrada nesta aula ainda.
                                </p>
                              ) : (
                                (lessonNotes[activeLesson.id] ?? []).map((note) => (
                                  <div
                                    key={note.id}
                                    className="rounded-xl border border-line bg-surface-2 p-2.5 text-2xs space-y-1"
                                  >
                                    <div className="flex items-center justify-between">
                                      <button
                                        type="button"
                                        onClick={() => setVideoStartSec(note.timestampSec)}
                                        className="font-mono font-bold text-amber-400 hover:underline"
                                      >
                                        ▶ {note.timestampLabel}
                                      </button>
                                      <span className="text-[10px] text-fg-3">{note.createdAt}</span>
                                    </div>
                                    <p className="text-fg-2">{note.text}</p>
                                  </div>
                                ))
                              )}
                            </div>
                          </div>
                        </Card>
                      </div>
                    </div>
                  ) : (
                    <Card>
                      <p className="text-xs text-fg-3">Nenhuma videoaula cadastrada para este tópico.</p>
                    </Card>
                  )}
                </div>
              )}

              {/* ================================================================
                  ETAPA 4: FLASHCARDS MULTIFORMATO & REPETIÇÃO ESPAÇADA (SM-2)
                 ================================================================ */}
              {activeTab === 'flashcards' && (
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-bold text-fg">
                        Flashcards Interativos Multiformato & Perspectiva 3D Real
                      </h3>
                      <p className="text-xs text-fg-3">
                        Pratique com cartões de Pergunta/Resposta, V/F, Complete a Lacuna e Identifique o Erro.
                      </p>
                    </div>

                    {/* Filtro por modelo de flashcard */}
                    <div className="flex flex-wrap items-center gap-1">
                      {[
                        { id: 'todos', label: 'Todos os Modelos' },
                        { id: 'pergunta_resposta', label: 'Pergunta & Resposta' },
                        { id: 'verdadeiro_falso', label: 'Verdadeiro / Falso' },
                        { id: 'complete_lacuna', label: 'Complete a Lacuna' },
                        { id: 'identifique_erro', label: 'Identifique o Erro' },
                      ].map((f) => (
                        <button
                          key={f.id}
                          type="button"
                          onClick={() => setFlashcardTypeFilter(f.id)}
                          className={`rounded-lg px-2.5 py-1 text-2xs font-semibold transition-all ${
                            flashcardTypeFilter === f.id
                              ? 'bg-amber-400 text-slate-950 font-bold'
                              : 'bg-surface border border-line text-fg-3 hover:text-fg'
                          }`}
                        >
                          {f.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {activeLesson.flashcards && activeLesson.flashcards.length > 0 ? (
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                      {activeLesson.flashcards
                        .filter((fc) =>
                          flashcardTypeFilter === 'todos' ? true : (fc.tipo || 'pergunta_resposta') === flashcardTypeFilter
                        )
                        .map((fc, idx) => {
                          const isFlipped = !!flippedCards[fc.id];
                          const isSaved = !!savedFlashcards[fc.id];
                          const isFav = !!favoriteFlashcards[fc.id];
                          const rated = cardDifficultyRatings[fc.id];
                          const guess = cardInteractiveGuess[fc.id];

                          const tipoLabels: Record<string, string> = {
                            pergunta_resposta: 'Pergunta & Resposta',
                            conceito_definicao: 'Conceito & Definição',
                            verdadeiro_falso: 'Verdadeiro ou Falso',
                            complete_lacuna: 'Complete a Lacuna',
                            identifique_erro: 'Identifique o Erro',
                            comparacao: 'Comparação Direta',
                            exemplo_pratico: 'Caso Prático',
                          };

                          return (
                            <div
                              key={fc.id}
                              style={{ perspective: '1000px' }}
                              className="group relative flex flex-col justify-between rounded-2xl border border-line bg-gradient-to-br from-surface via-surface-2 to-surface p-5 transition-all hover:border-amber-400/50 hover:shadow-lg min-h-[270px]"
                            >
                              {/* Topo do Cartão */}
                              <div>
                                <div className="flex items-center justify-between gap-2">
                                  <span className="rounded-md bg-purple-500/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-purple-300 border border-purple-500/30">
                                    {tipoLabels[fc.tipo || 'pergunta_resposta'] || `Cartão #${idx + 1}`}
                                  </span>
                                  <div className="flex items-center gap-1.5">
                                    <button
                                      type="button"
                                      onClick={() => toggleFavoriteCard(fc.id)}
                                      title="Favoritar cartão"
                                      className={`rounded p-1 transition-colors ${
                                        isFav ? 'text-amber-400' : 'text-fg-3 hover:text-fg'
                                      }`}
                                    >
                                      <Star size={13} className={isFav ? 'fill-current' : ''} />
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => toggleCardFlip(fc.id)}
                                      className="text-[10px] font-semibold text-amber-400 hover:underline"
                                    >
                                      {isFlipped ? '↺ Ver Frente' : '↻ Virar 3D'}
                                    </button>
                                  </div>
                                </div>

                                {/* Corpo com Rotação 3D Suave */}
                                <motion.div
                                  initial={false}
                                  animate={{ rotateY: isFlipped ? 180 : 0 }}
                                  transition={{ duration: 0.35 }}
                                  style={{ transformStyle: 'preserve-3d' }}
                                  className="mt-4"
                                >
                                  {!isFlipped ? (
                                    <div className="space-y-3">
                                      <p className="text-[10px] font-bold uppercase tracking-wider text-amber-400/80">
                                        Desafio Ativo
                                      </p>
                                      <h4 className="text-sm font-bold text-fg leading-relaxed">{fc.frente}</h4>

                                      {/* Interação antes de virar para V/F ou Complete a Lacuna */}
                                      {fc.tipo === 'verdadeiro_falso' && (
                                        <div className="flex gap-2 pt-1">
                                          {(['V', 'F'] as const).map((opt) => (
                                            <button
                                              key={opt}
                                              type="button"
                                              onClick={() => {
                                                setCardInteractiveGuess((p) => ({ ...p, [fc.id]: opt }));
                                                toggleCardFlip(fc.id);
                                              }}
                                              className="flex-1 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-bold text-fg hover:border-amber-400"
                                            >
                                              {opt === 'V' ? '✓ Verdadeiro' : '✗ Falso'}
                                            </button>
                                          ))}
                                        </div>
                                      )}

                                      {fc.tipo === 'complete_lacuna' && fc.lacuna_opcoes && (
                                        <div className="flex flex-wrap gap-1.5 pt-1">
                                          {fc.lacuna_opcoes.map((opt) => (
                                            <button
                                              key={opt}
                                              type="button"
                                              onClick={() => {
                                                setCardInteractiveGuess((p) => ({ ...p, [fc.id]: opt }));
                                                toggleCardFlip(fc.id);
                                              }}
                                              className="rounded-lg border border-line bg-surface px-2.5 py-1 text-2xs font-semibold text-fg-2 hover:border-amber-400 hover:text-fg"
                                            >
                                              {opt}
                                            </button>
                                          ))}
                                        </div>
                                      )}
                                    </div>
                                  ) : (
                                    <div style={{ transform: 'rotateY(180deg)' }} className="space-y-2.5">
                                      <div className="flex items-center justify-between">
                                        <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">
                                          Resposta & Fixação
                                        </p>
                                        {guess && (
                                          <span className="text-[10px] font-mono text-amber-300">
                                            Sua escolha: {guess}
                                          </span>
                                        )}
                                      </div>
                                      <p className="text-xs text-fg-2 leading-relaxed">{fc.verso}</p>
                                      {fc.mnemonico && (
                                        <div className="rounded-xl border border-amber-400/30 bg-amber-400/10 p-2.5 text-2xs text-amber-300">
                                          💡 <strong>Mnemônico:</strong> {fc.mnemonico}
                                        </div>
                                      )}
                                    </div>
                                  )}
                                </motion.div>
                              </div>

                              {/* Rodapé: Autoavaliação SM-2 + Salvar no Deck */}
                              <div className="mt-4 space-y-2 border-t border-line/60 pt-3">
                                {isFlipped && (
                                  <div className="grid grid-cols-3 gap-1">
                                    {[
                                      { label: 'Difícil', tone: 'text-rose-300 border-rose-500/30 bg-rose-500/10' },
                                      { label: 'Bom', tone: 'text-amber-300 border-amber-500/30 bg-amber-500/10' },
                                      {
                                        label: 'Fácil',
                                        tone: 'text-emerald-300 border-emerald-500/30 bg-emerald-500/10',
                                      },
                                    ].map((btn) => (
                                      <button
                                        key={btn.label}
                                        type="button"
                                        onClick={() => handleSaveFlashcard(fc, btn.label)}
                                        className={`rounded-lg border py-1 text-[10px] font-bold transition-all ${btn.tone}`}
                                      >
                                        {rated === btn.label ? `✓ ${btn.label}` : btn.label}
                                      </button>
                                    ))}
                                  </div>
                                )}

                                <div className="flex items-center justify-between gap-2">
                                  <button
                                    type="button"
                                    onClick={() => toggleCardFlip(fc.id)}
                                    className="text-2xs font-medium text-fg-3 hover:text-fg"
                                  >
                                    {isFlipped ? 'Ocultar resposta' : 'Clique para revelar verso'}
                                  </button>

                                  <button
                                    type="button"
                                    disabled={isSaved}
                                    onClick={() => handleSaveFlashcard(fc)}
                                    className={`rounded-lg px-2.5 py-1 text-[10px] font-bold transition-colors ${
                                      isSaved
                                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                                        : 'bg-surface-3 text-fg hover:bg-amber-400 hover:text-slate-950'
                                    }`}
                                  >
                                    {isSaved ? '✓ Salvo no Deck SM-2' : '+ Salvar no Deck SM-2'}
                                  </button>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                    </div>
                  ) : (
                    <Card>
                      <p className="text-xs text-fg-3">Nenhum flashcard disponível para esta aula.</p>
                    </Card>
                  )}
                </div>
              )}

              {/* ================================================================
                  ETAPA 5: RAIO-X DAS BANCAS (FUNDAMENTADO EM DADOS REAIS)
                 ================================================================ */}
              {activeTab === 'bancas' && (
                <div className="space-y-4">
                  {/* Métricas Verificáveis no Banco de Questões */}
                  {activeLesson.estatisticas_bancas_verificaveis && (
                    <Card
                      title="Evidência Verificável no Acervo de Provas"
                      subtitle="Contagem real baseada exclusivamente nas questões de concursos cadastradas no banco para esta matéria."
                    >
                      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                        {Object.entries(activeLesson.estatisticas_bancas_verificaveis.por_banca).map(
                          ([bancaKey, st]) => (
                            <div
                              key={bancaKey}
                              className="rounded-xl border border-line bg-surface-2/70 p-3.5 space-y-1"
                            >
                              <span className="text-xs font-black uppercase tracking-wider text-amber-400">
                                Banca {bancaKey.toUpperCase()}
                              </span>
                              <p className="font-mono text-lg font-bold text-fg">
                                {st.questoes_registradas} questão(ões)
                              </p>
                              <p className="text-[10px] text-fg-3">
                                Formato: {st.formatos_verificados.join(' • ')}
                              </p>
                            </div>
                          )
                        )}
                      </div>
                    </Card>
                  )}

                  <Card
                    title="Como Cada Banca Cobra Este Assunto"
                    subtitle="Compare o estilo de cobrança e as armadilhas favoritas das organizadoras."
                  >
                    <div className="grid gap-3.5 sm:grid-cols-2">
                      {Object.entries(activeLesson.radiografia_bancas).map(([bancaKey, analise]) => {
                        const bancaColors: Record<string, string> = {
                          fgv: 'border-amber-500/30 bg-amber-500/5 text-amber-300',
                          cebraspe: 'border-rose-500/30 bg-rose-500/5 text-rose-300',
                          quadrix: 'border-sky-500/30 bg-sky-500/5 text-sky-300',
                          ibfc: 'border-emerald-500/30 bg-emerald-500/5 text-emerald-300',
                        };
                        const styleClass =
                          bancaColors[bancaKey] || 'border-line bg-surface-2 text-fg-2';

                        return (
                          <div
                            key={bancaKey}
                            className={`rounded-xl border p-4 space-y-2 flex flex-col justify-between ${styleClass}`}
                          >
                            <div className="space-y-2">
                              <div className="flex items-center justify-between">
                                <span className="text-xs font-black uppercase tracking-wider">
                                  Banca {bancaKey.toUpperCase()}
                                </span>
                                <span className="text-[10px] uppercase tracking-wider opacity-75">
                                  Padrão de Prova
                                </span>
                              </div>
                              <p className="text-xs leading-relaxed text-fg">{analise}</p>
                            </div>

                            <div className="pt-2">
                              <button
                                type="button"
                                onClick={() => setActiveTab('questoes')}
                                className="text-2xs font-bold text-amber-400 hover:underline"
                              >
                                Resolver questões da {bancaKey.toUpperCase()} no Laboratório →
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </Card>
                </div>
              )}

              {/* ================================================================
                  ETAPA 6: LABORATÓRIO DE QUESTÕES INTERATIVAS & FEEDBACK INTELIGENTE
                 ================================================================ */}
              {activeTab === 'questoes' && (
                <div className="space-y-5">
                  {/* Seção A: Exercícios Interativos Estilo H5P / Brilliant */}
                  {activeLesson.exercicios_interativos &&
                    activeLesson.exercicios_interativos.length > 0 && (
                      <Card
                        title="Laboratório Interativo de Fixação Imediata"
                        subtitle="Atividades rápidas de preenchimento de lacuna e associação antes das questões de prova."
                      >
                        <div className="space-y-4">
                          {activeLesson.exercicios_interativos.map((ex: LessonInteractiveExercise) => {
                            const userVal = labExerciseState[ex.id];
                            const isRev = !!labExerciseRevealed[ex.id];
                            return (
                              <div
                                key={ex.id}
                                className="rounded-xl border border-line bg-surface-2/60 p-4 space-y-3"
                              >
                                <div className="flex items-center justify-between">
                                  <Badge tone="verified">{ex.titulo}</Badge>
                                  <span className="text-2xs font-mono text-fg-3 uppercase">{ex.tipo}</span>
                                </div>
                                <p className="text-xs font-medium text-fg leading-relaxed">{ex.enunciado}</p>

                                {ex.tipo === 'complete_lacuna' && ex.opcoes && (
                                  <div className="flex flex-wrap gap-2">
                                    {ex.opcoes.map((op) => {
                                      const isSelected = userVal === op;
                                      const isCorr = op === ex.resposta_correta;
                                      return (
                                        <button
                                          key={op}
                                          type="button"
                                          onClick={() => {
                                            setLabExerciseState((p) => ({ ...p, [ex.id]: op }));
                                            setLabExerciseRevealed((p) => ({ ...p, [ex.id]: true }));
                                          }}
                                          className={`rounded-xl border px-3 py-1.5 text-xs font-bold transition-all ${
                                            isRev
                                              ? isCorr
                                                ? 'border-emerald-500 bg-emerald-500/20 text-emerald-300'
                                                : isSelected
                                                  ? 'border-rose-500 bg-rose-500/20 text-rose-300'
                                                  : 'border-line bg-surface text-fg-3'
                                              : 'border-line bg-surface text-fg hover:border-amber-400'
                                          }`}
                                        >
                                          {op}
                                        </button>
                                      );
                                    })}
                                  </div>
                                )}

                                {ex.tipo === 'associacao_conceitos' && ex.pares && (
                                  <div className="grid gap-2 sm:grid-cols-2">
                                    {ex.pares.map((par) => (
                                      <div
                                        key={par.id}
                                        className="rounded-lg border border-line bg-surface p-2.5 text-2xs space-y-1"
                                      >
                                        <span className="font-bold text-amber-400">{par.conceito}</span>
                                        <p className="text-fg-2">➔ {par.definicao}</p>
                                      </div>
                                    ))}
                                  </div>
                                )}

                                {ex.tipo === 'ordenacao_etapas' && ex.etapas_corretas && (
                                  <div className="space-y-1.5">
                                    {ex.etapas_corretas.map((etapa, idx) => (
                                      <div
                                        key={idx}
                                        className="rounded-lg border border-line bg-surface px-3 py-2 text-xs text-fg-2 font-mono"
                                      >
                                        {etapa}
                                      </div>
                                    ))}
                                  </div>
                                )}

                                {isRev && (
                                  <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/30 p-3 text-2xs text-emerald-200">
                                    <strong>Explicação Didática:</strong> {ex.explicacao}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </Card>
                    )}

                  {/* Seção B: Questões de Provas Anteriores com Justificativa Alternativa por Alternativa */}
                  <Card
                    title="Caderno de Questões de Provas Reais Comentadas"
                    subtitle="Selecione uma alternativa, confirme sua resposta e veja a análise detalhada de cada item."
                  >
                    {activeLessonQuestions.length === 0 ? (
                      <p className="text-xs text-fg-3">
                        Nenhuma questão cadastrada para esta aula no momento.
                      </p>
                    ) : (
                      <div className="space-y-5">
                        {activeLessonQuestions.map((q, idx) => {
                          const selected = selectedAnswers[q.id];
                          const isRevealed = !!revealedQuestions[q.id];
                          const correctKey = q.gabarito;
                          const isCorrect = selected === correctKey;
                          const isCardCreated = !!questionConvertedToCard[q.id];

                          const optionsList =
                            q.alternativas_formatadas && q.alternativas_formatadas.length > 0
                              ? q.alternativas_formatadas
                              : (q.alternativas ?? []).map((txt, i) => {
                                  const letra = ['A', 'B', 'C', 'D', 'E'][i] || String(i + 1);
                                  return {
                                    letra,
                                    texto: txt,
                                    correta: letra === correctKey,
                                    justificativa: q.comentario,
                                  };
                                });

                          return (
                            <div
                              key={q.id}
                              className="rounded-2xl border border-line bg-surface p-4 sm:p-5 space-y-3.5 shadow-sm"
                            >
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <div className="flex flex-wrap items-center gap-2">
                                  <Badge tone="verified">Questão {idx + 1}</Badge>
                                  {q.banca_sigla && <Badge tone="neutral">{q.banca_sigla}</Badge>}
                                  {q.subtopico && (
                                    <span className="text-2xs text-amber-400 font-semibold">
                                      • {q.subtopico}
                                    </span>
                                  )}
                                </div>
                                <span className="text-[10px] font-mono text-fg-3">{q.fonte}</span>
                              </div>

                              <p className="text-xs leading-relaxed text-fg whitespace-pre-line font-medium">
                                {q.enunciado}
                              </p>

                              {/* Lista de Alternativas */}
                              <div className="space-y-2 pt-1">
                                {optionsList.map((opt) => {
                                  const isSelected = selected === opt.letra;
                                  const isThisCorrect = opt.letra === correctKey;

                                  let optionStyle =
                                    'border-line bg-surface-2/60 text-fg hover:border-line-strong hover:bg-surface-2';
                                  if (!isRevealed && isSelected) {
                                    optionStyle =
                                      'border-amber-400 bg-amber-400/15 text-amber-200 ring-1 ring-amber-400/40';
                                  } else if (isRevealed) {
                                    if (isThisCorrect) {
                                      optionStyle =
                                        'border-emerald-500/60 bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30';
                                    } else if (isSelected && !isThisCorrect) {
                                      optionStyle =
                                        'border-rose-500/60 bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/30';
                                    } else {
                                      optionStyle = 'border-line/40 bg-surface/40 text-fg-3 opacity-75';
                                    }
                                  }

                                  return (
                                    <div key={opt.letra} className="space-y-1">
                                      <button
                                        type="button"
                                        disabled={isRevealed}
                                        onClick={() => handleSelectOption(q.id, opt.letra)}
                                        className={`flex w-full items-start gap-3 rounded-xl border p-3 text-left text-xs transition-all ${optionStyle}`}
                                      >
                                        <span
                                          className={`flex size-5 shrink-0 items-center justify-center rounded font-bold text-2xs ${
                                            isRevealed && isThisCorrect
                                              ? 'bg-emerald-500 text-slate-950'
                                              : isRevealed && isSelected
                                                ? 'bg-rose-500 text-white'
                                                : isSelected
                                                  ? 'bg-amber-400 text-slate-950'
                                                  : 'bg-surface-3 text-fg'
                                          }`}
                                        >
                                          {opt.letra}
                                        </span>
                                        <span className="flex-1 leading-normal">{opt.texto}</span>
                                      </button>

                                      {/* Justificativa individual da alternativa selecionada ou correta */}
                                      {isRevealed && (isThisCorrect || isSelected) && opt.justificativa && (
                                        <div
                                          className={`ml-8 rounded-lg px-3 py-1.5 text-[11px] ${
                                            isThisCorrect
                                              ? 'bg-emerald-500/10 text-emerald-300'
                                              : 'bg-rose-500/10 text-rose-300'
                                          }`}
                                        >
                                          {opt.justificativa}
                                        </div>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>

                              {/* Botão de Confirmação ou Feedback Completo */}
                              {!isRevealed ? (
                                <div className="flex items-center justify-end pt-1">
                                  <Button
                                    variant="primary"
                                    size="sm"
                                    disabled={!selected}
                                    onClick={() => handleConfirmQuestion(q)}
                                  >
                                    Confirmar Resposta
                                  </Button>
                                </div>
                              ) : (
                                <div
                                  className={`rounded-xl border p-4 space-y-2.5 text-xs ${
                                    isCorrect
                                      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
                                      : 'border-rose-500/30 bg-rose-500/10 text-rose-200'
                                  }`}
                                >
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <div className="flex items-center gap-1.5 font-bold">
                                      {isCorrect ? (
                                        <>
                                          <CheckCircle2 size={15} className="text-emerald-400" />
                                          <span>Resposta Correta! Gabarito Oficial: {correctKey}</span>
                                        </>
                                      ) : (
                                        <>
                                          <XCircle size={15} className="text-rose-400" />
                                          <span>
                                            Você assinalou {selected}. O Gabarito Oficial é {correctKey}.
                                          </span>
                                        </>
                                      )}
                                    </div>

                                    <button
                                      type="button"
                                      disabled={isCardCreated}
                                      onClick={() => handleCreateFlashcardFromQuestion(q)}
                                      className="rounded-lg bg-surface/90 border border-line px-2.5 py-1 text-[10px] font-bold text-amber-300 hover:border-amber-400"
                                    >
                                      {isCardCreated
                                        ? '✓ Convertida em Flashcard SM-2'
                                        : '+ Transformar em Flashcard de Revisão'}
                                    </button>
                                  </div>

                                  {q.comentario && (
                                    <p className="text-fg-2 leading-relaxed pt-1 border-t border-white/10">
                                      <strong>Fundamentação Completa do Professor:</strong> {q.comentario}
                                    </p>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </Card>
                </div>
              )}

              {/* ================================================================
                  ETAPA 7: AVALIAÇÃO DE DOMÍNIO & DIAGNÓSTICO POR COMPETÊNCIA
                 ================================================================ */}
              {activeTab === 'avaliacao' && (
                <div className="space-y-5">
                  <Card
                    title={`Avaliação de Domínio: ${activeLesson.titulo}`}
                    subtitle="Verifique seu nível real de retenção por subtópico e receba a recomendação do próximo passo."
                  >
                    <div className="space-y-5">
                      {/* Painel de Resultados Reais */}
                      <div className="grid gap-3 sm:grid-cols-4">
                        <div className="rounded-xl border border-line bg-surface-2 p-3.5">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-fg-3">
                            Questões da Aula
                          </span>
                          <p className="mt-1 font-mono text-xl font-bold text-fg">
                            {masteryEvaluation.answered}/{masteryEvaluation.total}
                          </p>
                          <span className="text-2xs text-fg-3">Respondidas</span>
                        </div>

                        <div className="rounded-xl border border-line bg-surface-2 p-3.5">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">
                            Acertos Verificados
                          </span>
                          <p className="mt-1 font-mono text-xl font-bold text-emerald-400">
                            {masteryEvaluation.correct}
                          </p>
                          <span className="text-2xs text-fg-3">Erros: {masteryEvaluation.wrong}</span>
                        </div>

                        <div className="rounded-xl border border-line bg-surface-2 p-3.5">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400">
                            Aproveitamento Real
                          </span>
                          <p className="mt-1 font-mono text-xl font-bold text-amber-400">
                            {masteryEvaluation.pct}%
                          </p>
                          <span className="text-2xs text-fg-3">Meta de domínio: 70%</span>
                        </div>

                        <div className="rounded-xl border border-line bg-surface-2 p-3.5">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-sky-400">
                            Tempo Dedicado
                          </span>
                          <p className="mt-1 font-mono text-xl font-bold text-fg">{clock(studySeconds)}</p>
                          <span className="text-2xs text-fg-3">Nesta sessão</span>
                        </div>
                      </div>

                      {/* Barras de Domínio por Subtópico / Competência */}
                      <div className="rounded-2xl border border-line bg-surface-2/60 p-4 space-y-3">
                        <h4 className="text-xs font-bold uppercase tracking-wider text-amber-400">
                          Domínio por Competência da Aula (Baseado nas suas Respostas Reais)
                        </h4>
                        <div className="space-y-3">
                          {masteryEvaluation.byCompetence.map((comp) => (
                            <div key={comp.nome} className="space-y-1">
                              <div className="flex items-center justify-between text-xs">
                                <span className="font-semibold text-fg">{comp.nome}</span>
                                <span className="font-mono font-bold text-fg-2">
                                  {comp.acertos}/{comp.total} ({comp.pct}%)
                                </span>
                              </div>
                              <div className="h-2 w-full overflow-hidden rounded-full bg-surface-3">
                                <div
                                  className={`h-full rounded-full transition-all duration-500 ${
                                    comp.pct >= 70
                                      ? 'bg-emerald-400'
                                      : comp.pct >= 40
                                        ? 'bg-amber-400'
                                        : 'bg-rose-400'
                                  }`}
                                  style={{ width: `${comp.pct}%` }}
                                />
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Questões Rápidas caso o aluno ainda não tenha respondido todas */}
                      {masteryEvaluation.answered < masteryEvaluation.total && (
                        <div className="rounded-xl border border-amber-400/30 bg-amber-400/5 p-4 flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="text-xs font-bold text-amber-300">
                              Você respondeu {masteryEvaluation.answered} de {masteryEvaluation.total}{' '}
                              questões desta aula.
                            </p>
                            <p className="text-2xs text-fg-3">
                              Conclua todas as questões no Laboratório para obter o diagnóstico completo de
                              domínio.
                            </p>
                          </div>
                          <Button variant="primary" size="sm" onClick={() => setActiveTab('questoes')}>
                            Responder Questões Pendentes
                          </Button>
                        </div>
                      )}

                      {/* Recomendação Inteligente do Próximo Passo */}
                      <div className="rounded-2xl border border-line bg-surface p-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div className="space-y-1">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">
                            Próximo Passo Recomendado
                          </span>
                          <p className="text-xs font-semibold text-fg">
                            {masteryEvaluation.pct >= 70
                              ? 'Excelente domínio! Marque a aula como concluída e avance para a próxima aula da trilha.'
                              : 'Recomendamos revisar o Quadro Digital e salvar os Flashcards desta aula no seu deck SM-2 antes de avançar.'}
                          </p>
                        </div>

                        <div className="flex flex-wrap items-center gap-2 shrink-0">
                          {masteryEvaluation.pct < 70 ? (
                            <>
                              <Button variant="secondary" size="sm" onClick={() => setActiveTab('visual')}>
                                Revisar Quadro Visual
                              </Button>
                              <Button
                                variant="primary"
                                size="sm"
                                onClick={() => setActiveTab('flashcards')}
                              >
                                Praticar Flashcards
                              </Button>
                            </>
                          ) : (
                            <Button
                              variant="primary"
                              size="sm"
                              onClick={() => {
                                if (!completedLessons.includes(activeLesson.id)) {
                                  toggleLessonCompletion(activeLesson.id);
                                }
                                if (nextLesson) {
                                  handleSelectLesson(nextLesson.id);
                                }
                              }}
                            >
                              Concluir & Avançar <ArrowRight size={14} />
                            </Button>
                          )}
                        </div>
                      </div>
                    </div>
                  </Card>
                </div>
              )}

              {/* Rodapé de Navegação Entre Aulas */}
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-surface p-4">
                {prevLesson ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => handleSelectLesson(prevLesson.id)}
                    className="gap-2"
                  >
                    <ArrowLeft size={14} />
                    <span className="truncate max-w-[200px] sm:max-w-xs">{prevLesson.titulo}</span>
                  </Button>
                ) : (
                  <div />
                )}

                {nextLesson ? (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => handleSelectLesson(nextLesson.id)}
                    className="gap-2"
                  >
                    <span className="truncate max-w-[200px] sm:max-w-xs">
                      Próxima: {nextLesson.titulo}
                    </span>
                    <ArrowRight size={14} />
                  </Button>
                ) : (
                  <Button variant="secondary" size="sm" onClick={() => handleSelectLesson(null)}>
                    Concluir Trilha & Voltar ao Catálogo
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
