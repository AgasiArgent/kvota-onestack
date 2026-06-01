import { describe, it, expect } from "vitest";
import { resolveQuoteUserDisplay } from "../queries";

const USERS = new Map<string, { id: string; full_name: string }>([
  ["u-quote", { id: "u-quote", full_name: "Quote Level" }],
  ["u-inv-1", { id: "u-inv-1", full_name: "Invoice One" }],
  ["u-inv-2", { id: "u-inv-2", full_name: "Invoice Two" }],
]);

describe("resolveQuoteUserDisplay — Testing 2 row 94 МОЛ/МВЭД fallback", () => {
  it("uses the quote-level user when it is set (existing-correct rows unchanged)", () => {
    const result = resolveQuoteUserDisplay(
      "u-quote",
      new Set(["u-inv-1"]), // invoice-level present but ignored
      USERS
    );
    expect(result).toEqual({ id: "u-quote", full_name: "Quote Level" });
  });

  it("falls back to the single invoice-level user when quote-level is null", () => {
    const result = resolveQuoteUserDisplay(null, new Set(["u-inv-1"]), USERS);
    expect(result).toEqual({ id: "u-inv-1", full_name: "Invoice One" });
  });

  it("joins names of two distinct invoice-level users when quote-level is null", () => {
    const result = resolveQuoteUserDisplay(
      null,
      new Set(["u-inv-1", "u-inv-2"]),
      USERS
    );
    expect(result?.full_name).toBe("Invoice One, Invoice Two");
    // id is the first distinct invoice user, for a stable React key
    expect(result?.id).toBe("u-inv-1");
  });

  it("returns null when neither quote-level nor invoice-level users are set", () => {
    expect(resolveQuoteUserDisplay(null, undefined, USERS)).toBeNull();
    expect(resolveQuoteUserDisplay(null, new Set(), USERS)).toBeNull();
    expect(resolveQuoteUserDisplay(undefined, undefined, USERS)).toBeNull();
  });

  it("treats undefined quote-level the same as null (falls back to invoice)", () => {
    const result = resolveQuoteUserDisplay(
      undefined,
      new Set(["u-inv-2"]),
      USERS
    );
    expect(result).toEqual({ id: "u-inv-2", full_name: "Invoice Two" });
  });

  it("returns null for a quote-level id with no resolved profile", () => {
    expect(resolveQuoteUserDisplay("u-missing", undefined, USERS)).toBeNull();
  });

  it("skips invoice-level ids with no resolved name and joins the rest", () => {
    const result = resolveQuoteUserDisplay(
      null,
      new Set(["u-missing", "u-inv-2"]),
      USERS
    );
    expect(result?.full_name).toBe("Invoice Two");
  });
});
