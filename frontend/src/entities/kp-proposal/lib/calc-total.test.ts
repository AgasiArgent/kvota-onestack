import { describe, it, expect } from "vitest";
import { calcRowTotal, calcGrandTotal } from "./calc-total";
import type { KpItem } from "../model/types";

function item(qty: string, price: string): KpItem {
  return { name: "", model: "", qty, price };
}

describe("calcRowTotal", () => {
  it("multiplies parsed qty and price", () => {
    expect(calcRowTotal(item("2", "1500"))).toBe(3000);
  });

  it("strips spaces in numeric strings", () => {
    expect(calcRowTotal(item("1", "5 850 000"))).toBe(5_850_000);
  });

  it("returns null when qty is non-numeric", () => {
    expect(calcRowTotal(item("two", "1000"))).toBeNull();
  });

  it("returns null when price is non-numeric", () => {
    expect(calcRowTotal(item("1", "по запросу"))).toBeNull();
  });

  it("returns null on empty fields", () => {
    expect(calcRowTotal(item("", "1000"))).toBeNull();
    expect(calcRowTotal(item("1", ""))).toBeNull();
    expect(calcRowTotal(item("", ""))).toBeNull();
  });

  it("accepts comma as decimal separator", () => {
    expect(calcRowTotal(item("1", "10,5"))).toBe(10.5);
  });
});

describe("calcGrandTotal", () => {
  it("sums valid rows and ignores invalid ones", () => {
    const items: KpItem[] = [
      item("1", "5 850 000"),
      item("1", "6 630 000"),
      item("", ""), // empty placeholder row — contributes 0
      item("по запросу", "1000"), // unparseable qty — contributes 0
    ];
    expect(calcGrandTotal(items)).toBe(12_480_000);
  });

  it("returns 0 for an empty list", () => {
    expect(calcGrandTotal([])).toBe(0);
  });

  it("returns 0 when no row has both qty and price", () => {
    expect(
      calcGrandTotal([item("", ""), item("abc", "def"), item("1", "")]),
    ).toBe(0);
  });
});
