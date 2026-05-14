// @vitest-environment jsdom
/**
 * РОЛ Тест 07 #5c (W1 from Phase 5a type-design review): the action bar
 * previously summed `mainCostRub` blindly across mixed-currency segments
 * and labelled the result as RUB. With Combo-3 every segment carries its
 * own `currencyCode`, so the totals strip must convert into the parent
 * quote's currency and surface missing FX rates instead of producing a
 * silently wrong number.
 */
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { LogisticsActionBar } from "../logistics-action-bar";
import type { LogisticsSegment } from "@/entities/logistics-segment";

function makeSegment(overrides: Partial<LogisticsSegment> = {}): LogisticsSegment {
  return {
    id: overrides.id ?? "seg-1",
    invoiceId: "inv-1",
    sequenceOrder: overrides.sequenceOrder ?? 1,
    fromLocation: {
      id: "loc-from",
      country: "Китай",
      city: "Шанхай",
      type: "supplier",
    },
    toLocation: {
      id: "loc-to",
      country: "Россия",
      city: "Москва",
      type: "hub",
    },
    transitDays: 0,
    mainCostRub: 0,
    currencyCode: "RUB",
    expenses: [],
    ...overrides,
  };
}

afterEach(cleanup);

describe("LogisticsActionBar — currency-aware totals (5c W1)", () => {
  it("formats same-currency total in displayCurrency without warning", () => {
    const segments = [
      makeSegment({ id: "s1", sequenceOrder: 1, mainCostRub: 100, currencyCode: "USD" }),
      makeSegment({ id: "s2", sequenceOrder: 2, mainCostRub: 200, currencyCode: "USD" }),
    ];
    render(
      <LogisticsActionBar
        segments={segments}
        alreadyCompleted={false}
        needsReview={false}
        canEdit
        onComplete={vi.fn()}
        displayCurrency="USD"
        fxRates={{ USD: 90, EUR: 100 }}
      />,
    );

    const totals = screen.getByTestId("logistics-action-bar-totals");
    // 100 + 200 USD → 300 USD, formatted with ru-RU + USD currency.
    expect(totals.textContent).toMatch(/300/);
    expect(totals.textContent).toMatch(/\$|US\$|USD/);
    expect(
      screen.queryByTestId("logistics-action-bar-missing-rates"),
    ).toBeNull();
  });

  it("converts mixed-currency segments into displayCurrency", () => {
    // 100 USD @ 90 RUB/USD = 9 000 RUB, then ÷ 100 RUB/EUR = 90 EUR.
    // 100 EUR remains 100 EUR. Total ≈ 190 EUR.
    const segments = [
      makeSegment({ id: "s1", sequenceOrder: 1, mainCostRub: 100, currencyCode: "USD" }),
      makeSegment({ id: "s2", sequenceOrder: 2, mainCostRub: 100, currencyCode: "EUR" }),
    ];
    render(
      <LogisticsActionBar
        segments={segments}
        alreadyCompleted={false}
        needsReview={false}
        canEdit
        onComplete={vi.fn()}
        displayCurrency="EUR"
        fxRates={{ USD: 90, EUR: 100 }}
      />,
    );

    const totals = screen.getByTestId("logistics-action-bar-totals");
    expect(totals.textContent).toMatch(/190/);
    expect(
      screen.queryByTestId("logistics-action-bar-missing-rates"),
    ).toBeNull();
  });

  it("renders static «Логистика завершена» badge (no button) when alreadyCompleted", () => {
    // Testing 2 row 11 (part 3): the disabled-but-green «Логистика
    // готова» Button was misread as clickable by testers. A Badge has
    // no button affordance so the done state is unambiguous.
    const segments = [
      makeSegment({ id: "s1", sequenceOrder: 1, mainCostRub: 100, currencyCode: "RUB" }),
    ];
    render(
      <LogisticsActionBar
        segments={segments}
        alreadyCompleted
        needsReview={false}
        canEdit
        onComplete={vi.fn()}
        displayCurrency="RUB"
        fxRates={{}}
      />,
    );

    // No completion button when logistics is already done.
    expect(
      screen.queryByRole("button", { name: /Логистика/ }),
    ).toBeNull();

    // Badge replaces the button.
    const badge = screen.getByTestId("logistics-completed-badge");
    expect(badge.textContent).toMatch(/Логистика завершена/);
    expect(badge.querySelector("svg")).not.toBeNull();
  });

  it("does NOT call onComplete when the completion badge is clicked", () => {
    const segments = [
      makeSegment({ id: "s1", sequenceOrder: 1, mainCostRub: 100, currencyCode: "RUB" }),
    ];
    const handleComplete = vi.fn();
    render(
      <LogisticsActionBar
        segments={segments}
        alreadyCompleted
        needsReview={false}
        canEdit
        onComplete={handleComplete}
        displayCurrency="RUB"
        fxRates={{}}
      />,
    );

    const badge = screen.getByTestId("logistics-completed-badge");
    (badge as HTMLElement).click();
    expect(handleComplete).not.toHaveBeenCalled();
  });

  it("shows AlertCircle and ≈ prefix when an FX rate is missing", () => {
    const segments = [
      makeSegment({ id: "s1", sequenceOrder: 1, mainCostRub: 100, currencyCode: "USD" }),
      // CNY rate intentionally absent from fxRates → excluded from total.
      makeSegment({ id: "s2", sequenceOrder: 2, mainCostRub: 500, currencyCode: "CNY" }),
    ];
    render(
      <LogisticsActionBar
        segments={segments}
        alreadyCompleted={false}
        needsReview={false}
        canEdit
        onComplete={vi.fn()}
        displayCurrency="USD"
        fxRates={{ USD: 90 }}
      />,
    );

    const totals = screen.getByTestId("logistics-action-bar-totals");
    // 100 USD → 100 USD (exact); CNY excluded.
    expect(totals.textContent).toMatch(/≈/);
    expect(totals.textContent).toMatch(/100/);
    expect(
      screen.getByTestId("logistics-action-bar-missing-rates"),
    ).toBeTruthy();
  });
});
