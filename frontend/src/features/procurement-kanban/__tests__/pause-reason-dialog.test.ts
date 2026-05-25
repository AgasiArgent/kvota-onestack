import { describe, it, expect } from "vitest";
import { canSubmitPauseReason } from "../ui/pause-reason-dialog";

/**
 * canSubmitPauseReason controls the «Поставить на паузу» button state in
 * PauseReasonDialog. We test the pure helper directly since the dialog
 * portals via @base-ui/react, which requires a DOM environment.
 * Full interaction (typing, submit, cancel) is covered by localhost browser
 * verification during deploy.
 */
describe("PauseReasonDialog — canSubmitPauseReason", () => {
  it("returns false for an empty string (Testing 2 row 74 mandatory)", () => {
    expect(canSubmitPauseReason("", false)).toBe(false);
  });

  it("returns false for whitespace-only input", () => {
    expect(canSubmitPauseReason("   ", false)).toBe(false);
    expect(canSubmitPauseReason("\n\t", false)).toBe(false);
  });

  it("returns true for a non-empty trimmed reason", () => {
    expect(canSubmitPauseReason("supplier unreachable", false)).toBe(true);
  });

  it("returns false while a submit is in flight, even with valid text", () => {
    expect(canSubmitPauseReason("valid reason", true)).toBe(false);
  });
});
