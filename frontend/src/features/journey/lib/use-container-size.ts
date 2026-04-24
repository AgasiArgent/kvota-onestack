"use client";

/**
 * Tracks the live size of a DOM element via `ResizeObserver`.
 *
 * Used by the pin overlay (Task 22) to recompute pin positions when the
 * screenshot container resizes. SSR-safe: returns `{width: 0, height: 0}`
 * until the effect runs on mount.
 */

import { useEffect, useState, type RefObject } from "react";

export interface ContainerSize {
  readonly width: number;
  readonly height: number;
}

export function useContainerSize(
  ref: RefObject<HTMLElement | null>,
): ContainerSize {
  const [size, setSize] = useState<ContainerSize>({ width: 0, height: 0 });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof ResizeObserver === "undefined") {
      // SSR fallback / very old browsers — read clientRect once.
      const rect = el.getBoundingClientRect();
      setSize({ width: rect.width, height: rect.height });
      return;
    }
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const box = entry.contentBoxSize?.[0];
      if (box) {
        setSize({ width: box.inlineSize, height: box.blockSize });
      } else {
        const rect = entry.contentRect;
        setSize({ width: rect.width, height: rect.height });
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);

  return size;
}
