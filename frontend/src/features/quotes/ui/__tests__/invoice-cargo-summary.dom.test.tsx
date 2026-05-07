// @vitest-environment jsdom
/**
 * РОЛ Тест 07 #3.3 (cluster L-A, CRITICAL): the logistics view of a КПП
 * must show the actual cargo info entered by procurement — origin
 * country / city, total weight, total volume, package count and packed
 * dimensions — so the logistician can pick a route without bouncing
 * to the procurement tab.
 */
import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { InvoiceCargoSummary } from "../logistics-step/invoice-cargo-summary";
import type { QuoteInvoiceRow } from "@/entities/quote/queries";

function makeInvoice(
  overrides: Partial<QuoteInvoiceRow> = {},
): QuoteInvoiceRow {
  return {
    id: "inv-1",
    quote_id: "q-1",
    invoice_number: "INV-001",
    currency: "USD",
    supplier_id: null,
    buyer_company_id: null,
    pickup_location_id: null,
    pickup_country: null,
    pickup_city: null,
    pickup_country_code: null,
    total_weight_kg: null,
    total_volume_m3: null,
    package_count: null,
    height_m: null,
    length_m: null,
    width_m: null,
    supplier_incoterms: null,
    status: null,
    created_at: null,
    updated_at: null,
    logistics_supplier_to_hub: null,
    logistics_hub_to_customs: null,
    logistics_customs_to_customer: null,
    logistics_total_days: null,
    logistics_notes: null,
    logistics_completed_at: null,
    logistics_completed_by: null,
    logistics_supplier_to_hub_currency: null,
    logistics_hub_to_customs_currency: null,
    logistics_customs_to_customer_currency: null,
    procurement_completed_at: null,
    procurement_completed_by: null,
    customs_completed_at: null,
    customs_completed_by: null,
    assigned_logistics_user: null,
    assigned_customs_user: null,
    procurement_notes: null,
    invoice_file_url: null,
    verified_at: null,
    verified_by: null,
    sent_at: null,
    logistics_assigned_at: null,
    logistics_deadline_at: null,
    logistics_sla_hours: null,
    customs_assigned_at: null,
    customs_deadline_at: null,
    customs_sla_hours: null,
    logistics_needs_review_since: null,
    customs_needs_review_since: null,
    supplier: null,
    buyer_company: null,
    ...overrides,
  } as QuoteInvoiceRow;
}

afterEach(cleanup);

describe("InvoiceCargoSummary (РОЛ Тест 07 #3.3)", () => {
  it("renders origin country/city, weight, volume, package count and dimensions", () => {
    render(
      <InvoiceCargoSummary
        invoice={makeInvoice({
          pickup_country: "Китай",
          pickup_city: "Шанхай",
          total_weight_kg: 1240,
          total_volume_m3: 8.6,
          package_count: 17,
          length_m: 1.2,
          width_m: 0.8,
          height_m: 1.05,
          supplier_incoterms: "FCA",
        })}
      />,
    );

    expect(screen.getByText(/Китай, Шанхай/)).toBeTruthy();
    expect(screen.getByText(/1 240 кг/)).toBeTruthy();
    expect(screen.getByText(/8,6 м³/)).toBeTruthy();
    expect(screen.getByText("17")).toBeTruthy();
    // Dimensions are formatted as "L × W × H м"
    expect(
      screen.getByText((s) => /1,2.+×.+0,8.+×.+1,05.+м/.test(s)),
    ).toBeTruthy();
    expect(screen.getByText("FCA")).toBeTruthy();
  });

  it("shows an empty-state hint when procurement has not filled cargo data", () => {
    render(<InvoiceCargoSummary invoice={makeInvoice()} />);
    expect(screen.getByTestId("invoice-cargo-summary-empty")).toBeTruthy();
    expect(
      screen.getByText(/Закупка ещё не заполнила груз/i),
    ).toBeTruthy();
  });

  it("omits fields that are missing without producing «—» placeholders for them", () => {
    render(
      <InvoiceCargoSummary
        invoice={makeInvoice({
          pickup_country: "Турция",
          total_weight_kg: 50,
        })}
      />,
    );
    expect(screen.getByText("Турция")).toBeTruthy();
    expect(screen.getByText(/50 кг/)).toBeTruthy();
    // Volume / package count / dimensions / incoterms not provided —
    // their labels must be absent (not rendered as "—").
    expect(screen.queryByText("Объём:")).toBeNull();
    expect(screen.queryByText("Мест:")).toBeNull();
    expect(screen.queryByText("Габариты:")).toBeNull();
    expect(screen.queryByText("Incoterms:")).toBeNull();
  });
});
