// @vitest-environment jsdom
/**
 * РОЛ Тест 07 #3.3 (cluster L-A, CRITICAL): the logistics view of a КПП
 * must show the actual cargo info entered by procurement — origin
 * country / city, total weight, total volume, package count and packed
 * dimensions — so the logistician can pick a route without bouncing
 * to the procurement tab.
 *
 * МОЛ Тест row 14 (extends #3.3): the panel must additionally show the
 * destination (Куда) read from the parent quote and a digest of which
 * items ride in this КПП. Tester also asked for «Транзит через Турцию»
 * but the underlying column does not exist in kvota.invoices — that
 * flag is deferred until a schema migration adds it.
 */
import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { InvoiceCargoSummary } from "../logistics-step/invoice-cargo-summary";
import type {
  QuoteInvoiceRow,
  QuoteItemRow,
} from "@/entities/quote/queries";

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

function makeItem(overrides: Partial<QuoteItemRow> = {}): QuoteItemRow {
  return {
    id: overrides.id ?? "item-1",
    quote_id: "q-1",
    position: 0,
    product_name: "Item",
    product_code: null,
    quantity: 1,
    description: null,
    unit: null,
    created_at: null,
    updated_at: null,
    brand: null,
    custom_fields: null,
    idn_sku: null,
    product_category: null,
    proforma_number: null,
    proforma_date: null,
    proforma_currency: null,
    proforma_amount_excl_vat: null,
    proforma_amount_incl_vat: null,
    proforma_amount_excl_vat_usd: null,
    proforma_amount_incl_vat_usd: null,
    purchasing_company_id: null,
    supplier_id: null,
    purchasing_manager_id: null,
    pickup_country: null,
    supplier_payment_country: null,
    procurement_status: null,
    procurement_completed_at: null,
    procurement_completed_by: null,
    hs_code: null,
    customs_duty: null,
    customs_extra: null,
    supplier_payment_terms: null,
    payer_company: null,
    advance_to_supplier_percent: null,
    procurement_notes: null,
    assigned_procurement_user: null,
    supplier_city: null,
    logistics_supplier_to_hub: null,
    logistics_hub_to_customs: null,
    logistics_customs_to_customer: null,
    logistics_total_days: null,
    buyer_company_id: null,
    pickup_location_id: null,
    volume_m3: null,
    is_unavailable: null,
    license_ds_required: null,
    license_ss_required: null,
    license_sgr_required: null,
    supplier_sku: null,
    item_idn: null,
    supplier_advance_percent: null,
    weight_kg: null,
    customs_duty_percent: null,
    customs_extra_cost: null,
    supplier_sku_note: null,
    manufacturer_product_name: null,
    vat_rate: null,
    customs_util_fee: null,
    customs_excise: null,
    customs_psm_pts: null,
    customs_notification: null,
    customs_licenses: null,
    customs_eco_fee: null,
    customs_honest_mark: null,
    customs_duty_per_kg: null,
    import_banned: null,
    import_ban_reason: null,
    composition_selected_invoice_id: null,
    name_en: null,
    country_of_origin_oksm: null,
    has_origin_certificate: false,
    has_fta_certificate: false,
    customs_manual_override: false,
    customs_manual_rate_payload: null,
    ...overrides,
  } as QuoteItemRow;
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

  it("renders destination (Куда) when delivery_* fields are passed", () => {
    render(
      <InvoiceCargoSummary
        invoice={makeInvoice({
          pickup_country: "Испания",
          pickup_city: "Lleida",
        })}
        destination={{
          country: "Россия",
          city: "Москва",
          address:
            "141701, Московская область, г. Долгопрудный, Лихачевский проезд, д. 5 Б",
        }}
      />,
    );
    expect(screen.getByText("Куда:")).toBeTruthy();
    expect(
      screen.getByText(/Россия, Москва, 141701, Московская область/),
    ).toBeTruthy();
  });

  it("omits destination when all delivery fields are empty", () => {
    render(
      <InvoiceCargoSummary
        invoice={makeInvoice({ pickup_country: "Испания" })}
        destination={{ country: null, city: null, address: null }}
      />,
    );
    expect(screen.queryByText("Куда:")).toBeNull();
  });

  it("renders cargo item count and ALL product names (Testing 2 row 14 v2)", () => {
    // Testers (РОЛ/МОЛ/МВЭД) require every item to be visible —
    // no «+N» overflow hint. The flex-wrap container handles long lists.
    const items: QuoteItemRow[] = [
      makeItem({
        id: "i1",
        composition_selected_invoice_id: "inv-1",
        product_name: "Шайбы 100шт",
      }),
      makeItem({
        id: "i2",
        composition_selected_invoice_id: "inv-1",
        product_name: "Трубка для масла, 2 метра",
      }),
      makeItem({
        id: "i3",
        composition_selected_invoice_id: "inv-1",
        product_name: "ЗИП Комплект",
      }),
      // Item belonging to a different invoice — must not contribute.
      makeItem({
        id: "i4",
        composition_selected_invoice_id: "inv-other",
        product_name: "Other invoice item",
      }),
    ];
    render(
      <InvoiceCargoSummary
        invoice={makeInvoice({ pickup_country: "Испания" })}
        items={items}
      />,
    );
    expect(screen.getByText("Груз:")).toBeTruthy();
    // Count is 3 (one item is on a different invoice and is excluded).
    const digest = screen.getByText(
      /3 позиции: Шайбы 100шт, Трубка для масла, 2 метра, ЗИП Комплект/,
    );
    expect(digest).toBeTruthy();
    // No "+N" overflow tail — every cargo item must be visible.
    expect(digest.textContent ?? "").not.toMatch(/\+\d/);
  });

  it("shows every product name when the invoice has 5+ items (no truncation)", () => {
    const names = [
      "Кабель силовой 10м",
      "Разъём BNC",
      "Изолента ПВХ",
      "Хомуты 100шт",
      "Маркер промышленный",
    ];
    const items: QuoteItemRow[] = names.map((n, idx) =>
      makeItem({
        id: `i-${idx}`,
        composition_selected_invoice_id: "inv-1",
        product_name: n,
      }),
    );
    render(
      <InvoiceCargoSummary
        invoice={makeInvoice({ pickup_country: "Россия" })}
        items={items}
      />,
    );
    expect(screen.getByText("Груз:")).toBeTruthy();
    const digest = screen.getByText(
      (content) =>
        content.startsWith("5 позиций:") &&
        names.every((n) => content.includes(n)),
    );
    expect(digest).toBeTruthy();
    // Every product name appears in document order, comma-separated.
    const text = digest.textContent ?? "";
    expect(text).toContain(`5 позиций: ${names.join(", ")}`);
    expect(text).not.toMatch(/\+\d/);
  });

  it("does not render cargo digest when no items belong to this invoice", () => {
    render(
      <InvoiceCargoSummary
        invoice={makeInvoice({ pickup_country: "Испания" })}
        items={[
          makeItem({
            composition_selected_invoice_id: "inv-other",
            product_name: "Other invoice item",
          }),
        ]}
      />,
    );
    expect(screen.queryByText("Груз:")).toBeNull();
  });
});
