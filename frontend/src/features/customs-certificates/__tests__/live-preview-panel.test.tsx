import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect } from "vitest";

import {
  LivePreviewPanel,
  computePreviewRows,
  formatPercent,
} from "../ui/live-preview-panel";
import type { QuoteItemForSelect } from "../model/types";

/**
 * Tests for `LivePreviewPanel` (Phase B Wave 3 Task 7b).
 *
 * No jsdom in this workspace — we test pure helpers (`computePreviewRows`,
 * `formatPercent`) directly and use `react-dom/server` for SSR markup
 * assertions. The component is a pure render based on its props, so SSR
 * coverage is sufficient.
 *
 * Math parity vs `services/cost_split.py` is enforced upstream by
 * `tests/fixtures/cost_split_fixtures.json` (see Wave 1 Task 3) — these
 * tests verify only the panel's own composition + edge cases.
 */

const NBSP = String.fromCharCode(160); // U+00A0 — Intl ru-RU thousand sep

function makeItem(overrides: Partial<QuoteItemForSelect> = {}): QuoteItemForSelect {
  return {
    id: "item-1",
    position: 1,
    name: "Test product",
    product_code: "SKU-1",
    rub_basis: 0,
    ...overrides,
  };
}

// ============================================================================
// formatPercent — pure number → string
// ============================================================================

describe("formatPercent (pure)", () => {
  it("returns '0%' for zero", () => {
    expect(formatPercent(0)).toBe("0%");
  });

  it("returns '0%' for NaN", () => {
    expect(formatPercent(Number.NaN)).toBe("0%");
  });

  it("returns '0%' for Infinity", () => {
    expect(formatPercent(Number.POSITIVE_INFINITY)).toBe("0%");
  });

  it("renders integer percents without decimals", () => {
    expect(formatPercent(50)).toBe("50%");
    expect(formatPercent(100)).toBe("100%");
  });

  it("renders fractional percents with one decimal", () => {
    expect(formatPercent(33.333333)).toBe("33.3%");
    expect(formatPercent(66.6666)).toBe("66.7%");
  });

  it("rounds to one decimal place via toFixed (informational only)", () => {
    // toFixed uses IEEE-754 representation — 12.55 may round either way.
    // The percent value is informational; the kopek-exact share in
    // share_rub is the authoritative number, so this test only asserts
    // shape, not a specific tie-break direction.
    const out = formatPercent(12.555);
    expect(out).toMatch(/^\d+\.\d%$/);
  });
});

// ============================================================================
// computePreviewRows — pure compute
// ============================================================================

describe("computePreviewRows (pure)", () => {
  it("returns an empty array for empty selection (empty state UI)", () => {
    expect(computePreviewRows([], 1000)).toEqual([]);
  });

  it("returns full cost for a single item", () => {
    const items = [makeItem({ id: "a", position: 1, rub_basis: 5000 })];
    const rows = computePreviewRows(items, 1000);
    expect(rows).toHaveLength(1);
    expect(rows[0].share_rub).toBe(1000);
    expect(rows[0].share_percent).toBe(100);
  });

  it("splits proportionally across 3 items", () => {
    const items = [
      makeItem({ id: "a", position: 1, rub_basis: 150_000 }),
      makeItem({ id: "b", position: 2, rub_basis: 350_000 }),
      makeItem({ id: "c", position: 3, rub_basis: 90_000 }),
    ];
    const rows = computePreviewRows(items, 12_500);

    // The total of all shares MUST equal certCost — this is the residual rule.
    const sum = rows.reduce((acc, row) => acc + row.share_rub, 0);
    expect(sum).toBe(12_500);

    // The largest basis (350k) → largest share.
    expect(rows[1].share_rub).toBeGreaterThan(rows[0].share_rub);
    expect(rows[1].share_rub).toBeGreaterThan(rows[2].share_rub);
  });

  it("falls back to equal-split when all bases are zero", () => {
    const items = [
      makeItem({ id: "a", position: 1, rub_basis: 0 }),
      makeItem({ id: "b", position: 2, rub_basis: 0 }),
      makeItem({ id: "c", position: 3, rub_basis: 0 }),
    ];
    const rows = computePreviewRows(items, 10);
    const sum = rows.reduce((acc, row) => acc + row.share_rub, 0);
    expect(sum).toBe(10);
    // Last item absorbs residual on equal-split fallback.
    expect(rows[0].share_rub).toBe(3.33);
    expect(rows[1].share_rub).toBe(3.33);
    expect(rows[2].share_rub).toBe(3.34);
  });

  it("returns zero shares + zero percent when certCost is 0", () => {
    const items = [
      makeItem({ id: "a", position: 1, rub_basis: 100 }),
      makeItem({ id: "b", position: 2, rub_basis: 200 }),
    ];
    const rows = computePreviewRows(items, 0);
    expect(rows).toHaveLength(2);
    expect(rows[0].share_rub).toBe(0);
    expect(rows[0].share_percent).toBe(0);
    expect(rows[1].share_percent).toBe(0);
  });

  it("preserves input order in returned rows", () => {
    const items = [
      makeItem({ id: "a", position: 5, name: "A" }),
      makeItem({ id: "b", position: 2, name: "B" }),
    ];
    const rows = computePreviewRows(items, 100);
    expect(rows[0].id).toBe("a");
    expect(rows[1].id).toBe("b");
    expect(rows[0].position).toBe(5);
    expect(rows[1].position).toBe(2);
  });

  it("does not mutate the input array", () => {
    const items = [makeItem({ id: "a", position: 1, rub_basis: 100 })];
    const snapshot = JSON.stringify(items);
    computePreviewRows(items, 500);
    expect(JSON.stringify(items)).toBe(snapshot);
  });
});

