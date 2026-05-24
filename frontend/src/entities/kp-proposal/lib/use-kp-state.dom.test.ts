import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";

import {
  useKpState,
  KP_STORAGE_KEY,
  KP_ZOOM_STORAGE_KEY,
} from "./use-kp-state";
import { DEFAULT_PROPOSAL } from "../model/default-data";
import { EMPTY_PROPOSAL } from "../model/empty-data";

// ---------------------------------------------------------------------------
// In-memory localStorage stub. The vitest 4 jsdom default `window.localStorage`
// in this project is incomplete (`clear` / `removeItem` are missing), so we
// install a Map-backed fake before each test. Same pattern as
// `features/customers/ui/__tests__/customers-table.dom.test.tsx`.
// ---------------------------------------------------------------------------

function installLocalStorageStub(): Storage {
  const store = new Map<string, string>();
  const fake: Storage = {
    get length() {
      return store.size;
    },
    clear() {
      store.clear();
    },
    getItem(key: string) {
      return store.has(key) ? (store.get(key) as string) : null;
    },
    key(index: number) {
      return Array.from(store.keys())[index] ?? null;
    },
    removeItem(key: string) {
      store.delete(key);
    },
    setItem(key: string, value: string) {
      store.set(key, String(value));
    },
  };
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: fake,
  });
  return fake;
}

describe("useKpState (dom)", () => {
  beforeEach(() => {
    installLocalStorageStub();
  });

  it("hydrates with DEFAULT_PROPOSAL when storage is empty", () => {
    const { result } = renderHook(() => useKpState());
    expect(result.current.data).toEqual(DEFAULT_PROPOSAL);
    expect(result.current.zoom).toBe(0.7);
  });

  it("restores persisted proposal on mount", () => {
    const persisted = { ...DEFAULT_PROPOSAL, supplier: "ООО «Тест»" };
    window.localStorage.setItem(KP_STORAGE_KEY, JSON.stringify(persisted));
    window.localStorage.setItem(KP_ZOOM_STORAGE_KEY, "0.9");

    const { result } = renderHook(() => useKpState());

    expect(result.current.data.supplier).toBe("ООО «Тест»");
    expect(result.current.zoom).toBe(0.9);
  });

  it("falls back to defaults on malformed storage", () => {
    window.localStorage.setItem(KP_STORAGE_KEY, "{ not json");
    window.localStorage.setItem(KP_ZOOM_STORAGE_KEY, "garbage");

    const { result } = renderHook(() => useKpState());

    expect(result.current.data).toEqual(DEFAULT_PROPOSAL);
    expect(result.current.zoom).toBe(0.7);
  });

  it("persists data changes to localStorage", () => {
    const { result } = renderHook(() => useKpState());
    act(() => {
      result.current.setData((prev) => ({ ...prev, supplier: "Updated" }));
    });

    const stored = window.localStorage.getItem(KP_STORAGE_KEY);
    expect(stored).not.toBeNull();
    expect(JSON.parse(stored as string).supplier).toBe("Updated");
  });

  it("persists zoom changes to localStorage", () => {
    const { result } = renderHook(() => useKpState());
    act(() => {
      result.current.setZoom(1.0);
    });
    expect(window.localStorage.getItem(KP_ZOOM_STORAGE_KEY)).toBe("1");
  });

  it("clear() replaces state with EMPTY_PROPOSAL", () => {
    const { result } = renderHook(() => useKpState());
    act(() => {
      result.current.clear();
    });
    expect(result.current.data).toEqual(EMPTY_PROPOSAL);
  });

  it("loadExample() replaces state with DEFAULT_PROPOSAL", () => {
    const { result } = renderHook(() => useKpState());
    act(() => {
      result.current.clear();
    });
    expect(result.current.data).toEqual(EMPTY_PROPOSAL);
    act(() => {
      result.current.loadExample();
    });
    expect(result.current.data).toEqual(DEFAULT_PROPOSAL);
  });

  it("warns once when localStorage payload is malformed JSON", () => {
    // REQ-2.6's silent-fallback contract covers storage unavailability,
    // not corruption — a SyntaxError is a real bug signal and must be
    // visible in the console.
    window.localStorage.setItem(KP_STORAGE_KEY, "{ not json");
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    const { result } = renderHook(() => useKpState());

    expect(result.current.data).toEqual(DEFAULT_PROPOSAL);
    expect(warnSpy).toHaveBeenCalled();
    const firstArg = warnSpy.mock.calls[0]?.[0];
    expect(typeof firstArg).toBe("string");
    expect(firstArg).toContain("KP localStorage");

    warnSpy.mockRestore();
  });

  it("swallows QuotaExceededError silently on write", () => {
    // Replace setItem with a throwing stub — the hook must not bubble it.
    const failingStorage = installLocalStorageStub();
    const setItemSpy = vi
      .spyOn(failingStorage, "setItem")
      .mockImplementation(() => {
        throw new DOMException("QuotaExceededError", "QuotaExceededError");
      });

    const { result } = renderHook(() => useKpState());

    expect(() => {
      act(() => {
        result.current.setData((prev) => ({ ...prev, supplier: "fails" }));
      });
    }).not.toThrow();

    // State still updates in memory even though persistence failed.
    expect(result.current.data.supplier).toBe("fails");

    setItemSpy.mockRestore();
  });
});
