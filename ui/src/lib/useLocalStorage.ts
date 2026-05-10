import { useCallback, useState } from 'react';

/**
 * Persists a value in window.localStorage under `key`. Reads on mount;
 * writes on every set. Falls back to `initial` on read error (corrupt
 * JSON, quota, etc.) and silently ignores write errors.
 */
export function useLocalStorage<T>(key: string, initial: T): [T, (v: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = window.localStorage.getItem(key);
      return raw === null ? initial : (JSON.parse(raw) as T);
    } catch {
      return initial;
    }
  });
  const set = useCallback(
    (v: T) => {
      setValue(v);
      try {
        window.localStorage.setItem(key, JSON.stringify(v));
      } catch {
        // quota exceeded / disabled storage: silently ignore
      }
    },
    [key],
  );
  return [value, set];
}
