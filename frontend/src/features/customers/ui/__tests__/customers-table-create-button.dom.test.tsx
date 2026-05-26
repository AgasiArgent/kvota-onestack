// @vitest-environment jsdom
/**
 * Testing 2 row 82 — РОЗ (head_of_procurement) reported missing
 * «Новый клиент» button on /customers. Root cause was that the
 * `CustomersTable` rendered the button unconditionally while the
 * sidebar entry was gated to sales-only, so РОЗ users had no link to
 * the page (and no role-aware contract on the button itself).
 *
 * Fix:
 *   1. `canCreateCustomer(roles)` helper in `shared/lib/roles.ts`
 *   2. `CustomersTable.canCreate` prop drives button visibility
 *   3. Sidebar entry widened to the same role set
 *
 * This file verifies the button visibility contract on the table
 * component. Sidebar tests live alongside `sidebar-menu.ts`.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import type { CustomerListItem, CustomerFinancials } from "@/entities/customer";

// ---------------------------------------------------------------------------
// localStorage stub — same as customers-table.dom.test.tsx. The jsdom default
// window.localStorage is incomplete and the expanded-mode toggle reads from
// it on mount.
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
// Mocks — must come before component import (vitest hoists vi.mock).
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
import { canCreateCustomer } from "@/shared/lib/roles";

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
  quotes_count: 0,
  last_quote_date: null,
};

const financials = new Map<string, CustomerFinancials>();

function renderTable(canCreate: boolean) {
  return render(
    <CustomersTable
      initialData={[customer]}
      initialTotal={1}
      orgId="org-1"
      financials={financials}
      userRoles={[]}
      canCreate={canCreate}
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
// Helper-level tests — canCreateCustomer role contract
// ---------------------------------------------------------------------------

describe("canCreateCustomer — role gate (Testing 2 row 82)", () => {
  it.each([
    ["admin"],
    ["top_manager"],
    ["sales"],
    ["head_of_sales"],
    ["procurement"],
    ["procurement_senior"],
    ["head_of_procurement"],
  ])("authorizes role %s", (role) => {
    expect(canCreateCustomer([role])).toBe(true);
  });

  it.each([
    ["logistics"],
    ["head_of_logistics"],
    ["customs"],
    ["head_of_customs"],
    ["finance"],
    ["quote_controller"],
    ["spec_controller"],
    ["currency_controller"],
    ["newbie"],
  ])("rejects role %s", (role) => {
    expect(canCreateCustomer([role])).toBe(false);
  });

  it("returns false for an empty role list", () => {
    expect(canCreateCustomer([])).toBe(false);
  });

  it("authorizes a user with mixed roles when any role qualifies", () => {
    expect(canCreateCustomer(["logistics", "head_of_procurement"])).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Component-level tests — button visibility honours the prop
// ---------------------------------------------------------------------------

describe("CustomersTable — «Новый клиент» button visibility", () => {
  it("renders the button when canCreate is true", () => {
    renderTable(true);
    expect(
      screen.getByRole("button", { name: /Новый клиент/ }),
    ).toBeInTheDocument();
  });

  it("hides the button when canCreate is false", () => {
    renderTable(false);
    expect(
      screen.queryByRole("button", { name: /Новый клиент/ }),
    ).not.toBeInTheDocument();
  });

  it("defaults to hidden when canCreate is omitted", () => {
    render(
      <CustomersTable
        initialData={[customer]}
        initialTotal={1}
        orgId="org-1"
        financials={financials}
        userRoles={[]}
      />,
    );
    expect(
      screen.queryByRole("button", { name: /Новый клиент/ }),
    ).not.toBeInTheDocument();
  });
});
