import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { scopedStorageKey, useUserStorage } from './user-storage';

describe('useUserStorage', () => {
  beforeEach(() => localStorage.clear());

  it('gera chave determinística escopada por userId', () => {
    expect(scopedStorageKey('completed_lessons', 'alice-1')).toBe(
      'radar:u:alice-1:completed_lessons',
    );
    expect(scopedStorageKey('completed_lessons', null)).toBe('radar:u:local:completed_lessons');
  });

  it('isola dados entre dois userIds distintos no mesmo navegador', () => {
    const { result, rerender } = renderHook(
      ({ uid }) => useUserStorage<string[]>('completed_lessons', [], uid),
      { initialProps: { uid: 'alice-1' as string | null } },
    );
    act(() => result.current[1](['bd-01']));
    expect(result.current[0]).toEqual(['bd-01']);

    rerender({ uid: 'bob-2' });
    expect(result.current[0]).toEqual([]);

    rerender({ uid: 'alice-1' });
    expect(result.current[0]).toEqual(['bd-01']);
  });

  it('migra chave legada apenas para o perfil local sem vazar para estudantes logados', () => {
    localStorage.setItem('radar_completed_lessons', JSON.stringify(['seg-01']));

    const { result: studentResult } = renderHook(() =>
      useUserStorage<string[]>('completed_lessons', [], 'bob-2', 'radar_completed_lessons'),
    );
    expect(studentResult.current[0]).toEqual([]);

    const { result: localResult } = renderHook(() =>
      useUserStorage<string[]>('completed_lessons', [], null, 'radar_completed_lessons'),
    );
    expect(localResult.current[0]).toEqual(['seg-01']);
  });
});
