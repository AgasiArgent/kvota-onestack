/**
 * Filter logic for the procurement kanban board (Testing 2 row 66). Verifies:
 *  - Empty filter set is a no-op.
 *  - Multi-value picks combine with AND across slots, OR within a slot.
 *  - МОЗ filter matches any of the multiple procurement_user_ids on a card.
 *  - "На этапе > N дней" uses strict > with days_in_state.
 */

import { describe, expect, it } from "vitest";

import type { KanbanBrandCard, KanbanColumns } from "../model/types";
import {
  cardPassesProcurementFilters,
  emptyProcurementFilters,
  filterProcurementColumns,
  hasActiveProcurementFilters,
  totalProcurementCardCount,
  type ProcurementFilterState,
} from "../lib/filter-board";

function makeCard(overrides: Partial<KanbanBrandCard>): KanbanBrandCard {
  return {
    quote_id: "q-1",
    brand: "Nike",
    idn_quote: "Q-202604-0001",
    customer_id: "cust-1",
    customer_name: "Coca-Cola",
    days_in_state: 3,
    updated_at: "2026-05-20T09:00:00Z",
    latest_reason: null,
    procurement_substatus: "searching_supplier",
    manager_id: "mgr-1",
    manager_name: "Анна",
    procurement_user_ids: ["moz-1"],
    procurement_user_names: ["Иван"],
    invoice_sums: [],
    ...overrides,
  };
}

describe("hasActiveProcurementFilters", () => {
  it("returns false on an empty filter set", () => {
    expect(hasActiveProcurementFilters(emptyProcurementFilters())).toBe(false);
  });

  it("returns true when any slot is populated", () => {
    expect(
      hasActiveProcurementFilters({
        ...emptyProcurementFilters(),
        brands: ["Nike"],
      })
    ).toBe(true);
    expect(
      hasActiveProcurementFilters({
        ...emptyProcurementFilters(),
        stageAge: "gt_7",
      })
    ).toBe(true);
  });
});

describe("cardPassesProcurementFilters", () => {
  it("no filters: every card passes", () => {
    expect(
      cardPassesProcurementFilters(makeCard({}), emptyProcurementFilters())
    ).toBe(true);
  });

  it("customer: matches by id", () => {
    const filters: ProcurementFilterState = {
      ...emptyProcurementFilters(),
      customerIds: ["cust-1"],
    };
    expect(cardPassesProcurementFilters(makeCard({}), filters)).toBe(true);
    expect(
      cardPassesProcurementFilters(makeCard({ customer_id: "cust-2" }), filters)
    ).toBe(false);
    expect(
      cardPassesProcurementFilters(makeCard({ customer_id: null }), filters)
    ).toBe(false);
  });

  it("brand: matches by label, including empty string for «Без бренда»", () => {
    const filters: ProcurementFilterState = {
      ...emptyProcurementFilters(),
      brands: ["Nike", ""],
    };
    expect(cardPassesProcurementFilters(makeCard({ brand: "Nike" }), filters)).toBe(
      true
    );
    expect(cardPassesProcurementFilters(makeCard({ brand: "" }), filters)).toBe(
      true
    );
    expect(cardPassesProcurementFilters(makeCard({ brand: "Adidas" }), filters)).toBe(
      false
    );
  });

  it("МОП: matches by manager_id", () => {
    const filters: ProcurementFilterState = {
      ...emptyProcurementFilters(),
      managerIds: ["mgr-1"],
    };
    expect(cardPassesProcurementFilters(makeCard({}), filters)).toBe(true);
    expect(
      cardPassesProcurementFilters(makeCard({ manager_id: "mgr-2" }), filters)
    ).toBe(false);
    expect(
      cardPassesProcurementFilters(makeCard({ manager_id: null }), filters)
    ).toBe(false);
  });

  it("МОЗ: passes when ANY procurement_user_id matches a pick", () => {
    const filters: ProcurementFilterState = {
      ...emptyProcurementFilters(),
      procurementUserIds: ["moz-2"],
    };
    expect(
      cardPassesProcurementFilters(
        makeCard({ procurement_user_ids: ["moz-1", "moz-2"] }),
        filters
      )
    ).toBe(true);
    expect(
      cardPassesProcurementFilters(
        makeCard({ procurement_user_ids: ["moz-3"] }),
        filters
      )
    ).toBe(false);
    expect(
      cardPassesProcurementFilters(
        makeCard({ procurement_user_ids: [] }),
        filters
      )
    ).toBe(false);
  });

  it("stage age: uses strict > N", () => {
    const filters: ProcurementFilterState = {
      ...emptyProcurementFilters(),
      stageAge: "gt_7",
    };
    expect(
      cardPassesProcurementFilters(makeCard({ days_in_state: 8 }), filters)
    ).toBe(true);
    expect(
      cardPassesProcurementFilters(makeCard({ days_in_state: 7 }), filters)
    ).toBe(false);
  });
});

describe("filterProcurementColumns", () => {
  const cols: KanbanColumns = {
    distributing: [
      makeCard({ quote_id: "a", brand: "Nike" }),
      makeCard({ quote_id: "b", brand: "Adidas" }),
    ],
    request: [],
    searching_supplier: [
      makeCard({ quote_id: "c", brand: "Nike", days_in_state: 10 }),
    ],
    waiting_prices: [
      makeCard({ quote_id: "d", brand: "Adidas", days_in_state: 3 }),
    ],
    prices_ready: [
      makeCard({ quote_id: "e", brand: "Nike", days_in_state: 1 }),
    ],
    paused: [],
  };

  it("returns the full set with no filters", () => {
    expect(
      totalProcurementCardCount(
        filterProcurementColumns(cols, emptyProcurementFilters())
      )
    ).toBe(5);
  });

  it("filters across every column", () => {
    const out = filterProcurementColumns(cols, {
      ...emptyProcurementFilters(),
      brands: ["Nike"],
    });
    expect(out.distributing.map((c) => c.quote_id)).toEqual(["a"]);
    expect(out.searching_supplier.map((c) => c.quote_id)).toEqual(["c"]);
    expect(out.waiting_prices).toHaveLength(0);
    expect(out.prices_ready.map((c) => c.quote_id)).toEqual(["e"]);
  });
});
