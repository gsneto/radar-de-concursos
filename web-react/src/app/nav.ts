import {
  Award,
  BookOpen,
  CalendarDays,
  ClipboardCheck,
  ClipboardList,
  Compass,
  Gauge,
  GitMerge,
  GraduationCap,
  History,
  Layers,
  LayoutGrid,
  ListChecks,
  Settings,
  Sparkles,
  Target,
  Workflow,
  type LucideIcon,
} from 'lucide-react';

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const navGroups: NavGroup[] = [
  {
    label: 'Principal',
    items: [
      { to: '/', label: 'Meus Concursos', icon: Target, end: true },
      { to: '/oportunidades', label: 'Radar de Concursos', icon: Compass },
      { to: '/prazos', label: 'Prazos & Calendário', icon: CalendarDays },
      { to: '/visao-geral', label: 'Panorama de Editais', icon: Gauge },
    ],
  },
  {
    label: 'Estudos & Aprovação',
    items: [
      { to: '/estudos/aulas', label: 'Aulas & Teoria', icon: GraduationCap },
      { to: '/estudos/flashcards', label: 'Flashcards Visuais', icon: Layers },
      { to: '/estudos/questoes', label: 'Banco de Questões', icon: ListChecks },
      { to: '/estudos/cronograma', label: 'Ciclo Semanal', icon: Compass },
      { to: '/estudos/bancas', label: 'Raio-X das Bancas', icon: Award },
      { to: '/estudos/simulados', label: 'Simulados', icon: Sparkles },
      { to: '/estudos', label: 'Painel & Cronômetro', icon: BookOpen, end: true },
      { to: '/estudos/sessoes', label: 'Histórico de Sessões', icon: ClipboardList },
    ],
  },
  {
    label: 'Curadoria & Auditoria',
    items: [
      { to: '/mesa', label: 'Mesa de Validação', icon: LayoutGrid },
      { to: '/revisao', label: 'Revisão de Editais', icon: ClipboardCheck },
      { to: '/identidades', label: 'Padronização de Cargos', icon: GitMerge },
      { to: '/pipeline', label: 'Esteira de Editais', icon: Workflow },
    ],
  },
  {
    label: 'Sistema',
    items: [
      { to: '/historico', label: 'Histórico', icon: History },
      { to: '/configuracoes', label: 'Configurações', icon: Settings },
      { to: '/operacao', label: 'Diagnóstico', icon: Target },
    ],
  },
];

export const flatNav = navGroups.flatMap((group) => group.items);
