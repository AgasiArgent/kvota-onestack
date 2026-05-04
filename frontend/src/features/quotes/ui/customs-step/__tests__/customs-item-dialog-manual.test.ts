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
  license_ds_cost: "",
  license_ss_required: false,
  license_ss_cost: "",
  license_sgr_required: false,
  license_sgr_cost: "",
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
