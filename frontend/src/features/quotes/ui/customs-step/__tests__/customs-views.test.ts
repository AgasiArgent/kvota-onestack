import { describe, expect, it } from "vitest";

import { CUSTOMS_AVAILABLE_COLUMNS } from "../customs-columns";
import {
  CUSTOMS_SYSTEM_VIEWS,
  defaultSystemViewId,
  getHiddenColumnLabels,
  isSystemViewId,
  resolveSystemView,
} from "../customs-views";

/**
 * Pure-function tests for the customs-step `customs-views.ts` constants
 * (Phase B Wave 4 Task 8 / REQ-11).
 *
 * The frontend workspace has no jsdom (see `__tests__/customs-antidumping.test.ts`
 * precedent), so these tests stay strictly logical — no React rendering.
 *
 * Two structural guards:
 *   - Every `view.visibleColumnIds` entry must resolve against
 *     `CUSTOMS_AVAILABLE_COLUMNS` so a typo in a column key fails CI fast.
 *   - `system:all` is asserted to enumerate every available column so a
 *     newly-added column without a corresponding update to the «Все колонки»
 *     view also fails CI (REQ-11 AC#2 — first bullet pin).
 */

describe("isSystemViewId — type guard", () => {
  it("returns true for the four documented synthetic ids", () => {
    expect(isSystemViewId("system:all")).toBe(true);
    expect(isSystemViewId("system:tariffs-nds")).toBe(true);
    expect(isSystemViewId("system:documents")).toBe(true);
    expect(isSystemViewId("system:identification")).toBe(true);
  });

  it("returns true for any string with the `system:` prefix", () => {
    // The guard is structural — anything starting with `system:` is treated
    // as synthetic, even an unknown sub-id. `resolveSystemView` is the
    // mapping check for «known view»; callers compose them.
    expect(isSystemViewId("system:future")).toBe(true);
  });

  it("returns false for null / undefined / empty string", () => {
    expect(isSystemViewId(null)).toBe(false);
    expect(isSystemViewId(undefined)).toBe(false);
    expect(isSystemViewId("")).toBe(false);
  });

  it("returns false for UUID strings (real user_table_views ids)", () => {
    expect(
      isSystemViewId("11111111-2222-3333-4444-555555555555"),
    ).toBe(false);
    expect(isSystemViewId("abc-def-ghi")).toBe(false);
  });

  it("returns false for the literal string 'system' without colon", () => {
    expect(isSystemViewId("system")).toBe(false);
  });
});

describe("resolveSystemView — lookup", () => {
  it("returns the matching view for each known synthetic id", () => {
    expect(resolveSystemView("system:all")?.id).toBe("system:all");
    expect(resolveSystemView("system:tariffs-nds")?.id).toBe(
      "system:tariffs-nds",
    );
    expect(resolveSystemView("system:documents")?.id).toBe("system:documents");
    expect(resolveSystemView("system:identification")?.id).toBe(
      "system:identification",
    );
  });

  it("returns null for unknown synthetic sub-ids", () => {
    // `system:` prefix passes the guard but the registry has no entry.
    expect(resolveSystemView("system:bogus")).toBeNull();
  });

  it("returns null for UUID strings", () => {
    expect(
      resolveSystemView("11111111-2222-3333-4444-555555555555"),
    ).toBeNull();
  });

  it("returns null for null / undefined / empty string", () => {
    expect(resolveSystemView(null)).toBeNull();
    expect(resolveSystemView(undefined)).toBeNull();
    expect(resolveSystemView("")).toBeNull();
  });

  it("returns the same row that lives in CUSTOMS_SYSTEM_VIEWS (referential identity)", () => {
    const found = resolveSystemView("system:tariffs-nds");
    const original = CUSTOMS_SYSTEM_VIEWS.find(
      (v) => v.id === "system:tariffs-nds",
    );
    expect(found).toBe(original);
  });
});

describe("defaultSystemViewId", () => {
  it("returns 'system:all'", () => {
    expect(defaultSystemViewId()).toBe("system:all");
  });
});

