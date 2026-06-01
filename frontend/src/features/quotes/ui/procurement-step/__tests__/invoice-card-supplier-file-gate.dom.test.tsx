// @vitest-environment jsdom
/**
 * КПП «Файл КП поставщика» — card-level completion gate wiring.
 *
 * The backend rejects «Завершить закупку» with MISSING_SUPPLIER_FILE / 422
 * when no supplier-offer file is uploaded. Per the no-silent-validation rule
 * the card must, on that specific failure, BOTH toast the message AND highlight
 * the file field (not let the button silently fail). This test drives the
 * confirm → complete flow with `completeInvoiceProcurement` throwing a coded
 * error and asserts the file field is highlighted + the message rendered.
 */
import React from "react";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";

import type { QuoteInvoiceRow } from "@/entities/quote/queries";

// ---------------------------------------------------------------------------
// Mocks (hoisted)
// ---------------------------------------------------------------------------

const { toastState } = vi.hoisted(() => ({
  toastState: { errors: [] as string[] },
}));

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    from: () => ({
      select: () => ({
        eq: () => ({
          order: () => ({ order: () => Promise.resolve({ data: [], error: null }) }),
          maybeSingle: () => Promise.resolve({ data: null, error: null }),
          in: () => Promise.resolve({ data: [], error: null }),
        }),
      }),
      update: () => ({ eq: async () => ({ error: null }) }),
      delete: () => ({ in: async () => ({ error: null }) }),
    }),
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

// completeInvoiceProcurement throws the coded 422 error (the real mutation
// attaches `.code` from the structured envelope — see mutations.ts).
vi.mock("@/entities/quote/mutations", async () => {
  const actual = await vi.importActual<
    typeof import("@/entities/quote/mutations")
  >("@/entities/quote/mutations");
  return {
    ...actual,
    fetchCargoPlaces: vi.fn().mockResolvedValue([]),
    completeInvoiceProcurement: vi.fn().mockImplementation(() => {
      const err = new Error(
        "Загрузите файл КП поставщика перед завершением закупки",
      ) as Error & { code?: string };
      err.code = "MISSING_SUPPLIER_FILE";
      return Promise.reject(err);
    }),
  };
});

vi.mock("@/entities/quote/server-actions", () => ({
  notifyInvoiceCompletedForKanban: vi
    .fn()
    .mockResolvedValue({ advancedSlices: [] }),
  notifyInvoiceSentForKanban: vi.fn().mockResolvedValue({ advancedSlices: [] }),
}));

vi.mock("../procurement-items-editor", () => ({
  ProcurementItemsEditor: () => null,
}));
vi.mock("../send-history-panel", () => ({ SendHistoryPanel: () => null }));
vi.mock("../letter-draft-composer", () => ({ LetterDraftComposer: () => null }));
vi.mock("../split-inline-dialog", () => ({ SplitInlineDialog: () => null }));
vi.mock("../merge-inline-dialog", () => ({ MergeInlineDialog: () => null }));
vi.mock("../add-cargo-place-dialog", () => ({ AddCargoPlaceDialog: () => null }));
vi.mock("../add-positions-modal", () => ({ AddPositionsModal: () => null }));
vi.mock("../procurement-unlock-button", () => ({
  ProcurementUnlockButton: () => null,
}));

vi.mock("@/shared/ui/geo", async () => {
  const actual = await vi.importActual<typeof import("@/shared/ui/geo")>(
    "@/shared/ui/geo",
  );
  return { ...actual, CountryCombobox: () => null, CityAutocomplete: () => null };
});
vi.mock("@/shared/ui/searchable-combobox", () => ({
  SearchableCombobox: () => null,
}));

vi.mock("sonner", () => ({
  toast: {
    error: (msg: string) => toastState.errors.push(msg),
    success: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  },
}));

import { InvoiceCard, type InvoiceCardQuoteStub } from "../invoice-card";

// ---------------------------------------------------------------------------
// Fixtures — a completable КПП (priced position + advance) but NO file.
// ---------------------------------------------------------------------------

function makeInvoice(): QuoteInvoiceRow {
  return {
    id: "inv-file-1",
    invoice_number: "INV-Q-91",
    quote_id: "q-91",
    supplier_id: "sup-1",
    supplier: { id: "sup-1", name: "Acme" },
    buyer_company: { name: "Buyer LLC", company_code: "BUY-001" },
    supplier_contact_id: null,
    supplier_contact: null,
    sent_at: null,
    status: "pending_procurement",
    currency: "USD",
    advance_pct: 30,
    payment_terms: null,
    invoice_file_url: null,
    pickup_city: null,
    pickup_country: null,
    pickup_country_code: null,
    supplier_incoterms: null,
    total_weight_kg: null,
    total_volume_m3: null,
  } as unknown as QuoteInvoiceRow;
}

type CardProps = Parameters<typeof InvoiceCard>[0];
type CardInvoiceItem = NonNullable<CardProps["invoiceItems"]>[number];

const PRICED_ITEM = {
  id: "ii-1",
  invoice_id: "inv-file-1",
  position: 1,
  product_name: "Bolt",
  supplier_sku: "B-1",
  brand: "Acme",
  quantity: 10,
  purchase_price_original: 5,
  purchase_currency: "USD",
  minimum_order_quantity: null,
  production_time_days: null,
  weight_in_kg: null,
  dimension_height_mm: null,
  dimension_width_mm: null,
  dimension_length_mm: null,
} as unknown as CardInvoiceItem;

const quoteStub: InvoiceCardQuoteStub = { procurement_completed_at: null };

beforeEach(() => {
  toastState.errors = [];
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("InvoiceCard — supplier-file completion gate (422 → highlight)", () => {
  it("highlights the file field and toasts when completion is blocked by the missing file", async () => {
    render(
      <InvoiceCard
        invoice={makeInvoice()}
        items={[]}
        quote={quoteStub}
        invoiceItems={[PRICED_ITEM]}
        coverageSummaryByItem={{}}
        defaultExpanded={true}
      />,
    );

    // Open the confirm dialog, then confirm completion.
    fireEvent.click(await screen.findByText("Завершить закупку"));
    const confirmButtons = await screen.findAllByText("Завершить закупку");
    // The dialog's confirm button is the last rendered «Завершить закупку».
    fireEvent.click(confirmButtons[confirmButtons.length - 1]);

    // The 422 message is toasted (not silently swallowed)...
    await waitFor(() => {
      expect(toastState.errors).toContain(
        "Загрузите файл КП поставщика перед завершением закупки",
      );
    });

    // ...and the file field is highlighted with the same message.
    await waitFor(() => {
      const input = screen.getByTestId(
        "invoice-supplier-file-input",
      ) as HTMLInputElement;
      expect(input.getAttribute("aria-invalid")).toBe("true");
    });
    expect(
      screen.getByText(
        "Загрузите файл КП поставщика перед завершением закупки",
      ),
    ).toBeInTheDocument();
  });
});
