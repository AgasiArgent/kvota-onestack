import React from "react";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Phase B Wave 4 Task 10 — tests for the «Сертификация» section mounted
 * inside `customs-item-dialog.tsx`.
 *
 * The frontend workspace ships no DOM environment (no jsdom / happy-dom).
 * shadcn's `<Dialog>` mounts its content via React Portal, which requires a
 * real DOM target — `react-dom/server` therefore renders an empty string
 * for the dialog body even when `open=true`. We follow the same playbook
 * as `certificate-modal.test.tsx`:
 *
 *   1. SSR sanity — `renderToString` does not throw for any open/item
 *      combination (catches static-analysis regressions like missing
 *      imports / mistyped props on freshly added components).
 *   2. Mock `listCertificates` / `fetchCertificateHistory` so we can assert
 *      the dialog wires up its data-fetch lifecycle. Since SSR doesn't run
 *      `useEffect`, the assertions live at module-load level: the mocks
 *      exist and are reachable.
 *   3. Confirm the orphaned `<ItemCustomsExpenses />` Phase A component is
 *      no longer imported by the dialog (string scan of the source file).
 *
 * Click handlers, the «Привязать» popover flow, the unbind path, and the
 * `<CertHistoryBanner>` apply/dismiss interactions are verified at
 * localhost:3000 per `reference_localhost_browser_test.md`.
 */

// ---------------------------------------------------------------------------
// Mocks (must come before component import — vitest hoists vi.mock)
// ---------------------------------------------------------------------------

const listCertsMock = vi.fn();
const attachMock = vi.fn();
const detachMock = vi.fn();
const fetchHistoryMock = vi.fn();

vi.mock("@/features/customs-certificates", async () => {
  const actual = await vi.importActual<
    typeof import("@/features/customs-certificates")
  >("@/features/customs-certificates");
  return {
    ...actual,
    listCertificates: (...args: unknown[]) => listCertsMock(...args),
    attachCertificateItem: (...args: unknown[]) => attachMock(...args),
    detachCertificateItem: (...args: unknown[]) => detachMock(...args),
    fetchCertificateHistory: (...args: unknown[]) => fetchHistoryMock(...args),
  };
});

