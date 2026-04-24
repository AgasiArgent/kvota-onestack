/**
 * Pure-helper tests for the Task 23 QA verify-buttons UI.
 *
 * The interactive button row is verified via localhost browser testing; these
 * tests exercise the side-effect-free logic that backs it:
 *
 *   - buildVerificationPayload  — shape of the `createVerification` insert
 *   - classifyVerifyError       — Supabase/PostgREST → user-friendly kind
 *   - shouldShowVerifyButtons   — mode + ACL gate
 *   - deriveNodeQaStatus        — derived qa_status from latest per pin
 */

import { describe, it, expect } from "vitest";

import type {
  JourneyPin,
  JourneyVerification,
  RoleSlug,
} from "@/entities/journey";

import {
  buildVerificationPayload,
  classifyVerifyError,
  shouldShowVerifyButtons,
  deriveNodeQaStatus,
} from "../_verify-helpers";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const qaPin: JourneyPin = {
  id: "pin-1",
  node_id: "app:/quotes/new",
  selector: '[data-testid="save"]',
  expected_behavior: "Кнопка сохраняет",
  mode: "qa",
  training_step_order: null,
  linked_story_ref: null,
  last_rel_x: 0.1,
  last_rel_y: 0.2,
  last_rel_width: 0.05,
  last_rel_height: 0.04,
  last_position_update: "2026-04-20T10:00:00Z",
  selector_broken: false,
  created_by: "user-1",
  created_at: "2026-04-01T00:00:00Z",
};

const trainingPin: JourneyPin = {
  ...qaPin,
  id: "pin-2",
  mode: "training",
  training_step_order: 1,
};

function mkVerification(
  overrides: Partial<JourneyVerification> & { pin_id: string },
): JourneyVerification {
  return {
    id: `v-${overrides.pin_id}`,
    node_id: "app:/quotes/new",
    result: "verified",
    note: null,
    attachment_urls: null,
    tested_by: "user-1",
    tested_at: "2026-04-20T12:00:00Z",
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// buildVerificationPayload
// ---------------------------------------------------------------------------

describe("buildVerificationPayload", () => {
  it("produces a minimal verified payload (no note, no attachments)", () => {
    const payload = buildVerificationPayload({
      pinId: "pin-1",
      nodeId: "app:/quotes/new",
      result: "verified",
      testedBy: "user-1",
    });
    expect(payload.pin_id).toBe("pin-1");
    expect(payload.node_id).toBe("app:/quotes/new");
    expect(payload.result).toBe("verified");
    expect(payload.tested_by).toBe("user-1");
    expect(payload.note).toBeNull();
    expect(payload.attachment_urls).toBeNull();
    // DB defaults — must not be in the payload.
    expect("id" in payload).toBe(false);
    expect("tested_at" in payload).toBe(false);
  });

  it("preserves a trimmed note for broken result", () => {
    const payload = buildVerificationPayload({
      pinId: "pin-1",
      nodeId: "app:/quotes/new",
      result: "broken",
      note: "  Кнопка не реагирует на клик  ",
      testedBy: "user-1",
    });
    expect(payload.result).toBe("broken");
    expect(payload.note).toBe("Кнопка не реагирует на клик");
  });

  it("nulls out an empty-string note", () => {
    const payload = buildVerificationPayload({
      pinId: "pin-1",
      nodeId: "app:/quotes/new",
      result: "skip",
      note: "   ",
      testedBy: "user-1",
    });
    expect(payload.note).toBeNull();
  });

  it("does not accept attachment_urls (Task 24 scope)", () => {
    const payload = buildVerificationPayload({
      pinId: "pin-1",
      nodeId: "app:/quotes/new",
      result: "verified",
      testedBy: "user-1",
    });
    expect(payload.attachment_urls).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// classifyVerifyError
// ---------------------------------------------------------------------------

describe("classifyVerifyError", () => {
  it("maps RLS violation on INSERT to PERMISSION_DENIED", () => {
    const info = classifyVerifyError({
      code: "42501",
      message: "new row violates row-level security policy for table",
    });
    expect(info.kind).toBe("PERMISSION_DENIED");
    expect(info.userMessage.length).toBeGreaterThan(0);
  });

  it("maps update/delete denial to APPEND_ONLY_VIOLATION (defensive)", () => {
    const info = classifyVerifyError({
      code: "42501",
      message: "permission denied for UPDATE on journey_verifications",
    });
    expect(info.kind).toBe("APPEND_ONLY_VIOLATION");
  });

  it("maps DELETE denial to APPEND_ONLY_VIOLATION", () => {
    const info = classifyVerifyError({
      code: "42501",
      message: "permission denied for DELETE on journey_verifications",
    });
    expect(info.kind).toBe("APPEND_ONLY_VIOLATION");
  });

  it("falls through to GENERIC_ERROR for unknown shapes", () => {
    const info = classifyVerifyError({ message: "network down" });
    expect(info.kind).toBe("GENERIC_ERROR");
    expect(info.userMessage.length).toBeGreaterThan(0);
  });

  it("handles null/undefined errors", () => {
    expect(classifyVerifyError(null).kind).toBe("GENERIC_ERROR");
    expect(classifyVerifyError(undefined).kind).toBe("GENERIC_ERROR");
  });
});

// ---------------------------------------------------------------------------
// shouldShowVerifyButtons
// ---------------------------------------------------------------------------

describe("shouldShowVerifyButtons", () => {
  it("shows for a QA pin + QA-writer role", () => {
    expect(shouldShowVerifyButtons(qaPin, ["quote_controller"])).toBe(true);
    expect(shouldShowVerifyButtons(qaPin, ["spec_controller"])).toBe(true);
    expect(shouldShowVerifyButtons(qaPin, ["admin"])).toBe(true);
  });

  it("hides for training-mode pins even with QA role", () => {
    expect(shouldShowVerifyButtons(trainingPin, ["admin"])).toBe(false);
    expect(shouldShowVerifyButtons(trainingPin, ["quote_controller"])).toBe(
      false,
    );
  });

  it("hides for a QA pin but non-QA role", () => {
    const nonQaRoles: RoleSlug[] = ["sales", "procurement", "logistics"];
    for (const role of nonQaRoles) {
      expect(shouldShowVerifyButtons(qaPin, [role])).toBe(false);
    }
  });

  it("hides when user has no roles", () => {
    expect(shouldShowVerifyButtons(qaPin, [])).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// deriveNodeQaStatus
// ---------------------------------------------------------------------------

describe("deriveNodeQaStatus", () => {
  it("returns 'untested' for no verifications", () => {
    expect(deriveNodeQaStatus({})).toBe("untested");
  });

  it("returns 'broken' when any pin's latest is broken", () => {
    const map = {
      "pin-1": mkVerification({ pin_id: "pin-1", result: "verified" }),
      "pin-2": mkVerification({ pin_id: "pin-2", result: "broken" }),
    };
    expect(deriveNodeQaStatus(map)).toBe("broken");
  });

  it("returns 'verified' only when all pins are verified", () => {
    const map = {
      "pin-1": mkVerification({ pin_id: "pin-1", result: "verified" }),
      "pin-2": mkVerification({ pin_id: "pin-2", result: "verified" }),
    };
    expect(deriveNodeQaStatus(map)).toBe("verified");
  });

  it("returns 'untested' when a pin was skipped (no firm outcome)", () => {
    const map = {
      "pin-1": mkVerification({ pin_id: "pin-1", result: "verified" }),
      "pin-2": mkVerification({ pin_id: "pin-2", result: "skip" }),
    };
    expect(deriveNodeQaStatus(map)).toBe("untested");
  });
});
