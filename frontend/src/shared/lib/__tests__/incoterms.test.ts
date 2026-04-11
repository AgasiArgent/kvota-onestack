import { describe, it, expect } from "vitest";
import { INCOTERMS_2020, isValidIncoterm } from "../incoterms";

describe("INCOTERMS_2020", () => {
  it("contains exactly 11 entries", () => {
    expect(INCOTERMS_2020.length).toBe(11);
  });

  it("contains all 11 standard Incoterms 2020 codes in conventional order", () => {
    const expectedCodes = [
      "EXW",
      "FCA",
      "CPT",
      "CIP",
      "DAP",
      "DPU",
      "DDP",
      "FAS",
      "FOB",
      "CFR",
      "CIF",
    ];
    const actualCodes = INCOTERMS_2020.map((i) => i.code);
    expect(actualCodes).toEqual(expectedCodes);
  });

  it("every entry has a non-empty label", () => {
    for (const term of INCOTERMS_2020) {
      expect(term.label).toBeTruthy();
      expect(typeof term.label).toBe("string");
    }
  });
});

describe("isValidIncoterm", () => {
  it("returns true for an exact uppercase code", () => {
    expect(isValidIncoterm("DDP")).toBe(true);
  });

  it("is case-insensitive", () => {
    expect(isValidIncoterm("ddp")).toBe(true);
  });

  it("trims surrounding whitespace", () => {
    expect(isValidIncoterm(" DDP ")).toBe(true);
  });

  it("returns false for an unknown code", () => {
    expect(isValidIncoterm("XXX")).toBe(false);
  });

  it("returns false for an empty string", () => {
    expect(isValidIncoterm("")).toBe(false);
  });

  it("returns false for null", () => {
    expect(isValidIncoterm(null)).toBe(false);
  });

  it("returns false for undefined", () => {
    expect(isValidIncoterm(undefined)).toBe(false);
  });
});
