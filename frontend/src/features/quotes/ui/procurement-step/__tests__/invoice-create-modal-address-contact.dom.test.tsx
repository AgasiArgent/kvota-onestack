// @vitest-environment jsdom
/**
 * Testing 2 row 21 — pickup address + supplier-contact picker in the
 * «Создать КП поставщику» modal.
 *
 * Both fields are mandatory before КПП creation, and both must flow through
 * `createInvoice` so the supplier and downstream consumers (logistics, КПП
 * print) see them. SSR-style coverage in `invoice-create-modal.test.tsx`
 * confirms the module loads with its new imports; the jsdom substrate here
 * is needed because the supplier-contact useEffect, the validate gate, and
 * the submit handler all only run in a real DOM.
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mocks (vi.mock is hoisted — declared before component import)
//
// Use vi.hoisted so the mock fns are defined BEFORE vi.mock's factory closure
// runs. Plain `const` declarations at module top-level still come after the
// hoisted mock setup, which breaks the factory.
// ---------------------------------------------------------------------------

// Supplier contacts are now read via an inline browser-Supabase SELECT inside
// the modal (the server-side `fetchSupplierContacts` import was banned in
// Client Components — Turbopack build error). Tests control the returned rows
// via `supplierContactsState.rows` and inspect what supplier_id was queried
// via `supplierContactsState.lastSupplierId`.
const {
  createInvoiceMock,
  assignItemsToInvoiceMock,
  supplierContactsState,
} = vi.hoisted(() => {
  return {
    createInvoiceMock: vi.fn(async () => ({
      id: "inv-1",
      invoice_number: "INV-01-Q-202604-0001",
      bypass_reason: null,
    })),
    assignItemsToInvoiceMock: vi.fn(async () => undefined),
    supplierContactsState: {
      rows: [] as Array<Record<string, unknown>>,
      lastSupplierId: null as string | null,
    },
  };
});

vi.mock("@/entities/quote/mutations", () => ({
  createInvoice: createInvoiceMock,
  assignItemsToInvoice: assignItemsToInvoiceMock,
}));

vi.mock("@/entities/invoice/queries", () => ({
  fetchSupplierVatRate: vi.fn(async () => null),
}));

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: async () => ({ data: { session: null } }) },
    from: (table: string) => {
      if (table === "supplier_contacts") {
        // Chain: .select("*").eq("supplier_id", id).order("is_primary").order("name")
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
      return {
        select: () => ({
          eq: () => ({ in: async () => ({ data: [], error: null }) }),
        }),
        update: () => ({ in: async () => ({ data: [], error: null }) }),
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

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  },
}));

// CityAutocomplete pulls in HERE-Geocode network code that's unrelated to
// this test. Replace with a plain input so the city field still exists
// without making any HTTP requests.
vi.mock("@/shared/ui/geo", async () => {
  const actual = await vi.importActual<typeof import("@/shared/ui/geo")>(
    "@/shared/ui/geo"
  );
  return {
    ...actual,
    CityAutocomplete: ({
      value,
      onChange,
      ariaLabel,
    }: {
      value: string;
      onChange: (v: string) => void;
      ariaLabel?: string;
    }) => (
      <input
        aria-label={ariaLabel}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    ),
    CountryCombobox: ({
      value,
      onChange,
      ariaLabel,
    }: {
      value: string | null;
      onChange: (v: string | null) => void;
      ariaLabel?: string;
    }) => (
      <input
        aria-label={ariaLabel}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
      />
    ),
  };
});

// SearchableCombobox renders via @base-ui Popover (a portal-based Dialog) which
// jsdom can't reliably trigger via fireEvent.click. Replace with a plain
// <select> that exercises the same value/onChange contract. Tests below
// pick a supplier/buyer/contact by emitting `change` on the select rather
// than crawling the popover portal.
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

import { InvoiceCreateModal } from "../invoice-create-modal";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const SUPPLIER = { id: "sup-1", name: "Acme Bolts", country: "Турция" };
const BUYER = { id: "buy-1", name: "Buyer LLC", company_code: "BUY-001" };
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

function renderModal() {
  return render(
    <InvoiceCreateModal
      open={true}
      onClose={() => {}}
      quoteId="q-1"
      idnQuote="Q-202604-0001"
      selectedItems={[]}
      suppliers={[SUPPLIER]}
      buyerCompanies={[BUYER]}
    />
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("InvoiceCreateModal — pickup address + supplier-contact picker (Testing 2 row 21)", () => {
  beforeEach(() => {
    createInvoiceMock.mockClear();
    assignItemsToInvoiceMock.mockClear();
    supplierContactsState.lastSupplierId = null;
    supplierContactsState.rows = [
      CONTACT_A as unknown as Record<string, unknown>,
      CONTACT_B as unknown as Record<string, unknown>,
    ];
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders the «Адрес забора груза» input (Testing 2 row 25: optional)", () => {
    renderModal();
    // Testing 2 row 25 (FB 2026-05-14): label no longer carries the required
    // asterisk — the field is optional. Input must still be present + empty.
    const input = screen.getByLabelText(/Адрес забора груза/i);
    expect(input).toBeTruthy();
    expect((input as HTMLInputElement).value).toBe("");
  });

  it("loads supplier contacts after a supplier is picked", async () => {
    renderModal();
    const supplierSelect = screen.getByLabelText("Поставщик") as HTMLSelectElement;
    fireEvent.change(supplierSelect, { target: { value: "sup-1" } });
    await waitFor(() => {
      expect(supplierContactsState.lastSupplierId).toBe("sup-1");
    });
  });

  it("blocks submit on missing contact but allows empty pickup_address (Testing 2 row 25)", async () => {
    // Testing 2 row 25 (FB 2026-05-14): pickup_address is now optional, so a
    // blank address alone must no longer block submit. The named contact is
    // still mandatory — submit fails only on the contact field.
    supplierContactsState.rows = [];
    renderModal();
    fireEvent.change(screen.getByLabelText("Поставщик"), {
      target: { value: "sup-1" },
    });
    fireEvent.change(screen.getByLabelText("Компания-покупатель"), {
      target: { value: "buy-1" },
    });
    await waitFor(() => {
      expect(supplierContactsState.lastSupplierId).toBe("sup-1");
    });

    fireEvent.click(screen.getByRole("button", { name: /Создать/i }));

    // Contact error must surface; pickup_address error must NOT appear.
    await waitFor(() => {
      expect(
        screen.getByText(/У поставщика нет контактов/i)
      ).toBeTruthy();
    });
    expect(
      screen.queryByText(/Укажите адрес забора груза/i)
    ).toBeNull();
    expect(createInvoiceMock).not.toHaveBeenCalled();
  });

  it("submits without pickup_address when only contact is provided (Testing 2 row 25)", async () => {
    renderModal();
    fireEvent.change(screen.getByLabelText("Поставщик"), {
      target: { value: "sup-1" },
    });
    fireEvent.change(screen.getByLabelText("Компания-покупатель"), {
      target: { value: "buy-1" },
    });

    await waitFor(() => {
      expect(supplierContactsState.lastSupplierId).toBe("sup-1");
    });
    await waitFor(() => {
      const contactSelect = screen.getByLabelText(
        "Контакт поставщика"
      ) as HTMLSelectElement;
      expect(contactSelect.value).toBe("c-1");
    });

    // Submit WITHOUT touching the pickup_address input.
    fireEvent.click(screen.getByRole("button", { name: /Создать/i }));

    await waitFor(() => {
      expect(createInvoiceMock).toHaveBeenCalledTimes(1);
    });
    const call = (createInvoiceMock.mock.calls[0] as unknown as [
      Record<string, unknown>,
    ])[0];
    expect(call.pickup_address).toBeUndefined();
    expect(call.supplier_contact_id).toBe("c-1");
  });

  it("submits pickup_address + supplier_contact_id to createInvoice when valid", async () => {
    renderModal();
    fireEvent.change(screen.getByLabelText("Поставщик"), {
      target: { value: "sup-1" },
    });
    fireEvent.change(screen.getByLabelText("Компания-покупатель"), {
      target: { value: "buy-1" },
    });

    // Wait for primary contact (CONTACT_A) to be auto-selected after the
    // contacts effect resolves.
    await waitFor(() => {
      expect(supplierContactsState.lastSupplierId).toBe("sup-1");
    });
    await waitFor(() => {
      // After fetch resolves, the contact <select> should reflect the
      // auto-picked primary (is_primary=true → CONTACT_A → "c-1").
      const contactSelect = screen.getByLabelText(
        "Контакт поставщика"
      ) as HTMLSelectElement;
      expect(contactSelect.value).toBe("c-1");
    });

    const addressInput = screen.getByLabelText(
      /Адрес забора груза/i
    ) as HTMLInputElement;
    fireEvent.change(addressInput, {
      target: { value: "ул. Промышленная, 12, склад 4" },
    });

    fireEvent.click(screen.getByRole("button", { name: /Создать/i }));

    await waitFor(() => {
      expect(createInvoiceMock).toHaveBeenCalledTimes(1);
    });
    const call = (createInvoiceMock.mock.calls[0] as unknown as [
      Record<string, unknown>,
    ])[0];
    expect(call.pickup_address).toBe("ул. Промышленная, 12, склад 4");
    // CONTACT_A is is_primary=true and ordered first, so it auto-selects.
    expect(call.supplier_contact_id).toBe("c-1");
  });
});
