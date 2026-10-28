import { describe, expect, it } from 'vitest';
import {
  OPERATIONAL_GROUPS,
  groupsParam,
  isOperationalGroup,
  isUpcoming,
  nextOperationalDeadline,
} from './deadlines';

describe('grupos operacionais de prazo', () => {
  it('inclui inscrição, isenção e data da prova', () => {
    expect([...OPERATIONAL_GROUPS]).toEqual([
      'inscricao_inicio',
      'inscricao_fim',
      'isencao_inicio',
      'isencao_fim',
      'data_prova',
    ]);
  });

  // O pedido do usuário: resultado e recurso de isenção não são prazo a cumprir.
  it('exclui resultado de isenção e recurso', () => {
    for (const group of [
      'resultado_isencao_preliminar',
      'resultado_isencao_final',
      'recurso_isencao',
    ]) {
      expect(isOperationalGroup(group)).toBe(false);
    }
  });

  it('reconhece os grupos operacionais e recusa lixo', () => {
    expect(isOperationalGroup('inscricao_fim')).toBe(true);
    expect(isOperationalGroup('data_prova')).toBe(true);
    expect(isOperationalGroup('xyz')).toBe(false);
    expect(isOperationalGroup(null)).toBe(false);
    expect(isOperationalGroup(undefined)).toBe(false);
  });
});

describe('groupsParam', () => {
  it('monta a lista separada por vírgula', () => {
    expect(groupsParam(['inscricao_fim', 'data_prova'])).toBe('inscricao_fim,data_prova');
  });

  it('lista vazia não gera filtro', () => {
    expect(groupsParam([])).toBeUndefined();
    expect(groupsParam(null)).toBeUndefined();
    expect(groupsParam(undefined)).toBeUndefined();
  });
});

describe('nextOperationalDeadline', () => {
  const prazo = (grupo: string, dias: number, valor = '2026-11-18') => ({
    grupo,
    estado_temporal: 'futuro',
    dias_restantes: dias,
    valor,
  });

  // O caso real: recurso de isenção em 1 dia não é o "prazo" da oportunidade.
  it('ignora resultado e recurso de isenção mesmo sendo mais próximos', () => {
    const prazos = [prazo('recurso_isencao', 1), prazo('inscricao_fim', 22)];
    expect(nextOperationalDeadline(prazos)?.grupo).toBe('inscricao_fim');
  });

  it('escolhe o mais próximo entre os operacionais', () => {
    const prazos = [prazo('data_prova', 40), prazo('isencao_fim', 5), prazo('inscricao_inicio', 9)];
    expect(nextOperationalDeadline(prazos)?.grupo).toBe('isencao_fim');
  });

  it('só com grupos não operacionais devolve null', () => {
    expect(nextOperationalDeadline([prazo('resultado_isencao_final', 3)])).toBeNull();
  });

  it('descarta prazo passado, sem data ou sem dias', () => {
    expect(
      nextOperationalDeadline([
        { grupo: 'inscricao_fim', estado_temporal: 'expirado', dias_restantes: -5, valor: '2020-01-01' },
        { grupo: 'inscricao_inicio', estado_temporal: 'futuro', dias_restantes: null, valor: null },
      ]),
    ).toBeNull();
  });

  it('lista vazia devolve null', () => {
    expect(nextOperationalDeadline([])).toBeNull();
    expect(nextOperationalDeadline(null)).toBeNull();
  });
});

describe('janela de próximos prazos', () => {
  it('aceita hoje, até 7 e até 30 dias', () => {
    expect(isUpcoming('hoje')).toBe(true);
    expect(isUpcoming('ate_7_dias')).toBe(true);
    expect(isUpcoming('ate_30_dias')).toBe(true);
  });

  it('recusa futuro distante, vencido e sem data', () => {
    expect(isUpcoming('futuro')).toBe(false);
    expect(isUpcoming('vencido')).toBe(false);
    expect(isUpcoming('sem_data')).toBe(false);
  });
});
