/**
 * Persistence-layer tests for the Manual duty-rate UI (Phase A Req 4, Task 10).
 *
 * Covers the pure helpers exported from customs-item-dialog.tsx:
 *   - buildManualRatePayload: shape compatible with Alta Rate dataclass
 *   - buildUpdates: customs_manual_override + customs_manual_rate_payload
 *     persistence in Manual mode; legacy customs_duty / customs_duty_per_kg
 *     in Auto mode
 *
 * The DOM-bound dialog itself (toggle visibility, conditional rendering of
 * slot 2, etc.) is exercised via integration / browser tests; this file
 * unit-tests the data plumbing.
 */

import { describe, it, expect } from "vitest";

import {
  buildManualRatePayload,
  buildUpdates,
  type FormState,
} from "../customs-item-dialog";

const BASE_FORM: FormState = {
  hs_code: "8517120000",
  duty_mode: "pct",
  duty_value: "10",
  customs_util_fee: "",
  customs_excise: "",
  customs_psm_pts: "",
  customs_notification: "",
  customs_licenses: "",
  customs_eco_fee: "",
  customs_honest_mark: "",
  import_banned: false,
  import_ban_reason: "",
  license_ds_required: false,
  license_ss_required: false,
  license_sgr_required: false,
  country_of_origin_oksm: 156,
  has_origin_certificate: false,
  has_fta_certificate: false,
  // Manual fields
  duty_manual_mode: false,
  duty_rate_type: "simple",
  duty_value_1: "",
  duty_unit_1: "percent",
  duty_value_2: "",
  duty_unit_2: "EUR/kg",
  duty_sign: null,
};

describe("buildManualRatePayload", () => {
  it("returns simple-percent shape for rate_type='simple'", () => {
    const payload = buildManualRatePayload({
      duty_rate_type: "simple",
      duty_value_1: "10",
      duty_unit_1: "percent",
      duty_value_2: "",
      duty_unit_2: "EUR/kg",
      duty_sign: null,
    });
    expect(payload).toEqual({
      duty_rate_type: "simple",
      value_1_number: 10,
      value_1_unit: "percent",
      value_1_currency: null,
      value_2_number: null,
      value_2_unit: null,
      value_2_currency: null,
      sign_1: null,
    });
  });

  it("returns combined shape with sign + both slots", () => {
    const payload = buildManualRatePayload({
      duty_rate_type: "combined",
      duty_value_1: "10",
      duty_unit_1: "percent",
      duty_value_2: "0.04",
      duty_unit_2: "EUR/kg",
      duty_sign: ">",
    });
    expect(payload).toEqual({
      duty_rate_type: "combined",
      value_1_number: 10,
      value_1_unit: "percent",
      value_1_currency: null,
      value_2_number: 0.04,
      value_2_unit: "EUR/kg",
      value_2_currency: "EUR",
      sign_1: ">",
    });
  });

  it("returns specific shape with currency extracted from unit", () => {
    const payload = buildManualRatePayload({
      duty_rate_type: "specific",
      duty_value_1: "0.5",
      duty_unit_1: "USD/kg",
      duty_value_2: "",
      duty_unit_2: "EUR/kg",
      duty_sign: null,
    });
    expect(payload.value_1_currency).toBe("USD");
    expect(payload.value_2_number).toBeNull();
    expect(payload.sign_1).toBeNull();
  });

  it("ignores slot 2 fields when rate_type is not 'combined'", () => {
    // Even if user previously filled slot 2 then switched to "simple",
    // the payload should null slot 2 + sign.
    const payload = buildManualRatePayload({
      duty_rate_type: "simple",
      duty_value_1: "10",
      duty_unit_1: "percent",
      duty_value_2: "0.04",
      duty_unit_2: "EUR/kg",
      duty_sign: ">",
    });
    expect(payload.value_2_number).toBeNull();
    expect(payload.value_2_unit).toBeNull();
    expect(payload.value_2_currency).toBeNull();
    expect(payload.sign_1).toBeNull();
  });
});

