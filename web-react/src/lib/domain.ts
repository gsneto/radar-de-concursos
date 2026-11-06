import type { Tone } from '@/components/ui/badge';

export const readinessLabels: Record<string, string> = {
  oportunidade_historica: 'Oportunidade histórica',
  identidade_cargo_pendente: 'Identidade pendente',
  campos_decisivos_ausentes: 'Campos ausentes',
  conflito_documental_pendente: 'Conflito documental',
};

export const readinessTones: Record<string, Tone> = {
  oportunidade_historica: 'neutral',
  identidade_cargo_pendente: 'warn',
  campos_decisivos_ausentes: 'accent',
  conflito_documental_pendente: 'risk',
};

export const readinessColors: Record<string, string> = {
  oportunidade_historica: '#64748b',
  identidade_cargo_pendente: 'var(--color-warn)',
  campos_decisivos_ausentes: 'var(--color-accent)',
  conflito_documental_pendente: 'var(--color-risk)',
};

export const siLabels: Record<string, string> = {
  explicito: 'Aceitação expressa',
  categoria_inclui_curso: 'Categoria inclui o curso',
  area_correlata_interpretacao: 'Exige interpretação',
  outras_formacoes: 'Outras formações',
  nao_informado: 'Não informado',
  nao_encontrado: 'Não encontrado',
  extracao_incompleta: 'Extração incompleta',
};

export const siShort: Record<string, string> = {
  explicito: 'Aceitação expressa',
  categoria_inclui_curso: 'Categoria inclui',
  area_correlata_interpretacao: 'Exige interpretação',
  outras_formacoes: 'Outras formações',
  nao_informado: 'Não informado',
  nao_encontrado: 'Não encontrado',
  extracao_incompleta: 'Extração incompleta',
};

export const siTones: Record<string, Tone> = {
  explicito: 'ok',
  categoria_inclui_curso: 'ok',
  area_correlata_interpretacao: 'warn',
  outras_formacoes: 'neutral',
  nao_informado: 'unknown',
  nao_encontrado: 'unknown',
  extracao_incompleta: 'warn',
};

export const indigenousLabels: Record<string, string> = {
  explicito_imediato: 'Vaga exclusiva publicada',
  apenas_reserva: 'Apenas reserva',
  explicito_sem_vaga_imediata: 'Modalidade explícita, sem vaga imediata',
  mencao_sem_quantidade: 'Menção sem quantidade',
  reserva_combinada_com_outros_grupos: 'Reserva combinada',
  mencao_fora_do_escopo_de_reserva: 'Fora do escopo de reserva',
  fora_do_escopo_de_reserva: 'Fora do escopo de reserva',
  agregado_sem_modalidade: 'Agregado sem modalidade',
  nao_mencionado: 'Não mencionado',
  nao_pesquisado: 'Não pesquisado',
  reserva_sem_quantidade: 'Reserva sem quantidade',
};

export const indigenousShort: Record<string, string> = {
  explicito_imediato: 'Vaga exclusiva',
  apenas_reserva: 'Apenas reserva',
  explicito_sem_vaga_imediata: 'Sem vaga imediata',
  mencao_sem_quantidade: 'Menção sem qtd.',
  reserva_combinada_com_outros_grupos: 'Reserva combinada',
  mencao_fora_do_escopo_de_reserva: 'Fora do escopo',
  fora_do_escopo_de_reserva: 'Fora do escopo',
  agregado_sem_modalidade: 'Sem modalidade',
  nao_mencionado: 'Não mencionado',
  nao_pesquisado: 'Não pesquisado',
  reserva_sem_quantidade: 'Sem quantidade',
};

export const indigenousTones: Record<string, Tone> = {
  explicito_imediato: 'accent',
  apenas_reserva: 'verified',
  explicito_sem_vaga_imediata: 'verified',
  mencao_sem_quantidade: 'neutral',
  reserva_combinada_com_outros_grupos: 'warn',
  mencao_fora_do_escopo_de_reserva: 'neutral',
  fora_do_escopo_de_reserva: 'neutral',
  agregado_sem_modalidade: 'neutral',
  nao_mencionado: 'unknown',
  nao_pesquisado: 'unknown',
  reserva_sem_quantidade: 'verified',
};

export const urgencyLabels: Record<string, string> = {
  hoje: 'Hoje',
  ate_7_dias: 'Até 7 dias',
  ate_30_dias: 'Até 30 dias',
  futuro: 'Futuro',
  vencido: 'Vencido',
  sem_data: 'Sem data',
};

