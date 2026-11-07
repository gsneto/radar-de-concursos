import { useState } from 'react';
import { useLesson, useLessons, useQuestions } from '@/app/queries';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { SkeletonRows } from '@/components/ui/states';
import { AlertCircle, ArrowLeft, CheckCircle2, ChevronRight, XCircle } from 'lucide-react';

export function LessonsView() {
  const [selectedDisciplina, setSelectedDisciplina] = useState<string>('');
  const [activeLessonId, setActiveLessonId] = useState<string | null>(null);

  const { data: lessonsData, isLoading: lessonsLoading } = useLessons(
    selectedDisciplina || undefined
  );
  const { data: lessonDetailData, isLoading: lessonDetailLoading } = useLesson(activeLessonId);
  const { data: allQuestions } = useQuestions();

  const lessons = lessonsData?.aulas ?? [];
  const activeLesson = lessonDetailData?.aula;

  // Question practice interactive state: questionId -> selectedOption
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

  return (
    <div className="space-y-4">
      {/* If no lesson is actively selected, show catalog and filters */}
      {!activeLessonId ? (
        <Card
          title="Plano de Aulas Estruturado"
          subtitle="Roteiro pedagógico completo com teoria direta ao ponto, como as bancas cobram e questões comentadas."
        >
          {/* Discipline selector */}
          <div className="flex flex-wrap gap-2 border-b border-line pb-3">
            {disciplinesList.map((d) => (
              <button
                key={d.id}
                type="button"
                onClick={() => setSelectedDisciplina(d.id)}
                className={`rounded-md px-3 py-1.5 text-xs font-semibold uppercase tracking-wider transition-colors ${
                  selectedDisciplina === d.id
                    ? 'bg-accent text-white shadow-sm'
                    : 'bg-surface-2 text-fg-3 border border-line hover:text-fg hover:border-line-strong'
                }`}
              >
                {d.label}
              </button>
            ))}
          </div>

          {lessonsLoading ? (
            <SkeletonRows rows={4} className="mt-4" />
          ) : lessons.length === 0 ? (
            <div className="py-8 text-center text-xs text-fg-3">
              Nenhuma aula encontrada para este filtro.
            </div>
          ) : (
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {lessons.map((lesson) => (
                <div
                  key={lesson.id}
                  onClick={() => setActiveLessonId(lesson.id)}
                  className="group flex flex-col justify-between rounded-lg border border-line bg-surface p-4 transition-all hover:border-accent/50 hover:bg-surface-2 cursor-pointer"
                >
                  <div>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-accent">
                        {lesson.disciplina}
                      </span>
                      <Badge tone="verified">
                        {lesson.questoes_count} questões reais
                      </Badge>
                    </div>
                    <h3 className="mt-2 text-sm font-bold text-fg group-hover:text-accent transition-colors">
                      {lesson.titulo}
                    </h3>
                    <ul className="mt-2.5 space-y-1">
                      {lesson.objetivos.slice(0, 2).map((obj, i) => (
                        <li key={i} className="flex items-start gap-1.5 text-2xs text-fg-3">
                          <span className="text-accent">›</span>
                          <span className="line-clamp-1">{obj}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="mt-4 flex items-center justify-between border-t border-line/60 pt-3 text-xs font-semibold text-accent">
                    <span>Estudar Aula</span>
                    <ChevronRight size={14} className="transition-transform group-hover:translate-x-1" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      ) : (
        /* Active Lesson Detail View */
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setActiveLessonId(null)}
              className="gap-1.5"
            >
              <ArrowLeft size={14} /> Voltar para o Catálogo de Aulas
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
                  <span className="text-xs font-bold uppercase tracking-wider text-accent">
                    {activeLesson.disciplina}
                  </span>
                  <Badge tone="verified">
                    {activeLesson.questoes_ids.length} Questões da Aula
                  </Badge>
                </div>
                <h2 className="mt-3 text-lg font-bold text-fg">
                  {activeLesson.titulo}
                </h2>

                <div className="mt-4 rounded-md border border-line-strong bg-surface-2 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wider text-fg-3">
                    Objetivos desta Aula
                  </p>
                  <ul className="mt-2 space-y-1.5 text-xs text-fg-2">
                    {activeLesson.objetivos.map((obj, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <CheckCircle2 size={14} className="mt-0.5 text-accent shrink-0" />
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
                <div className="prose prose-invert max-w-none text-xs leading-relaxed text-fg-2 space-y-3 whitespace-pre-line font-sans">
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
                      className="rounded-lg border border-line bg-surface-2 p-3.5 space-y-1.5"
                    >
                      <div className="flex items-center gap-1.5">
                        <span className="rounded bg-accent/20 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-accent">
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
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 space-y-2">
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

                  return (
                    <div className="space-y-6">
                      {lessonQuestions.map((q, idx) => {
                        const selected = userAnswers[q.id];
                        const isRevealed = revealedKeys[q.id];
                        const correctKey = q.gabarito ?? '';
                        const isCorrect = selected === correctKey;

                        return (
                          <div
                            key={q.id}
                            className="rounded-lg border border-line bg-surface p-4 space-y-3"
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
                                    'border-line bg-surface-2 text-fg hover:border-accent/60';
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
                                      className={`flex w-full items-start gap-2.5 rounded-md border p-2.5 text-left text-xs transition-colors ${optClass}`}
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

                                    let btnClass = 'border-line bg-surface-2 text-fg hover:border-accent';
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
                                        className={`flex flex-1 items-center justify-center gap-2 rounded-md border p-2.5 text-xs font-semibold ${btnClass}`}
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
                                className={`mt-3 rounded-md border p-3 text-xs space-y-1.5 ${
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
                                    <span className="font-semibold">Comentário do Professor: </span>
                                    {q.comentario}
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
            </>
          )}
        </div>
      )}
    </div>
  );
}
