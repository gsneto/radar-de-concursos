/**
 * Responsável local pelas decisões humanas. Fica no navegador (não no servidor):
 * é o nome que aparece em cada registro append-only.
 */
export const REVIEWER_KEY = 'radar.reviewer';

export function readReviewer(): string {
  try {
    return localStorage.getItem(REVIEWER_KEY) ?? '';
  } catch {
    return '';
  }
}

export function saveReviewer(value: string): void {
  try {
    localStorage.setItem(REVIEWER_KEY, value);
  } catch {
    /* preferência só nesta sessão */
  }
}
