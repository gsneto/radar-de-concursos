import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { keys, useLesson, useLessons, useQuestions } from '@/app/queries';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { SkeletonRows } from '@/components/ui/states';
import { api } from '@/lib/api';
import { clock } from '@/lib/format';
import type {
  LessonFlashcard,
  LessonQuestionDetail,
} from '@/lib/types';
import { JottaFlashcardGrid } from './JottaFlashcardView';
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

/** Divide a teoria em blocos numerados com títulos claros para eliminar "paredes de texto" */
function parseStructuredTheory(raw: string): { title: string; body: string }[] {
  const paragraphs = raw
    .trim()
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean);

  return paragraphs.map((p, idx) => {
    const clean = p.replace(/\*\*/g, '');
    const firstColon = clean.indexOf(':');
    if (firstColon > 0 && firstColon < 65) {
      return {
        title: clean.slice(0, firstColon).replace(/^[-•]\s*/, '').trim(),
        body: clean.slice(firstColon + 1).trim(),
      };
    }
    const titles = [
      'Visão Geral e Conceito Base',
      'Regras Fundamentais Cobradas em Prova',
      'Diferenciação Técnica e Aplicações',
      'Síntese Estratégica de Resolução',
    ];
    return {
      title: titles[idx % titles.length],
      body: clean,
    };
  });
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

  // 5 Etapas Claras (mais abas de compatibilidade)
  const [activeTab, setActiveTab] = useState<
    'resumo' | 'visual' | 'video' | 'flashcards' | 'questoes'
  >('resumo');

  // Professor Virtual Contextual
  const [tutorOpen, setTutorOpen] = useState<boolean>(false);
  const [activeTutorMode, setActiveTutorMode] = useState<
    'explicar_simples' | 'exemplo_pratico' | 'comparar_conceitos' | 'resumo_1_minuto'
  >('explicar_simples');
  const [tutorCustomFeedback, setTutorCustomFeedback] = useState<string | null>(null);

  // Studio de Criação de Aula
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [newLessonTitle, setNewLessonTitle] = useState<string>('');
  const [newLessonDisc, setNewLessonDisc] = useState<string>('Banco de Dados');
  const [newLessonMod, setNewLessonMod] = useState<string>('Módulo 1: Tópicos Especiais');
  const [newLessonSummary, setNewLessonSummary] = useState<string>('');
  const [newLessonObjective, setNewLessonObjective] = useState<string>('');
  const [creatingLesson, setCreatingLesson] = useState<boolean>(false);

  // Videoaula: player verificado + slides interativos + capítulos + notas
  const [selectedVideoIndex, setSelectedVideoIndex] = useState<number>(0);
  const [videoPresentationMode, setVideoPresentationMode] = useState<'video' | 'slides'>('video');
  const [activeSlideIdx, setActiveSlideIdx] = useState<number>(0);
  const [videoStartSec, setVideoStartSec] = useState<number>(0);
  const [activeChapterId, setActiveChapterId] = useState<string>('');
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

  // Quadro Visual e Mapa Mental
  const [activeVisualStep, setActiveVisualStep] = useState<number>(0);
  const [selectedMindMapNodeId, setSelectedMindMapNodeId] = useState<string | null>(null);

  // Flashcards Visuais Estilo Jotta e SM-2
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

  // Questões & Laboratório
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, string>>({});
  const [revealedQuestions, setRevealedQuestions] = useState<Record<string, boolean>>({});
  const [questionConvertedToCard, setQuestionConvertedToCard] = useState<Record<string, boolean>>({});
  const [labExerciseState, setLabExerciseState] = useState<Record<string, string>>({});
  const [labExerciseRevealed, setLabExerciseRevealed] = useState<Record<string, boolean>>({});

  // Sincroniza URL ?aula=...
  useEffect(() => {
    if (aulaParam !== activeLessonId) {
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

  // Aulas concluídas
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

  // Cronômetro integrado
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
    setTimerRunning(Boolean(activeLessonId));
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

  const totalEarnedXp = useMemo(() => {
    const lessonsXp = completedCount * 120;
    const questionsXp = Object.keys(revealedQuestions).length * 25;
    const flashcardsXp = Object.keys(savedFlashcards).length * 15 + Object.keys(cardDifficultyRatings).length * 10;
    const chaptersXp = Object.values(completedChapters).filter(Boolean).length * 20;
    return lessonsXp + questionsXp + flashcardsXp + chaptersXp;
  }, [completedCount, revealedQuestions, savedFlashcards, cardDifficultyRatings, completedChapters]);

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

  const currentLessonIndex = lessons.findIndex((l) => l.id === activeLessonId);
  const prevLesson = currentLessonIndex > 0 ? lessons[currentLessonIndex - 1] : null;
  const nextLesson =
    currentLessonIndex >= 0 && currentLessonIndex < lessons.length - 1 ? lessons[currentLessonIndex + 1] : null;

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

  const handleSaveFlashcard = async (fc: LessonFlashcard, customQualityLabel?: string) => {
    if (customQualityLabel) {
      setCardDifficultyRatings((prev) => ({ ...prev, [fc.id]: customQualityLabel }));
    }
    try {
      await api.post('/api/estudos/flashcards', {
        frente: fc.frente,
        verso: `${fc.verso}${fc.mnemonico ? `\n\n💡 Mnemônico: ${fc.mnemonico}` : ''}`,
        tags: [fc.tag, fc.tipo || 'visual'].filter(Boolean),
        fonte: activeLesson?.titulo || 'Aula GSN',
      });
      setSavedFlashcards((prev) => ({ ...prev, [fc.id]: true }));
      void queryClient.invalidateQueries({ queryKey: keys.flashQueue() });
      void queryClient.invalidateQueries({ queryKey: keys.flashStats() });
    } catch {
      setSavedFlashcards((prev) => ({ ...prev, [fc.id]: true }));
    }
  };

  const handleSelectOption = (questionId: string, optionKey: string) => {
    if (revealedQuestions[questionId]) return;
    setSelectedAnswers((prev) => ({ ...prev, [questionId]: optionKey }));
    setRevealedQuestions((prev) => ({ ...prev, [questionId]: true }));

    void api
      .post('/api/estudos/tentativas', {
        questao_id: questionId,
        resposta: optionKey,
        modo: 'aula',
      })
      .then(() => {
        void queryClient.invalidateQueries({ queryKey: keys.performance() });
        void queryClient.invalidateQueries({ queryKey: keys.study() });
      })
      .catch(() => {
        // fallback silencioso
      });
  };

  const handleConvertQuestionToFlashcard = async (q: LessonQuestionDetail) => {
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
    } catch {
      setQuestionConvertedToCard((prev) => ({ ...prev, [q.id]: true }));
    }
  };

  const handleJumpToChapter = (chapterId: string, startSec: number) => {
    setActiveChapterId(chapterId);
    setVideoStartSec(startSec);
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

  const handleAddVideoNote = (chapterTitle: string, timestampLabel: string, timestampSec: number) => {
    if (!activeLesson || !noteInput.trim()) return;
    const newNote: SyncedVideoNote = {
      id: `note-${Date.now()}`,
      chapterTitle,
      timestampLabel,
      timestampSec,
      text: noteInput.trim(),
      createdAt: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }),
    };
    setLessonNotes((prev) => {
      const current = prev[activeLesson.id] ?? [];
      const updated = { ...prev, [activeLesson.id]: [newNote, ...current] };
      try {
        localStorage.setItem('radar_lesson_synced_notes', JSON.stringify(updated));
      } catch {
        // ignore
      }
      return updated;
    });
    setNoteInput('');
  };

  const handleCreateCustomLesson = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newLessonTitle.trim() || !newLessonDisc.trim()) return;
    setCreatingLesson(true);
    try {
      const res = await api.post<{ ok: boolean; aula: { id: string } }>('/api/estudos/aulas', {
        titulo: newLessonTitle.trim(),
        disciplina: newLessonDisc.trim(),
        modulo: newLessonMod.trim(),
        teoria_resumida:
          newLessonSummary.trim() || `Resumo didático estruturado sobre ${newLessonTitle.trim()}.`,
        objetivos: [
          newLessonObjective.trim() || `Dominar a aplicação prática de ${newLessonTitle.trim()} nas provas.`,
          'Resolver questões reais comentadas com segurança.',
        ],
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

  const masteryStats = useMemo(() => {
    const total = activeLessonQuestions.length;
    if (total === 0) {
      return { total: 0, answered: 0, correct: 0, wrong: 0, pct: 0 };
    }
    let answered = 0;
    let correct = 0;
    for (const q of activeLessonQuestions) {
      const userAns = selectedAnswers[q.id];
      if (userAns) {
        answered += 1;
        if (userAns === q.gabarito) {
          correct += 1;
        }
      }
    }
    const wrong = Math.max(0, answered - correct);
    const pct = total > 0 ? Math.round((correct / total) * 100) : 0;
    return { total, answered, correct, wrong, pct };
  }, [activeLessonQuestions, selectedAnswers]);

  return (
    <div className="space-y-6">
      {/* MODAL DE NOVA AULA */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
          <div className="w-full max-w-xl rounded-2xl border border-line-strong bg-surface p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-line pb-3">
              <div className="flex items-center gap-2">
                <span className="flex size-8 items-center justify-center rounded-lg bg-amber-400 text-slate-950">
                  <Plus size={16} />
                </span>
                <div>
                  <h3 className="text-base font-bold text-fg">Criar Nova Aula Estruturada</h3>
                  <p className="text-xs text-fg-2">
                    Publique um novo módulo com resumo, quadro visual e flashcards automáticos.
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

            <form onSubmit={handleCreateCustomLesson} className="space-y-3.5">
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className="text-xs font-bold text-fg-2">Disciplina</label>
                  <select
                    value={newLessonDisc}
                    onChange={(e) => setNewLessonDisc(e.target.value)}
                    className="mt-1 h-10 w-full rounded-xl border border-line-strong bg-surface-2 px-3 text-sm text-fg"
                  >
                    {disciplinas
                      .filter((d) => d.key)
                      .map((d) => (
                        <option key={d.key} value={d.key}>
                          {d.label}
                        </option>
                      ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-bold text-fg-2">Módulo</label>
                  <input
                    type="text"
                    value={newLessonMod}
                    onChange={(e) => setNewLessonMod(e.target.value)}
                    className="mt-1 h-10 w-full rounded-xl border border-line-strong bg-surface-2 px-3 text-sm text-fg"
                  />
                </div>
              </div>
              <div>
                <label className="text-xs font-bold text-fg-2">Título da Aula</label>
                <input
                  type="text"
                  required
                  value={newLessonTitle}
                  onChange={(e) => setNewLessonTitle(e.target.value)}
                  placeholder="Ex: Aula 03: Índices B-Tree e Otimização de Consultas"
                  className="mt-1 h-10 w-full rounded-xl border border-line-strong bg-surface-2 px-3 text-sm text-fg"
                />
              </div>
              <div>
                <label className="text-xs font-bold text-fg-2">Objetivo Principal</label>
                <input
                  type="text"
                  value={newLessonObjective}
                  onChange={(e) => setNewLessonObjective(e.target.value)}
                  placeholder="Ex: Compreender quando criar índices compostos."
                  className="mt-1 h-10 w-full rounded-xl border border-line-strong bg-surface-2 px-3 text-sm text-fg"
                />
              </div>
              <div>
                <label className="text-xs font-bold text-fg-2">Resumo Teórico</label>
                <textarea
                  rows={3}
                  value={newLessonSummary}
                  onChange={(e) => setNewLessonSummary(e.target.value)}
                  placeholder="Síntese explicativa do conteúdo..."
                  className="mt-1 w-full rounded-xl border border-line-strong bg-surface-2 p-3 text-sm text-fg"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="ghost" size="sm" onClick={() => setShowCreateModal(false)}>
                  Cancelar
                </Button>
                <Button variant="primary" size="sm" type="submit" disabled={creatingLesson}>
                  {creatingLesson ? 'Publicando...' : 'Publicar Aula'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ====================================================================
          VISÃO 1: CATÁLOGO DE AULAS (QUANDO NENHUMA AULA ESTÁ ABERTA)
         ==================================================================== */}
      {!activeLessonId && (
        <>
          <div className="rounded-2xl border border-line-strong bg-surface p-6 shadow-md">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
              <div className="space-y-2 max-w-2xl">
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center gap-1.5 rounded-md bg-amber-400 px-2.5 py-1 text-xs font-black uppercase tracking-wider text-slate-950">
                    <Sparkles size={13} /> Ambiente Completo de Ensino
                  </span>
                  <span className="rounded-md border border-emerald-500/40 bg-emerald-500/15 px-2.5 py-1 text-xs font-bold text-emerald-300">
                    Teoria + Videoaulas + Flashcards Visuais
                  </span>
                </div>
                <h2 className="font-display text-2xl sm:text-3xl font-extrabold text-fg tracking-tight">
                  Trilha de Aulas Esquematizadas
                </h2>
                <p className="text-sm text-fg-2 leading-relaxed">
                  Escolha uma aula abaixo para estudar a teoria dividida por blocos, assistir às videoaulas verificadas,
                  revisar as fichas visuais e responder questões comentadas.
                </p>
              </div>

              <div className="grid grid-cols-3 gap-3 shrink-0">
                <div className="rounded-xl border border-amber-400/40 bg-amber-400/10 p-3.5 text-center">
                  <span className="text-[11px] font-extrabold uppercase tracking-wider text-amber-300 block">
                    XP Acumulado
                  </span>
                  <p className="mt-1 font-display text-xl font-black text-fg tabular">{totalEarnedXp} XP</p>
                </div>
                <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 p-3.5 text-center">
                  <span className="text-[11px] font-extrabold uppercase tracking-wider text-emerald-300 block">
                    Concluídas
                  </span>
                  <p className="mt-1 font-display text-xl font-black text-fg tabular">
                    {completedCount}/{totalLessonsCount} ({completionPercentage}%)
                  </p>
                </div>
                <div className="flex flex-col justify-center rounded-xl border border-line-strong bg-surface-2 p-3 text-center">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setShowCreateModal(true)}
                    className="w-full gap-1.5 text-xs font-bold text-amber-300 border-amber-400/40"
                  >
                    <Plus size={14} /> Nova Aula
                  </Button>
                </div>
              </div>
            </div>

            {/* Busca e Filtros */}
            <div className="mt-5 pt-4 border-t border-line flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
              <div className="relative flex-1 max-w-md">
                <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-fg-3" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Buscar aula por assunto (ex: SQL, 3FN, Scrum, Conectivos, Criptografia)..."
                  className="w-full rounded-xl border border-line-strong bg-surface-2 pl-10 pr-4 py-2.5 text-sm text-fg placeholder:text-fg-3 focus:border-amber-400 focus:outline-none"
                />
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <div className="flex items-center gap-1 rounded-xl border border-line-strong bg-surface-2 p-1">
                  <button
                    type="button"
                    onClick={() => setCatalogViewMode('modulos')}
                    className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
                      catalogViewMode === 'modulos'
                        ? 'bg-amber-400 text-slate-950'
                        : 'text-fg-2 hover:text-fg'
                    }`}
                  >
                    <ListTree size={14} /> Por Módulos
                  </button>
                  <button
                    type="button"
                    onClick={() => setCatalogViewMode('grade')}
                    className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
                      catalogViewMode === 'grade'
                        ? 'bg-amber-400 text-slate-950'
                        : 'text-fg-2 hover:text-fg'
                    }`}
                  >
                    <LayoutGrid size={14} /> Grade
                  </button>
                </div>

                <div className="flex items-center gap-1 rounded-xl border border-line-strong bg-surface-2 p-1">
                  {(
                    [
                      { key: 'todas', label: `Todas (${totalLessonsCount})` },
                      { key: 'pendentes', label: `Pendentes (${totalLessonsCount - completedCount})` },
                      { key: 'concluidas', label: `Concluídas (${completedCount})` },
                    ] as const
                  ).map((f) => (
                    <button
                      key={f.key}
                      type="button"
                      onClick={() => setStatusFilter(f.key)}
                      className={`rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
                        statusFilter === f.key
                          ? 'bg-surface text-amber-300 border border-amber-400/40'
                          : 'text-fg-2 hover:text-fg'
                      }`}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Pílulas de Disciplinas */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1">
            {disciplinas.map((disc) => {
              const active = selectedDisciplina === disc.key;
              return (
                <button
                  key={disc.key}
                  type="button"
                  onClick={() => setSelectedDisciplina(disc.key)}
                  className={`px-4 py-2 rounded-xl text-xs font-extrabold whitespace-nowrap transition-all ${
                    active
                      ? 'bg-amber-400 text-slate-950 shadow-sm'
                      : 'bg-surface border border-line-strong text-fg-2 hover:text-fg hover:border-amber-400/50'
                  }`}
                >
                  {disc.label}
                </button>
              );
            })}
          </div>

          {/* Lista de Aulas */}
          {lessonsLoading ? (
            <SkeletonRows rows={4} />
          ) : catalogViewMode === 'modulos' ? (
            <div className="space-y-5">
              {groupedByModule.map((grp) => (
                <div
                  key={`${grp.disciplina}-${grp.modulo}`}
                  className="rounded-2xl border border-line-strong bg-surface overflow-hidden shadow-md"
                >
                  <div className="flex items-center justify-between border-b border-line bg-surface-2 px-6 py-4">
                    <div className="flex items-center gap-3">
                      <span className="flex size-10 items-center justify-center rounded-xl bg-amber-400/20 text-amber-300 border border-amber-400/40">
                        <GraduationCap size={20} />
                      </span>
                      <div>
                        <span className="text-xs font-black uppercase tracking-wider text-amber-400">
                          {grp.disciplina}
                        </span>
                        <h3 className="text-base sm:text-lg font-extrabold text-fg">{grp.modulo}</h3>
                      </div>
                    </div>
                    <Badge tone="neutral">{grp.aulas.length} aula(s)</Badge>
                  </div>

                  <div className="divide-y divide-line">
                    {grp.aulas.map((lesson) => {
                      const isDone = completedLessons.includes(lesson.id);
                      const qCount = lesson.questoes_count ?? lesson.total_questoes ?? 0;
                      const vCount = lesson.videoaulas_count ?? 2;
                      const fCount = lesson.flashcards_count ?? 6;
                      return (
                        <div
                          key={lesson.id}
                          onClick={() => handleSelectLesson(lesson.id)}
                          className="group flex flex-col lg:flex-row lg:items-center justify-between gap-4 p-6 cursor-pointer hover:bg-surface-2/60 transition-all"
                        >
                          <div className="space-y-2 max-w-3xl">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="rounded-md bg-amber-400/15 border border-amber-400/40 px-2.5 py-0.5 text-xs font-extrabold text-amber-300">
                                {lesson.nivel || 'Essencial'}
                              </span>
                              <span className="flex items-center gap-1 text-xs font-semibold text-fg-2">
                                <Clock size={13} className="text-amber-400" /> {lesson.tempo_estimado_min || 45} min
                              </span>
                              <span className="flex items-center gap-1 text-xs font-extrabold text-emerald-300">
                                <Zap size={13} /> +{lesson.xp_recompensa || 120} XP
                              </span>
                              {isDone && (
                                <span className="inline-flex items-center gap-1 rounded-md bg-emerald-500/20 px-2.5 py-0.5 text-xs font-bold text-emerald-300">
                                  <CheckCircle2 size={13} /> Concluída
                                </span>
                              )}
                            </div>

                            <h4 className="font-display text-lg font-extrabold text-fg group-hover:text-amber-300 transition-colors">
                              {lesson.titulo}
                            </h4>

                            <p className="text-sm text-fg-2">
                              ✓ {lesson.objetivos[0]}
                            </p>
                          </div>

                          <div className="flex flex-wrap items-center gap-3 shrink-0">
                            <div className="flex items-center gap-2 text-xs font-bold text-fg-2">
                              <span className="rounded-lg border border-line-strong bg-surface-2 px-2.5 py-1.5">
                                {vCount} vídeos
                              </span>
                              <span className="rounded-lg border border-line-strong bg-surface-2 px-2.5 py-1.5">
                                {fCount} flashcards
                              </span>
                              <span className="rounded-lg border border-line-strong bg-surface-2 px-2.5 py-1.5">
                                {qCount} questões
                              </span>
                            </div>

                            <Button variant="primary" size="md" className="gap-1.5 font-extrabold">
                              <span>Entrar na Aula</span>
                              <ChevronRight size={15} />
                            </Button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {filteredLessons.map((lesson) => {
                const qCount = lesson.questoes_count ?? lesson.total_questoes ?? 0;
                return (
                  <div
                    key={lesson.id}
                    onClick={() => handleSelectLesson(lesson.id)}
                    className="group cursor-pointer rounded-2xl border border-line-strong bg-surface p-6 hover:border-amber-400 transition-all flex flex-col justify-between gap-4 shadow-md"
                  >
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <Badge tone="accent">{lesson.disciplina}</Badge>
                        <span className="text-xs font-bold text-fg-2">{qCount} questões</span>
                      </div>
                      <h3 className="font-display text-lg font-extrabold text-fg group-hover:text-amber-300">
                        {lesson.titulo}
                      </h3>
                      <ul className="space-y-1.5">
                        {lesson.objetivos.slice(0, 2).map((obj, idx) => (
                          <li key={idx} className="text-xs text-fg-2 flex items-start gap-2">
                            <CheckCircle2 size={14} className="text-emerald-400 shrink-0 mt-0.5" />
                            <span>{obj}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div className="pt-3 border-t border-line flex items-center justify-between">
                      <span className="text-xs font-bold text-amber-400">Abrir Aula Completa</span>
                      <ChevronRight size={16} className="text-amber-400" />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* ====================================================================
          VISÃO 2: AMBIENTE INTERNO DA AULA (5 ETAPAS CLARAS E ORGANIZADAS)
         ==================================================================== */}
      {activeLessonId && (
        <div className="space-y-6">
          {/* BARRA SUPERIOR DA AULA: VOLTAR + CRONÔMETRO + PROFESSOR VIRTUAL + CONCLUIR */}
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line-strong bg-surface px-5 py-3.5 shadow-md">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleSelectLesson(null)}
              className="gap-2 text-xs font-extrabold"
            >
              <ArrowLeft size={15} /> Voltar para Todas as Aulas
            </Button>

            <div className="flex flex-wrap items-center gap-2.5">
              {/* Cronômetro */}
              <div className="flex items-center gap-2 rounded-xl border border-line-strong bg-surface-2 px-3.5 py-1.5">
                <Clock size={14} className="text-amber-400" />
                <span className="font-mono text-xs font-extrabold tabular text-fg">{clock(studySeconds)}</span>
                <button
                  type="button"
                  onClick={() => setTimerRunning((r) => !r)}
                  className="rounded p-1 text-fg-2 hover:text-fg"
                  title={timerRunning ? 'Pausar' : 'Retomar'}
                >
                  {timerRunning ? <Pause size={13} /> : <Play size={13} />}
                </button>
                <button
                  type="button"
                  onClick={() => setStudySeconds(0)}
                  className="rounded p-1 text-fg-2 hover:text-fg"
                  title="Zerar"
                >
                  <RotateCcw size={12} />
                </button>
              </div>

              {/* Botão Professor Virtual */}
              <button
                type="button"
                onClick={() => setTutorOpen((o) => !o)}
                className={`flex items-center gap-1.5 rounded-xl border px-3.5 py-2 text-xs font-extrabold transition-all ${
                  tutorOpen
                    ? 'border-amber-400 bg-amber-400 text-slate-950'
                    : 'border-amber-400/50 bg-amber-400/15 text-amber-300 hover:bg-amber-400/25'
                }`}
              >
                <Bot size={15} /> Professor Virtual
              </button>

              {/* Marcar como Concluída */}
              {activeLesson && (
                <button
                  type="button"
                  onClick={() => toggleLessonCompletion(activeLesson.id)}
                  className={`flex items-center gap-1.5 rounded-xl border px-3.5 py-2 text-xs font-extrabold transition-all ${
                    completedLessons.includes(activeLesson.id)
                      ? 'border-emerald-500/50 bg-emerald-500/20 text-emerald-300'
                      : 'border-line-strong bg-surface-2 text-fg hover:border-amber-400'
                  }`}
                >
                  <CheckCircle2 size={15} />
                  {completedLessons.includes(activeLesson.id) ? 'Aula Concluída' : 'Marcar Concluída'}
                </button>
              )}
            </div>
          </div>

          {lessonLoading || !activeLesson ? (
            <SkeletonRows rows={6} />
          ) : (
            <>
              {/* GAVETA DO PROFESSOR VIRTUAL */}
              {tutorOpen && activeLesson.tutor_contextual && (
                <div className="rounded-2xl border-2 border-amber-400/50 bg-surface p-6 shadow-xl space-y-4">
                  <div className="flex items-center justify-between border-b border-line pb-3">
                    <div className="flex items-center gap-3">
                      <span className="flex size-10 items-center justify-center rounded-xl bg-amber-400 text-slate-950">
                        <Bot size={20} />
                      </span>
                      <div>
                        <h3 className="text-base font-extrabold text-fg">
                          Professor Virtual · Explicação Direta da Aula
                        </h3>
                        <p className="text-xs text-fg-2">
                          Escolha abaixo como prefere revisar este assunto agora:
                        </p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setTutorOpen(false)}
                      className="rounded-lg p-1.5 text-fg-3 hover:text-fg"
                    >
                      <X size={18} />
                    </button>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {(
                      [
                        { key: 'explicar_simples', label: '1. Explicar de Forma Simples' },
                        { key: 'exemplo_pratico', label: '2. Dar Exemplo de Prova' },
                        { key: 'comparar_conceitos', label: '3. Comparar Conceitos' },
                        { key: 'resumo_1_minuto', label: '4. Resumo de 1 Minuto' },
                      ] as const
                    ).map((m) => (
                      <button
                        key={m.key}
                        type="button"
                        onClick={() => {
                          setActiveTutorMode(m.key);
                          setTutorCustomFeedback(null);
                        }}
                        className={`rounded-xl px-4 py-2 text-xs font-extrabold transition-all ${
                          activeTutorMode === m.key
                            ? 'bg-amber-400 text-slate-950'
                            : 'border border-line-strong bg-surface-2 text-fg-2 hover:text-fg'
                        }`}
                      >
                        {m.label}
                      </button>
                    ))}
                  </div>

                  <div className="rounded-xl border border-line-strong bg-surface-2 p-4 text-sm text-fg leading-relaxed whitespace-pre-line">
                    {activeLesson.tutor_contextual[activeTutorMode]}
                  </div>

                  {tutorCustomFeedback && (
                    <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/15 px-4 py-2.5 text-xs font-bold text-emerald-300">
                      {tutorCustomFeedback}
                    </div>
                  )}
                </div>
              )}

              {/* CABEÇALHO LIMPO DA AULA */}
              <div className="rounded-2xl border border-line-strong bg-surface p-6 shadow-md space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-md bg-amber-400 px-2.5 py-1 text-xs font-black uppercase tracking-wider text-slate-950">
                    {activeLesson.disciplina}
                  </span>
                  <span className="rounded-md border border-line-strong bg-surface-2 px-2.5 py-1 text-xs font-bold text-fg-2">
                    {activeLesson.modulo || 'Módulo Principal'}
                  </span>
                  <span className="rounded-md border border-line-strong bg-surface-2 px-2.5 py-1 text-xs font-bold text-fg-2">
                    ⏱ {activeLesson.tempo_estimado_min || 45} min
                  </span>
                </div>

                <h1 className="font-display text-2xl sm:text-3xl font-extrabold text-fg leading-tight">
                  {activeLesson.titulo}
                </h1>

                {/* Objetivos em linha horizontal clara */}
                <div className="grid gap-2.5 sm:grid-cols-3 pt-1">
                  {activeLesson.objetivos.map((obj, idx) => (
                    <div
                      key={idx}
                      className="flex items-start gap-2.5 rounded-xl border border-line-strong bg-surface-2/70 p-3"
                    >
                      <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-amber-400/20 text-xs font-black text-amber-300">
                        {idx + 1}
                      </span>
                      <span className="text-xs font-medium text-fg leading-relaxed">{obj}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* BARRA DE NAVEGAÇÃO DAS 5 ETAPAS DA AULA (SEM CORTAR TEXTO!) */}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 rounded-2xl border border-line-strong bg-surface-2 p-2 shadow-sm">
                <button
                  type="button"
                  onClick={() => setActiveTab('resumo')}
                  className={`flex items-center justify-center gap-2 rounded-xl px-3 py-3 text-xs font-extrabold transition-all ${
                    activeTab === 'resumo'
                      ? 'bg-amber-400 text-slate-950 shadow-sm'
                      : 'bg-surface text-fg-2 hover:text-fg'
                  }`}
                >
                  <BookOpen size={15} />
                  <span>1. Resumo & Teoria</span>
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab('visual')}
                  className={`flex items-center justify-center gap-2 rounded-xl px-3 py-3 text-xs font-extrabold transition-all ${
                    activeTab === 'visual'
                      ? 'bg-amber-400 text-slate-950 shadow-sm'
                      : 'bg-surface text-fg-2 hover:text-fg'
                  }`}
                >
                  <Network size={15} />
                  <span>2. Quadro Digital & Mapa Mental</span>
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab('video')}
                  className={`flex items-center justify-center gap-2 rounded-xl px-3 py-3 text-xs font-extrabold transition-all ${
                    activeTab === 'video'
                      ? 'bg-amber-400 text-slate-950 shadow-sm'
                      : 'bg-surface text-fg-2 hover:text-fg'
                  }`}
                >
                  <Video size={15} />
                  <span>3. Videoaula Recomendada ({(activeLesson.videoaulas ?? []).length})</span>
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab('flashcards')}
                  className={`flex items-center justify-center gap-2 rounded-xl px-3 py-3 text-xs font-extrabold transition-all ${
                    activeTab === 'flashcards'
                      ? 'bg-amber-400 text-slate-950 shadow-sm'
                      : 'bg-surface text-fg-2 hover:text-fg'
                  }`}
                >
                  <Layers size={15} />
                  <span>4. Flashcards Visuais ({(activeLesson.flashcards ?? []).length})</span>
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab('questoes')}
                  className={`flex items-center justify-center gap-2 rounded-xl px-3 py-3 text-xs font-extrabold transition-all ${
                    activeTab === 'questoes'
                      ? 'bg-amber-400 text-slate-950 shadow-sm'
                      : 'bg-surface text-fg-2 hover:text-fg'
                  }`}
                >
                  <Target size={15} />
                  <span>5. Questões & Avaliação de Domínio ({activeLessonQuestions.length})</span>
                </button>
              </div>

              {/* ================================================================
                  ETAPA 1: RESUMO & TEORIA ESQUEMATIZADA (COM TÍTULOS CLAROS!)
                 ================================================================ */}
              {activeTab === 'resumo' && (
                <div className="space-y-6">
                  {/* Banner de Orientação da Etapa 1 */}
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border-l-4 border-l-amber-400 border border-line-strong bg-surface p-5">
                    <div>
                      <span className="text-xs font-black uppercase tracking-widest text-amber-400">
                        ETAPA 1 DE 5 · BASE TEÓRICA ESQUEMATIZADA
                      </span>
                      <h2 className="mt-1 font-display text-xl font-extrabold text-fg">
                        O que você precisa saber antes de ir para os exercícios
                      </h2>
                    </div>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => setActiveTab('visual')}
                      className="gap-1.5 font-extrabold"
                    >
                      <span>Ir para Etapa 2: Quadro Digital</span>
                      <ArrowRight size={14} />
                    </Button>
                  </div>

                  {/* Blocos Teóricos Numerados (Fim do "Muro de Texto") */}
                  <div className="grid gap-4 md:grid-cols-2">
                    {parseStructuredTheory(
                      activeLesson.teoria_resumida ||
                        (activeLesson as unknown as { conteudo_resumo?: string }).conteudo_resumo ||
                        ''
                    ).map((block, idx) => (
                      <div
                        key={idx}
                        className="rounded-2xl border border-line-strong bg-surface p-6 shadow-sm space-y-3"
                      >
                        <div className="flex items-center gap-3">
                          <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-amber-400 text-sm font-black text-slate-950">
                            0{idx + 1}
                          </span>
                          <h3 className="font-display text-base sm:text-lg font-extrabold text-fg">
                            {block.title}
                          </h3>
                        </div>
                        <p className="text-sm text-fg leading-relaxed whitespace-pre-line">
                          {block.body}
                        </p>
                      </div>
                    ))}
                  </div>

                  {/* TABELA COMPARATIVA DE MEMORIZAÇÃO */}
                  {activeLesson.tabela_resumo && (
                    <div className="rounded-2xl border border-line-strong bg-surface overflow-hidden shadow-md">
                      <div className="border-b border-line bg-surface-2 px-6 py-4">
                        <span className="text-xs font-black uppercase tracking-wider text-amber-400">
                          TABELA DE COMPARAÇÃO RÁPIDA
                        </span>
                        <h3 className="mt-0.5 font-display text-lg font-extrabold text-fg">
                          {activeLesson.tabela_resumo.titulo}
                        </h3>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse">
                          <thead>
                            <tr className="border-b-2 border-line bg-surface-2/60">
                              {activeLesson.tabela_resumo.colunas.map((col, idx) => (
                                <th
                                  key={idx}
                                  className="px-5 py-3.5 text-xs font-extrabold uppercase tracking-wider text-amber-300"
                                >
                                  {col}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-line">
                            {activeLesson.tabela_resumo.linhas.map((row, rIdx) => (
                              <tr key={rIdx} className="hover:bg-surface-2/40">
                                {row.map((cell, cIdx) => (
                                  <td
                                    key={cIdx}
                                  className={`px-5 py-3.5 text-sm leading-relaxed ${
                                      cIdx === 0 ? 'font-extrabold text-amber-300' : 'text-fg'
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
                    </div>
                  )}

                  {/* PEGADINHAS DE PROVA E COMO AS BANCAS COBRAM */}
                  <div className="grid gap-5 lg:grid-cols-2">
                    <div className="rounded-2xl border-2 border-rose-500/30 bg-surface p-6 space-y-4">
                      <div className="flex items-center gap-2.5">
                        <span className="flex size-8 items-center justify-center rounded-lg bg-rose-500/20 text-rose-400">
                          <Flame size={18} />
                        </span>
                        <div>
                          <span className="text-xs font-black uppercase tracking-wider text-rose-400">
                            CUIDADO NA PROVA
                          </span>
                          <h3 className="font-display text-lg font-extrabold text-fg">
                            3 Pegadinhas Clássicas deste Assunto
                          </h3>
                        </div>
                      </div>
                      <ul className="space-y-3">
                        {activeLesson.pontos_criticos.map((ponto, idx) => (
                          <li
                            key={idx}
                            className="flex items-start gap-3 rounded-xl border border-rose-500/25 bg-rose-500/10 p-3.5 text-sm text-fg leading-relaxed"
                          >
                            <AlertCircle size={16} className="text-rose-400 shrink-0 mt-0.5" />
                            <span>{ponto}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="rounded-2xl border border-line-strong bg-surface p-6 space-y-4">
                      <div className="flex items-center gap-2.5">
                        <span className="flex size-8 items-center justify-center rounded-lg bg-amber-400/20 text-amber-300">
                          <Award size={18} />
                        </span>
                        <div>
                          <span className="text-xs font-black uppercase tracking-wider text-amber-400">
                            RAIO-X DAS BANCAS
                          </span>
                          <h3 className="font-display text-lg font-extrabold text-fg">
                            Como FGV, Cebraspe e Quadrix Cobram
                          </h3>
                        </div>
                      </div>
                      <div className="space-y-3">
                        {Object.entries(
                          activeLesson.radiografia_bancas ??
                            (activeLesson as unknown as { bancas_destaque?: Record<string, string> })
                              .bancas_destaque ??
                            {}
                        ).map(([banca, analise]) => (
                          <div
                            key={banca}
                            className="rounded-xl border border-line-strong bg-surface-2 p-3.5 space-y-1"
                          >
                            <span className="inline-block rounded bg-amber-400/20 px-2 py-0.5 text-xs font-black uppercase text-amber-300">
                              Banca {banca.toUpperCase()}
                            </span>
                            <p className="text-sm text-fg leading-relaxed">{analise}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* ================================================================
                  ETAPA 2: QUADRO DIGITAL & MAPA MENTAL (SEM REPETIÇÃO DE TEXTO!)
                 ================================================================ */}
              {activeTab === 'visual' && (
                <div className="space-y-6">
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border-l-4 border-l-sky-400 border border-line-strong bg-surface p-5">
                    <div>
                      <span className="text-xs font-black uppercase tracking-widest text-sky-400">
                        ETAPA 2 DE 5 · ESQUEMA VISUAL & MAPA INTERATIVO
                      </span>
                      <h2 className="mt-1 font-display text-xl font-extrabold text-fg">
                        {activeLesson.quadro_visual?.titulo || 'Quadro Digital Esquematizado'}
                      </h2>
                    </div>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => setActiveTab('video')}
                      className="gap-1.5 font-extrabold"
                    >
                      <span>Ir para Etapa 3: Videoaula</span>
                      <ArrowRight size={14} />
                    </Button>
                  </div>

                  {/* CARTÕES LIMPOS DO QUADRO DIGITAL (1 TÍTULO + PÍLULAS + 1 REGRA + 1 EXEMPLO) */}
                  {activeLesson.quadro_visual && (
                    <div className="grid gap-5 lg:grid-cols-3">
                      {activeLesson.quadro_visual.relacoes_conceituais.map((rel, rIdx) => (
                        <div
                          key={rel.id}
                          className="flex flex-col justify-between rounded-2xl border-2 border-line-strong bg-surface p-5 shadow-md space-y-4"
                        >
                          <div className="space-y-3">
                            <div className="flex items-center justify-between">
                              <span className="rounded-lg bg-amber-400 px-3 py-1 text-xs font-black uppercase tracking-wider text-slate-950">
                                {rel.categoria}
                              </span>
                              <span className="text-xs font-extrabold text-fg-3">Bloco #{rIdx + 1}</span>
                            </div>

                            {/* Pílulas de palavras-chave */}
                            <div className="flex flex-wrap gap-1.5 pt-1">
                              {rel.conectivos.map((c) => (
                                <span
                                  key={c}
                                  className="rounded-lg border border-amber-400/40 bg-amber-400/10 px-2.5 py-1 text-xs font-bold text-amber-200"
                                >
                                  {c}
                                </span>
                              ))}
                            </div>

                            {/* Regra Central (1 frase clara, sem repetir!) */}
                            <div className="rounded-xl border border-line-strong bg-surface-2 p-3.5">
                              <span className="block text-[10px] font-black uppercase tracking-wider text-sky-300 mb-1">
                                DEFINIÇÃO DIRETA
                              </span>
                              <p className="text-sm font-bold text-fg leading-relaxed">
                                {rel.regra_ouro}
                              </p>
                            </div>
                          </div>

                          {/* Caso de Prova */}
                          <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3.5">
                            <span className="block text-[10px] font-black uppercase tracking-wider text-emerald-300 mb-1">
                              COMO CAI NA PROVA
                            </span>
                            <p className="text-xs font-medium text-fg leading-relaxed">
                              {rel.exemplo_destacado}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* PASSO A PASSO INTERATIVO */}
                  {activeLesson.quadro_visual?.passos_animados &&
                    activeLesson.quadro_visual.passos_animados.length > 0 && (
                      <div className="rounded-2xl border border-line-strong bg-surface p-6 space-y-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div>
                            <span className="text-xs font-black uppercase tracking-wider text-amber-400">
                              RACIOCÍNIO PASSO A PASSO
                            </span>
                            <h3 className="font-display text-lg font-extrabold text-fg">
                              Como resolver qualquer questão deste tema em 3 passos
                            </h3>
                          </div>
                          <div className="flex items-center gap-1.5">
                            {activeLesson.quadro_visual.passos_animados.map((st, idx) => (
                              <button
                                key={st.passo}
                                type="button"
                                onClick={() => setActiveVisualStep(idx)}
                                className={`rounded-xl px-3.5 py-2 text-xs font-extrabold transition-all ${
                                  activeVisualStep === idx
                                    ? 'bg-amber-400 text-slate-950'
                                    : 'border border-line-strong bg-surface-2 text-fg-2 hover:text-fg'
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
                            <div className="rounded-xl border border-amber-400/40 bg-surface-2 p-5 space-y-3">
                              <h4 className="font-display text-base sm:text-lg font-extrabold text-amber-300">
                                {step.titulo}
                              </h4>
                              <p className="text-sm text-fg leading-relaxed">{step.detalhe}</p>
                              <div className="rounded-lg border border-line-strong bg-surface p-3 font-mono text-xs font-bold text-emerald-300">
                                {step.destaque_codigo}
                              </div>
                            </div>
                          );
                        })()}
                      </div>
                    )}

                  {/* MAPA MENTAL CLICÁVEL */}
                  {activeLesson.mapa_mental && (
                    <div className="rounded-2xl border border-line-strong bg-surface p-6 space-y-4">
                      <div>
                        <span className="text-xs font-black uppercase tracking-wider text-sky-400">
                          MAPA MENTAL INTERATIVO
                        </span>
                        <h3 className="font-display text-lg font-extrabold text-fg">
                          Clique em qualquer ramo abaixo para expandir os detalhes
                        </h3>
                      </div>

                      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                        {activeLesson.mapa_mental.nos.map((node) => {
                          const isSelected = selectedMindMapNodeId === node.id;
                          return (
                            <button
                              key={node.id}
                              type="button"
                              onClick={() => setSelectedMindMapNodeId(isSelected ? null : node.id)}
                              className={`text-left rounded-xl border-2 p-4 transition-all ${
                                isSelected
                                  ? 'border-amber-400 bg-amber-400/10'
                                  : 'border-line-strong bg-surface-2 hover:border-amber-400/50'
                              }`}
                            >
                              <span className="text-xs font-black uppercase text-amber-400 block">
                                {node.titulo}
                              </span>
                              <p className="mt-1 text-xs text-fg-2 line-clamp-2">{node.descricao}</p>
                            </button>
                          );
                        })}
                      </div>

                      {(() => {
                        const activeNode =
                          activeLesson.mapa_mental.nos.find((n) => n.id === selectedMindMapNodeId) ??
                          activeLesson.mapa_mental.nos[0];
                        if (!activeNode) return null;
                        return (
                          <div className="rounded-xl border border-line-strong bg-surface-2 p-5 grid gap-4 md:grid-cols-3">
                            <div>
                              <span className="text-[11px] font-black uppercase text-amber-400">
                                CONCEITO SELECIONADO
                              </span>
                              <h4 className="mt-1 font-display text-base font-extrabold text-fg">
                                {activeNode.titulo}
                              </h4>
                              <p className="mt-1 text-xs text-fg-2 leading-relaxed">{activeNode.descricao}</p>
                            </div>
                            <div>
                              <span className="text-[11px] font-black uppercase text-emerald-400">
                                APLICAÇÃO PRÁTICA
                              </span>
                              <p className="mt-1 text-xs text-fg leading-relaxed">{activeNode.exemplo}</p>
                            </div>
                            <div>
                              <span className="text-[11px] font-black uppercase text-rose-400">
                                DICA DE BANCA
                              </span>
                              <p className="mt-1 text-xs text-fg leading-relaxed">{activeNode.dica_banca}</p>
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                  )}
                </div>
              )}

              {/* ================================================================
                  ETAPA 3: VIDEOAULA RECOMENDADA (100% VERIFICADA E FUNCIONAL!)
                 ================================================================ */}
              {activeTab === 'video' && (
                <div className="space-y-6">
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border-l-4 border-l-amber-400 border border-line-strong bg-surface p-5">
                    <div>
                      <span className="text-xs font-black uppercase tracking-widest text-amber-400">
                        ETAPA 3 DE 5 · VIDEOAULAS VERIFICADAS & SLIDES GUIADOS
                      </span>
                      <h2 className="mt-1 font-display text-xl font-extrabold text-fg">
                        Assista à aula em vídeo ou navegue pelos slides esquematizados
                      </h2>
                    </div>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => setActiveTab('flashcards')}
                      className="gap-1.5 font-extrabold"
                    >
                      <span>Ir para Etapa 4: Flashcards Visuais</span>
                      <ArrowRight size={14} />
                    </Button>
                  </div>

                  {(() => {
                    const videos = activeLesson.videoaulas ?? [];
                    const currentVideo = videos[selectedVideoIndex] ?? videos[0];
                    if (!currentVideo) return null;

                    const chapters = currentVideo.capitulos ?? [];
                    const slides = currentVideo.slides_guiados ?? [];
                    const currentSlide = slides[activeSlideIdx] ?? slides[0];
                    const checkpoints = currentVideo.perguntas_video ?? [];
                    const currentNotes = lessonNotes[activeLesson.id] ?? [];

                    return (
                      <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
                        <div className="space-y-4">
                          <div className="overflow-hidden rounded-2xl border-2 border-line-strong bg-surface shadow-lg">
                            {/* Seletor Player de Vídeo vs Apresentação de Slides */}
                            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-surface-2 px-4 py-3">
                              <div className="flex items-center gap-2">
                                <button
                                  type="button"
                                  onClick={() => setVideoPresentationMode('video')}
                                  className={`flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-extrabold transition-all ${
                                    videoPresentationMode === 'video'
                                      ? 'bg-amber-400 text-slate-950'
                                      : 'text-fg-2 hover:text-fg'
                                  }`}
                                >
                                  <Video size={14} /> Player de Vídeo (YouTube)
                                </button>
                                <button
                                  type="button"
                                  onClick={() => setVideoPresentationMode('slides')}
                                  className={`flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-extrabold transition-all ${
                                    videoPresentationMode === 'slides'
                                      ? 'bg-amber-400 text-slate-950'
                                      : 'text-fg-2 hover:text-fg'
                                  }`}
                                >
                                  <Sparkles size={14} /> Slides da Aula ({slides.length})
                                </button>
                              </div>

                              <a
                                href={`https://www.youtube.com/watch?v=${currentVideo.youtube_id}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1.5 rounded-lg border border-line-strong bg-surface px-3 py-1.5 text-xs font-bold text-amber-300 hover:border-amber-400"
                              >
                                <span>Abrir no YouTube</span>
                                <ExternalLink size={12} />
                              </a>
                            </div>

                            {/* Área de Exibição */}
                            {videoPresentationMode === 'video' ? (
                              <div className="relative aspect-video w-full bg-black">
                                <iframe
                                  key={`${currentVideo.youtube_id}-${videoStartSec}`}
                                  className="w-full h-full"
                                  src={`https://www.youtube.com/embed/${currentVideo.youtube_id}?rel=0&modestbranding=1${
                                    videoStartSec > 0 ? `&start=${videoStartSec}&autoplay=1` : ''
                                  }`}
                                  title={currentVideo.titulo}
                                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                  allowFullScreen
                                />
                              </div>
                            ) : (
                              <div className="aspect-video w-full bg-surface p-8 flex flex-col justify-between">
                                <div className="flex items-center justify-between">
                                  <span className="rounded-md bg-amber-400 px-3 py-1 text-xs font-black uppercase text-slate-950">
                                    {currentSlide?.tag || 'SLIDE DIDÁTICO'}
                                  </span>
                                  <span className="text-xs font-bold text-fg-2">
                                    Slide {activeSlideIdx + 1} de {slides.length}
                                  </span>
                                </div>

                                <div className="my-auto space-y-4">
                                  <h3 className="font-display text-2xl font-extrabold text-fg">
                                    {currentSlide?.titulo}
                                  </h3>
                                  <p className="text-base text-fg-2 leading-relaxed">
                                    {currentSlide?.conteudo}
                                  </p>
                                  {currentSlide?.destaque && (
                                    <div className="rounded-xl border border-amber-400/40 bg-amber-400/10 p-4 text-sm font-bold text-amber-200">
                                      💡 {currentSlide.destaque}
                                    </div>
                                  )}
                                </div>

                                <div className="flex items-center justify-between pt-4 border-t border-line">
                                  <Button
                                    variant="secondary"
                                    size="sm"
                                    disabled={activeSlideIdx === 0}
                                    onClick={() => setActiveSlideIdx((i) => Math.max(0, i - 1))}
                                  >
                                    <ArrowLeft size={14} /> Anterior
                                  </Button>
                                  <Button
                                    variant="primary"
                                    size="sm"
                                    disabled={activeSlideIdx >= slides.length - 1}
                                    onClick={() =>
                                      setActiveSlideIdx((i) => Math.min(slides.length - 1, i + 1))
                                    }
                                  >
                                    Próximo Slide <ArrowRight size={14} />
                                  </Button>
                                </div>
                              </div>
                            )}

                            {/* Rodapé do Player */}
                            <div className="p-4 bg-surface-2 border-t border-line">
                              <h4 className="font-display text-base font-extrabold text-fg">
                                {currentVideo.titulo}
                              </h4>
                              <p className="text-xs text-fg-2 mt-0.5">
                                Canal: <strong>{currentVideo.canal}</strong> · Duração: {currentVideo.duracao}
                              </p>
                            </div>
                          </div>

                          {/* Pergunta Rápida sobre a Videoaula */}
                          {checkpoints.map((cp) => {
                            const ans = checkpointAnswers[cp.id];
                            const answered = ans !== undefined;
                            return (
                              <div
                                key={cp.id}
                                className="rounded-2xl border border-line-strong bg-surface p-5 space-y-3"
                              >
                                <span className="text-xs font-black uppercase tracking-wider text-amber-400">
                                  PERGUNTA DE FIXAÇÃO DO VÍDEO ({cp.momento_label})
                                </span>
                                <p className="text-sm font-bold text-fg">{cp.pergunta}</p>
                                <div className="grid gap-2 sm:grid-cols-2">
                                  {cp.alternativas.map((alt, aIdx) => {
                                    const isCorr = aIdx === cp.correta_idx;
                                    const isSel = ans === aIdx;
                                    return (
                                      <button
                                        key={aIdx}
                                        type="button"
                                        disabled={answered}
                                        onClick={() =>
                                          setCheckpointAnswers((prev) => ({ ...prev, [cp.id]: aIdx }))
                                        }
                                        className={`text-left rounded-xl border p-3 text-xs font-medium transition-all ${
                                          !answered
                                            ? 'border-line-strong bg-surface-2 hover:border-amber-400 text-fg'
                                            : isCorr
                                            ? 'border-emerald-500/50 bg-emerald-500/15 text-emerald-200 font-bold'
                                            : isSel
                                            ? 'border-rose-500/50 bg-rose-500/15 text-rose-200'
                                            : 'border-line bg-surface-2/40 text-fg-3'
                                        }`}
                                      >
                                        {alt}
                                      </button>
                                    );
                                  })}
                                </div>
                              </div>
                            );
                          })}
                        </div>

                        {/* COLUNA LATERAL: SELEÇÃO DE VÍDEO + CAPÍTULOS + NOTAS */}
                        <div className="space-y-4">
                          <div className="rounded-2xl border border-line-strong bg-surface p-5 space-y-3">
                            <h4 className="font-display text-base font-extrabold text-fg">
                              Vídeos & Capítulos desta Aula
                            </h4>
                            <div className="space-y-2.5">
                              {videos.map((vid, idx) => {
                                const isSel = idx === selectedVideoIndex;
                                return (
                                  <div key={idx} className="space-y-2">
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setSelectedVideoIndex(idx);
                                        setVideoStartSec(0);
                                      }}
                                      className={`w-full text-left rounded-xl border p-3.5 transition-all ${
                                        isSel
                                          ? 'border-amber-400 bg-amber-400/15'
                                          : 'border-line-strong bg-surface-2 hover:border-amber-400/40'
                                      }`}
                                    >
                                      <div className="flex items-center gap-2.5">
                                        <span
                                          className={`flex size-7 shrink-0 items-center justify-center rounded-lg text-xs font-black ${
                                            isSel
                                              ? 'bg-amber-400 text-slate-950'
                                              : 'bg-surface text-fg-2'
                                          }`}
                                        >
                                          {idx + 1}
                                        </span>
                                        <div className="min-w-0">
                                          <p className="text-xs font-extrabold text-fg truncate">
                                            {vid.titulo}
                                          </p>
                                          <p className="text-[11px] text-fg-2">
                                            {vid.canal} · {vid.duracao}
                                          </p>
                                        </div>
                                      </div>
                                    </button>

                                    {isSel && chapters.length > 0 && (
                                      <div className="pl-3 border-l-2 border-amber-400/40 space-y-1.5">
                                        {chapters.map((cap) => (
                                          <button
                                            key={cap.id}
                                            type="button"
                                            onClick={() => handleJumpToChapter(cap.id, cap.tempo_seg)}
                                            className={`w-full text-left rounded-lg border px-3 py-2 text-xs transition-all flex items-center justify-between ${
                                              activeChapterId === cap.id
                                                ? 'border-amber-400 bg-amber-400/10 text-fg font-bold'
                                                : 'border-line bg-surface-2/60 text-fg-2 hover:text-fg'
                                            }`}
                                          >
                                            <span className="truncate">{cap.titulo}</span>
                                            <span className="font-mono text-[11px] text-amber-400 shrink-0 ml-2">
                                              {cap.tempo_label}
                                            </span>
                                          </button>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>

                          {/* Bloco de Anotações da Aula */}
                          <div className="rounded-2xl border border-line-strong bg-surface p-5 space-y-3">
                            <h4 className="font-display text-base font-extrabold text-fg">
                              Suas Anotações nesta Aula
                            </h4>
                            <div className="flex gap-2">
                              <input
                                type="text"
                                value={noteInput}
                                onChange={(e) => setNoteInput(e.target.value)}
                                placeholder="Anotar ponto importante..."
                                className="flex-1 rounded-xl border border-line-strong bg-surface-2 px-3 py-2 text-xs text-fg"
                              />
                              <Button
                                variant="primary"
                                size="sm"
                                onClick={() => handleAddVideoNote('Nota da Aula', '00:00', videoStartSec)}
                              >
                                Salvar
                              </Button>
                            </div>
                            {currentNotes.length > 0 && (
                              <div className="space-y-2 pt-1">
                                {currentNotes.map((n) => (
                                  <div
                                    key={n.id}
                                    className="rounded-xl border border-line bg-surface-2 p-3 text-xs text-fg"
                                  >
                                    {n.text}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })()}
                </div>
              )}

              {/* ================================================================
                  ETAPA 4: FLASHCARDS VISUAIS ESTILO JOTTA
                 ================================================================ */}
              {activeTab === 'flashcards' && (
                <div className="space-y-6">
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border-l-4 border-l-amber-400 border border-line-strong bg-surface p-5">
                    <div>
                      <span className="text-xs font-black uppercase tracking-widest text-amber-400">
                        ETAPA 4 DE 5 · FLASHCARDS VISUAIS ESQUEMATIZADOS
                      </span>
                      <h2 className="mt-1 font-display text-xl font-extrabold text-fg">
                        Fichas de Memorização Visual da Aula
                      </h2>
                    </div>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => setActiveTab('questoes')}
                      className="gap-1.5 font-extrabold"
                    >
                      <span>Ir para Etapa 5: Questões & Domínio</span>
                      <ArrowRight size={14} />
                    </Button>
                  </div>

                  <JottaFlashcardGrid
                    cards={activeLesson.flashcards ?? []}
                    savedFlashcards={savedFlashcards}
                    favoriteFlashcards={favoriteFlashcards}
                    cardDifficultyRatings={cardDifficultyRatings}
                    onSaveCard={(fc, rating) => void handleSaveFlashcard(fc, rating)}
                    onToggleFavorite={toggleFavoriteCard}
                  />
                </div>
              )}

              {/* ================================================================
                  ETAPA 5: QUESTÕES DE PROVA & AVALIAÇÃO DE DOMÍNIO INTEGRADA
                 ================================================================ */}
              {activeTab === 'questoes' && (
                <div className="space-y-6">
                  {/* Painel Integrado de Domínio da Aula (Nunca mais fica vazio sem questões!) */}
                  <div className="rounded-2xl border-2 border-amber-400/40 bg-surface p-6 shadow-md">
                    <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                      <div>
                        <span className="text-xs font-black uppercase tracking-widest text-amber-400">
                          ETAPA 5 DE 5 · PRÁTICA DE PROVA & DOMÍNIO DA AULA
                        </span>
                        <h2 className="mt-1 font-display text-xl font-extrabold text-fg">
                          Resolva as questões abaixo para medir seu domínio real
                        </h2>
                      </div>

                      <div className="flex flex-wrap items-center gap-3">
                        <div className="rounded-xl border border-line-strong bg-surface-2 px-4 py-2.5 text-center">
                          <span className="text-[10px] font-bold uppercase text-fg-3 block">Respondidas</span>
                          <span className="font-display text-lg font-black text-fg tabular">
                            {masteryStats.answered}/{masteryStats.total}
                          </span>
                        </div>
                        <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-2.5 text-center">
                          <span className="text-[10px] font-bold uppercase text-emerald-300 block">Acertos</span>
                          <span className="font-display text-lg font-black text-emerald-300 tabular">
                            {masteryStats.correct}
                          </span>
                        </div>
                        <div className="rounded-xl border border-amber-400/40 bg-amber-400/10 px-4 py-2.5 text-center">
                          <span className="text-[10px] font-bold uppercase text-amber-300 block">Domínio</span>
                          <span className="font-display text-lg font-black text-amber-300 tabular">
                            {masteryStats.pct}%
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* EXERCÍCIOS RÁPIDOS DE FIXAÇÃO */}
                  {activeLesson.exercicios_interativos &&
                    activeLesson.exercicios_interativos.length > 0 && (
                      <div className="grid gap-4 lg:grid-cols-2">
                        {activeLesson.exercicios_interativos.map((ex) => {
                          const revealed = Boolean(labExerciseRevealed[ex.id]);
                          const selected = labExerciseState[ex.id];
                          return (
                            <div
                              key={ex.id}
                              className="rounded-2xl border border-line-strong bg-surface p-5 space-y-3"
                            >
                              <span className="rounded bg-sky-500/20 px-2.5 py-1 text-[11px] font-black uppercase text-sky-300">
                                Aquecimento Rápido
                              </span>
                              <h4 className="font-display text-base font-extrabold text-fg">{ex.titulo}</h4>
                              <p className="text-xs text-fg-2 leading-relaxed">{ex.enunciado}</p>

                              {ex.tipo === 'complete_lacuna' && ex.opcoes && (
                                <div className="flex flex-wrap gap-2 pt-1">
                                  {ex.opcoes.map((op) => (
                                    <button
                                      key={op}
                                      type="button"
                                      onClick={() => {
                                        setLabExerciseState((prev) => ({ ...prev, [ex.id]: op }));
                                        setLabExerciseRevealed((prev) => ({ ...prev, [ex.id]: true }));
                                      }}
                                      className={`rounded-xl border px-3.5 py-2 text-xs font-extrabold transition-all ${
                                        selected === op
                                          ? op === ex.resposta_correta
                                            ? 'border-emerald-500 bg-emerald-500/20 text-emerald-300'
                                            : 'border-rose-500 bg-rose-500/20 text-rose-300'
                                          : 'border-line-strong bg-surface-2 text-fg hover:border-amber-400'
                                      }`}
                                    >
                                      {op}
                                    </button>
                                  ))}
                                </div>
                              )}

                              {ex.tipo === 'associacao_conceitos' && ex.pares && (
                                <div className="space-y-2">
                                  {ex.pares.map((p) => (
                                    <div
                                      key={p.id}
                                      className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 rounded-xl border border-line bg-surface-2 px-3.5 py-2 text-xs"
                                    >
                                      <span className="font-extrabold text-amber-300">{p.conceito}</span>
                                      <span className="text-fg">{p.definicao}</span>
                                    </div>
                                  ))}
                                </div>
                              )}

                              {revealed && (
                                <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-fg">
                                  ✓ {ex.explicacao}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}

                  {/* QUESTÕES OFICIAIS DE PROVA COMENTADAS */}
                  <div className="space-y-5">
                    {activeLessonQuestions.map((q, idx) => {
                      const chosen = selectedAnswers[q.id];
                      const isRevealed = Boolean(revealedQuestions[q.id]);
                      const isCorrect = chosen === q.gabarito;
                      const options = q.alternativas_formatadas ?? [];

                      return (
                        <div
                          key={q.id}
                          className="rounded-2xl border-2 border-line-strong bg-surface p-6 shadow-md space-y-4"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-3">
                            <div className="flex items-center gap-2">
                              <span className="flex size-8 items-center justify-center rounded-lg bg-amber-400 text-xs font-black text-slate-950">
                                Q{idx + 1}
                              </span>
                              <span className="rounded-md bg-surface-2 border border-line-strong px-2.5 py-1 text-xs font-extrabold text-amber-300">
                                {q.banca_sigla || 'PROVA OFICIAL'}
                              </span>
                              <span className="text-xs font-bold text-fg-2">{q.fonte}</span>
                            </div>

                            {isRevealed && (
                              <span
                                className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1 text-xs font-extrabold ${
                                  isCorrect
                                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                                    : 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                                }`}
                              >
                                {isCorrect ? (
                                  <>
                                    <CheckCircle2 size={14} /> Você Acertou!
                                  </>
                                ) : (
                                  <>
                                    <XCircle size={14} /> Gabarito Oficial: {q.gabarito}
                                  </>
                                )}
                              </span>
                            )}
                          </div>

                          <p className="text-base font-medium text-fg leading-relaxed">{q.enunciado}</p>

                          <div className="space-y-2.5">
                            {options.map((opt) => {
                              const isChosen = chosen === opt.letra;
                              let cls = 'border-line-strong bg-surface-2 hover:border-amber-400 text-fg';
                              if (isRevealed) {
                                if (opt.correta) {
                                  cls = 'border-emerald-500 bg-emerald-500/15 text-fg font-bold';
                                } else if (isChosen) {
                                  cls = 'border-rose-500 bg-rose-500/15 text-rose-200';
                                } else {
                                  cls = 'border-line bg-surface-2/40 text-fg-3';
                                }
                              }
                              return (
                                <button
                                  key={opt.letra}
                                  type="button"
                                  disabled={isRevealed}
                                  onClick={() => handleSelectOption(q.id, opt.letra)}
                                  className={`w-full text-left rounded-xl border-2 p-4 transition-all flex items-start gap-3 ${cls}`}
                                >
                                  <span
                                    className={`flex size-7 shrink-0 items-center justify-center rounded-lg text-xs font-black ${
                                      isRevealed && opt.correta
                                        ? 'bg-emerald-400 text-slate-950'
                                        : isRevealed && isChosen
                                        ? 'bg-rose-400 text-slate-950'
                                        : 'bg-surface border border-line-strong text-fg'
                                    }`}
                                  >
                                    {opt.letra}
                                  </span>
                                  <span className="text-sm leading-relaxed">{opt.texto}</span>
                                </button>
                              );
                            })}
                          </div>

                          {isRevealed && (
                            <div className="rounded-xl border-2 border-amber-400/40 bg-amber-400/10 p-5 space-y-3">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="text-xs font-black uppercase tracking-wider text-amber-300">
                                  COMENTÁRIO DO PROFESSOR (GABARITO: {q.gabarito})
                                </span>
                                <Button
                                  variant="secondary"
                                  size="sm"
                                  disabled={Boolean(questionConvertedToCard[q.id])}
                                  onClick={() => void handleConvertQuestionToFlashcard(q)}
                                  className="gap-1.5 text-xs font-bold"
                                >
                                  {questionConvertedToCard[q.id] ? (
                                    <>
                                      <Check size={13} /> Salva nos Flashcards
                                    </>
                                  ) : (
                                    <>
                                      <Layers size={13} /> Transformar em Flashcard
                                    </>
                                  )}
                                </Button>
                              </div>
                              <p className="text-sm text-fg leading-relaxed">{q.comentario}</p>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* RODAPÉ DE NAVEGAÇÃO ENTRE AULAS */}
              <div className="flex flex-col sm:flex-row items-center justify-between gap-3 rounded-2xl border border-line-strong bg-surface p-5">
                {prevLesson ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => handleSelectLesson(prevLesson.id)}
                    className="gap-2"
                  >
                    <ArrowLeft size={14} /> Aula Anterior
                  </Button>
                ) : (
                  <div />
                )}

                {nextLesson ? (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => handleSelectLesson(nextLesson.id)}
                    className="gap-2 font-extrabold"
                  >
                    Próxima Aula: {nextLesson.titulo.slice(0, 38)}... <ArrowRight size={14} />
                  </Button>
                ) : (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => handleSelectLesson(null)}
                    className="gap-2 font-extrabold"
                  >
                    <Trophy size={14} /> Concluir Trilha
                  </Button>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
