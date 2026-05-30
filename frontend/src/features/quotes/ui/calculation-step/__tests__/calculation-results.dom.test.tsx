// @vitest-environment jsdom
/**
 * Calc-step P0 fix (2026-05-25) — items table is always rendered.
 *
 * Pre-fix: `CalculationResults` early-returned a centered placeholder card
 * when `quote.total_quote_currency` was null (i.e. no successful calculation
 * yet). The user lost all visibility into the quote items — including the
 * one with the missing price that was blocking the calc. The tester saw an
 * empty page + a brief English toast and could not recover.
 *
 * Post-fix contract:
 *   - Items table renders unconditionally (any time the component mounts).
 *   - When total_quote_currency is null, an inline info banner («Расчёт ещё
 *     не выполнен») sits above the table — not in place of it.
 *   - When base_price_vat is null on an item, the price/total cells degrade
 *     to «—» via the existing fmt() helper.
 *
 * These three properties are the regression guard.
 */
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";

import {
  CalculationResults,
  type CalculationResultsItem,
} from "../calculation-results";
import type { QuoteDetailRow } from "@/entities/quote/queries";

afterEach(() => {
  cleanup();
});

function makeQuote(overrides: Record<string, unknown> = {}): QuoteDetailRow {
  return {
    id: "q-1",
    currency: "USD",
    total_quote_currency: null,
    revenue_no_vat_quote_currency: null,
    profit_quote_currency: null,
    cogs_quote_currency: null,
    ...overrides,
  } as unknown as QuoteDetailRow;
}

function makeItem(
  overrides: Partial<CalculationResultsItem> = {},
): CalculationResultsItem {
  return {
    id: "qi-1",
    product_name: "Миксер пневматический PM-3/TJ3",
    brand: "Китайский бренд",
    quantity: 3,
    minimum_order_quantity: null,
    base_price_vat: null,
    ...overrides,
  };
}

describe("CalculationResults — items table rendered even when no calc yet", () => {
  it("renders the items table when total_quote_currency is null", () => {
    const quote = makeQuote({ total_quote_currency: null });
    const items = [makeItem()];

    render(<CalculationResults quote={quote} items={items} />);

    // Table headers are present — table is rendered, not replaced.
    expect(screen.getByText("Наименование")).toBeTruthy();
    expect(screen.getByText("Кол-во")).toBeTruthy();
    // Item name renders inside the table.
    expect(
      screen.getByText("Миксер пневматический PM-3/TJ3"),
    ).toBeTruthy();
  });

  it("shows the «Расчёт ещё не выполнен» info banner above the table when total is null", () => {
    const quote = makeQuote({ total_quote_currency: null });

    render(<CalculationResults quote={quote} items={[makeItem()]} />);

    // The placeholder text is preserved — but as an info banner, not as the
    // sole content of the component.
    expect(
      screen.getByText(/Расчёт ещё не выполнен/),
    ).toBeTruthy();
    // And the items table is still rendered alongside.
    expect(
      screen.getByText("Миксер пневматический PM-3/TJ3"),
    ).toBeTruthy();
  });

  it("renders «—» (em-dash) for items with null base_price_vat", () => {
    const quote = makeQuote({ total_quote_currency: null });
    const items = [
      makeItem({
        id: "a",
        product_name: "Без цены",
        base_price_vat: null,
        quantity: 5,
      }),
    ];

    render(<CalculationResults quote={quote} items={items} />);

    // The row for the unpriced item exists.
    const row = screen.getByText("Без цены").closest("tr");
    expect(row).toBeTruthy();
    // And at least one «—» appears inside that row (price cell + total cell).
    const emDashCells = within(row as HTMLElement).getAllByText("—");
    expect(emDashCells.length).toBeGreaterThan(0);
  });

  it("does NOT render summary cards (Сумма с НДС / Профит / Маржа) when total is null", () => {
    const quote = makeQuote({ total_quote_currency: null });

    render(<CalculationResults quote={quote} items={[makeItem()]} />);

    // Summary cards only appear after a successful calc.
    expect(screen.queryByText("Сумма с НДС")).toBeNull();
    expect(screen.queryByText("Профит")).toBeNull();
    expect(screen.queryByText("Маржа")).toBeNull();
  });

  it("renders summary cards AND the items table after a successful calc", () => {
    const quote = makeQuote({
      total_quote_currency: 1000,
      revenue_no_vat_quote_currency: 800,
      profit_quote_currency: 200,
    });
    const items = [
      makeItem({
        id: "a",
        product_name: "С ценой",
        base_price_vat: 50,
        quantity: 4,
      }),
    ];

    render(<CalculationResults quote={quote} items={items} />);

    // Banner is gone.
    expect(screen.queryByText(/Расчёт ещё не выполнен/)).toBeNull();
    // Summary cards visible.
    expect(screen.getByText("Сумма с НДС")).toBeTruthy();
    expect(screen.getByText("Профит")).toBeTruthy();
    // Table still present.
    expect(screen.getByText("С ценой")).toBeTruthy();
  });
});

describe("CalculationResults — effective quantity (supplier override)", () => {
  it("renders effective qty + «кол-во поставщика» hint when supplier qty overrides", () => {
    const quote = makeQuote({ total_quote_currency: 1000 });
    const items = [
      makeItem({
        id: "a",
        product_name: "С поставщиком",
        base_price_vat: 100,
        quantity: 5,
        minimum_order_quantity: 10,
      }),
    ];

    render(<CalculationResults quote={quote} items={items} />);

    const row = screen.getByText("С поставщиком").closest("tr") as HTMLElement;
    // Effective qty (10) is shown.
    expect(within(row).getByText("10")).toBeTruthy();
    // Two-sided hint visible, with the ordered qty in its tooltip.
    const hint = within(row).getByText(/кол-во поставщика: 10/);
    expect(hint).toBeTruthy();
    expect(hint.getAttribute("title")).toContain("заказано 5");
  });
});