// ============================================================================
// Component rendering (SSR)
// ============================================================================

describe("LivePreviewPanel — rendering (SSR)", () => {
  it("renders the header «Распределение стоимости»", () => {
    const html = renderToString(
      <LivePreviewPanel selectedItems={[]} certCost={0} />,
    );
    expect(html).toContain("Распределение стоимости");
  });

  it("renders the empty state when no items are selected", () => {
    const html = renderToString(
      <LivePreviewPanel selectedItems={[]} certCost={1000} />,
    );
    expect(html).toContain("Выберите позиции для распределения");
  });

  it("does NOT render «Всего:» footer when empty", () => {
    const html = renderToString(
      <LivePreviewPanel selectedItems={[]} certCost={1000} />,
    );
    expect(html).not.toContain("Всего:");
  });

  it("renders one row per selected item", () => {
    const items = [
      makeItem({ id: "a", position: 1, name: "Alpha", rub_basis: 100 }),
      makeItem({ id: "b", position: 2, name: "Beta", rub_basis: 200 }),
    ];
    const html = renderToString(
      <LivePreviewPanel selectedItems={items} certCost={1000} />,
    );
    expect(html).toContain("Alpha");
    expect(html).toContain("Beta");
    expect(html).toContain("№1");
    expect(html).toContain("№2");
  });

  it("renders the «Всего: {certCost} ₽» footer", () => {
    const items = [makeItem({ id: "a", position: 1, rub_basis: 100 })];
    const html = renderToString(
      <LivePreviewPanel selectedItems={items} certCost={12_500} />,
    );
    expect(html).toContain("Всего:");
    expect(html).toContain(`12${NBSP}500${NBSP}₽`);
  });

  it("renders share_rub and share_percent for each row", () => {
    const items = [makeItem({ id: "a", position: 1, rub_basis: 100 })];
    const html = renderToString(
      <LivePreviewPanel selectedItems={items} certCost={1000} />,
    );
    // Single item — gets full cert cost.
    expect(html).toContain(`1${NBSP}000${NBSP}₽`);
    expect(html).toContain("100%");
  });

  it("renders proportional shares for multi-item selection", () => {
    const items = [
      makeItem({ id: "a", position: 1, name: "X", rub_basis: 100 }),
      makeItem({ id: "b", position: 2, name: "Y", rub_basis: 100 }),
    ];
    const html = renderToString(
      <LivePreviewPanel selectedItems={items} certCost={1000} />,
    );
    // Equal basis — both items 50%. Total still 1000.
    expect(html).toContain("50%");
    expect(html).toContain(`1${NBSP}000${NBSP}₽`);
  });

  it("handles certCost === 0 gracefully", () => {
    const items = [makeItem({ id: "a", position: 1, rub_basis: 100 })];
    const html = renderToString(
      <LivePreviewPanel selectedItems={items} certCost={0} />,
    );
    expect(html).toContain("Всего:");
    expect(html).toContain(`0${NBSP}₽`);
    // Percent for zero-cost share resolves to "0%".
    expect(html).toContain("0%");
  });

  it("data-slot identifies the root container", () => {
    const html = renderToString(
      <LivePreviewPanel selectedItems={[]} certCost={0} />,
    );
    expect(html).toContain('data-slot="live-preview-panel"');
  });

  it("data-item-id is set on each preview row", () => {
    const items = [
      makeItem({ id: "row-a", position: 1, name: "X", rub_basis: 100 }),
      makeItem({ id: "row-b", position: 2, name: "Y", rub_basis: 200 }),
    ];
    const html = renderToString(
      <LivePreviewPanel selectedItems={items} certCost={500} />,
    );
    expect(html).toContain('data-item-id="row-a"');
    expect(html).toContain('data-item-id="row-b"');
  });
});

// ============================================================================
// Pure-render contract (no side effects)
// ============================================================================

describe("LivePreviewPanel — pure-render contract", () => {
  it("re-rendering with the same props produces identical markup", () => {
    const items = [makeItem({ id: "a", position: 1, rub_basis: 100 })];
    const a = renderToString(
      <LivePreviewPanel selectedItems={items} certCost={1000} />,
    );
    const b = renderToString(
      <LivePreviewPanel selectedItems={items} certCost={1000} />,
    );
    expect(a).toBe(b);
  });

  it("does not mutate the selectedItems array on render", () => {
    const items = [makeItem({ id: "a", position: 1, rub_basis: 100 })];
    const snapshot = JSON.stringify(items);
    renderToString(<LivePreviewPanel selectedItems={items} certCost={500} />);
    expect(JSON.stringify(items)).toBe(snapshot);
  });
});
