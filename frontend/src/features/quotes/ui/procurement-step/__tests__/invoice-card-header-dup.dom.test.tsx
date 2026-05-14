// @vitest-environment jsdom
/**
 * РОЗ-107/108 + МОЗ-94 — header chips must hide when the invoice card is
 * expanded. The «Параметры отгрузки» / «Грузовые места» sections render the
 * same data as editable form fields below the header, and stacking both
 * causes the long-value overflow / truncation reported by the tester
 * («Часть не возможно прочесть»). MОЗ-94 explicitly asks: «Там где в
 * header количество мест - данные не меняются - в целом удалить это из
 * header».
 *
 * Collapsed state must KEEP the chips so the card stays useful as a preview.
 */
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import type { QuoteInvoiceRow } from "@/entities/quote/queries";

// ---------------------------------------------------------------------------
// Mocks (must come before component import — vitest hoists vi.mock)
// ---------------------------------------------------------------------------

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

// Supabase client — invoice-card hits it on mount to fetch invoice_items
// + coverage. Return empty so the load() effect resolves without surfacing
// any rendering side-effects.
vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => {
    // Testing 2 row 25 added a `.order().order()` chain for supplier_contacts
    // fetch. The orderable returned here is a thenable AND accepts another
    // `.order()` so both single- and double-chained awaits resolve.
    interface Orderable {
      order: () => Orderable;
      then: (resolve: (v: { data: unknown[]; error: null }) => unknown) => unknown;
    }
    const makeOrderable = (): Orderable => ({
      order: () => makeOrderable(),
      then: (resolve) => resolve({ data: [], error: null }),
    });
    return {
      from: () => ({
        select: () => ({
          eq: () => ({
            order: () => makeOrderable(),
            maybeSingle: () => Promise.resolve({ data: null, error: null }),
          }),
          in: () => ({ data: [], error: null }),
        }),
        update: () => ({ eq: async () => ({ error: null }) }),
        delete: () => ({ in: async () => ({ error: null }) }),
      }),
    };
  },
}));

// Cargo-place fetch side-effect mock — the card calls fetchCargoPlaces on
// mount; an empty list keeps the cargo-summary chip out of the picture
// when we deliberately want pickup_location only.
vi.mock("@/entities/quote/mutations", async () => {
  const actual = await vi.importActual<
    typeof import("@/entities/quote/mutations")
  >("@/entities/quote/mutations");
  return {
    ...actual,
    fetchCargoPlaces: vi.fn().mockResolvedValue([]),
  };
});

// Heavy child components contribute nothing to header-chip assertions and
// pull in dynamic imports / portal mounts that complicate jsdom render flow.
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

// Geo combobox + city autocomplete depend on Supabase + HERE; out of scope
// for header-chip behaviour.
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
    id: "inv-A",
    invoice_number: "INV-01-Q-202604-0067",
    quote_id: "q-1",
    supplier_id: "sup-1",
    supplier: { id: "sup-1", name: "ADLER SpA" },
    buyer_company: { name: "GESTUS Trading Ltd", company_code: "GESTUS" },
    sent_at: null,
    status: "pending_procurement",
    currency: "USD",
    pickup_city: "Milan",
    pickup_country: "Италия",
    pickup_country_code: "IT",
    supplier_incoterms: "EXW",
    total_weight_kg: 12.5,
    total_volume_m3: 0.34,
    ...overrides,
  } as unknown as QuoteInvoiceRow;
}

const quoteStub: InvoiceCardQuoteStub = { procurement_completed_at: null };

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("InvoiceCard — header chips hide when expanded (РОЗ-107/108, МОЗ-94)", () => {
  it("renders pickup location / incoterms / weight chips in the header when collapsed", () => {
    render(
      <InvoiceCard
        invoice={makeInvoice()}
        items={[]}
        quote={quoteStub}
        invoiceItems={[]}
        coverageSummaryByItem={{}}
        defaultExpanded={false}
      />,
    );

    expect(
      screen.getByTestId("invoice-card-header-pickup-location"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("invoice-card-header-incoterms"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("invoice-card-header-weight"),
    ).toBeInTheDocument();
  });

  it("hides pickup location / incoterms / weight chips from the header when expanded", () => {
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

    // The same data appears in the editable «Параметры отгрузки» section
    // below the header, so duplicating it as chips is pure noise.
    expect(
      screen.queryByTestId("invoice-card-header-pickup-location"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("invoice-card-header-incoterms"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("invoice-card-header-weight"),
    ).not.toBeInTheDocument();
  });

  it("keeps always-visible summary metadata when collapsed (invoice number, supplier, buyer)", () => {
    // Invoice number, supplier name, and buyer name are NOT duplicated in
    // the form below — they're identifying labels, not editable fields,
    // so they must always render regardless of expand state.
    render(
      <InvoiceCard
        invoice={makeInvoice()}
        items={[]}
        quote={quoteStub}
        invoiceItems={[]}
        coverageSummaryByItem={{}}
        defaultExpanded={false}
      />,
    );

    expect(screen.getByText("INV-01-Q-202604-0067")).toBeInTheDocument();
    expect(screen.getByText("ADLER SpA")).toBeInTheDocument();
    expect(screen.getByText(/GESTUS Trading Ltd/)).toBeInTheDocument();
  });

  it("keeps always-visible summary metadata when expanded (invoice number, supplier, buyer)", () => {
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

    expect(screen.getByText("INV-01-Q-202604-0067")).toBeInTheDocument();
    expect(screen.getByText("ADLER SpA")).toBeInTheDocument();
    expect(screen.getByText(/GESTUS Trading Ltd/)).toBeInTheDocument();
  });
});
