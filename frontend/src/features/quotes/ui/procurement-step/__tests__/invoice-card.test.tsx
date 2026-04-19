import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect, vi } from "vitest";

/**
 * Phase 5c Task 11 — invoice-card rewrite tests.
 *
 * Verifies:
 *   - Items list rendered from invoice_items (not the legacy
 *     quote_items.invoice_id filter)
 *   - Each row shows coverage summary (split, merge, or nothing for 1:1)
 *   - isSent → isLocked rename (derived from quote.procurement_completed_at)
 *   - Green "Отправлено [date]" badge kept as informational metadata when
 *     invoice.sent_at != null (no lock effect)
 *   - Regression guard: sent_at != null AND procurement_completed_at == null
 *     → edit actions enabled (Phase 4a semantics removal)
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
      select: () => ({
        eq: () => ({
          order: () => ({
            select: async () => ({ data: [], error: null }),
          }),
        }),
        in: async () => ({ data: [], error: null }),
      }),
    }),
  }),
}));

import { InvoiceCard } from "../invoice-card";
import type { InvoiceItemRow } from "../invoice-card";
import type { QuoteItemRow, QuoteInvoiceRow } from "@/entities/quote/queries";

interface InvoiceCardQuoteStub {
  procurement_completed_at: string | null;
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

function makeQuoteItem(overrides: Partial<QuoteItemRow> = {}): QuoteItemRow {
  return {
    id: "qi-1",
    quote_id: "q-1",
    product_name: "Test",
    brand: null,
    product_code: null,
    quantity: 1,
    invoice_id: null,
    composition_selected_invoice_id: null,
    is_unavailable: false,
    position: 1,
    ...overrides,
  } as QuoteItemRow;
}

// Phase 5d Group 5 Appendix: invoice_items row factory — mirrors the
// kvota.invoice_items schema that procurement-handsontable COLUMN_KEYS bind
// to. Tests may override any field via `overrides`.
function makeInvoiceItem(
  overrides: Partial<InvoiceItemRow> = {}
): InvoiceItemRow {
  return {
    id: "ii-1",
    invoice_id: "inv-A",
    position: 1,
    product_name: "Test",
    supplier_sku: null,
    brand: null,
    quantity: 1,
    purchase_price_original: null,
    purchase_currency: "USD",
    minimum_order_quantity: null,
    production_time_days: null,
    weight_in_kg: null,
    dimension_height_mm: null,
    dimension_width_mm: null,
    dimension_length_mm: null,
    ...overrides,
  };
}

describe("InvoiceCard — data-invoice-id attribute for scroll-to-card", () => {
  it("emits data-invoice-id on the card wrapper so Positions chips can scroll to it", () => {
    const invoice = makeInvoice({ id: "inv-scroll-target" });
    const quote: InvoiceCardQuoteStub = { procurement_completed_at: null };

    const html = renderToString(
      <InvoiceCard
        invoice={invoice}
        items={[]}
        quote={quote}
        invoiceItems={[]}
        coverageSummaryByItem={{}}
      />
    );

    expect(html).toContain('data-invoice-id="inv-scroll-target"');
  });
});

describe("InvoiceCard — isLocked semantics (Phase 5c edit-gate)", () => {
  it("does NOT render ProcurementUnlockButton when procurement_completed_at is null (editable by default)", () => {
    const invoice = makeInvoice({ sent_at: null });
    const quote: InvoiceCardQuoteStub = { procurement_completed_at: null };

    const html = renderToString(
      <InvoiceCard
        invoice={invoice}
        items={[]}
        quote={quote}
        invoiceItems={[]}
        coverageSummaryByItem={{}}
      />
    );

    // The ProcurementUnlockButton copy is "Редактировать с одобрением"
    expect(html).not.toContain("Редактировать с одобрением");
  });

  it("renders ProcurementUnlockButton when procurement_completed_at is set", () => {
    const invoice = makeInvoice({ sent_at: null });
    const quote: InvoiceCardQuoteStub = {
      procurement_completed_at: "2026-04-18T10:00:00Z",
    };

    const html = renderToString(
      <InvoiceCard
        invoice={invoice}
        items={[]}
        quote={quote}
        invoiceItems={[]}
        coverageSummaryByItem={{}}
      />
    );

    expect(html).toContain("Редактировать с одобрением");
  });

  it("regression: sent_at set but procurement_completed_at null → editable (no unlock button)", () => {
    // Phase 4a gated on sent_at; Phase 5c decouples: sent alone never locks.
    const invoice = makeInvoice({ sent_at: "2026-04-18T09:00:00Z" });
    const quote: InvoiceCardQuoteStub = { procurement_completed_at: null };

    const html = renderToString(
      <InvoiceCard
        invoice={invoice}
        items={[]}
        quote={quote}
        invoiceItems={[]}
        coverageSummaryByItem={{}}
      />
    );

    expect(html).not.toContain("Редактировать с одобрением");
  });
});

describe("InvoiceCard — sent_at badge is purely informational", () => {
  it("renders green 'Отправлено [date]' badge when invoice.sent_at != null", () => {
    const invoice = makeInvoice({ sent_at: "2026-04-18T09:00:00Z" });
    const quote: InvoiceCardQuoteStub = { procurement_completed_at: null };

    const html = renderToString(
      <InvoiceCard
        invoice={invoice}
        items={[]}
        quote={quote}
        invoiceItems={[]}
        coverageSummaryByItem={{}}
      />
    );

    expect(html).toContain("Отправлено");
  });

  it("omits the 'Отправлено' badge when invoice.sent_at is null", () => {
    const invoice = makeInvoice({ sent_at: null });
    const quote: InvoiceCardQuoteStub = { procurement_completed_at: null };

    const html = renderToString(
      <InvoiceCard
        invoice={invoice}
        items={[]}
        quote={quote}
        invoiceItems={[]}
        coverageSummaryByItem={{}}
      />
    );

    expect(html).not.toContain("Отправлено");
  });
});

describe("InvoiceCard — items source is invoice_items (not legacy FK filter)", () => {
  it("renders invoice_items rows with their own product_name (supplier-side)", () => {
    const invoice = makeInvoice();
    const quote: InvoiceCardQuoteStub = { procurement_completed_at: null };
    const quoteItems = [
      makeQuoteItem({ id: "qi-1", product_name: "Customer sees: Болт" }),
    ];
    const invoiceItems = [
      makeInvoiceItem({
        id: "ii-1",
        product_name: "Supplier sees: Bolt M8",
        supplier_sku: "SUP-SKU-1",
        brand: "ABB",
        quantity: 100,
        purchase_price_original: 12.5,
      }),
    ];

    const html = renderToString(
      <InvoiceCard
        invoice={invoice}
        items={quoteItems}
        quote={quote}
        invoiceItems={invoiceItems}
        coverageSummaryByItem={{}}
        defaultExpanded
      />
    );

    // Supplier-side name from invoice_items must appear.
    expect(html).toContain("Supplier sees: Bolt M8");
  });

  it("renders coverage summary for a split invoice_item (covers 2+ quote_items) ", () => {
    const invoice = makeInvoice();
    const quote: InvoiceCardQuoteStub = { procurement_completed_at: null };
    const invoiceItems = [
      makeInvoiceItem({
        id: "ii-1",
        product_name: "Болт",
        quantity: 100,
        purchase_price_original: 10,
      }),
    ];
    const coverageSummaryByItem = {
      "ii-1": "← болт, гайка, шайба объединены",
    };

    const html = renderToString(
      <InvoiceCard
        invoice={invoice}
        items={[]}
        quote={quote}
        invoiceItems={invoiceItems}
        coverageSummaryByItem={coverageSummaryByItem}
        defaultExpanded
      />
    );

    expect(html).toContain("← болт, гайка, шайба объединены");
  });

  it("renders coverage summary for a split (1 → N) invoice_item", () => {
    const invoice = makeInvoice();
    const quote: InvoiceCardQuoteStub = { procurement_completed_at: null };
    const invoiceItems = [
      makeInvoiceItem({
        id: "ii-bolt",
        position: 1,
        product_name: "болт",
        quantity: 100,
        purchase_price_original: 5,
      }),
      makeInvoiceItem({
        id: "ii-washer",
        position: 2,
        product_name: "шайба",
        quantity: 200,
        purchase_price_original: 1,
      }),
    ];
    const coverageSummaryByItem = {
      "ii-bolt": "→ болт ×1 + шайба ×2",
      "ii-washer": "→ болт ×1 + шайба ×2",
    };

    const html = renderToString(
      <InvoiceCard
        invoice={invoice}
        items={[]}
        quote={quote}
        invoiceItems={invoiceItems}
        coverageSummaryByItem={coverageSummaryByItem}
        defaultExpanded
      />
    );

    expect(html).toContain("→ болт ×1 + шайба ×2");
  });

  it("renders no coverage summary label for a plain 1:1 invoice_item", () => {
    const invoice = makeInvoice();
    const quote: InvoiceCardQuoteStub = { procurement_completed_at: null };
    const invoiceItems = [
      makeInvoiceItem({
        id: "ii-1",
        product_name: "болт",
        quantity: 100,
        purchase_price_original: 5,
      }),
    ];
    // No entry for ii-1 in coverageSummaryByItem → 1:1, no label
    const coverageSummaryByItem = {};

    const html = renderToString(
      <InvoiceCard
        invoice={invoice}
        items={[]}
        quote={quote}
        invoiceItems={invoiceItems}
        coverageSummaryByItem={coverageSummaryByItem}
        defaultExpanded
      />
    );

    expect(html).not.toContain("→");
    expect(html).not.toContain("←");
    expect(html).not.toContain("объединены");
  });
});

/**
 * Phase 5d Group 5 Appendix — caller-chain fix. Task 14 rebound the
 * handsontable's COLUMN_KEYS to `invoice_items` fields
 * (minimum_order_quantity, purchase_price_original, etc). The invoice-card
 * must now pass its `invoiceItems` (supplier-side) down to
 * ProcurementItemsEditor — not the `items` (customer-side QuoteItemRow[])
 * that was being passed before.
 *
 * We spy on ProcurementItemsEditor by mocking it and inspect the `items`
 * prop it receives. Its shape must match kvota.invoice_items.
 */
