// @vitest-environment jsdom
/**
 * Regression test for Testing 2 row 27 / FB-260514-123129-2203 —
 * «При выборе комбинированной или специфической пошлины и нажать на
 * пустое поле в модалке — выбор сбрасывается до ПРОСТАЯ».
 *
 * Root cause: the dialog's `Field` wrapper rendered a `<label>` element.
 * The «Пошлина» Field contains the rate-type chip group (Простая /
 * Комбинированная / Специфическая) followed by value/unit slots. The
 * browser's standard `<label>` behavior forwards stray clicks on the
 * label's text/whitespace to the FIRST focusable form control inside it
 * — which is the «Простая» chip button — silently resetting the user's
 * chosen rate type.
 *
 * Fix: `Field` now renders a `<div>` (no `htmlFor` was ever used on the
 * label, so this is a faithful no-op for the simple-input fields).
 */

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { QuoteItemRow } from "@/entities/quote/queries";

// Force ALTA off so the Manual UI (rate-type chips) is rendered
// unconditionally. With ALTA on, the chips would be hidden behind a
// Manual toggle and the bug would not be reproducible from a fresh row.
vi.mock("@/shared/lib/feature-flags", () => ({
  ALTA_FEATURES_ENABLED: false,
}));

// Stub heavy sibling features so the dialog mounts cleanly in jsdom.
vi.mock("@/features/customs-classify", () => ({ ClassifyButton: () => null }));
vi.mock("@/features/customs-country-dropdown", () => ({
  CustomsCountryDropdown: () => null,
}));
vi.mock("@/features/customs-rate-resolve", () => ({
  AutoResolveButton: () => null,
  RateBreakdown: () => null,
  SourceTimestamp: () => null,
  SpecialDutyBlock: () => null,
  formatDutyFormula: () => "—",
}));
vi.mock("@/features/customs-non-tariff-measures", () => ({
  MeasuresList: () => null,
}));
vi.mock("@/features/customs-history", () => ({
  HistoryBanner: () => null,
  fetchHistory: async () => ({ success: true, data: null }),
  formatDateRussian: (s: string) => s,
}));
vi.mock("@/features/customs-certificates", () => ({
  CertificateBindPopover: () => null,
  CertificateCoverageList: () => null,
  CertificateDetailsModal: () => null,
  CertificateModal: () => null,
  HistoryBanner: () => null,
  attachCertificateItem: async () => ({ success: true }),
  detachCertificateItem: async () => ({ success: true }),
  fetchCertificateHistory: async () => ({
    success: true,
    data: { match: null },
  }),
  listCertificates: async () => ({
    success: true,
    data: { certificates: [] },
  }),
}));
vi.mock("@/entities/quote/mutations", () => ({
  updateQuoteItem: async () => ({}),
}));
vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  },
}));

import { CustomsItemDialog } from "../customs-item-dialog";

function makeItem(overrides: Partial<QuoteItemRow> = {}): QuoteItemRow {
  return {
    id: "item-1",
    quote_id: "quote-1",
    position: 1,
    product_name: "Sample item",
    product_code: "SKU-1",
    quantity: 1,
    brand: "Acme",
    proforma_amount_excl_vat: 100_000,
    supplier_id: "supplier-1",
    hs_code: "",
    customs_duty: null,
    customs_duty_per_kg: null,
    customs_manual_override: false,
    customs_manual_rate_payload: null,
    has_origin_certificate: false,
    has_fta_certificate: false,
    country_of_origin_oksm: null,
    ...overrides,
  } as unknown as QuoteItemRow;
}

describe("CustomsItemDialog — duty rate-type preservation (Testing 2 row 27)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("clicking on the «Пошлина» label whitespace does NOT reset the rate type to «Простая»", async () => {
    const user = userEvent.setup();
    const item = makeItem();

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

    // The dialog renders synchronously when item is provided; chip group
    // is part of the initial paint.
    const combinedBtn = await screen.findByRole("button", {
      name: "Комбинированная",
    });
    const simpleBtn = screen.getByRole("button", { name: "Простая" });
    const specificBtn = screen.getByRole("button", { name: "Специфическая" });

    // Click Комбинированная — the chip group is the user-driven source of
    // truth for the rate type. After this click the «active» chip must be
    // Комбинированная (asserted indirectly via the buttons' classes).
    await user.click(combinedBtn);

    // The active chip carries `bg-accent` in ChipButton. Read the live
    // class state after the click to assert mode = combined.
    expect(combinedBtn.className).toContain("bg-accent");
    expect(simpleBtn.className).not.toContain("bg-accent");
    expect(specificBtn.className).not.toContain("bg-accent");

    // Now click the label text «Пошлина». This is the «пустое поле» the
    // tester described — clicking outside any input but inside the field
    // wrapper. Previously a `<label>` wrapper would forward this click to
    // the first focusable button inside (Простая), silently flipping the
    // rate type back to simple. With `Field` rendered as a `<div>`, the
    // click should be a no-op.
    const dutyLabel = screen.getByText("Пошлина");
    await user.click(dutyLabel);

    // Rate type must STILL be «Комбинированная» — the bug would flip it
    // back to «Простая» here.
    expect(combinedBtn.className).toContain("bg-accent");
    expect(simpleBtn.className).not.toContain("bg-accent");
  });

  it("clicking on the «Пошлина» field wrapper whitespace preserves Специфическая mode", async () => {
    const user = userEvent.setup();
    const item = makeItem();

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

    const specificBtn = await screen.findByRole("button", {
      name: "Специфическая",
    });
    const simpleBtn = screen.getByRole("button", { name: "Простая" });

    await user.click(specificBtn);
    expect(specificBtn.className).toContain("bg-accent");

    // Click the label text — second mode (Специфическая) must also survive.
    const dutyLabel = screen.getByText("Пошлина");
    await user.click(dutyLabel);

    expect(specificBtn.className).toContain("bg-accent");
    expect(simpleBtn.className).not.toContain("bg-accent");
  });

  it("«Пошлина» Field renders as a <div>, not a <label> (regression guard)", async () => {
    const item = makeItem();

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

    // Find the «Пошлина» label text, then walk up to the Field wrapper.
    // The wrapper must be a <div> — a <label> would re-introduce the
    // bug because labels forward clicks to the first form control inside.
    const labelText = await screen.findByText("Пошлина");
    const wrapper = labelText.closest(".flex.flex-col.gap-1");
    expect(wrapper).not.toBeNull();
    expect(wrapper?.tagName).toBe("DIV");
  });
});
