// @vitest-environment jsdom
/**
 * Seller company (юр.лицо) picker on the calc step (Testing 2 row 48b).
 *
 * Contract (CalculationForm):
 *   - When sellerCompanies is non-empty, the «Наше юрлицо» picker renders
 *     inside the «Компания и условия» card with the current selection shown.
 *   - When sellerCompanies is empty, the picker is not rendered (nothing to
 *     choose from — matches the create-quote dialog behaviour).
 *   - Selecting a company fires onSellerCompanyChange with that company id;
 *     selecting «-- Не указано --» fires it with null (clear).
 *
 * Persistence + the recalc banner are covered separately in
 * calculation-step-seller.dom.test.tsx (parent-level wiring).
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { CalculationForm } from "../calculation-form";
import type { QuoteDetailRow } from "@/entities/quote/queries";

const noop = vi.fn();

const baseQuote = {
  id: "q-1",
  currency: "USD",
  workflow_status: "draft",
} as unknown as QuoteDetailRow;

const formValues: Record<string, string> = {
  offer_incoterms: "DDP",
  currency: "USD",
  markup: "15",
  dm_fee_type: "fixed",
  dm_fee_value: "0",
  dm_fee_currency: "RUB",
  advance_from_client: "100",
  time_to_advance: "0",
  advance_on_loading: "0",
  time_to_advance_loading: "0",
  advance_on_going_to_country_destination: "0",
  time_to_advance_going_to_country_destination: "0",
  advance_on_customs_clearance: "0",
  time_to_advance_on_customs_clearance: "0",
  time_to_advance_on_receiving: "0",
};

const companies = [
  { id: "sc-1", name: "ООО Альфа" },
  { id: "sc-2", name: "ООО Бета" },
];

function renderForm(
  sellerCompanies: Array<{ id: string; name: string }>,
  sellerCompanyId: string | null,
  onSellerCompanyChange: (next: string | null) => void,
) {
  return render(
    <CalculationForm
      quote={baseQuote}
      savedVariables={null}
      formValues={formValues}
      onFieldChange={noop}
      sellerCompanies={sellerCompanies}
      sellerCompanyId={sellerCompanyId}
      onSellerCompanyChange={onSellerCompanyChange}
    />,
  );
}

afterEach(() => {
  cleanup();
});

/**
 * base-ui Select commits a selection when the highlighted option receives the
 * click→pointerdown→pointerup→click sequence (a bare click only highlights).
 * Helper opens the picker and selects the option whose text matches.
 */
function selectOption(triggerLabel: string, optionText: string) {
  fireEvent.click(screen.getByLabelText(triggerLabel));
  const option = screen
    .getAllByRole("option")
    .find((el) => el.textContent === optionText);
  if (!option) throw new Error(`option not found: ${optionText}`);
  fireEvent.click(option);
  fireEvent.pointerDown(option);
  fireEvent.pointerUp(option);
  fireEvent.click(option);
}

describe("CalculationForm — seller company picker (row 48b)", () => {
  it("renders the «Наше юрлицо» picker showing the current selection", () => {
    renderForm(companies, "sc-2", vi.fn());
    expect(screen.getByText("Наше юрлицо")).toBeInTheDocument();
    // The trigger shows the resolved label of the selected company (the
    // `items` map on Select.Root drives label resolution).
    expect(screen.getByLabelText("Наше юрлицо").textContent).toContain(
      "ООО Бета",
    );
  });

  it("does NOT render the picker when there are no seller companies", () => {
    renderForm([], null, vi.fn());
    expect(screen.queryByText("Наше юрлицо")).toBeNull();
  });

  it("shows the «Не указано» placeholder when nothing is selected", () => {
    renderForm(companies, null, vi.fn());
    expect(screen.getByText("-- Не указано --")).toBeInTheDocument();
  });

  it("fires onSellerCompanyChange with a company id when a company is picked", () => {
    const onChange = vi.fn();
    renderForm(companies, null, onChange);

    selectOption("Наше юрлицо", "ООО Альфа");

    expect(onChange).toHaveBeenCalledWith("sc-1");
  });

  it("fires onSellerCompanyChange with null when «-- Не указано --» is picked", () => {
    const onChange = vi.fn();
    renderForm(companies, "sc-1", onChange);

    selectOption("Наше юрлицо", "-- Не указано --");

    expect(onChange).toHaveBeenCalledWith(null);
  });
});
