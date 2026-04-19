import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect, vi } from "vitest";

/**
 * Phase 5c Task 13 — MergeModal tests.
 *
 * MergeModal consolidates N ≥ 2 quote_items (each currently 1:1 covered in
 * this invoice) into one merged invoice_item with N coverage rows (all
 * ratio=1). The merge is local to the invoice — coverage in other invoices
 * for the same quote_items is untouched.
 *
 * Blocked: a quote_item that's already part of a split or existing merge
 * (ratio != 1 or its covering invoice_item covers multiple quote_items).
 * These are filtered out of `candidates` by the caller (invoice-card
 * computes the 1:1-only set).
 *
 * Same SSR caveat as SplitModal: @base-ui Dialog uses a Portal omitted in
 * SSR, so UI tests target the extracted MergeModalBody directly.
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

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    from: () => ({
      select: () => ({ eq: () => ({ in: async () => ({ data: [], error: null }) }) }),
    }),
    auth: { getSession: async () => ({ data: { session: null } }) },
  }),
}));

import {
  MergeModal,
  MergeModalBody,
  defaultMergeQuantity,
  isMergeFormValid,
  type MergeFormState,
} from "../merge-modal";

interface QuoteItemCandidate {
  id: string;
  product_name: string;
  quantity: number;
}

describe("MergeModalBody — source multi-select", () => {
  it("renders one checkbox per 1:1 candidate quote_item", () => {
    const candidates: QuoteItemCandidate[] = [
      { id: "qi-1", product_name: "Болт", quantity: 100 },
      { id: "qi-2", product_name: "Гайка", quantity: 100 },
      { id: "qi-3", product_name: "Шайба", quantity: 100 },
    ];

    const html = renderToString(
      <MergeModalBody
        candidates={candidates}
        selectedQuoteItemIds={new Set()}
        onToggle={() => {}}
        merged={{
          product_name: "",
          supplier_sku: "",
          brand: "",
          quantity: "",
          purchase_price_original: "",
          purchase_currency: "USD",
          weight_in_kg: "",
          customs_code: "",
        }}
        onMergedChange={() => {}}
      />
    );

    expect(html).toContain("Болт");
    expect(html).toContain("Гайка");
    expect(html).toContain("Шайба");
  });

  it("shows quantity next to each candidate for context", () => {
    const candidates: QuoteItemCandidate[] = [
      { id: "qi-1", product_name: "Болт", quantity: 100 },
      { id: "qi-2", product_name: "Гайка", quantity: 50 },
    ];

    const html = renderToString(
      <MergeModalBody
        candidates={candidates}
        selectedQuoteItemIds={new Set()}
        onToggle={() => {}}
        merged={{
          product_name: "",
          supplier_sku: "",
          brand: "",
          quantity: "",
          purchase_price_original: "",
          purchase_currency: "USD",
          weight_in_kg: "",
          customs_code: "",
        }}
        onMergedChange={() => {}}
      />
    );

    expect(html).toMatch(/100/);
    expect(html).toMatch(/50/);
  });

  it("renders merged row form fields (product_name, price, currency)", () => {
    const html = renderToString(
      <MergeModalBody
        candidates={[]}
        selectedQuoteItemIds={new Set()}
        onToggle={() => {}}
        merged={{
          product_name: "",
          supplier_sku: "",
          brand: "",
          quantity: "",
          purchase_price_original: "",
          purchase_currency: "USD",
          weight_in_kg: "",
          customs_code: "",
        }}
        onMergedChange={() => {}}
      />
    );

    expect(html).toContain('placeholder="Наименование"');
    expect(html).toContain("Цена закупки");
    expect(html).toContain("Валюта");
  });
});

describe("MergeModal — root dialog container", () => {
  it("module exports the expected component (SSR portal not rendered)", () => {
    // @base-ui Dialog Portal is not rendered during SSR. Confirm the module
    // provides MergeModal as a function.
    expect(typeof MergeModal).toBe("function");
  });
});

describe("defaultMergeQuantity — max of source quote_items' quantities", () => {
  it("returns the max quantity across source quote_items", () => {
    expect(
      defaultMergeQuantity([
        { id: "qi-1", product_name: "Болт", quantity: 100 },
        { id: "qi-2", product_name: "Гайка", quantity: 50 },
        { id: "qi-3", product_name: "Шайба", quantity: 200 },
      ])
    ).toBe(200);
  });

  it("returns the single quantity when only one is given", () => {
    expect(
      defaultMergeQuantity([{ id: "qi-1", product_name: "Болт", quantity: 42 }])
    ).toBe(42);
  });

  it("returns 0 for empty array", () => {
    expect(defaultMergeQuantity([])).toBe(0);
  });
});

describe("isMergeFormValid — submit gate", () => {
  const validMerged: MergeFormState = {
    product_name: "Крепёж",
    supplier_sku: "",
    brand: "",
    quantity: "100",
    purchase_price_original: "12.5",
    purchase_currency: "USD",
    weight_in_kg: "",
    customs_code: "",
  };

  it("rejects when fewer than 2 quote_items selected", () => {
    expect(
      isMergeFormValid({
        selectedQuoteItemIds: new Set(["qi-1"]),
        merged: validMerged,
      })
    ).toBe(false);
  });

  it("rejects when zero quote_items selected", () => {
    expect(
      isMergeFormValid({
        selectedQuoteItemIds: new Set<string>(),
        merged: validMerged,
      })
    ).toBe(false);
  });

  it("rejects when product_name is empty", () => {
    expect(
      isMergeFormValid({
        selectedQuoteItemIds: new Set(["qi-1", "qi-2"]),
        merged: { ...validMerged, product_name: "" },
      })
    ).toBe(false);
  });

  it("rejects when quantity is empty or non-positive", () => {
    expect(
      isMergeFormValid({
        selectedQuoteItemIds: new Set(["qi-1", "qi-2"]),
        merged: { ...validMerged, quantity: "" },
      })
    ).toBe(false);
    expect(
      isMergeFormValid({
        selectedQuoteItemIds: new Set(["qi-1", "qi-2"]),
        merged: { ...validMerged, quantity: "0" },
      })
    ).toBe(false);
    expect(
      isMergeFormValid({
        selectedQuoteItemIds: new Set(["qi-1", "qi-2"]),
        merged: { ...validMerged, quantity: "-5" },
      })
    ).toBe(false);
  });

  it("rejects when purchase_price_original is empty", () => {
    expect(
      isMergeFormValid({
        selectedQuoteItemIds: new Set(["qi-1", "qi-2"]),
        merged: { ...validMerged, purchase_price_original: "" },
      })
    ).toBe(false);
  });

  it("rejects when purchase_price_original is zero", () => {
    expect(
      isMergeFormValid({
        selectedQuoteItemIds: new Set(["qi-1", "qi-2"]),
        merged: { ...validMerged, purchase_price_original: "0" },
      })
    ).toBe(false);
  });

  it("accepts valid form with ≥2 sources + product_name + price + quantity", () => {
    expect(
      isMergeFormValid({
        selectedQuoteItemIds: new Set(["qi-1", "qi-2"]),
        merged: validMerged,
      })
    ).toBe(true);
  });

  it("accepts valid form with 3 selected sources", () => {
    expect(
      isMergeFormValid({
        selectedQuoteItemIds: new Set(["qi-1", "qi-2", "qi-3"]),
        merged: validMerged,
      })
    ).toBe(true);
  });
});
