// @vitest-environment jsdom
/**
 * Phase 4 hotfix plan — jsdom test for the per-item dialog's
 * «Сертификация» empty-state.
 *
 * REQ-8 AC#3 mandates two buttons inside the amber empty-state card when
 * an item has no certificates attached:
 *   • «Привязать к существующему» — opens the bind popover.
 *   • «Создать новый» — opens <CertificateModal> with the current item
 *     pre-ticked via `preSelectedItemIds`.
 *
 * The pre-Phase-4 code shipped only the «Привязать» button. This file
 * locks the new wiring in:
 *   1. Both buttons render in the amber empty-state container.
 *   2. Clicking «Создать новый» mounts <CertificateModal> with
 *      `preSelectedItemIds=[item.id]` so the current position is
 *      auto-ticked in the multi-select on first render.
 *
 * SSR coverage of the same dialog lives in
 * `customs-item-dialog-certification.test.tsx` — that file uses
 * `react-dom/server` and cannot mount Radix portal contents. jsdom +
 * @testing-library/react are the right substrate for click flow.
 */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { QuoteItemRow } from "@/entities/quote/queries";

// ---------------------------------------------------------------------------
// Mocks (must come before component import — vitest hoists vi.mock)
// ---------------------------------------------------------------------------

// `listCertificates` returns an empty list so the empty-state branch renders.
// `fetchCertificateHistory` returns no match so the history banner stays
// hidden and never steals focus from the empty-state card.
const listCertsMock = vi.fn();
const fetchHistoryMock = vi.fn();

// Spy on the props <CertificateModal> receives. The component itself is
// stubbed out so we don't have to mount its full form internals.
const certificateModalSpy = vi.fn();

vi.mock("@/features/customs-certificates", async () => {
  const actual = await vi.importActual<
    typeof import("@/features/customs-certificates")
  >("@/features/customs-certificates");
  return {
    ...actual,
    listCertificates: (...args: unknown[]) => listCertsMock(...args),
    fetchCertificateHistory: (...args: unknown[]) => fetchHistoryMock(...args),
    // Lightweight stub — render a sentinel that exposes the controlling
    // props as `data-*` attributes so tests can assert without poking at
    // React internals.
    CertificateModal: (props: {
      open: boolean;
      preSelectedItemIds?: string[];
      quoteId: string;
    }) => {
      certificateModalSpy(props);
      if (!props.open) return null;
      return (
        <div
          data-testid="certificate-modal-stub"
          data-pre-selected={JSON.stringify(props.preSelectedItemIds ?? [])}
          data-quote-id={props.quoteId}
        >
          stub
        </div>
      );
    },
  };
});

// Phase A history banner is also a no-op so its fetch lifecycle does not
// race with the empty-state assertions.
vi.mock("@/features/customs-history", async () => {
  const actual = await vi.importActual<
    typeof import("@/features/customs-history")
  >("@/features/customs-history");
  return {
    ...actual,
    fetchHistory: vi.fn().mockResolvedValue({ success: true, data: null }),
  };
});

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  },
}));

// `customs-rate-resolve` makes a dynamic import for AltaResolveButton — it
// pulls server-only chunks that jsdom can't load. The module is otherwise
// orthogonal to the empty-state assertions.
vi.mock("@/features/customs-rate-resolve", async () => {
  const actual = await vi.importActual<
    typeof import("@/features/customs-rate-resolve")
  >("@/features/customs-rate-resolve");
  return {
    ...actual,
    AutoResolveButton: () => null,
    RateBreakdown: () => null,
    SourceTimestamp: () => null,
    SpecialDutyBlock: () => null,
  };
});

