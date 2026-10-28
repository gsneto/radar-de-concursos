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

interface DeadlineLike {
  grupo: string;
  estado_temporal?: string | null;
  dias_restantes?: number | null;
  valor?: string | null;
}

/**
 * Próximo prazo que exige ação, não o próximo evento qualquer.
 *
 * Sem o recorte, uma oportunidade aparecia com "Recurso da isenção · amanhã" como
 * prazo principal, escondendo a inscrição que de fato importa.
 */
export function nextOperationalDeadline<T extends DeadlineLike>(
  prazos: readonly T[] | null | undefined,
): T | null {
  if (!prazos || !prazos.length) return null;
  const future = prazos
    .filter(
      (item) =>
        isOperationalGroup(item.grupo) &&
        item.estado_temporal === 'futuro' &&
        item.dias_restantes !== null &&
        item.dias_restantes !== undefined,
    )
    .sort((a, b) => (a.dias_restantes ?? 0) - (b.dias_restantes ?? 0));
  return future[0] ?? null;
}

/** Janela do card de próximos prazos, em dias. */
export const UPCOMING_DAYS = 30;

export const UPCOMING_URGENCIES = ['hoje', 'ate_7_dias', 'ate_30_dias'] as const;

export function isUpcoming(urgency: unknown): boolean {
  return typeof urgency === 'string' && (UPCOMING_URGENCIES as readonly string[]).includes(urgency);
}
