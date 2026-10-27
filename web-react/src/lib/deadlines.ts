/**
 * Recorte de prazos da interface.
 *
 * "Prazos próximos" existe para agir: inscrição, isenção e data da prova. Resultado
 * de isenção e recurso são acompanhamento, não prazo a cumprir — continuam visíveis
 * na página Prazos quando o filtro é limpo.
 */
export const OPERATIONAL_GROUPS = [
  'inscricao_inicio',
  'inscricao_fim',
  'isencao_inicio',
  'isencao_fim',
  'data_prova',
] as const;

export type OperationalGroup = (typeof OPERATIONAL_GROUPS)[number];

const operational = new Set<string>(OPERATIONAL_GROUPS);

export function isOperationalGroup(group: unknown): boolean {
  return typeof group === 'string' && operational.has(group);
}

/** Parâmetro `groups` do calendário, ou undefined quando não há recorte. */
export function groupsParam(groups: readonly string[] | null | undefined): string | undefined {
  if (!groups || !groups.length) return undefined;
  return groups.join(',');
}

/** Janela do card de próximos prazos, em dias. */
export const UPCOMING_DAYS = 30;

export const UPCOMING_URGENCIES = ['hoje', 'ate_7_dias', 'ate_30_dias'] as const;

export function isUpcoming(urgency: unknown): boolean {
  return typeof urgency === 'string' && (UPCOMING_URGENCIES as readonly string[]).includes(urgency);
}
