import { describe, it, expect } from "vitest";
import { canSubmitReason } from "../ui/substatus-reason-dialog";

/**
 * canSubmitReason controls the submit button state in SubstatusReasonDialog.
 * We test the pure helper directly since the dialog portals via @base-ui/react,
 * which requires a DOM environment not configured in this workspace.
 * Full interaction (typing, submit, cancel) is covered by localhost browser
 * verification during deploy.
 */
describe("SubstatusReasonDialog — canSubmitReason", () => {
  it("returns false for an empty string", () => {
    expect(canSubmitReason("", false)).toBe(false);
  });

  it("returns false for whitespace-only input", () => {
    expect(canSubmitReason("   ", false)).toBe(false);
    expect(canSubmitReason("\n\t", false)).toBe(false);
  });

  it("returns true for a non-empty trimmed reason", () => {
    expect(canSubmitReason("supplier unreachable", false)).toBe(true);
  });

  it("returns false while a submit is in flight, even with valid text", () => {
    expect(canSubmitReason("valid reason", true)).toBe(false);
  });
});