describe("buildUpdates — Auto mode (legacy compatibility)", () => {
  it("writes customs_duty when duty_mode='pct'", () => {
    const updates = buildUpdates({ ...BASE_FORM, duty_mode: "pct" });
    expect(updates.customs_duty).toBe(10);
    expect(updates.customs_duty_per_kg).toBeNull();
    expect(updates.customs_manual_override).toBe(false);
    expect(updates.customs_manual_rate_payload).toBeNull();
  });

  it("writes customs_duty_per_kg when duty_mode='perKg'", () => {
    const updates = buildUpdates({
      ...BASE_FORM,
      duty_mode: "perKg",
      duty_value: "0.5",
    });
    expect(updates.customs_duty).toBeNull();
    expect(updates.customs_duty_per_kg).toBe(0.5);
  });

  it("does not include manual payload in Auto mode", () => {
    const updates = buildUpdates(BASE_FORM);
    expect(updates.customs_manual_override).toBe(false);
    expect(updates.customs_manual_rate_payload).toBeNull();
  });

  it("normalizes hs_code — strips separators from pasted code", () => {
    const updates = buildUpdates({ ...BASE_FORM, hs_code: "8517 12 0000" });
    expect(updates.hs_code).toBe("8517120000");
  });

  it("normalizes hs_code — empty after normalization becomes null", () => {
    const updates = buildUpdates({ ...BASE_FORM, hs_code: "  " });
    expect(updates.hs_code).toBeNull();
  });
});

describe("buildUpdates — Manual mode persists payload", () => {
  it("sets customs_manual_override=true and writes 3-slot payload", () => {
    const form: FormState = {
      ...BASE_FORM,
      duty_manual_mode: true,
      duty_rate_type: "combined",
      duty_value_1: "10",
      duty_unit_1: "percent",
      duty_value_2: "0.04",
      duty_unit_2: "EUR/kg",
      duty_sign: ">",
    };
    const updates = buildUpdates(form);
    expect(updates.customs_manual_override).toBe(true);
    expect(updates.customs_manual_rate_payload).toEqual({
      duty_rate_type: "combined",
      value_1_number: 10,
      value_1_unit: "percent",
      value_1_currency: null,
      value_2_number: 0.04,
      value_2_unit: "EUR/kg",
      value_2_currency: "EUR",
      sign_1: ">",
    });
  });

  it("derives customs_duty from slot 1 when unit_1='percent'", () => {
    const form: FormState = {
      ...BASE_FORM,
      duty_manual_mode: true,
      duty_rate_type: "simple",
      duty_value_1: "5",
      duty_unit_1: "percent",
    };
    const updates = buildUpdates(form);
    // Calc-engine continues to read this column unchanged.
    expect(updates.customs_duty).toBe(5);
    expect(updates.customs_duty_per_kg).toBeNull();
  });

  it("derives customs_duty_per_kg from slot 1 when unit_1 is non-percent", () => {
    const form: FormState = {
      ...BASE_FORM,
      duty_manual_mode: true,
      duty_rate_type: "specific",
      duty_value_1: "0.04",
      duty_unit_1: "EUR/kg",
    };
    const updates = buildUpdates(form);
    expect(updates.customs_duty).toBeNull();
    expect(updates.customs_duty_per_kg).toBe(0.04);
  });
});

/**
 * Regression test for FB-260511-212235-0384.
 *
 * Migration 284 (Phase 5d) dropped `license_ds_cost`, `license_ss_cost`,
 * and `license_sgr_cost` from `kvota.quote_items` — per-supplier costs
 * now live on `kvota.invoice_items`, and ad-hoc «общий расход на КП» lives
 * on `kvota.quote_certificates` with `is_custom_expense=true`.
 *
 * If anyone re-introduces those keys into `buildUpdates()` output, every
 * customs-item save will fail with PostgREST 400 PGRST204 (ghost column).
 */
