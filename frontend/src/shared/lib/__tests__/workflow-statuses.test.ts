import { describe, it, expect } from "vitest";
import {
  WORKFLOW_STATUS_LABELS_RU,
  WORKFLOW_STATUS_FILTER_VALUES,
  getWorkflowStatusFilterOptions,
  workflowStatusLabel,
} from "../workflow-statuses";

describe("workflowStatusLabel", () => {
  it("translates pending_procurement → «Закупки» (МОЗ-47 regression)", () => {
    expect(workflowStatusLabel("pending_procurement")).toBe("Закупки");
  });

  it("translates procurement_complete (status that previously fell through to raw English)", () => {
    // Before the fix, the static label list in queries.ts omitted
    // procurement_complete; the table cell rendered the raw enum value
    // because statusLabelMap.get() returned undefined.
    expect(workflowStatusLabel("procurement_complete")).toBe(
      "Закупки завершены"
    );
  });

  it("covers every workflow_status the backend can store on a quote", () => {
    // Every value the Python WorkflowStatus enum can write to
    // kvota.quotes.workflow_status. If the backend grows a new variant the
    // map must grow with it — this assertion fails loudly so the regression
    // surfaces in CI rather than as English text in the table cell.
    const enumValues = [
      "draft",
      "pending_procurement",
      "procurement_complete",
      "pending_logistics",
      "pending_customs",
      "pending_logistics_and_customs",
      "pending_quote_control",
      "pending_spec_control",
      "pending_sales_review",
      "pending_approval",
      "approved",
      "sent_to_client",
      "client_negotiation",
      "accepted",
      "pending_signature",
      "spec_signed",
      "deal",
      "rejected",
      "cancelled",
    ];
    for (const value of enumValues) {
      expect(WORKFLOW_STATUS_LABELS_RU[value]).toBeDefined();
      // Sanity: the label must contain at least one Cyrillic character so
      // we don't accidentally ship `pending_procurement: "pending_procurement"`.
      expect(WORKFLOW_STATUS_LABELS_RU[value]).toMatch(/[Ѐ-ӿ]/);
    }
  });

  it("falls back to the raw status when the enum value is genuinely unknown", () => {
    // Unknown statuses can sneak in from legacy/dirty rows; we'd rather
    // surface them verbatim than render an empty cell.
    expect(workflowStatusLabel("totally_made_up")).toBe("totally_made_up");
  });

  it("returns an em-dash for null / undefined / empty status", () => {
    expect(workflowStatusLabel(null)).toBe("—");
    expect(workflowStatusLabel(undefined)).toBe("—");
    expect(workflowStatusLabel("")).toBe("—");
  });
});

describe("getWorkflowStatusFilterOptions", () => {
  it("returns Russian labels for every filter value", () => {
    const options = getWorkflowStatusFilterOptions();
    expect(options.length).toBe(WORKFLOW_STATUS_FILTER_VALUES.length);
    for (const opt of options) {
      expect(opt.label).not.toBe(opt.value);
      expect(opt.label).toMatch(/[Ѐ-ӿ]/);
    }
  });

  it("preserves the declared order so the dropdown is deterministic", () => {
    const options = getWorkflowStatusFilterOptions();
    expect(options.map((o) => o.value)).toEqual([
      ...WORKFLOW_STATUS_FILTER_VALUES,
    ]);
  });
});
