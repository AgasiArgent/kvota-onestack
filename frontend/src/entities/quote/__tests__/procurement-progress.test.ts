import { describe, expect, it } from "vitest";

import {
  getProcurementProgress,
  type ProcurementProgressInvoice,
} from "../procurement-progress";

describe("getProcurementProgress", () => {
  it("returns empty when no invoices", () => {
    expect(getProcurementProgress([])).toEqual({
      completed: 0,
      total: 0,
      label: "",
    });
  });

  it("excludes empty invoices from the total", () => {
    const invoices: ProcurementProgressInvoice[] = [
      { procurement_completed_at: null, items_count: 0 },
      { procurement_completed_at: null, items_count: 0 },
    ];
    expect(getProcurementProgress(invoices).total).toBe(0);
    expect(getProcurementProgress(invoices).label).toBe("");
  });

  it("counts only invoices with items", () => {
    const invoices: ProcurementProgressInvoice[] = [
      { procurement_completed_at: "2026-05-01T10:00:00Z", items_count: 2 },
      { procurement_completed_at: null, items_count: 1 },
      { procurement_completed_at: null, items_count: 0 },
    ];
    const result = getProcurementProgress(invoices);
    expect(result.completed).toBe(1);
    expect(result.total).toBe(2);
    expect(result.label).toBe("1/2 КП завершено");
  });

  it("collapses to «Закупка завершена» when every real invoice is closed", () => {
    const invoices: ProcurementProgressInvoice[] = [
      { procurement_completed_at: "2026-05-01T10:00:00Z", items_count: 1 },
      { procurement_completed_at: "2026-05-01T11:00:00Z", items_count: 3 },
      { procurement_completed_at: null, items_count: 0 }, // empty draft, ignored
    ];
    expect(getProcurementProgress(invoices)).toEqual({
      completed: 2,
      total: 2,
      label: "Закупка завершена",
    });
  });

  it("treats unknown items_count as non-empty", () => {
    const invoices: ProcurementProgressInvoice[] = [
      { procurement_completed_at: null },
      { procurement_completed_at: "2026-05-01T10:00:00Z" },
    ];
    expect(getProcurementProgress(invoices)).toEqual({
      completed: 1,
      total: 2,
      label: "1/2 КП завершено",
    });
  });
});