describe("buildUpdates — no license_*_cost ghost columns (FB-260511-212235-0384)", () => {
  const GHOST_KEYS = [
    "license_ds_cost",
    "license_ss_cost",
    "license_sgr_cost",
  ] as const;

  it("does not emit ghost license_*_cost keys in Auto mode", () => {
    const updates = buildUpdates({ ...BASE_FORM, duty_manual_mode: false });
    for (const key of GHOST_KEYS) {
      expect(updates).not.toHaveProperty(key);
    }
  });

  it("does not emit ghost license_*_cost keys in Manual mode", () => {
    const updates = buildUpdates({
      ...BASE_FORM,
      duty_manual_mode: true,
      duty_rate_type: "simple",
      duty_value_1: "10",
      duty_unit_1: "percent",
    });
    for (const key of GHOST_KEYS) {
      expect(updates).not.toHaveProperty(key);
    }
  });
});

/**
 * Source-sanity regression for FB-260511-212235-0384 — guards the wider
 * write-paths flagged in Phase 5a review.
 *
 * Phase 5a review identified 4 more files that referenced
 * `license_(ds|ss|sgr)_cost` after migration 284 dropped the columns from
 * `kvota.quote_items`:
 *
 *   - `customs-handsontable.tsx` — inline edit path (CRITICAL: live broken).
 *   - `customs-step.tsx#handleBulkAccept` — `/api/customs/{id}/items/bulk`
 *     payload (CRITICAL: dormant only because ALTA_FEATURES_ENABLED=false).
 *   - `customs-columns.ts` / `customs-views.ts` — column registry leakage
 *     (HIGH: cosmetic empty columns if user toggles visibility).
 *   - `features/customs-autofill/types.ts` — `CustomsAutofillSuggestion`
 *     contract (HIGH: shape drift, FE expected fields that backend no
 *     longer returns).
 *
 * The asserts below use the same readFileSync source-scan pattern as
 * `customs-item-dialog-certification.test.tsx` (orphan removal block) so
 * the regression catches re-introductions without needing to render the
 * Handsontable in jsdom.
 */
describe(
  "customs-step source sanity — no license_*_cost ghosts (FB-260511-212235-0384)",
  () => {
    const GHOST_RE = /license_(ds|ss|sgr)_cost/;

    async function readSiblingSource(filename: string): Promise<string> {
      const fs = await import("node:fs/promises");
      const path = await import("node:path");
      const filePath = path.resolve(__dirname, "..", filename);
      return fs.readFile(filePath, "utf-8");
    }

    it("customs-handsontable.tsx no longer references license_*_cost", async () => {
      const src = await readSiblingSource("customs-handsontable.tsx");
      expect(src).not.toMatch(GHOST_RE);
    });

    it("customs-step.tsx handleBulkAccept payload omits license_*_cost", async () => {
      const src = await readSiblingSource("customs-step.tsx");
      expect(src).not.toMatch(GHOST_RE);
    });

    it("customs-columns.ts registry omits license_*_cost", async () => {
      const src = await readSiblingSource("customs-columns.ts");
      expect(src).not.toMatch(GHOST_RE);
    });

    it("customs-views.ts presets omit license_*_cost", async () => {
      const src = await readSiblingSource("customs-views.ts");
      expect(src).not.toMatch(GHOST_RE);
    });

    it(
      "customs-autofill types omit license_*_cost (contract removed)",
      async () => {
        const fs = await import("node:fs/promises");
        const path = await import("node:path");
        // __tests__ → customs-step → ui → quotes → features → customs-autofill/types.ts
        const typesPath = path.resolve(
          __dirname,
          "..",
          "..",
          "..",
          "..",
          "customs-autofill",
          "types.ts",
        );
        const src = await fs.readFile(typesPath, "utf-8");
        // Match only TypeScript field declarations like `license_ds_cost:`.
        // Comments mentioning the removal are explicitly allowed.
        const FIELD_RE = /^\s*license_(ds|ss|sgr)_cost\s*[?:]/m;
        expect(src).not.toMatch(FIELD_RE);
      },
    );
  },
);
