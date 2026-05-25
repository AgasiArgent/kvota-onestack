// @vitest-environment jsdom
/**
 * Calc-step hard-stop 5% markup (Testing 2 row 47).
 *
 * Tester request: «Можно поставить ниже. В дальнейшем сделаем функционал
 * согласования, но сейчас не ниже 5%». Decision: hard stop, no согласование
 * path yet — backend rejects with MARKUP_TOO_LOW (400), frontend disables
 * «Рассчитать» and shows inline error under the input.
 *
 * Contract (frontend):
 *   - markup < 5 (e.g. 4.9, 4, 0) → inline error «Наценка не может быть
 *     меньше 5%» visible under the «Наценка %» input.
 *   - markup >= 5 (including exactly 5) → no inline error.
 *   - The hint «Минимальная наценка — 5%» stays visible regardless (steady
 *     guidance, not error styling).
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { CalculationForm } from "../calculation-form";
import type { QuoteDetailRow } from "@/entities/quote/queries";

const noop = vi.fn();

const baseQuote = {
  id: "q-1",
  currency: "USD",
  workflow_status: "draft",
} as unknown as QuoteDetailRow;

function renderForm(markup: string) {
  return render(
    <CalculationForm
      quote={baseQuote}
      savedVariables={null}
      formValues={makeFormValues(markup)}
      onFieldChange={noop}
    />,
  );
}

function makeFormValues(markup: string): Record<string, string> {
  return {
    offer_sale_type: "поставка",
    offer_incoterms: "DDP",
    currency: "USD",
    markup,
    supplier_discount: "0",
    exchange_rate: "1.0",
    delivery_time: "30",
    seller_company: "",
    logistics_supplier_hub: "0",
    logistics_hub_customs: "0",
    logistics_customs_client: "0",
    brokerage_hub: "0",
    brokerage_hub_currency: "RUB",
    brokerage_customs: "0",
    brokerage_customs_currency: "RUB",
    warehousing_at_customs: "0",
    warehousing_at_customs_currency: "RUB",
    customs_documentation: "0",
    customs_documentation_currency: "RUB",
    brokerage_extra: "0",
    brokerage_extra_currency: "RUB",
    advance_to_supplier: "100",
    advance_from_client: "100",
    time_to_advance: "0",
    advance_on_loading: "0",
    time_to_advance_loading: "0",
    advance_on_going_to_country_destination: "0",
    time_to_advance_going_to_country_destination: "0",
    advance_on_customs_clearance: "0",
    time_to_advance_on_customs_clearance: "0",
    time_to_advance_on_receiving: "0",
    dm_fee_type: "fixed",
    dm_fee_value: "0",
    dm_fee_currency: "RUB",
  };
}

afterEach(() => {
  cleanup();
});

describe("CalculationForm — markup minimum 5%", () => {
  it("shows inline error when markup is below 5 (4.9)", () => {
    renderForm("4.9");
    expect(
      screen.getByText("Наценка не может быть меньше 5%"),
    ).toBeInTheDocument();
  });

  it("shows inline error when markup is exactly 4", () => {
    renderForm("4");
    expect(
      screen.getByText("Наценка не может быть меньше 5%"),
    ).toBeInTheDocument();
  });

  it("shows inline error when markup is 0", () => {
    renderForm("0");
    expect(
      screen.getByText("Наценка не может быть меньше 5%"),
    ).toBeInTheDocument();
  });

  it("does NOT show inline error when markup is exactly 5 (boundary)", () => {
    renderForm("5");
    expect(
      screen.queryByText("Наценка не может быть меньше 5%"),
    ).toBeNull();
  });

  it("does NOT show inline error when markup is above 5 (15)", () => {
    renderForm("15");
    expect(
      screen.queryByText("Наценка не может быть меньше 5%"),
    ).toBeNull();
  });

  it("does NOT show inline error when markup is empty (treat empty as not-yet-invalid)", () => {
    renderForm("");
    expect(
      screen.queryByText("Наценка не может быть меньше 5%"),
    ).toBeNull();
  });

  it("keeps the static hint «Минимальная наценка — 5%» always visible", () => {
    const { rerender } = renderForm("15");
    expect(screen.getByText("Минимальная наценка — 5%")).toBeInTheDocument();

    rerender(
      <CalculationForm
        quote={baseQuote}
        savedVariables={null}
        formValues={makeFormValues("4")}
        onFieldChange={noop}
      />,
    );
    expect(screen.getByText("Минимальная наценка — 5%")).toBeInTheDocument();
  });
});
