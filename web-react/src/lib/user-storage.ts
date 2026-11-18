import { useCallback, useEffect, useRef, useState } from 'react';

export function scopedStorageKey(baseKey: string, userId?: string | null): string {
  const scope = userId && userId.trim() ? userId.trim() : 'local';
  return `radar:u:${scope}:${baseKey}`;
}

function readFromStorage<T>(
  fullKey: string,
  fallback: T,
  allowLegacyMigration: boolean,
  legacyKey?: string,
): T {
  try {
    const raw = localStorage.getItem(fullKey);
    if (raw !== null) {
      return JSON.parse(raw) as T;
    }
    if (allowLegacyMigration && legacyKey) {
      const legacyRaw = localStorage.getItem(legacyKey);
      if (legacyRaw !== null) {
        const parsed = JSON.parse(legacyRaw) as T;
        localStorage.setItem(fullKey, legacyRaw);
        return parsed;
      }
    }
  } catch {
    /* ignore malformed or unavailable storage */
  }
  return fallback;
}

export function useUserStorage<T>(
  baseKey: string,
  initialValue: T,
  userId?: string | null,
  legacyKey?: string,
): [T, (next: T | ((prev: T) => T)) => void, () => void] {
  const fullKey = scopedStorageKey(baseKey, userId);
  const isLocalProfile = !userId || !userId.trim();
  const fallbackRef = useRef(initialValue);

  const [state, setState] = useState<T>(() =>
    readFromStorage(fullKey, fallbackRef.current, isLocalProfile, legacyKey),
  );

  useEffect(() => {
    setState(readFromStorage(fullKey, fallbackRef.current, isLocalProfile, legacyKey));
  }, [fullKey, isLocalProfile, legacyKey]);

  const setValue = useCallback(
    (next: T | ((prev: T) => T)) => {
      setState((prev) => {
        const resolved = typeof next === 'function' ? (next as (p: T) => T)(prev) : next;
        try {
          localStorage.setItem(fullKey, JSON.stringify(resolved));
        } catch {
          /* ignore quota/privacy errors */
        }
        return resolved;
      });
    },
    [fullKey],
  );

  const clearValue = useCallback(() => {
    setState(fallbackRef.current);
    try {
      localStorage.removeItem(fullKey);
      if (isLocalProfile && legacyKey) {
        localStorage.removeItem(legacyKey);
      }
    } catch {
      /* ignore */
    }
  }, [fullKey, isLocalProfile, legacyKey]);

  return [state, setValue, clearValue];
}
