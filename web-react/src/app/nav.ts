import {
  BookOpen,
  CalendarDays,
  ClipboardCheck,
  ClipboardList,
  Compass,
  Gauge,
  History,
  Layers,
  ListChecks,
  Settings,
  Sparkles,
  Target,
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
      { to: '/', label: 'Visão geral', icon: Gauge, end: true },
      { to: '/oportunidades', label: 'Oportunidades', icon: Compass },
      { to: '/prazos', label: 'Prazos', icon: CalendarDays },
      { to: '/revisao', label: 'Revisão', icon: ClipboardCheck },
    ],
  },
  {
    label: 'Estudos',
    items: [
      { to: '/estudos', label: 'Visão geral', icon: BookOpen, end: true },
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
      { to: '/operacao', label: 'Operação', icon: Target },
    ],
  },
];

export const flatNav = navGroups.flatMap((group) => group.items);
