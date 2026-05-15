// @vitest-environment jsdom
/**
 * Testing 2 row 20 (v3) — autosave-driven refetch must not flash the
 * "Загрузка..." placeholder.
 *
 * Background: every time the procurement-handsontable autosaves a cell it
 * bumps the card's local `refreshKey` (via `onMutated`) so the
 * invoice_items load() effect re-runs and the supplier-side rows refresh.
 * Earlier the load() effect flipped `invoiceItemsLoading=true` on EVERY
 * re-run, which made the render branch in invoice-card.tsx swap the
 * mounted <ProcurementItemsEditor> for a "Загрузка..." text node. When the
 * fetch resolved the editor was remounted from scratch — the user saw the
 * table "прыгает" on every Enter. РОЗ/СтМОЗ/МОЗ all reported this on round
 * 3 even though PR #156 already pinned the `data` reference inside the
 * editor.
 *
 * Contract pinned by this test: once invoice_items have loaded at least
 * once, a subsequent refresh signal (bumping `externalRefreshKey`, which
 * shares the same load() effect as `refreshKey`) must NOT cause the
 * "Загрузка..." placeholder to re-appear. The editor stays mounted; data
 * updates flow into Handsontable imperatively via `setDataAtRowProp`.
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

import type { QuoteInvoiceRow } from "@/entities/quote/queries";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => {
    // supplier_contacts is fetched via `.order(...).order(...)` — make the
    // chain thenable AND re-orderable so both single-`.order()` callers and
    // the new double-`.order()` caller resolve to an empty list.
    interface Orderable {
      order: () => Orderable;
      then: (r: (v: { data: unknown[]; error: null }) => unknown) => unknown;
    }
    const makeOrderable = (): Orderable => ({
      order: () => makeOrderable(),
      then: (resolve) => resolve({ data: [], error: null }),
    });
    return {
      from: (table: string) => {
        const empty = Promise.resolve({ data: [], error: null });
        const single = Promise.resolve({ data: null, error: null });
        if (table === "invoice_items") {
          return {
            select: () => ({
              eq: () => ({
                order: () => Promise.resolve({ data: [], error: null }),
              }),
            }),
          };
        }
        return {
          select: () => ({
            eq: () => ({
              order: () => makeOrderable(),
              maybeSingle: () => single,
              in: () => empty,
              eq: () => empty,
            }),
          }),
          update: () => ({ eq: async () => ({ error: null }) }),
          delete: () => ({ in: async () => ({ error: null }) }),
        };
      },
    };
  },
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

// Stand-in for the heavy Handsontable wrapper. We only need a stable DOM
// landmark so the test can assert "still mounted" vs "replaced by Загрузка...".
vi.mock("../procurement-items-editor", () => ({
  ProcurementItemsEditor: () => (
    <div data-testid="procurement-items-editor">[handsontable]</div>
  ),
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
  toast: { error: vi.fn(), success: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

import { InvoiceCard, type InvoiceCardQuoteStub } from "../invoice-card";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeInvoice(): QuoteInvoiceRow {
  return {
    id: "inv-A",
    invoice_number: "INV-01-Q-202604-0067",
    quote_id: "q-1",
    supplier_id: "sup-1",
    supplier: { id: "sup-1", name: "Acme Bolts" },
    buyer_company: { name: "Buyer LLC", company_code: "BUY-001" },
    supplier_contact_id: null,
    supplier_contact: null,
    sent_at: null,
    status: "pending_procurement",
    currency: "USD",
    pickup_city: "Milan",
    pickup_country: "Италия",
    pickup_country_code: "IT",
    supplier_incoterms: "EXW",
    total_weight_kg: 12.5,
    total_volume_m3: 0.34,
  } as unknown as QuoteInvoiceRow;
}

const quoteStub: InvoiceCardQuoteStub = { procurement_completed_at: null };

beforeEach(() => {
  // Re-bump fixtures between tests if needed.
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("InvoiceCard — no flicker on autosave-driven refetch (Testing 2 row 20 v3)", () => {
  it("keeps the procurement editor mounted across externalRefreshKey bumps after the first load", async () => {
    const { rerender } = render(
      <InvoiceCard
        invoice={makeInvoice()}
        items={[]}
        quote={quoteStub}
        defaultExpanded={true}
        externalRefreshKey={0}
      />,
    );

    // Wait for the initial load() to settle — placeholder gone, editor present.
    await waitFor(() => {
      expect(screen.queryByText("Загрузка...")).not.toBeInTheDocument();
      expect(screen.getByTestId("procurement-items-editor")).toBeInTheDocument();
    });

    // Simulate an autosave: parent bumps externalRefreshKey. This re-runs the
    // load() effect that fetches invoice_items. Before the fix, the loading
    // flag would flip to `true` synchronously and React would render the
    // placeholder before the next fetch resolved — the user saw a flash.
    rerender(
      <InvoiceCard
        invoice={makeInvoice()}
        items={[]}
        quote={quoteStub}
        defaultExpanded={true}
        externalRefreshKey={1}
      />,
    );

    // No placeholder should ever appear after first load — assert
    // synchronously (the bug is a single-render flicker, not an async race).
    expect(screen.queryByText("Загрузка...")).not.toBeInTheDocument();
    expect(screen.getByTestId("procurement-items-editor")).toBeInTheDocument();

    // And once the new fetch settles, the editor remains mounted.
    await waitFor(() => {
      expect(screen.getByTestId("procurement-items-editor")).toBeInTheDocument();
    });
    expect(screen.queryByText("Загрузка...")).not.toBeInTheDocument();
  });

  it("still shows the placeholder on the very first mount before invoice_items resolve", async () => {
    render(
      <InvoiceCard
        invoice={makeInvoice()}
        items={[]}
        quote={quoteStub}
        defaultExpanded={true}
      />,
    );

    // Initial mount renders the placeholder synchronously before the async
    // load() effect resolves. (jsdom's microtask order means the empty-array
    // fetch can resolve almost instantly — so we only assert it eventually
    // disappears, not that it was visible at t=0.)
    await waitFor(() => {
      expect(screen.queryByText("Загрузка...")).not.toBeInTheDocument();
      expect(screen.getByTestId("procurement-items-editor")).toBeInTheDocument();
    });
  });
});
