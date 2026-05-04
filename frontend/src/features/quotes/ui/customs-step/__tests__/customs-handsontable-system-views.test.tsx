import { describe, expect, it } from "vitest";

import { CUSTOMS_AVAILABLE_COLUMNS } from "../customs-columns";
import {
  CUSTOMS_SYSTEM_VIEWS,
  resolveSystemView,
} from "../customs-views";
import {
  effectiveVisibleColumns,
  resolveActiveSystemView,
  shouldRenderHintBanner,
} from "../customs-handsontable";

/**
 * Phase B Wave 4 Task 11 — pure-function tests for the synthetic
 * `system:*` view resolver wired into `customs-handsontable.tsx`.
 *
 * The frontend workspace has no jsdom (see `customs-antidumping.test.ts`
 * precedent + `vitest.config.ts`), so these tests stay strictly logical:
 * the helpers are extracted from the component on purpose so URL → view
 * → column-filter routing is testable without rendering Handsontable.
 *
 * Coverage (REQ-11 AC#5, AC#7, AC#8, AC#9):
 *   - `system:*` known IDs resolve to a virtual view (columns filtered).
 *   - `system:all` keeps all 24 columns visible (default fallback).
 *   - Unknown `system:*` IDs degrade gracefully → existing prop wins.
 *   - UUID strings (real `user_table_views` rows) leave the prop path
 *     untouched — no system override.
 *   - Hint-banner predicate fires only for non-default system views.
 *   - `null`/`undefined` URL param → no system override.
 */

const KNOWN_VIEW_IDS = [
  "system:all",
  "system:tariffs-nds",
  "system:documents",
  "system:identification",
] as const;

describe("resolveActiveSystemView — URL param → SystemView | null", () => {
  it("returns the matching virtual view for every known synthetic id", () => {
    for (const id of KNOWN_VIEW_IDS) {
      const view = resolveActiveSystemView(id);
      expect(view, `expected resolver to return a view for ${id}`).not.toBeNull();
      expect(view?.id).toBe(id);
      expect(view?.is_system).toBe(true);
    }
  });

  it("returns the same referential row that lives in CUSTOMS_SYSTEM_VIEWS", () => {
    // Sanity check — the resolver must not clone, otherwise downstream
    // `===` comparisons (e.g. inside `shouldRenderHintBanner`) silently
    // break for callers that hold an earlier reference.
    const original = CUSTOMS_SYSTEM_VIEWS.find(
      (v) => v.id === "system:tariffs-nds",
    );
    expect(resolveActiveSystemView("system:tariffs-nds")).toBe(original);
  });

  it("returns null for unknown `system:*` sub-ids (graceful degrade)", () => {
    expect(resolveActiveSystemView("system:bogus")).toBeNull();
    expect(resolveActiveSystemView("system:future")).toBeNull();
  });

  it("returns null for UUID strings (real user_table_views rows)", () => {
    expect(
      resolveActiveSystemView("11111111-2222-3333-4444-555555555555"),
    ).toBeNull();
    expect(resolveActiveSystemView("abc-def-ghi")).toBeNull();
  });

  it("returns null for null / undefined / empty string", () => {
    expect(resolveActiveSystemView(null)).toBeNull();
    expect(resolveActiveSystemView(undefined)).toBeNull();
    expect(resolveActiveSystemView("")).toBeNull();
  });
});

