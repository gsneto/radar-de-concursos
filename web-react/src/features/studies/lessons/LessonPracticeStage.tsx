import { useMemo, useState } from 'react';
import { Check, CheckCircle2, Layers, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { LessonDetail, LessonQuestionDetail } from '@/lib/types';

interface LessonPracticeStageProps {
  lesson: LessonDetail;
  questions: LessonQuestionDetail[];
  selectedAnswers: Record<string, string>;
  revealedQuestions: Record<string, boolean>;
  questionConvertedToCard: Record<string, boolean>;
  onSelectOption: (questionId: string, optionKey: string) => void;
  onConvertQuestionToFlashcard: (question: LessonQuestionDetail) => void;
}

export function LessonPracticeStage({
  lesson,
  questions,
  selectedAnswers,
  revealedQuestions,
  questionConvertedToCard,
  onSelectOption,
  onConvertQuestionToFlashcard,
}: LessonPracticeStageProps) {
  const [labExerciseState, setLabExerciseState] = useState<Record<string, string>>({});
  const [labExerciseRevealed, setLabExerciseRevealed] = useState<Record<string, boolean>>({});

  const masteryStats = useMemo(() => {
    const total = questions.length;
    if (total === 0) return { total: 0, answered: 0, correct: 0, pct: 0 };
    let answered = 0;
    let correct = 0;
    for (const q of questions) {
      const userAns = selectedAnswers[q.id];
      if (userAns) {
        answered += 1;
        if (userAns === q.gabarito) correct += 1;
      }
    }
    const pct = total > 0 ? Math.round((correct / total) * 100) : 0;
    return { total, answered, correct, pct };
  }, [questions, selectedAnswers]);

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border-2 border-amber-400/40 bg-surface p-6 shadow-md">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <span className="text-xs font-black uppercase tracking-widest text-accent-ink">
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
              <span className="text-[10px] font-bold uppercase text-ok-ink block">Acertos</span>
              <span className="font-display text-lg font-black text-ok-ink tabular">{masteryStats.correct}</span>
            </div>
            <div className="rounded-xl border border-amber-400/40 bg-amber-400/10 px-4 py-2.5 text-center">
              <span className="text-[10px] font-bold uppercase text-accent-ink block">Domínio</span>
              <span className="font-display text-lg font-black text-accent-ink tabular">{masteryStats.pct}%</span>
            </div>
          </div>
        </div>
      </div>

      {lesson.exercicios_interativos && lesson.exercicios_interativos.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-2">
          {lesson.exercicios_interativos.map((ex) => {
            const revealed = Boolean(labExerciseRevealed[ex.id]);
            const selected = labExerciseState[ex.id];
            return (
              <div key={ex.id} className="rounded-2xl border border-line-strong bg-surface p-5 space-y-3">
                <span className="rounded bg-sky-500/20 px-2.5 py-1 text-[11px] font-black uppercase text-info-ink">
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
                              ? 'border-emerald-500 bg-emerald-500/20 text-ok-ink'
                              : 'border-rose-500 bg-rose-500/20 text-risk-ink'
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
                        <span className="font-extrabold text-accent-ink">{p.conceito}</span>
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

      <div className="space-y-5">
        {questions.map((q, idx) => {
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
                  <span className="rounded-md bg-surface-2 border border-line-strong px-2.5 py-1 text-xs font-extrabold text-accent-ink">
                    {q.banca_sigla || 'PROVA OFICIAL'}
                  </span>
                  <span className="text-xs font-bold text-fg-2">{q.fonte}</span>
                </div>

                {isRevealed && (
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1 text-xs font-extrabold ${
                      isCorrect
                        ? 'bg-emerald-500/20 text-ok-ink border border-emerald-500/40'
                        : 'bg-rose-500/20 text-risk-ink border border-rose-500/40'
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
                      cls = 'border-rose-500 bg-rose-500/15 text-risk-ink';
                    } else {
                      cls = 'border-line bg-surface-2/40 text-fg-3';
                    }
                  }
                  return (
                    <button
                      key={opt.letra}
                      type="button"
                      disabled={isRevealed}
                      onClick={() => onSelectOption(q.id, opt.letra)}
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
                    <span className="text-xs font-black uppercase tracking-wider text-accent-ink">
                      COMENTÁRIO DO PROFESSOR (GABARITO: {q.gabarito})
                    </span>
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={Boolean(questionConvertedToCard[q.id])}
                      onClick={() => onConvertQuestionToFlashcard(q)}
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
  );
}
