import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Award,
  BookOpen,
  Check,
  CheckSquare,
  ChevronLeft,
  ChevronRight,
  Clock,
  Clock3,
  Compass,
  DownloadCloud,
  Layers,
  LayoutDashboard,
  Pause,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  Sparkles,
  Square,
  Target,
  Trophy,
  X,
  Zap,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import {
  keys,
  useDisciplines,
  useExams,
  useFlashQueue,
  useFlashStats,
  usePerformance,
  usePortfolio,
  useQuestions,
  useRevisions,
  useSessions,
  useStudyPanel,
  type Exam,
  type Question,
} from '@/app/queries';
import { AreaChart, BarList, DataTableFallback, Meter } from '@/components/charts';
import { PageHeader } from '@/components/layout/page-header';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Kpi, NumberTicker } from '@/components/ui/kpi';
import { EmptyState, ErrorState, SkeletonRows } from '@/components/ui/states';
import { api, syncProgramToStudy } from '@/lib/api';
import { formatTitleCase } from '@/lib/domain';
import { clock, dateTime, duration, integer, percent, shortDate } from '@/lib/format';
import type { StudyPanel, StudySession } from '@/lib/types';
import { LessonsView } from './LessonsView';
import { BancaRadiographyView } from './BancaRadiographyView';
import { StudyScheduleView } from './StudyScheduleView';

const TABS = [
  { path: '', label: 'Visão geral', icon: LayoutDashboard, badge: null },
  { path: '/cronograma', label: 'Ciclo Semanal', icon: Compass, badge: 'IA' },
  { path: '/aulas', label: 'Aulas', icon: BookOpen, badge: 'Trilha' },
  { path: '/bancas', label: 'Bancas', icon: Award, badge: '16' },
  { path: '/sessoes', label: 'Sessões', icon: Clock, badge: null },
  { path: '/questoes', label: 'Questões', icon: CheckSquare, badge: null },
  { path: '/flashcards', label: 'Flashcards', icon: Layers, badge: 'Revisão' },
  { path: '/simulados', label: 'Simulados', icon: Target, badge: 'Rankings' },
] as const;

