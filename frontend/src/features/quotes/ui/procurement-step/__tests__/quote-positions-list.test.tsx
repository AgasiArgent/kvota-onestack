import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect, vi } from "vitest";

// next/navigation's useRouter has no App Router context during SSR tests.
// Mock it to return a no-op object — the component only calls router.refresh()
// inside async handlers that never fire during an initial renderToString.
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

// Supabase client is constructed inside the useEffect-fetched coverage path.
// The component never hits it when coverageByQuoteItem is provided as prop,
// but SSR still evaluates module top-level — stub to avoid env var reads.
vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    from: () => ({
      select: () => ({ in: async () => ({ data: [], error: null }) }),
    }),
  }),
}));

import { QuotePositionsList } from "../quote-positions-list";
import type { QuoteItemRow, QuoteInvoiceRow } from "@/entities/quote/queries";

/**
 * QuotePositionsList is the non-destructive replacement for UnassignedItems
 * (Phase 5c Task 9). It renders ALL quote_items regardless of whether they
 * are covered in any invoice, shows a "В КП" chip column listing every
 * invoice that currently covers the item via invoice_item_coverage, and
 * offers a "Назначить в КП" dropdown that lists all sibling invoices plus
 * "➕ Создать новый КП".
 *
 * Browser-environment (no DOM in vitest) tests are asserted via SSR against
 * the initial render string — identical pattern to CountryCombobox tests.
 */

function makeItem(overrides: Partial<QuoteItemRow> = {}): QuoteItemRow {
  return {
    id: "qi-1",
    quote_id: "q-1",
    product_name: "Болт М8",
    brand: "ABB",
    product_code: "SKU-1",
    quantity: 100,
    composition_selected_invoice_id: null,
    is_unavailable: false,
    position: 1,
    ...overrides,
  } as QuoteItemRow;
}

function makeInvoice(overrides: Partial<QuoteInvoiceRow> = {}): QuoteInvoiceRow {
  return {
    id: "inv-A",
    invoice_number: "INV-01-Q-202604-0001",
    quote_id: "q-1",
    supplier_id: "sup-1",
    supplier: { id: "sup-1", name: "Supplier A" },
    buyer_company: null,
    sent_at: null,
    status: "pending_procurement",
    currency: "USD",
    pickup_city: null,
    pickup_country: null,
    pickup_country_code: null,
    supplier_incoterms: null,
    total_weight_kg: null,
    total_volume_m3: null,
    ...overrides,
  } as unknown as QuoteInvoiceRow;
}

describe("QuotePositionsList — rendering", () => {
  it("renders ALL quote_items regardless of coverage status (does not filter by invoice_id)", () => {
    // Phase 5d: invoice_id is no longer on quote_items — the field moved
    // to invoice_items with an invoice_item_coverage join. The test now
    // only asserts that all three quote_items render regardless of
    // coverage, which is what the component contract guarantees.
    const items = [
      makeItem({ id: "qi-1", product_name: "Болт" }),
      makeItem({
        id: "qi-2",
        product_name: "Гайка",
      }),
      makeItem({
        id: "qi-3",
        product_name: "Шайба",
        composition_selected_invoice_id: "inv-B",
      }),
    ];
    const invoices = [makeInvoice()];

    const html = renderToString(
      <QuotePositionsList
        items={items}
        invoices={invoices}
        coverageByQuoteItem={{}}
      />
    );

    expect(html).toContain("Болт");
    expect(html).toContain("Гайка");
    expect(html).toContain("Шайба");
  });

  it("displays the 'Позиции заявки' header with total item count (not 'Нераспределённые')", () => {
    const items = [
      makeItem({ id: "qi-1" }),
      makeItem({ id: "qi-2" }),
      makeItem({ id: "qi-3" }),
    ];

    const html = renderToString(
      <QuotePositionsList
        items={items}
        invoices={[]}
        coverageByQuoteItem={{}}
      />
    );

    expect(html).toContain("Позиции заявки");
    // React SSR interleaves <!-- --> markers between text and state; match
    // the entire line loosely with a regex instead of literal "(3)".
    expect(html).toMatch(/Позиции заявки.*3/);
    expect(html).not.toContain("Нераспределённые");
  });

  it("renders a 'В КП' chip with invoice_number for each covering invoice", () => {
    const items = [makeItem({ id: "qi-1" })];
    const invoices = [
      makeInvoice({ id: "inv-A", invoice_number: "INV-01-Q" }),
      makeInvoice({ id: "inv-B", invoice_number: "INV-02-Q" }),
    ];
    const coverageByQuoteItem = {
      "qi-1": [
        { invoice_id: "inv-A", invoice_number: "INV-01-Q" },
        { invoice_id: "inv-B", invoice_number: "INV-02-Q" },
      ],
    };

    const html = renderToString(
      <QuotePositionsList
        items={items}
        invoices={invoices}
        coverageByQuoteItem={coverageByQuoteItem}
      />
    );

    expect(html).toContain("INV-01-Q");
    expect(html).toContain("INV-02-Q");
  });

  it("renders an empty 'В КП' cell (em-dash) when the quote_item has no coverage", () => {
    const items = [makeItem({ id: "qi-uncovered" })];

    const html = renderToString(
      <QuotePositionsList
        items={items}
        invoices={[]}
        coverageByQuoteItem={{}}
      />
    );

    // Uncovered row emits an em-dash placeholder for the В КП column
    expect(html).toContain("\u2014");
  });

  it("renders one <tr> per quote_item (never filters hidden/covered items)", () => {
    const items = [
      makeItem({ id: "qi-1" }),
      makeItem({ id: "qi-2" }),
      makeItem({ id: "qi-3" }),
    ];

    const html = renderToString(
      <QuotePositionsList
        items={items}
        invoices={[makeInvoice()]}
        coverageByQuoteItem={{}}
      />
    );

    // Three <tr> rows inside <tbody> (checkbox is in <thead>, plus 3 body rows = 4 total)
    const trMatches = html.match(/<tr\b/g) ?? [];
    expect(trMatches.length).toBe(4);
  });
});

describe("QuotePositionsList — does NOT auto-hide when everything is covered", () => {
  it("still renders when every item is covered (non-destructive — always visible)", () => {
    const items = [makeItem({ id: "qi-1" }), makeItem({ id: "qi-2" })];
    const invoices = [makeInvoice({ id: "inv-A" })];

    const html = renderToString(
      <QuotePositionsList
        items={items}
        invoices={invoices}
        coverageByQuoteItem={{
          "qi-1": [{ invoice_id: "inv-A", invoice_number: "INV-01" }],
          "qi-2": [{ invoice_id: "inv-A", invoice_number: "INV-01" }],
        }}
      />
    );

    // With UnassignedItems, this returned null. QuotePositionsList always renders.
    expect(html).toContain("Позиции заявки");
  });
});
