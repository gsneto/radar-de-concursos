/** Tipos derivados de docs/API.md e das respostas reais do backend (Fase 44). */

export type ReadinessState =
  | 'oportunidade_historica'
  | 'identidade_cargo_pendente'
  | 'campos_decisivos_ausentes'
  | 'conflito_documental_pendente';

export type SiState =
  | 'explicito'
  | 'categoria_inclui_curso'
  | 'area_correlata_interpretacao'
  | 'outras_formacoes'
  | 'nao_informado'
  | 'nao_encontrado'
  | 'extracao_incompleta';

export type IndigenousState =
  | 'explicito_imediato'
  | 'apenas_reserva'
  | 'mencao_sem_quantidade'
  | 'reserva_combinada_com_outros_grupos'
  | 'nao_mencionado'
  | 'fora_do_escopo_de_reserva'
  | 'reserva_sem_quantidade';

export type Urgency = 'hoje' | 'ate_7_dias' | 'ate_30_dias' | 'futuro' | 'vencido' | 'sem_data';

export interface Deadline {
  contest_id: string;
  grupo: string;
  grupo_label: string;
  prioridade_grupo?: number;
  escopo?: string | null;
  escopo_rotulo?: string | null;
  estado_operacional: string;
  estado_operacional_label: string;
  estado_temporal: 'futuro' | 'expirado' | 'sem_data';
  valor: string | null;
  dias_restantes: number | null;
  urgencia: Urgency;
  urgencia_label: string;
  documento: string | null;
  documento_id?: string | null;
  tipo_documental?: string | null;
  pagina: number | null;
  trecho?: string | null;
  official_url?: string | null;
  precisa_revalidacao?: boolean;
  proxima_acao?: string;
}

export interface FieldState {
  campo: string;
  label: string;
  estado: string;
  valores: string[];
  propostas: number;
  evidencias?: EvidenceItem[];
}

export interface EvidenceItem {
  proposal_id: string;
  value: number | string | null;
  state: string;
  document_id?: string;
  document_title?: string | null;
  tipo_documental?: string | null;
  official_url?: string | null;
  version_id?: string | null;
  sha256?: string | null;
  page_number?: number | null;
  quote?: string | null;
  extraction_method?: string | null;
  decision?: string | null;
}

export interface Opportunity {
  contest_id: string;
  competition_id: string | null;
  contest_title: string | null;
  contest_label: string | null;
  role_id: string | null;
  role_name: string | null;
  role_reconciliado: boolean;
  role_code: string | null;
  role_specialty: string | null;
  scope: string;
  documental: {
    estado: string;
    estado_label: string;
    documentos: number;
    documentos_oficiais: number;
    editais: number;
    retificacoes: number;
    proxima_acao: string;
  };
  prontidao: { estado: ReadinessState; estado_label: string; motivos: string[] };
  prioridade: { motivos: string[] };
  prazos: Deadline[];
  si: { estado: SiState | string; estado_label: string; itens?: unknown[]; agregado?: boolean };
  indigenas: {
    estado: IndigenousState | string;
    estado_label: string;
    ambito?: string;
    nota?: string;
    mencao?: { quote: string; page_number: number; contexto_label: string } | null;
    imediata?: unknown[];
    reserva?: unknown[];
    derivado_de_agregado?: boolean;
  };
  formacao?: Record<string, unknown>;
  localizacao: {
    prova: LocationInfo;
    lotacao: LocationInfo;
    nota?: string;
  };
  conflitos: { campos: Record<string, unknown>; oportunidade: unknown[] };
  lacunas: string[];
  proxima_acao: string;
  dossie: { contest_id: string; role_id: string | null; scope: string | null };
  propostas: number;
  pendentes: number;
  ultima_atualizacao: string | null;
}

export interface LocationInfo {
  state: string;
  uf: string | null;
  municipios: string[];
  scope: string;
  confidence: string | null;
  text: string | null;
  reason: string | null;
  evidence: { quote: string; page_number: number } | null;
  version_id?: string | null;
}

export interface Portfolio {
  version: string;
  generated_at: string;
  referencia: { agora_utc: string; hoje_local: string; fuso: string };
  total: number;
  por_prontidao: Record<string, number>;
  por_urgencia: Record<string, number>;
  limit: number;
  offset: number;
  has_more: boolean;
  itens: Opportunity[];
  limitacao: string;
}

export interface Coverage {
  version: string;
  generated_at: string;
  escopo: {
    concursos: number;
    containers_fonte: number;
    documentos_em_container: number;
    com_documento: number;
    com_edital_oficial: number;
    com_edital_analisado: number;
    com_propostas: number;
    propostas: number;
    cargos_identidade: number;
    reconciliacoes_cargo: number;
    auditorias_humanas: number;
  };
  funil: { etapa: string; quantidade: number; de: number }[];
  causas: Record<string, number>;
}

