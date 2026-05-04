import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect } from "vitest";

import {
  PositionsMultiSelect,
  filterItems,
  toggleId,
  allFilteredSelected,
  nextSelectionAfterToggleAll,
} from "../ui/positions-multi-select";
import type { QuoteItemForSelect } from "../model/types";

/**
 * Tests for `PositionsMultiSelect` (Phase B Wave 3 Task 7b).
 *
 * The frontend workspace has no jsdom configured, so we follow the same
 * pattern as `country-combobox.test.tsx`:
 *
 *   1. Pure helpers (`filterItems`, `toggleId`, `allFilteredSelected`,
 *      `nextSelectionAfterToggleAll`) carry the search-filter and selection
 *      logic and are testable without a DOM.
 *   2. React's server renderer (`react-dom/server`) covers static markup
 *      assertions — selected counter, search input, "Выбрать все" toggle,
 *      formatted RUB-basis per row.
 *
 * Click handlers, checkbox state changes, and filtered-list re-renders are
 * verified via localhost:3000 per `reference_localhost_browser_test.md`.
 */

const NBSP = String.fromCharCode(160); // U+00A0 — Intl ru-RU thousand sep

function makeItem(overrides: Partial<QuoteItemForSelect> = {}): QuoteItemForSelect {
  return {
    id: "item-1",
    position: 1,
    name: "Test product",
    product_code: "SKU-1",
    rub_basis: 10000,
    ...overrides,
  };
}

const ITEMS: QuoteItemForSelect[] = [
  makeItem({ id: "i-1", position: 1, name: "Альфа", product_code: "A-100" }),
  makeItem({ id: "i-2", position: 2, name: "Бета", product_code: "B-200" }),
  makeItem({ id: "i-3", position: 3, name: "Гамма", product_code: "G-300" }),
];

// ============================================================================
// filterItems — pure search-filter logic
// ============================================================================

describe("filterItems (pure)", () => {
  it("returns the full list for an empty query", () => {
    expect(filterItems(ITEMS, "")).toEqual(ITEMS);
  });

  it("returns the full list for a whitespace-only query", () => {
    expect(filterItems(ITEMS, "   ")).toEqual(ITEMS);
  });

  it("matches case-insensitively against name", () => {
    const result = filterItems(ITEMS, "альф");
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("i-1");
  });

  it("matches case-insensitively against name with mixed case", () => {
    const result = filterItems(ITEMS, "БЕТ");
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("i-2");
  });

  it("matches case-insensitively against product_code", () => {
    const result = filterItems(ITEMS, "g-3");
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("i-3");
  });

  it("returns an empty list when nothing matches", () => {
    expect(filterItems(ITEMS, "zzzzzzz")).toEqual([]);
  });

  it("trims surrounding whitespace before matching", () => {
    const result = filterItems(ITEMS, "  альф  ");
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("i-1");
  });

  it("handles items with null product_code", () => {
    const items: QuoteItemForSelect[] = [
      makeItem({ id: "x", name: "Дельта", product_code: null }),
    ];
    expect(filterItems(items, "дельт")).toHaveLength(1);
    expect(filterItems(items, "sku")).toEqual([]);
  });
});

// ============================================================================
// toggleId — pure selection toggle
// ============================================================================

describe("toggleId (pure)", () => {
  it("adds the id when missing", () => {
    expect(toggleId(["a"], "b")).toEqual(["a", "b"]);
  });

  it("removes the id when present", () => {
    expect(toggleId(["a", "b", "c"], "b")).toEqual(["a", "c"]);
  });

  it("returns a new array (does not mutate input)", () => {
    const original = ["a", "b"];
    const next = toggleId(original, "c");
    expect(original).toEqual(["a", "b"]);
    expect(next).not.toBe(original);
  });

  it("preserves order when removing", () => {
    expect(toggleId(["x", "y", "z"], "y")).toEqual(["x", "z"]);
  });

  it("appends to the end when adding", () => {
    expect(toggleId(["x", "y"], "z")).toEqual(["x", "y", "z"]);
  });

  it("toggles the same id twice → original membership", () => {
    const after = toggleId(toggleId(["a"], "b"), "b");
    expect(after).toEqual(["a"]);
  });
});

// ============================================================================
// allFilteredSelected — pure predicate
// ============================================================================

describe("allFilteredSelected (pure)", () => {
  it("returns false for an empty filtered list", () => {
    expect(allFilteredSelected([], ["a"])).toBe(false);
  });

  it("returns true when every visible item is selected", () => {
    expect(allFilteredSelected(ITEMS, ["i-1", "i-2", "i-3"])).toBe(true);
  });

  it("returns false when at least one visible item is not selected", () => {
    expect(allFilteredSelected(ITEMS, ["i-1", "i-2"])).toBe(false);
  });

  it("returns true even with extra unrelated ids in the selection", () => {
    expect(
      allFilteredSelected(ITEMS, ["i-1", "i-2", "i-3", "extra-id"]),
    ).toBe(true);
  });
});

// ============================================================================
// nextSelectionAfterToggleAll — pure batch-toggle
// ============================================================================