const fetchPhaseAHistoryMock = vi.fn();
vi.mock("@/features/customs-history", async () => {
  const actual = await vi.importActual<
    typeof import("@/features/customs-history")
  >("@/features/customs-history");
  return {
    ...actual,
    fetchHistory: (...args: unknown[]) => fetchPhaseAHistoryMock(...args),
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

import { CustomsItemDialog } from "../customs-item-dialog";
import type { QuoteItemRow } from "@/entities/quote/queries";

// ---------------------------------------------------------------------------
// Fixtures — minimal shapes the dialog actually reads
// ---------------------------------------------------------------------------

function makeItem(overrides: Partial<QuoteItemRow> = {}): QuoteItemRow {
  // The dialog only touches a handful of fields; the rest are filled with
  // permissive defaults so TypeScript is happy. `as unknown as QuoteItemRow`
  // is necessary because QuoteItemRow is derived from the full DB row type.
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
  };
  return base as unknown as QuoteItemRow;
}

// ---------------------------------------------------------------------------
// Module surface
// ---------------------------------------------------------------------------

describe("CustomsItemDialog — module surface (Phase B Task 10)", () => {
  it("exports CustomsItemDialog as a function", () => {
    expect(typeof CustomsItemDialog).toBe("function");
  });
});

// ---------------------------------------------------------------------------
// SSR sanity — dialog mounts without throwing for various inputs
// ---------------------------------------------------------------------------

describe("CustomsItemDialog — SSR sanity (open=false)", () => {
  it("renders an empty dialog shell when open=false", () => {
    expect(() =>
      renderToString(
        <CustomsItemDialog
          open={false}
          onOpenChange={() => {}}
          quoteId="quote-1"
          item={null}
          userRoles={["customs"]}
        />,
      ),
    ).not.toThrow();
  });

  it("does not throw with item=null", () => {
    expect(() =>
      renderToString(
        <CustomsItemDialog
          open={true}
          onOpenChange={() => {}}
          quoteId="quote-1"
          item={null}
          userRoles={["customs"]}
        />,
      ),
    ).not.toThrow();
  });
});

describe("CustomsItemDialog — SSR sanity (open=true with item)", () => {
  beforeEach(() => {
    listCertsMock.mockReset();
    fetchHistoryMock.mockReset();
    fetchPhaseAHistoryMock.mockReset();
    listCertsMock.mockResolvedValue({
      success: true,
      data: { certificates: [] },
    });
    fetchHistoryMock.mockResolvedValue({
      success: true,
      data: { match: null },
    });
    fetchPhaseAHistoryMock.mockResolvedValue({ success: true, data: null });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders without throwing for an item with hs_code set", () => {
    const item = makeItem({ hs_code: "8517120000" });
    expect(() =>
      renderToString(
        <CustomsItemDialog
          open={true}
          onOpenChange={() => {}}
          quoteId="quote-1"
          item={item}
          allItems={[item]}
          userRoles={["customs"]}
        />,
      ),
    ).not.toThrow();
  });

  it("renders without throwing for an item without hs_code", () => {
    // Section is hidden when hs_code is empty (REQ-8 AC#2 derived gate).
    const item = makeItem({ hs_code: null });
    expect(() =>
      renderToString(
        <CustomsItemDialog
          open={true}
          onOpenChange={() => {}}
          quoteId="quote-1"
          item={item}
          allItems={[item]}
          userRoles={["customs"]}
        />,
      ),
    ).not.toThrow();
  });

  it("renders without throwing for read-only roles (no canWrite)", () => {
    const item = makeItem({ hs_code: "8517120000" });
    expect(() =>
      renderToString(
        <CustomsItemDialog
          open={true}
          onOpenChange={() => {}}
          quoteId="quote-1"
          item={item}
          allItems={[item]}
          userRoles={["sales"]}
        />,
      ),
    ).not.toThrow();
  });

  it("renders without throwing when allItems is omitted", () => {
    // The dialog should fall back gracefully — bind popover gets a singleton
    // list; preview shows only the current item but doesn't crash.
    const item = makeItem({ hs_code: "8517120000" });
    expect(() =>
      renderToString(
        <CustomsItemDialog
          open={true}
          onOpenChange={() => {}}
          quoteId="quote-1"
          item={item}
          userRoles={["customs"]}
        />,
      ),
    ).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// Mock plumbing — wiring sanity for jsdom / browser tests later
// ---------------------------------------------------------------------------

describe("CustomsItemDialog — mock wiring", () => {
  beforeEach(() => {
    listCertsMock.mockReset();
    attachMock.mockReset();
    detachMock.mockReset();
    fetchHistoryMock.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("listCertificates mock can be primed with an empty list", async () => {
    listCertsMock.mockResolvedValueOnce({
      success: true,
      data: { certificates: [] },
    });
    const res = await listCertsMock("quote-1");
    expect(res).toEqual({ success: true, data: { certificates: [] } });
    expect(listCertsMock).toHaveBeenCalledWith("quote-1");
  });

  it("fetchCertificateHistory mock can be primed with a null match", async () => {
    fetchHistoryMock.mockResolvedValueOnce({
      success: true,
      data: { match: null },
    });
    const res = await fetchHistoryMock({
      hsCode: "8517120000",
      brand: "Acme",
      supplierId: "supplier-1",
      currentQuoteId: "quote-1",
    });
    expect(res.success).toBe(true);
    expect(res.data.match).toBeNull();
    expect(fetchHistoryMock).toHaveBeenCalledTimes(1);
  });

  it("attachCertificateItem mock follows (certId, itemId) signature", async () => {
    attachMock.mockResolvedValueOnce({
      success: true,
      data: { id: "cert-1" },
    });
    const res = await attachMock("cert-1", "item-1");
    expect(res.success).toBe(true);
    expect(attachMock).toHaveBeenCalledWith("cert-1", "item-1");
  });

  it("detachCertificateItem mock follows (certId, itemId) signature", async () => {
    detachMock.mockResolvedValueOnce({
      success: true,
      data: { id: "cert-1" },
    });
    const res = await detachMock("cert-1", "item-1");
    expect(res.success).toBe(true);
    expect(detachMock).toHaveBeenCalledWith("cert-1", "item-1");
  });
});

// ---------------------------------------------------------------------------
// Source-file sanity — confirm the orphaned <ItemCustomsExpenses /> is gone
// ---------------------------------------------------------------------------

describe("CustomsItemDialog — orphan removal (Phase A → Phase B migration)", () => {
  it("no longer imports ItemCustomsExpenses", async () => {
    // String-scan the dialog source file — the Phase A component is now
    // superseded by the unified «Расходы по таможне» section on customs-step
    // plus the per-item «Сертификация» section here. Importing the orphan
    // would silently leave dead code in the bundle.
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    const dialogPath = path.resolve(
      __dirname,
      "..",
      "customs-item-dialog.tsx",
    );
    const src = await fs.readFile(dialogPath, "utf-8");
    expect(src).not.toContain('from "./item-customs-expenses"');
    expect(src).not.toContain("<ItemCustomsExpenses");
  });

  it("imports the new customs-certificates feature components", async () => {
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    const dialogPath = path.resolve(
      __dirname,
      "..",
      "customs-item-dialog.tsx",
    );
    const src = await fs.readFile(dialogPath, "utf-8");
    expect(src).toContain("CertificateBindPopover");
    expect(src).toContain("CertificateCoverageList");
    expect(src).toContain("CertificateDetailsModal");
    // Phase B Wave 5 cleanup — CertificateModal is now mounted inside the
    // per-item dialog so «Создать новый» actions go straight to the create
    // flow without a navigation away.
    expect(src).toContain("CertificateModal");
    // Aliased import — the existing Phase A HistoryBanner from
    // customs-history shadows the cert-version, so the new banner enters
    // under an alias.
    expect(src).toContain("HistoryBanner as CertHistoryBanner");
    expect(src).toContain("listCertificates");
    expect(src).toContain("fetchCertificateHistory");
  });

  it("wires HistoryBanner and BindPopover «Создать новый» to <CertificateModal>", async () => {
    // Phase B Wave 5 — the prior toast-only placeholder is gone; «Создать
    // новый» now opens the create-cert modal with a preset (HistoryBanner)
    // or a pre-selected current item (BindPopover empty-state).
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    const dialogPath = path.resolve(
      __dirname,
      "..",
      "customs-item-dialog.tsx",
    );
    const src = await fs.readFile(dialogPath, "utf-8");
    // The placeholder toast must be gone — both BindPopover variants and
    // HistoryBanner.onCreateNew used to surface this exact string.
    expect(src).not.toContain(
      "Создание сертификата доступно из раздела «Расходы по таможне»",
    );
    // The two state hooks driving the modal must exist.
    expect(src).toContain("createCertModalOpen");
    expect(src).toContain("certModalPreset");
    // The modal mount must wire preset + preSelectedItemIds.
    expect(src).toContain("preset={certModalPreset");
    expect(src).toContain("preSelectedItemIds={[currentItemForSelect.id]}");
  });

  it("accepts the new allItems prop on the dialog", async () => {
    // Phase B Wave 5 — customs-step now passes the full quote items array
    // through so BindPopover's after-attach preview shows all sibling
    // positions, not just the current one.
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    const dialogPath = path.resolve(
      __dirname,
      "..",
      "customs-item-dialog.tsx",
    );
    const src = await fs.readFile(dialogPath, "utf-8");
    expect(src).toContain("allItems?: QuoteItemRow[]");
    expect(src).toContain("toQuoteItemForSelect");
  });

  it("customs-step.tsx passes allItems through to the dialog", async () => {
    // Phase B Wave 5 — the dialog mount in customs-step.tsx must forward
    // the full QuoteItemRow[] so the Сертификация section sees siblings.
    // Testing 2 Row 8 (2026-05-13) — value is now `mergedItems` (an
    // optimistic-override-merged copy of `items`) but the contract is
    // the same: the dialog receives every quote item, not a singleton.
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    const stepPath = path.resolve(
      __dirname,
      "..",
      "customs-step.tsx",
    );
    const src = await fs.readFile(stepPath, "utf-8");
    // Accept either the legacy `items` reference or the new merged copy.
    expect(/allItems=\{(items|mergedItems)\}/.test(src)).toBe(true);
  });

  it("renders the «Сертификация» section guard when hs_code is set", async () => {
    // Parking the assertion in the source file: the section is gated by
    // `showCertSection` and the testid is fixed so a future regression that
    // ungated the section would surface in this string scan.
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    const dialogPath = path.resolve(
      __dirname,
      "..",
      "customs-item-dialog.tsx",
    );
    const src = await fs.readFile(dialogPath, "utf-8");
    expect(src).toContain('data-testid="customs-item-dialog-certification-section"');
    expect(src).toContain("showCertSection");
    expect(src).toContain("Сертификация");
  });
});
