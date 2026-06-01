import { describe, it, expect } from "vitest";
import {
  DEADLINE_TRACKED_STAGES,
  WORKFLOW_STATUS_LABELS_RU,
  getDeadlineTrackedStageOptions,
} from "../workflow-statuses";

/**
 * Testing 2 row 55 — Настройки › «Дедлайны стадий» must reflect the ACTUAL
 * system stages. The deadline-tracked set must equal Python's
 * IN_PROGRESS_STATUSES (services/workflow_service.py): every non-terminal,
 * non-draft workflow status. If the two drift, a quote can sit in a stage the
 * settings screen can't configure (regression: `approved` was missing).
 */
describe("DEADLINE_TRACKED_STAGES", () => {
  // Mirror of Python IN_PROGRESS_STATUSES — the stages stage_timer_service.py
  // tracks (all workflow_status values minus TERMINAL_STATUSES + draft).
  const CANONICAL_IN_PROGRESS = [
    "pending_procurement",
    "pending_logistics",
    "pending_customs",
    "pending_logistics_and_customs",
    "pending_sales_review",
    "pending_quote_control",
    "pending_approval",
    "approved",
    "sent_to_client",
    "client_negotiation",
    "pending_spec_control",
    "pending_signature",
  ];

  it("matches the canonical in-progress stage SET exactly", () => {
    expect([...DEADLINE_TRACKED_STAGES].sort()).toEqual(
      [...CANONICAL_IN_PROGRESS].sort()
    );
  });

  it("includes `approved` (the stage missing from the original seed)", () => {
    expect(DEADLINE_TRACKED_STAGES).toContain("approved");
  });

  it("excludes terminal / draft stages that carry no deadline timer", () => {
    for (const terminal of ["draft", "deal", "rejected", "cancelled"]) {
      expect(DEADLINE_TRACKED_STAGES).not.toContain(terminal);
    }
  });

  it("has a canonical Russian label for every tracked stage", () => {
    for (const stage of DEADLINE_TRACKED_STAGES) {
      expect(WORKFLOW_STATUS_LABELS_RU[stage]).toBeDefined();
      expect(WORKFLOW_STATUS_LABELS_RU[stage]).toMatch(/[Ѐ-ӿ]/);
    }
  });
});

describe("getDeadlineTrackedStageOptions", () => {
  it("returns one {stage,label} per tracked stage in declared order", () => {
    const options = getDeadlineTrackedStageOptions();
    expect(options.map((o) => o.stage)).toEqual([...DEADLINE_TRACKED_STAGES]);
  });

  it("labels every option with its canonical Russian label, never the raw key", () => {
    for (const opt of getDeadlineTrackedStageOptions()) {
      expect(opt.label).toBe(WORKFLOW_STATUS_LABELS_RU[opt.stage]);
      expect(opt.label).not.toBe(opt.stage);
      expect(opt.label).toMatch(/[Ѐ-ӿ]/);
    }
  });
});
