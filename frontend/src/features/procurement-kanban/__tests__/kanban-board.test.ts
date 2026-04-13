import { describe, it, expect } from "vitest";
import {
  PROCUREMENT_SUBSTATUSES,
  SUBSTATUS_LABELS_RU,
} from "@/shared/lib/workflow-substates";
import {
  brandCardKey,
  parseBrandCardKey,
  type KanbanBrandCard,
  type KanbanColumns,
} from "../model/types";

/**
 * Board-layout invariants. We verify that the 4 column keys and their Russian
 * labels are present and stable — the KanbanBoard renders one column per key.
 * Full drag interaction is verified on localhost per
 * reference_localhost_browser_test.md (dnd-kit requires a real DOM).
 */
describe("KanbanBoard — column configuration", () => {
  it("produces exactly 4 columns in fixed order", () => {
    expect(PROCUREMENT_SUBSTATUSES).toHaveLength(4);
    expect(PROCUREMENT_SUBSTATUSES[0]).toBe("distributing");
    expect(PROCUREMENT_SUBSTATUSES[3]).toBe("prices_ready");
  });

  it("uses the Russian labels required by the UI spec", () => {
    expect(SUBSTATUS_LABELS_RU.distributing).toBe("Распределение");
    expect(SUBSTATUS_LABELS_RU.searching_supplier).toBe("Поиск поставщика");
    expect(SUBSTATUS_LABELS_RU.waiting_prices).toBe("Ожидание цен");
    expect(SUBSTATUS_LABELS_RU.prices_ready).toBe("Цены готовы");
  });

  it("KanbanColumns type accepts empty arrays per substatus", () => {
    const empty: KanbanColumns = {
      distributing: [],
      searching_supplier: [],
      waiting_prices: [],
      prices_ready: [],
    };
    for (const sub of PROCUREMENT_SUBSTATUSES) {
      expect(empty[sub]).toEqual([]);
    }
  });

  it("card counts can be derived per column from KanbanColumns shape", () => {
    const state: KanbanColumns = {
      distributing: [makeCard({ quote_id: "q1", brand: "ABB" })],
      searching_supplier: [],
      waiting_prices: [],
      prices_ready: [],
    };
    const counts = PROCUREMENT_SUBSTATUSES.map((s) => state[s].length);
    expect(counts).toEqual([1, 0, 0, 0]);
    expect(counts.reduce((a, b) => a + b, 0)).toBe(1);
  });
});

describe("KanbanBrandCard — identity", () => {
  it("brandCardKey joins quote_id and brand with a pipe", () => {
    const card = makeCard({ quote_id: "q1", brand: "ABB" });
    expect(brandCardKey(card)).toBe("q1|ABB");
  });

  it("brandCardKey uses empty string for unbranded cards", () => {
    const card = makeCard({ quote_id: "q1", brand: "" });
    expect(brandCardKey(card)).toBe("q1|");
  });

  it("parseBrandCardKey round-trips for branded cards", () => {
    expect(parseBrandCardKey("q1|ABB")).toEqual({
      quote_id: "q1",
      brand: "ABB",
    });
  });

  it("parseBrandCardKey round-trips for unbranded cards", () => {
    expect(parseBrandCardKey("q1|")).toEqual({ quote_id: "q1", brand: "" });
  });

  it("parseBrandCardKey preserves pipes inside brand names", () => {
    // Defensive: if a brand ever contained a literal '|', only the FIRST pipe
    // separates quote_id from the rest.
    expect(parseBrandCardKey("q1|A|B")).toEqual({
      quote_id: "q1",
      brand: "A|B",
    });
  });
});

describe("KanbanBoard — per-(quote, brand) slicing", () => {
  it("allows the same quote to appear under multiple brands in one column", () => {
    const q1Abb = makeCard({ quote_id: "q1", brand: "ABB" });
    const q1Siemens = makeCard({ quote_id: "q1", brand: "Siemens" });
    const state: KanbanColumns = {
      distributing: [q1Abb, q1Siemens],
      searching_supplier: [],
      waiting_prices: [],
      prices_ready: [],
    };
    expect(state.distributing).toHaveLength(2);
    expect(brandCardKey(state.distributing[0])).not.toBe(
      brandCardKey(state.distributing[1])
    );
  });

  it("allows the same quote to span columns when brands are at different substatuses", () => {
    const q1Abb = makeCard({
      quote_id: "q1",
      brand: "ABB",
      procurement_substatus: "distributing",
    });
    const q1Siemens = makeCard({
      quote_id: "q1",
      brand: "Siemens",
      procurement_substatus: "waiting_prices",
    });
    const state: KanbanColumns = {
      distributing: [q1Abb],
      searching_supplier: [],
      waiting_prices: [q1Siemens],
      prices_ready: [],
    };
    // Both cards share the same quote_id but live in different columns.
    expect(state.distributing[0].quote_id).toBe(state.waiting_prices[0].quote_id);
    expect(brandCardKey(state.distributing[0])).not.toBe(
      brandCardKey(state.waiting_prices[0])
    );
  });

  it("unbranded cards are valid and render as brand=''", () => {
    const unbranded = makeCard({ quote_id: "q2", brand: "" });
    expect(unbranded.brand).toBe("");
    expect(brandCardKey(unbranded)).toBe("q2|");
  });
});

function makeCard(overrides: Partial<KanbanBrandCard>): KanbanBrandCard {
  return {
    quote_id: "q1",
    brand: "",
    idn_quote: "Q-202604-0001",
    customer_name: "Acme",
    days_in_state: 2,
    latest_reason: null,
    procurement_substatus: "distributing",
    manager_name: null,
    procurement_user_names: [],
    invoice_sums: [],
    ...overrides,
  };
}
