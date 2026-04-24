/**
 * Pure-helper tests for the Task 27 training-section UI.
 *
 * Interactive dialog behaviour is verified via localhost browser testing;
 * these tests exercise the ordering + ACL helpers.
 */

import { describe, it, expect } from "vitest";

import type { JourneyPin } from "@/entities/journey";

import {
  canEditTraining,
  nextTrainingStepOrder,
  orderTrainingSteps,
} from "../_training-helpers";

function pin(overrides: Partial<JourneyPin>): JourneyPin {
  return {
    id: overrides.id ?? "p-1",
    node_id: "app:/quotes/new",
    selector: overrides.selector ?? '[data-testid="x"]',
    expected_behavior: overrides.expected_behavior ?? "step body",
    mode: overrides.mode ?? "training",
    training_step_order: overrides.training_step_order ?? null,
    linked_story_ref: null,
    last_rel_x: null,
    last_rel_y: null,
    last_rel_width: null,
    last_rel_height: null,
    last_position_update: null,
    selector_broken: false,
    created_by: "u-1",
    created_at: "2026-04-24T00:00:00Z",
  };
}

describe("orderTrainingSteps", () => {
  it("filters out non-training pins", () => {
    const pins = [
      pin({ id: "a", mode: "qa", training_step_order: 1 }),
      pin({ id: "b", mode: "training", training_step_order: 2 }),
    ];
    const out = orderTrainingSteps(pins);
    expect(out).toHaveLength(1);
    expect(out[0].id).toBe("b");
  });

  it("sorts by training_step_order ascending", () => {
    const pins = [
      pin({ id: "c", training_step_order: 3 }),
      pin({ id: "a", training_step_order: 1 }),
      pin({ id: "b", training_step_order: 2 }),
    ];
    const out = orderTrainingSteps(pins);
    expect(out.map((p) => p.id)).toEqual(["a", "b", "c"]);
  });

  it("places null-order pins at the end, preserving insertion order", () => {
    const pins = [
      pin({ id: "null2", training_step_order: null }),
      pin({ id: "ordered", training_step_order: 1 }),
      pin({ id: "null1", training_step_order: null }),
    ];
    const out = orderTrainingSteps(pins);
    expect(out.map((p) => p.id)).toEqual(["ordered", "null2", "null1"]);
  });

  it("returns an empty array when given no training pins", () => {
    expect(orderTrainingSteps([pin({ id: "x", mode: "qa" })])).toEqual([]);
  });

  it("does not mutate its input", () => {
    const pins = [
      pin({ id: "b", training_step_order: 2 }),
      pin({ id: "a", training_step_order: 1 }),
    ];
    const before = pins.map((p) => p.id).join(",");
    orderTrainingSteps(pins);
    expect(pins.map((p) => p.id).join(",")).toBe(before);
  });
});

describe("nextTrainingStepOrder", () => {
  it("returns 1 when no training pins exist", () => {
    expect(nextTrainingStepOrder([])).toBe(1);
    expect(nextTrainingStepOrder([pin({ id: "x", mode: "qa" })])).toBe(1);
  });

  it("returns max + 1 over existing training pins", () => {
    const pins = [
      pin({ id: "a", training_step_order: 1 }),
      pin({ id: "b", training_step_order: 3 }),
      pin({ id: "c", training_step_order: 2 }),
    ];
    expect(nextTrainingStepOrder(pins)).toBe(4);
  });

  it("ignores training pins with null order", () => {
    const pins = [
      pin({ id: "a", training_step_order: 5 }),
      pin({ id: "b", training_step_order: null }),
    ];
    expect(nextTrainingStepOrder(pins)).toBe(6);
  });

  it("ignores QA pins", () => {
    const pins = [
      pin({ id: "a", training_step_order: 1 }),
      pin({ id: "b", mode: "qa", training_step_order: 99 }),
    ];
    expect(nextTrainingStepOrder(pins)).toBe(2);
  });
});

describe("canEditTraining", () => {
  it("accepts admin", () => {
    expect(canEditTraining(["admin"])).toBe(true);
  });

  it("accepts each head_of_* role", () => {
    expect(canEditTraining(["head_of_sales"])).toBe(true);
    expect(canEditTraining(["head_of_procurement"])).toBe(true);
    expect(canEditTraining(["head_of_logistics"])).toBe(true);
  });

  it("rejects line-level roles", () => {
    expect(canEditTraining(["sales"])).toBe(false);
    expect(canEditTraining(["procurement"])).toBe(false);
    expect(canEditTraining(["logistics"])).toBe(false);
    expect(canEditTraining(["customs"])).toBe(false);
    expect(canEditTraining(["quote_controller"])).toBe(false);
    expect(canEditTraining(["spec_controller"])).toBe(false);
    expect(canEditTraining(["top_manager"])).toBe(false);
  });

  it("rejects an empty role list", () => {
    expect(canEditTraining([])).toBe(false);
  });

  it("matches if any held role qualifies", () => {
    expect(canEditTraining(["sales", "admin"])).toBe(true);
  });
});
