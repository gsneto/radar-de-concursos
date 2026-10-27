import { describe, expect, it } from 'vitest';
import {
  UNKNOWN,
  clock,
  duration,
  humanize,
  integer,
  percent,
  percentOf,
  relativeDays,
  safeUrl,
  truncate,
} from './format';

// Regra de integridade §7.2: ausente vira "Não informado"; zero permanece zero.
describe('integer', () => {
  it('ausente vira Não informado, nunca zero', () => {
    expect(integer(null)).toBe(UNKNOWN);
    expect(integer(undefined)).toBe(UNKNOWN);
    expect(integer('')).toBe(UNKNOWN);
  });

  it('zero permanece zero', () => {
    expect(integer(0)).toBe('0');
    expect(integer('0')).toBe('0');
  });

  it('formata milhar em pt-BR', () => {
    expect(integer(1234)).toBe('1.234');
  });

  it('valor não numérico não vira número inventado', () => {
    expect(integer('abc')).toBe(UNKNOWN);
    expect(integer(Number.NaN)).toBe(UNKNOWN);
  });
});

describe('percent / percentOf', () => {
  it('formata com vírgula decimal', () => {
    expect(percent(12.345)).toBe('12,3%');
  });

  it('ausente vira Não informado', () => {
    expect(percent(null)).toBe(UNKNOWN);
  });

  // Regra §7.3: percentual só com denominador.
  it('sem denominador válido não há percentual', () => {
    expect(percentOf(3, 0)).toBeNull();
    expect(percentOf(3, null)).toBeNull();
    expect(percentOf(null, 10)).toBeNull();
  });

  it('calcula com uma casa decimal', () => {
    expect(percentOf(1, 3)).toBe(33.3);
  });
});

describe('duration / clock', () => {
  it('duração ausente vira Não informado', () => {
    expect(duration(null)).toBe(UNKNOWN);
  });

  it('formata horas, minutos e segundos', () => {
    expect(duration(3_900)).toBe('1h 05min');
    expect(duration(600)).toBe('10min');
    expect(duration(42)).toBe('42s');
    expect(duration(0)).toBe('0 min');
  });

  it('cronômetro nunca fica negativo', () => {
    expect(clock(3_661)).toBe('01:01:01');
    expect(clock(-5)).toBe('00:00:00');
  });
});

describe('relativeDays', () => {
  it('sem data é explícito', () => {
    expect(relativeDays(null)).toBe('Sem data');
  });

  it('hoje, amanhã, futuro e passado', () => {
    expect(relativeDays(0)).toBe('Hoje');
    expect(relativeDays(1)).toBe('Amanhã');
    expect(relativeDays(5)).toBe('Em 5 dias');
    expect(relativeDays(-3)).toBe('Há 3 dias');
  });
});

describe('truncate / humanize', () => {
  it('trunca com reticências sem passar do limite', () => {
    const out = truncate('a'.repeat(200), 10);
    expect(out.length).toBe(10);
    expect(out.endsWith('…')).toBe(true);
  });

  it('humaniza rótulo técnico sem inventar significado', () => {
    expect(humanize('campos_decisivos_ausentes')).toBe('campos decisivos ausentes');
    expect(humanize(null)).toBe('—');
  });
});

describe('safeUrl', () => {
  it('aceita apenas http(s)', () => {
    expect(safeUrl('https://www.gov.br/edital.pdf')).toBe('https://www.gov.br/edital.pdf');
    expect(safeUrl('javascript:alert(1)')).toBeNull();
    expect(safeUrl('data:text/html,oi')).toBeNull();
    expect(safeUrl(null)).toBeNull();
  });
});
