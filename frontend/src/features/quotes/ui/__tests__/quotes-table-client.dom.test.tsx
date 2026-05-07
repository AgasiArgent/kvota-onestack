// @vitest-environment jsdom
/**
 * СтМоз Q6 (UX-часть, Bug 5) — financial aggregate columns (СУММА,
 * ПРИБЫЛЬ) must be hidden in the /quotes list for procurement /
 * logistics / customs roles. They execute later pipeline stages
 * where these aren't in scope, and the empty cells just confuse
 * them. Версия stays for everyone.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import type { QuoteListItem } from "@/entities/quote";

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

// Heavy DataTable substrate is replaced with a minimal stub that just
// renders one <th> per column — enough to assert presence/absence of
// the financial columns by header label.
vi.mock("@/shared/ui/data-table", async () => {
  const actual = await vi.importActual<typeof import("@/shared/ui/data-table")>(
    "@/shared/ui/data-table",
  );
  type StubColumn = { key: string; label: string };
  type StubProps = { columns: readonly StubColumn[] };
  return {
    ...actual,
    DataTable: ({ columns }: StubProps) => (
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} data-testid={`col-${c.key}`}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
      </table>
    ),
  };
});

vi.mock("../create-quote-dialog", () => ({
  CreateQuoteDialog: () => null,
}));

import { QuotesTableClient } from "../quotes-table-client";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const filterOptions = {
  customers: [],
  managers: [],
  procurementManagers: [],
  brands: [],
  statuses: [],
  participants: {
    sales: [],
    procurement: [],
    logistics: [],
    customs: [],
  },
};

const quotes: readonly QuoteListItem[] = [];

function renderTable(userRoles: string[]) {
  return render(
    <QuotesTableClient
      rows={quotes}
      total={0}
      page={1}
      pageSize={50}
      filterOptions={filterOptions}
      userRoles={userRoles}
      userId="user-1"
      orgId="org-1"
      salesGroupId={null}
      actionStatuses={[]}
    />,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests — financial columns visible for sales-side roles
// ---------------------------------------------------------------------------

describe("QuotesTableClient — financial columns by role (СтМоз Q6)", () => {
  it.each([["admin"], ["sales"], ["quote_controller"], ["finance"], ["top_manager"]])(
    "shows СУММА and ПРИБЫЛЬ columns for role %s",
    (role) => {
      renderTable([role]);

      expect(screen.getByTestId("col-amount")).toHaveTextContent("Сумма");
      expect(screen.getByTestId("col-profit")).toHaveTextContent("Прибыль");
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
  ])("hides СУММА and ПРИБЫЛЬ columns for role %s", (role) => {
    renderTable([role]);

    expect(screen.queryByTestId("col-amount")).not.toBeInTheDocument();
    expect(screen.queryByTestId("col-profit")).not.toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Версия column is not financial — stays for everyone
  // -------------------------------------------------------------------------

  it("keeps Версия column for procurement role", () => {
    renderTable(["procurement"]);

    expect(screen.getByTestId("col-version")).toHaveTextContent("Версия");
  });

  it("keeps Версия column for sales role", () => {
    renderTable(["sales"]);

    expect(screen.getByTestId("col-version")).toHaveTextContent("Версия");
  });
});
