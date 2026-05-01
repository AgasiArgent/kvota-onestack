import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";

/**
 * Tests for the inline merge UX (per-row trigger replacing the legacy
 * top-level MergeModal). Same SSR caveat as split: @base-ui's Dialog
 * Portal is omitted during SSR, so we cover:
 *
 *   - the pure validation helpers (isValidMergeForm, isPartnerSelected),
 *     which encode the new tightened rules: brand + supplier_sku required,
 *     ≥1 partner selected, price > 0
 *   - SSR sanity: module loads cleanly and closed-state component renders
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
  mergeInvoiceItems: vi.fn(async () => undefined),
}));

import {
  MergeInlineDialog,
  isValidMergeForm,
  isPartnerSelected,
  type MergeFormState,
} from "../merge-inline-dialog";

function makeState(overrides: Partial<MergeFormState> = {}): MergeFormState {
  return {
    product_name: "Болт M8",
    brand: "ABB",
    supplier_sku: "SUP-1",
    purchase_price_original: "12.5",
    selectedPartnerIds: new Set(["ii-2"]),
    ...overrides,
  };
}

describe("isPartnerSelected", () => {
  it("returns true when invoice_item id is in the set", () => {
    const state = makeState({ selectedPartnerIds: new Set(["ii-1", "ii-2"]) });
    expect(isPartnerSelected(state, "ii-1")).toBe(true);
    expect(isPartnerSelected(state, "ii-2")).toBe(true);
  });

  it("returns false when invoice_item id is not in the set", () => {
    const state = makeState({ selectedPartnerIds: new Set(["ii-1"]) });
    expect(isPartnerSelected(state, "ii-99")).toBe(false);
  });

  it("returns false on empty set", () => {
    const state = makeState({ selectedPartnerIds: new Set() });
    expect(isPartnerSelected(state, "ii-1")).toBe(false);
  });
});

describe("isValidMergeForm — newly tightened rules", () => {
  it("accepts a complete state with at least one partner selected", () => {
    expect(isValidMergeForm(makeState())).toBe(true);
  });

  it("rejects when no partners are selected", () => {
    expect(isValidMergeForm(makeState({ selectedPartnerIds: new Set() }))).toBe(
      false
    );
  });

  it("rejects when product_name is blank", () => {
    expect(isValidMergeForm(makeState({ product_name: "" }))).toBe(false);
    expect(isValidMergeForm(makeState({ product_name: "   " }))).toBe(false);
  });

  it("rejects when brand is blank (newly required)", () => {
    expect(isValidMergeForm(makeState({ brand: "" }))).toBe(false);
    expect(isValidMergeForm(makeState({ brand: "  " }))).toBe(false);
  });

  it("rejects when supplier_sku is blank (newly required)", () => {
    expect(isValidMergeForm(makeState({ supplier_sku: "" }))).toBe(false);
    expect(isValidMergeForm(makeState({ supplier_sku: "  " }))).toBe(false);
  });

  it("rejects non-positive prices", () => {
    expect(
      isValidMergeForm(makeState({ purchase_price_original: "0" }))
    ).toBe(false);
    expect(
      isValidMergeForm(makeState({ purchase_price_original: "-1" }))
    ).toBe(false);
    expect(
      isValidMergeForm(makeState({ purchase_price_original: "abc" }))
    ).toBe(false);
    expect(
      isValidMergeForm(makeState({ purchase_price_original: "" }))
    ).toBe(false);
  });

  it("accepts when 2+ partners are selected", () => {
    const state = makeState({
      selectedPartnerIds: new Set(["ii-2", "ii-3", "ii-4"]),
    });
    expect(isValidMergeForm(state)).toBe(true);
  });
});

describe("MergeInlineDialog — module + closed-state SSR sanity", () => {
  it("exports as a function", () => {
    expect(typeof MergeInlineDialog).toBe("function");
  });

  it("renders without throwing when open=false (Portal omitted during SSR)", () => {
    const html = renderToString(
      <MergeInlineDialog
        open={false}
        onClose={() => {}}
        invoiceId="inv-1"
        initiatorInvoiceItemId="ii-1"
        initiatorSourceQuoteItemId="qi-1"
        initiatorQuantity={100}
        candidates={[]}
        currency="USD"
        defaults={{
          product_name: "Болт M8",
          brand: "ABB",
          supplier_sku: "SUP-1",
          purchase_price_original: 10,
        }}
      />
    );
    expect(typeof html).toBe("string");
  });
});
