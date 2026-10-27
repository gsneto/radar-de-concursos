/** Formatação pt-BR determinística. Ausente nunca vira zero. */

export const UNKNOWN = 'Não informado';

export const isMissing = (value: unknown): boolean =>
  value === null || value === undefined || value === '';

export function integer(value: unknown): string {
  if (isMissing(value)) return UNKNOWN;
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n)) return UNKNOWN;
  return n.toLocaleString('pt-BR', { maximumFractionDigits: 0 });
}

export function percent(value: unknown, digits = 1): string {
  if (isMissing(value)) return UNKNOWN;
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n)) return UNKNOWN;
  return (
    n.toLocaleString('pt-BR', {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }) + '%'
  );
}

export function date(value: unknown): string {
  if (isMissing(value)) return UNKNOWN;
  const d = new Date(String(value));
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' });
}

export function shortDate(value: unknown): string {
  if (isMissing(value)) return '—';
  const d = new Date(String(value));
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
}

export function dayMonth(value: unknown): { day: string; month: string } {
  if (isMissing(value)) return { day: '—', month: '' };
  const d = new Date(String(value));
  if (Number.isNaN(d.getTime())) return { day: '—', month: '' };
  return {
    day: String(d.getDate()).padStart(2, '0'),
    month: d.toLocaleDateString('pt-BR', { month: 'short' }).replace('.', ''),
  };
}

export function dateTime(value: unknown): string {
  if (isMissing(value)) return UNKNOWN;
  const d = new Date(String(value));
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function longToday(now = new Date()): string {
  return now.toLocaleDateString('pt-BR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}

export function duration(seconds: unknown): string {
  if (isMissing(seconds)) return UNKNOWN;
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  if (h > 0) return `${h}h ${String(m).padStart(2, '0')}min`;
  if (m > 0) return `${m}min`;
  if (total > 0) return `${total}s`;
  return '0 min';
}

export function clock(seconds: unknown): string {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return [h, m, s].map((n) => String(n).padStart(2, '0')).join(':');
}

export function relativeDays(value: unknown): string {
  if (isMissing(value)) return 'Sem data';
  const n = Number(value);
  if (!Number.isFinite(n)) return 'Sem data';
  if (n === 0) return 'Hoje';
  if (n === 1) return 'Amanhã';
  if (n > 1) return `Em ${n} dias`;
  return `Há ${Math.abs(n)} dias`;
}

export function truncate(value: unknown, max = 160): string {
  const text = isMissing(value) ? '' : String(value);
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1).trimEnd()}…`;
}

export function safeUrl(value: unknown): string | null {
  if (isMissing(value)) return null;
  try {
    const url = new URL(String(value), window.location.href);
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : null;
  } catch {
    return null;
  }
}

export function percentOf(part: unknown, total: unknown): number | null {
  const p = Number(part);
  const t = Number(total);
  if (!Number.isFinite(p) || !Number.isFinite(t) || t <= 0) return null;
  return Math.round((p / t) * 1000) / 10;
}

/** Converte rótulo técnico em texto legível, sem inventar significado. */
export function humanize(value: unknown): string {
  if (isMissing(value)) return '—';
  return String(value).replace(/_/g, ' ');
}
