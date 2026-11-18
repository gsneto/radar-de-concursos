import { Link } from 'react-router-dom';
import { BookOpen, CheckCircle2, Compass, Sparkles, Target, X } from 'lucide-react';
import { useAuthMe, useFlashStats, useStudyPanel } from '@/app/queries';
import { useUserStorage } from '@/lib/user-storage';

interface StudentOnboardingChecklistProps {
  selectedContestsCount: number;
}

export function StudentOnboardingChecklist({ selectedContestsCount }: StudentOnboardingChecklistProps) {
  const authMe = useAuthMe();
  const authReady = !authMe.isLoading;
  const userId = authMe.data?.user?.id ?? null;
  const [dismissed, setDismissed] = useUserStorage<boolean>('onboarding_dismissed', false, userId, undefined, authReady);
  const [completedSchedule] = useUserStorage<Record<string, boolean>>(
    'weekly_schedule_completed',
    {},
    userId,
    'radar_weekly_study_schedule_completed',
    authReady,
  );
  const [completedLessons] = useUserStorage<string[]>(
    'completed_lessons',
    [],
    userId,
    'radar_completed_lessons',
    authReady,
  );
  const studyPanel = useStudyPanel();
  const flashStats = useFlashStats();

  if (!authReady || dismissed) return null;

  const step1Done = selectedContestsCount > 0;
  const step2Done = Object.values(completedSchedule).some(Boolean);
  const step3Done =
    completedLessons.length > 0 ||
    (studyPanel.data?.sessoes_concluidas ?? 0) > 0 ||
    (flashStats.data?.revisoes ?? 0) > 0;

  const steps = [
    {
      title: '1. Escolher Concurso Foco',
      description: 'Selecione ao menos um certame no Radar para monitorar prazos e vagas.',
      done: step1Done,
      to: '/oportunidades',
      cta: step1Done ? 'Revisar Radar' : 'Explorar Radar',
      icon: Target,
    },
    {
      title: '2. Abrir Ciclo Semanal',
      description: 'Marque o primeiro bloco da sua grade semanal calibrada pela banca.',
      done: step2Done,
      to: '/estudos/cronograma',
      cta: step2Done ? 'Ver Ciclo' : 'Configurar Ciclo',
      icon: Compass,
    },
    {
      title: '3. Iniciar 1ª Aula ou Flashcard',
      description: 'Conclua uma sessão de estudo ou revise um cartão na fila SM-2.',
      done: step3Done,
      to: '/estudos/aulas',
      cta: step3Done ? 'Continuar Aulas' : 'Abrir Aulas',
      icon: BookOpen,
    },
  ] as const;

  const completedCount = steps.filter((s) => s.done).length;

  return (
    <section
      aria-label="Guia rápido de ativação"
      className="mb-5 rounded-2xl border border-amber-400/35 bg-surface p-4 sm:p-5 shadow-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-3">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 rounded-md bg-amber-400/15 border border-amber-400/35 px-2 py-0.5 text-[10px] font-extrabold uppercase tracking-wider text-accent-ink">
            <Sparkles size={12} /> Primeiros Passos
          </span>
          <span className="text-xs font-bold text-fg">
            Trilha de Ativação · {completedCount}/3 concluídos
          </span>
        </div>
        <button
          type="button"
          onClick={() => setDismissed(true)}
          className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-2xs font-semibold text-fg-3 hover:bg-surface-2 hover:text-fg transition-colors"
        >
          <X size={13} /> Ocultar guia
        </button>
      </div>

      <div className="mt-3.5 grid gap-3 md:grid-cols-3">
        {steps.map((step) => {
          const Icon = step.icon;
          return (
            <div
              key={step.title}
              className={`flex flex-col justify-between rounded-xl border p-3.5 transition-colors ${
                step.done
                  ? 'border-emerald-500/35 bg-emerald-500/5'
                  : 'border-line-strong bg-surface-2/60 hover:border-amber-400/40'
              }`}
            >
              <div>
                <div className="flex items-center justify-between gap-2">
                  <span
                    className={`flex size-7 items-center justify-center rounded-lg border ${
                      step.done
                        ? 'border-emerald-500/40 bg-emerald-500/15 text-ok-ink'
                        : 'border-amber-400/35 bg-amber-400/10 text-accent-ink'
                    }`}
                  >
                    {step.done ? <CheckCircle2 size={15} /> : <Icon size={14} />}
                  </span>
                  <span
                    className={`text-[10px] font-bold uppercase tracking-wider ${
                      step.done ? 'text-ok-ink' : 'text-fg-3'
                    }`}
                  >
                    {step.done ? 'Concluído' : 'Pendente'}
                  </span>
                </div>
                <h3 className="mt-2.5 text-xs font-bold text-fg">{step.title}</h3>
                <p className="mt-1 text-2xs text-fg-2 leading-relaxed">{step.description}</p>
              </div>

              <div className="mt-3 pt-2 border-t border-line/60">
                <Link
                  to={step.to}
                  className="inline-flex items-center gap-1 text-2xs font-extrabold text-accent-ink hover:underline"
                >
                  {step.cta} ›
                </Link>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
