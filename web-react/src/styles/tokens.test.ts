import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

/**
 * Contraste dos tokens de texto, medido no CSS — não estimado.
 *
 * A spec do Observatório (§8) exige ≥ 4,5:1 para texto normal. O tema é escuro,
 * então os tokens de texto são medidos contra as superfícies reais.
 */
const css = readFileSync(resolve(process.cwd(), 'src/styles/tailwind.css'), 'utf-8');

function token(name: string): string {
  const match = css.match(new RegExp(`--color-${name}:\\s*([^;]+);`));
  if (!match) throw new Error(`token ausente: ${name}`);
  return match[1].trim();
}

function hex(value: string): [number, number, number] {
  const raw = value.startsWith('var(')
    ? token(value.slice(value.indexOf('--color-') + 8, value.indexOf(')')))
    : value;
  const text = raw.replace('#', '');
  return [0, 2, 4].map((index) => parseInt(text.slice(index, index + 2), 16)) as [
    number,
    number,
    number,
  ];
}

function luminance(rgb: [number, number, number]): number {
  const [r, g, b] = rgb.map((channel) => {
    const s = channel / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function ratio(a: string, b: string): number {
  const la = luminance(hex(a));
  const lb = luminance(hex(b));
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

const SURFACES = ['bg', 'surface', 'surface-2', 'surface-3'];
const TEXTS = ['fg', 'fg-2', 'fg-3'];

describe('contraste dos tokens de texto', () => {
  for (const text of TEXTS) {
    for (const surface of SURFACES) {
      it(`${text} sobre ${surface} atinge 4,5:1`, () => {
        const value = ratio(token(text), token(surface));
        expect(value).toBeGreaterThanOrEqual(4.5);
      });
    }
  }

  it('fg-3 continua mais discreto que fg-2 (hierarquia preservada)', () => {
    expect(luminance(hex(token('fg-3')))).toBeLessThan(luminance(hex(token('fg-2'))));
  });
});
