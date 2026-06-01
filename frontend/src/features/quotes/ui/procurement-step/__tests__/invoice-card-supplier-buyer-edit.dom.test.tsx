// @vitest-environment jsdom
/**
 * Testing 2 row 91 — supplier + buyer_company are editable on the КПП card.
 *
 * Before the <InvoiceFieldsForm> unification, supplier_id and buyer_company_id
 * were SET at КПП creation but DISPLAY-ONLY on the card — they drifted because
 * the create modal and the card each owned their own field form. Both now
 * render the same shared component, so these two fields are editable in EDIT
 * mode too. This test pins:
 *
 *   1. The Поставщик and Компания-покупатель pickers render on the card and
 *      reflect the КПП's current supplier_id / buyer_company_id.
 *   2. Changing the buyer PATCHes invoices.buyer_company_id.
 *   3. Changing the supplier PATCHes invoices.supplier_id AND resets
 *      supplier_contact_id to null in the SAME update (the old contact belongs
 *      to the previous supplier), and surfaces the inline reset warning.
 *   4. When the КПП procurement is completed (locked), the pickers are
 *      disabled — a locked edit must go through the unlock → approval flow.
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
// that exercises the same value/onChange contract — same pattern the sibling
// supplier-contact + create-modal dom tests use.
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

const SUPPLIERS = [
  { id: "sup-1", name: "Acme Bolts", country: "Турция" },
  { id: "sup-2", name: "Globex Fasteners", country: "Германия" },
];

const BUYERS = [
  { id: "buy-1", name: "Buyer LLC", company_code: "BUY-001" },
  { id: "buy-2", name: "Trade House", company_code: "BUY-002" },
];

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

function makeInvoice(
  overrides: Partial<QuoteInvoiceRow> = {},
): QuoteInvoiceRow {
  return {
    id: "inv-A",
    invoice_number: "INV-01-Q-202604-0091",
    quote_id: "q-1",
    supplier_id: "sup-1",
    buyer_company_id: "buy-1",
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

beforeEach(() => {
  supplierContactsState.lastSupplierId = null;
  supplierContactsState.rows = [
    CONTACT_A as unknown as Record<string, unknown>,
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

describe("InvoiceCard — supplier + buyer editable in EDIT mode (Testing 2 row 91)", () => {
  function renderCard(invoice = makeInvoice()) {
    return render(
      <InvoiceCard
        invoice={invoice}
        items={[]}
        quote={quoteStub}
        invoiceItems={[]}
        coverageSummaryByItem={{}}
        defaultExpanded={true}
        suppliers={SUPPLIERS}
        buyerCompanies={BUYERS}
      />,
    );
  }

  it("renders the Поставщик and Компания-покупатель pickers with the current selection", async () => {
    renderCard();
    const supplier = (await screen.findByLabelText(
      "Поставщик",
    )) as HTMLSelectElement;
    const buyer = (await screen.findByLabelText(
      "Компания-покупатель",
    )) as HTMLSelectElement;
    expect(supplier.value).toBe("sup-1");
    expect(buyer.value).toBe("buy-1");
  });

  it("PATCHes invoices.buyer_company_id when the user changes the buyer", async () => {
    renderCard();
    const buyer = (await screen.findByLabelText(
      "Компания-покупатель",
    )) as HTMLSelectElement;
    fireEvent.change(buyer, { target: { value: "buy-2" } });

    await waitFor(() => {
      expect(invoicesUpdateState.lastInvoiceId).toBe("inv-A");
    });
    expect(invoicesUpdateState.lastUpdate).toEqual({ buyer_company_id: "buy-2" });
  });

  it("PATCHes supplier_id AND resets supplier_contact_id when the supplier changes", async () => {
    renderCard();
    const supplier = (await screen.findByLabelText(
      "Поставщик",
    )) as HTMLSelectElement;
    fireEvent.change(supplier, { target: { value: "sup-2" } });

    await waitFor(() => {
      expect(invoicesUpdateState.lastInvoiceId).toBe("inv-A");
    });
    // Supplier change must clear the old supplier's contact in the same PATCH.
    expect(invoicesUpdateState.lastUpdate).toMatchObject({
      supplier_id: "sup-2",
      supplier_contact_id: null,
    });
  });

  it("shows the inline contact-reset warning after a supplier change", async () => {
    renderCard();
    const supplier = (await screen.findByLabelText(
      "Поставщик",
    )) as HTMLSelectElement;
    fireEvent.change(supplier, { target: { value: "sup-2" } });

    await waitFor(() => {
      expect(screen.getByText(/Контакт сброшен/i)).toBeInTheDocument();
    });
  });

  it("does not render the editable supplier/buyer pickers when the КПП is locked (procurement completed → unlock flow)", async () => {
    // When procurement is completed the card collapses the editable field
    // section to a read-only summary and surfaces the unlock → approval flow;
    // the supplier/buyer pickers must not appear as editable inputs (a locked
    // edit goes through ProcurementUnlockButton, not these fields).
    renderCard(
      makeInvoice({
        procurement_completed_at: "2026-05-30T10:00:00Z",
      } as Partial<QuoteInvoiceRow>),
    );
    await waitFor(() => {
      expect(screen.queryByLabelText("Поставщик")).toBeNull();
    });
    expect(screen.queryByLabelText("Компания-покупатель")).toBeNull();
  });
});

describe("InvoiceFieldsForm — locked prop disables every field", () => {
  it("renders all pickers disabled when locked=true", async () => {
    const { InvoiceFieldsForm } = await import("../invoice-fields-form");
    render(
      <InvoiceFieldsForm
        mode="edit"
        locked
        value={{
          supplierId: "sup-1",
          buyerCompanyId: "buy-1",
          countryCode: null,
          city: "",
          pickupAddress: "",
          supplierContactId: "c-1",
          incoterms: "",
          currency: "USD",
        }}
        onFieldSave={() => {}}
        suppliers={SUPPLIERS}
        buyerCompanies={BUYERS}
      />,
    );
    const supplier = (await screen.findByLabelText(
      "Поставщик",
    )) as HTMLSelectElement;
    const buyer = screen.getByLabelText(
      "Компания-покупатель",
    ) as HTMLSelectElement;
    const incoterms = screen.getByLabelText(
      "Условия поставки",
    ) as HTMLSelectElement;
    const currency = screen.getByLabelText("Валюта") as HTMLSelectElement;
    expect(supplier.disabled).toBe(true);
    expect(buyer.disabled).toBe(true);
    expect(incoterms.disabled).toBe(true);
    expect(currency.disabled).toBe(true);
  });
});
