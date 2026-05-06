// @vitest-environment jsdom
/**
 * РОЗ-95 / МОЗ-82 — VAT rate autofill from `kvota.vat_rates_by_country`.
 *
 * The procurement КПП card auto-suggests «Ставка НДС, %» when the user picks
 * an отгрузка country. The lookup table is admin-managed at /admin/vat-rates.
 *
 * Two anti-stomp invariants this suite locks in:
 *   1. AUTOFILL fires only when the local vat_rate field is empty — a saved
 *      DB value or a value the user just typed is never overwritten.
 *   2. Re-checking the empty guard happens twice (sync at effect entry, and
 *      again at promise resolution) so a keystroke during the network
 *      round-trip wins over the network result.
 *
 * SSR-style tests in `invoice-card.test.tsx` cover render correctness; the
 * jsdom substrate here is needed because the autofill is a useEffect that
 * never runs during `renderToString`.
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, waitFor } from "@testing-library/react";

import type { QuoteInvoiceRow } from "@/entities/quote/queries";
import type { InvoiceCardQuoteStub } from "../invoice-card";

// ---------------------------------------------------------------------------
// Mocks (vi.mock is hoisted — declared before component import)
// ---------------------------------------------------------------------------

// Track every supabase.from(...) call so tests can assert which tables were
// hit. The factory below returns a per-table chain that resolves to the data
// configured in `mockData` for that table (or empty defaults).
const fromCalls: string[] = [];
const mockData: Record<string, unknown> = {};
const updateCalls: Array<{ table: string; payload: Record<string, unknown> }> = [];

function makeChain(table: string) {
  // Chainable PostgREST builder stub. Each terminal awaits to a `{ data, error }`
  // shape; chained methods just return the same builder.
  const result =
    table === "vat_rates_by_country"
      ? mockData.vat_rates_by_country ?? null
      : null;

  const chain: Record<string, unknown> = {
    select: () => chain,
    eq: () => chain,
    in: () => Promise.resolve({ data: [], error: null }),
    order: () => Promise.resolve({ data: [], error: null }),
    maybeSingle: () => Promise.resolve({ data: result, error: null }),
    update: (payload: Record<string, unknown>) => {
      updateCalls.push({ table, payload });
      return chain;
    },
    then: undefined,
  };
  return chain;
}

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    from: (table: string) => {
      fromCalls.push(table);
      return makeChain(table);
    },
    auth: {
      getSession: async () => ({ data: { session: null } }),
    },
  }),
}));

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

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  },
}));

// Heavy children of InvoiceCard — replace with no-ops so the dom render
// stays focused on the «Параметры отгрузки» row that hosts the VAT input.
vi.mock("../procurement-items-editor", () => ({
  ProcurementItemsEditor: () => null,
}));

vi.mock("../send-history-panel", () => ({
  SendHistoryPanel: () => null,
}));

vi.mock("../procurement-unlock-button", () => ({
  ProcurementUnlockButton: () => null,
}));

vi.mock("../letter-draft-composer", () => ({
  LetterDraftComposer: () => null,
}));

vi.mock("../split-inline-dialog", () => ({
  SplitInlineDialog: () => null,
}));

vi.mock("../merge-inline-dialog", () => ({
  MergeInlineDialog: () => null,
}));

vi.mock("../add-cargo-place-dialog", () => ({
  AddCargoPlaceDialog: () => null,
}));

vi.mock("../add-positions-modal", () => ({
  AddPositionsModal: () => null,
}));

// Cargo-place fetch is unrelated to VAT autofill — return empty list so the
// effect hits its no-op branch without exercising the real API.
vi.mock("@/entities/quote/mutations", async () => {
  const actual = await vi.importActual<
    typeof import("@/entities/quote/mutations")
  >("@/entities/quote/mutations");
  return {
    ...actual,
    fetchCargoPlaces: vi.fn(async () => []),
    deleteCargoPlace: vi.fn(async () => undefined),
    deleteInvoice: vi.fn(async () => undefined),
    completeInvoiceProcurement: vi.fn(async () => undefined),
    undoMerge: vi.fn(async () => undefined),
    undoSplit: vi.fn(async () => undefined),
    updateCargoPlace: vi.fn(async () => undefined),
  };
});

vi.mock("@/entities/quote/server-actions", () => ({
  notifyInvoiceCompletedForKanban: vi.fn(async () => ({ advancedSlices: [] })),
  notifyInvoiceSentForKanban: vi.fn(async () => ({ advancedSlices: [] })),
}));

vi.mock("@/entities/invoice/mutations", () => ({
  downloadInvoiceXls: vi.fn(async () => undefined),
  markInvoiceSent: vi.fn(async () => undefined),
}));

import { InvoiceCard } from "../invoice-card";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeInvoice(
  overrides: Partial<QuoteInvoiceRow> & { vat_rate?: number | null } = {}
): QuoteInvoiceRow {
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
    vat_rate: null,
    ...overrides,
  } as unknown as QuoteInvoiceRow;
}

const quoteStub: InvoiceCardQuoteStub = { procurement_completed_at: null };

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("InvoiceCard — VAT autofill from kvota.vat_rates_by_country", () => {
  beforeEach(() => {
    fromCalls.length = 0;
    updateCalls.length = 0;
    delete mockData.vat_rates_by_country;
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("fills empty НДС from the country lookup on mount when invoice.vat_rate is null", async () => {
    mockData.vat_rates_by_country = { rate: 22 };

    const invoice = makeInvoice({
      pickup_country_code: "IT",
      vat_rate: null,
    });

    const { container } = render(
      <InvoiceCard invoice={invoice} items={[]} quote={quoteStub} invoiceItems={[]} defaultExpanded />
    );

    // Hits the lookup table (the load() effect also queries invoice_items
    // and quote_items, those are tolerated).
    await waitFor(() => {
      expect(fromCalls).toContain("vat_rates_by_country");
    });

    // The «Ставка НДС, %» input is the only number input with min=0 max=100
    // step=0.01 in the «Параметры отгрузки» block. Locate by placeholder.
    await waitFor(() => {
      const vatInput = container.querySelector<HTMLInputElement>(
        'input[placeholder="НДС"]'
      );
      expect(vatInput).not.toBeNull();
      expect(vatInput!.value).toBe("22");
    });

    // The autofill also persists to invoices.vat_rate so a page reload picks
    // up the same number.
    await waitFor(() => {
      const update = updateCalls.find((u) => u.table === "invoices");
      expect(update).toBeDefined();
      expect(update!.payload).toMatchObject({ vat_rate: 22 });
    });
  });

  it("does NOT overwrite an existing saved vat_rate (18) even if the country lookup returns a different value", async () => {
    mockData.vat_rates_by_country = { rate: 22 };

    const invoice = makeInvoice({
      pickup_country_code: "IT",
      vat_rate: 18,
    });

    const { container } = render(
      <InvoiceCard invoice={invoice} items={[]} quote={quoteStub} invoiceItems={[]} defaultExpanded />
    );

    // Give the autofill effect time to consider the lookup.
    await new Promise((resolve) => setTimeout(resolve, 0));

    const vatInput = container.querySelector<HTMLInputElement>(
      'input[placeholder="НДС"]'
    );
    expect(vatInput).not.toBeNull();
    expect(vatInput!.value).toBe("18");

    // No invoice update should have fired — the saved value wins.
    const updates = updateCalls.filter((u) => u.table === "invoices");
    expect(updates).toEqual([]);
  });

  it("skips the autofill (no fetch, no overwrite) when pickup_country_code is null", async () => {
    mockData.vat_rates_by_country = { rate: 22 };

    const invoice = makeInvoice({
      pickup_country_code: null,
      vat_rate: null,
    });

    render(
      <InvoiceCard invoice={invoice} items={[]} quote={quoteStub} invoiceItems={[]} defaultExpanded />
    );

    await new Promise((resolve) => setTimeout(resolve, 0));

    // No country → no lookup. The other load() supabase calls (invoice_items,
    // quote_items) are still allowed.
    expect(fromCalls).not.toContain("vat_rates_by_country");
    expect(updateCalls.filter((u) => u.table === "invoices")).toEqual([]);
  });
});
