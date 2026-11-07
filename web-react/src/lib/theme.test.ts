import { beforeEach, describe, expect, it } from 'vitest';
import { applyTheme, getStoredTheme } from './theme';

describe('theme utilities', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.className = '';
    document.documentElement.removeAttribute('data-theme');
  });

  it('retorna dark como padrão quando localStorage está vazio', () => {
    expect(getStoredTheme()).toBe('dark');
  });

  it('aplica tema light e atualiza classes no documentElement e localStorage', () => {
    applyTheme('light');
    expect(document.documentElement.classList.contains('light')).toBe(true);
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(localStorage.getItem('radar_theme')).toBe('light');
  });

  it('aplica tema dark e atualiza classes no documentElement e localStorage', () => {
    applyTheme('light');
    applyTheme('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(document.documentElement.classList.contains('light')).toBe(false);
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(localStorage.getItem('radar_theme')).toBe('dark');
  });
});
