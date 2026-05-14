/**
 * Regression tests for Testing 2 rows 8/9 (customs duty modal silently
 * dropped mode/value/unit on save).
 *
 * Root cause:
 *
 *   `DutyRateInput` derives the visible UI from
 *     `isManual = !showAutoToggle || form.duty_manual_mode`
 *   where `showAutoToggle = ALTA_FEATURES_ENABLED`. When the flag is OFF
 *   the Auto/Manual toggle is hidden and the Manual UI is rendered
 *   unconditionally — regardless of `form.duty_manual_mode`.
 *
 *   But `buildUpdates` switched branches purely on `form.duty_manual_mode`:
 *     if (!form.duty_manual_mode) { /* Auto branch reads form.duty_value *\/ }
 *
 *   For a fresh row (no prior `customs_manual_override` saved), the seed
 *   state was `duty_manual_mode = false`. The user interacted with Manual
 *   slots (Простая / Комбинированная / Специфическая + value + unit), the
 *   controlled state updated correctly, but on save `buildUpdates` took the
 *   Auto branch and read the empty `form.duty_value` — silently producing
 *   `{ customs_duty: 0, customs_duty_per_kg: null }` regardless of what
 *   the user typed.
 *
 * Fix: seed state derives `duty_manual_mode` the same way the UI does —
 *   `manualOverride || !ALTA_FEATURES_ENABLED`. The save handler now takes
 *   the Manual branch whenever the Manual UI was the only thing rendered.
 */

import { describe, it, expect, vi } from "vitest";

// Force the flag OFF before the module under test imports
// `@/shared/lib/feature-flags`. The flag is captured at module-load time
// from `process.env.NEXT_PUBLIC_ALTA_FEATURES_ENABLED === "true"`, so the
// test needs to either stub the env before import OR mock the module.
// Module mock is cleaner and survives bundler env-inlining.
vi.mock("@/shared/lib/feature-flags", () => ({
  ALTA_FEATURES_ENABLED: false,
}));

// Stub heavy sibling modules so the customs-item-dialog import graph
// doesn't drag in Handsontable / Radix / API client side effects in the
// node-env vitest project.
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
  fetchCertificateHistory: async () => ({ success: true, data: { match: null } }),
  listCertificates: async () => ({ success: true, data: { certificates: [] } }),
}));
vi.mock("@/entities/quote/mutations", () => ({
  updateQuoteItem: async () => ({}),
}));

import {
  buildUpdates,
  stateFromItem,
} from "../customs-item-dialog";
import type { QuoteItemRow } from "@/entities/quote/queries";

// Minimal item: no prior customs_manual_override, no manual payload, no
// customs_duty value. Mirrors a fresh row a tester would open from the
// customs Handsontable.
function freshItem(): QuoteItemRow {
  return {
    id: "00000000-0000-0000-0000-000000000001",
    quote_id: "00000000-0000-0000-0000-000000000002",
    position: 1,
    product_name: "Test position",
    product_code: "TEST-001",
    brand: null,
    quantity: 1,
    customs_duty: 0,
    customs_duty_per_kg: null,
    customs_manual_override: false,
    customs_manual_rate_payload: null,
  } as unknown as QuoteItemRow;
}

describe("stateFromItem — ALTA_FEATURES_ENABLED=false forces Manual seed", () => {
  it("seeds duty_manual_mode=true when ALTA flag is off (Manual UI is the only UI)", () => {
    const form = stateFromItem(freshItem());
    // Critical invariant: UI shows Manual, save handler must use Manual.
    expect(form.duty_manual_mode).toBe(true);
  });
});

describe(
  "buildUpdates — Testing 2 rows 8/9 regression " +
    "(Специфическая 250 EUR/kg persists)",
  () => {
    it(
      "writes customs_duty_per_kg=250 + customs_manual_rate_payload " +
        "when user picks Специфическая + 250 + EUR/kg on a fresh row",
      () => {
        // Reproduce the exact tester repro:
        //   1. Open modal on fresh row
        //   2. Mode = Специфическая
        //   3. Value = 250
        //   4. Unit = EUR/kg
        //   5. Save
        const form = stateFromItem(freshItem());
        // User changes flow through the `update()` helper — simulated via
        // a plain spread. `duty_manual_mode` stays true (seeded by fix).
        const userEdited = {
          ...form,
          duty_rate_type: "specific" as const,
          duty_value_1: "250",
          duty_unit_1: "EUR/kg" as const,
        };

        const updates = buildUpdates(userEdited);

        // The chip + value + unit must all survive the save.
        expect(updates.customs_manual_override).toBe(true);
        expect(updates.customs_duty).toBeNull();
        expect(updates.customs_duty_per_kg).toBe(250);
        expect(updates.customs_manual_rate_payload).toMatchObject({
          duty_rate_type: "specific",
          value_1_number: 250,
          value_1_unit: "EUR/kg",
          value_1_currency: "EUR",
        });
      },
    );

    it(
      "writes customs_duty=5 + percent payload when user picks Простая + 5 + %",
      () => {
        const form = stateFromItem(freshItem());
        const userEdited = {
          ...form,
          duty_rate_type: "simple" as const,
          duty_value_1: "5",
          duty_unit_1: "percent" as const,
        };

        const updates = buildUpdates(userEdited);

        expect(updates.customs_manual_override).toBe(true);
        expect(updates.customs_duty).toBe(5);
        expect(updates.customs_duty_per_kg).toBeNull();
        expect(updates.customs_manual_rate_payload).toMatchObject({
          duty_rate_type: "simple",
          value_1_number: 5,
          value_1_unit: "percent",
        });
      },
    );

    it(
      "does NOT silently drop user-entered slot 1 to the legacy Auto branch",
      () => {
        // Tester observed PATCH body: `customs_duty: 0, customs_duty_per_kg: null`.
        // The Auto branch reads `form.duty_value` (untouched, defaults to the
        // pre-existing customs_duty). This test would have caught that.
        const form = stateFromItem(freshItem());
        const userEdited = {
          ...form,
          duty_rate_type: "specific" as const,
          duty_value_1: "250",
          duty_unit_1: "EUR/kg" as const,
        };
        const updates = buildUpdates(userEdited);

        // Bug shape: customs_duty=0, customs_duty_per_kg=null, no payload.
        // The assertions below are the inverse — any of them failing means
        // the Auto-branch regression is back.
        expect(updates.customs_duty).not.toBe(0);
        expect(updates.customs_manual_rate_payload).not.toBeNull();
      },
    );
  },
);
