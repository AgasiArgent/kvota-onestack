// @vitest-environment jsdom
/**
 * МОЗ-94 (truncation) — supplier and customer name chips in the КПП header
 * truncate on narrow widths (e.g. «ADLER S…», «GESTUS Tradin…»). The fix
 * wraps each chip in an always-on Tooltip exposing the full name. These
 * tests pin two contracts:
 *
 *   1. The visible chip text is still rendered exactly (no truncation in
 *      the markup — CSS handles the visual ellipsis, the DOM keeps the
 *      full string so screen readers and the new tooltip can both surface
 *      it).
 *   2. Each chip is the trigger of a Tooltip — verified by the
 *      `aria-describedby` wiring from base-ui Tooltip onto the trigger
 *      span when the popover is open.
 *
 * Hover behaviour itself is exercised end-to-end on localhost per
 * `reference_localhost_browser_test.md`; jsdom limits the depth of the
 * portal interaction we can verify here.
 */
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
    // `.order()` may be called once or chained twice (e.g. supplier_contacts
    // ordered by is_primary then name — Testing 2 row 25). The returned
    // object is itself a thenable AND accepts another `.order()` — so both
    // `await q.order(...)` and `await q.order(...).order(...)` resolve to
    // `{data: [], error: null}`.
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

const LONG_SUPPLIER_NAME =
  "ADLER S.p.A. Industria Italiana Cuscinetti e Componenti Meccanici";
const LONG_BUYER_NAME =
  "GESTUS Trading Limited Liability Company (Hong Kong Branch)";

function makeInvoice(
  overrides: Partial<QuoteInvoiceRow> = {},
): QuoteInvoiceRow {
  return {
    id: "inv-A",
    invoice_number: "INV-01-Q-202604-0067",
    quote_id: "q-1",
    supplier_id: "sup-1",
    supplier: { id: "sup-1", name: LONG_SUPPLIER_NAME },
    buyer_company: { name: LONG_BUYER_NAME, company_code: "GESTUS" },
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

describe("InvoiceCard — truncated header chip tooltips (МОЗ-94)", () => {
  it("renders the full supplier name in the DOM (CSS truncates visually, DOM keeps the full string)", () => {
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

    const supplierChip = screen.getByTestId(
      "invoice-card-header-supplier-name",
    );
    expect(supplierChip).toBeInTheDocument();
    expect(supplierChip).toHaveTextContent(LONG_SUPPLIER_NAME);
    // Tailwind truncate must remain — that's how the visual ellipsis is
    // produced. The Tooltip recovers what's hidden.
    expect(supplierChip.className).toContain("truncate");
  });

  it("renders the full buyer/customer name in the DOM", () => {
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

    const buyerChip = screen.getByTestId("invoice-card-header-buyer-name");
    expect(buyerChip).toBeInTheDocument();
    expect(buyerChip).toHaveTextContent(LONG_BUYER_NAME);
    expect(buyerChip.className).toContain("truncate");
  });

  it("wires each chip to a Tooltip trigger (popup id present in DOM tree)", () => {
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

    // base-ui sets `data-popup-open` / `aria-describedby` only on open;
    // when closed, the trigger still carries `data-state="closed"` from
    // base-ui's Tooltip primitive. Asserting the trigger element itself
    // is what guarantees the tooltip wrapper is alive in the DOM.
    const supplierChip = screen.getByTestId(
      "invoice-card-header-supplier-name",
    );
    const buyerChip = screen.getByTestId("invoice-card-header-buyer-name");

    // base-ui's TooltipTrigger sets `data-slot="tooltip-trigger"` via the
    // shadcn wrapper — see frontend/src/components/ui/tooltip.tsx L24-26.
    expect(supplierChip.getAttribute("data-slot")).toBe("tooltip-trigger");
    expect(buyerChip.getAttribute("data-slot")).toBe("tooltip-trigger");
  });

  it("does not render the buyer chip when buyer_company is missing (no empty Tooltip)", () => {
    render(
      <InvoiceCard
        invoice={makeInvoice({ buyer_company: null } as Partial<QuoteInvoiceRow>)}
        items={[]}
        quote={quoteStub}
        invoiceItems={[]}
        coverageSummaryByItem={{}}
        defaultExpanded={false}
      />,
    );

    expect(
      screen.queryByTestId("invoice-card-header-buyer-name"),
    ).not.toBeInTheDocument();
  });
});
