/**
 * Regression test for Testing 2 row 26 — «Если добавить данные пошлины
 * через модалку, то после появления в таблице значка М — изменение через
 * ячейку таблицы невозможно».
 *
 * Repro:
 *   1. User opens the customs item dialog, picks Комбинированная /
 *      Специфическая mode, saves → row gets `customs_manual_override=true`
 *      and a `customs_manual_rate_payload` snapshot.
 *   2. The handsontable duty cell renders a read-only formula chip with
 *      an «M» badge (manual mode renderer).
 *   3. User double-clicks the cell, types a plain percent value, presses
 *      Enter. The cell repaints the OLD formula chip and the user perceives
 *      «ячейка не редактируется».
 *
 * Root cause: `handleAfterChange` only wrote `customs_duty` /
 * `customs_duty_per_kg`; `customs_manual_override` stayed `true`, so the
 * renderer kept hitting the Manual branch and painted the stale formula
 * from `customs_manual_rate_payload`.
 *
 * Fix: `buildDutyCompositeUpdates` now clears the Manual snapshot whenever
 * the cell is edited on a Manual row.
 */

import { describe, expect, it } from "vitest";

import {
  buildDutyCompositeUpdates,
  parsePastedNumeric,
} from "../customs-handsontable";

describe("parsePastedNumeric — Testing 2 row 72 (decimal precision on paste)", () => {
  // Each case mirrors a real shape МВЭД testers have pasted into «% пошлины»
  // and the surrounding numeric customs columns. Tester re-report:
  // pasting `7.5` was silently truncated to `7` (or rounded to `8` in the
  // calc preview) — the new locale-aware parser keeps the full precision.

  it("preserves a dot decimal (`7.5` → 7.5)", () => {
    // Plain en-US input. parseFloat already handles this — the test guards
    // against future regressions of the cleanup logic stripping the dot.
    expect(parsePastedNumeric("7.5")).toBe(7.5);
  });

  it("preserves a multi-digit dot decimal (`7.123` → 7.123)", () => {
    // DB column is NUMERIC(15,4), so we must preserve at least 4 decimals.
    expect(parsePastedNumeric("7.123")).toBe(7.123);
  });

  it("preserves a comma decimal (`7,5` → 7.5)", () => {
    // ru-RU keyboard / Excel ru-RU export.
    expect(parsePastedNumeric("7,5")).toBe(7.5);
  });

  it("strips a trailing % suffix (`7.5%` → 7.5)", () => {
    // Tester habit — copy «12,5%» from the customs reference column,
    // paste into the editable cell. The % must not block parsing.
    expect(parsePastedNumeric("7.5%")).toBe(7.5);
  });

  it("strips a trailing currency unit (`0,5 ₽/кг` → 0.5)", () => {
    // ₽/кг chip text is sometimes copied along with the value.
    expect(parsePastedNumeric("0,5 ₽/кг")).toBe(0.5);
  });

  it("handles ru-RU thousands grouping with space (`1 234,56` → 1234.56)", () => {
    // Excel ru-RU exports a non-breaking space (U+00A0) between thousands.
    // The naïve `replace(",", ".")` would yield `1 234.56` and parseFloat
    // would stop at the space → 1, dropping the entire fractional part.
    expect(parsePastedNumeric("1 234,56")).toBe(1234.56);
    expect(parsePastedNumeric("1 234,56")).toBe(1234.56);
  });

  it("handles de-DE thousands grouping with dot (`1.234,56` → 1234.56)", () => {
    // Excel de-DE format: comma decimal, dot thousands separator. The old
    // first-comma-only fix produced `1.234.56` → parseFloat stopped at the
    // second dot → 1.234. New parser drops dots and replaces the trailing
    // comma with a dot.
    expect(parsePastedNumeric("1.234,56")).toBe(1234.56);
  });

  it("handles en-US thousands grouping with comma (`1,234.56` → 1234.56)", () => {
    // Excel en-US default. parseFloat already eats this on its own, but the
    // old `replace(",", ".")` corrupted it to `1.234.56` → 1.234.
    expect(parsePastedNumeric("1,234.56")).toBe(1234.56);
  });

  it("handles multi-comma en-US grouping with no decimal (`1,234,567` → 1234567)", () => {
    // No fractional part — every comma is a thousands separator.
    expect(parsePastedNumeric("1,234,567")).toBe(1234567);
  });

  it("passes through a JS number unchanged (`7.5` number → 7.5)", () => {
    // HoT's valueSetter often converts the pasted string to a number
    // before afterChange fires. The parser must not corrupt that path.
    expect(parsePastedNumeric(7.5)).toBe(7.5);
  });

  it("returns null for empty / unparseable input", () => {
    expect(parsePastedNumeric("")).toBeNull();
    expect(parsePastedNumeric("   ")).toBeNull();
    expect(parsePastedNumeric("abc")).toBeNull();
    expect(parsePastedNumeric("—")).toBeNull();
    expect(parsePastedNumeric(null)).toBeNull();
    expect(parsePastedNumeric(undefined)).toBeNull();
  });

  it("handles negative values (`-7,5` → -7.5)", () => {
    expect(parsePastedNumeric("-7,5")).toBe(-7.5);
    expect(parsePastedNumeric("-1.234,56")).toBe(-1234.56);
  });
});

