import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect, vi } from "vitest";

/**
 * Phase 5d Task 12 (Agent A) — invoice-comparison-panel refactor.
 *
 * Migration 284 drops legacy supplier-side columns (invoice_id,
 * purchase_price_original, purchase_currency) from kvota.quote_items.
 *
 * This component shows per-invoice supplier positions alongside the
 * supplier scan — semantically tied to invoice_items, not quote_items.
 * The pre-Phase-5d implementation filtered quote_items by invoice_id;
 * post-5d the source is invoice_items loaded via an internal Supabase
 * call (Pattern B, same approach as invoice-card.tsx).
 *
 * These tests use the `invoiceItemsByInvoiceIdOverride` test-override
 * prop (introduced below) to inject preloaded invoice_items synchronously,
 * avoiding the async useEffect fetch under renderToString.
 */

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    from: () => ({
      select: () => ({
        in: async () => ({ data: [], error: null }),
      }),
    }),
    storage: {
      from: () => ({
        createSignedUrl: async () => ({
          data: { signedUrl: "signed-url" },
          error: null,
        }),
      }),
    },
  }),
}));

import { InvoiceComparisonPanel } from "../invoice-comparison-panel";
import type { QuoteInvoiceRow } from "@/entities/quote/queries";
import type { DocumentRow } from "../use-control-data";
import type { InvoiceItemRow } from "../invoice-comparison-panel";

function makeInvoice(overrides: Partial<QuoteInvoiceRow> = {}): QuoteInvoiceRow {
  return {
    id: "inv-A",
    invoice_number: "INV-01",
    quote_id: "q-1",
    supplier_id: "sup-1",
    supplier: { id: "sup-1", name: "Supplier A" },
    buyer_company: null,
    currency: "USD",
    pickup_city: null,
    pickup_country: null,
    total_weight_kg: null,
    total_volume_m3: null,
    status: "pending_procurement",
    ...overrides,
  } as unknown as QuoteInvoiceRow;
}

function makeInvoiceItem(overrides: Partial<InvoiceItemRow> = {}): InvoiceItemRow {
  return {
    id: "ii-1",
    invoice_id: "inv-A",
    position: 1,
    product_name: "Болт М8",
    supplier_sku: "SUP-1",
    brand: null,
    quantity: 10,
    purchase_price_original: 12.5,
    purchase_currency: "USD",
    ...overrides,
  };
}

describe("InvoiceComparisonPanel — empty state", () => {
  it("renders 'Нет инвойсов поставщиков' when invoices is empty", () => {
    const html = renderToString(
      <InvoiceComparisonPanel
        quoteId="q-1"
        invoices={[]}
        invoiceDocuments={new Map<string, DocumentRow>()}
      />
    );

    expect(html).toContain("Нет инвойсов поставщиков");
  });
});

describe("InvoiceComparisonPanel — reads invoice_items (not legacy quote_items.invoice_id)", () => {
  it("renders one button per invoice with supplier name and invoice number", () => {
    const invoices = [
      makeInvoice({ id: "inv-A", invoice_number: "INV-01" }),
      makeInvoice({
        id: "inv-B",
        invoice_number: "INV-02",
        supplier: { id: "sup-2", name: "Supplier B" },
      }),
    ];

    const html = renderToString(
      <InvoiceComparisonPanel
        quoteId="q-1"
        invoices={invoices}
        invoiceDocuments={new Map<string, DocumentRow>()}
        invoiceItemsByInvoiceIdOverride={new Map()}
      />
    );

    expect(html).toContain("INV-01");
    expect(html).toContain("INV-02");
    expect(html).toContain("Supplier A");
    expect(html).toContain("Supplier B");
  });

  it("shows position count per invoice sourced from invoice_items (not the items prop)", () => {
    const invoices = [makeInvoice({ id: "inv-A" })];
    const invoiceItemsByInvoiceId = new Map<string, InvoiceItemRow[]>([
      [
        "inv-A",
        [
          makeInvoiceItem({ id: "ii-1", quantity: 10, purchase_price_original: 12.5 }),
          makeInvoiceItem({ id: "ii-2", quantity: 5, purchase_price_original: 20 }),
        ],
      ],
    ]);

    const html = renderToString(
      <InvoiceComparisonPanel
        quoteId="q-1"
        invoices={invoices}
        invoiceDocuments={new Map<string, DocumentRow>()}
        invoiceItemsByInvoiceIdOverride={invoiceItemsByInvoiceId}
      />
    );

    // React inserts a comment between {count} and " поз." when rendering.
    expect(html).toMatch(/2(<!--\s*-->)?\s*поз\./);
    // total = 10*12.5 + 5*20 = 125 + 100 = 225.00
    expect(html).toContain("225,00");
  });

  it("shows 'Нет скана' badge when no document for invoice", () => {
    const invoices = [makeInvoice({ id: "inv-A" })];

    const html = renderToString(
      <InvoiceComparisonPanel
        quoteId="q-1"
        invoices={invoices}
        invoiceDocuments={new Map<string, DocumentRow>()}
        invoiceItemsByInvoiceIdOverride={new Map()}
      />
    );

    expect(html).toContain("Нет скана");
  });

  it("shows 'Скан загружен' badge when document present for invoice", () => {
    const invoices = [makeInvoice({ id: "inv-A" })];
    const invoiceDocuments = new Map<string, DocumentRow>([
      [
        "inv-A",
        {
          id: "doc-1",
          entity_id: "inv-A",
          storage_path: "documents/inv-A.pdf",
          original_filename: "scan.pdf",
          mime_type: "application/pdf",
        },
      ],
    ]);

    const html = renderToString(
      <InvoiceComparisonPanel
        quoteId="q-1"
        invoices={invoices}
        invoiceDocuments={invoiceDocuments}
        invoiceItemsByInvoiceIdOverride={new Map()}
      />
    );

    expect(html).toContain("Скан загружен");
  });
});
