import { useMemo, useState } from 'react';
import {
  CheckCircle2,
  ChevronRight,
  Clock,
  GraduationCap,
  LayoutGrid,
  ListTree,
  Plus,
  Search,
  Sparkles,
  Zap,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { SkeletonRows } from '@/components/ui/states';
import type { LessonSummary } from '@/lib/types';
import {
  CreateLessonModal,
  LESSON_DISCIPLINES,
  type CreateCustomLessonInput,
} from './CreateLessonModal';

export type { CreateCustomLessonInput };

interface LessonCatalogViewProps {
  lessons: LessonSummary[];
  lessonsLoading: boolean;
  completedLessons: string[];
  getLessonPercent?: (lessonId: string, isCompleted?: boolean) => number;
  totalEarnedXp: number;
  selectedDisciplina: string;
  onSelectDisciplina: (disciplina: string) => void;
  onSelectLesson: (lessonId: string) => void;
  isAdmin: boolean;
  onCreateLesson: (payload: CreateCustomLessonInput) => Promise<void>;
}

export function LessonCatalogView({
  lessons,
  lessonsLoading,
  completedLessons,
  getLessonPercent,
  totalEarnedXp,
  selectedDisciplina,
  onSelectDisciplina,
  onSelectLesson,
  isAdmin,
  onCreateLesson,
}: LessonCatalogViewProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'todas' | 'pendentes' | 'concluidas'>('todas');
  const [catalogViewMode, setCatalogViewMode] = useState<'modulos' | 'grade'>('modulos');
  const [showCreateModal, setShowCreateModal] = useState(false);

  const filteredLessons = useMemo(() => {
    return lessons.filter((lesson) => {
      const isCompleted = completedLessons.includes(lesson.id);
      if (statusFilter === 'pendentes' && isCompleted) return false;
      if (statusFilter === 'concluidas' && !isCompleted) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          lesson.titulo.toLowerCase().includes(q) ||
          lesson.disciplina.toLowerCase().includes(q) ||
          (lesson.modulo || '').toLowerCase().includes(q) ||
          lesson.objetivos.some((o) => o.toLowerCase().includes(q))
        );
      }
      return true;
    });
  }, [lessons, completedLessons, statusFilter, searchQuery]);

  const groupedByModule = useMemo(() => {
    const groups: Record<string, { disciplina: string; modulo: string; aulas: LessonSummary[] }> = {};
    for (const l of filteredLessons) {
      const mod = l.modulo || `Módulo Essencial: ${l.disciplina}`;
      const key = `${l.disciplina}::${mod}`;
      if (!groups[key]) groups[key] = { disciplina: l.disciplina, modulo: mod, aulas: [] };
      groups[key].aulas.push(l);
    }
    return Object.values(groups);
  }, [filteredLessons]);

  const totalLessonsCount = lessons.length;
  const completedCount = lessons.filter((l) => completedLessons.includes(l.id)).length;
  const completionPercentage = totalLessonsCount > 0 ? Math.round((completedCount / totalLessonsCount) * 100) : 0;

  return (
    <>
      <CreateLessonModal
        open={showCreateModal}
        onOpenChange={setShowCreateModal}
        onCreateLesson={onCreateLesson}
      />

      <div className="rounded-2xl border border-line-strong bg-surface p-6 shadow-md">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
          <div className="space-y-2 max-w-2xl">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-md bg-amber-400 px-2.5 py-1 text-xs font-black uppercase tracking-wider text-slate-950">
                <Sparkles size={13} /> Ambiente Completo de Ensino
              </span>
              <span className="rounded-md border border-emerald-500/40 bg-emerald-500/15 px-2.5 py-1 text-xs font-bold text-ok-ink">
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
              <span className="text-[11px] font-extrabold uppercase tracking-wider text-accent-ink block">
                XP Acumulado
              </span>
              <p className="mt-1 font-display text-xl font-black text-fg tabular">{totalEarnedXp} XP</p>
            </div>
            <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 p-3.5 text-center">
              <span className="text-[11px] font-extrabold uppercase tracking-wider text-ok-ink block">
                Concluídas
              </span>
              <p className="mt-1 font-display text-xl font-black text-fg tabular">
                {completedCount}/{totalLessonsCount} ({completionPercentage}%)
              </p>
            </div>
            {isAdmin && (
              <div className="flex flex-col justify-center rounded-xl border border-line-strong bg-surface-2 p-3 text-center">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setShowCreateModal(true)}
                  className="w-full gap-1.5 text-xs font-bold text-accent-ink border-amber-400/40"
                >
                  <Plus size={14} /> Nova Aula
                </Button>
              </div>
            )}
          </div>
        </div>

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
                  catalogViewMode === 'modulos' ? 'bg-amber-400 text-slate-950' : 'text-fg-2 hover:text-fg'
                }`}
              >
                <ListTree size={14} /> Por Módulos
              </button>
              <button
                type="button"
                onClick={() => setCatalogViewMode('grade')}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
                  catalogViewMode === 'grade' ? 'bg-amber-400 text-slate-950' : 'text-fg-2 hover:text-fg'
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
                      ? 'bg-surface text-accent-ink border border-amber-400/40'
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

      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        {LESSON_DISCIPLINES.map((disc) => {
          const active = selectedDisciplina === disc.key;
          return (
            <button
              key={disc.key}
              type="button"
              onClick={() => onSelectDisciplina(disc.key)}
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
                  <span className="flex size-10 items-center justify-center rounded-xl bg-amber-400/20 text-accent-ink border border-amber-400/40">
                    <GraduationCap size={20} />
                  </span>
                  <div>
                    <span className="text-xs font-black uppercase tracking-wider text-accent-ink">
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
                  const pct = getLessonPercent ? getLessonPercent(lesson.id, isDone) : isDone ? 100 : 0;
                  const qCount = lesson.questoes_count ?? lesson.total_questoes ?? 0;
                  const vCount = lesson.videoaulas_count ?? 2;
                  const fCount = lesson.flashcards_count ?? 6;
                  return (
                    <div
                      key={lesson.id}
                      onClick={() => onSelectLesson(lesson.id)}
                      className="group flex flex-col lg:flex-row lg:items-center justify-between gap-4 p-6 cursor-pointer hover:bg-surface-2/60 transition-all"
                    >
                      <div className="space-y-2 max-w-3xl">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-md bg-amber-400/15 border border-amber-400/40 px-2.5 py-0.5 text-xs font-extrabold text-accent-ink">
                            {lesson.nivel || 'Essencial'}
                          </span>
                          <span className="flex items-center gap-1 text-xs font-semibold text-fg-2">
                            <Clock size={13} className="text-amber-400" /> {lesson.tempo_estimado_min || 45} min
                          </span>
                          <span className="flex items-center gap-1 text-xs font-extrabold text-ok-ink">
                            <Zap size={13} /> +{lesson.xp_recompensa || 120} XP
                          </span>
                          <span
                            className={`inline-flex items-center gap-1 rounded-md px-2.5 py-0.5 text-xs font-bold tabular ${
                              pct === 100
                                ? 'bg-emerald-500/20 text-ok-ink'
                                : pct > 0
                                  ? 'bg-amber-400/15 text-accent-ink border border-amber-400/30'
                                  : 'bg-surface-2 text-fg-3 border border-line'
                            }`}
                          >
                            {pct === 100 ? <CheckCircle2 size={13} /> : null}
                            {pct === 100 ? '100% Concluída' : `${pct}% das etapas`}
                          </span>
                        </div>
                        <h4 className="font-display text-lg font-extrabold text-fg group-hover:text-accent-ink transition-colors">
                          {lesson.titulo}
                        </h4>
                        <p className="text-sm text-fg-2">✓ {lesson.objetivos[0]}</p>
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
                onClick={() => onSelectLesson(lesson.id)}
                className="group cursor-pointer rounded-2xl border border-line-strong bg-surface p-6 hover:border-amber-400 transition-all flex flex-col justify-between gap-4 shadow-md"
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <Badge tone="accent">{lesson.disciplina}</Badge>
                    <span className="text-xs font-bold text-fg-2">{qCount} questões</span>
                  </div>
                  <h3 className="font-display text-lg font-extrabold text-fg group-hover:text-accent-ink">
                    {lesson.titulo}
                  </h3>
                  <ul className="space-y-1.5">
                    {lesson.objetivos.slice(0, 2).map((obj, idx) => (
                      <li key={idx} className="text-xs text-fg-2 flex items-start gap-2">
                        <CheckCircle2 size={14} className="text-ok-ink shrink-0 mt-0.5" />
                        <span>{obj}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="pt-3 border-t border-line flex items-center justify-between">
                  <span className="text-xs font-bold text-accent-ink">Abrir Aula Completa</span>
                  <ChevronRight size={16} className="text-accent-ink" />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
