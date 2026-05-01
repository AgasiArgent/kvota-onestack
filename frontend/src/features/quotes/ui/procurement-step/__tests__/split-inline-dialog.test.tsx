import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";

/**
 * Tests for the inline split UX (per-row trigger replacing the legacy
 * top-level SplitModal). The dialog body is dynamically portalled by
 * @base-ui's Dialog and skipped during SSR, so we can't assert on the
 * inputs directly here. Instead, we cover:
 *
 *   - the pure validation helpers (isValidSplitChild, isSplitFormValid,
 *     computeChildQuantity), which encode the new tightened rules
 *     (brand + supplier_sku now required) and the dropped fields
 *     (currency / weight / customs_code / volume — no longer in the form)
 *   - SSR sanity: the closed-state component exports cleanly and renders
 *     without throwing.
 */

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    refresh: () => {},
    push: () => {},
    replace: () => {},
    back: () => {},
    forward: () => {},
    prefetch: () => {},
  }),
}));

vi.mock("@/entities/quote/mutations", () => ({
  splitInvoiceItem: vi.fn(async () => undefined),
}));

import {
  SplitInlineDialog,
  computeChildQuantity,
  isValidSplitChild,
  isSplitFormValid,
  type SplitChildFormState,
} from "../split-inline-dialog";

function makeChild(overrides: Partial<SplitChildFormState> = {}): SplitChildFormState {
  return {
    product_name: "Болт M8",
    brand: "ABB",
    supplier_sku: "SUP-1",
    quantity_ratio: "1",
    purchase_price_original: "10.5",
    ...overrides,
  };
}

describe("computeChildQuantity", () => {
  it("multiplies source quantity by ratio", () => {
    expect(computeChildQuantity(100, 0.5)).toBe(50);
    expect(computeChildQuantity(20, 2)).toBe(40);
  });

  it("returns 0 for non-finite or non-positive ratios", () => {
    expect(computeChildQuantity(100, NaN)).toBe(0);
    expect(computeChildQuantity(100, 0)).toBe(0);
    expect(computeChildQuantity(100, -1)).toBe(0);
    expect(computeChildQuantity(100, Infinity)).toBe(0);
  });
});

describe("isValidSplitChild — tightened required-field rules", () => {
  it("accepts a complete child", () => {
    expect(isValidSplitChild(makeChild())).toBe(true);
  });

  it("rejects when product_name is blank", () => {
    expect(isValidSplitChild(makeChild({ product_name: "" }))).toBe(false);
    expect(isValidSplitChild(makeChild({ product_name: "   " }))).toBe(false);
  });

  it("rejects when brand is blank (newly required)", () => {
    // Old SplitModal allowed empty brand; new dialog tightens this to required.
    expect(isValidSplitChild(makeChild({ brand: "" }))).toBe(false);
    expect(isValidSplitChild(makeChild({ brand: "   " }))).toBe(false);
  });

  it("rejects when supplier_sku is blank (newly required)", () => {
    // Same tightening: supplier_sku is now mandatory.
    expect(isValidSplitChild(makeChild({ supplier_sku: "" }))).toBe(false);
    expect(isValidSplitChild(makeChild({ supplier_sku: "   " }))).toBe(false);
  });

  it("rejects non-positive ratios", () => {
    expect(isValidSplitChild(makeChild({ quantity_ratio: "0" }))).toBe(false);
    expect(isValidSplitChild(makeChild({ quantity_ratio: "-1" }))).toBe(false);
    expect(isValidSplitChild(makeChild({ quantity_ratio: "abc" }))).toBe(false);
  });

  it("rejects non-positive prices", () => {
    expect(isValidSplitChild(makeChild({ purchase_price_original: "0" }))).toBe(
      false
    );
    expect(
      isValidSplitChild(makeChild({ purchase_price_original: "-5" }))
    ).toBe(false);
    expect(isValidSplitChild(makeChild({ purchase_price_original: "" }))).toBe(
      false
    );
  });
});

describe("isSplitFormValid", () => {
  it("requires at least 2 children", () => {
    expect(isSplitFormValid([makeChild()])).toBe(false);
    expect(isSplitFormValid([makeChild(), makeChild()])).toBe(true);
  });

  it("returns false if any child fails validation", () => {
    expect(
      isSplitFormValid([makeChild(), makeChild({ brand: "" })])
    ).toBe(false);
    expect(
      isSplitFormValid([makeChild(), makeChild({ supplier_sku: "" })])
    ).toBe(false);
  });

  it("supports 3 children when all valid", () => {
    expect(
      isSplitFormValid([makeChild(), makeChild(), makeChild()])
    ).toBe(true);
  });
});

describe("SplitInlineDialog — module + closed-state SSR sanity", () => {
  it("exports as a function", () => {
    expect(typeof SplitInlineDialog).toBe("function");
  });

  it("renders without throwing when open=false (Portal omitted during SSR)", () => {
    const html = renderToString(
      <SplitInlineDialog
        open={false}
        onClose={() => {}}
        invoiceId="inv-1"
        sourceQuoteItemId="qi-1"
        sourceQuantity={100}
        sourceProductName="Болт M8"
        currency="USD"
      />
    );
    expect(typeof html).toBe("string");
  });
});
