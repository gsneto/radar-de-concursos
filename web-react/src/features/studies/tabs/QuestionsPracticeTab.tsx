import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { keys, usePerformance, useQuestions, type Question } from '@/app/queries';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Kpi, NumberTicker } from '@/components/ui/kpi';
import { EmptyState, ErrorState, SkeletonRows } from '@/components/ui/states';
import { api } from '@/lib/api';
import { integer, percent } from '@/lib/format';

export function QuestionsPracticeTab() {
  const questions = useQuestions();
  const performance = usePerformance();
  const [visibleCount, setVisibleCount] = useState(12);

  if (questions.isLoading) return <SkeletonRows rows={4} />;
  if (questions.isError)
    return (
      <Card>
        <ErrorState message={questions.error.message} onRetry={() => questions.refetch()} />
      </Card>
    );

  const geral = performance.data?.geral;
  const totalQuestions = questions.data?.length ?? 0;

  return (
    <div className="space-y-3">
      <section aria-label="Desempenho em questões" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi
          feature
          tone="accent"
          label="Tentativas"
          value={<NumberTicker value={geral?.respondidas ?? 0} />}
          context={`${integer(geral?.total ?? 0)} questão(ões) com tentativa`}
        />
        <Kpi
          label="Acertos"
          value={<NumberTicker value={geral?.acertos ?? 0} />}
          context={geral?.pct === null || geral?.pct === undefined ? 'Percentual não calculável' : percent(geral.pct)}
        />
        <Kpi
          label="Erros"
          value={<NumberTicker value={geral?.erros ?? 0} />}
          context={`${integer(geral?.brancos ?? 0)} em branco`}
        />
        <Kpi
          label="Disciplinas medidas"
          value={<NumberTicker value={performance.data?.por_disciplina.length ?? 0} />}
          context="Somente com tentativas"
        />
      </section>

      <Card title="Praticar questões" subtitle="Correção no servidor; o gabarito aparece só após responder.">
        {!totalQuestions ? (
          <EmptyState
            title="Nenhuma questão cadastrada"
            description="Crie questões na Operação para praticar aqui. Nenhum conteúdo de terceiros é importado."
          />
        ) : (
          <div className="space-y-2.5">
            {questions.data!.slice(0, visibleCount).map((question) => (
              <QuestionCard key={question.id} question={question} />
            ))}
            {visibleCount < totalQuestions && (
              <div className="pt-2 flex justify-center">
                <Button size="sm" variant="secondary" onClick={() => setVisibleCount((prev) => prev + 12)}>
                  Carregar mais questões ({totalQuestions - visibleCount} restantes)
                </Button>
              </div>
            )}
          </div>
        )}
      </Card>

      {(performance.data?.por_disciplina.length ?? 0) > 0 && (
        <Card title="Desempenho por disciplina" subtitle="Percentual sobre tentativas respondidas.">
          <ul className="divide-y divide-line">
            {performance.data!.por_disciplina.map((item) => (
              <li key={item.grupo} className="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0">
                <div className="min-w-0">
                  <p className="truncate text-xs text-fg">{item.grupo}</p>
                  <p className="text-2xs text-fg-3">
                    {item.acertos} acertos · {item.erros} erros · {item.brancos} em branco
                  </p>
                </div>
                <span className="shrink-0 text-xs font-medium tabular text-fg">
                  {item.pct === null ? '—' : percent(item.pct)}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

function QuestionCard({ question }: { question: Question }) {
  const queryClient = useQueryClient();
  const [answer, setAnswer] = useState<string | null>(null);
  const [result, setResult] = useState<{ correta: boolean; gabarito: string } | null>(null);
  const submit = useMutation({
    mutationFn: (resposta: string) =>
      api.post<{ correta: boolean; gabarito: string }>('/api/estudos/tentativas', {
        questao_id: question.id,
        resposta,
      }),
    onSuccess: (data) => {
      setResult(data);
      void queryClient.invalidateQueries({ queryKey: keys.performance() });
      void queryClient.invalidateQueries({ queryKey: keys.study() });
    },
  });

  return (
    <div className="rounded-sm border border-line bg-surface-2 p-3">
      <p className="text-xs leading-relaxed text-fg">{question.enunciado}</p>
      <p className="mt-1 text-2xs text-fg-3">
        {[question.disciplina, question.topico, question.dificuldade].filter(Boolean).join(' · ') || 'Sem classificação'}
      </p>
      <ul className="mt-2 space-y-1">
        {(question.alternativas ?? []).map((alternative) => (
          <li key={alternative.letra}>
            <label className="flex cursor-pointer items-center gap-2 rounded-xs border border-line bg-surface px-2.5 py-1.5 text-2xs text-fg-2 transition-colors hover:border-line-strong">
              <input
                type="radio"
                name={`q-${question.id}`}
                value={alternative.letra}
                checked={answer === alternative.letra}
                onChange={() => setAnswer(alternative.letra)}
                disabled={Boolean(result)}
                className="accent-[var(--color-accent)]"
              />
              <span>
                {alternative.letra} · {alternative.texto}
              </span>
            </label>
          </li>
        ))}
      </ul>
      <div className="mt-2 flex items-center gap-2">
        <Button
          size="sm"
          variant="primary"
          disabled={!answer || Boolean(result) || submit.isPending}
          onClick={() => answer && submit.mutate(answer)}
        >
          Responder
        </Button>
        {result && (
          <span className={result.correta ? 'text-2xs text-ok-ink' : 'text-2xs text-risk-ink'}>
            {result.correta ? 'Correta' : 'Incorreta'} · gabarito {result.gabarito}
          </span>
        )}
        {submit.isError && <span className="text-2xs text-risk-ink">{(submit.error as Error).message}</span>}
      </div>
    </div>
  );
}