export interface Timeline {
  version: string;
  generated_at: string;
  referencia: { desde: string; ate: string };
  snapshot_anterior: { documentos: number; versoes: number; propostas: number; revisoes: number };
  novos: { documentos: number; versoes: number; propostas: number; revisoes: number };
  eventos: Record<string, number>;
  ciclos: {
    cycle_id: string;
    started_at: string;
    finished_at: string | null;
    state: string;
    documents_found: number;
    documents_new: number;
    versions_new: number;
    changes_pending: number;
    fontes: {
      source_url: string;
      state: string;
      documents_new: number;
      versions_new: number;
      error_code: string | null;
    }[];
  }[];
}

export interface StudyPanel {
  disciplinas: number;
  topicos: number;
  conteudo: {
    topics: { done: number; total: number; pct: number };
    overall: { done: number; total: number; pct: number };
  };
  progresso: unknown[];
  total_segundos: number;
  semana_segundos: number;
  sessoes_concluidas: number;
  minutos_por_disciplina: { disciplina_id: string; nome: string; minutos: number }[];
  revisoes_pendentes: number;
  revisoes: { revisao_id: string; progresso_id: string; data: string; topico_id: string }[];
  sessao_aberta: StudySession | null;
}

export interface StudySession {
  id: string;
  disciplina_id: string | null;
  topico_id: string | null;
  contest_id: string;
  inicio: string | null;
  fim: string | null;
  duracao_segundos: number;
  estado: 'em_andamento' | 'pausada' | 'concluida';
  modo: string;
  notas: string | null;
  created_at: string;
  elapsed_seconds: number;
}

export interface Discipline {
  id: string;
  nome: string;
}

export interface DeadlineCalendar {
  version: string;
  generated_at: string;
  referencia: { hoje_local: string; fuso: string; agora_utc: string };
  total: number;
  por_temporal: Record<string, number>;
  por_situacao: Record<string, number>;
  por_grupo: Record<string, number>;
  por_urgencia: Record<string, number>;
  por_conflito: Record<string, number>;
  limit: number;
  offset: number;
  has_more: boolean;
  itens: Deadline[];
  limitacao: string;
}

export interface Preferences {
  reference_municipio: string | null;
  reference_uf: string | null;
  interest_states: string[];
  practical_distance_km: number | null;
  priority: string;
}

export interface Dossier {
  version: string;
  generated_at: string;
  contest_id: string;
  role_id: string | null;
  scope: string | null;
  identificacao: {
    contest_title: string | null;
    contest_label: string | null;
    observacoes: { source_url: string; competition_id: string }[];
    role_name: string | null;
    role_reconciliado: boolean;
    documentos: number;
    edital_principal: {
      document_id: string;
      title: string;
      tipo: string;
      official_url: string | null;
      issuer: string | null;
      published_at: string | null;
      discovered_at: string | null;
      versoes: number;
      paginas_extraidas: number;
    } | null;
    retificacoes: unknown[];
  };
  vagas: {
    total_publicado: FieldState | null;
    imediatas: FieldState | null;
    reserva: FieldState | null;
    indigenas: Opportunity['indigenas'] | null;
    nota: string;
  };
  formacao: {
    requisito: FieldState | null;
    cursos_aceitos: FieldState | null;
    si_compatibility: FieldState | null;
    si_por_cargo: Opportunity['si'] | null;
    nota: string;
  };
  prazos: Deadline[];
  localizacao: Opportunity['localizacao'];
  conflitos: { campos: Record<string, unknown>; oportunidade: unknown[] };
  prontidao: { estado: ReadinessState; estado_label: string; motivos: string[] };
  proxima_acao: string;
  lacunas: string[];
  limitacao: string;
}

export interface ContestDetails {
  contest: { id: string; observations: { source_url: string; competition_id: string }[] };
  roles: unknown[];
  coverage: { state: string; checked_at: string | null; checked_urls: string[]; reviewer: string | null };
  documents: {
    id: string;
    kind: string;
    document_type: string | null;
    official_url: string | null;
    issuer: string | null;
    published_at: string | null;
    title: string;
    state: string;
    versions: {
      id: string;
      sha256: string;
      fetched_at: string;
      content_type: string;
      byte_size: number;
      extraction_state: string;
      error_code: string | null;
    }[];
  }[];
  proposals: {
    field_name: string;
    value: unknown;
    state: string;
    quote?: string | null;
    page_number?: number | null;
    document_title?: string | null;
  }[];
  current_values: unknown[];
  conflicts: unknown[];
}

export interface Performance {
  geral: {
    total: number;
    respondidas: number;
    acertos: number;
    erros: number;
    brancos: number;
    denominator: number;
    pct: number | null;
    basis: string;
  };
  por_disciplina: {
    grupo: string;
    total: number;
    acertos: number;
    erros: number;
    brancos: number;
    pct: number | null;
  }[];
  por_topico: unknown[];
  simulados: unknown[];
}

export interface FlashcardStats {
  ativos: number;
  arquivados: number;
  novos: number;
  pendentes: number;
  revisoes: number;
  acertos: number;
  pct_acerto: number | null;
  basis: string;
}
