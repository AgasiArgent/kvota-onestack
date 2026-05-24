"use client";

/**
 * React hook owning the КП form snapshot + zoom level.
 *
 * Responsibilities:
 * - Hydrate from `localStorage` on mount; fall back to `DEFAULT_PROPOSAL`
 *   when the storage entry is missing or corrupted (REQ-2.1, REQ-2.3).
 * - Persist every state change to `localStorage`; swallow `QuotaExceededError`
 *   silently per ADR-7 (form state lives in React anyway, so cross-reload
 *   survival is the only thing degraded).
 * - Expose `clear()` and `loadExample()` for the form header buttons (the
 *   confirm dialogs live in the calling component — this hook just mutates
 *   state).
 * - Persist and restore zoom level (range 0.3–1.2, default 0.7).
 *
 * Hydration strategy: lazy initializer in `useState`. We read from
 * `localStorage` inside the initializer (which runs once on mount) so the
 * client-side initial render already shows persisted data — no flash of
 * default content, and no `useEffect` + `setState` cascade. On the server
 * `window` is undefined so we fall back to the default; the first client
 * render then reads the real value and React re-renders.
 *
 * The hook lives in a "use client" file, so the component using it is
 * always rendered on the client — there's no SSR/CSR hydration mismatch
 * because both passes inside the same client run share the initializer
 * output.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { DEFAULT_PROPOSAL } from "../model/default-data";
import { EMPTY_PROPOSAL } from "../model/empty-data";
import type { KpProposal } from "../model/types";

export const KP_STORAGE_KEY = "kvotaflow.kp.v1";
export const KP_ZOOM_STORAGE_KEY = "kvotaflow.kp.v1.zoom";

const DEFAULT_ZOOM = 0.7;
const MIN_ZOOM = 0.3;
const MAX_ZOOM = 1.2;

function safeReadProposal(): KpProposal {
  if (typeof window === "undefined") return DEFAULT_PROPOSAL;
  try {
    const raw = window.localStorage.getItem(KP_STORAGE_KEY);
    if (!raw) return DEFAULT_PROPOSAL;
    const parsed = JSON.parse(raw) as Partial<KpProposal>;
    // Shallow merge so missing keys fall back to defaults if the schema
    // changes between versions (we bump the storage key on breaking changes).
    return { ...DEFAULT_PROPOSAL, ...parsed };
  } catch (e) {
    // Corrupted JSON (manual edit, partial write) — log once so a future
    // bug isn't masked. REQ-2.6's silent-fallback contract is only for
    // storage unavailability (QuotaExceededError / SecurityError /
    // no-window), not for malformed payloads.
    if (e instanceof SyntaxError) {
      console.warn("KP localStorage corrupted, resetting to defaults", e);
    }
    return DEFAULT_PROPOSAL;
  }
}

function safeReadZoom(): number {
  if (typeof window === "undefined") return DEFAULT_ZOOM;
  try {
    const raw = window.localStorage.getItem(KP_ZOOM_STORAGE_KEY);
    if (!raw) return DEFAULT_ZOOM;
    const parsed = Number(raw);
    if (!Number.isFinite(parsed)) return DEFAULT_ZOOM;
    if (parsed < MIN_ZOOM || parsed > MAX_ZOOM) return DEFAULT_ZOOM;
    return parsed;
  } catch (e) {
    if (e instanceof SyntaxError) {
      console.warn("KP zoom localStorage corrupted, resetting to default", e);
    }
    return DEFAULT_ZOOM;
  }
}

function safeWrite(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value);
  } catch (e) {
    // ADR-7: localStorage may be full, blocked (private Safari), or
    // unavailable. Quota / security errors are expected — degrade silently
    // since in-memory React state still works, only cross-reload survival
    // is lost. Any other exception (e.g. TypeError from a circular
    // structure passed by a future caller) is a bug — surface it.
    const isExpected =
      e instanceof DOMException &&
      (e.name === "QuotaExceededError" || e.name === "SecurityError");
    if (!isExpected) {
      console.warn("KP localStorage write failed", e);
    }
  }
}

export interface UseKpStateReturn {
  data: KpProposal;
  setData: React.Dispatch<React.SetStateAction<KpProposal>>;
  clear: () => void;
  loadExample: () => void;
  zoom: number;
  setZoom: React.Dispatch<React.SetStateAction<number>>;
}

export function useKpState(): UseKpStateReturn {
  // Lazy initializers run once on mount. On the client `window` is defined
  // so we read directly from localStorage; the first render shows persisted
  // data without an effect-driven re-render cascade.
  const [data, setData] = useState<KpProposal>(safeReadProposal);
  const [zoom, setZoom] = useState<number>(safeReadZoom);

  // Skip persistence on the very first render — the value we'd write back
  // is exactly what we just read.
  const firstRunRef = useRef(true);
  useEffect(() => {
    if (firstRunRef.current) {
      firstRunRef.current = false;
      return;
    }
    safeWrite(KP_STORAGE_KEY, JSON.stringify(data));
  }, [data]);

  const firstZoomRef = useRef(true);
  useEffect(() => {
    if (firstZoomRef.current) {
      firstZoomRef.current = false;
      return;
    }
    safeWrite(KP_ZOOM_STORAGE_KEY, String(zoom));
  }, [zoom]);

  const clear = useCallback(() => {
    setData(EMPTY_PROPOSAL);
  }, []);

  const loadExample = useCallback(() => {
    setData(DEFAULT_PROPOSAL);
  }, []);

  return { data, setData, clear, loadExample, zoom, setZoom };
}
