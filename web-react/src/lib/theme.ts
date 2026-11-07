import { useEffect, useState } from 'react';

export type Theme = 'dark' | 'light';

const THEME_KEY = 'radar_theme';

export function getStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === 'light' || stored === 'dark') {
      return stored;
    }
  } catch {
    // Modo restrito de cookies/localStorage
  }
  return 'dark';
}

export function applyTheme(theme: Theme) {
  const root = document.documentElement;
  const metaColorScheme = document.querySelector('meta[name="color-scheme"]');
  const metaThemeColor = document.querySelector('meta[name="theme-color"]');

  if (theme === 'light') {
    root.classList.remove('dark');
    root.classList.add('light');
    root.setAttribute('data-theme', 'light');
    root.style.colorScheme = 'light';
    if (metaColorScheme) metaColorScheme.setAttribute('content', 'light');
    if (metaThemeColor) metaThemeColor.setAttribute('content', '#f8fafc');
  } else {
    root.classList.remove('light');
    root.classList.add('dark');
    root.setAttribute('data-theme', 'dark');
    root.style.colorScheme = 'dark';
    if (metaColorScheme) metaColorScheme.setAttribute('content', 'dark');
    if (metaThemeColor) metaThemeColor.setAttribute('content', '#07090d');
  }

  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    // Modo restrito
  }
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(getStoredTheme);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const toggleTheme = () => {
    setThemeState((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  const setTheme = (next: Theme) => {
    setThemeState(next);
  };

  return { theme, toggleTheme, setTheme };
}
