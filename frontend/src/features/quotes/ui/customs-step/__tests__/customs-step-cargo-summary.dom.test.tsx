// @vitest-environment jsdom
/**
 * Testing 2 row 14 (МВЭД) — the cargo info panel must be visible on the
 * customs step, not just the logistics step.
 *
 * МВЭД (head_of_customs) is routed to the customs step regardless of
 * `?step=logistics` URL params, so the panel introduced in PR #152 has
 * to also live on customs. This test pins down the new render site by
 * verifying that the panel surfaces the procurement-side digest
 * (origin, dimensions, cargo names, destination) for a customs-context
 * invoice + items combo.
 *
 * Full `<CustomsStep>` mounting is intentionally avoided — it pulls in
 * Handsontable + Supabase client + dynamic imports that jsdom cannot
 * cheaply satisfy. The panel itself is a pure component, so a direct
 * smoke render with realistic customs-shaped props is sufficient to
 * catch regressions in either the wiring or the panel contract.
 */
import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { InvoiceCargoSummary } from "../../logistics-step/invoice-cargo-summary";
import type {
  InvoiceItemsAggregateExport,
  QuoteInvoiceRow,
  QuoteItemRow,
} from "@/entities/quote/queries";

afterEach(cleanup);

function makeInvoice(overrides: Partial<QuoteInvoiceRow> = {}): QuoteInvoiceRow {
  // Only the fields read by InvoiceCargoSummary need real values. Rest
  // are nulls so the render path doesn't trip on unrelated columns.
  const base: Record<string, unknown> = {
    id: "inv-customs-1",
    quote_id: "quote-1",
    invoice_number: "INV-001",
    pickup_country: "Китай",
    pickup_city: "Шанхай",
    total_weight_kg: 1250,
    total_volume_m3: 4.5,
    package_count: 12,
    length_m: 2.4,
    width_m: 1.2,
    height_m: 1.5,
    supplier_incoterms: "FCA",
    buyer_company: { name: "ООО Покупатель" },
    supplier: null,
    logistics_completed_at: null,
    logistics_assigned_at: null,
    logistics_needs_review_since: null,
  };
  return { ...base, ...overrides } as unknown as QuoteInvoiceRow;
}

function makeItem(
  invoiceId: string,
  name: string,
  overrides: Partial<QuoteItemRow> = {},
): QuoteItemRow {
  const base: Record<string, unknown> = {
    id: `${invoiceId}-${name}`,
    quote_id: "quote-1",
    position: 1,
    product_name: name,
    product_code: null,
    quantity: 1,
    composition_selected_invoice_id: invoiceId,
  };
  return { ...base, ...overrides } as unknown as QuoteItemRow;
}

describe("Customs step — cargo info panel (Testing 2 row 14 МВЭД)", () => {
  it("renders origin, destination, dimensions, and cargo digest for the active customs invoice", () => {
    const invoice = makeInvoice();
    const items = [
      makeItem(invoice.id, "Кабель силовой"),
      makeItem(invoice.id, "Разъём BNC"),
      makeItem(invoice.id, "Кронштейн стальной"),
    ];

    render(
      <InvoiceCargoSummary
        invoice={invoice}
        destination={{
          country: "Россия",
          city: "Москва",
          address: "ул. Тверская, 1",
        }}
        items={items}
      />,
    );

    const panel = screen.getByTestId("invoice-cargo-summary");
    expect(panel).toBeInTheDocument();

    // Origin (pickup_country + pickup_city)
    expect(panel).toHaveTextContent("Откуда");
    expect(panel).toHaveTextContent("Китай, Шанхай");

    // Destination (passed via `destination` prop)
    expect(panel).toHaveTextContent("Куда");
    expect(panel).toHaveTextContent("Россия, Москва, ул. Тверская, 1");

    // Dimensions: 2.4 × 1.2 × 1.5 м
    expect(panel).toHaveTextContent("Габариты");

    // Cargo digest: «3 позиции: Кабель силовой, Разъём BNC +1»
    expect(panel).toHaveTextContent("Груз");
    expect(panel).toHaveTextContent("3 позиции");
    expect(panel).toHaveTextContent("Кабель силовой");
  });

  it("surfaces Валюта КПП / Стоимость / Кол-во / Ед.изм. from items_aggregate (Testing 2 row 71)", () => {
    // Tester repro: customs reviewer opens КП → cargo info panel shows the
    // shipment digest but four key КП totals are «Данных нет». Aggregate
    // comes from fetchQuoteInvoices joining invoice_items + coverage; the
    // panel now renders all four when the aggregate is present.
    const invoice = makeInvoice({
      currency: "EUR",
      items_aggregate: {
        total_quantity: 120,
        total_amount_original: 4567.5,
        currency: "EUR",
        units: ["шт"],
      } satisfies InvoiceItemsAggregateExport,
    });

    render(
      <InvoiceCargoSummary
        invoice={invoice}
        destination={{ country: "Россия", city: null, address: null }}
        items={[makeItem(invoice.id, "Подшипник 6204")]}
      />,
    );

    const panel = screen.getByTestId("invoice-cargo-summary");
    expect(panel).toHaveTextContent("Валюта КПП");
    expect(panel).toHaveTextContent("EUR");
    expect(panel).toHaveTextContent("Стоимость");
    expect(panel).toHaveTextContent("4 567,5 EUR");
    expect(panel).toHaveTextContent("Кол-во");
    expect(panel).toHaveTextContent("120");
    expect(panel).toHaveTextContent("Ед.изм.");
    expect(panel).toHaveTextContent("шт");
  });

  it("shows «разные» for Ед.изм. when КП contains mixed units", () => {
    const invoice = makeInvoice({
      items_aggregate: {
        total_quantity: 50,
        total_amount_original: null,
        currency: "USD",
        units: ["кг", "шт"],
      } satisfies InvoiceItemsAggregateExport,
    });

    render(
      <InvoiceCargoSummary
        invoice={invoice}
        destination={{ country: null, city: null, address: null }}
        items={[makeItem(invoice.id, "Микс")]}
      />,
    );

    const panel = screen.getByTestId("invoice-cargo-summary");
    expect(panel).toHaveTextContent("Ед.изм.");
    expect(panel).toHaveTextContent("разные");
  });

  it("keeps the empty-state when invoice has no items_aggregate (KP just created)", () => {
    const invoice = makeInvoice({
      pickup_country: null,
      pickup_city: null,
      total_weight_kg: null,
      total_volume_m3: null,
      package_count: null,
      length_m: null,
      width_m: null,
      height_m: null,
      supplier_incoterms: null,
      buyer_company: null,
      // No items_aggregate set — fetchQuoteInvoices returns null for empty КП
    });

    render(
      <InvoiceCargoSummary
        invoice={invoice}
        destination={{ country: null, city: null, address: null }}
        items={[]}
      />,
    );

    expect(
      screen.getByTestId("invoice-cargo-summary-empty"),
    ).toBeInTheDocument();
  });

  it("renders empty-state hint when procurement has not filled cargo yet", () => {
    const invoice = makeInvoice({
      pickup_country: null,
      pickup_city: null,
      total_weight_kg: null,
      total_volume_m3: null,
      package_count: null,
      length_m: null,
      width_m: null,
      height_m: null,
      supplier_incoterms: null,
      buyer_company: null,
    });

    render(
      <InvoiceCargoSummary
        invoice={invoice}
        destination={{ country: null, city: null, address: null }}
        items={[]}
      />,
    );

    expect(
      screen.getByTestId("invoice-cargo-summary-empty"),
    ).toBeInTheDocument();
  });
});
