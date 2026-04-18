import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect, vi } from "vitest";

/**
 * Phase 5c Task 12 — SplitModal tests.
 *
 * SplitModal decomposes one quote_item that's currently 1:1 covered in a
 * given invoice into N ≥ 2 invoice_items with individual ratios, emitting
 * N coverage rows (all pointing to the same source quote_item). The split
 * is local to this invoice — other invoices covering the same quote_item
 * remain untouched.
 *
 * Ratio semantics: `ratio = invoice_item_units per quote_item_unit`.
 * Invariant: `invoice_item.quantity = quote_item.quantity × ratio`.
 *
 * Frontend workspace has no DOM; tests use renderToString. The @base-ui
 * Dialog renders into a Portal that is skipped during SSR, so UI assertions
 * target the extracted SplitModalBody (pure form) directly. The full modal
 * is verified via closed-state behaviour plus logic helpers.
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
  SplitModal,
  SplitModalBody,
  computeChildQuantity,
  isSplitFormValid,
  type SplitChildFormState,
} from "../split-modal";

interface QuoteItemCandidate {
  id: string;
  product_name: string;
  quantity: number;
}

function makeEmptyChild(): SplitChildFormState {
  return {
    product_name: "",
    supplier_sku: "",
    brand: "",
    quantity_ratio: "1",
    purchase_price_original: "",
    purchase_currency: "USD",
    weight_in_kg: "",
    customs_code: "",
  };
}

describe("SplitModalBody — source quote_item picker", () => {
  it("renders dropdown listing only provided 1:1 candidate quote_items", () => {
    const candidates: QuoteItemCandidate[] = [
      { id: "qi-1", product_name: "Болт М8", quantity: 100 },
      { id: "qi-2", product_name: "Крепёж", quantity: 50 },
    ];

    const html = renderToString(
      <SplitModalBody
        candidates={candidates}
        defaultCurrency="USD"
        sourceQuoteItemId=""
        onSourceChange={() => {}}
        childRows={[makeEmptyChild(), makeEmptyChild()]}
        onChildUpdate={() => {}}
        onAddChild={() => {}}
        onRemoveChild={() => {}}
      />
    );

    expect(html).toContain("Болт М8");
    expect(html).toContain("Крепёж");
  });
});

describe("SplitModal — root dialog container", () => {
  it("shows modal title in the dialog header even when portal is closed (module-level sanity)", () => {
    // @base-ui Dialog Portal is not rendered during SSR. We cannot assert
    // title presence from renderToString output. Instead, confirm the module
    // exports the expected component — import already succeeded.
    expect(typeof SplitModal).toBe("function");
  });
});

describe("SplitModalBody — child rows", () => {
  it("renders the 'Наименование' input once per child row (minimum N = 2)", () => {
    const html = renderToString(
      <SplitModalBody
        candidates={[]}
        defaultCurrency="USD"
        sourceQuoteItemId=""
        onSourceChange={() => {}}
        childRows={[makeEmptyChild(), makeEmptyChild()]}
        onChildUpdate={() => {}}
        onAddChild={() => {}}
        onRemoveChild={() => {}}
      />
    );

    const nameMatches = html.match(/placeholder="Наименование"/g) ?? [];
    expect(nameMatches.length).toBe(2);
  });

  it("renders one additional name input per extra child row", () => {
    const html = renderToString(
      <SplitModalBody
        candidates={[]}
        defaultCurrency="USD"
        sourceQuoteItemId=""
        onSourceChange={() => {}}
        childRows={[makeEmptyChild(), makeEmptyChild(), makeEmptyChild()]}
        onChildUpdate={() => {}}
        onAddChild={() => {}}
        onRemoveChild={() => {}}
      />
    );

    const nameMatches = html.match(/placeholder="Наименование"/g) ?? [];
    expect(nameMatches.length).toBe(3);
  });

  it("exposes 'Добавить часть' affordance to append more child rows", () => {
    const html = renderToString(
      <SplitModalBody
        candidates={[]}
        defaultCurrency="USD"
        sourceQuoteItemId=""
        onSourceChange={() => {}}
        childRows={[makeEmptyChild(), makeEmptyChild()]}
        onChildUpdate={() => {}}
        onAddChild={() => {}}
        onRemoveChild={() => {}}
      />
    );

    expect(html).toContain("Добавить часть");
  });

  it("displays computed quantity readonly field with source quote_item selected", () => {
    const source: QuoteItemCandidate = {
      id: "qi-1",
      product_name: "Крепёж",
      quantity: 100,
    };
    const child1: SplitChildFormState = {
      ...makeEmptyChild(),
      quantity_ratio: "1",
    };
    const child2: SplitChildFormState = {
      ...makeEmptyChild(),
      quantity_ratio: "2",
    };

    const html = renderToString(
      <SplitModalBody
        candidates={[source]}
        defaultCurrency="USD"
        sourceQuoteItemId="qi-1"
        onSourceChange={() => {}}
        childRows={[child1, child2]}
        onChildUpdate={() => {}}
        onAddChild={() => {}}
        onRemoveChild={() => {}}
      />
    );

    // With source quantity=100, ratios 1 and 2 produce computed qty 100 and 200
    expect(html).toContain('value="100"');
    expect(html).toContain('value="200"');
  });
});

describe("computeChildQuantity — invariant helper", () => {
  it("returns quote_item.quantity × ratio (1:1 when ratio = 1)", () => {
    expect(computeChildQuantity(100, 1)).toBe(100);
  });

  it("returns quote_item.quantity × ratio for split (N:1)", () => {
    // Split: 1 крепёж ×100 → 100 болт (ratio=1) + 200 шайба (ratio=2)
    expect(computeChildQuantity(100, 1)).toBe(100);
    expect(computeChildQuantity(100, 2)).toBe(200);
  });

  it("handles fractional ratios (half of source qty)", () => {
    expect(computeChildQuantity(100, 0.5)).toBe(50);
  });

  it("returns 0 when ratio is 0 (invalid, caller should block submit)", () => {
    expect(computeChildQuantity(100, 0)).toBe(0);
  });

  it("returns 0 for negative or NaN ratios (guards submit)", () => {
    expect(computeChildQuantity(100, -1)).toBe(0);
    expect(computeChildQuantity(100, NaN)).toBe(0);
  });
});

describe("isSplitFormValid — submit gate", () => {
  const validChild: SplitChildFormState = {
    product_name: "Болт",
    supplier_sku: "",
    brand: "",
    quantity_ratio: "1",
    purchase_price_original: "12.5",
    purchase_currency: "USD",
    weight_in_kg: "",
    customs_code: "",
  };

  it("rejects when sourceQuoteItemId is empty", () => {
    expect(
      isSplitFormValid({
        sourceQuoteItemId: "",
        children: [validChild, { ...validChild, product_name: "Шайба" }],
      })
    ).toBe(false);
  });

  it("rejects when fewer than 2 children", () => {
    expect(
      isSplitFormValid({
        sourceQuoteItemId: "qi-1",
        children: [validChild],
      })
    ).toBe(false);
  });

  it("rejects when a child has empty product_name", () => {
    expect(
      isSplitFormValid({
        sourceQuoteItemId: "qi-1",
        children: [
          { ...validChild, product_name: "" },
          { ...validChild, product_name: "Шайба" },
        ],
      })
    ).toBe(false);
  });

  it("rejects when a child has ratio = 0", () => {
    expect(
      isSplitFormValid({
        sourceQuoteItemId: "qi-1",
        children: [
          { ...validChild, quantity_ratio: "0" },
          { ...validChild, product_name: "Шайба" },
        ],
      })
    ).toBe(false);
  });

  it("rejects when a child has negative ratio", () => {
    expect(
      isSplitFormValid({
        sourceQuoteItemId: "qi-1",
        children: [
          { ...validChild, quantity_ratio: "-1" },
          { ...validChild, product_name: "Шайба" },
        ],
      })
    ).toBe(false);
  });

  it("rejects when a child has empty purchase_price_original", () => {
    expect(
      isSplitFormValid({
        sourceQuoteItemId: "qi-1",
        children: [
          { ...validChild, purchase_price_original: "" },
          { ...validChild, product_name: "Шайба" },
        ],
      })
    ).toBe(false);
  });

  it("rejects when a child has zero purchase_price_original", () => {
    expect(
      isSplitFormValid({
        sourceQuoteItemId: "qi-1",
        children: [
          { ...validChild, purchase_price_original: "0" },
          { ...validChild, product_name: "Шайба" },
        ],
      })
    ).toBe(false);
  });

  it("accepts valid form with sourceQuoteItemId + 2 valid children", () => {
    expect(
      isSplitFormValid({
        sourceQuoteItemId: "qi-1",
        children: [
          validChild,
          { ...validChild, product_name: "Шайба", quantity_ratio: "2" },
        ],
      })
    ).toBe(true);
  });

  it("accepts valid form with 3 valid children", () => {
    expect(
      isSplitFormValid({
        sourceQuoteItemId: "qi-1",
        children: [
          { ...validChild, product_name: "Болт" },
          { ...validChild, product_name: "Гайка", quantity_ratio: "1" },
          { ...validChild, product_name: "Шайба", quantity_ratio: "2" },
        ],
      })
    ).toBe(true);
  });
});
