import { describe, it, expect } from "vitest";
import { extractErrorMessage } from "../errors";

describe("extractErrorMessage", () => {
  describe("Supabase PostgrestError shape", () => {
    it("returns the message when only code+message are present", () => {
      const err = { code: "23505", message: "duplicate key value" };
      expect(extractErrorMessage(err)).toBe("duplicate key value");
    });

    it("appends details in parens when present", () => {
      const err = {
        code: "23505",
        message: "duplicate key value",
        details: "Key (id)=(abc) already exists.",
      };
      expect(extractErrorMessage(err)).toBe(
        "duplicate key value (Key (id)=(abc) already exists.)"
      );
    });

    it("appends hint in parens when details is missing", () => {
      const err = {
        code: "42501",
        message: "permission denied for table quote_items",
        hint: "Check RLS policies",
      };
      expect(extractErrorMessage(err)).toBe(
        "permission denied for table quote_items (Check RLS policies)"
      );
    });

    it("prefers details over hint when both are present", () => {
      const err = {
        code: "23505",
        message: "duplicate key",
        details: "actual detail",
        hint: "ignored hint",
      };
      expect(extractErrorMessage(err)).toBe("duplicate key (actual detail)");
    });

    it("ignores empty-string details/hint", () => {
      const err = {
        code: "23505",
        message: "duplicate key",
        details: "",
        hint: "  ",
      };
      expect(extractErrorMessage(err)).toBe("duplicate key");
    });

    it("strips duplicate whitespace from the combined message", () => {
      const err = {
        code: "xx",
        message: "bad   thing",
        details: "line1\n\nline2",
      };
      expect(extractErrorMessage(err)).toBe("bad thing (line1 line2)");
    });
  });

  describe("Fetch-response error shape", () => {
    it("returns nested error.message", () => {
      const err = {
        success: false,
        error: { code: "VALIDATION_ERROR", message: "Missing field: supplier_id" },
      };
      expect(extractErrorMessage(err)).toBe("Missing field: supplier_id");
    });

    it("handles response shape without success flag", () => {
      const err = { error: { message: "Forbidden" } };
      expect(extractErrorMessage(err)).toBe("Forbidden");
    });

    it("returns null when nested error.message is empty", () => {
      const err = { success: false, error: { code: "x", message: "" } };
      expect(extractErrorMessage(err)).toBeNull();
    });

    it("returns null when nested error is not an object", () => {
      const err = { success: false, error: "string error" };
      expect(extractErrorMessage(err)).toBeNull();
    });
  });

  describe("Native Error", () => {
    it("returns err.message", () => {
      const err = new Error("something went wrong");
      expect(extractErrorMessage(err)).toBe("something went wrong");
    });

    it("returns null for Error with empty message", () => {
      const err = new Error("");
      expect(extractErrorMessage(err)).toBeNull();
    });

    it("handles Error subclasses", () => {
      class CustomError extends Error {}
      const err = new CustomError("custom failure");
      expect(extractErrorMessage(err)).toBe("custom failure");
    });
  });

  describe("String", () => {
    it("returns the string as-is when non-empty", () => {
      expect(extractErrorMessage("Something broke")).toBe("Something broke");
    });

    it("trims whitespace-only strings to null", () => {
      expect(extractErrorMessage("   ")).toBeNull();
    });

    it("trims surrounding whitespace on real strings", () => {
      expect(extractErrorMessage("  real message  ")).toBe("real message");
    });
  });

  describe("Fallback cases", () => {
    it("returns null for null", () => {
      expect(extractErrorMessage(null)).toBeNull();
    });

    it("returns null for undefined", () => {
      expect(extractErrorMessage(undefined)).toBeNull();
    });

    it("returns null for empty string", () => {
      expect(extractErrorMessage("")).toBeNull();
    });

    it("returns null for an object without message or error fields", () => {
      const err = { foo: "bar", code: 42 };
      expect(extractErrorMessage(err)).toBeNull();
    });

    it("returns null for an empty object", () => {
      expect(extractErrorMessage({})).toBeNull();
    });

    it("returns null for number", () => {
      expect(extractErrorMessage(500)).toBeNull();
    });

    it("returns null for boolean", () => {
      expect(extractErrorMessage(false)).toBeNull();
    });

    it("returns null for an object with code but no message", () => {
      const err = { code: "PGRST100" };
      expect(extractErrorMessage(err)).toBeNull();
    });

    it("returns null for an object with message but no code (not a PostgrestError)", () => {
      const err = { message: "looks like an error but no code" };
      expect(extractErrorMessage(err)).toBeNull();
    });
  });
});
