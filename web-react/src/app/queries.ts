import { useQuery } from '@tanstack/react-query';
import { api, qs } from '@/lib/api';
import type {
  ContestDetails,
  Coverage,
  DeadlineCalendar,
  Discipline,
  Dossier,
  FlashcardStats,
  Opportunity,
  Performance,
  Portfolio,
  Preferences,
  StudyPanel,
  StudySession,
  Timeline,
} from '@/lib/types';

/* Chaves centralizadas: invalidação previsível. */
export const keys = {
  portfolio: (filters: Record<string, unknown>) => ['portfolio', filters] as const,
  coverage: () => ['coverage'] as const,
  timeline: () => ['timeline'] as const,
  study: () => ['study', 'panel'] as const,
  sessions: () => ['study', 'sessions'] as const,
  disciplines: () => ['study', 'disciplines'] as const,
  revisions: () => ['study', 'revisions'] as const,
  performance: () => ['study', 'performance'] as const,
  flashStats: () => ['study', 'flashcards', 'stats'] as const,
  flashQueue: () => ['study', 'flashcards', 'queue'] as const,
  questions: () => ['study', 'questions'] as const,
  exams: () => ['study', 'exams'] as const,
  deadlines: (filters: Record<string, unknown>) => ['deadlines', filters] as const,
  dossier: (contestId: string, scope: string | null) => ['dossier', contestId, scope] as const,
  details: (contestId: string) => ['contest', contestId] as const,
  preferences: () => ['preferences'] as const,
};

export interface PortfolioFilters {
  q?: string;
  uf?: string;
  prontidao?: string;
  si?: string;
  indigena?: string;
  prazo?: string;
  documental?: string;
  conflito?: string;
  offset?: number;
  limit?: number;
}

export function usePortfolio(filters: PortfolioFilters) {
  const limit = filters.limit ?? 20;
  const offset = filters.offset ?? 0;
  const query = qs({
    search: filters.q,
    uf: filters.uf,
    prontidao: filters.prontidao,
    si: filters.si,
    indigena: filters.indigena,
    prazo: filters.prazo,
    documental: filters.documental,
    conflito: filters.conflito,
    limit,
    offset,
  });
  return useQuery({
    queryKey: keys.portfolio({ ...filters, limit, offset }),
    queryFn: () => api.get<Portfolio>(`/api/carteira${query}`),
  });
}

export function useCoverage() {
  return useQuery({
    queryKey: keys.coverage(),
    queryFn: () => api.get<Coverage>('/api/cobertura/resumo'),
    staleTime: 5 * 60_000,
  });
}

export function useTimeline() {
  return useQuery({
    queryKey: keys.timeline(),
    queryFn: () => api.get<Timeline>('/api/linha-do-tempo?limit=1'),
    staleTime: 5 * 60_000,
  });
}

export function useStudyPanel() {
  return useQuery({
    queryKey: keys.study(),
    queryFn: () => api.get<StudyPanel>('/api/estudos/painel'),
    staleTime: 30_000,
  });
}

export function useSessions() {
  return useQuery({
    queryKey: keys.sessions(),
    queryFn: () => api.get<StudySession[]>('/api/estudos/sessoes?limit=50'),
    staleTime: 30_000,
  });
}

export function useDisciplines() {
  return useQuery({
    queryKey: keys.disciplines(),
    queryFn: () => api.get<Discipline[]>('/api/estudos/disciplinas'),
    staleTime: 5 * 60_000,
  });
}

export function useRevisions() {
  return useQuery({
    queryKey: keys.revisions(),
    queryFn: () => api.get<StudyPanel['revisoes']>('/api/estudos/revisoes'),
    staleTime: 30_000,
  });
}

export function usePerformance() {
  return useQuery({
    queryKey: keys.performance(),
    queryFn: () => api.get<Performance>('/api/estudos/desempenho'),
    staleTime: 30_000,
  });
}

export function useFlashStats() {
  return useQuery({
    queryKey: keys.flashStats(),
    queryFn: () => api.get<FlashcardStats>('/api/estudos/flashcards/estatisticas'),
    staleTime: 30_000,
  });
}

export function useFlashQueue() {
  return useQuery({
    queryKey: keys.flashQueue(),
    queryFn: () =>
      api.get<{ novos: Flashcard[]; vencidos: Flashcard[]; futuros: Flashcard[] }>(
        '/api/estudos/flashcards/fila?limit=20',
      ),
    staleTime: 30_000,
  });
}

export interface Flashcard {
  id: string;
  frente: string;
  verso: string;
  estado: string;
  intervalo: number;
  repeticoes: number;
  proxima_revisao: string | null;
}

export function useQuestions() {
  return useQuery({
    queryKey: keys.questions(),
    queryFn: () => api.get<Question[]>('/api/estudos/questoes?incluir_arquivadas=0'),
    staleTime: 60_000,
  });
}

export interface Question {
  id: string;
  enunciado: string;
  alternativas: { letra: string; texto: string }[];
  gabarito?: string;
  disciplina: string | null;
  topico: string | null;
  dificuldade: string | null;
}

export function useExams() {
  return useQuery({
    queryKey: keys.exams(),
    queryFn: () => api.get<Exam[]>('/api/estudos/simulados?limit=30'),
    staleTime: 30_000,
  });
}

export interface Exam {
  id: string;
  nome: string;
  estado: string;
  modo: string;
  duracao_segundos: number | null;
  iniciado_em: string | null;
  finalizado_em: string | null;
  questao_atual: number;
}

export function useDeadlines(filters: {
  group?: string;
  groups?: readonly string[];
  urgency?: string;
  limit?: number;
}) {
  const query = qs({
    group: filters.group,
    groups: filters.groups?.length ? filters.groups.join(',') : undefined,
    urgency: filters.urgency,
    limit: filters.limit ?? 200,
  });
  return useQuery({
    queryKey: keys.deadlines(filters),
    queryFn: () => api.get<DeadlineCalendar>(`/api/prazos/calendario${query}`),
    staleTime: 5 * 60_000,
  });
}

export function useDossier(contestId: string | undefined, scope: string | null) {
  return useQuery({
    queryKey: keys.dossier(contestId ?? '', scope),
    queryFn: () =>
      api.get<Dossier>(`/api/carteira/dossie${qs({ contest_id: contestId, scope })}`),
    enabled: Boolean(contestId),
  });
}

export function useContestDetails(contestId: string | undefined) {
  return useQuery({
    queryKey: keys.details(contestId ?? ''),
    queryFn: () =>
      api.get<ContestDetails>(`/api/concursos/${encodeURIComponent(contestId!)}/detalhes`),
    enabled: Boolean(contestId),
  });
}

export function usePreferences() {
  return useQuery({
    queryKey: keys.preferences(),
    queryFn: () => api.get<Preferences>('/api/preferencias'),
    staleTime: Infinity,
  });
}

export type { Opportunity };
