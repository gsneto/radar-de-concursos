import { useState, useEffect, useMemo } from 'react';
import { useLesson, useLessons, useQuestions } from '@/app/queries';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { SkeletonRows } from '@/components/ui/states';
import { clock } from '@/lib/format';
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock,
  Pause,
  Play,
  RotateCcw,
  Search,
  Sparkles,
  Trophy,
  XCircle,
} from 'lucide-react';

export function LessonsView() {
  const [selectedDisciplina, setSelectedDisciplina] = useState<string>('');
  const [activeLessonId, setActiveLessonId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'todas' | 'pendentes' | 'concluidas'>('todas');

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

  // Dedicated Study Focus Stopwatch
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

  // Filter lessons by search query and completion status
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

  // Interactive Question State: questionId -> selectedOption
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
    { id: 'Língua Portuguesa', label: 'Língua Portuguesa' },
    { id: 'Direito Constitucional', label: 'Direito Constitucional' },
  ];

  // Syllabus progress metrics
  const totalLessonsCount = lessons.length;
  const completedCount = lessons.filter((l) => completedLessons.includes(l.id)).length;
  const completionPercentage = totalLessonsCount > 0 ? Math.round((completedCount / totalLessonsCount) * 100) : 0;

  // Navigation between lessons
  const currentLessonIndex = lessons.findIndex((l) => l.id === activeLessonId);
  const prevLesson = currentLessonIndex > 0 ? lessons[currentLessonIndex - 1] : null;
  const nextLesson = currentLessonIndex >= 0 && currentLessonIndex < lessons.length - 1 ? lessons[currentLessonIndex + 1] : null;

  return (
    <div className="space-y-5">
      {/* If no lesson is actively selected, show catalog and filters */}
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
                    Trilha Pedagógica Verticalizada
                  </span>
                </div>
                <h2 className="mt-1 font-display text-xl font-bold tracking-tight text-fg sm:text-2xl">
                  Plano de Aulas Estruturado
                </h2>
                <p className="mt-1 text-xs text-fg-3 max-w-xl">
                  Roteiro pedagógico completo com teoria direta ao ponto, como as bancas cobram e questões comentadas.
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
                  placeholder="Pesquisar por assunto ou palavra-chave (ex: SQL, Scrum, ACID)..."
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
            <SkeletonRows rows={4} className="mt-4" />
          ) : filteredLessons.length === 0 ? (
            <div className="py-12 text-center rounded-2xl border border-dashed border-line bg-surface/40">
              <BookOpen size={28} className="mx-auto text-fg-3/60 mb-2" />
              <p className="text-xs font-medium text-fg-2">Nenhuma aula encontrada com esses filtros.</p>
              <button
                type="button"
                onClick={() => {
                  setSelectedDisciplina('');
                  setSearchQuery('');
                  setStatusFilter('todas');
                }}
                className="mt-2 text-xs text-amber-400 hover:underline"
              >
                Limpar todos os filtros
              </button>
            </div>
          ) : (
            <div className="grid gap-3.5 sm:grid-cols-2">
              {filteredLessons.map((lesson) => {
                const isCompleted = completedLessons.includes(lesson.id);

                return (
                  <div
                    key={lesson.id}
                    className={`group relative flex flex-col justify-between rounded-xl border p-4 sm:p-5 transition-all cursor-pointer ${
                      isCompleted
                        ? 'border-emerald-500/40 bg-emerald-950/10 hover:border-emerald-500/70 hover:bg-emerald-950/20'
                        : 'border-line bg-surface hover:border-amber-400/50 hover:bg-surface-2 shadow-xs'
                    }`}
                    onClick={() => setActiveLessonId(lesson.id)}
                  >
                    <div>
                      {/* Top Chips */}
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400">
                            {lesson.disciplina}
                          </span>
                          <span className="text-2xs text-fg-3 flex items-center gap-1">
                            <Clock size={11} /> ~25 min
                          </span>
                        </div>

                        <div className="flex items-center gap-1.5">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleLessonCompletion(lesson.id);
                            }}
                            title={isCompleted ? 'Desmarcar conclusão' : 'Marcar como concluída'}
                            className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold transition-colors ${
                              isCompleted
                                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                                : 'bg-surface-2 text-fg-3 border border-line hover:text-fg hover:border-line-strong'
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
                            {lesson.questoes_count} questões reais
                          </Badge>
                        </div>
                      </div>

                      {/* Título da Aula */}
                      <h3 className="mt-2.5 text-sm font-bold text-fg group-hover:text-amber-300 transition-colors">
                        {lesson.titulo}
                      </h3>

                      {/* Objetivos Principais */}
                      <ul className="mt-3 space-y-1.5">
                        {lesson.objetivos.slice(0, 2).map((obj, i) => (
                          <li key={i} className="flex items-start gap-1.5 text-2xs text-fg-3">
                            <span className="text-amber-400 font-bold">›</span>
                            <span className="line-clamp-1">{obj}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="mt-4 flex items-center justify-between border-t border-line/60 pt-3 text-xs font-semibold text-amber-400 group-hover:text-amber-300">
                      <span>Estudar Aula</span>
                      <ChevronRight size={14} className="transition-transform group-hover:translate-x-1" />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ) : (
        /* Active Lesson Detail View */
        <div className="space-y-4">
          {/* Top Sticky Navigation and Focus Stopwatch Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-surface/90 p-3 backdrop-blur-md shadow-sm">
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setActiveLessonId(null)}
                className="gap-1.5"
              >
                <ArrowLeft size={14} /> Voltar ao Catálogo
              </Button>

              {/* Navegação entre aulas */}
              {prevLesson && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setActiveLessonId(prevLesson.id)}
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
                  onClick={() => setActiveLessonId(nextLesson.id)}
                  title={`Próxima Aula: ${nextLesson.titulo}`}
                  className="hidden sm:inline-flex gap-1 text-2xs"
                >
                  Próxima <ArrowRight size={12} />
                </Button>
              )}
            </div>

            {/* Widget de Cronômetro de Foco / Pomodoro */}
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

            {/* Botão de Conclusão da Aula */}
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
                  <span>Marcar como Concluída</span>
                </>
              )}
            </Button>
          </div>

          {lessonDetailLoading || !activeLesson ? (
            <Card>
              <SkeletonRows rows={6} />
            </Card>
          ) : (
            <>
              {/* Header Card */}
              <Card>
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-amber-400">
                      {activeLesson.disciplina}
                    </span>
                    <span className="text-fg-3 text-xs">·</span>
                    <span className="text-2xs text-fg-3 flex items-center gap-1">
                      <Clock size={11} /> Leitura estimada: 25 minutos
                    </span>
                  </div>

                  <Badge tone="verified">
                    {activeLesson.questoes_ids.length} Questões da Aula
                  </Badge>
                </div>

                <h2 className="mt-3 text-lg font-bold text-fg sm:text-xl">
                  {activeLesson.titulo}
                </h2>

                <div className="mt-4 rounded-xl border border-line-strong bg-surface-2 p-3.5">
                  <p className="text-xs font-semibold uppercase tracking-wider text-fg-3">
                    Objetivos desta Aula
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
              </Card>

              {/* Theory Card */}
              <Card
                title="Teoria Essencial & Conceitos-Chave"
                subtitle="Conteúdo sintetizado com foco no que realmente aparece nas provas."
              >
                <div className="rounded-xl border border-line/60 bg-surface-2/40 p-4 text-xs leading-relaxed text-fg-2 whitespace-pre-line font-sans space-y-3">
                  {activeLesson.teoria_resumida}
                </div>
              </Card>

              {/* Radiografia das Bancas */}
              <Card
                title="Como as Bancas Cobram Este Assunto"
                subtitle="Análise comparativa das nuances e armadilhas específicas de cada examinadora."
              >
                <div className="grid gap-3 sm:grid-cols-2">
                  {Object.entries(activeLesson.radiografia_bancas).map(([bancaKey, desc]) => (
                    <div
                      key={bancaKey}
                      className="rounded-xl border border-line bg-surface-2 p-3.5 space-y-1.5"
                    >
                      <div className="flex items-center gap-1.5">
                        <span className="rounded bg-amber-400/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-300 border border-amber-400/25">
                          {bancaKey}
                        </span>
                      </div>
                      <p className="text-xs leading-normal text-fg-2">
                        {desc}
                      </p>
                    </div>
                  ))}
                </div>
              </Card>

              {/* Pontos Críticos / Armadilhas */}
              <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 space-y-2">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-amber-300">
                  <AlertCircle size={16} /> Pontos Críticos & Pegadinhas Clássicas
                </div>
                <ul className="space-y-1.5 text-xs text-amber-100/90">
                  {activeLesson.pontos_criticos.map((ponto, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-amber-400 font-bold">›</span>
                      <span>{ponto}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Interactive Practice Questions */}
              <Card
                title="Treino Prático com Questões de Provas Reais"
                subtitle="Teste seus conhecimentos imediatamente com questões autênticas de concursos anteriores."
              >
                {(() => {
                  const lessonQuestions = (allQuestions ?? []).filter((q) =>
                    activeLesson.questoes_ids.includes(q.id)
                  );

                  if (lessonQuestions.length === 0) {
                    return (
                      <p className="text-xs text-fg-3">
                        Nenhuma questão carregada para esta aula no momento.
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
                                  <Badge key={t} tone="neutral" className="text-[10px]">
                                    {t.replace(/^banca:/, 'Banca: ').toUpperCase()}
                                  </Badge>
                                ))}
                              </div>
                            </div>

                            <p className="text-xs leading-relaxed text-fg whitespace-pre-line font-medium">
                              {q.enunciado}
                            </p>

                            {/* Options */}
                            <div className="space-y-2 pt-1">
                              {q.opcoes ? (
                                Object.entries(q.opcoes).map(([optKey, optText]) => {
                                  const isThisSelected = selected === optKey;
                                  const isThisCorrect = optKey === correctKey;

                                  let optClass =
                                    'border-line bg-surface-2 text-fg hover:border-amber-400/60';
                                  if (isRevealed) {
                                    if (isThisCorrect) {
                                      optClass =
                                        'border-emerald-500/60 bg-emerald-500/15 text-emerald-200';
                                    } else if (isThisSelected && !isThisCorrect) {
                                      optClass =
                                        'border-rose-500/60 bg-rose-500/15 text-rose-200';
                                    }
                                  }

                                  return (
                                    <button
                                      key={optKey}
                                      type="button"
                                      onClick={() => handleSelectOption(q.id, optKey)}
                                      className={`flex w-full items-start gap-2.5 rounded-lg border p-2.5 text-left text-xs transition-colors ${optClass}`}
                                    >
                                      <span className="flex size-5 shrink-0 items-center justify-center rounded border border-current font-bold text-2xs">
                                        {optKey}
                                      </span>
                                      <span className="leading-snug">{String(optText)}</span>
                                    </button>
                                  );
                                })
                              ) : (
                                /* Certo / Errado */
                                <div className="flex gap-3">
                                  {['V', 'F'].map((val) => {
                                    const label = val === 'V' ? 'Certo (Verdadeiro)' : 'Errado (Falso)';
                                    const isThisSelected = selected === val;
                                    const isThisCorrect = val === correctKey;

                                    let btnClass = 'border-line bg-surface-2 text-fg hover:border-amber-400';
                                    if (isRevealed) {
                                      if (isThisCorrect) {
                                        btnClass = 'border-emerald-500/60 bg-emerald-500/15 text-emerald-200';
                                      } else if (isThisSelected) {
                                        btnClass = 'border-rose-500/60 bg-rose-500/15 text-rose-200';
                                      }
                                    }

                                    return (
                                      <button
                                        key={val}
                                        type="button"
                                        onClick={() => handleSelectOption(q.id, val)}
                                        className={`flex flex-1 items-center justify-center gap-2 rounded-lg border p-2.5 text-xs font-semibold ${btnClass}`}
                                      >
                                        <span>{label}</span>
                                      </button>
                                    );
                                  })}
                                </div>
                              )}
                            </div>

                            {/* Feedback & Pedagogical Commentary */}
                            {isRevealed && (
                              <div
                                className={`mt-3 rounded-lg border p-3 text-xs space-y-1.5 ${
                                  isCorrect
                                    ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-100'
                                    : 'border-amber-500/40 bg-amber-500/10 text-amber-100'
                                }`}
                              >
                                <div className="flex items-center gap-1.5 font-bold">
                                  {isCorrect ? (
                                    <>
                                      <CheckCircle2 size={15} className="text-emerald-400" />
                                      <span>Parabéns! Resposta Correta (Gabarito: {correctKey})</span>
                                    </>
                                  ) : (
                                    <>
                                      <XCircle size={15} className="text-amber-400" />
                                      <span>Atenção: Gabarito Oficial é {correctKey}</span>
                                    </>
                                  )}
                                </div>
                                {q.comentario && (
                                  <p className="leading-relaxed opacity-90 pt-1">
                                    <span className="font-semibold">Comentário Pedagógico: </span>
                                    {q.comentario}
                                  </p>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}

                      {/* Footer Actions */}
                      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line/60 pt-4">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => {
                            toggleLessonCompletion(activeLessonId);
                            if (nextLesson) setActiveLessonId(nextLesson.id);
                          }}
                          className="gap-1.5 font-semibold"
                        >
                          <Check size={14} className="text-emerald-400" />
                          Concluir e Ir para Próxima Aula
                        </Button>

                        {nextLesson && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setActiveLessonId(nextLesson.id)}
                            className="gap-1 text-xs"
                          >
                            Pular para Próxima: {nextLesson.titulo} <ArrowRight size={14} />
                          </Button>
                        )}
                      </div>
                    </div>
                  );
                })()}
              </Card>
            </>
          )}
        </div>
      )}
    </div>
  );
}