describe("InvoiceCard — passes invoice_items to ProcurementItemsEditor (caller-chain fix)", () => {
  it("passes supplier-side invoice_items rows (not customer-side QuoteItemRow[]) to the editor", async () => {
    const capturedEditorProps: Record<string, unknown>[] = [];
    vi.resetModules();

    vi.doMock("../procurement-items-editor", () => ({
      ProcurementItemsEditor: (props: Record<string, unknown>) => {
        capturedEditorProps.push(props);
        return null;
      },
    }));

    // Re-apply mocks that the full file sets up once at module-top.
    vi.doMock("next/navigation", () => ({
      useRouter: () => ({
        refresh: () => {},
        push: () => {},
        replace: () => {},
        back: () => {},
        forward: () => {},
        prefetch: () => {},
      }),
    }));
    vi.doMock("@/shared/lib/supabase/client", () => ({
      createClient: () => ({
        from: () => ({
          select: () => ({
            eq: () => ({
              order: () => ({
                select: async () => ({ data: [], error: null }),
              }),
            }),
            in: async () => ({ data: [], error: null }),
          }),
        }),
      }),
    }));

    const mod = await import("../invoice-card");
    const { InvoiceCard: IsolatedInvoiceCard } = mod;

    const invoice = makeInvoice();
    const quote: InvoiceCardQuoteStub = { procurement_completed_at: null };

    // Supplier-side invoice_items — must be forwarded to the editor.
    const invoiceItems = [
      {
        id: "ii-1",
        invoice_id: "inv-A",
        position: 1,
        product_name: "Bolt (supplier)",
        supplier_sku: "SUP-SKU-1",
        brand: "ABB",
        quantity: 100,
        purchase_price_original: 12.5,
        purchase_currency: "USD",
        minimum_order_quantity: 50,
        production_time_days: 14,
        weight_in_kg: 0.1,
        dimension_height_mm: 10,
        dimension_width_mm: 20,
        dimension_length_mm: 30,
      },
    ];

    // Customer-side QuoteItemRow[] — legacy prop; must NOT be what the
    // editor receives.
    const quoteItems = [
      makeQuoteItem({ id: "qi-1", product_name: "Customer view: Болт" }),
    ];

    renderToString(
      <IsolatedInvoiceCard
        invoice={invoice}
        items={quoteItems}
        quote={quote}
        invoiceItems={invoiceItems}
        coverageSummaryByItem={{}}
        defaultExpanded
      />
    );

    expect(capturedEditorProps.length).toBeGreaterThan(0);
    const editorItems = capturedEditorProps[0].items as Array<{
      id: string;
      product_name: string;
      minimum_order_quantity?: number | null;
    }>;

    // Editor must receive invoice_items rows (by id/name), not quote_items.
    expect(editorItems).toHaveLength(1);
    expect(editorItems[0].id).toBe("ii-1");
    expect(editorItems[0].product_name).toBe("Bolt (supplier)");
    // Key that handsontable COLUMN_KEYS rely on post-284.
    expect(editorItems[0].minimum_order_quantity).toBe(50);

    // And it must NOT pass the customer-side QuoteItemRow[] (qi-1).
    expect(editorItems.find((r) => r.id === "qi-1")).toBeUndefined();

    vi.doUnmock("../procurement-items-editor");
    vi.doUnmock("next/navigation");
    vi.doUnmock("@/shared/lib/supabase/client");
  });
});
