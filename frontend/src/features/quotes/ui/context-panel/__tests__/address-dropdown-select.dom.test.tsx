// @vitest-environment jsdom
/**
 * Testing 2 row 24 (FB 2026-05-14) — «Адрес доставки» dropdown on quote info
 * panel used to read only from `customer_delivery_addresses`, leaving МОП
 * users staring at «Нет адресов» whenever the customer's addresses lived on
 * the `customers` row itself (legal/actual/postal text fields +
 * `warehouse_addresses` jsonb array). This dom test pins the merged source
 * behavior:
 *   - delivery rows keep their own name
 *   - warehouse jsonb entries surface as "Склад: <label>"
 *   - legal/actual/postal text fields surface as «Юридический» /
 *     «Фактический» / «Почтовый»
 *   - duplicate address strings dedupe (case-insensitive, trimmed)
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mocks (vi.mock hoists — declared before component import)
// ---------------------------------------------------------------------------

interface DeliveryRow {
  id: string;
  name: string | null;
  address: string;
  is_default: boolean | null;
}
interface CustomerRow {
  legal_address: string | null;
  actual_address: string | null;
  postal_address: string | null;
  warehouse_addresses: Array<{ label?: string; address?: string }> | null;
}

const dbState: {
  deliveryRows: DeliveryRow[];
  customer: CustomerRow | null;
} = {
  deliveryRows: [],
  customer: null,
};

function makeDeliveryChain() {
  // Chain: select().eq().order().order() — the final .order() call is awaited
  // as a thenable. Component code does `const [a, b] = await Promise.all([...])`
  // so each chain endpoint must look like a Promise resolving to { data, error }.
  const finalPromise = Promise.resolve({
    data: dbState.deliveryRows,
    error: null,
  });
  const builder: Record<string, unknown> = {
    select: () => builder,
    eq: () => builder,
    order: () => orderable,
  };
  // After the first .order() we expose a thenable that ALSO has .order() so
  // the second .order() call works. Both yield the same final promise.
  const orderable: Record<string, unknown> = {
    order: () => orderable,
    then: finalPromise.then.bind(finalPromise),
    catch: finalPromise.catch.bind(finalPromise),
    finally: finalPromise.finally.bind(finalPromise),
  };
  return builder;
}

function makeCustomerChain() {
  // Chain: select().eq().maybeSingle() resolves to { data, error }.
  const builder = {
    select: () => builder,
    eq: () => builder,
    maybeSingle: () =>
      Promise.resolve({ data: dbState.customer, error: null }),
  };
  return builder;
}

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    from: (table: string) => {
      if (table === "customer_delivery_addresses") return makeDeliveryChain();
      if (table === "customers") return makeCustomerChain();
      // Fallback empty chain
      return makeDeliveryChain();
    },
    auth: {
      getSession: async () => ({ data: { session: null } }),
    },
  }),
}));

const patchQuoteMock = vi.fn(async (..._args: unknown[]) => undefined);
vi.mock("@/entities/quote/mutations", () => ({
  patchQuote: (...args: unknown[]) => patchQuoteMock(...args),
}));

// The AddAddressForm pulls in heavy form deps; sentinel is enough for this
// test because we never click «Добавить адрес».
vi.mock("../add-address-form", () => ({
  AddAddressForm: () => null,
}));

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  },
}));

import { AddressDropdownSelect } from "../address-dropdown-select";

// ---------------------------------------------------------------------------
// Fixtures + helpers
// ---------------------------------------------------------------------------

function renderDropdown() {
  return render(
    <AddressDropdownSelect
      quoteId="q-1"
      customerId="cust-1"
      initialAddress={null}
    />,
  );
}

beforeEach(() => {
  dbState.deliveryRows = [];
  dbState.customer = null;
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AddressDropdownSelect — merged address sources (Testing 2 row 24)", () => {
  it("shows warehouses + legal/actual/postal addresses from customers row when delivery table is empty", async () => {
    dbState.deliveryRows = [];
    dbState.customer = {
      legal_address: "111677, г Москва, ул Маресьева, д 6",
      actual_address: "Фактический адрес, Москва",
      postal_address: null,
      warehouse_addresses: [
        { label: "Химки", address: "Россия, Химки, ул. Панфилова, 37" },
      ],
    };

    renderDropdown();
    fireEvent.click(screen.getByRole("button"));

    // Wait for fetch to resolve and items to render.
    await waitFor(() => {
      expect(
        screen.getByText("Россия, Химки, ул. Панфилова, 37"),
      ).toBeTruthy();
    });
    expect(screen.getByText("Склад: Химки")).toBeTruthy();
    expect(
      screen.getByText("111677, г Москва, ул Маресьева, д 6"),
    ).toBeTruthy();
    expect(screen.getByText("Юридический")).toBeTruthy();
    expect(screen.getByText("Фактический адрес, Москва")).toBeTruthy();
    expect(screen.getByText("Фактический")).toBeTruthy();
    // postal_address was null — must not appear.
    expect(screen.queryByText("Почтовый")).toBeNull();
    // «Нет адресов» empty state must NOT appear.
    expect(screen.queryByText(/Нет адресов/i)).toBeNull();
  });

  it("merges delivery rows with customer addresses and dedupes by trimmed/lowercased address", async () => {
    dbState.deliveryRows = [
      {
        id: "dlv-1",
        name: "Основной склад",
        address: "Россия, Химки, ул. Панфилова, 37",
        is_default: true,
      },
    ];
    dbState.customer = {
      legal_address: "Юр. адрес ООО",
      actual_address: null,
      postal_address: null,
      // Same address as the delivery row, but with different casing / spaces.
      // Must dedupe to a single entry (the delivery row wins because it came
      // first in the merge order).
      warehouse_addresses: [
        { label: "Химки", address: "  россия, химки, ул. панфилова, 37  " },
      ],
    };

    renderDropdown();
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(screen.getByText("Основной склад")).toBeTruthy();
    });
    // The shared address string appears once across both sources.
    const matches = screen.getAllByText("Россия, Химки, ул. Панфилова, 37");
    expect(matches.length).toBe(1);
    // Warehouse-prefixed name must NOT appear since it was deduped out.
    expect(screen.queryByText("Склад: Химки")).toBeNull();
    // Legal address still appears as its own entry.
    expect(screen.getByText("Юр. адрес ООО")).toBeTruthy();
    expect(screen.getByText("Юридический")).toBeTruthy();
  });

  it("renders «Нет адресов» when neither table has any address", async () => {
    dbState.deliveryRows = [];
    dbState.customer = {
      legal_address: null,
      actual_address: null,
      postal_address: null,
      warehouse_addresses: null,
    };

    renderDropdown();
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(screen.getByText(/Нет адресов/i)).toBeTruthy();
    });
  });
});
