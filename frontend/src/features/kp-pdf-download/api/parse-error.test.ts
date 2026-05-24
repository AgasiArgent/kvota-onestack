import { describe, it, expect } from "vitest";

import { parseErrorMessage } from "./parse-error";

/**
 * REQ-19: each known error code from the Python KP renderer maps to a
 * specific Russian-language toast string. Unknown codes fall back to the
 * server's message (if any) or to a generic copy — never "Unknown error".
 */
describe("parseErrorMessage", () => {
  it("maps UNAUTHORIZED to the session-expired copy", () => {
    expect(
      parseErrorMessage({ code: "UNAUTHORIZED", message: "ignored" }),
    ).toBe("Сессия истекла, перезагрузите страницу");
  });

  it("returns the server-provided message verbatim for VALIDATION_ERROR", () => {
    // REQ-19.2: the buyer must see which field tripped validation.
    expect(
      parseErrorMessage({
        code: "VALIDATION_ERROR",
        message: "Email is required",
      }),
    ).toBe("Email is required");
  });

  it("includes the requestId tail for RENDER_ERROR when present", () => {
    expect(
      parseErrorMessage({
        code: "RENDER_ERROR",
        message: "ignored",
        requestId: "req-abc-123",
      }),
    ).toBe("Не удалось сгенерировать PDF, попробуйте ещё раз (ID: req-abc-123)");
  });

  it("falls back to generic RENDER_ERROR copy without requestId", () => {
    expect(
      parseErrorMessage({ code: "RENDER_ERROR", message: "ignored" }),
    ).toBe("Не удалось сгенерировать PDF, попробуйте ещё раз");
  });

  it("falls back to generic copy on unknown code", () => {
    expect(
      parseErrorMessage({ code: "SOMETHING_NEW", message: "" }),
    ).toBe("Не удалось сгенерировать PDF");
  });
});
