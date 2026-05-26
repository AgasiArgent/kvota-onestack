// @vitest-environment jsdom
/**
 * Testing 2 row 69 (m328) — supplier-payment fields moved from positions to
 * the invoice level. Two invoices from the same supplier may carry different
 * terms (stocking vs. prepaid lots), so the values now live on
 * `kvota.invoices` (advance_pct + payment_terms), not on each quote_item.
 *
 * This pins three contracts for the invoice-card header block:
 *
 *   1. Two inputs render in the header next to currency/VAT: «% аванса»
 *      (numeric 0..100) and «Условия оплаты» (free text).
 *   2. Initial values come from `invoice.advance_pct` / `invoice.payment_terms`.
 *   3. On blur, valid changes call Supabase
 *      `update({ advance_pct })` or `update({ payment_terms })` on the
 *      `invoices` row.
 *
 * Companion negative test — the procurement handsontable must NOT render the
 * old per-position columns. That's covered in
 * `procurement-handsontable.columns.dom.test.tsx`.
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { QuoteInvoiceRow } from "@/entities/quote/queries";

// ---------------------------------------------------------------------------
// Mocks (vi.mock is hoisted — must precede component import)
// ---------------------------------------------------------------------------

const { invoicesUpdateState } = vi.hoisted(() => {
  return {
    invoicesUpdateState: {
      lastUpdate: null as Record<string, unknown> | null,
      lastInvoiceId: null as string | null,
    },
  };
});

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    from: (table: string) => {
      if (table === "invoices") {
        return {
          update: (payload: Record<string, unknown>) => {
            invoicesUpdateState.lastUpdate = payload;
            return {
              eq: async (_col: string, id: string) => {
                invoicesUpdateState.lastInvoiceId = id;
                return { error: null };
              },
            };
          },
          select: () => ({
            eq: () => ({
              order: () => Promise.resolve({ data: [], error: null }),
              maybeSingle: () => Promise.resolve({ data: null, error: null }),
              in: () => Promise.resolve({ data: [], error: null }),
            }),
          }),
        };
      }
      // Generic fallback — vat_rates_by_country, supplier_contacts, etc.
      return {
        select: () => ({
          eq: () => ({
            order: () => ({ order: () => Promise.resolve({ data: [], error: null }) }),
            maybeSingle: () => Promise.resolve({ data: null, error: null }),
            in: () => Promise.resolve({ data: [], error: null }),
          }),
        }),
        update: () => ({ eq: async () => ({ error: null }) }),
        delete: () => ({ in: async () => ({ error: null }) }),
      };
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

vi.mock("@/entities/quote/mutations", async () => {
  const actual = await vi.importActual<
    typeof import("@/entities/quote/mutations")
  >("@/entities/quote/mutations");
  return {
    ...actual,
    fetchCargoPlaces: vi.fn().mockResolvedValue([]),
  };
});

vi.mock("../procurement-items-editor", () => ({
  ProcurementItemsEditor: () => null,
}));
vi.mock("../send-history-panel", () => ({
  SendHistoryPanel: () => null,
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
vi.mock("../procurement-unlock-button", () => ({
  ProcurementUnlockButton: () => null,
}));

vi.mock("@/shared/ui/geo", async () => {
  const actual = await vi.importActual<typeof import("@/shared/ui/geo")>(
    "@/shared/ui/geo",
  );
  return {
    ...actual,
    CountryCombobox: () => null,
    CityAutocomplete: () => null,
  };
});

vi.mock("@/shared/ui/searchable-combobox", () => ({
  SearchableCombobox: () => null,
}));

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  },
}));

import { InvoiceCard, type InvoiceCardQuoteStub } from "../invoice-card";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeInvoice(
  overrides: Partial<QuoteInvoiceRow> = {},
): QuoteInvoiceRow {
  return {
    id: "inv-payment-1",
    invoice_number: "INV-Q-69",
    quote_id: "q-69",
    supplier_id: "sup-1",
    supplier: { id: "sup-1", name: "Acme" },
    buyer_company: { name: "Buyer LLC", company_code: "BUY-001" },
    supplier_contact_id: null,
    supplier_contact: null,
    sent_at: null,
    status: "pending_procurement",
    currency: "USD",
    vat_rate: null,
    pickup_city: null,
    pickup_country: null,
    pickup_country_code: null,
    supplier_incoterms: null,
    total_weight_kg: 12.5,
    total_volume_m3: 0.34,
    advance_pct: null,
    payment_terms: null,
    ...overrides,
  } as unknown as QuoteInvoiceRow;
}

const quoteStub: InvoiceCardQuoteStub = { procurement_completed_at: null };

beforeEach(() => {
  invoicesUpdateState.lastUpdate = null;
  invoicesUpdateState.lastInvoiceId = null;
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("InvoiceCard — invoice-level payment fields (m328, Testing 2 row 69)", () => {
  it("renders the «% аванса» and «Условия оплаты» inputs in the header block", async () => {
    render(
      <InvoiceCard
        invoice={makeInvoice()}
        items={[]}
        quote={quoteStub}
        invoiceItems={[]}
        coverageSummaryByItem={{}}
        defaultExpanded={true}
      />,
    );

    expect(await screen.findByLabelText("% аванса")).toBeInTheDocument();
    expect(screen.getByLabelText("Условия оплаты")).toBeInTheDocument();
    expect(
      screen.getByTestId("invoice-card-advance-pct"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("invoice-card-payment-terms"),
    ).toBeInTheDocument();
  });

  it("prefills the inputs from invoice.advance_pct / invoice.payment_terms", async () => {
    render(
      <InvoiceCard
        invoice={makeInvoice({
          advance_pct: 30,
          payment_terms: "30% advance, 70% before shipment",
        } as Partial<QuoteInvoiceRow>)}
        items={[]}
        quote={quoteStub}
        invoiceItems={[]}
        coverageSummaryByItem={{}}
        defaultExpanded={true}
      />,
    );

    const advance = (await screen.findByLabelText(
      "% аванса",
    )) as HTMLInputElement;
    const terms = screen.getByLabelText("Условия оплаты") as HTMLInputElement;
    expect(advance.value).toBe("30");
    expect(terms.value).toBe("30% advance, 70% before shipment");
  });

  it("PATCHes invoices.advance_pct on blur with a valid 0..100 value", async () => {
    render(
      <InvoiceCard
        invoice={makeInvoice()}
        items={[]}
        quote={quoteStub}
        invoiceItems={[]}
        coverageSummaryByItem={{}}
        defaultExpanded={true}
      />,
    );

    const input = (await screen.findByLabelText("% аванса")) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "50" } });
    fireEvent.blur(input);

    await waitFor(() => {
      expect(invoicesUpdateState.lastInvoiceId).toBe("inv-payment-1");
    });
    expect(invoicesUpdateState.lastUpdate).toEqual({ advance_pct: 50 });
  });

  it("PATCHes invoices.payment_terms on blur with non-empty text", async () => {
    render(
      <InvoiceCard
        invoice={makeInvoice()}
        items={[]}
        quote={quoteStub}
        invoiceItems={[]}
        coverageSummaryByItem={{}}
        defaultExpanded={true}
      />,
    );

    const input = (await screen.findByLabelText(
      "Условия оплаты",
    )) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "50% advance, 50% on delivery" } });
    fireEvent.blur(input);

    await waitFor(() => {
      expect(invoicesUpdateState.lastInvoiceId).toBe("inv-payment-1");
    });
    expect(invoicesUpdateState.lastUpdate).toEqual({
      payment_terms: "50% advance, 50% on delivery",
    });
  });

  it("PATCHes payment_terms=null when the user clears the input", async () => {
    render(
      <InvoiceCard
        invoice={makeInvoice({
          payment_terms: "30% advance, 70% before shipment",
        } as Partial<QuoteInvoiceRow>)}
        items={[]}
        quote={quoteStub}
        invoiceItems={[]}
        coverageSummaryByItem={{}}
        defaultExpanded={true}
      />,
    );

    const input = (await screen.findByLabelText(
      "Условия оплаты",
    )) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "" } });
    fireEvent.blur(input);

    await waitFor(() => {
      expect(invoicesUpdateState.lastInvoiceId).toBe("inv-payment-1");
    });
    expect(invoicesUpdateState.lastUpdate).toEqual({ payment_terms: null });
  });

  it("rejects out-of-range advance_pct (e.g., 150) without PATCH", async () => {
    render(
      <InvoiceCard
        invoice={makeInvoice()}
        items={[]}
        quote={quoteStub}
        invoiceItems={[]}
        coverageSummaryByItem={{}}
        defaultExpanded={true}
      />,
    );

    const input = (await screen.findByLabelText("% аванса")) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "150" } });
    fireEvent.blur(input);

    // Range validation skips the network call; lastUpdate stays null.
    expect(invoicesUpdateState.lastUpdate).toBeNull();
  });
});
