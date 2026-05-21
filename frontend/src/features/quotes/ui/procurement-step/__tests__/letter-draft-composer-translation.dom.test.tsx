// @vitest-environment jsdom
/**
 * РОЗ-117 / МОЗ-104 — letter-draft composer must render translated
 * position names when language=EN.
 *
 * Source of truth for the translation is `quote_items.name_en` (filled by
 * sales). The supplier-side `invoice_items` table has no translation column
 * — translations are joined via `invoice_item_coverage`. The composer reads
 * `name_en` directly off each item it receives; the wiring lives in
 * `invoice-card.tsx`, which builds `salesByItemId` (now including `name_en`)
 * and forwards it onto the composer's `items` prop.
 *
 * What this file pins:
 *   1. When language=EN and `name_en` is set, the composer body must
 *      contain the translated name (not the Russian product_name).
 *   2. When language=EN and `name_en` is null, the composer body must
 *      gracefully fall back to product_name (no crash, no empty row).
 *   3. When language=RU, the composer body must always render
 *      product_name regardless of name_en.
 *
 * The XLS export side of the same fix lives in
 * `services/xls_export_service.py` — `_get_item_name` already prefers
 * `name_en` for EN exports. This test focuses on the email-letter path
 * because that's where the regression was reported.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { QuoteItemRow } from "@/entities/quote/queries";

// ---------------------------------------------------------------------------
// Mocks (must come before component import — vitest hoists vi.mock)
// ---------------------------------------------------------------------------

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({
        data: { session: { access_token: "test-token" } },
      }),
    },
    from: () => ({
      select: () => ({
        eq: () => ({
          order: () => ({
            select: async () => ({ data: [], error: null }),
          }),
        }),
        in: async () => ({ data: [], error: null }),
      }),
    }),
  }),
}));

// `fetchActiveLetterDraft` returns null so the composer falls through to
// the template-render branch — that's where name_en consumption happens.
vi.mock("@/entities/invoice/queries", () => ({
  fetchActiveLetterDraft: async () => null,
}));

// Mutations are stubbed — the test never actually saves/sends.
vi.mock("@/entities/invoice/mutations", () => ({
  saveLetterDraft: async () => {},
  sendLetterDraft: async () => {},
}));

vi.mock("@/entities/quote/server-actions", () => ({
  notifyInvoiceSentForKanban: async () => ({ advancedSlices: [] }),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  },
}));

import { LetterDraftComposer } from "../letter-draft-composer";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeItem(overrides: Partial<QuoteItemRow> = {}): QuoteItemRow {
  // Minimal QuoteItemRow shape — only the fields the composer reads need
  // real values; the rest are nulls. Mirrors the make pattern used by
  // sibling SSR tests (invoice-card.test.tsx).
  const base = {
    id: "qi-1",
    quote_id: "q-1",
    position: 1,
    product_name: "Шуруп оцинкованный 4×30",
    product_code: "SKU-1",
    quantity: 100,
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

// Helper: get the composer's body textarea text once it has settled.
// The Textarea uses shadcn's `Textarea` component which doesn't link the
// label to the textarea via `htmlFor`/`id`; using `getByRole('textbox')`
// finds inputs too. The composer has exactly one <textarea> in its form.
async function getBodyText(): Promise<string> {
  // Wait for the form to be rendered (no longer in loading state).
  // Subject input has a stable placeholder we can poll on.
  await screen.findByPlaceholderText("Запрос коммерческого предложения");
  const textarea = document.querySelector("textarea");
  if (!textarea) throw new Error("textarea not rendered yet");
  return textarea.value;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("LetterDraftComposer — translation wiring (РОЗ-117 / МОЗ-104)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders quote_items.name_en in the EN letter body when sales has filled it", async () => {
    const item = makeItem({
      product_name: "Шуруп оцинкованный 4×30",
      name_en: "Galvanized screw 4x30",
    });

    render(
      <LetterDraftComposer
        open
        onClose={() => {}}
        invoiceId="inv-1"
        supplierName="Test Supplier"
        supplierEmail="supplier@test.com"
        items={[item]}
        currency="USD"
        incoterms="FOB"
        pickupCountry="China"
        initialLanguage="en"
      />,
    );

    await waitFor(async () => {
      const body = await getBodyText();
      // EN translation should win over the Russian product_name.
      expect(body).toContain("Galvanized screw 4x30");
      expect(body).not.toContain("Шуруп оцинкованный 4×30");
    });
  });

  it("falls back to product_name in the EN letter body when name_en is null (no crash, no empty row)", async () => {
    const item = makeItem({
      product_name: "Шуруп оцинкованный 4×30",
      name_en: null,
    });

    render(
      <LetterDraftComposer
        open
        onClose={() => {}}
        invoiceId="inv-1"
        supplierName="Test Supplier"
        supplierEmail="supplier@test.com"
        items={[item]}
        currency="USD"
        incoterms="FOB"
        pickupCountry="China"
        initialLanguage="en"
      />,
    );

    await waitFor(async () => {
      const body = await getBodyText();
      // Without a translation we render the Russian name verbatim plus an
      // explicit marker so the supplier (and the МОЗ sender) can see at a
      // glance that the line is intentionally bilingual rather than a typo.
      // Silent fallback is what testers reported as МОЗ-104.
      expect(body).toContain("Шуруп оцинкованный 4×30 (no translation)");
      // Sanity: the (quantity pcs) suffix tells us the row was rendered,
      // not silently dropped.
      expect(body).toContain("(100 pcs)");
    });
  });

  it("renders product_name in the RU letter body regardless of name_en", async () => {
    const item = makeItem({
      product_name: "Шуруп оцинкованный 4×30",
      name_en: "Galvanized screw 4x30",
    });

    render(
      <LetterDraftComposer
        open
        onClose={() => {}}
        invoiceId="inv-1"
        supplierName="Тест Поставщик"
        supplierEmail="supplier@test.com"
        items={[item]}
        currency="USD"
        incoterms="FOB"
        pickupCountry="Китай"
        initialLanguage="ru"
      />,
    );

    await waitFor(async () => {
      const body = await getBodyText();
      // RU letter must always use the Russian product_name even when a
      // translation exists — the translation is for outbound EN docs only.
      expect(body).toContain("Шуруп оцинкованный 4×30");
      expect(body).not.toContain("Galvanized screw 4x30");
      // Russian quantity unit (шт.) confirms the RU template was rendered.
      expect(body).toContain("(100 шт.)");
    });
  });

  it("switching from RU to EN swaps product_name for name_en in the (untouched) body", async () => {
    const user = userEvent.setup();
    const item = makeItem({
      product_name: "Шуруп оцинкованный 4×30",
      name_en: "Galvanized screw 4x30",
    });

    render(
      <LetterDraftComposer
        open
        onClose={() => {}}
        invoiceId="inv-1"
        supplierName="Test Supplier"
        supplierEmail="supplier@test.com"
        items={[item]}
        currency="USD"
        incoterms="FOB"
        pickupCountry="China"
        initialLanguage="ru"
      />,
    );

    // Start in RU — Russian name visible.
    await waitFor(async () => {
      const body = await getBodyText();
      expect(body).toContain("Шуруп оцинкованный 4×30");
    });

    // Click the EN toggle — body should re-render with the translation
    // (the user hasn't edited it, so the snapshot guard lets us overwrite).
    await user.click(screen.getByRole("radio", { name: "EN" }));

    await waitFor(async () => {
      const body = await getBodyText();
      expect(body).toContain("Galvanized screw 4x30");
      expect(body).not.toContain("Шуруп оцинкованный 4×30");
    });
  });
});
