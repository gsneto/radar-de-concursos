import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  Award,
  BookOpen,
  CalendarCheck2,
  CheckCircle2,
  ChevronRight,
  Clock,
  Layers,
  Sparkles,
  Target,
} from 'lucide-react';
import {
  useAuthMe,
  useExams,
  useFlashStats,
  useLessons,
  usePerformance,
  useSessions,
  useStudyPanel,
} from '@/app/queries';
import { BarList, Ring } from '@/components/charts';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { Kpi } from '@/components/ui/kpi';
import { EmptyState } from '@/components/ui/states';
import { cn } from '@/lib/cn';
import { dateTime, duration, integer, percent } from '@/lib/format';
import {
  LESSON_STAGES,
  useLessonStageProgress,
  useStudentActivityLog,
} from '@/lib/lesson-progress';
import { useUserStorage } from '@/lib/user-storage';

type TimelineCategory = 'all' | 'aulas' | 'questoes' | 'flashcards' | 'sessoes';

interface UnifiedHistoryItem {
  id: string;
  category: Exclude<TimelineCategory, 'all'>;
  title: string;
  subtitle?: string;
  badgeText?: string;
  badgeTone?: 'ok' | 'accent' | 'verified' | 'neutral';
  lessonId?: string;
  timestamp: string;
}

