import { useEffect, useState } from "react";

/** State persisted in sessionStorage so drafts survive navigation between modules. */
export function useDraft<T>(key: string, initial: T): [T, (v: T) => void] {
  const storageKey = `devpilot.draft.${key}`;
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = sessionStorage.getItem(storageKey);
      return raw != null ? (JSON.parse(raw) as T) : initial;
    } catch {
      return initial;
    }
  });
  useEffect(() => {
    const t = setTimeout(() => {
      try {
        sessionStorage.setItem(storageKey, JSON.stringify(value));
      } catch {
        /* quota exceeded: drafts are best-effort */
      }
    }, 250);
    return () => clearTimeout(t);
  }, [storageKey, value]);
  return [value, setValue];
}
