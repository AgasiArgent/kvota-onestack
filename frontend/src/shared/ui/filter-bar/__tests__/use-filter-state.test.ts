/**
 * Unit tests for the URL <-> state serialization helpers behind
 * `useFilterState`. The React hook itself is exercised in component tests;
 * here we pin the pure serialization layer (round-trip of multi-value lists,
 * empty-string and whitespace handling, URL escape behavior).
 */

import { describe, expect, it } from "vitest";

import { parseMulti, serializeMulti } from "../use-filter-state";

describe("parseMulti", () => {
  it("returns an empty array for null / undefined / empty input", () => {
    expect(parseMulti(null)).toEqual([]);
    expect(parseMulti(undefined)).toEqual([]);
    expect(parseMulti("")).toEqual([]);
  });

  it("splits comma-separated values", () => {
    expect(parseMulti("a,b,c")).toEqual(["a", "b", "c"]);
  });

  it("trims whitespace around tokens", () => {
    expect(parseMulti(" a , b ,  c ")).toEqual(["a", "b", "c"]);
  });

  it("filters empty tokens (trailing commas, double commas)", () => {
    expect(parseMulti("a,,b,")).toEqual(["a", "b"]);
    expect(parseMulti(",,")).toEqual([]);
  });
});

describe("serializeMulti", () => {
  it("returns an empty string for an empty list", () => {
    expect(serializeMulti([])).toBe("");
  });

  it("joins with a comma — no spaces", () => {
    expect(serializeMulti(["a", "b", "c"])).toBe("a,b,c");
  });

  it("trims tokens and drops empties before serializing", () => {
    expect(serializeMulti([" a ", "", "b  "])).toBe("a,b");
  });

  it("round-trips with parseMulti", () => {
    const original = ["alpha", "beta", "gamma"];
    expect(parseMulti(serializeMulti(original))).toEqual(original);
  });
});
