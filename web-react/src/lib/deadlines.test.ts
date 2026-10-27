import { describe, expect, it } from 'vitest';
import {
  OPERATIONAL_GROUPS,
  groupsParam,
  isOperationalGroup,
  isUpcoming,
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
