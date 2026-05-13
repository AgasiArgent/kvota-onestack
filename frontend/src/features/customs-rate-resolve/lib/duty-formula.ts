/**
 * Live preview helper for the Manual duty-rate UI (Phase A Req 4, Task 10).
 *
 * Pure functions — no DOM dependencies. Consumed by the Manual-mode block
 * inside `customs-item-dialog.tsx` and unit-tested in `duty-formula.test.ts`.
 *
 * The output is a single-line monospace string suitable for display below
 * the input slots, e.g.:
 *
 *   duty = max(150 000 × 10%, 95.5 × 0.04 × 95.5) = max(15 000, 365) = 15 000 ₽
 *
 * Numbers use ru-RU locale formatting (NBSP thousands, comma decimals)
 * to match the rest of the customs UI. When required inputs are missing
 * (customs_value or value_1), the helper returns "—" — caller renders
 * a placeholder instead of a partial formula.
 */

export type DutyRateType = "simple" | "combined" | "specific";
export type DutySign = ">" | "+" | null;

/** Units available in the Manual UI selector. */
export type DutyUnit =
  | "percent"
  | "EUR/kg"
  | "USD/kg"
  | "USD/pc"
  | "RUB/l"
  | "EUR/l"
  | "USD/l";

export interface DutyFormulaArgs {
  rate_type: DutyRateType;
  /** First slot — required for any preview. */
  value_1: number | null;
  unit_1: DutyUnit | string;
  /** Second slot — only used when rate_type === "combined". */
  value_2?: number | null;
  unit_2?: DutyUnit | string | null;
  /** Combiner for combined-rate; ignored for simple/specific. */
  sign?: DutySign;
  /** Customs value in RUB — used for ad-valorem (% of customs_value). */
  customs_value: number | null;
  /** Net weight in kg — used for per-kg / per-l specific rates. */
  weight_kg: number | null;
  /** Quantity (pcs) — used for per-pc specific rates. */
  quantity?: number | null;
  /** EUR→RUB / USD→RUB conversion rate matching the slot's currency. */
  currency_rate?: number | null;
}

/** Returns the contribution of the percent (ad-valorem) part. */
function adValoremPart(customs_value: number, percent: number): number {
  return (customs_value * percent) / 100;
}

/** Returns the contribution of a per-unit (specific) part. */
function specificPart(
  weight_kg: number | null,
  quantity: number | null,
  value: number,
  unit: string,
  currency_rate: number | null,
): number {
  // Per-kg rates (EUR/USD per kg).
  if (unit === "EUR/kg" || unit === "USD/kg") {
    const w = weight_kg ?? 0;
    const c = currency_rate ?? 0;
    return w * value * c;
  }
  // Per-pc rates (USD/pc most common).
  if (unit === "USD/pc" || unit === "EUR/pc") {
    const q = quantity ?? 0;
    const c = currency_rate ?? 0;
    return q * value * c;
  }
  // Per-litre rates — mass proxy until a `volume_l` field is propagated.
  if (unit === "RUB/l" || unit === "EUR/l" || unit === "USD/l") {
    const w = weight_kg ?? 0;
    const c = unit === "RUB/l" ? 1 : currency_rate ?? 0;
    return w * value * c;
  }
  return value;
}

/** Format a number with ru-RU thousand separators (NBSP) and 2 decimals max. */
export function formatRub(n: number): string {
  return n.toLocaleString("ru-RU", { maximumFractionDigits: 2 });
}

/**
 * Compose a single-line monospace duty preview.
 *
 * Returns "—" when required inputs are missing.
 */
export function formatDutyFormula(args: DutyFormulaArgs): string {
  const {
    rate_type,
    value_1,
    unit_1,
    value_2,
    unit_2,
    sign,
    customs_value,
    weight_kg,
    quantity,
    currency_rate,
  } = args;

  if (value_1 == null || customs_value == null) {
    return "—";
  }

  const fmt = formatRub;

  // Combined needs both slots filled and a sign — otherwise fall back to
  // single-slot rendering so customs sees something useful while typing.
  const isCombinedComplete =
    rate_type === "combined" &&
    value_2 != null &&
    unit_2 != null &&
    sign != null;

  if (rate_type === "simple" || rate_type === "specific" || !isCombinedComplete) {
    if (unit_1 === "percent") {
      const amount = adValoremPart(customs_value, value_1);
      return `duty = ${fmt(customs_value)} × ${value_1}% = ${fmt(amount)} ₽`;
    }
    const amount = specificPart(
      weight_kg,
      quantity ?? null,
      value_1,
      unit_1,
      currency_rate ?? null,
    );
    return `duty = ${value_1} ${unit_1} = ${fmt(amount)} ₽`;
  }

  // Combined branch — both slots present.
  const part1 =
    unit_1 === "percent"
      ? adValoremPart(customs_value, value_1)
      : specificPart(
          weight_kg,
          quantity ?? null,
          value_1,
          unit_1,
          currency_rate ?? null,
        );
  const part2 =
    unit_2 === "percent"
      ? adValoremPart(customs_value, value_2 as number)
      : specificPart(
          weight_kg,
          quantity ?? null,
          value_2 as number,
          unit_2 as string,
          currency_rate ?? null,
        );

  const result = sign === ">" ? Math.max(part1, part2) : part1 + part2;
  const op = sign === ">" ? "max" : "sum";

  return `duty = ${op}(${fmt(part1)}, ${fmt(part2)}) = ${fmt(result)} ₽`;
}

/**
 * Short single-line chip representation for the Handsontable «Пошлина»
 * column when Manual mode is active.
 *
 * Examples:
 *   simple percent       → "10%"
 *   specific perKg       → "0.5 EUR/kg"
 *   combined "но не менее"→ "10% > 0.5 EUR/kg"
 *   combined "плюс"      → "10% + 0.5 EUR/kg"
 *
 * Returns "—" when value_1 is missing. Unlike formatDutyFormula this
 * helper does NOT require customs_value / weight_kg — it just echoes
 * the raw user input, suitable for a narrow cell that confirms
 * "value was saved" without doing the RUB math.
 */
export function formatDutyChip(args: {
  rate_type: DutyRateType;
  value_1: number | null;
  unit_1: DutyUnit | string;
  value_2?: number | null;
  unit_2?: DutyUnit | string | null;
  sign?: DutySign;
}): string {
  const { rate_type, value_1, unit_1, value_2, unit_2, sign } = args;
  if (value_1 == null) return "—";

  const slot1 =
    unit_1 === "percent" ? `${value_1}%` : `${value_1} ${unit_1}`;

  if (rate_type !== "combined" || value_2 == null || unit_2 == null) {
    return slot1;
  }

  const slot2 =
    unit_2 === "percent" ? `${value_2}%` : `${value_2} ${unit_2}`;
  const op = sign === "+" ? "+" : ">";
  return `${slot1} ${op} ${slot2}`;
}