describe("effectiveVisibleColumns — system override vs prop fallback", () => {
  it("returns the system view's visibleColumnIds when one is active", () => {
    const view = resolveSystemView("system:tariffs-nds")!;
    const result = effectiveVisibleColumns(view, undefined);
    expect(result).toBe(view.visibleColumnIds);
  });

  it("does not let the prop override an active system view", () => {
    // Even if the parent threads in a UUID-derived prop, the URL `system:*`
    // takes precedence — REQ-11 AC#5 (URL persistence is the source of
    // truth for system views).
    const view = resolveSystemView("system:identification")!;
    const propColumns = ["position", "brand"];
    const result = effectiveVisibleColumns(view, propColumns);
    expect(result).toBe(view.visibleColumnIds);
    expect(result).not.toBe(propColumns);
  });

  it("returns the prop unchanged when no system view is active (UUID path)", () => {
    const propColumns = ["position", "brand", "hs_code"];
    expect(effectiveVisibleColumns(null, propColumns)).toBe(propColumns);
  });

  it("returns undefined (no filter) when neither system view nor prop is set", () => {
    expect(effectiveVisibleColumns(null, undefined)).toBeUndefined();
  });

  it("system:all enumerates all 24 columns — equivalent to no filter", () => {
    const view = resolveSystemView("system:all")!;
    const result = effectiveVisibleColumns(view, undefined);
    expect(result).toBeDefined();
    expect(result!.length).toBe(CUSTOMS_AVAILABLE_COLUMNS.length);
    // Sorted comparison — view declares the canonical column order, but
    // the registry order is what surfaces hidden labels.
    expect([...result!].sort()).toEqual(
      CUSTOMS_AVAILABLE_COLUMNS.map((c) => c.key).sort(),
    );
  });
});

describe("shouldRenderHintBanner — REQ-11 AC#9 mount predicate", () => {
  it("returns false when no system view is active", () => {
    expect(shouldRenderHintBanner(null)).toBe(false);
  });

  it("returns false for the default `system:all` view", () => {
    const view = resolveSystemView("system:all")!;
    expect(shouldRenderHintBanner(view)).toBe(false);
  });

  it("returns true for every non-default system view", () => {
    const nonDefaultIds = KNOWN_VIEW_IDS.filter((id) => id !== "system:all");
    for (const id of nonDefaultIds) {
      const view = resolveSystemView(id)!;
      expect(
        shouldRenderHintBanner(view),
        `expected banner to render for ${id}`,
      ).toBe(true);
    }
  });
});

describe("URL param routing — end-to-end resolver pipeline", () => {
  it("URL param missing → no override, prop fallback takes over", () => {
    const view = resolveActiveSystemView(null);
    const visibleColumns = effectiveVisibleColumns(view, undefined);
    expect(view).toBeNull();
    expect(visibleColumns).toBeUndefined();
    expect(shouldRenderHintBanner(view)).toBe(false);
  });

  it("URL param = `system:tariffs-nds` → columns filtered + banner mounted", () => {
    const view = resolveActiveSystemView("system:tariffs-nds");
    const visibleColumns = effectiveVisibleColumns(view, undefined);
    expect(view?.id).toBe("system:tariffs-nds");
    expect(visibleColumns).toEqual(view?.visibleColumnIds);
    expect(shouldRenderHintBanner(view)).toBe(true);
  });

  it("URL param = `system:all` → all 24 columns + no banner", () => {
    const view = resolveActiveSystemView("system:all");
    const visibleColumns = effectiveVisibleColumns(view, undefined);
    expect(view?.id).toBe("system:all");
    expect(visibleColumns?.length).toBe(CUSTOMS_AVAILABLE_COLUMNS.length);
    expect(shouldRenderHintBanner(view)).toBe(false);
  });

  it("URL param = unknown `system:*` ID → no override + no banner", () => {
    const view = resolveActiveSystemView("system:bogus");
    const propColumns = ["position", "hs_code"];
    const visibleColumns = effectiveVisibleColumns(view, propColumns);
    expect(view).toBeNull();
    expect(visibleColumns).toBe(propColumns);
    expect(shouldRenderHintBanner(view)).toBe(false);
  });

  it("URL param = UUID → user view path untouched (prop wins, no banner)", () => {
    const view = resolveActiveSystemView(
      "11111111-2222-3333-4444-555555555555",
    );
    const propColumns = ["position", "brand", "product_code"];
    const visibleColumns = effectiveVisibleColumns(view, propColumns);
    expect(view).toBeNull();
    expect(visibleColumns).toBe(propColumns);
    expect(shouldRenderHintBanner(view)).toBe(false);
  });
});
