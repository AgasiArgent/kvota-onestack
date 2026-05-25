// @vitest-environment jsdom
/**
 * Testing 2 row 19 — split-table grouping ("Требует вашего действия /
 * Остальные") is replaced by a toolbar filter toggle ("Только требует
 * действия"). 6 testers rejected the persistent split as confusing.
 *
 * Spec:
 *   - Toggle off (default) → all rows handed to the table.
 *   - Toggle on → only rows whose workflow_status is in actionStatuses.
 *   - URL `?onlyAction=true` initializes the toggle as checked.
 *   - Clicking the toggle updates the URL (router.replace).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { QuoteListItem } from "@/entities/quote";

// ---------------------------------------------------------------------------
// Mocks (must come before component import — vitest hoists vi.mock)
// ---------------------------------------------------------------------------

const routerReplace = vi.fn();
const searchParamsState: { value: string } = { value: "" };

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    refresh: () => {},
    push: () => {},
    replace: routerReplace,
    back: () => {},
    forward: () => {},
    prefetch: () => {},
  }),
  useSearchParams: () => ({
    toString: () => searchParamsState.value,
    get: (key: string) =>
      new URLSearchParams(searchParamsState.value).get(key),
  }),
}));

/**
 * Stub DataTable so we can introspect the rows it was handed without pulling
 * in the full table substrate (useSearchParams, ResizeObserver, etc.). It
 * also renders the `toolbarFilter` slot so the checkbox is real and clickable.
 */
vi.mock("@/shared/ui/data-table", async () => {
  const actual = await vi.importActual<typeof import("@/shared/ui/data-table")>(
    "@/shared/ui/data-table",
  );
  type StubProps = {
    rows: readonly { id: string }[];
    total: number;
    toolbarFilter?: React.ReactNode;
  };
  return {
    ...actual,
    DataTable: ({ rows, total, toolbarFilter }: StubProps) => (
      <div>
        <div data-testid="toolbar-filter">{toolbarFilter}</div>
        <div data-testid="row-count">{rows.length}</div>
        <div data-testid="total">{total}</div>
        <ul data-testid="row-ids">
          {rows.map((r) => (
            <li key={r.id} data-testid={`row-${r.id}`}>
              {r.id}
            </li>
          ))}
        </ul>
      </div>
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

function makeQuote(id: string, status: string): QuoteListItem {
  return {
    id,
    idn_quote: `Q-${id}`,
    created_at: "2026-05-01T00:00:00Z",
    workflow_status: status,
    total_quote_currency: 100,
    total_profit_usd: 10,
    currency: "USD",
    customer: null,
    manager: null,
    version_count: 1,
    current_version: 1,
    brands: [],
    procurement_managers: [],
    logistics_user: null,
    customs_user: null,
  };
}

const quotes: readonly QuoteListItem[] = [
  makeQuote("a1", "pending_sales_review"), // actionable
  makeQuote("a2", "approved"), // actionable
  makeQuote("o1", "draft"), // not actionable
  makeQuote("o2", "completed"), // not actionable
];

const actionStatuses = ["pending_sales_review", "approved"];

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

function renderTable() {
  return render(
    <QuotesTableClient
      rows={quotes}
      total={quotes.length}
      page={1}
      pageSize={50}
      filterOptions={filterOptions}
      userRoles={["sales"]}
      userId="user-1"
      orgId="org-1"
      salesGroupId={null}
      actionStatuses={actionStatuses}
    />,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("QuotesTableClient — action toggle (Testing 2 row 19)", () => {
  beforeEach(() => {
    routerReplace.mockClear();
    searchParamsState.value = "";
  });

  afterEach(() => {
    cleanup();
  });

  it("renders the 'Только требует действия' toggle in the toolbar", () => {
    renderTable();

    expect(
      screen.getByRole("checkbox", { name: "Только требует действия" }),
    ).toBeInTheDocument();
  });

  it("shows all rows when toggle is off (default)", () => {
    renderTable();

    expect(screen.getByTestId("row-count")).toHaveTextContent("4");
    expect(screen.getByTestId("row-a1")).toBeInTheDocument();
    expect(screen.getByTestId("row-a2")).toBeInTheDocument();
    expect(screen.getByTestId("row-o1")).toBeInTheDocument();
    expect(screen.getByTestId("row-o2")).toBeInTheDocument();
  });

  it("shows only actionable rows when URL has ?onlyAction=true", () => {
    searchParamsState.value = "onlyAction=true";

    renderTable();

    expect(screen.getByTestId("row-count")).toHaveTextContent("2");
    expect(screen.getByTestId("row-a1")).toBeInTheDocument();
    expect(screen.getByTestId("row-a2")).toBeInTheDocument();
    expect(screen.queryByTestId("row-o1")).not.toBeInTheDocument();
    expect(screen.queryByTestId("row-o2")).not.toBeInTheDocument();
  });

  it("initializes the toggle as checked when URL has ?onlyAction=true", () => {
    searchParamsState.value = "onlyAction=true";

    renderTable();

    const checkbox = screen.getByRole("checkbox", { name: "Только требует действия" });
    expect(checkbox).toHaveAttribute("aria-checked", "true");
  });

  it("initializes the toggle as unchecked by default", () => {
    renderTable();

    const checkbox = screen.getByRole("checkbox", { name: "Только требует действия" });
    expect(checkbox).toHaveAttribute("aria-checked", "false");
  });

  it("updates the URL when the toggle is checked", async () => {
    const user = userEvent.setup();

    renderTable();

    await user.click(screen.getByRole("checkbox", { name: "Только требует действия" }));

    expect(routerReplace).toHaveBeenCalledWith("/quotes?onlyAction=true");
  });

  it("removes onlyAction from URL when toggle is unchecked", async () => {
    searchParamsState.value = "onlyAction=true";

    const user = userEvent.setup();

    renderTable();

    await user.click(screen.getByRole("checkbox", { name: "Только требует действия" }));

    expect(routerReplace).toHaveBeenCalledWith("/quotes");
  });

  it("resets pagination on toggle change", async () => {
    searchParamsState.value = "page=3";

    const user = userEvent.setup();

    renderTable();

    await user.click(screen.getByRole("checkbox", { name: "Только требует действия" }));

    expect(routerReplace).toHaveBeenCalledWith("/quotes?onlyAction=true");
  });

  it("preserves other URL params on toggle change", async () => {
    searchParamsState.value = "search=foo&sort=-amount";

    const user = userEvent.setup();

    renderTable();

    await user.click(screen.getByRole("checkbox", { name: "Только требует действия" }));

    const calls = routerReplace.mock.calls;
    expect(calls).toHaveLength(1);

    const url = new URL(calls[0][0], "http://test.local");
    expect(url.pathname).toBe("/quotes");
    expect(url.searchParams.get("search")).toBe("foo");
    expect(url.searchParams.get("sort")).toBe("-amount");
    expect(url.searchParams.get("onlyAction")).toBe("true");
  });

  it("reports filtered count via `total` when toggle is on", () => {
    searchParamsState.value = "onlyAction=true";

    renderTable();

    expect(screen.getByTestId("total")).toHaveTextContent("2");
  });

  it("reports full count via `total` when toggle is off", () => {
    renderTable();

    expect(screen.getByTestId("total")).toHaveTextContent("4");
  });
});
