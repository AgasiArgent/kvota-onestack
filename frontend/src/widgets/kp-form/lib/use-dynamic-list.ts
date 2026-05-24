"use client";

/**
 * Reusable add/remove/update helpers for the dynamic lists in the КП form
 * (`items`, `specs`, `packaging`, `conditions`).
 *
 * The hook is purely a wrapper around a controlled list + setter; it does
 * not own the list state. Owning the state on the caller side keeps the
 * proposal as a single source of truth (one big setData on the page).
 *
 * All updates are immutable spreads — never mutate the incoming array.
 */

import { useCallback } from "react";

export interface UseDynamicListReturn<T> {
  add: (value: T) => void;
  remove: (index: number) => void;
  update: (index: number, value: T) => void;
}

export function useDynamicList<T>(
  items: T[],
  setItems: (next: T[]) => void,
): UseDynamicListReturn<T> {
  const add = useCallback(
    (value: T) => {
      setItems([...items, value]);
    },
    [items, setItems],
  );

  const remove = useCallback(
    (index: number) => {
      setItems(items.filter((_, i) => i !== index));
    },
    [items, setItems],
  );

  const update = useCallback(
    (index: number, value: T) => {
      const next = [...items];
      next[index] = value;
      setItems(next);
    },
    [items, setItems],
  );

  return { add, remove, update };
}
