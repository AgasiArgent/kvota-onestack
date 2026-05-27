// @vitest-environment jsdom
/**
 * Testing 2 row 89 — Дата дедлайна КПП в теле КПП.
 *
 * The КПП card surfaces its parent procurement-request deadline inline so
 * МОЗ/РОЗ sees when the closing window expires without leaving the card.
 * The deadline is canonical at the quote-stage level (parent), the card
 * mirrors it read-only.
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

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => {
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
    invoice_number: "INV-01-Q-202604-0089",
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

const quoteStub: InvoiceCardQuoteStub = { procurement_completed_at: null };

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("InvoiceCard — procurement deadline cell (Testing 2 row 89)", () => {
  it("renders Дедлайн badge with the formatted parent procurement deadline", () => {
    // 28 May 2026 12:00 UTC — deterministic so we can assert the formatted
    // string without timezone wobble (Intl 'ru-RU' day-month-year is stable
    // across locales when the date falls on the same calendar day in UTC+0
    // and the host TZ). 12:00 UTC sits comfortably inside the 28th in every
    // TZ that vitest CI runs against.
    const deadlineAt = "2026-05-28T12:00:00.000Z";

    render(
      <InvoiceCard
        invoice={makeInvoice()}
        items={[]}
        quote={quoteStub}
        invoiceItems={[]}
        coverageSummaryByItem={{}}
        procurementDeadlineAt={deadlineAt}
      />,
    );

    const badge = screen.getByTestId("invoice-card-procurement-deadline");
    expect(badge).toBeTruthy();
    expect(badge.textContent ?? "").toMatch(/Дедлайн/);
    expect(badge.textContent ?? "").toMatch(/28\.05\.2026/);
  });

  it("hides the Дедлайн badge when procurementDeadlineAt is null", () => {
    render(
      <InvoiceCard
        invoice={makeInvoice()}
        items={[]}
        quote={quoteStub}
        invoiceItems={[]}
        coverageSummaryByItem={{}}
        procurementDeadlineAt={null}
      />,
    );

    expect(
      screen.queryByTestId("invoice-card-procurement-deadline"),
    ).toBeNull();
  });

  it("hides the Дедлайн badge when procurementDeadlineAt prop is omitted", () => {
    // Default-prop path: callers that haven't been updated yet (legacy
    // tests, storybook) keep working without surfacing a phantom deadline.
    render(
      <InvoiceCard
        invoice={makeInvoice()}
        items={[]}
        quote={quoteStub}
        invoiceItems={[]}
        coverageSummaryByItem={{}}
      />,
    );

    expect(
      screen.queryByTestId("invoice-card-procurement-deadline"),
    ).toBeNull();
  });
});
