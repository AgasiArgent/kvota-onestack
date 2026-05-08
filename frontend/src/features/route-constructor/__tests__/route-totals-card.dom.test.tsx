/**
 * RouteTotalsCard — per-segment currency totals (РОЛ Тест 07 #3.7).
 *
 * Verifies that mixed-currency segments and expenses are correctly
 * converted into the display currency using the supplied
 * foreign→RUB rate map, and that missing rates surface a warning.
 */
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { LogisticsSegment } from "@/entities/logistics-segment";
import { RouteTotalsCard } from "../ui/route-totals-card";

afterEach(cleanup);

function makeSegment(overrides: Partial<LogisticsSegment> = {}): LogisticsSegment {
  return {
    id: overrides.id ?? "seg-1",
    invoiceId: "inv-1",
    sequenceOrder: 1,
    fromLocation: undefined,
    toLocation: undefined,
    label: undefined,
    transitDays: undefined,
    mainCostRub: 0,
    currencyCode: "RUB",
    carrier: undefined,
    notes: undefined,
    expenses: [],
    ...overrides,
  };
}

const ratesToRub = { USD: 90, EUR: 100, CNY: 12 };

function getAmount(label: string): string {
  // Each <dt>{label}</dt><dd>{value}</dd> pair lives inside the same flex
  // column, so we walk from the dt up to the parent and read its dd.
  const dt = screen.getByText(label);
  const dd = dt.parentElement?.querySelector("dd");
  if (!dd) throw new Error(`No dd sibling for label "${label}"`);
  return (dd.textContent ?? "").replace(/ /g, " ");
}

describe("RouteTotalsCard FX conversion", () => {
  it("sums identical-currency segments without conversion", () => {
    render(
      <RouteTotalsCard
        segments={[
          makeSegment({ id: "a", mainCostRub: 100, currencyCode: "RUB" }),
          makeSegment({ id: "b", mainCostRub: 50, currencyCode: "RUB" }),
        ]}
        displayCurrency="RUB"
        ratesToRub={ratesToRub}
      />,
    );
    expect(getAmount("Основная стоимость")).toMatch(/150/);
    expect(getAmount("Всего")).toMatch(/150/);
    expect(screen.queryByTestId("route-totals-missing-rates")).toBeNull();
  });

  it("converts mixed-currency segments into display currency", () => {
    render(
      <RouteTotalsCard
        segments={[
          // 10 USD = 900 RUB
          makeSegment({ id: "a", mainCostRub: 10, currencyCode: "USD" }),
          // 5 EUR = 500 RUB
          makeSegment({ id: "b", mainCostRub: 5, currencyCode: "EUR" }),
        ]}
        displayCurrency="RUB"
        ratesToRub={ratesToRub}
      />,
    );
    expect(getAmount("Всего")).toMatch(/1\D?400/);
    expect(screen.queryByTestId("route-totals-missing-rates")).toBeNull();
  });

  it("converts segment expenses with their own currency", () => {
    render(
      <RouteTotalsCard
        segments={[
          makeSegment({
            id: "a",
            mainCostRub: 100,
            currencyCode: "RUB",
            expenses: [
              {
                id: "e1",
                label: "Insurance",
                costRub: 5,
                currencyCode: "USD", // 5 * 90 = 450 RUB
              },
            ],
          }),
        ]}
        displayCurrency="RUB"
        ratesToRub={ratesToRub}
      />,
    );
    expect(getAmount("Доп. расходы")).toMatch(/450/);
    expect(getAmount("Всего")).toMatch(/550/);
  });

  it("flags missing rates and excludes those amounts from the total", () => {
    render(
      <RouteTotalsCard
        segments={[
          makeSegment({ id: "a", mainCostRub: 100, currencyCode: "RUB" }),
          // GBP not in the rate map → excluded with warning
          makeSegment({
            id: "b",
            mainCostRub: 1000,
            currencyCode: "GBP" as never,
          }),
        ]}
        displayCurrency="RUB"
        ratesToRub={ratesToRub}
      />,
    );
    // Total reflects only the 100 RUB row — GBP excluded.
    expect(getAmount("Всего")).toMatch(/100/);
    const warning = screen.getByTestId("route-totals-missing-rates");
    expect(warning.textContent).toMatch(/GBP/);
  });
});