describe("buildDutyCompositeUpdates — Auto-mode rows", () => {
  it("writes customs_duty when current mode is percent (perKg slot is null)", () => {
    const updates = buildDutyCompositeUpdates("12.5", {
      customs_duty_per_kg: null,
      customs_manual_override: false,
    });
    expect(updates.customs_duty).toBe(12.5);
    expect(updates.customs_duty_per_kg).toBeNull();
  });

  it("accepts comma decimal separator from Russian locale paste (Testing 2 row 72)", () => {
    // Testing 2 row 72 — «Десятичные округляются при копировании % пошлины».
    // Repro: МВЭД copies 12,5% (Handsontable copies the displayed value in
    // ru-RU locale → "12,5") and pastes into another cell. `parseFloat("12,5")`
    // stops at the comma and returns 12, dropping the fractional part.
    // Fix normalizes comma → dot before parsing so RU-locale paste and
    // Russian-keyboard typing both round-trip cleanly.
    const updates = buildDutyCompositeUpdates("12,5", {
      customs_duty_per_kg: null,
      customs_manual_override: false,
    });
    expect(updates.customs_duty).toBe(12.5);
  });

  it("accepts comma decimal separator for ₽/кг slot as well", () => {
    const updates = buildDutyCompositeUpdates("0,25", {
      customs_duty_per_kg: 0.5,
      customs_manual_override: false,
    });
    expect(updates.customs_duty_per_kg).toBe(0.25);
    expect(updates.customs_duty).toBeNull();
  });

  it("preserves dot decimals from a plain paste (`7.5`, Testing 2 row 72 re-report)", () => {
    // Tester re-report after PR #215 — `7.5` was still rounding because
    // upstream paste-cleanup logic stripped the dot.
    const updates = buildDutyCompositeUpdates("7.5", {
      customs_duty_per_kg: null,
      customs_manual_override: false,
    });
    expect(updates.customs_duty).toBe(7.5);
  });

  it("preserves 3-decimal precision (`7.123`)", () => {
    // DB is NUMERIC(15,4) — 4 fractional digits must round-trip cleanly.
    const updates = buildDutyCompositeUpdates("7.123", {
      customs_duty_per_kg: null,
      customs_manual_override: false,
    });
    expect(updates.customs_duty).toBe(7.123);
  });

  it("recovers thousands-grouped values (`1.234,56` → 1234.56)", () => {
    // de-DE Excel export. Old parser produced 1.234, dropping the decimals.
    const updates = buildDutyCompositeUpdates("1.234,56", {
      customs_duty_per_kg: null,
      customs_manual_override: false,
    });
    expect(updates.customs_duty).toBe(1234.56);
  });

  it("writes customs_duty_per_kg when current mode is perKg", () => {
    const updates = buildDutyCompositeUpdates("0.5", {
      customs_duty_per_kg: 0.25,
      customs_manual_override: false,
    });
    expect(updates.customs_duty).toBeNull();
    expect(updates.customs_duty_per_kg).toBe(0.5);
  });

  it("treats unparseable input as null", () => {
    const updates = buildDutyCompositeUpdates("", {
      customs_duty_per_kg: null,
      customs_manual_override: false,
    });
    expect(updates.customs_duty).toBeNull();
    expect(updates.customs_duty_per_kg).toBeNull();
  });

  it("does NOT touch Manual override columns for Auto-mode rows", () => {
    const updates = buildDutyCompositeUpdates("10", {
      customs_duty_per_kg: null,
      customs_manual_override: false,
    });
    expect(updates.customs_manual_override).toBeUndefined();
    expect(updates.customs_manual_rate_payload).toBeUndefined();
  });
});

describe("buildDutyCompositeUpdates — Testing 2 row 26 regression", () => {
  it("clears customs_manual_override + payload when editing a Manual-mode row", () => {
    // Tester repro: row was saved via modal in Manual mode (Специфическая /
    // 250 EUR/kg → customs_manual_override=true, payload snapshot saved,
    // customs_duty_per_kg=250). User now types 10 in the cell directly.
    const updates = buildDutyCompositeUpdates("10", {
      customs_duty_per_kg: 250,
      customs_manual_override: true,
    });
    // Manual snapshot must be cleared so the renderer's Manual branch
    // stops firing and the new value takes effect.
    expect(updates.customs_manual_override).toBe(false);
    expect(updates.customs_manual_rate_payload).toBeNull();
  });

  it("re-emits the user-typed value under the existing storage slot", () => {
    // The row stored its prior Manual rate in customs_duty_per_kg, so the
    // inline edit stays in perKg mode — the user only changes the value,
    // not the unit semantics. Mode toggle is a separate code path.
    const updates = buildDutyCompositeUpdates("10", {
      customs_duty_per_kg: 250,
      customs_manual_override: true,
    });
    expect(updates.customs_duty).toBeNull();
    expect(updates.customs_duty_per_kg).toBe(10);
  });

  it("clears Manual snapshot even when the user types into a pct-mode Manual row", () => {
    // Edge case: row was saved Manually with a "simple percent" payload
    // (customs_duty=5, customs_duty_per_kg=null, manual_override=true).
    // Inline edit must still clear the override so direct editing works.
    const updates = buildDutyCompositeUpdates("8", {
      customs_duty_per_kg: null,
      customs_manual_override: true,
    });
    expect(updates.customs_duty).toBe(8);
    expect(updates.customs_duty_per_kg).toBeNull();
    expect(updates.customs_manual_override).toBe(false);
    expect(updates.customs_manual_rate_payload).toBeNull();
  });

  it("clears Manual snapshot when the user blanks the cell", () => {
    // Empty input → null value, but still must clear the snapshot, otherwise
    // the renderer paints the formula chip again and the cell still looks
    // un-editable.
    const updates = buildDutyCompositeUpdates("", {
      customs_duty_per_kg: 250,
      customs_manual_override: true,
    });
    expect(updates.customs_duty_per_kg).toBeNull();
    expect(updates.customs_manual_override).toBe(false);
    expect(updates.customs_manual_rate_payload).toBeNull();
  });
});
