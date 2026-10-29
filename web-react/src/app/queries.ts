import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, qs } from '@/lib/api';
import type {
  ContestDetails,
  ConflictGroups,
  Coverage,
  DeadlineCalendar,
  Discipline,
  Dossier,
  FlashcardStats,
  Opportunity,
  OpportunityList,
  Performance,
  PipelineCoverage,
  PipelineDocuments,
  PipelineSummary,
  Portfolio,
  Preferences,
  ReconciliationQueue,
  ReviewGroups,
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

export type ReviewState = 'prontos' | 'aberto' | 'decidido' | 'todos';

export function useReviewGroups(state: ReviewState, limit = 20, offset = 0) {
  return useQuery({
    queryKey: ['review-groups', state, limit, offset] as const,
    queryFn: () =>
      api.get<ReviewGroups>(
        `/api/revisao/grupos${qs({ state, limit, offset })}`,
      ),
    staleTime: 30_000,
  });
}

export interface DecisionInput {
  proposalId: string;
  decision: 'validado' | 'rejeitado' | 'adiado' | 'ambiguo' | 'nova_extracao';
  reviewer: string;
  reason: string;
  evidenceSha256: string;
  scopeSnapshot: string[];
}

/**
 * Decisão humana por campo. A interface declara a impressão da evidência vista
 * (`evidence_sha256`) e o escopo no momento da abertura: o servidor recusa se
 * algo mudou desde então.
 */
export function useDecideProposal() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: DecisionInput) =>
      api.post<{ decision: string; duplicada?: boolean }>(
        `/api/revisao/proposta/${encodeURIComponent(input.proposalId)}`,
        {
          decision: input.decision,
          reviewer: input.reviewer,
          reason: input.reason,
          origin: 'interface',
          evidence_sha256: input.evidenceSha256,
          scope_snapshot: input.scopeSnapshot,
        },
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['review-groups'] });
    },
  });
}

export interface ReconciliationFilters {
  state?: string;
  nature?: string;
  minCandidates?: number;
  contestId?: string;
  limit?: number;
  offset?: number;
}

export function useReconciliation(filters: ReconciliationFilters) {
  const query = qs({
    state: filters.state,
    nature: filters.nature,
    min_candidates: filters.minCandidates,
    contest_id: filters.contestId,
    limit: filters.limit ?? 50,
    offset: filters.offset ?? 0,
  });
  return useQuery({
    queryKey: ['reconciliation', filters] as const,
    queryFn: () => api.get<ReconciliationQueue>(`/api/reconciliacao${query}`),
    staleTime: 60_000,
  });
}

export interface ReconciliationDecision {
  contestId: string;
  label: string;
  state: 'confirmada' | 'rejeitada' | 'ambigua' | 'reaberta';
  reviewer: string;
  reason: string;
  roleId?: string | null;
  nature?: string | null;
}

/**
 * Decisão de identidade de cargo: append-only, com autor e justificativa.
 * `dry_run` vai como false explicitamente — o padrão do servidor é simular.
 */
export function useDecideReconciliation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: ReconciliationDecision) =>
      api.post<{ state: string; gravado?: boolean }>('/api/reconciliacao', {
        contest_id: input.contestId,
        label: input.label,
        state: input.state,
        reviewer: input.reviewer,
        reason: input.reason,
        role_id: input.roleId ?? null,
        nature: input.nature ?? null,
        dry_run: false,
      }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['reconciliation'] });
      void client.invalidateQueries({ queryKey: ['review-groups'] });
    },
  });
}

export function useConflicts(filters: { cause?: string; contestId?: string; limit?: number; offset?: number }) {
  const query = qs({
    cause: filters.cause,
    contest_id: filters.contestId,
    limit: filters.limit ?? 25,
    offset: filters.offset ?? 0,
  });
  return useQuery({
    queryKey: ['conflicts', filters] as const,
    queryFn: () => api.get<ConflictGroups>(`/api/conflitos-revisao${query}`),
    staleTime: 60_000,
  });
}

export function usePipelineSummary() {
  return useQuery({
    queryKey: ['pipeline', 'summary'] as const,
    queryFn: () => api.get<PipelineSummary>('/api/pipeline'),
    staleTime: 5 * 60_000,
  });
}

export function usePipelineCoverage(limit = 500) {
  return useQuery({
    queryKey: ['pipeline', 'coverage', limit] as const,
    queryFn: () => api.get<PipelineCoverage>(`/api/pipeline/cobertura?limit=${limit}`),
    staleTime: 5 * 60_000,
  });
}

export function usePipelineDocuments(filters: { pending?: boolean; contestId?: string; limit?: number }) {
  const query = qs({
    pending: filters.pending ? '1' : undefined,
    contest_id: filters.contestId,
    limit: filters.limit ?? 100,
  });
  return useQuery({
    queryKey: ['pipeline', 'documents', filters] as const,
    queryFn: () => api.get<PipelineDocuments>(`/api/pipeline/documentos${query}`),
    staleTime: 5 * 60_000,
  });
}

export interface MesaFilters {
  field?: string;
  conflict?: string;
  documentState?: string;
  search?: string;
  minPriority?: number;
  contestId?: string;
  limit?: number;
  offset?: number;
}

export function useOpportunities(filters: MesaFilters) {
  const query = qs({
    field: filters.field,
    conflict: filters.conflict,
    document_state: filters.documentState,
    search: filters.search,
    min_priority: filters.minPriority,
    contest_id: filters.contestId,
    limit: filters.limit ?? 25,
    offset: filters.offset ?? 0,
  });
  return useQuery({
    queryKey: ['opportunities', filters] as const,
    queryFn: () => api.get<OpportunityList>(`/api/oportunidades${query}`),
    staleTime: 60_000,
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
