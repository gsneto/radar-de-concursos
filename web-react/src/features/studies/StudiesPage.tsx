import { lazy, Suspense } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Award,
  BookOpen,
  CheckSquare,
  Clock,
  Compass,
  Layers,
  LayoutDashboard,
  Target,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { Button } from '@/components/ui/button';
import { SkeletonRows } from '@/components/ui/states';
import { ExamsSimulationTab } from './tabs/ExamsSimulationTab';
import { FlashcardsDeckTab } from './tabs/FlashcardsDeckTab';
import { QuestionsPracticeTab } from './tabs/QuestionsPracticeTab';
import { SessionsTimerTab } from './tabs/SessionsTimerTab';
import { StudyOverviewTab } from './tabs/StudyOverviewTab';

const LessonsView = lazy(() => import('./LessonsView').then((m) => ({ default: m.LessonsView })));
const BancaRadiographyView = lazy(() =>
  import('./BancaRadiographyView').then((m) => ({ default: m.BancaRadiographyView })),
);
const StudyScheduleView = lazy(() =>
  import('./StudyScheduleView').then((m) => ({ default: m.StudyScheduleView })),
);

const TABS = [
  { path: '', label: 'Visão geral', icon: LayoutDashboard, badge: null },
  { path: '/cronograma', label: 'Ciclo Semanal', icon: Compass, badge: 'IA' },
  { path: '/aulas', label: 'Aulas & Teoria', icon: BookOpen, badge: 'Trilha' },
  { path: '/flashcards', label: 'Flashcards Visuais', icon: Layers, badge: 'Jotta' },
  { path: '/questoes', label: 'Questões', icon: CheckSquare, badge: null },
  { path: '/bancas', label: 'Bancas', icon: Award, badge: '16' },
  { path: '/simulados', label: 'Simulados', icon: Target, badge: 'Rankings' },
  { path: '/sessoes', label: 'Sessões', icon: Clock, badge: null },
] as const;

export function StudiesPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const contestId = searchParams.get('concurso');
  const suffix = location.pathname.replace(/^\/estudos/, '');
  const active = TABS.find((tab) => tab.path === suffix)?.path ?? '';
  const isInsideSpecificLesson = active === '/aulas' && Boolean(searchParams.get('aula'));

  return (
    <>
      {!isInsideSpecificLesson && (
        <>
          <PageHeader
            eyebrow="Aprendizagem & Foco"
            title="Central de Estudos & Aprovação"
            description="Aulas estruturadas, quadros esquemáticos estilo Jotta, videoaulas verificadas, questões comentadas e revisão espaçada SM-2."
          />

          {contestId && (
            <div className="mb-4 flex items-center justify-between gap-3 p-3.5 rounded-lg border border-amber-400/30 bg-amber-400/5 text-xs text-fg">
              <div className="flex items-center gap-2.5 min-w-0">
                <Target size={16} className="text-accent-ink shrink-0" />
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
                            ? 'bg-amber-400/20 text-accent-ink border border-amber-400/30'
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
        </>
      )}

      <Suspense fallback={<SkeletonRows rows={5} />}>
        {active === '' && <StudyOverviewTab />}
        {active === '/cronograma' && <StudyScheduleView />}
        {active === '/aulas' && <LessonsView />}
        {active === '/bancas' && (
          <BancaRadiographyView
            onSelectBancaSimulado={() => {
              navigate('/estudos/simulados');
            }}
          />
        )}
        {active === '/sessoes' && <SessionsTimerTab />}
        {active === '/questoes' && <QuestionsPracticeTab />}
        {active === '/flashcards' && <FlashcardsDeckTab />}
        {active === '/simulados' && <ExamsSimulationTab />}
      </Suspense>
    </>
  );
}
