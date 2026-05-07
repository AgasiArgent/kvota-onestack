// @vitest-environment jsdom
/**
 * СтМоз C9 (UX-часть, Bug 4) — financial aggregate columns
 * (Кол-во КП / Выручка / Спец / Прибыль) must be hidden in the
 * "Подробно" (expanded) view for procurement / logistics / customs
 * roles. They execute later pipeline stages where these don't make
 * sense, and the empty cells just confuse them.
 *
 * The non-financial expanded columns (Менеджер, Посл. КП, Статус)
 * stay visible for everyone.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import type { CustomerListItem, CustomerFinancials } from "@/entities/customer";

// ---------------------------------------------------------------------------
// In-memory localStorage stub. The vitest 4 jsdom default `window.localStorage`
// in this project is incomplete (only `getItem`/`setItem` work; `removeItem`,
// `clear`, etc. are not implemented). The expanded-view toggle reads from
// localStorage on mount, so we install a minimal fake before each test.
// ---------------------------------------------------------------------------

function installLocalStorageStub() {
  const store = new Map<string, string>();
  const fake: Storage = {
    get length() {
      return store.size;
    },
    clear() {
      store.clear();
    },
    getItem(key: string) {
      return store.has(key) ? (store.get(key) as string) : null;
    },
    key(index: number) {
      return Array.from(store.keys())[index] ?? null;
    },
    removeItem(key: string) {
      store.delete(key);
    },
    setItem(key: string, value: string) {
      store.set(key, String(value));
    },
  };
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: fake,
  });
  return fake;
}

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
  useSearchParams: () => ({
    toString: () => "",
    get: () => null,
  }),
}));

vi.mock("../create-customer-dialog", () => ({
  CreateCustomerDialog: () => null,
}));

import { CustomersTable } from "../customers-table";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const customer: CustomerListItem = {
  id: "cust-1",
  name: "ООО Ромашка",
  inn: "7700000000",
  status: "active",
  created_at: "2026-04-01T10:00:00Z",
  manager: { full_name: "Иванова А." },
  quotes_count: 3,
  last_quote_date: "2026-04-20T10:00:00Z",
};

const financials = new Map<string, CustomerFinancials>([
  [
    "cust-1",
    {
      customer_id: "cust-1",
      quotes_count: 3,
      last_quote_date: "2026-04-20T10:00:00Z",
      specs_count: 1,
      revenue_usd: 12000,
      profit_usd: 2400,
    },
  ],
]);

function renderTable(userRoles: string[]) {
  // localStorage is the only thing toggling expanded mode — preset before render.
  window.localStorage.setItem("customers-view-mode", "expanded");

  return render(
    <CustomersTable
      initialData={[customer]}
      initialTotal={1}
      orgId="org-1"
      financials={financials}
      userRoles={userRoles}
    />,
  );
}

beforeEach(() => {
  installLocalStorageStub();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests — financial columns visible for sales-side roles
// ---------------------------------------------------------------------------

describe("CustomersTable — financial columns by role (СтМоз C9)", () => {
  it.each([["admin"], ["sales"], ["quote_controller"], ["finance"], ["top_manager"]])(
    "shows financial columns for role %s",
    (role) => {
      renderTable([role]);

      // Header chips
      expect(
        screen.getByRole("columnheader", { name: "Выручка" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("columnheader", { name: "Прибыль" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("columnheader", { name: "Спец." }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("columnheader", { name: "КП" }),
      ).toBeInTheDocument();
    },
  );

  // -------------------------------------------------------------------------
  // Procurement / logistics / customs — financial columns absent
  // -------------------------------------------------------------------------

  it.each([
    ["procurement"],
    ["procurement_senior"],
    ["head_of_procurement"],
    ["logistics"],
    ["head_of_logistics"],
    ["customs"],
  ])("hides financial columns for role %s", (role) => {
    renderTable([role]);

    expect(
      screen.queryByRole("columnheader", { name: "Выручка" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("columnheader", { name: "Прибыль" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("columnheader", { name: "Спец." }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("columnheader", { name: "КП" }),
    ).not.toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Non-financial expanded columns stay for everyone — sanity check
  // -------------------------------------------------------------------------

  it("keeps Менеджер / Посл. КП / Статус headers for procurement role", () => {
    renderTable(["procurement"]);

    expect(
      screen.getByRole("columnheader", { name: "Менеджер" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: "Посл. КП" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: "Статус" }),
    ).toBeInTheDocument();
  });

  it("keeps Менеджер / Посл. КП / Статус headers for sales role", () => {
    renderTable(["sales"]);

    expect(
      screen.getByRole("columnheader", { name: "Менеджер" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: "Посл. КП" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: "Статус" }),
    ).toBeInTheDocument();
  });
});
