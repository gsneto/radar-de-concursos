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

/* --- Revisão humana por linha documental --------------------------------- */

export interface ReviewEvidence {
  quote: string | null;
  page_number: number | null;
  version_id: string;
  start_offset: number | null;
  end_offset: number | null;
  document_id: string;
}

export interface ReviewProposal {
  proposal_id: string;
  field_name: string;
  field_label: string;
  value: unknown;
  state: string;
  last_decision: string | null;
  selected: boolean;
  consequencia?: string | null;
  historico: { decision: string; reviewed_at: string; reviewer: string; reason: string }[];
  ambiguity_reason: string | null;
  extraction_method: string;
  evidence_sha256: string;
  scope_snapshot: string[];
  evidence: ReviewEvidence;
}

export interface ReviewValidation {
  tipo: string;
  publicado: number | null;
  soma: number | null;
  diferenca: number | null;
  estado: string;
  regra: string;
}

export interface ReviewGroup {
  linha_id: string;
  contest_id: string;
  competition_id: string | null;
  document_id: string;
  document_title: string | null;
  tipo_documental: string | null;
  issuer: string | null;
  official_url: string | null;
  version_id: string;
  page_number: number | null;
  scope: string;
  scopes: string[];
  identidade: 'reconciliado' | 'pendente';
  prioridade: number;
  estado: 'pendente' | 'parcial' | 'decidido';
  estados: string[];
  pendentes: number;
  conflito: boolean;
  contexto: { tipo?: string; trecho?: string | null; cargo?: string | null } | null;
  validacao: ReviewValidation | null;
  rotulo_divergente: { armazenado: string; parser: string } | null;
  propostas: ReviewProposal[];
  proxima_acao: string;
}

export interface ReviewGroups {
  version: string;
  generated_at: string;
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  filtros: Record<string, unknown>;
  resumo: {
    linhas: number;
    linhas_prontas: number;
    linhas_divergentes: number;
    propostas: number;
    propostas_pendentes: number;
    com_conflito: number;
    decisoes_registradas: number;
  };
  itens: ReviewGroup[];
  limitacao: string;
}

/* --- Identidades: reconciliação de cargo e conflitos ---------------------- */

export interface ReconciliationFactor {
  fator: string;
  pontos: number;
  motivo: string;
}

export interface ReconciliationSuggestion {
  role_id: string;
  role_name: string;
  specialty: string | null;
  code: string | null;
  state: string;
  pontuacao: number;
  fatores: ReconciliationFactor[];
}

export interface ReconciliationEvidence {
  document_id: string;
  document_title: string | null;
  tipo_documental: string | null;
  published_at: string | null;
  page_number: number | null;
  quote: string | null;
  version_id: string;
  proposal_id: string;
}

export interface ReconciliationItem {
  contest_id: string;
  label: string;
  nature: string;
  nature_label: string;
  normalized: string;
  proposals: number;
  fields: string[];
  documents: { document_id: string; title: string | null }[];
  pages: number[];
  first_evidence: ReconciliationEvidence | null;
  suggestions: ReconciliationSuggestion[];
  cargo_count: number;
  decision: { state: string; reviewer: string; reason: string; decided_at: string } | null;
  state: string;
}

export interface ReconciliationQueue {
  version: string;
  generated_at: string;
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  itens: ReconciliationItem[];
  limitacao: string;
}

export interface ConflictProposal {
  proposal_id: string;
  value: unknown;
  state: string;
  document_id: string;
  document_title: string | null;
  tipo_documental: string | null;
  published_at: string | null;
  version_id: string;
  page_number: number | null;
  quote: string | null;
  extraction_method: string;
}

export interface ConflictGroup {
  contest_id: string;
  scope: string;
  field_name: string;
  cause: string;
  cause_label: string;
  motivos: string[];
  prioridade: number;
  proxima_acao: string;
  valores_distintos: number;
  propostas: ConflictProposal[];
  documentos: { document_id: string; title: string | null; tipo_documental: string | null }[];
  vigente_candidato: unknown;
  vigente_documento: unknown;
}

export interface ConflictGroups {
  version: string;
  generated_at: string;
  total: number;
  por_causa: Record<string, number>;
  por_prioridade: Record<string, number>;
  limit: number;
  offset: number;
  has_more: boolean;
  itens: ConflictGroup[];
  limitacao: string;
}

/* --- Pipeline documental -------------------------------------------------- */

export interface PipelineSummary {
  version: string;
  generated_at: string;
  concursos: number;
  concursos_com_documento: number;
  concursos_com_edital: number;
  documentos: number;
  documentos_com_texto: number;
  versoes: number;
  versoes_extraidas: number;
  propostas: number;
  evidencias: number;
  revisoes_humanas: number;
  campos_confirmados: number;
  falhas_por_codigo: Record<string, number>;
}

export interface PipelineDocument {
  document_id: string;
  contest_id: string;
  title: string | null;
  official_url: string | null;
  tipo_documental: string | null;
  kind: string | null;
  issuer: string | null;
  source_identifier: string | null;
  stages: string[];
  versions: number;
  extracted_versions: number;
  blocks: number;
  proposals: number;
  association_state: string | null;
  contest_state: string | null;
  blocked_at: string | null;
  blocked_reason: string | null;
  last_extraction_state: string | null;
  review_ready: boolean;
}

export interface PipelineDocuments {
  version: string;
  generated_at: string;
  total: number;
  returned: number;
  truncated: boolean;
  por_bloqueio: Record<string, number>;
  itens: PipelineDocument[];
  limitacao: string;
}

export interface PipelineCoverage {
  version: string;
  generated_at: string;
  concursos: number;
  por_categoria: Record<string, number>;
  itens: {
    contest_id: string;
    categoria: string;
    documentos: number;
    documentos_oficiais: number;
    edital_principal: number;
    retificacoes: number;
    documentos_com_texto: number;
    propostas: number;
    campos_com_proposta: number;
    falhas_extracao: number;
    sem_texto: number;
  }[];
  limitacao: string;
}

/* --- Mesa: oportunidades técnicas ---------------------------------------- */

export interface OpportunityField {
  campo: string;
  label: string;
  estado: string;
  valores: string[];
  propostas: number;
  com_pagina: number;
}

export interface OpportunityRow {
  contest_id: string;
  competition_id: string | null;
  contest_title: string | null;
  role_id: string | null;
  scope: string;
  role_name: string | null;
  role_reconciliado: boolean;
  role_code: string | null;
  role_specialty: string | null;
  documental: {
    estado: string;
    estado_label: string;
    documentos: number;
    documentos_oficiais: number;
    editais: number;
    retificacoes: number;
    proxima_acao: string;
  };
  campos: Record<string, OpportunityField>;
  pendentes: number;
  propostas: number;
  conflitos: number;
  tem_pagina: boolean;
  ultima_atualizacao: string | null;
  prioridade: number;
  motivos: string[];
  proxima_acao: string;
}

export interface OpportunityList {
  version: string;
  generated_at: string;
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  itens: OpportunityRow[];
  limitacao: string;
}