describe("CUSTOMS_SYSTEM_VIEWS — structural integrity", () => {
  it("contains exactly four views in the documented order", () => {
    expect(CUSTOMS_SYSTEM_VIEWS).toHaveLength(4);
    expect(CUSTOMS_SYSTEM_VIEWS.map((v) => v.id)).toEqual([
      "system:all",
      "system:tariffs-nds",
      "system:documents",
      "system:identification",
    ]);
  });

  it("flags every view as a system view", () => {
    for (const view of CUSTOMS_SYSTEM_VIEWS) {
      expect(view.is_system).toBe(true);
    }
  });

  it("uses Russian labels", () => {
    const labels = CUSTOMS_SYSTEM_VIEWS.map((v) => v.label);
    expect(labels).toEqual([
      "Все колонки",
      "Тарифы и НДС",
      "Документы и сертификаты",
      "Только идентификация",
    ]);
  });

  it("declares every visibleColumnIds entry as a known column key", () => {
    // Catches typos in `visibleColumnIds[]` entries — REQ-11 AC#2 column ids
    // must round-trip against the canonical `CUSTOMS_AVAILABLE_COLUMNS`.
    const knownKeys = new Set(CUSTOMS_AVAILABLE_COLUMNS.map((c) => c.key));
    for (const view of CUSTOMS_SYSTEM_VIEWS) {
      for (const colId of view.visibleColumnIds) {
        expect(
          knownKeys.has(colId),
          `${view.id} references unknown column key '${colId}'`,
        ).toBe(true);
      }
    }
  });

  it("system:all enumerates every available column", () => {
    // If a new column lands in `customs-columns.ts` and the «Все колонки»
    // view is not updated, this assertion fires and forces a sync.
    const allView = CUSTOMS_SYSTEM_VIEWS.find((v) => v.id === "system:all");
    expect(allView).toBeDefined();
    expect(allView!.visibleColumnIds).toHaveLength(
      CUSTOMS_AVAILABLE_COLUMNS.length,
    );
    expect([...allView!.visibleColumnIds].sort()).toEqual(
      CUSTOMS_AVAILABLE_COLUMNS.map((c) => c.key).sort(),
    );
  });

  it("system:identification is the minimal six-column view", () => {
    const view = CUSTOMS_SYSTEM_VIEWS.find(
      (v) => v.id === "system:identification",
    );
    expect(view).toBeDefined();
    expect(view!.visibleColumnIds).toEqual([
      "position",
      "brand",
      "product_code",
      "product_name",
      "quantity",
      "hs_code",
    ]);
  });
});

describe("getHiddenColumnLabels", () => {
  it("returns an empty array for the system:all view (nothing hidden)", () => {
    const view = resolveSystemView("system:all")!;
    expect(getHiddenColumnLabels(view)).toEqual([]);
  });

  it("returns labels for every column not in system:identification (24 - 6 = 18)", () => {
    const view = resolveSystemView("system:identification")!;
    const visibleSet = new Set(view.visibleColumnIds);
    const expected = CUSTOMS_AVAILABLE_COLUMNS.filter(
      (c) => !visibleSet.has(c.key),
    ).map((c) => c.label);

    const actual = getHiddenColumnLabels(view);
    expect(actual).toEqual(expected);
    expect(actual).toHaveLength(
      CUSTOMS_AVAILABLE_COLUMNS.length - view.visibleColumnIds.length,
    );
  });

  it("preserves the column-registry order", () => {
    const view = resolveSystemView("system:tariffs-nds")!;
    const labels = getHiddenColumnLabels(view);

    // Reconstruct the expected output by walking CUSTOMS_AVAILABLE_COLUMNS
    // in declared order — the helper must not re-sort.
    const visibleSet = new Set(view.visibleColumnIds);
    const expected = CUSTOMS_AVAILABLE_COLUMNS.filter(
      (c) => !visibleSet.has(c.key),
    ).map((c) => c.label);
    expect(labels).toEqual(expected);
  });

  it("accepts an injected column registry for synthetic test inputs", () => {
    const fakeRegistry = [
      { key: "position", label: "№" },
      { key: "brand", label: "Бренд" },
      { key: "extra_col", label: "Доп. колонка" },
    ];
    const view = resolveSystemView("system:identification")!;
    // Only `position` and `brand` are in `view.visibleColumnIds` from the
    // fake registry — `extra_col` is the only hidden one.
    expect(getHiddenColumnLabels(view, fakeRegistry)).toEqual([
      "Доп. колонка",
    ]);
  });

  it("returns labels (not keys) for the documents view", () => {
    const view = resolveSystemView("system:documents")!;
    const labels = getHiddenColumnLabels(view);
    // Labels are Russian — assert at least one human-readable string is present.
    expect(labels).toContain("Бренд");
    // And no raw column keys leak through.
    expect(labels).not.toContain("brand");
  });
});