import { CustomsItemDialog } from "../customs-item-dialog";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeItem(overrides: Partial<QuoteItemRow> = {}): QuoteItemRow {
  // Same minimal-row pattern as the existing SSR test — only the fields
  // the dialog actually reads need real values; the rest are nulls.
  const base = {
    id: "item-1",
    quote_id: "quote-1",
    position: 1,
    product_name: "Sample item",
    product_code: "SKU-1",
    quantity: 1,
    description: null,
    unit: null,
    created_at: null,
    updated_at: null,
    brand: "Acme",
    custom_fields: null,
    idn_sku: null,
    product_category: null,
    proforma_number: null,
    proforma_date: null,
    proforma_currency: null,
    proforma_amount_excl_vat: 100_000,
    proforma_amount_incl_vat: null,
    proforma_amount_excl_vat_usd: null,
    proforma_amount_incl_vat_usd: null,
    purchasing_company_id: null,
    supplier_id: "supplier-1",
    purchasing_manager_id: null,
    pickup_country: null,
    supplier_payment_country: null,
    procurement_status: null,
    procurement_completed_at: null,
    procurement_completed_by: null,
    hs_code: "8517120000",
    customs_duty: null,
    customs_extra: null,
    payer_company: null,
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
  };
  return base as unknown as QuoteItemRow;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CustomsItemDialog — empty-state «Сертификация» (Phase 4)", () => {
  beforeEach(() => {
    listCertsMock.mockReset();
    fetchHistoryMock.mockReset();
    certificateModalSpy.mockReset();
    listCertsMock.mockResolvedValue({
      success: true,
      data: { certificates: [] },
    });
    fetchHistoryMock.mockResolvedValue({
      success: true,
      data: { match: null },
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders both «Привязать к существующему» and «Создать новый» buttons in the amber empty-state", async () => {
    const item = makeItem({ hs_code: "8517120000" });

    render(
      <CustomsItemDialog
        open={true}
        onOpenChange={() => {}}
        quoteId="quote-1"
        item={item}
        allItems={[item]}
        userRoles={["customs"]}
      />,
    );

    // The empty-state card is keyed by its testid — wait for it to surface
    // after `useEffect` settles the cert fetch.
    const emptyCard = await screen.findByTestId(
      "customs-item-dialog-certification-empty",
    );

    // REQ-8 AC#3 copy must match the spec mockup verbatim.
    expect(emptyCard).toHaveTextContent("Сертификат соответствия не оформлен");

    // Bind trigger — outline variant, opens the existing popover.
    expect(
      within(emptyCard).getByTestId(
        "customs-item-dialog-cert-bind-trigger",
      ),
    ).toHaveTextContent("Привязать к существующему");

    // Create trigger — default variant, opens <CertificateModal>.
    expect(
      within(emptyCard).getByTestId(
        "customs-item-dialog-cert-create-trigger",
      ),
    ).toHaveTextContent("Создать новый");
  });

  it("clicking «Создать новый» opens <CertificateModal> with the current item pre-ticked via preSelectedItemIds", async () => {
    const user = userEvent.setup();
    const item = makeItem({ hs_code: "8517120000" });

    render(
      <CustomsItemDialog
        open={true}
        onOpenChange={() => {}}
        quoteId="quote-1"
        item={item}
        allItems={[item]}
        userRoles={["customs"]}
      />,
    );

    const createBtn = await screen.findByTestId(
      "customs-item-dialog-cert-create-trigger",
    );

    // Modal stub stays mounted but invisible while open=false (the stub
    // returns null when not open, so the testid query must fail before the
    // click).
    expect(
      screen.queryByTestId("certificate-modal-stub"),
    ).not.toBeInTheDocument();

    await user.click(createBtn);

    // After click, the modal stub renders with the controlling props from
    // the parent. preSelectedItemIds MUST contain the current item id so
    // the multi-select inside the real modal pre-ticks the row.
    const modalStub = await screen.findByTestId("certificate-modal-stub");
    expect(modalStub).toHaveAttribute("data-quote-id", "quote-1");
    expect(modalStub).toHaveAttribute(
      "data-pre-selected",
      JSON.stringify([item.id]),
    );

    // Sanity check the spy directly — last call's `open` must be `true`
    // and `preSelectedItemIds` must match the current item.
    const lastCallProps = certificateModalSpy.mock.calls.at(-1)?.[0];
    expect(lastCallProps).toMatchObject({
      open: true,
      quoteId: "quote-1",
      preSelectedItemIds: [item.id],
    });
  });
});
