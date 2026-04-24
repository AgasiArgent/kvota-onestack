/**
 * Pure-helper tests for the Task 27 training-editor dialog.
 *
 * The dialog itself (drag/reorder UX, optimistic updates, rollback) is
 * verified via localhost browser testing per the pattern documented in
 * node-drawer.test.tsx. These tests pin the side-effect-free logic:
 *
 *   - buildTrainingStepPayload   — shape of the `createPin` insert
 *   - computeReorderedSteps      — pure array reorder → id/order tuples
 *   - classifyTrainingEditorError — Supabase/PostgREST → user-friendly kind
 */

import { describe, it, expect } from "vitest";

import type { JourneyPin } from "@/entities/journey";

import {
  buildTrainingStepPayload,
  classifyTrainingEditorError,
  computeReorderedSteps,
} from "../_training-helpers";

function pin(id: string, order: number | null): JourneyPin {
  return {
    id,
    node_id: "app:/quotes/new",
    selector: '[data-testid="x"]',
    expected_behavior: `step ${id}`,
    mode: "training",
    training_step_order: order,
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

describe("buildTrainingStepPayload", () => {
  it("returns a training-mode insert with a non-null step order", () => {
    const payload = buildTrainingStepPayload({
      stepOrder: 2,
      expected_behavior: "**Bold** step body",
      selector: '[data-testid="save"]',
      node_id: "app:/quotes/new",
      created_by: "user-1",
    });
    expect(payload.mode).toBe("training");
    expect(payload.training_step_order).toBe(2);
    expect(payload.node_id).toBe("app:/quotes/new");
    expect(payload.selector).toBe('[data-testid="save"]');
    expect(payload.expected_behavior).toBe("**Bold** step body");
    expect(payload.created_by).toBe("user-1");
    expect(payload.linked_story_ref).toBeNull();
  });

  it("preserves linked_story_ref when provided", () => {
    const payload = buildTrainingStepPayload({
      stepOrder: 1,
      expected_behavior: "step",
      selector: ".btn",
      node_id: "app:/quotes/new",
      created_by: "u",
      linked_story_ref: "phase-5b#3",
    });
    expect(payload.linked_story_ref).toBe("phase-5b#3");
  });

  it("forces mode=training even for step order 0 or negative input", () => {
    // The editor is expected to reject non-positive orders at the form
    // level; this test just pins the raw payload shape so a bug in form
    // validation can't slip a wrong-mode row into the DB.
    const payload = buildTrainingStepPayload({
      stepOrder: -1,
      expected_behavior: "x",
      selector: ".y",
      node_id: "app:/quotes/new",
      created_by: "u",
    });
    expect(payload.mode).toBe("training");
    expect(payload.training_step_order).toBe(-1);
  });
});

describe("computeReorderedSteps", () => {
  it("returns an empty list when from == to", () => {
    const steps = [pin("a", 1), pin("b", 2), pin("c", 3)];
    expect(computeReorderedSteps(steps, 1, 1)).toEqual([]);
  });

  it("moves item forward and reports only changed rows", () => {
    const steps = [pin("a", 1), pin("b", 2), pin("c", 3)];
    // move "a" from index 0 to index 2 → [b, c, a]
    const changes = computeReorderedSteps(steps, 0, 2);
    // New order: b→1, c→2, a→3. "b" went from 2→1, "c" from 3→2, "a" from 1→3
    expect(changes).toEqual([
      { id: "b", training_step_order: 1 },
      { id: "c", training_step_order: 2 },
      { id: "a", training_step_order: 3 },
    ]);
  });

  it("moves item backward and reports only changed rows", () => {
    const steps = [pin("a", 1), pin("b", 2), pin("c", 3)];
    // move "c" from index 2 to index 0 → [c, a, b]
    const changes = computeReorderedSteps(steps, 2, 0);
    expect(changes).toEqual([
      { id: "c", training_step_order: 1 },
      { id: "a", training_step_order: 2 },
      { id: "b", training_step_order: 3 },
    ]);
  });

  it("moves adjacent items and only reports the swapped pair", () => {
    const steps = [pin("a", 1), pin("b", 2), pin("c", 3)];
    // swap a <-> b → [b, a, c]. "c" stays at 3, not reported.
    const changes = computeReorderedSteps(steps, 0, 1);
    expect(changes).toEqual([
      { id: "b", training_step_order: 1 },
      { id: "a", training_step_order: 2 },
    ]);
  });

  it("assigns contiguous 1..N orders even when input orders are sparse", () => {
    const steps = [pin("a", 5), pin("b", 9), pin("c", 20)];
    const changes = computeReorderedSteps(steps, 0, 1);
    // After reorder: [b, a, c]. New orders 1, 2, 3 — all differ from input.
    expect(changes).toEqual([
      { id: "b", training_step_order: 1 },
      { id: "a", training_step_order: 2 },
      { id: "c", training_step_order: 3 },
    ]);
  });

  it("returns empty for out-of-range indices", () => {
    const steps = [pin("a", 1), pin("b", 2)];
    expect(computeReorderedSteps(steps, -1, 0)).toEqual([]);
    expect(computeReorderedSteps(steps, 0, 5)).toEqual([]);
    expect(computeReorderedSteps(steps, 2, 0)).toEqual([]);
  });

  it("does not mutate its input", () => {
    const steps = [pin("a", 1), pin("b", 2), pin("c", 3)];
    const before = steps.map((p) => `${p.id}:${p.training_step_order}`).join(",");
    computeReorderedSteps(steps, 0, 2);
    const after = steps.map((p) => `${p.id}:${p.training_step_order}`).join(",");
    expect(after).toBe(before);
  });
});

describe("classifyTrainingEditorError", () => {
  it("maps RLS 42501 to PERMISSION_DENIED with a Russian message", () => {
    const info = classifyTrainingEditorError({
      code: "42501",
      message: "new row violates row-level security policy",
    });
    expect(info.kind).toBe("PERMISSION_DENIED");
    expect(info.userMessage).toMatch(/прав|доступ/i);
  });

  it("maps PostgREST-wrapped RLS message to PERMISSION_DENIED", () => {
    const info = classifyTrainingEditorError({
      message:
        'new row violates row-level security policy for table "journey_pins"',
    });
    expect(info.kind).toBe("PERMISSION_DENIED");
  });

  it("maps CHECK constraint violations to VALIDATION", () => {
    const info = classifyTrainingEditorError({
      code: "23514",
      message: 'new row violates check constraint "journey_pins_training_order_chk"',
    });
    expect(info.kind).toBe("VALIDATION");
    expect(info.userMessage.length).toBeGreaterThan(0);
  });

  it("maps FK violation 23503 to FK_VIOLATION", () => {
    const info = classifyTrainingEditorError({
      code: "23503",
      message: "insert or update on table violates foreign key constraint",
    });
    expect(info.kind).toBe("FK_VIOLATION");
  });

  it("falls back to UNKNOWN for unmapped errors", () => {
    const info = classifyTrainingEditorError({
      code: "XX000",
      message: "boom",
    });
    expect(info.kind).toBe("UNKNOWN");
    expect(info.userMessage).toBe("boom");
  });

  it("handles null/undefined gracefully", () => {
    expect(classifyTrainingEditorError(null).kind).toBe("UNKNOWN");
    expect(classifyTrainingEditorError(undefined).kind).toBe("UNKNOWN");
  });
});
