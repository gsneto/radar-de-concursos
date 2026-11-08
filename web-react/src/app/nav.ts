import {
  BookOpen,
  CalendarDays,
  ClipboardCheck,
  ClipboardList,
  Compass,
  Gauge,
  GitMerge,
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
      { to: '/prazos', label: 'Prazos', icon: CalendarDays },
      { to: '/visao-geral', label: 'Visão geral', icon: Gauge },
      { to: '/revisao', label: 'Revisão', icon: ClipboardCheck },
    ],
  },
  {
    label: 'Curadoria & Auditoria',
    items: [
      { to: '/mesa', label: 'Mesa de Validação', icon: LayoutGrid },
      { to: '/identidades', label: 'Padronização de Cargos', icon: GitMerge },
      { to: '/pipeline', label: 'Esteira de Editais', icon: Workflow },
    ],
  },
  {
    label: 'Estudos',
    items: [
      { to: '/estudos', label: 'Visão geral', icon: BookOpen, end: true },
      { to: '/estudos/cronograma', label: 'Ciclo Semanal', icon: Compass },
      { to: '/estudos/sessoes', label: 'Sessões', icon: ClipboardList },
      { to: '/estudos/questoes', label: 'Questões', icon: ListChecks },
      { to: '/estudos/flashcards', label: 'Flashcards', icon: Layers },
      { to: '/estudos/simulados', label: 'Simulados', icon: Sparkles },
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
