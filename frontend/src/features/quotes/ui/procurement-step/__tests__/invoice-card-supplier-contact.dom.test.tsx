// @vitest-environment jsdom
/**
 * Testing 2 row 25 — supplier-contact picker on the КПП card.
 *
 * The procurement user must be able to swap the named supplier contact
 * inline on the card (no detour to the supplier page). Mirrors the picker
 * in `invoice-create-modal.tsx`. This test pins three contracts:
 *
 *   1. The contact list is fetched scoped to the КПП's `supplier_id`.
 *   2. The currently-selected contact's реквизиты (position/phone/email)
 *      render below the picker so the user sees what they picked at a
 *      glance — the trigger only shows the name.
 *   3. Choosing a different contact calls Supabase
 *      `update({ supplier_contact_id: <id> })` for the КПП row.
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { QuoteInvoiceRow } from "@/entities/quote/queries";

// ---------------------------------------------------------------------------
// Mocks (vi.mock is hoisted — must precede component import)
// ---------------------------------------------------------------------------

const { supplierContactsState, invoicesUpdateState } = vi.hoisted(() => {
  return {
    supplierContactsState: {
      rows: [] as Array<Record<string, unknown>>,
      lastSupplierId: null as string | null,
    },
    invoicesUpdateState: {
      lastUpdate: null as Record<string, unknown> | null,
      lastInvoiceId: null as string | null,
    },
  };
});

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    from: (table: string) => {
      if (table === "supplier_contacts") {
        const settle = () =>
          Promise.resolve({ data: supplierContactsState.rows, error: null });
        return {
          select: () => ({
            eq: (_col: string, val: string) => {
              supplierContactsState.lastSupplierId = val;
              return {
                order: () => ({ order: settle }),
              };
            },
          }),
        };
      }
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
      // Generic fallback for vat_rates_by_country, etc.
      return {
        select: () => ({
          eq: () => ({
            order: () => Promise.resolve({ data: [], error: null }),
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

// SearchableCombobox renders via @base-ui Popover (portal-based) which jsdom
// can't reliably drive via fireEvent.click. Replace with a plain <select>
// that exercises the same value/onChange contract — same pattern used in
// `invoice-create-modal-address-contact.dom.test.tsx`.
vi.mock("@/shared/ui/searchable-combobox", () => ({
  SearchableCombobox: <T extends { id: string }>({
    value,
    onChange,
    items,
    getLabel,
    ariaLabel,
    disabled,
  }: {
    value: string | null;
    onChange: (v: string | null) => void;
    items: T[];
    getLabel: (i: T) => string;
    ariaLabel?: string;
    disabled?: boolean;
  }) => (
    <select
      aria-label={ariaLabel}
      value={value ?? ""}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value || null)}
    >
      <option value="">—</option>
      {items.map((item) => (
        <option key={item.id} value={item.id}>
          {getLabel(item)}
        </option>
      ))}
    </select>
  ),
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

const CONTACT_A = {
  id: "c-1",
  supplier_id: "sup-1",
  name: "Иван Петров",
  position: "Менеджер по продажам",
  email: "ivan@acme.tr",
  phone: "+90 555 111 22 33",
  is_primary: true,
  notes: null,
  created_at: "",
  updated_at: null,
};
const CONTACT_B = {
  id: "c-2",
  supplier_id: "sup-1",
  name: "Мария Иванова",
  position: "Бухгалтер",
  email: "maria@acme.tr",
  phone: "+90 555 444 55 66",
  is_primary: false,
  notes: null,
  created_at: "",
  updated_at: null,
};

function makeInvoice(
  overrides: Partial<QuoteInvoiceRow> = {},
): QuoteInvoiceRow {
  return {
    id: "inv-A",
    invoice_number: "INV-01-Q-202604-0067",
    quote_id: "q-1",
    supplier_id: "sup-1",
    supplier: { id: "sup-1", name: "Acme Bolts" },
    buyer_company: { name: "Buyer LLC", company_code: "BUY-001" },
    supplier_contact_id: "c-1",
    supplier_contact: {
      id: "c-1",
      name: "Иван Петров",
      position: "Менеджер по продажам",
      email: "ivan@acme.tr",
      phone: "+90 555 111 22 33",
    },
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

beforeEach(() => {
  supplierContactsState.lastSupplierId = null;
  supplierContactsState.rows = [
    CONTACT_A as unknown as Record<string, unknown>,
    CONTACT_B as unknown as Record<string, unknown>,
  ];
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

describe("InvoiceCard — supplier-contact inline edit (Testing 2 row 25)", () => {
  it("fetches contacts scoped to the КПП's supplier_id", async () => {
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
    await waitFor(() => {
      expect(supplierContactsState.lastSupplierId).toBe("sup-1");
    });
  });

  it("renders the supplier-contact picker with the current selection + реквизиты", async () => {
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
    // Picker is rendered with the current contact preselected.
    const select = (await screen.findByLabelText(
      "Контакт поставщика",
    )) as HTMLSelectElement;
    expect(select.value).toBe("c-1");
    // Section wrapper carries the existing testid for hooks/inspection.
    expect(screen.getByTestId("invoice-card-supplier-contact")).toBeInTheDocument();
    // Реквизиты of the selected contact stay visible below the picker.
    expect(
      screen.getByText(/Менеджер по продажам/i),
    ).toBeInTheDocument();
  });

  it("PATCHes invoices.supplier_contact_id when the user picks a different contact", async () => {
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
    // Wait for contacts to load so both options are in the select.
    await waitFor(() => {
      expect(supplierContactsState.lastSupplierId).toBe("sup-1");
    });
    const select = screen.getByLabelText("Контакт поставщика") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "c-2" } });

    await waitFor(() => {
      expect(invoicesUpdateState.lastInvoiceId).toBe("inv-A");
    });
    expect(invoicesUpdateState.lastUpdate).toEqual({
      supplier_contact_id: "c-2",
    });
  });

  it("allows deselecting (null) the contact", async () => {
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
    await waitFor(() => {
      expect(supplierContactsState.lastSupplierId).toBe("sup-1");
    });
    const select = screen.getByLabelText("Контакт поставщика") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "" } });

    await waitFor(() => {
      expect(invoicesUpdateState.lastInvoiceId).toBe("inv-A");
    });
    expect(invoicesUpdateState.lastUpdate).toEqual({
      supplier_contact_id: null,
    });
  });
});
