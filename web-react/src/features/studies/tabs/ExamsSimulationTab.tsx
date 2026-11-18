import { useEffect, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Clock3, Plus, RefreshCw, X } from 'lucide-react';
import { keys, useExams, type Exam } from '@/app/queries';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { EmptyState, SkeletonRows } from '@/components/ui/states';
import { api } from '@/lib/api';
import { duration, integer, percent } from '@/lib/format';

export function ExamsSimulationTab() {
  const queryClient = useQueryClient();
  const exams = useExams();
  const [name, setName] = useState('');
  const [limit, setLimit] = useState('10');
  const [minutes, setMinutes] = useState('');
  const [openExam, setOpenExam] = useState<Exam | null>(null);

  const create = useMutation({
    mutationFn: () =>
      api.post('/api/estudos/simulados', {
        nome: name.trim() || 'Simulado',
        limit: Number(limit) || 10,
        duracao_segundos: Number(minutes) > 0 ? Number(minutes) * 60 : null,
      }),
    onSuccess: () => {
      setName('');
      void queryClient.invalidateQueries({ queryKey: keys.exams() });
    },
  });

  return (
    <div className="space-y-3">
      <Card title="Montar simulado" subtitle="Questões sem repetição; o tempo é controlado pelo servidor.">
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate();
          }}
        >
          <label className="flex min-w-[180px] flex-1 flex-col gap-1">
            <span className="text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase">Nome</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Simulado"
              className="h-9 rounded-sm border border-line-strong bg-surface-2 px-3 text-sm text-fg outline-none placeholder:text-fg-3 focus:border-accent/60"
            />
          </label>
          <label className="flex w-24 flex-col gap-1">
            <span className="text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase">Questões</span>
            <input
              type="number"
              min={1}
              max={100}
              value={limit}
              onChange={(event) => setLimit(event.target.value)}
              className="h-9 rounded-sm border border-line-strong bg-surface-2 px-2 text-sm tabular text-fg outline-none focus:border-accent/60"
            />
          </label>
          <label className="flex w-28 flex-col gap-1">
            <span className="text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase">Minutos</span>
            <input
              type="number"
              min={0}
              value={minutes}
              onChange={(event) => setMinutes(event.target.value)}
              placeholder="livre"
              className="h-9 rounded-sm border border-line-strong bg-surface-2 px-2 text-sm tabular text-fg outline-none placeholder:text-fg-3 focus:border-accent/60"
            />
          </label>
          <Button type="submit" variant="primary" disabled={create.isPending}>
            <Plus size={14} /> Criar simulado
          </Button>
        </form>
        {create.isError && <p className="mt-2 text-2xs text-risk-ink">{(create.error as Error).message}</p>}
      </Card>

      <Card title="Simulados" subtitle="Abra para responder ou ver o resultado.">
        {exams.isLoading ? (
          <SkeletonRows rows={3} />
        ) : !exams.data?.length ? (
          <EmptyState
            title="Nenhum simulado criado"
            description="Monte o primeiro simulado acima. Não há conteúdo de terceiros."
          />
        ) : (
          <ul className="divide-y divide-line">
            {exams.data.map((exam) => (
              <li key={exam.id} className="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0">
                <div className="min-w-0">
                  <p className="truncate text-xs font-medium text-fg">{exam.nome}</p>
                  <p className="mt-0.5 text-2xs text-fg-3">
                    {exam.modo} · {exam.duracao_segundos ? duration(exam.duracao_segundos) : 'sem limite'}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Badge tone={exam.estado === 'finalizado' ? 'ok' : exam.estado === 'expirado' ? 'warn' : 'accent'}>
                    {exam.estado}
                  </Badge>
                  <Button size="sm" variant="ghost" onClick={() => setOpenExam(exam)}>
                    {exam.estado === 'em_andamento' ? 'Continuar' : 'Abrir'}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {openExam && (
        <ExamRunner
          key={openExam.id}
          exam={openExam}
          onClose={() => {
            setOpenExam(null);
            void queryClient.invalidateQueries({ queryKey: keys.exams() });
          }}
        />
      )}
    </div>
  );
}

function ExamRunner({ exam, onClose }: { exam: Exam; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [items, setItems] = useState<
    | {
        ordem: number;
        questao_id: string;
        enunciado: string;
        alternativas: { letra: string; texto: string }[];
        resposta?: string;
      }[]
    | null
  >(null);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    if (exam.estado === 'finalizado' || exam.estado === 'expirado') {
      api
        .get<{ resultado?: Record<string, unknown> }>(
          `/api/estudos/simulados/${encodeURIComponent(exam.id)}/resultado`,
        )
        .then((payload) => {
          if (!alive) return;
          setResult((payload.resultado ?? payload) as Record<string, unknown>);
        })
        .catch((err: Error) => alive && setError(err.message));
      return () => {
        alive = false;
      };
    }

    api
      .get<{ questoes: typeof items }>(`/api/estudos/simulados/${encodeURIComponent(exam.id)}/questoes`)
      .then((payload) => {
        if (!alive) return;
        const list = payload.questoes ?? [];
        setItems(list);
        const initial: Record<number, string> = {};
        for (const item of list) {
          if (item.resposta) initial[item.ordem] = item.resposta;
        }
        setAnswers(initial);
      })
      .catch((err: Error) => alive && setError(err.message));
    return () => {
      alive = false;
    };
  }, [exam.id, exam.estado]);

  const finish = async () => {
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await Promise.all(
        Object.entries(answers).map(([ordem, resposta]) =>
          api.post(`/api/estudos/simulados/${encodeURIComponent(exam.id)}/responder`, {
            ordem: Number(ordem),
            resposta,
          }),
        ),
      );
      await api.post(`/api/estudos/simulados/${encodeURIComponent(exam.id)}/finalizar`, {});
      const payload = await api.get<{ resultado?: Record<string, unknown> }>(
        `/api/estudos/simulados/${encodeURIComponent(exam.id)}/resultado`,
      );
      setResult((payload.resultado ?? payload) as Record<string, unknown>);
      void queryClient.invalidateQueries({ queryKey: keys.performance() });
      void queryClient.invalidateQueries({ queryKey: keys.study() });
      void queryClient.invalidateQueries({ queryKey: keys.exams() });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card
      title={exam.nome}
      subtitle="Responda e finalize; o resultado é calculado no servidor."
      action={
        <Button size="sm" variant="ghost" onClick={onClose}>
          <X size={13} /> Fechar
        </Button>
      }
    >
      {error && <p className="mb-2 text-2xs text-risk-ink">{error}</p>}
      {result ? (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-sm border border-line bg-surface-2 p-2.5">
              <p className="text-[9px] uppercase tracking-[0.1em] text-fg-3">Acertos</p>
              <p className="mt-1 font-display text-lg font-semibold tabular text-fg">
                {integer(result.acertos as number)}/{integer(result.total as number)}
              </p>
            </div>
            <div className="rounded-sm border border-line bg-surface-2 p-2.5">
              <p className="text-[9px] uppercase tracking-[0.1em] text-fg-3">Brancos</p>
              <p className="mt-1 font-display text-lg font-semibold tabular text-fg">
                {integer(result.brancos as number)}
              </p>
            </div>
            <div className="rounded-sm border border-line bg-surface-2 p-2.5">
              <p className="text-[9px] uppercase tracking-[0.1em] text-fg-3">Percentual</p>
              <p className="mt-1 font-display text-lg font-semibold tabular text-fg">
                {result.pct === null || result.pct === undefined ? '—' : percent(result.pct as number)}
              </p>
            </div>
          </div>
          <p className="text-2xs text-fg-3">{String(result.basis ?? '')}</p>
          <Button size="sm" variant="ghost" onClick={onClose}>
            <RefreshCw size={12} /> Voltar aos simulados
          </Button>
        </div>
      ) : !items ? (
        <SkeletonRows rows={3} />
      ) : !items.length ? (
        <EmptyState title="Simulado sem questões" description="Não há questões elegíveis para os filtros usados." />
      ) : (
        <div>
          <p className="text-2xs text-fg-3">
            Questão {index + 1} de {items.length}
          </p>
          <p className="mt-1 text-xs font-medium text-fg">{items[index].enunciado}</p>
          <ul className="mt-2 space-y-1">
            {items[index].alternativas.map((alternative) => (
              <li key={alternative.letra}>
                <label className="flex cursor-pointer items-center gap-2 rounded-xs border border-line bg-surface-2 px-2.5 py-1.5 text-2xs text-fg-2 hover:border-line-strong">
                  <input
                    type="radio"
                    name={`exam-${exam.id}`}
                    checked={answers[items[index].ordem] === alternative.letra}
                    onChange={() =>
                      setAnswers((current) => ({ ...current, [items[index].ordem]: alternative.letra }))
                    }
                    className="accent-[var(--color-accent)]"
                  />
                  <span>
                    {alternative.letra} · {alternative.texto}
                  </span>
                </label>
              </li>
            ))}
          </ul>
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            <Button size="sm" variant="ghost" disabled={index === 0} onClick={() => setIndex((i) => i - 1)}>
              Anterior
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={index >= items.length - 1}
              onClick={() => setIndex((i) => i + 1)}
            >
              Próxima
            </Button>
            <Button size="sm" variant="primary" disabled={submitting} onClick={finish}>
              <Clock3 size={12} /> {submitting ? 'Finalizando...' : 'Finalizar'}
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