describe("nextSelectionAfterToggleAll (pure)", () => {
  it("selects all filtered ids when none are currently selected", () => {
    const next = nextSelectionAfterToggleAll(ITEMS, []);
    expect(next.sort()).toEqual(["i-1", "i-2", "i-3"]);
  });

  it("merges filtered ids with existing selection", () => {
    const next = nextSelectionAfterToggleAll(ITEMS.slice(0, 2), ["i-3"]);
    expect(next.sort()).toEqual(["i-1", "i-2", "i-3"]);
  });

  it("does not duplicate ids already in the selection", () => {
    const next = nextSelectionAfterToggleAll(ITEMS, ["i-1"]);
    expect(next.sort()).toEqual(["i-1", "i-2", "i-3"]);
  });

  it("removes only filtered ids when all visible are selected (deselect-all in scope)", () => {
    const filtered = ITEMS.slice(0, 2); // i-1, i-2
    const selected = ["i-1", "i-2", "out-of-scope"];
    const next = nextSelectionAfterToggleAll(filtered, selected);
    expect(next).toEqual(["out-of-scope"]);
  });

  it("returns a new array (does not mutate input)", () => {
    const selected = ["i-1"];
    const next = nextSelectionAfterToggleAll(ITEMS, selected);
    expect(selected).toEqual(["i-1"]);
    expect(next).not.toBe(selected);
  });
});

// ============================================================================
// Component rendering (SSR)
// ============================================================================

describe("PositionsMultiSelect — rendering (SSR)", () => {
  it("renders the search input by default", () => {
    const html = renderToString(
      <PositionsMultiSelect
        items={ITEMS}
        selectedIds={[]}
        onChange={() => {}}
      />,
    );
    expect(html).toContain("Поиск по названию/SKU");
  });

  it("hides the search input when searchable={false}", () => {
    const html = renderToString(
      <PositionsMultiSelect
        items={ITEMS}
        selectedIds={[]}
        onChange={() => {}}
        searchable={false}
      />,
    );
    expect(html).not.toContain("Поиск по названию/SKU");
  });

  it("renders the selected counter «Выбрано: 0 из 3»", () => {
    const html = renderToString(
      <PositionsMultiSelect
        items={ITEMS}
        selectedIds={[]}
        onChange={() => {}}
      />,
    );
    expect(html).toContain("Выбрано: 0 из 3");
  });

  it("renders the selected counter with current selection length", () => {
    const html = renderToString(
      <PositionsMultiSelect
        items={ITEMS}
        selectedIds={["i-1", "i-2"]}
        onChange={() => {}}
      />,
    );
    expect(html).toContain("Выбрано: 2 из 3");
  });

  it("renders «Выбрать все» when nothing is selected", () => {
    const html = renderToString(
      <PositionsMultiSelect
        items={ITEMS}
        selectedIds={[]}
        onChange={() => {}}
      />,
    );
    expect(html).toContain("Выбрать все");
    expect(html).not.toContain("Снять все");
  });

  it("renders «Снять все» when every visible item is selected", () => {
    const html = renderToString(
      <PositionsMultiSelect
        items={ITEMS}
        selectedIds={["i-1", "i-2", "i-3"]}
        onChange={() => {}}
      />,
    );
    expect(html).toContain("Снять все");
  });

  it("renders one row per item", () => {
    const html = renderToString(
      <PositionsMultiSelect
        items={ITEMS}
        selectedIds={[]}
        onChange={() => {}}
      />,
    );
    expect(html).toContain("Альфа");
    expect(html).toContain("Бета");
    expect(html).toContain("Гамма");
  });

  it("renders position numbers «№N»", () => {
    const html = renderToString(
      <PositionsMultiSelect
        items={ITEMS}
        selectedIds={[]}
        onChange={() => {}}
      />,
    );
    expect(html).toContain("№1");
    expect(html).toContain("№2");
    expect(html).toContain("№3");
  });

  it("renders the formatted RUB basis per row", () => {
    const items: QuoteItemForSelect[] = [
      makeItem({ id: "i-1", rub_basis: 12500 }),
    ];
    const html = renderToString(
      <PositionsMultiSelect
        items={items}
        selectedIds={[]}
        onChange={() => {}}
      />,
    );
    expect(html).toContain(`12${NBSP}500${NBSP}₽`);
  });

  it("renders product_code when present", () => {
    const html = renderToString(
      <PositionsMultiSelect
        items={ITEMS}
        selectedIds={[]}
        onChange={() => {}}
      />,
    );
    expect(html).toContain("A-100");
    expect(html).toContain("B-200");
  });

  it("renders the empty state when items is empty", () => {
    const html = renderToString(
      <PositionsMultiSelect items={[]} selectedIds={[]} onChange={() => {}} />,
    );
    expect(html).toContain("Ничего не найдено");
  });

  it("data-slot identifies the root container", () => {
    const html = renderToString(
      <PositionsMultiSelect
        items={ITEMS}
        selectedIds={[]}
        onChange={() => {}}
      />,
    );
    expect(html).toContain('data-slot="positions-multi-select"');
  });

  it("data-item-id is set on each row for E2E hooking", () => {
    const html = renderToString(
      <PositionsMultiSelect
        items={ITEMS}
        selectedIds={[]}
        onChange={() => {}}
      />,
    );
    expect(html).toContain('data-item-id="i-1"');
    expect(html).toContain('data-item-id="i-2"');
    expect(html).toContain('data-item-id="i-3"');
  });
});

// ============================================================================
// onChange contract — invocation smoke (non-DOM)
// ============================================================================

describe("PositionsMultiSelect — onChange contract (non-DOM)", () => {
  it("renders without throwing when onChange is provided", () => {
    const onChange = (_ids: string[]) => {};
    expect(() =>
      renderToString(
        <PositionsMultiSelect
          items={ITEMS}
          selectedIds={[]}
          onChange={onChange}
        />,
      ),
    ).not.toThrow();
  });
});