export function StudiesPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const contestId = searchParams.get('concurso');
  const suffix = location.pathname.replace(/^\/estudos/, '');
  const active = TABS.find((tab) => tab.path === suffix)?.path ?? '';

  return (
    <>
      <PageHeader
        eyebrow="Aprendizagem & Foco"
        title="Estudos"
        description="Sessões, revisões, questões e simulados direcionados para os seus concursos alvo."
      />

      {contestId && (
        <div className="mb-4 flex items-center justify-between gap-3 p-3.5 rounded-lg border border-amber-400/30 bg-amber-400/5 text-xs text-fg">
          <div className="flex items-center gap-2.5 min-w-0">
            <Target size={16} className="text-amber-400 shrink-0" />
            <span className="truncate">
              Foco ativado: visualizando conteúdo e matérias para o concurso selecionado.
            </span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              const next = new URLSearchParams(searchParams);
              next.delete('concurso');
              setSearchParams(next);
            }}
          >
            Ver Todas
          </Button>
        </div>
      )}

      {/* Menu Horizontal Premium Estilo Segmented Control / Dock */}
      <div className="mb-6 rounded-2xl border border-line/80 bg-surface-2/70 p-1.5 shadow-md backdrop-blur-md">
        <div
          role="tablist"
          aria-label="Seções de estudos"
          className="flex items-center gap-1.5 overflow-x-auto scrollbar-none"
        >
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isSelected = active === tab.path;
            const queryParams = contestId ? `?concurso=${encodeURIComponent(contestId)}` : '';
            return (
              <button
                key={tab.path}
                type="button"
                role="tab"
                aria-selected={isSelected}
                onClick={() => navigate(`/estudos${tab.path}${queryParams}`)}
                className={`group relative flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs font-semibold whitespace-nowrap transition-all duration-200 ${
                  isSelected
                    ? 'bg-surface text-fg shadow-sm border border-line ring-1 ring-accent/30'
                    : 'text-fg-3 hover:bg-surface/50 hover:text-fg'
                }`}
              >
                <Icon
                  size={15}
                  className={`shrink-0 transition-colors ${
                    isSelected ? 'text-amber-400' : 'text-fg-3 group-hover:text-fg-2'
                  }`}
                />
                <span>{tab.label}</span>
                {tab.badge && (
                  <span
                    className={`ml-0.5 rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
                      isSelected
                        ? 'bg-amber-400/20 text-amber-300 border border-amber-400/30'
                        : 'bg-surface-2 text-fg-3 border border-line/60 group-hover:text-fg-2'
                    }`}
                  >
                    {tab.badge}
                  </span>
                )}
                {isSelected && (
                  <span className="absolute -bottom-1.5 left-3 right-3 h-0.5 rounded-full bg-accent shadow-xs shadow-accent" />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {active === '' && <Overview />}
      {active === '/cronograma' && <StudyScheduleView />}
      {active === '/aulas' && <LessonsView />}
      {active === '/bancas' && (
        <BancaRadiographyView
          onSelectBancaSimulado={(_banca) => {
            navigate('/estudos/simulados');
          }}
        />
      )}
      {active === '/sessoes' && <SessionsTab />}
      {active === '/questoes' && <QuestionsTab />}
      {active === '/flashcards' && <FlashcardsTab />}
      {active === '/simulados' && <ExamsTab />}
    </>
  );
}

/* ------------------------------------------------------------------ */

function Overview() {
  const navigate = useNavigate();
  const panel = useStudyPanel();
  const sessions = useSessions();
  const revisions = useRevisions();
  const performance = usePerformance();
  const flash = useFlashStats();

  if (panel.isLoading) return <SkeletonRows rows={5} />;
  if (panel.isError)
    return (
      <Card>
        <ErrorState message={panel.error.message} onRetry={() => panel.refetch()} />
      </Card>
    );

  const data = panel.data!;
  const geral = performance.data?.geral;
  const topics = data.conteudo?.topics ?? { done: 0, total: 0, pct: 0 };
  const activity = buildActivity(sessions.data ?? []);
  const empty =
    data.total_segundos === 0 &&
    data.sessoes_concluidas === 0 &&
    topics.total === 0 &&
    data.disciplinas === 0;

  return (
    <div className="space-y-3">
      <section aria-label="Indicadores de estudo" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi
          feature
          tone="accent"
          label="Tempo estudado"
          value={<span className="tabular">{duration(data.total_segundos)}</span>}
          context={`${duration(data.semana_segundos)} nos últimos 7 dias`}
        />
        <Kpi
          label="Sessões concluídas"
          value={<NumberTicker value={data.sessoes_concluidas} />}
          context={data.sessao_aberta ? 'Uma sessão está aberta' : 'Nenhuma sessão aberta'}
        />
        <Kpi
          label="Revisões pendentes"
          value={<NumberTicker value={data.revisoes_pendentes} />}
          context={data.revisoes_pendentes ? 'Agenda de revisão espaçada' : 'Nada vencido'}
        />
        <Kpi
          label="Questões respondidas"
          value={<NumberTicker value={geral?.respondidas ?? 0} />}
          context={
            geral?.pct === null || geral?.pct === undefined
              ? 'Percentual não calculável'
              : `${percent(geral.pct)} de acerto · ${geral.basis}`
          }
        />
      </section>

      {/* Banner Ciclo Semanal Inteligente */}
      <div className="rounded-xl border border-amber-400/30 bg-gradient-to-r from-amber-400/10 via-surface to-surface-2 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-amber-400/15 border border-amber-400/30 flex items-center justify-center text-amber-400 shrink-0">
            <Compass size={20} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-fg">Ciclo Semanal de Estudos Ativo</span>
              <span className="px-1.5 py-0.2 rounded-full text-[9px] font-bold bg-amber-400/20 text-amber-300 border border-amber-400/30 uppercase">
                Recomendado pela IA
              </span>
            </div>
            <p className="text-2xs text-fg-3 mt-0.5">
              Grade intercalada de alta retenção calibrada para a banca do seu concurso foco.
            </p>
          </div>
        </div>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => navigate('/estudos/cronograma')}
          className="gap-1.5 shrink-0 text-xs font-semibold"
        >
          <span>Abrir Ciclo Completo</span>
          <ChevronRight size={13} />
        </Button>
      </div>

      <div className="grid gap-3 xl:grid-cols-[1.3fr_1fr]">
        <Card title="Sessão de estudo" subtitle="O cronômetro roda no servidor; fechar a aba não apaga a sessão.">
          <TimerBlock panel={data} />
        </Card>

        <Card title="Tempo por disciplina" subtitle="Somente sessões concluídas.">
          {!data.minutos_por_disciplina.length ? (
            <EmptyState
              title="Sem tempo registrado"
              description="Conclua uma sessão para ver a distribuição por disciplina."
            />
          ) : (
            <BarList
              ariaLabel="Minutos estudados por disciplina"
              data={data.minutos_por_disciplina.map((item) => ({
                label: formatTitleCase(item.nome),
                value: item.minutos,
                title: `${formatTitleCase(item.nome)}: ${item.minutos} min`,
              }))}
            />
          )}
        </Card>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <Card title="Atividade recente" subtitle="Minutos concluídos por dia nos últimos 14 dias.">
          {activity.every((point) => point.value === 0) ? (
            <EmptyState
              title="Sem atividade registrada"
              description="Conclua uma sessão para alimentar o gráfico."
            />
          ) : (
            <>
              <AreaChart
                data={activity}
                height={186}
                unit="min"
                color="var(--color-verified)"
                ariaLabel="Minutos estudados por dia"
                description="Série temporal com minutos concluídos nos últimos 14 dias."
              />
              <DataTableFallback
                summary="Ver dias em tabela"
                columns={['Dia', 'Minutos']}
                rows={activity.map((point) => [point.label, point.value])}
              />
            </>
          )}
        </Card>

        <Card title="Revisões de hoje" subtitle="Agenda persistida, sem sequência inventada.">
          <RevisionList revisions={revisions.data ?? []} pending={data.revisoes_pendentes} />
        </Card>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <Card title="Progresso do conteúdo" subtitle="Tópicos concluídos sobre o total cadastrado.">
          {topics.total === 0 ? (
            <EmptyState
              title="Nenhum tópico cadastrado"
              description="Crie disciplinas e tópicos na aba Sessões para medir progresso."
            />
          ) : (
            <div className="space-y-3">
              <Meter label="Tópicos" value={topics.done} total={topics.total} />
              <Meter
                label="Geral"
                value={data.conteudo.overall.done}
                total={data.conteudo.overall.total}
                color="var(--color-verified)"
              />
            </div>
          )}
        </Card>

        <Card title="Práticas" subtitle="Estado real do banco de questões e flashcards.">
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-sm border border-line bg-surface-2 p-2.5">
              <p className="text-[9px] font-semibold tracking-[0.1em] text-fg-3 uppercase">Flashcards ativos</p>
              <p className="mt-1 font-display text-lg font-semibold tabular text-fg">
                {integer(flash.data?.ativos ?? 0)}
              </p>
              <p className="mt-0.5 text-2xs text-fg-3">{flash.data?.basis ?? '—'}</p>
            </div>
            <div className="rounded-sm border border-line bg-surface-2 p-2.5">
              <p className="text-[9px] font-semibold tracking-[0.1em] text-fg-3 uppercase">Acerto em questões</p>
              <p className="mt-1 font-display text-lg font-semibold tabular text-fg">
                {geral?.pct === null || geral?.pct === undefined ? '—' : percent(geral.pct)}
              </p>
              <p className="mt-0.5 text-2xs text-fg-3">{geral?.basis ?? 'Sem tentativas'}</p>
            </div>
          </div>
          {empty && (
            <p className="mt-2 text-2xs text-fg-3">
              Comece criando uma disciplina ou importando o conteúdo programático do edital.
            </p>
          )}
        </Card>
      </div>

      <SyncEditalCard />
    </div>
  );
}