export const deadlineGroups: Record<string, string> = {
  inscricao_inicio: 'Início das inscrições',
  inscricao_fim: 'Fim das inscrições',
  isencao_inicio: 'Início da isenção',
  isencao_fim: 'Fim da isenção',
  recurso_isencao: 'Recurso da isenção',
  resultado_isencao_preliminar: 'Resultado preliminar da isenção',
  resultado_isencao_final: 'Resultado final da isenção',
  pagamento: 'Pagamento da taxa',
};

export const documentalLabels: Record<string, string> = {
  campos_confirmados: 'Campos confirmados',
  campos_candidatos: 'Campos candidatos',
  edital_extraido: 'Edital extraído',
  conflito: 'Documentação conflitante',
  oficial_sem_extracao: 'Oficial sem extração',
  oficial_sem_edital: 'Oficial sem edital',
  identidade_pendente: 'Identidade pendente',
  obtencao_nao_autorizada: 'Obtenção não autorizada',
  oficial_nao_importado: 'Oficial não importado',
  apenas_agregador: 'Apenas agregador',
  fonte_nao_catalogada: 'Fonte não catalogada',
  sem_documento: 'Sem documento',
};

export const documentTypes: Record<string, string> = {
  edital_abertura: 'Edital de abertura',
  edital_retificado: 'Edital retificado',
  retificacao: 'Retificação',
  cronograma: 'Cronograma',
  comunicado: 'Comunicado',
  resultado: 'Resultado',
  convocacao: 'Convocação',
  homologacao: 'Homologação',
  gabarito: 'Gabarito',
  anexo: 'Anexo',
  pagina_concurso: 'Página do concurso',
  pagina_banca: 'Página da banca',
  pagina_agregador: 'Página de agregador',
  outro: 'Documento',
};

export const extractionLabels: Record<string, string> = {
  nao_iniciada: 'Não iniciada',
  em_andamento: 'Em andamento',
  parcial: 'Parcial',
  concluida: 'Concluída',
  falhou: 'Falhou',
};

export const cycleLabels: Record<string, string> = {
  concluido: 'Concluído',
  parcial: 'Parcial',
  falhou: 'Falhou',
  interrompido: 'Interrompido',
  em_andamento: 'Em andamento',
};

export const cycleTones: Record<string, Tone> = {
  concluido: 'ok',
  parcial: 'warn',
  falhou: 'risk',
  interrompido: 'warn',
  em_andamento: 'accent',
};

export const fieldLabels: Record<string, string> = {
  immediate_vacancies: 'Vagas imediatas',
  vagas_total_publicado: 'Total publicado',
  reserve_vacancies: 'Cadastro de reserva',
  indigenous_vacancies: 'Vagas indígenas exclusivas',
  indigenous_reserve_vacancies: 'Reserva indígena',
  education: 'Escolaridade/requisito',
  accepted_courses: 'Cursos aceitos',
  si_compatibility: 'Compatibilidade com SI',
  registration_start: 'Início das inscrições',
  registration_end: 'Fim das inscrições',
  exam_date: 'Data da prova',
  exam_location: 'Local de prova',
  work_location: 'Local de exercício',
};

export function label(map: Record<string, string>, value: unknown, fallback = '—'): string {
  if (value === null || value === undefined || value === '') return fallback;
  return map[String(value)] ?? String(value).replace(/_/g, ' ');
}

/**
 * Converte títulos e rótulos totalmente em maiúsculas (ALL CAPS) em Title Case elegante.
 * Preserva termos técnicos curtos conhecidos (como SI, TI, DRE, FGV, etc.) e preposições.
 */
export function formatTitleCase(text: string | null | undefined): string {
  if (!text) return '';
  const trimmed = text.trim();
  const letters = trimmed.replace(/[^a-zA-ZÀ-ÿ]/g, '');
  if (letters.length >= 3 && letters === letters.toUpperCase()) {
    const lowercaseWords = new Set([
      'e', 'de', 'da', 'do', 'das', 'dos', 'em', 'para', 'com', 'por', 'a', 'o', 'as', 'os', 'no', 'na', 'nos', 'nas'
    ]);
    const uppercaseAcronyms = new Set([
      'ti', 'si', 'dre', 'fgv', 'dou', 'uf', 'cebraspe', 'fcc', 'pci', 'abdi', 'pas', 'pst', 'tjpb', 'tjrj', 'tjsp'
    ]);

    return trimmed
      .toLowerCase()
      .split(/\s+/)
      .map((word, index) => {
        const cleanWord = word.replace(/[^a-zÀ-ÿ]/g, '');
        if (uppercaseAcronyms.has(cleanWord)) {
          return word.toUpperCase();
        }
        if (index > 0 && lowercaseWords.has(cleanWord)) {
          return word;
        }
        return word.charAt(0).toUpperCase() + word.slice(1);
      })
      .join(' ');
  }
  return trimmed;
}
