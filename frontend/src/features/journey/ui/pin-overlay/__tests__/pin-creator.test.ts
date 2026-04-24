/**
 * Pure-helper tests for the Task 21 pin-creation UI.
 *
 * The interactive dialog is verified via localhost browser testing; these
 * tests exercise the side-effect-free logic that backs it:
 *
 *   - buildPinPayload           — shape of the `createPin` insert
 *   - validatePinForm           — field-level errors (Russian copy)
 *   - classifyPinCreateError    — Supabase/PostgREST → user-friendly kind
 */

import { describe, it, expect } from "vitest";
import {
  buildPinPayload,
  validatePinForm,
  classifyPinCreateError,
  type PinFormValues,
} from "../_pin-helpers";

const baseForm: PinFormValues = {
  mode: "qa",
  selector: '[data-testid="save-button"]',
  expected_behavior: "Кнопка сохраняет форму",
  training_step_order: null,
  linked_story_ref: null,
};

describe("buildPinPayload", () => {
  it("produces a valid QA pin payload with null training_step_order", () => {
    const payload = buildPinPayload({
      form: baseForm,
      node_id: "app:/quotes/new",
      created_by: "user-1",
    });
    expect(payload.node_id).toBe("app:/quotes/new");
    expect(payload.mode).toBe("qa");
    expect(payload.selector).toBe('[data-testid="save-button"]');
    expect(payload.expected_behavior).toBe("Кнопка сохраняет форму");
    expect(payload.training_step_order).toBeNull();
    expect(payload.linked_story_ref).toBeNull();
    expect(payload.created_by).toBe("user-1");
  });

  it("preserves training_step_order for training-mode pins", () => {
    const payload = buildPinPayload({
      form: { ...baseForm, mode: "training", training_step_order: 3 },
      node_id: "app:/quotes/new",
      created_by: "user-1",
    });
    expect(payload.mode).toBe("training");
    expect(payload.training_step_order).toBe(3);
  });

  it("forces training_step_order to null when mode=qa, even if set in form", () => {
    const payload = buildPinPayload({
      form: { ...baseForm, mode: "qa", training_step_order: 5 },
      node_id: "app:/quotes/new",
      created_by: "user-1",
    });
    expect(payload.training_step_order).toBeNull();
  });

  it("preserves linked_story_ref when provided", () => {
    const payload = buildPinPayload({
      form: { ...baseForm, linked_story_ref: "phase-5b#3" },
      node_id: "app:/quotes/new",
      created_by: "user-1",
    });
    expect(payload.linked_story_ref).toBe("phase-5b#3");
  });
});

describe("validatePinForm", () => {
  it("accepts a well-formed QA pin", () => {
    expect(validatePinForm(baseForm)).toEqual({ valid: true, errors: {} });
  });

  it("accepts a well-formed training pin with order", () => {
    expect(
      validatePinForm({
        ...baseForm,
        mode: "training",
        training_step_order: 1,
      }),
    ).toEqual({ valid: true, errors: {} });
  });

  it("rejects an empty selector", () => {
    const r = validatePinForm({ ...baseForm, selector: "" });
    expect(r.valid).toBe(false);
    expect(r.errors.selector).toBe("Обязательное поле");
  });

  it("rejects a whitespace-only selector", () => {
    const r = validatePinForm({ ...baseForm, selector: "   " });
    expect(r.valid).toBe(false);
    expect(r.errors.selector).toBe("Обязательное поле");
  });

  it("rejects an empty expected_behavior", () => {
    const r = validatePinForm({ ...baseForm, expected_behavior: "" });
    expect(r.valid).toBe(false);
    expect(r.errors.expected_behavior).toBe("Обязательное поле");
  });

  it("rejects training mode with null training_step_order", () => {
    const r = validatePinForm({
      ...baseForm,
      mode: "training",
      training_step_order: null,
    });
    expect(r.valid).toBe(false);
    expect(r.errors.training_step_order).toBe("Укажите порядок шага");
  });

  it("rejects training mode with non-positive training_step_order", () => {
    const r = validatePinForm({
      ...baseForm,
      mode: "training",
      training_step_order: 0,
    });
    expect(r.valid).toBe(false);
    expect(r.errors.training_step_order).toBeTruthy();
  });

  it("rejects a selector that doesn't look like CSS (no [, ., #, tag)", () => {
    const r = validatePinForm({
      ...baseForm,
      selector: "   just some text with spaces   ",
    });
    expect(r.valid).toBe(false);
    expect(r.errors.selector).toBeTruthy();
  });

  it("accepts selectors starting with [", () => {
    expect(
      validatePinForm({ ...baseForm, selector: '[data-testid="x"]' }).valid,
    ).toBe(true);
  });

  it("accepts selectors starting with .", () => {
    expect(validatePinForm({ ...baseForm, selector: ".btn-primary" }).valid).toBe(
      true,
    );
  });

  it("accepts selectors starting with #", () => {
    expect(validatePinForm({ ...baseForm, selector: "#submit" }).valid).toBe(
      true,
    );
  });

  it("accepts plain tag selectors", () => {
    expect(validatePinForm({ ...baseForm, selector: "button" }).valid).toBe(
      true,
    );
  });
});

describe("classifyPinCreateError", () => {
  it("maps RLS 42501 to PERMISSION_DENIED with a Russian message", () => {
    const result = classifyPinCreateError({
      code: "42501",
      message: "new row violates row-level security policy",
    });
    expect(result.kind).toBe("PERMISSION_DENIED");
    expect(result.userMessage).toMatch(/прав|доступ/i);
  });

  it("maps PostgREST-wrapped RLS message to PERMISSION_DENIED", () => {
    const result = classifyPinCreateError({
      message:
        'new row violates row-level security policy for table "journey_pins"',
    });
    expect(result.kind).toBe("PERMISSION_DENIED");
  });

  it("maps FK violation 23503 to FK_VIOLATION", () => {
    const result = classifyPinCreateError({
      code: "23503",
      message: "insert or update on table violates foreign key constraint",
    });
    expect(result.kind).toBe("FK_VIOLATION");
    expect(result.userMessage.length).toBeGreaterThan(0);
  });

  it("maps unique violation 23505 to UNIQUE_VIOLATION", () => {
    const result = classifyPinCreateError({
      code: "23505",
      message: "duplicate key value violates unique constraint",
    });
    expect(result.kind).toBe("UNIQUE_VIOLATION");
    expect(result.userMessage.length).toBeGreaterThan(0);
  });

  it("falls back to UNKNOWN for unmapped errors", () => {
    const result = classifyPinCreateError({
      code: "XX000",
      message: "internal error",
    });
    expect(result.kind).toBe("UNKNOWN");
    expect(result.userMessage.length).toBeGreaterThan(0);
  });

  it("handles null/undefined gracefully", () => {
    expect(classifyPinCreateError(null).kind).toBe("UNKNOWN");
    expect(classifyPinCreateError(undefined).kind).toBe("UNKNOWN");
  });
});