function buildActivity(sessions: StudySession[]) {
  const byDay = new Map<string, number>();
  for (const session of sessions) {
    if (session.estado !== 'concluida' || !session.fim) continue;
    const key = session.fim.slice(0, 10);
    byDay.set(key, (byDay.get(key) ?? 0) + Math.round(session.duracao_segundos / 60));
  }
  const points: { label: string; value: number; title: string }[] = [];
  const today = new Date();
  for (let i = 13; i >= 0; i -= 1) {
    const day = new Date(today.getFullYear(), today.getMonth(), today.getDate() - i);
    const key = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`;
    const value = byDay.get(key) ?? 0;
    points.push({
      label: day.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }),
      value,
      title: `${day.toLocaleDateString('pt-BR')}: ${value} min`,
    });
  }
  return points;
}

/* ------------------------------------------------------------------ */

function TimerBlock({ panel }: { panel: StudyPanel }) {
  const queryClient = useQueryClient();
  const disciplines = useDisciplines();
  const session = panel.sessao_aberta;
  const [selected, setSelected] = useState('');
  const [elapsed, setElapsed] = useState(session?.elapsed_seconds ?? 0);

  useEffect(() => {
    setElapsed(session?.elapsed_seconds ?? 0);
    if (!session || session.estado !== 'em_andamento') return;
    const started = Date.now();
    const base = session.elapsed_seconds ?? 0;
    const timer = window.setInterval(() => setElapsed(base + (Date.now() - started) / 1000), 1000);
    return () => window.clearInterval(timer);
  }, [session]);

  const action = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post('/api/estudos/sessoes', body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keys.study() });
      void queryClient.invalidateQueries({ queryKey: keys.sessions() });
    },
  });

  const rawDisciplineName = session?.disciplina_id
    ? disciplines.data?.find((item) => item.id === session.disciplina_id)?.nome
    : null;
  const disciplineName = rawDisciplineName ? formatTitleCase(rawDisciplineName) : null;

  return (
    <div className="flex flex-wrap items-center gap-4">
      <div className="min-w-[132px]">
        <p className="font-mono text-[2rem] leading-none font-semibold tabular text-fg">
          {clock(elapsed)}
        </p>
        <p className="mt-1.5 text-2xs text-fg-3">
          {session
            ? `${session.estado === 'pausada' ? 'Sessão pausada' : 'Sessão em andamento'}${disciplineName ? ` · ${disciplineName}` : ''}`
            : 'Nenhuma sessão aberta'}
        </p>
      </div>

      <div className="flex flex-1 flex-wrap items-center gap-2">
        {!session ? (
          <>
            <select
              value={selected}
              onChange={(event) => setSelected(event.target.value)}
              aria-label="Disciplina da sessão"
              className="h-9 min-w-[150px] rounded-sm border border-line-strong bg-surface-2 px-2.5 text-xs text-fg outline-none focus:border-accent/60"
            >
              <option value="">Sem disciplina</option>
              {disciplines.data?.map((item) => (
                <option key={item.id} value={item.id}>{formatTitleCase(item.nome)}</option>
              ))}
            </select>
            <Button
              variant="primary"
              size="md"
              disabled={action.isPending}
              onClick={() =>
                action.mutate({ action: 'start', disciplina_id: selected || null, modo: 'livre' })
              }
            >
              <Play size={14} /> Iniciar sessão
            </Button>
          </>
        ) : (
          <>
            {session.estado === 'pausada' ? (
              <Button variant="secondary" size="md" onClick={() => action.mutate({ action: 'resume', id: session.id })}>
                <Play size={14} /> Retomar
              </Button>
            ) : (
              <Button variant="secondary" size="md" onClick={() => action.mutate({ action: 'pause', id: session.id })}>
                <Pause size={14} /> Pausar
              </Button>
            )}
            <Button variant="primary" size="md" onClick={() => action.mutate({ action: 'finish', id: session.id })}>
              <Square size={13} /> Concluir
            </Button>
            <Button variant="ghost" size="md" onClick={() => action.mutate({ action: 'discard', id: session.id })}>
              <X size={14} /> Descartar
            </Button>
          </>
        )}
      </div>

      {action.isError && (
        <p className="w-full text-2xs text-risk" role="alert">
          {(action.error as Error).message}
        </p>
      )}
    </div>
  );
}

function RevisionList({
  revisions,
  pending,
}: {
  revisions: { revisao_id: string; progresso_id: string; data: string; topico_id: string }[];
  pending: number;
}) {
  const queryClient = useQueryClient();
  const mark = useMutation({
    mutationFn: (progressoId: string) =>
      api.post('/api/estudos/revisoes', { progresso_id: progressoId, resultado: 'concluida' }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keys.study() });
      void queryClient.invalidateQueries({ queryKey: keys.revisions() });
    },
  });

  if (!revisions.length) {
    return (
      <EmptyState
        title={pending ? 'Revisões em processamento' : 'Nenhuma revisão pendente'}
        description="A agenda aparece quando um tópico é concluído e entra na revisão espaçada."
      />
    );
  }

  return (
    <ul className="divide-y divide-line">
      {revisions.slice(0, 6).map((revision) => (
        <li key={revision.revisao_id} className="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0">
          <div className="min-w-0">
            <p className="truncate text-xs font-medium text-fg">Revisão de {shortDate(revision.data)}</p>
            <p className="mt-0.5 text-2xs text-fg-3">Tópico {revision.topico_id.slice(0, 8)}</p>
          </div>
          <Button
            size="sm"
            variant="ghost"
            disabled={mark.isPending}
            onClick={() => mark.mutate(revision.progresso_id)}
          >
            <Check size={12} /> Revisada
          </Button>
        </li>
      ))}
    </ul>
  );
}

/* ------------------------------------------------------------------ */

function SyncEditalCard({ className = '' }: { className?: string }) {
  const queryClient = useQueryClient();
  const portfolio = usePortfolio({ limit: 40 });
  const [selectedContest, setSelectedContest] = useState('');
  const [feedback, setFeedback] = useState<{ type: 'ok' | 'err'; text: string } | null>(null);

  const sync = useMutation({
    mutationFn: (contestId: string) => syncProgramToStudy(contestId),
    onSuccess: (data) => {
      if (data.ok) {
        setFeedback({
          type: 'ok',
          text: `Sucesso: ${data.disciplinas_importadas} nova(s) disciplina(s) e ${data.topicos_importados} tópico(s) importados para o plano de estudos!`
        });
        void queryClient.invalidateQueries({ queryKey: keys.disciplines() });
        void queryClient.invalidateQueries({ queryKey: keys.study() });
      } else {
        setFeedback({
          type: 'err',
          text: data.mensagem || 'Nenhum conteúdo programático localizado para este concurso.'
        });
      }
    },
    onError: (err) => {
      setFeedback({ type: 'err', text: (err as Error).message });
    },
  });

  const contests = (portfolio.data?.itens ?? []).filter((c) => c.contest_id);

  return (
    <Card
      title="Sincronizar com Edital"
      subtitle="Importe automaticamente disciplinas e tópicos de um concurso analisado para o seu plano de estudos."
      className={className}
    >
      <div className="flex flex-col gap-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={selectedContest}
            onChange={(e) => {
              setSelectedContest(e.target.value);
              setFeedback(null);
            }}
            aria-label="Concurso para importar matérias"
            className="h-9 flex-1 min-w-[220px] rounded-sm border border-line-strong bg-surface-2 px-3 text-xs text-fg outline-none focus:border-accent/60"
          >
            <option value="">Selecione um concurso analisado...</option>
            {contests.map((item) => (
              <option key={item.contest_id} value={item.contest_id}>
                {item.contest_label ?? item.competition_id ?? item.contest_id}
              </option>
            ))}
          </select>
          <Button
            variant="secondary"
            size="md"
            disabled={!selectedContest || sync.isPending}
            onClick={() => {
              if (selectedContest) sync.mutate(selectedContest);
            }}
          >
            <DownloadCloud size={14} /> {sync.isPending ? 'Sincronizando...' : 'Importar Matérias'}
          </Button>
        </div>

        {feedback && (
          <div
            role="alert"
            className={`flex items-center gap-2 rounded-xs border p-2 text-xs ${
              feedback.type === 'ok'
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                : 'border-amber-500/30 bg-amber-500/10 text-amber-300'
            }`}
          >
            <Sparkles size={14} className="shrink-0" />
            <span>{feedback.text}</span>
          </div>
        )}
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ */

function SessionsTab() {
  const queryClient = useQueryClient();
  const disciplines = useDisciplines();
  const sessions = useSessions();
  const [name, setName] = useState('');

  const create = useMutation({
    mutationFn: (nome: string) => api.post('/api/estudos/disciplinas', { nome }),
    onSuccess: () => {
      setName('');
      void queryClient.invalidateQueries({ queryKey: keys.disciplines() });
      void queryClient.invalidateQueries({ queryKey: keys.study() });
    },
  });

  return (
    <div className="space-y-3">
      <SyncEditalCard />

      <Card title="Disciplinas" subtitle="A base do plano de estudos. Tudo fica no banco local.">
        <form
          className="flex flex-wrap gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (name.trim()) create.mutate(name.trim());
          }}
        >
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Nome da disciplina"
            aria-label="Nome da disciplina"
            className="h-9 flex-1 rounded-sm border border-line-strong bg-surface-2 px-3 text-sm text-fg outline-none placeholder:text-fg-3 focus:border-accent/60"
          />
          <Button type="submit" variant="primary" disabled={create.isPending || !name.trim()}>
            <Plus size={14} /> Criar
          </Button>
        </form>
        {create.isError && <p className="mt-2 text-2xs text-risk">{(create.error as Error).message}</p>}

        {disciplines.isLoading ? (
          <SkeletonRows rows={2} className="mt-3" />
        ) : !disciplines.data?.length ? (
          <EmptyState
            title="Nenhuma disciplina criada"
            description="Crie a primeira disciplina para registrar sessões e tópicos."
          />
        ) : (
          <ul className="mt-3 divide-y divide-line">
            {disciplines.data.map((discipline) => (
              <li key={discipline.id} className="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0">
                <span className="truncate text-xs text-fg">{formatTitleCase(discipline.nome)}</span>
                <AddTopic disciplineId={discipline.id} />
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Histórico de sessões" subtitle="Duração e estado calculados pelo servidor.">
        {sessions.isLoading ? (
          <SkeletonRows rows={4} />
        ) : !sessions.data?.length ? (
          <EmptyState
            title="Nenhuma sessão registrada"
            description="Inicie o cronômetro na visão geral."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] border-collapse text-xs">
              <caption className="sr-only">Histórico de sessões</caption>
              <thead>
                <tr className="border-b border-line">
                  {['Início', 'Duração', 'Estado', 'Modo'].map((text) => (
                    <th key={text} scope="col" className="px-2 py-1.5 text-left text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase">
                      {text}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sessions.data.slice(0, 30).map((session) => (
                  <tr key={session.id} className="border-b border-line/60 last:border-0">
                    <td className="px-2 py-2 text-2xs text-fg-2">{dateTime(session.inicio ?? session.created_at)}</td>
                    <td className="px-2 py-2 text-2xs tabular text-fg">{duration(session.duracao_segundos)}</td>
                    <td className="px-2 py-2">
                      <Badge tone={session.estado === 'concluida' ? 'ok' : 'neutral'}>{session.estado}</Badge>
                    </td>
                    <td className="px-2 py-2 text-2xs text-fg-3">{session.modo}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function AddTopic({ disciplineId }: { disciplineId: string }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const create = useMutation({
    mutationFn: (nome: string) => api.post('/api/estudos/topicos', { disciplina_id: disciplineId, nome }),
    onSuccess: () => {
      setName('');
      setOpen(false);
      void queryClient.invalidateQueries({ queryKey: keys.study() });
    },
  });

  if (!open) {
    return (
      <Button size="sm" variant="ghost" onClick={() => setOpen(true)}>
        <Plus size={12} /> Tópico
      </Button>
    );
  }

  return (
    <form
      className="flex items-center gap-1.5"
      onSubmit={(event) => {
        event.preventDefault();
        if (name.trim()) create.mutate(name.trim());
      }}
    >
      <input
        value={name}
        onChange={(event) => setName(event.target.value)}
        placeholder="Tópico"
        aria-label="Nome do tópico"
        autoFocus
        className="h-7 w-32 rounded-xs border border-line-strong bg-surface-2 px-2 text-2xs text-fg outline-none focus:border-accent/60"
      />
      <Button type="submit" size="sm" variant="primary" disabled={create.isPending}>
        <Check size={12} />
      </Button>
      <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
        <X size={12} />
      </Button>
    </form>
  );
}

/* ------------------------------------------------------------------ */

function QuestionsTab() {
  const questions = useQuestions();
  const performance = usePerformance();

  if (questions.isLoading) return <SkeletonRows rows={4} />;
  if (questions.isError)
    return (
      <Card>
        <ErrorState message={questions.error.message} onRetry={() => questions.refetch()} />
      </Card>
    );

  const geral = performance.data?.geral;

  return (
    <div className="space-y-3">
      <section aria-label="Desempenho em questões" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi feature tone="accent" label="Tentativas" value={<NumberTicker value={geral?.respondidas ?? 0} />} context={`${integer(geral?.total ?? 0)} questão(ões) com tentativa`} />
        <Kpi label="Acertos" value={<NumberTicker value={geral?.acertos ?? 0} />} context={geral?.pct === null || geral?.pct === undefined ? 'Percentual não calculável' : percent(geral.pct)} />
        <Kpi label="Erros" value={<NumberTicker value={geral?.erros ?? 0} />} context={`${integer(geral?.brancos ?? 0)} em branco`} />
        <Kpi label="Disciplinas medidas" value={<NumberTicker value={performance.data?.por_disciplina.length ?? 0} />} context="Somente com tentativas" />
      </section>

      <Card title="Praticar questões" subtitle="Correção no servidor; o gabarito aparece só após responder.">
        {!questions.data?.length ? (
          <EmptyState
            title="Nenhuma questão cadastrada"
            description="Crie questões na Operação para praticar aqui. Nenhum conteúdo de terceiros é importado."
          />
        ) : (
          <div className="space-y-2.5">
            {questions.data.slice(0, 8).map((question) => (
              <QuestionCard key={question.id} question={question} />
            ))}
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
  const [answer, setAnswer] = useState<string | null>(null);
  const [result, setResult] = useState<{ correta: boolean; gabarito: string } | null>(null);
  const submit = useMutation({
    mutationFn: (resposta: string) =>
      api.post<{ correta: boolean; gabarito: string }>('/api/estudos/tentativas', {
        questao_id: question.id,
        resposta,
      }),
    onSuccess: (data) => setResult(data),
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
          <span className={result.correta ? 'text-2xs text-ok' : 'text-2xs text-risk'}>
            {result.correta ? 'Correta' : 'Incorreta'} · gabarito {result.gabarito}
          </span>
        )}
        {submit.isError && <span className="text-2xs text-risk">{(submit.error as Error).message}</span>}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */

function FlashcardsTab() {
  const queryClient = useQueryClient();
  const stats = useFlashStats();
  const queue = useFlashQueue();

  const [currentIndex, setCurrentIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [newFront, setNewFront] = useState('');
  const [newBack, setNewBack] = useState('');
  const [newTags, setNewTags] = useState('');

  const cards = useMemo(() => {
    return queue.data ? [...(queue.data.novos ?? []), ...(queue.data.vencidos ?? [])] : [];
  }, [queue.data]);

  const totalCards = cards.length;
  const currentCard = cards[currentIndex] ?? cards[0];

  const review = useMutation({
    mutationFn: (qualidade: number) =>
      api.post('/api/estudos/flashcards', { action: 'review', id: currentCard.id, qualidade }),
    onSuccess: () => {
      setRevealed(false);
      if (currentIndex >= cards.length - 1) {
        setCurrentIndex(0);
      }
      void queryClient.invalidateQueries({ queryKey: keys.flashQueue() });
      void queryClient.invalidateQueries({ queryKey: keys.flashStats() });
    },
  });

  const createCard = useMutation({
    mutationFn: (body: { action: string; frente: string; verso: string; tags: string[] }) =>
      api.post('/api/estudos/flashcards', body),
    onSuccess: () => {
      setShowCreate(false);
      setNewFront('');
      setNewBack('');
      setNewTags('');
      void queryClient.invalidateQueries({ queryKey: keys.flashQueue() });
      void queryClient.invalidateQueries({ queryKey: keys.flashStats() });
    },
  });

  if (stats.isLoading || queue.isLoading) return <SkeletonRows rows={4} />;

  return (
    <div className="space-y-4">
      {/* Indicadores de Estudo com Flashcards */}
      <section aria-label="Indicadores de flashcards" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <Kpi
          feature
          tone="accent"
          label="Cartões ativos"
          value={<NumberTicker value={stats.data?.ativos ?? 0} />}
          context={`${integer(stats.data?.novos ?? 0)} novos · ${integer(stats.data?.pendentes ?? 0)} para hoje`}
        />
        <Kpi
          label="Revisões registradas"
          value={<NumberTicker value={stats.data?.revisoes ?? 0} />}
          context={stats.data?.basis ?? 'Algoritmo SM-2-lite ativo'}
        />
        <Kpi
          label="Arquivados"
          value={<NumberTicker value={stats.data?.arquivados ?? 0} />}
          context="Fora da fila de repetição"
        />
      </section>

      {/* Barra de Ações: Criar Flashcard */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="flex size-6 items-center justify-center rounded-lg bg-amber-400/15 text-amber-400">
            <Zap size={14} />
          </span>
          <span className="text-xs font-bold text-fg">
            Sessão de Revisão Espaçada (SM-2)
          </span>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setShowCreate(!showCreate)}
          className="gap-1.5"
        >
          <Plus size={14} /> Novo Flashcard
        </Button>
      </div>

      {/* Formulário de Criação (Drawer/Card) */}
      {showCreate && (
        <Card title="Criar Novo Flashcard" subtitle="Adicione uma pergunta ou conceito para memorização ativa.">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!newFront.trim() || !newBack.trim()) return;
              createCard.mutate({
                action: 'create',
                frente: newFront.trim(),
                verso: newBack.trim(),
                tags: newTags.split(',').map((t) => t.trim()).filter(Boolean),
              });
            }}
            className="space-y-3"
          >
            <div>
              <label className="text-2xs font-semibold uppercase tracking-wider text-fg-3">Frente (Pergunta / Conceito)</label>
              <textarea
                value={newFront}
                onChange={(e) => setNewFront(e.target.value)}
                placeholder="Ex: O que é o Teorema CAP em bancos NoSQL?"
                required
                className="mt-1 w-full rounded-xl border border-line bg-surface-2 p-3 text-xs text-fg placeholder:text-fg-3/60 focus:border-amber-400 focus:outline-none"
                rows={2}
              />
            </div>
            <div>
              <label className="text-2xs font-semibold uppercase tracking-wider text-fg-3">Verso (Resposta / Explicação)</label>
              <textarea
                value={newBack}
                onChange={(e) => setNewBack(e.target.value)}
                placeholder="Ex: Em sistemas distribuídos, só é possível garantir 2 de 3 propriedades: Consistência, Disponibilidade e Tolerância a Partições."
                required
                className="mt-1 w-full rounded-xl border border-line bg-surface-2 p-3 text-xs text-fg placeholder:text-fg-3/60 focus:border-amber-400 focus:outline-none"
                rows={3}
              />
            </div>
            <div>
              <label className="text-2xs font-semibold uppercase tracking-wider text-fg-3">Tags (separadas por vírgula)</label>
              <input
                type="text"
                value={newTags}
                onChange={(e) => setNewTags(e.target.value)}
                placeholder="banco-de-dados, nosql, ti"
                className="mt-1 w-full rounded-xl border border-line bg-surface-2 px-3 py-2 text-xs text-fg placeholder:text-fg-3/60 focus:border-amber-400 focus:outline-none"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" size="sm" onClick={() => setShowCreate(false)}>Cancelar</Button>
              <Button variant="primary" size="sm" type="submit" disabled={createCard.isPending}>
                Salvar Flashcard
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* Arena de Revisão Ativa / Fila */}
      {!cards.length ? (
        <Card>
          <div className="py-10 text-center space-y-3">
            <div className="mx-auto flex size-12 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Trophy size={24} />
            </div>
            <h3 className="text-sm font-bold text-fg">Fila de Flashcards Zerada!</h3>
            <p className="text-xs text-fg-3 max-w-md mx-auto">
              {(queue.data?.futuros.length ?? 0) > 0
                ? `${queue.data!.futuros.length} cartão(ões) agendado(s) para os próximos ciclos de repetição espaçada.`
                : 'Você revisou todos os cartões disponíveis. Continue estudando nas Aulas e Questões ou crie novos cartões.'}
            </p>
          </div>
        </Card>
      ) : (
        <div className="space-y-4">
          {/* Cartão de Estudo em Destaque (Flip Card) */}
          <div className="relative overflow-hidden rounded-2xl border border-line bg-surface shadow-md">
            {/* Topbar do Flashcard */}
            <div className="flex items-center justify-between border-b border-line px-5 py-3 text-xs bg-surface-2/40">
              <span className="font-mono text-2xs font-semibold text-fg-3">
                Cartão {currentIndex + 1} de {totalCards} na fila
              </span>
              <div className="flex items-center gap-1.5">
                {((currentCard.tags ?? []) as string[]).slice(0, 3).map((tag: string) => (
                  <Badge key={tag} tone="neutral" className="text-[10px]">
                    {tag.toUpperCase()}
                  </Badge>
                ))}
              </div>
            </div>

            {/* Conteúdo do Cartão */}
            <div
              onClick={() => setRevealed(!revealed)}
              className="p-6 sm:p-8 cursor-pointer select-none transition-colors hover:bg-surface-2/30 min-h-[200px] flex flex-col justify-between"
            >
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400">
                  {revealed ? 'Resposta (Verso)' : 'Pergunta (Frente)'}
                </span>
                <p className="mt-3 text-base sm:text-lg font-bold text-fg leading-relaxed">
                  {currentCard.frente}
                </p>

                {revealed && (
                  <div className="mt-5 border-t border-line/80 pt-4 text-sm text-fg-2 leading-relaxed whitespace-pre-line font-medium">
                    {currentCard.verso}
                  </div>
                )}
              </div>

              {!revealed && (
                <p className="mt-6 text-2xs text-fg-3 flex items-center gap-1.5">
                  <RotateCcw size={12} className="text-amber-400" />
                  Clique em qualquer lugar do cartão para virar e conferir a resposta
                </p>
              )}
            </div>

            {/* Avaliação SM-2 */}
            <div className="border-t border-line bg-surface-2/60 p-4">
              {!revealed ? (
                <div className="flex justify-center">
                  <Button
                    variant="primary"
                    size="md"
                    onClick={() => setRevealed(true)}
                    className="w-full sm:w-auto px-8 gap-2 font-bold"
                  >
                    Mostrar Resposta
                  </Button>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-center text-2xs font-semibold text-fg-3 uppercase tracking-wider">
                    Como foi a sua recordação? (Algoritmo SM-2)
                  </p>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 max-w-xl mx-auto">
                    <button
                      type="button"
                      disabled={review.isPending}
                      onClick={() => review.mutate(1)}
                      className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-2.5 text-center text-xs font-bold text-rose-300 hover:bg-rose-500/20 transition-all"
                    >
                      <span className="block text-2xs text-rose-400 font-normal">1 dia</span>
                      Errei (1)
                    </button>
                    <button
                      type="button"
                      disabled={review.isPending}
                      onClick={() => review.mutate(2)}
                      className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-2.5 text-center text-xs font-bold text-amber-300 hover:bg-amber-500/20 transition-all"
                    >
                      <span className="block text-2xs text-amber-400 font-normal">Difícil</span>
                      Difícil (2)
                    </button>
                    <button
                      type="button"
                      disabled={review.isPending}
                      onClick={() => review.mutate(3)}
                      className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-2.5 text-center text-xs font-bold text-cyan-300 hover:bg-cyan-500/20 transition-all"
                    >
                      <span className="block text-2xs text-cyan-400 font-normal">Normal</span>
                      Bom (3)
                    </button>
                    <button
                      type="button"
                      disabled={review.isPending}
                      onClick={() => review.mutate(5)}
                      className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-2.5 text-center text-xs font-bold text-emerald-300 hover:bg-emerald-500/20 transition-all"
                    >
                      <span className="block text-2xs text-emerald-400 font-normal">Fácil</span>
                      Fácil (5)
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Navegação entre cartões */}
          <div className="flex items-center justify-between text-xs text-fg-3 px-1">
            <button
              type="button"
              disabled={currentIndex <= 0}
              onClick={() => {
                setRevealed(false);
                setCurrentIndex((i) => Math.max(0, i - 1));
              }}
              className="flex items-center gap-1 hover:text-fg disabled:opacity-30 disabled:pointer-events-none"
            >
              <ChevronLeft size={14} /> Cartão Anterior
            </button>
            <button
              type="button"
              disabled={currentIndex >= totalCards - 1}
              onClick={() => {
                setRevealed(false);
                setCurrentIndex((i) => Math.min(totalCards - 1, i + 1));
              }}
              className="flex items-center gap-1 hover:text-fg disabled:opacity-30 disabled:pointer-events-none"
            >
              Próximo Cartão <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */

function ExamsTab() {
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
        {create.isError && <p className="mt-2 text-2xs text-risk">{(create.error as Error).message}</p>}
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
  const [items, setItems] = useState<
    { ordem: number; questao_id: string; enunciado: string; alternativas: { letra: string; texto: string }[]; resposta?: string }[]
    | null
  >(null);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .get<{ questoes: typeof items }>(`/api/estudos/simulados/${encodeURIComponent(exam.id)}/questoes`)
      .then((payload) => {
        if (!alive) return;
        setItems(payload.questoes ?? []);
      })
      .catch((err: Error) => alive && setError(err.message));
    return () => {
      alive = false;
    };
  }, [exam.id]);

  const finish = async () => {
    try {
      for (const [ordem, resposta] of Object.entries(answers)) {
        await api.post(`/api/estudos/simulados/${encodeURIComponent(exam.id)}/responder`, {
          ordem: Number(ordem),
          resposta,
        });
      }
      await api.post(`/api/estudos/simulados/${encodeURIComponent(exam.id)}/finalizar`, {});
      const payload = await api.get<{ resultado: Record<string, unknown> }>(
        `/api/estudos/simulados/${encodeURIComponent(exam.id)}/resultado`,
      );
      setResult(payload.resultado ?? payload);
    } catch (err) {
      setError((err as Error).message);
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
      {error && <p className="mb-2 text-2xs text-risk">{error}</p>}
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
            <Button size="sm" variant="primary" onClick={finish}>
              <Clock3 size={12} /> Finalizar
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

