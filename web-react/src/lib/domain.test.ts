import { describe, expect, it } from 'vitest';
import { indigenousLabels, label, siLabels, siTones } from './domain';

describe('label', () => {
  it('usa o rótulo mapeado', () => {
    expect(label(siLabels, 'explicito')).toBe('Aceitação expressa');
  });

  it('valor desconhecido é humanizado, não inventado', () => {
    expect(label(siLabels, 'estado_novo')).toBe('estado novo');
  });

  it('ausente usa o fallback', () => {
    expect(label(siLabels, null)).toBe('—');
    expect(label(siLabels, '', 'Não informado')).toBe('Não informado');
  });
});

// Regra §7.5: compatibilidade com SI vem do estado calculado. Só aceitação
// expressa ou categoria que inclui o curso podem aparecer como positivas.
describe('compatibilidade com SI', () => {
  it('apenas estados com evidência formal têm tom positivo', () => {
    const positivos = Object.entries(siTones)
      .filter(([, tone]) => tone === 'ok')
      .map(([key]) => key)
      .sort();
    expect(positivos).toEqual(['categoria_inclui_curso', 'explicito']);
  });

  it('interpretação de área correlata não é positiva', () => {
    expect(siTones.area_correlata_interpretacao).toBe('warn');
  });
});

// Regra §7.4: reserva indígena e vaga exclusiva são coisas distintas.
describe('rótulos indígenas', () => {
  it('distinguem vaga exclusiva de reserva', () => {
    expect(indigenousLabels.explicito_imediato).toMatch(/exclusiva/i);
    expect(indigenousLabels.apenas_reserva).toMatch(/reserva/i);
    expect(indigenousLabels.apenas_reserva).not.toMatch(/exclusiva/i);
  });
});
