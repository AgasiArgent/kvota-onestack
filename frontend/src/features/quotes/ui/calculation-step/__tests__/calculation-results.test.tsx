import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect } from "vitest";

/**
 * Phase 5d Task 12 (Agent A) — calculation-results regression.
 *
 * Verifies the component is purely presentational:
 *   - Summary cards source from quote.total_quote_currency / profit / cogs
 *     (extended fields written by Python calc API)
 *   - Per-item table reads item.base_price_vat (the calc-engine per-unit
 *     write-back from main.py:14410)
 *   - No own Supabase call — all data arrives via props from
 *     CalculationStep -> page.tsx -> fetchQuoteItems/fetchQuoteDetail
 *
 * Task 12 case (a): verify the prop contract; no refactor in this task.
 */

import {
  CalculationResults,
  type CalculationResultsItem,
} from "../calculation-results";
import type { QuoteDetailRow } from "@/entities/quote/queries";

function makeQuote(
  overrides: Record<string, unknown> = {}
): QuoteDetailRow {
  return {
    id: "q-1",
    currency: "USD",
    total_quote_currency: 1000,
    revenue_no_vat_quote_currency: 800,
    profit_quote_currency: 200,
    cogs_quote_currency: 600,
    ...overrides,
  } as unknown as QuoteDetailRow;
}

function makeItem(
  overrides: Partial<CalculationResultsItem> = {}
): CalculationResultsItem {
  return {
    id: "qi-1",
    product_name: "Товар",
    brand: null,
    quantity: 10,
    base_price_vat: 100,
    ...overrides,
  };
}

describe("CalculationResults — summary cards source from quote extended fields", () => {
  it("renders 'Расчёт ещё не выполнен' placeholder when total_quote_currency is null", () => {
    const quote = makeQuote({ total_quote_currency: null });

    const html = renderToString(
      <CalculationResults quote={quote} items={[]} />
    );

    expect(html).toContain("Расчёт ещё не выполнен");
  });

  it("renders summary totals from quote.total_quote_currency / revenue / profit", () => {
    const quote = makeQuote({
      total_quote_currency: 12000,
      revenue_no_vat_quote_currency: 10000,
      profit_quote_currency: 2000,
    });

    const html = renderToString(
      <CalculationResults quote={quote} items={[]} />
    );

    // ru-RU formatter uses U+00A0 (nbsp) for grouping separator.
    expect(html).toMatch(/10\s000,00/);
    expect(html).toMatch(/12\s000,00/);
    expect(html).toMatch(/2\s000,00/);
    // Margin = profit / revenue_no_vat = 2000 / 10000 = 20.0%
    expect(html).toContain("20.0%");
  });
});

describe("CalculationResults — per-item rows read item.base_price_vat", () => {
  it("renders price and line total from item.base_price_vat × quantity", () => {
    const quote = makeQuote();
    const items = [
      makeItem({ id: "a", product_name: "Болт", base_price_vat: 50, quantity: 3 }),
    ];

    const html = renderToString(
      <CalculationResults quote={quote} items={items} />
    );

    expect(html).toContain("Болт");
    // per-unit 50.00
    expect(html).toContain("50,00");
    // line total 150.00
    expect(html).toContain("150,00");
  });

  it("handles null base_price_vat gracefully", () => {
    const quote = makeQuote();
    const items = [
      makeItem({ id: "a", product_name: "X", base_price_vat: null, quantity: 2 }),
    ];

    const html = renderToString(
      <CalculationResults quote={quote} items={items} />
    );

    expect(html).toContain("X");
    // em-dash for null
    expect(html).toMatch(/—|&#x2014;/);
  });
});
