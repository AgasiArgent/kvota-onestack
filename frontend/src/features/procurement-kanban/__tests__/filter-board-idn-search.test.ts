/**
 * IDN search filter for the procurement kanban (Testing 2 row 66).
 *
 * Verifies the case-insensitive substring match against `idn_quote` and
 * graceful handling of empty / whitespace-only queries.
 */

import { describe, expect, it } from "vitest";

import type { KanbanBrandCard } from "../model/types";
import {
  cardPassesProcurementFilters,
  emptyProcurementFilters,
  hasActiveProcurementFilters,
} from "../lib/filter-board";

function makeCard(overrides: Partial<KanbanBrandCard>): KanbanBrandCard {
  return {
    quote_id: "q-1",
    brand: "Nike",
    idn_quote: "Q-202605-0042",
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

describe("procurement: hasActiveProcurementFilters with idnSearch", () => {
  it("treats null idnSearch as inactive", () => {
    expect(
      hasActiveProcurementFilters({
        ...emptyProcurementFilters(),
        idnSearch: null,
      })
    ).toBe(false);
  });

  it("treats empty / whitespace-only idnSearch as inactive", () => {
    expect(
      hasActiveProcurementFilters({
        ...emptyProcurementFilters(),
        idnSearch: "",
      })
    ).toBe(false);
    expect(
      hasActiveProcurementFilters({
        ...emptyProcurementFilters(),
        idnSearch: "   ",
      })
    ).toBe(false);
  });

  it("reports active when idnSearch has non-empty content", () => {
    expect(
      hasActiveProcurementFilters({
        ...emptyProcurementFilters(),
        idnSearch: "Q-2026",
      })
    ).toBe(true);
  });
});

describe("procurement: cardPassesProcurementFilters — idnSearch", () => {
  it("matches when idn_quote contains the search substring", () => {
    const filters = { ...emptyProcurementFilters(), idnSearch: "0042" };
    expect(
      cardPassesProcurementFilters(
        makeCard({ idn_quote: "Q-202605-0042" }),
        filters
      )
    ).toBe(true);
  });

  it("is case-insensitive", () => {
    const filters = { ...emptyProcurementFilters(), idnSearch: "q-202605" };
    expect(
      cardPassesProcurementFilters(
        makeCard({ idn_quote: "Q-202605-0042" }),
        filters
      )
    ).toBe(true);
    const filters2 = { ...emptyProcurementFilters(), idnSearch: "Q-202605" };
    expect(
      cardPassesProcurementFilters(
        makeCard({ idn_quote: "q-202605-0042" }),
        filters2
      )
    ).toBe(true);
  });

  it("rejects cards whose idn_quote does not contain the substring", () => {
    const filters = { ...emptyProcurementFilters(), idnSearch: "0042" };
    expect(
      cardPassesProcurementFilters(
        makeCard({ idn_quote: "Q-202605-9999" }),
        filters
      )
    ).toBe(false);
  });

  it("ignores leading/trailing whitespace in the query", () => {
    const filters = {
      ...emptyProcurementFilters(),
      idnSearch: "  Q-202605  ",
    };
    expect(
      cardPassesProcurementFilters(
        makeCard({ idn_quote: "Q-202605-0042" }),
        filters
      )
    ).toBe(true);
  });

  it("is a no-op when idnSearch is whitespace-only (treated as unset)", () => {
    const filters = { ...emptyProcurementFilters(), idnSearch: "   " };
    expect(
      cardPassesProcurementFilters(
        makeCard({ idn_quote: "Q-202605-0042" }),
        filters
      )
    ).toBe(true);
  });
});
