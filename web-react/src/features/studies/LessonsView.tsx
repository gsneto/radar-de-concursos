import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useLesson, useLessons, useQuestions } from '@/app/queries';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { SkeletonRows } from '@/components/ui/states';
import { api } from '@/lib/api';
import { clock } from '@/lib/format';
import type { LessonFlashcard, LessonVideo } from '@/lib/types';
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Award,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock,
  ExternalLink,
  Layers,
  Lightbulb,
  Pause,
  Play,
  RotateCcw,
  Search,
  Sparkles,
  Table,
  Target,
  Trophy,
  Video,
  XCircle,
  Zap,
} from 'lucide-react';

export function LessonsView() {
  const [searchParams, setSearchParams] = useSearchParams();
  const aulaParam = searchParams.get('aula');

  const [selectedDisciplina, setSelectedDisciplina] = useState<string>('');
  const [activeLessonId, setActiveLessonId] = useState<string | null>(aulaParam);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'todas' | 'pendentes' | 'concluidas'>('todas');

  // Aba ativa dentro da aula: 'resumo' | 'video' | 'flashcards' | 'bancas' | 'questoes'
  const [activeTab, setActiveTab] = useState<'resumo' | 'video' | 'flashcards' | 'bancas' | 'questoes'>('resumo');

  // Video ativo no player
  const [selectedVideoIndex, setSelectedVideoIndex] = useState<number>(0);

  // Estado dos flashcards virados (id -> boolean)
  const [flippedCards, setFlippedCards] = useState<Record<string, boolean>>({});

  // Flashcards salvos no deck de repetição
  const [savedFlashcards, setSavedFlashcards] = useState<Record<string, boolean>>({});

  // Sincroniza activeLessonId com searchParams
  useEffect(() => {
    if (aulaParam && aulaParam !== activeLessonId) {
      setActiveLessonId(aulaParam);
    }
  }, [aulaParam, activeLessonId]);

  const handleSelectLesson = (id: string | null) => {
    setActiveLessonId(id);
    setSelectedVideoIndex(0);
    setFlippedCards({});
    const next = new URLSearchParams(searchParams);
    if (id) {
      next.set('aula', id);
    } else {
      next.delete('aula');
    }
    setSearchParams(next, { replace: true });
  };

  // Persistence of completed lessons in localStorage
  const [completedLessons, setCompletedLessons] = useState<string[]>(() => {
    try {
      const stored = localStorage.getItem('radar_completed_lessons');
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  const toggleLessonCompletion = (lessonId: string) => {
    setCompletedLessons((prev) => {
      const next = prev.includes(lessonId)
        ? prev.filter((id) => id !== lessonId)
        : [...prev, lessonId];
      try {
        localStorage.setItem('radar_completed_lessons', JSON.stringify(next));
      } catch {
        // Ignore storage errors in restricted contexts
      }
      return next;
    });
  };

  // Cronômetro de Foco
  const [timerSeconds, setTimerSeconds] = useState(0);
  const [isTimerRunning, setIsTimerRunning] = useState(false);

  useEffect(() => {
    let interval: number | undefined;
    if (isTimerRunning) {
      interval = window.setInterval(() => {
        setTimerSeconds((prev) => prev + 1);
      }, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isTimerRunning]);

  const { data: lessonsData, isLoading: lessonsLoading } = useLessons(
    selectedDisciplina || undefined
  );
  const { data: lessonDetailData, isLoading: lessonDetailLoading } = useLesson(activeLessonId);
  const { data: allQuestions } = useQuestions();

  const lessons = useMemo(() => lessonsData?.aulas ?? [], [lessonsData]);
  const activeLesson = lessonDetailData?.aula;

  // Filtro de aulas
  const filteredLessons = useMemo(() => {
    return lessons.filter((lesson) => {
      const query = searchQuery.trim().toLowerCase();
      const matchesSearch =
        !query ||
        lesson.titulo.toLowerCase().includes(query) ||
        lesson.disciplina.toLowerCase().includes(query) ||
        lesson.objetivos.some((obj) => obj.toLowerCase().includes(query));

      const isCompleted = completedLessons.includes(lesson.id);
      const matchesStatus =
        statusFilter === 'todas' ||
        (statusFilter === 'concluidas' && isCompleted) ||
        (statusFilter === 'pendentes' && !isCompleted);

      return matchesSearch && matchesStatus;
    });
  }, [lessons, searchQuery, statusFilter, completedLessons]);

  // Resposta interativa de questões
  const [userAnswers, setUserAnswers] = useState<Record<string, string>>({});
  const [revealedKeys, setRevealedKeys] = useState<Record<string, boolean>>({});

  const handleSelectOption = (questionId: string, optionKey: string) => {
    setUserAnswers((prev) => ({ ...prev, [questionId]: optionKey }));
    setRevealedKeys((prev) => ({ ...prev, [questionId]: true }));
  };

  const disciplinesList = [
    { id: '', label: 'Todas as Matérias' },
    { id: 'Banco de Dados', label: 'Banco de Dados' },
    { id: 'Engenharia de Software', label: 'Engenharia de Software' },
    { id: 'Redes de Computadores', label: 'Redes de Computadores' },
    { id: 'Segurança da Informação', label: 'Segurança da Informação' },
    { id: 'Língua Portuguesa', label: 'Língua Portuguesa' },
    { id: 'Direito Constitucional', label: 'Direito Constitucional' },
  ];

  const totalLessonsCount = lessons.length;
  const completedCount = lessons.filter((l) => completedLessons.includes(l.id)).length;
  const completionPercentage = totalLessonsCount > 0 ? Math.round((completedCount / totalLessonsCount) * 100) : 0;

  // Navegação anterior / próxima
  const currentLessonIndex = lessons.findIndex((l) => l.id === activeLessonId);
  const prevLesson = currentLessonIndex > 0 ? lessons[currentLessonIndex - 1] : null;
  const nextLesson = currentLessonIndex >= 0 && currentLessonIndex < lessons.length - 1 ? lessons[currentLessonIndex + 1] : null;

  // Virar flashcard
  const toggleCardFlip = (cardId: string) => {
    setFlippedCards((prev) => ({ ...prev, [cardId]: !prev[cardId] }));
  };

  // Salvar flashcard no deck de repetição
  const handleSaveFlashcard = async (fc: LessonFlashcard) => {
    try {
      await api.post('/api/estudos/flashcards', {
        frente: fc.frente,
        verso: `${fc.verso}${fc.mnemonico ? `\n\n💡 Mnemônico: ${fc.mnemonico}` : ''}`,
        disciplina: activeLesson?.disciplina || 'Geral',
        tags: [fc.tag],
      });
      setSavedFlashcards((prev) => ({ ...prev, [fc.id]: true }));
    } catch {
      // fallback gracioso
      setSavedFlashcards((prev) => ({ ...prev, [fc.id]: true }));
    }
  };

  return (
    <div className="space-y-5">
      {/* Visualização de Catálogo de Aulas */}
      {!activeLessonId ? (
        <div className="space-y-4">
          {/* Cockpit de Progresso da Trilha */}
          <div className="relative overflow-hidden rounded-2xl border border-line bg-gradient-to-r from-surface via-surface-2 to-surface p-5 sm:p-6 shadow-md">
            <div
              aria-hidden="true"
              className="pointer-events-none absolute -right-20 -top-20 size-64 rounded-full bg-amber-500/10 blur-3xl"
            />
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="flex size-6 items-center justify-center rounded-lg bg-amber-400/20 text-amber-400">
                    <Sparkles size={14} />
                  </span>
                  <span className="text-xs font-bold uppercase tracking-wider text-amber-400">
                    Ambiente Completo de Ensino
                  </span>
                </div>
                <h2 className="mt-1 font-display text-xl font-bold tracking-tight text-fg sm:text-2xl">
                  Aulas, Resumos Explicados & Videoaulas
                </h2>
                <p className="mt-1 text-xs text-fg-3 max-w-xl">
                  Aprenda de verdade com videoaulas selecionadas, resumos didáticos em tabelas, flashcards visuais e questões comentadas.
                </p>
              </div>

              {/* Métricas de Progresso */}
              <div className="flex flex-wrap items-center gap-4 sm:flex-col sm:items-end sm:gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-fg-3">Progresso do Edital:</span>
                  <span className="font-mono text-base font-bold text-fg">
                    {completedCount} <span className="text-xs text-fg-3">/ {totalLessonsCount} aulas</span>
                  </span>
                  <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs font-bold text-emerald-400 border border-emerald-500/30">
                    {completionPercentage}%
                  </span>
                </div>

                <div className="h-2 w-full max-w-[200px] overflow-hidden rounded-full bg-surface-3">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-amber-400 to-emerald-400 transition-all duration-500"
                    style={{ width: `${completionPercentage}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Filtros e Barra de Pesquisa */}
            <div className="mt-6 flex flex-col gap-3 border-t border-line/80 pt-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="relative flex-1 max-w-md">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-fg-3" />
                <input
                  type="text"
                  placeholder="Pesquisar por assunto ou palavra-chave (ex: SQL, Scrum, ACID, Criptografia)..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full rounded-xl border border-line bg-surface/90 py-2 pl-9 pr-3 text-xs text-fg placeholder:text-fg-3/60 focus:border-amber-400/60 focus:outline-none focus:ring-1 focus:ring-amber-400/40"
                />
              </div>

              {/* Filtro por Estado: Todas / Pendentes / Concluídas */}
              <div className="flex items-center gap-1 rounded-xl border border-line bg-surface/80 p-1">
                {(['todas', 'pendentes', 'concluidas'] as const).map((filterKey) => {
                  const label =
                    filterKey === 'todas'
                      ? `Todas (${lessons.length})`
                      : filterKey === 'pendentes'
                        ? `Pendentes (${lessons.length - completedCount})`
                        : `Concluídas (${completedCount})`;
                  const isSelected = statusFilter === filterKey;
                  return (
                    <button
                      key={filterKey}
                      type="button"
                      onClick={() => setStatusFilter(filterKey)}
                      className={`rounded-lg px-2.5 py-1 text-2xs font-semibold uppercase tracking-wider transition-colors ${
                        isSelected
                          ? 'bg-amber-400 text-slate-950 shadow-xs'
                          : 'text-fg-3 hover:text-fg hover:bg-surface-2'
                      }`}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Seletor de Disciplina */}
          <div className="flex flex-wrap gap-2 border-b border-line pb-3">
            {disciplinesList.map((d) => (
              <button
                key={d.id}
                type="button"
                onClick={() => setSelectedDisciplina(d.id)}
                className={`rounded-xl px-3.5 py-1.5 text-xs font-semibold tracking-wider transition-all ${
                  selectedDisciplina === d.id
                    ? 'bg-amber-400 text-slate-950 shadow-sm font-bold'
                    : 'bg-surface-2 text-fg-3 border border-line hover:text-fg hover:border-line-strong'
                }`}
              >
                {d.label}
              </button>
            ))}
          </div>

          {/* Lista de Aulas em Grid */}
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
                  Tente alterar os termos de busca ou selecionar outra disciplina nos filtros acima.
                </p>
              </div>
            </Card>
          ) : (
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
                      {/* Topo do Card */}
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400">
                          {lesson.disciplina}
                        </span>

                        <div className="flex items-center gap-1.5">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleLessonCompletion(lesson.id);
                            }}
                            className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold transition-colors ${
                              isCompleted
                                ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                                : 'bg-surface-2 text-fg-3 border border-line hover:text-fg'
                            }`}
                          >
                            {isCompleted ? (
                              <>
                                <Check size={11} className="text-emerald-400" />
                                <span>Concluída</span>
                              </>
                            ) : (
                              <span>Pendente</span>
                            )}
                          </button>

                          <Badge tone="verified">
                            {lesson.questoes_count} questões
                          </Badge>
                        </div>
                      </div>

                      {/* Título da Aula */}
                      <h3 className="mt-2.5 text-sm font-bold text-fg group-hover:text-amber-400 transition-colors leading-snug">
                        {lesson.titulo}
                      </h3>

                      {/* Recursos da Aula: Video, Resumo, Flashcards */}
                      <div className="mt-3 flex flex-wrap gap-1 text-[10px] font-medium text-fg-3">
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-surface-2 border border-line">
                          <Video size={11} className="text-rose-400" /> Videoaula
                        </span>
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-surface-2 border border-line">
                          <Table size={11} className="text-amber-400" /> Resumo Visual
                        </span>
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-surface-2 border border-line">
                          <Layers size={11} className="text-purple-400" /> Flashcards
                        </span>
                      </div>

                      {/* Objetivos Principais */}
                      <ul className="mt-3 space-y-1">
                        {lesson.objetivos.slice(0, 2).map((obj, i) => (
                          <li key={i} className="flex items-start gap-1.5 text-2xs text-fg-3">
                            <span className="text-amber-400 font-bold">›</span>
                            <span className="line-clamp-1">{obj}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="mt-4 flex items-center justify-between border-t border-line/60 pt-3 text-xs font-semibold text-amber-400 group-hover:text-amber-300">
                      <span>Assistir & Estudar</span>
                      <ChevronRight size={14} className="transition-transform group-hover:translate-x-1" />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ) : (
        /* Visualização de Aula Ativa (Ambiente de Ensino Completo) */
        <div className="space-y-4">
          {/* Top Bar de Navegação & Cronômetro de Foco */}
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

              {prevLesson && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSelectLesson(prevLesson.id)}
                  title={`Aula Anterior: ${prevLesson.titulo}`}
                  className="hidden sm:inline-flex gap-1 text-2xs"
                >
                  <ArrowLeft size={12} /> Anterior
                </Button>
              )}
              {nextLesson && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSelectLesson(nextLesson.id)}
                  title={`Próxima Aula: ${nextLesson.titulo}`}
                  className="hidden sm:inline-flex gap-1 text-2xs"
                >
                  Próxima <ArrowRight size={12} />
                </Button>
              )}
            </div>

            {/* Cronômetro Pomodoro de Foco */}
            <div className="flex items-center gap-2 rounded-xl border border-line bg-surface-2 px-3 py-1.5">
              <Clock size={13} className="text-amber-400" />
              <span className="font-mono text-xs font-bold tabular text-fg">
                {clock(timerSeconds)}
              </span>
              <button
                type="button"
                onClick={() => setIsTimerRunning(!isTimerRunning)}
                className="ml-1 rounded p-1 text-fg-3 hover:text-fg hover:bg-surface transition-colors"
                title={isTimerRunning ? 'Pausar foco' : 'Iniciar foco'}
              >
                {isTimerRunning ? <Pause size={12} /> : <Play size={12} />}
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsTimerRunning(false);
                  setTimerSeconds(0);
                }}
                className="rounded p-1 text-fg-3 hover:text-fg hover:bg-surface transition-colors"
                title="Zerar cronômetro"
              >
                <RotateCcw size={11} />
              </button>
            </div>

            {/* Marcar Conclusão */}
            <Button
              variant={completedLessons.includes(activeLessonId) ? 'secondary' : 'primary'}
              size="sm"
              onClick={() => toggleLessonCompletion(activeLessonId)}
              className="gap-1.5"
            >
              {completedLessons.includes(activeLessonId) ? (
                <>
                  <CheckCircle2 size={14} className="text-emerald-400" />
                  <span>Aula Concluída</span>
                </>
              ) : (
                <>
                  <Check size={14} />
                  <span>Concluir Aula</span>
                </>
              )}
            </Button>
          </div>

          {lessonDetailLoading || !activeLesson ? (
            <Card>
              <SkeletonRows rows={6} />
            </Card>
          ) : (
            <div className="space-y-4">
              {/* Cabeçalho da Aula */}
              <div className="rounded-2xl border border-line bg-gradient-to-br from-surface to-surface-2 p-5 sm:p-6 shadow-md">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line/60 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-amber-400">
                      {activeLesson.disciplina}
                    </span>
                    <span className="text-fg-3 text-xs">·</span>
                    <span className="text-2xs text-fg-3 flex items-center gap-1">
                      <Clock size={11} /> 30-45 min de estudo recomendado
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5">
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
                      <Target size={11} /> {activeLesson.questoes_ids?.length ?? activeLesson.questoes_count ?? 0} Questões
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

              {/* Menu de Abas Pedagógicas */}
              <div className="flex items-center gap-1.5 overflow-x-auto rounded-xl border border-line bg-surface-2 p-1.5 scrollbar-none">
                {[
                  { id: 'resumo', label: 'Resumo & Teoria Explicada', icon: BookOpen },
                  { id: 'video', label: 'Videoaula Recomendada', icon: Video, badge: activeLesson.videoaulas?.length },
                  { id: 'flashcards', label: 'Flashcards Visuais (3D)', icon: Layers, badge: activeLesson.flashcards?.length },
                  { id: 'bancas', label: 'Raio-X das Bancas', icon: Award },
                  { id: 'questoes', label: 'Caderno de Questões', icon: Target, badge: activeLesson.questoes_ids?.length ?? activeLesson.questoes_count },
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
                      {tab.badge !== undefined && (
                        <span
                          className={`rounded-full px-1.5 py-0.2 text-[10px] font-bold ${
                            isCurrent
                              ? 'bg-slate-950 text-amber-300'
                              : 'bg-surface border border-line text-fg-3'
                          }`}
                        >
                          {tab.badge}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>

              {/* CONTEÚDO 1: RESUMO & TEORIA EXPLICADA */}
              {activeTab === 'resumo' && (
                <div className="space-y-4">
                  {/* Tabela Comparativa de Alta Retenção (se houver) */}
                  {activeLesson.tabela_resumo && (
                    <Card
                      title={activeLesson.tabela_resumo.titulo}
                      subtitle="Esquema comparativo estruturado para gabaritar questões da banca sem confusão."
                    >
                      <div className="overflow-x-auto rounded-xl border border-line bg-surface-2/60">
                        <table className="w-full text-left text-xs">
                          <thead>
                            <tr className="border-b border-line bg-surface-3/50 text-[11px] font-bold uppercase tracking-wider text-fg-3">
                              {activeLesson.tabela_resumo.colunas.map((col, idx) => (
                                <th key={idx} className="p-3">
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
                                    className={`p-3 ${
                                      cIdx === 0
                                        ? 'font-bold text-amber-400'
                                        : 'text-fg-2'
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

                  {/* Teoria Resumida com Formatação Rica */}
                  <Card
                    title="Conceitos Essenciais da Matéria"
                    subtitle="Teoria mastigada, sem enrolação e focada nos conceitos que têm maior recorrência em prova."
                  >
                    <div className="rounded-xl border border-line/60 bg-surface-2/40 p-4 sm:p-5 text-xs sm:text-sm leading-relaxed text-fg-2 whitespace-pre-line font-sans space-y-3">
                      {activeLesson.teoria_resumida}
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

              {/* CONTEÚDO 2: VIDEOAULA RECOMENDADA */}
              {activeTab === 'video' && (
                <div className="space-y-4">
                  {activeLesson.videoaulas && activeLesson.videoaulas.length > 0 ? (
                    (() => {
                      const currentVideo: LessonVideo =
                        activeLesson.videoaulas[selectedVideoIndex] ?? activeLesson.videoaulas[0];

                      return (
                        <div className="space-y-4">
                          {/* Player de Vídeo Responsivo 16:9 */}
                          <div className="relative aspect-video w-full overflow-hidden rounded-2xl border border-line bg-slate-950 shadow-2xl">
                            <iframe
                              src={`https://www.youtube-nocookie.com/embed/${currentVideo.youtube_id}?rel=0&modestbranding=1`}
                              title={currentVideo.titulo}
                              className="h-full w-full"
                              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                              allowFullScreen
                            />
                          </div>

                          {/* Informações da Videoaula */}
                          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-line bg-surface p-4">
                            <div className="space-y-1">
                              <div className="flex items-center gap-2">
                                <span className="inline-flex items-center gap-1 rounded bg-rose-500/15 px-2 py-0.5 text-[10px] font-bold text-rose-400 border border-rose-500/30">
                                  <Video size={11} /> {currentVideo.canal}
                                </span>
                                <span className="text-2xs text-fg-3 flex items-center gap-1">
                                  <Clock size={11} /> {currentVideo.duracao}
                                </span>
                              </div>
                              <h3 className="text-sm font-bold text-fg sm:text-base">
                                {currentVideo.titulo}
                              </h3>
                              {currentVideo.descricao && (
                                <p className="text-xs text-fg-3 max-w-2xl">{currentVideo.descricao}</p>
                              )}
                            </div>

                            <a
                              href={`https://www.youtube.com/watch?v=${currentVideo.youtube_id}`}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface-2 px-3 py-2 text-xs font-semibold text-fg hover:text-amber-400 transition-colors shrink-0"
                            >
                              <span>Assistir no YouTube</span>
                              <ExternalLink size={13} />
                            </a>
                          </div>

                          {/* Seletor de Outros Vídeos da Aula */}
                          {activeLesson.videoaulas.length > 1 && (
                            <div className="space-y-2">
                              <h4 className="text-xs font-bold text-fg uppercase tracking-wider">
                                Todas as Videoaulas Deste Assunto ({activeLesson.videoaulas.length})
                              </h4>
                              <div className="grid gap-2.5 sm:grid-cols-2">
                                {activeLesson.videoaulas.map((vid, idx) => (
                                  <div
                                    key={idx}
                                    onClick={() => setSelectedVideoIndex(idx)}
                                    className={`cursor-pointer rounded-xl border p-3 transition-all flex items-start gap-3 ${
                                      selectedVideoIndex === idx
                                        ? 'border-amber-400 bg-amber-400/10 ring-1 ring-amber-400/30'
                                        : 'border-line bg-surface hover:border-line-strong'
                                    }`}
                                  >
                                    <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-surface-2 text-fg font-bold text-xs">
                                      {idx + 1}
                                    </div>
                                    <div className="min-w-0 flex-1 space-y-0.5">
                                      <p className="text-xs font-bold text-fg truncate">{vid.titulo}</p>
                                      <div className="flex items-center gap-2 text-2xs text-fg-3">
                                        <span>{vid.canal}</span>
                                        <span>·</span>
                                        <span>{vid.duracao}</span>
                                      </div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })()
                  ) : (
                    <Card>
                      <div className="py-12 text-center space-y-2">
                        <Video size={32} className="mx-auto text-fg-3/40" />
                        <h3 className="text-sm font-bold text-fg">Videoaula em Curadoria</h3>
                        <p className="text-xs text-fg-3 max-w-sm mx-auto">
                          A videoaula deste tópico está sendo selecionada. Aproveite o Resumo Explicado e os Flashcards Visuais da aba ao lado!
                        </p>
                      </div>
                    </Card>
                  )}
                </div>
              )}

              {/* CONTEÚDO 3: FLASHCARDS VISUAIS INTERATIVOS */}
              {activeTab === 'flashcards' && (
                <div className="space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-2xl border border-line bg-surface p-4">
                    <div>
                      <h3 className="text-sm font-bold text-fg flex items-center gap-2">
                        <Layers size={16} className="text-purple-400" />
                        Flashcards de Fixação Imediata
                      </h3>
                      <p className="text-xs text-fg-3 mt-0.5">
                        Clique em qualquer cartão para virar e conferir a resposta. Adicione ao seu deck diário com repetição espaçada SM-2.
                      </p>
                    </div>

                    <span className="text-2xs font-mono font-medium text-fg-3 px-2.5 py-1 rounded-full bg-surface-2 border border-line shrink-0">
                      {activeLesson.flashcards?.length ?? 0} cartões disponíveis
                    </span>
                  </div>

                  {activeLesson.flashcards && activeLesson.flashcards.length > 0 ? (
                    <div className="grid gap-4 sm:grid-cols-2">
                      {activeLesson.flashcards.map((fc) => {
                        const isFlipped = !!flippedCards[fc.id];
                        const isSaved = !!savedFlashcards[fc.id];

                        return (
                          <div
                            key={fc.id}
                            onClick={() => toggleCardFlip(fc.id)}
                            className="cursor-pointer group relative flex flex-col justify-between min-h-[220px] rounded-2xl border border-line bg-surface p-5 transition-all duration-300 hover:border-amber-400/50 hover:shadow-xl"
                          >
                            {/* Topo do Flashcard */}
                            <div className="flex items-center justify-between gap-2 border-b border-line/60 pb-2.5">
                              <span className="text-[10px] font-bold uppercase tracking-wider text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
                                {fc.tag}
                              </span>

                              <span className="text-[10px] text-fg-3 flex items-center gap-1 font-medium">
                                <RotateCcw size={11} /> Clique para virar
                              </span>
                            </div>

                            {/* Conteúdo: Frente vs Verso */}
                            <div className="py-4 my-auto">
                              {!isFlipped ? (
                                <div className="space-y-2">
                                  <span className="text-[10px] font-bold uppercase tracking-wider text-fg-3 block">
                                    Pergunta / Conceito:
                                  </span>
                                  <h4 className="text-sm font-bold text-fg leading-snug group-hover:text-amber-400 transition-colors">
                                    {fc.frente}
                                  </h4>
                                </div>
                              ) : (
                                <div className="space-y-3">
                                  <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400 block">
                                    Resposta Didática:
                                  </span>
                                  <p className="text-xs sm:text-sm text-fg font-medium leading-relaxed">
                                    {fc.verso}
                                  </p>

                                  {fc.mnemonico && (
                                    <div className="rounded-lg border border-amber-400/30 bg-amber-400/10 p-2 text-2xs text-amber-300 flex items-start gap-1.5 leading-relaxed">
                                      <Lightbulb size={13} className="shrink-0 mt-0.5 text-amber-400" />
                                      <span><strong>Mnemônico:</strong> {fc.mnemonico}</span>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>

                            {/* Rodapé: Ação de Salvar no Deck de Revisão */}
                            <div className="flex items-center justify-between border-t border-line/60 pt-2.5">
                              <span className="text-2xs text-fg-3">
                                {isFlipped ? 'Verso revelado' : 'Frente'}
                              </span>

                              <Button
                                size="sm"
                                variant={isSaved ? 'secondary' : 'ghost'}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleSaveFlashcard(fc);
                                }}
                                className="gap-1 text-2xs h-7 px-2"
                                title="Adicionar à fila oficial de repetição espaçada"
                              >
                                {isSaved ? (
                                  <>
                                    <CheckCircle2 size={12} className="text-emerald-400" />
                                    <span>Salvo na Revisão</span>
                                  </>
                                ) : (
                                  <>
                                    <Zap size={12} className="text-amber-400" />
                                    <span>Salvar no Deck</span>
                                  </>
                                )}
                              </Button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <Card>
                      <p className="text-xs text-fg-3 text-center py-8">
                        Nenhum flashcard cadastrado para esta aula no momento.
                      </p>
                    </Card>
                  )}
                </div>
              )}

              {/* CONTEÚDO 4: RAIO-X DAS BANCAS */}
              {activeTab === 'bancas' && (
                <div className="space-y-4">
                  <Card
                    title="Como as Bancas Examinadoras Cobram Este Assunto"
                    subtitle="Análise comparativa das nuances, estilo de questão e armadilhas específicas de cada banca."
                  >
                    <div className="grid gap-3.5 sm:grid-cols-2">
                      {Object.entries(activeLesson.radiografia_bancas).map(([bancaKey, desc]) => (
                        <div
                          key={bancaKey}
                          className="rounded-xl border border-line bg-surface-2 p-4 space-y-2"
                        >
                          <div className="flex items-center gap-1.5">
                            <span className="rounded bg-amber-400/15 px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider text-amber-300 border border-amber-400/30">
                              {bancaKey}
                            </span>
                          </div>
                          <p className="text-xs leading-relaxed text-fg-2">
                            {desc}
                          </p>
                        </div>
                      ))}
                    </div>
                  </Card>
                </div>
              )}

              {/* CONTEÚDO 5: CADERNO DE QUESTÕES */}
              {activeTab === 'questoes' && (
                <Card
                  title="Treino Prático com Questões de Provas Reais"
                  subtitle="Teste seus conhecimentos imediatamente com questões autênticas de concursos anteriores."
                >
                  {(() => {
                    const lessonQuestions = (allQuestions ?? []).filter((q) =>
                      activeLesson.questoes_ids?.includes(q.id) ?? false
                    );

                    if (lessonQuestions.length === 0) {
                      return (
                        <p className="text-xs text-fg-3">
                          Nenhuma questão cadastrada para esta aula no momento.
                        </p>
                      );
                    }

                    const answeredCount = lessonQuestions.filter((q) => revealedKeys[q.id]).length;
                    const correctCount = lessonQuestions.filter(
                      (q) => revealedKeys[q.id] && userAnswers[q.id] === q.gabarito
                    ).length;

                    return (
                      <div className="space-y-6">
                        {/* Placar de Desempenho da Aula */}
                        <div className="flex items-center justify-between rounded-xl border border-line bg-surface-2 p-3 text-xs">
                          <div className="flex items-center gap-2">
                            <Trophy size={16} className="text-amber-400" />
                            <span className="font-semibold text-fg">Desempenho no Caderno da Aula:</span>
                          </div>
                          <div className="flex items-center gap-2 font-mono">
                            <span className="text-fg-3">
                              {answeredCount} de {lessonQuestions.length} respondidas
                            </span>
                            {answeredCount > 0 && (
                              <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-2xs font-bold text-emerald-300 border border-emerald-500/30">
                                {correctCount} acertos ({Math.round((correctCount / answeredCount) * 100)}%)
                              </span>
                            )}
                          </div>
                        </div>

                        {lessonQuestions.map((q, idx) => {
                          const selected = userAnswers[q.id];
                          const isRevealed = revealedKeys[q.id];
                          const correctKey = q.gabarito ?? '';
                          const isCorrect = selected === correctKey;

                          return (
                            <div
                              key={q.id}
                              className="rounded-xl border border-line bg-surface p-4 space-y-3 shadow-xs"
                            >
                              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2.5">
                                <span className="text-xs font-bold text-fg">
                                  Questão {idx + 1}
                                </span>
                                <div className="flex flex-wrap gap-1.5">
                                  {(q.tags ?? []).map((t) => (
                                    <span
                                      key={t}
                                      className="rounded bg-surface-2 px-1.5 py-0.5 text-[10px] font-medium text-fg-3 border border-line"
                                    >
                                      {t}
                                    </span>
                                  ))}
                                </div>
                              </div>

                              <p className="text-xs leading-relaxed text-fg whitespace-pre-line font-medium">
                                {q.enunciado}
                              </p>

                              {/* Alternativas */}
                              <div className="space-y-2 pt-1">
                                {(() => {
                                  const optionsList: { key: string; text: string }[] =
                                    Array.isArray(q.alternativas) && q.alternativas.length > 0
                                      ? q.alternativas.map((alt) => ({ key: alt.letra, text: alt.texto }))
                                      : q.opcoes && typeof q.opcoes === 'object'
                                        ? Object.entries(q.opcoes).map(([k, v]) => ({ key: k, text: String(v) }))
                                        : [];

                                  return optionsList.map(({ key, text }) => {
                                    const isSelected = selected === key;
                                    const isThisCorrect = key === correctKey;

                                    let optionStyle = 'border-line bg-surface-2/60 text-fg hover:border-line-strong hover:bg-surface-2';
                                    if (isRevealed) {
                                      if (isThisCorrect) {
                                        optionStyle = 'border-emerald-500/60 bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30';
                                      } else if (isSelected && !isThisCorrect) {
                                        optionStyle = 'border-rose-500/60 bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/30';
                                      } else {
                                        optionStyle = 'border-line/40 bg-surface/40 text-fg-3 opacity-60';
                                      }
                                    }

                                    return (
                                      <button
                                        key={key}
                                        type="button"
                                        disabled={isRevealed}
                                        onClick={() => handleSelectOption(q.id, key)}
                                        className={`flex w-full items-start gap-3 rounded-xl border p-3 text-left text-xs transition-all ${optionStyle}`}
                                      >
                                        <span
                                          className={`flex size-5 shrink-0 items-center justify-center rounded font-bold text-2xs ${
                                            isRevealed && isThisCorrect
                                              ? 'bg-emerald-500 text-slate-950'
                                              : isRevealed && isSelected
                                                ? 'bg-rose-500 text-white'
                                                : 'bg-surface-3 text-fg'
                                          }`}
                                        >
                                          {key}
                                        </span>
                                        <span className="flex-1 leading-normal">{text}</span>
                                      </button>
                                    );
                                  });
                                })()}
                              </div>

                              {/* Feedback com Gabarito e Justificativa */}
                              {isRevealed && (
                                <div
                                  className={`rounded-xl border p-3.5 space-y-1.5 text-xs ${
                                    isCorrect
                                      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
                                      : 'border-rose-500/30 bg-rose-500/10 text-rose-200'
                                  }`}
                                >
                                  <div className="flex items-center gap-1.5 font-bold">
                                    {isCorrect ? (
                                      <>
                                        <CheckCircle2 size={16} className="text-emerald-400" />
                                        <span>Você acertou! Gabarito oficial: {correctKey}</span>
                                      </>
                                    ) : (
                                      <>
                                        <XCircle size={16} className="text-rose-400" />
                                        <span>Você errou. Gabarito oficial correto: {correctKey}</span>
                                      </>
                                    )}
                                  </div>

                                  {q.comentario && (
                                    <p className="text-2xs leading-relaxed text-fg-2 pt-1 border-t border-line/40">
                                      <strong>Comentário do Professor:</strong> {q.comentario}
                                    </p>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    );
                  })()}
                </Card>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
