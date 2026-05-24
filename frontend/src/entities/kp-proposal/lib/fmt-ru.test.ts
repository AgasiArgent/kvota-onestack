import { describe, it, expect } from "vitest";
import { fmtRu } from "./fmt-ru";

/**
 * Parity tests with `services/kp_export.py:_fmt_ru`.
 *
 * Note: Intl.NumberFormat("ru-RU") uses U+202F (narrow no-break space) as
 * the thousands separator — we build expected strings from that codepoint
 * explicitly so the test isn't confused with U+00A0 (NBSP) which looks
 * visually identical in many editors.
 */
const NNBSP = " ";

describe("fmtRu", () => {
  it("returns empty string for null/undefined/empty input", () => {
    expect(fmtRu(null)).toBe("");
    expect(fmtRu(undefined)).toBe("");
    expect(fmtRu("")).toBe("");
    expect(fmtRu("   ")).toBe("");
  });

  it("formats plain integer with Russian thousand separators", () => {
    expect(fmtRu("5850000")).toBe(`5${NNBSP}850${NNBSP}000`);
  });

  it("strips user-typed ASCII spaces before parsing", () => {
    expect(fmtRu("5 850 000")).toBe(`5${NNBSP}850${NNBSP}000`);
  });

  it("strips non-breaking and narrow no-break spaces in input", () => {
    expect(fmtRu(`5 850 000`)).toBe(`5${NNBSP}850${NNBSP}000`);
    expect(fmtRu(`5${NNBSP}850${NNBSP}000`)).toBe(`5${NNBSP}850${NNBSP}000`);
  });

  it("treats comma as decimal separator", () => {
    expect(fmtRu("5850,5")).toBe(`5${NNBSP}850,5`);
  });

  it("returns raw input verbatim on parse failure", () => {
    expect(fmtRu("по запросу")).toBe("по запросу");
    expect(fmtRu("abc")).toBe("abc");
  });

  it("handles decimal numbers with dot separator", () => {
    expect(fmtRu("1234.56")).toBe(`1${NNBSP}234,56`);
  });

  it("preserves negative sign", () => {
    expect(fmtRu("-1000")).toBe(`-1${NNBSP}000`);
  });
});
