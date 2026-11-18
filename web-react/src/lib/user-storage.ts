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
  ready = true,
): [T, (next: T | ((prev: T) => T)) => void, () => void] {
  const fullKey = scopedStorageKey(baseKey, userId);
  const isLocalProfile = !userId || !userId.trim();
  const fallbackRef = useRef(initialValue);

  const [entry, setEntry] = useState<{ key: string; value: T }>(() =>
    ready
      ? {
          key: fullKey,
          value: readFromStorage(fullKey, fallbackRef.current, isLocalProfile, legacyKey),
        }
      : { key: '__pending__', value: fallbackRef.current },
  );

  const currentValue = !ready
    ? fallbackRef.current
    : entry.key === fullKey
      ? entry.value
      : readFromStorage(fullKey, fallbackRef.current, isLocalProfile, legacyKey);

  useEffect(() => {
    if (!ready) return;
    setEntry((prev) =>
      prev.key === fullKey
        ? prev
        : {
            key: fullKey,
            value: readFromStorage(fullKey, fallbackRef.current, isLocalProfile, legacyKey),
          },
    );
  }, [fullKey, isLocalProfile, legacyKey, ready]);

  const setValue = useCallback(
    (next: T | ((prev: T) => T)) => {
      setEntry((prev) => {
        const base =
          ready && prev.key === fullKey
            ? prev.value
            : ready
              ? readFromStorage(fullKey, fallbackRef.current, isLocalProfile, legacyKey)
              : fallbackRef.current;
        const resolved = typeof next === 'function' ? (next as (p: T) => T)(base) : next;
        if (ready) {
          try {
            localStorage.setItem(fullKey, JSON.stringify(resolved));
          } catch {
            /* ignore quota/privacy errors */
          }
        }
        return { key: ready ? fullKey : '__pending__', value: resolved };
      });
    },
    [fullKey, isLocalProfile, legacyKey, ready],
  );

  const clearValue = useCallback(() => {
    setEntry({ key: ready ? fullKey : '__pending__', value: fallbackRef.current });
    if (!ready) return;
    try {
      localStorage.removeItem(fullKey);
      if (isLocalProfile && legacyKey) {
        localStorage.removeItem(legacyKey);
      }
    } catch {
      /* ignore */
    }
  }, [fullKey, isLocalProfile, legacyKey, ready]);

  return [currentValue, setValue, clearValue];
}