export function StudentJourneyDashboard() {
  const authMe = useAuthMe();
  const userId = authMe.data?.user?.id ?? null;
  const authReady = !authMe.isLoading;

  const [completedLessons] = useUserStorage<string[]>(
    'completed_lessons',
    [],
    userId,
    'radar_completed_lessons',
    authReady,
  );
  const stageProgress = useLessonStageProgress(userId, authReady);
  const { activities } = useStudentActivityLog(userId, authReady);

  const lessonsQuery = useLessons();
  const studyPanel = useStudyPanel();
  const performance = usePerformance();
  const sessions = useSessions();
  const exams = useExams();
  const flashStats = useFlashStats();

  const [categoryFilter, setCategoryFilter] = useState<TimelineCategory>('all');

  const lessons = lessonsQuery.data?.aulas ?? [];

  const lessonBreakdown = useMemo(() => {
    return lessons.map((lesson) => {
      const done = completedLessons.includes(lesson.id);
      const completedStages = stageProgress.getCompletedStages(lesson.id);
      const pct = stageProgress.getLessonPercent(lesson.id, done);
      return {
        lesson,
        done: done || pct === 100,
        completedStages,
        stagesDoneCount: done ? LESSON_STAGES.length : completedStages.length,
        pct,
      };
    });
  }, [lessons, completedLessons, stageProgress]);

  const totalPossibleStages = lessons.length * LESSON_STAGES.length;
  const totalCompletedStages = lessonBreakdown.reduce((acc, item) => acc + item.stagesDoneCount, 0);
  const overallLessonPct =
    totalPossibleStages > 0 ? Math.round((totalCompletedStages / totalPossibleStages) * 100) : 0;
  const completedLessonsCount = lessonBreakdown.filter((item) => item.done).length;

  const unifiedTimeline = useMemo<UnifiedHistoryItem[]>(() => {
    const list: UnifiedHistoryItem[] = [];

    for (const act of activities) {
      const category: Exclude<TimelineCategory, 'all'> =
        act.type === 'flashcard_salvo'
          ? 'flashcards'
          : act.type === 'questao_respondida'
            ? 'questoes'
            : 'aulas';
      list.push({
        id: act.id,
        category,
        title: act.title,
        subtitle: act.subtitle || act.disciplina,
        badgeText:
          act.pct !== undefined
            ? `${act.pct}%`
            : act.type === 'flashcard_salvo'
              ? 'SM-2'
              : act.correct !== undefined
                ? act.correct
                  ? 'Acerto'
                  : 'Revisão'
                : act.disciplina,
        badgeTone:
          act.pct === 100 || act.correct === true
            ? 'ok'
            : act.type === 'flashcard_salvo'
              ? 'verified'
              : 'accent',
        lessonId: act.lessonId,
        timestamp: act.timestamp,
      });
    }

    for (const s of Array.isArray(sessions.data) ? sessions.data : []) {
      const ts =
        (s as unknown as { encerrada_em?: string; iniciada_em?: string; started_at?: string }).encerrada_em ||
        (s as unknown as { iniciada_em?: string; started_at?: string }).iniciada_em ||
        (s as unknown as { started_at?: string }).started_at ||
        '';
      const secs =
        (s as unknown as { segundos_acumulados?: number; elapsed_seconds?: number }).segundos_acumulados ??
        (s as unknown as { elapsed_seconds?: number }).elapsed_seconds ??
        0;
      if (!ts) continue;
      list.push({
        id: `sess-${s.id}`,
        category: 'sessoes',
        title: `Sessão de estudo (${s.modo || 'livre'}) — ${duration(secs)}`,
        subtitle: `Estado: ${s.estado}`,
        badgeText: duration(secs),
        badgeTone: s.estado === 'concluida' ? 'ok' : 'neutral',
        timestamp: ts,
      });
    }

    for (const ex of Array.isArray(exams.data) ? exams.data : []) {
      const ts =
        (ex as unknown as { criado_em?: string; created_at?: string }).criado_em ||
        (ex as unknown as { created_at?: string }).created_at ||
        '';
      list.push({
        id: `exam-${ex.id}`,
        category: 'questoes',
        title: `${ex.nome}`,
        subtitle: `Simulado ${ex.modo} · ${ex.estado}`,
        badgeText: ex.estado === 'finalizado' ? 'Finalizado' : 'Simulado',
        badgeTone: ex.estado === 'finalizado' ? 'ok' : 'accent',
        timestamp: ts || '1970-01-01T00:00:00Z',
      });
    }

    return list.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
  }, [activities, sessions.data, exams.data]);

  const activeDaysCount = useMemo(() => {
    const days = new Set<string>();
    for (const item of unifiedTimeline) {
      if (item.timestamp && !item.timestamp.startsWith('1970-')) {
        days.add(item.timestamp.slice(0, 10));
      }
    }
    return days.size;
  }, [unifiedTimeline]);

  const filteredTimeline = useMemo(
    () =>
      categoryFilter === 'all'
        ? unifiedTimeline
        : unifiedTimeline.filter((item) => item.category === categoryFilter),
    [unifiedTimeline, categoryFilter],
  );

  const perfGeneral = performance.data?.geral;
  const perfByDisc = performance.data?.por_disciplina ?? [];

  return (
    <div className="space-y-5">
      {/* 1. Hero Bento de Evolução Geral + KPIs Reais */}
      <div className="grid gap-4 lg:grid-cols-[1.15fr_2fr]">
        <div className="flex items-center gap-5 rounded-2xl border border-line bg-gradient-to-br from-surface to-surface-2 p-5 shadow-sm">
          <Ring
            value={totalCompletedStages}
            total={Math.max(1, totalPossibleStages)}
            size={92}
            thickness={9}
            color="var(--color-ok)"
            label="Etapas concluídas na trilha"
          >
            <div className="text-center">
              <span className="font-display text-xl font-black tabular text-fg">{overallLessonPct}%</span>
              <span className="block text-[9px] font-bold uppercase tracking-wider text-fg-3">Trilha</span>
            </div>
          </Ring>

          <div className="min-w-0 space-y-1.5">
            <div className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-ok-ink">
              <Sparkles size={11} /> Painel Pessoal de Evolução
            </div>
            <h2 className="font-display text-lg font-bold text-fg leading-snug">
              Domínio por Etapa & Histórico Completo
            </h2>
            <p className="text-xs text-fg-3">
              <strong className="text-fg">{totalCompletedStages}</strong> de{' '}
              <strong className="text-fg">{totalPossibleStages}</strong> etapas concluídas ·{' '}
              <strong className="text-ok-ink">{completedLessonsCount}</strong>/{lessons.length} aulas em 100%
            </p>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Kpi
            tone="accent"
            label="Tempo Estudado"
            value={duration(studyPanel.data?.total_segundos ?? 0)}
            context={`${integer(studyPanel.data?.sessoes_concluidas ?? 0)} sessões concluídas`}
          />
          <Kpi
            tone="accent"
            label="Acerto em Questões"
            value={
              perfGeneral?.pct !== null && perfGeneral?.pct !== undefined
                ? percent(perfGeneral.pct)
                : '—'
            }
            context={`${integer(perfGeneral?.respondidas ?? 0)} questões respondidas`}
          />
          <Kpi
            label="Flashcards SM-2"
            value={integer(flashStats.data?.ativos ?? 0)}
            context={`${integer(flashStats.data?.revisoes ?? 0)} revisões registradas`}
          />
          <Kpi
            label="Dias Ativos"
            value={integer(activeDaysCount)}
            context="Dias com estudo real registrado"
          />
        </div>
      </div>

      {/* 2. Mapa de Porcentagem por Aula (5 etapas) + Desempenho por Disciplina */}
      <div className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
        <Card
          title="Porcentagem por Aula & Etapas Concluídas"
          subtitle="Cada etapa concluída soma 20% (Resumo · Quadro · Vídeo · Flashcards · Questões)."
        >
          {lessons.length === 0 ? (
            <EmptyState
              title="Nenhuma aula disponível"
              description="Abra a aba Aulas & Teoria para iniciar sua trilha estruturada."
            />
          ) : (
            <ul className="divide-y divide-line">
              {lessonBreakdown.map(({ lesson, completedStages, done, pct }) => (
                <li key={lesson.id} className="py-3 first:pt-0 last:pb-0 space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <Badge tone={done ? 'ok' : pct > 0 ? 'accent' : 'neutral'}>
                          {lesson.disciplina}
                        </Badge>
                        <span className="font-display text-sm font-extrabold tabular text-ok-ink">
                          {pct}%
                        </span>
                      </div>
                      <p className="mt-1 truncate text-xs font-semibold text-fg">{lesson.titulo}</p>
                    </div>

                    <Link
                      to={`/estudos/aulas?aula=${encodeURIComponent(lesson.id)}`}
                      className="shrink-0 inline-flex items-center gap-1 rounded-lg border border-line-strong bg-surface-2 px-2.5 py-1.5 text-2xs font-bold text-fg hover:border-accent/50 hover:text-accent-ink transition-colors"
                    >
                      {pct === 100 ? 'Revisar' : pct > 0 ? 'Continuar' : 'Iniciar'}
                      <ChevronRight size={12} />
                    </Link>
                  </div>

                  {/* Barra de 5 etapas individuais */}
                  <div className="grid grid-cols-5 gap-1.5">
                    {LESSON_STAGES.map((st) => {
                      const stageDone = done || completedStages.includes(st.key);
                      return (
                        <div key={st.key} className="space-y-0.5">
                          <div
                            className={cn(
                              'h-1.5 w-full rounded-full transition-colors',
                              stageDone ? 'bg-emerald-500' : 'bg-surface-2',
                            )}
                          />
                          <span
                            className={cn(
                              'block truncate text-[10px]',
                              stageDone ? 'font-bold text-ok-ink' : 'text-fg-3',
                            )}
                          >
                            {st.number}. {st.shortLabel}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card
          title="Aproveitamento por Disciplina"
          subtitle="Percentual real calculado sobre questões e simulados respondidos."
        >
          {perfByDisc.length === 0 ? (
            <EmptyState
              title="Sem questões respondidas ainda"
              description="Resolva questões nas aulas ou inicie um simulado em 1 clique para gerar o gráfico."
            />
          ) : (
            <BarList
              ariaLabel="Aproveitamento percentual por disciplina"
              data={perfByDisc.map((d) => ({
                label: `${d.grupo} (${d.acertos}/${d.total})`,
                value: Math.round(d.pct ?? 0),
                color: (d.pct ?? 0) >= 70 ? 'var(--color-ok)' : 'var(--color-accent)',
              }))}
            />
          )}
        </Card>
      </div>

      {/* 3. Linha do Tempo Completa: Tudo o que você fez */}
      <Card
        title="Histórico Completo — Tudo o que você fez"
        subtitle="Registro cronológico unificado de etapas de aula, questões, simulados, flashcards e sessões."
      >
        <div className="mb-4 flex flex-wrap items-center gap-1.5">
          {(
            [
              { id: 'all', label: 'Tudo', icon: Activity },
              { id: 'aulas', label: 'Aulas & Etapas', icon: BookOpen },
              { id: 'questoes', label: 'Questões & Simulados', icon: Target },
              { id: 'flashcards', label: 'Flashcards', icon: Layers },
              { id: 'sessoes', label: 'Sessões', icon: Clock },
            ] as const
          ).map((tab) => {
            const Icon = tab.icon;
            const active = categoryFilter === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setCategoryFilter(tab.id)}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold border transition-colors',
                  active
                    ? 'border-accent/50 bg-accent/15 text-accent-ink font-bold'
                    : 'border-line bg-surface-2/60 text-fg-2 hover:text-fg',
                )}
              >
                <Icon size={13} />
                {tab.label}
              </button>
            );
          })}
        </div>

        {filteredTimeline.length === 0 ? (
          <EmptyState
            title="Ainda não há atividades registradas"
            description="Conclua etapas de uma aula, salve flashcards ou finalize um simulado para construir seu histórico completo."
          />
        ) : (
          <ol className="relative border-l border-line-strong ml-3 space-y-3 pl-5">
            {filteredTimeline.map((item) => (
              <li key={item.id} className="relative rounded-xl border border-line bg-surface-2/40 p-3">
                <span className="absolute -left-[27px] top-3.5 flex size-3.5 items-center justify-center rounded-full border-2 border-emerald-500 bg-surface" />
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      {item.category === 'aulas' && <CheckCircle2 size={14} className="text-ok-ink shrink-0" />}
                      {item.category === 'questoes' && <Award size={14} className="text-accent-ink shrink-0" />}
                      {item.category === 'flashcards' && <Layers size={14} className="text-info-ink shrink-0" />}
                      {item.category === 'sessoes' && <CalendarCheck2 size={14} className="text-fg-2 shrink-0" />}
                      <p className="text-xs font-semibold text-fg">{item.title}</p>
                      {item.badgeText && (
                        <Badge tone={item.badgeTone ?? 'neutral'}>{item.badgeText}</Badge>
                      )}
                    </div>
                    {item.subtitle && (
                      <p className="mt-0.5 text-2xs text-fg-3">{item.subtitle}</p>
                    )}
                  </div>

                  <div className="flex items-center gap-2 shrink-0 text-2xs text-fg-3">
                    {!item.timestamp.startsWith('1970-') && (
                      <span className="tabular">{dateTime(item.timestamp)}</span>
                    )}
                    {item.lessonId && (
                      <Link
                        to={`/estudos/aulas?aula=${encodeURIComponent(item.lessonId)}`}
                        className="font-semibold text-accent-ink hover:underline"
                      >
                        Abrir Aula ›
                      </Link>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ol>
        )}
      </Card>
    </div>
  );
}
