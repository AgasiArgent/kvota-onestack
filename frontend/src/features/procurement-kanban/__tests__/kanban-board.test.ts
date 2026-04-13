import { describe, it, expect } from "vitest";
import {
  PROCUREMENT_SUBSTATUSES,
  SUBSTATUS_LABELS_RU,
} from "@/shared/lib/workflow-substates";
import type { KanbanColumns } from "../model/types";

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
      distributing: [
        {
          id: "q1",
          idn_quote: "Q-202604-0001",
          customer_name: "Acme",
          days_in_state: 2,
          latest_reason: null,
          procurement_substatus: "distributing",
          brands: [],
          manager_name: null,
          procurement_user_names: [],
          invoice_sums: [],
        },
      ],
      searching_supplier: [],
      waiting_prices: [],
      prices_ready: [],
    };
    const counts = PROCUREMENT_SUBSTATUSES.map((s) => state[s].length);
    expect(counts).toEqual([1, 0, 0, 0]);
    expect(counts.reduce((a, b) => a + b, 0)).toBe(1);
  });
});
