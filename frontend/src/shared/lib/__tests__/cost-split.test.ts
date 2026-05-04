/**
 * Tests for `frontend/src/shared/lib/cost-split.ts` — REQ-3 (Phase B
 * customs-shared-certificates).
 *
 * 6 fixture-driven scenarios from `tests/fixtures/cost_split_fixtures.json`
 * exercise the proportional split, equal-split fallback, residual rule, and
 * multi-currency RUB-basis derivation. Additional unit tests cover edge
 * cases not in the fixtures (empty list, single item, all zeros).
 *
 * The same JSON fixture is consumed by the Python sister implementation in
 * `tests/services/test_cost_split.py` to guarantee kopek-identical output
 * between Python and TS (REQ-3 AC#11/AC#12).
 *
 * Numbers in the fixture are encoded as Decimal-safe strings — convert to
 * `number` via `parseFloat` and compare via `result.toFixed(2)` against the
 * fixture string for kopek-exactness.
 */
import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";
import { roundHalfUp2, splitCost, splitCostBatch } from "../cost-split";

// ---------------------------------------------------------------------------
// Fixture loader — relative path to the project-root fixture so both Python
// and TS read the same file. The TS test lives 5 levels deep:
//   frontend/src/shared/lib/__tests__/cost-split.test.ts
// → ../../../../../tests/fixtures/cost_split_fixtures.json
// ---------------------------------------------------------------------------

interface FixtureItem {
  purchase_price_original: string;
  purchase_currency: string;
  quantity: string;
  currency_rate_to_rub: string;
}

interface Fixture {
  name: string;
  items: FixtureItem[];
  item_values: string[];
  cert_cost: string;
  expected_shares: string[];
  notes: string;
}

const FIXTURE_PATH = path.resolve(
  __dirname,
  "../../../../../tests/fixtures/cost_split_fixtures.json",
);

const FIXTURES: Fixture[] = JSON.parse(
  fs.readFileSync(FIXTURE_PATH, "utf-8"),
) as Fixture[];

// Compare a numeric result to a fixture string by 2-decimal-place stringification.
function assertKopekEqual(actual: number, expected: string, label: string) {
  expect(actual.toFixed(2), label).toBe(expected);
}

// ---------------------------------------------------------------------------
// Fixture-driven tests (REQ-3 AC#10) — 6 scenarios, kopek-equality with Python.
// ---------------------------------------------------------------------------

describe("splitCostBatch — JSON fixture parity vs Python", () => {
  for (const fixture of FIXTURES) {
    it(fixture.name, () => {
      // 1) Derive RUB basis from raw upstream fields (parity formula).
      const derived = fixture.items.map(
        (it) =>
          parseFloat(it.purchase_price_original) *
          parseFloat(it.quantity) *
          parseFloat(it.currency_rate_to_rub),
      );

      // 2) Sanity-check: derived basis matches the pre-computed item_values
      //    in the fixture (so the JSON file is self-consistent — Python side
      //    derives identically).
      const declared = fixture.item_values.map((s) => parseFloat(s));
      expect(derived.length).toBe(declared.length);
      for (let i = 0; i < derived.length; i += 1) {
        expect(
          derived[i].toFixed(2),
          `derived[${i}] in '${fixture.name}'`,
        ).toBe(declared[i].toFixed(2));
      }

      // 3) Run the batch split.
      const certCost = parseFloat(fixture.cert_cost);
      const actual = splitCostBatch(derived, certCost);
      const expected = fixture.expected_shares;

      // 4) Length and per-share kopek-equality.
      expect(actual.length).toBe(expected.length);
      for (let i = 0; i < actual.length; i += 1) {
        assertKopekEqual(
          actual[i],
          expected[i],
          `share[${i}] in '${fixture.name}'`,
        );
      }

      // 5) Sum invariant (REQ-3 AC#7) — shares sum to certCost (kopek-exact
      //    on string compare; raw sum may carry sub-cent floating drift).
      let sum = 0;
      for (const s of actual) {
        sum += s;
      }
      expect(sum.toFixed(2)).toBe(certCost.toFixed(2));
    });
  }
});

// ---------------------------------------------------------------------------
// Direct unit tests for splitCost (single-share).
// ---------------------------------------------------------------------------

describe("splitCost", () => {
  it("computes proportional share rounded to kopeks", () => {
    // 100/400 * 12.50 = 3.125 → ROUND_HALF_UP to 0.01 → 3.13
    expect(splitCost(100, 400, 12.5).toFixed(2)).toBe("3.13");
  });

  it("returns 0 when totalItemsValue === 0 (batch-level fallback handles equal split)", () => {
    expect(splitCost(0, 0, 100)).toBe(0);
  });

  it("returns 0 when certCost === 0", () => {
    expect(splitCost(100, 400, 0)).toBe(0);
  });

  it("rounds .5 boundary up (not banker's-round to even)", () => {
    // 1/2 * 0.01 = 0.005 → ROUND_HALF_UP → 0.01
    expect(splitCost(1, 2, 0.01).toFixed(2)).toBe("0.01");
  });
});

// ---------------------------------------------------------------------------
// Direct unit tests for splitCostBatch — edge cases not in fixtures.
// ---------------------------------------------------------------------------

describe("splitCostBatch", () => {
  it("returns [] for an empty array", () => {
    expect(splitCostBatch([], 100)).toEqual([]);
  });

  it("returns [certCost] for a single item — no rounding (REQ-3 AC#6)", () => {
    expect(splitCostBatch([123.456789], 999.99)).toEqual([999.99]);
  });

  it("equal-split fallback when total basis === 0 (no residual)", () => {
    // 100 / 4 = 25.00 exactly — no residual.
    const result = splitCostBatch([0, 0, 0, 0], 100);
    expect(result.map((v) => v.toFixed(2))).toEqual([
      "25.00",
      "25.00",
      "25.00",
      "25.00",
    ]);
    let sum = 0;
    for (const s of result) {
      sum += s;
    }
    expect(sum.toFixed(2)).toBe("100.00");
  });

  it("equal-split fallback also absorbs rounding residual on the last item", () => {
    // 100 / 3 = 33.333… → 33.33 first two, last = 100 - 66.66 = 33.34.
    const result = splitCostBatch([0, 0, 0], 100);
    expect(result.map((v) => v.toFixed(2))).toEqual([
      "33.33",
      "33.33",
      "33.34",
    ]);
    let sum = 0;
    for (const s of result) {
      sum += s;
    }
    expect(sum.toFixed(2)).toBe("100.00");
  });

  it("places the rounding residual on the LAST item, not split (REQ-3 AC#7)", () => {
    const result = splitCostBatch([1, 1, 1], 10);
    expect(result.map((v) => v.toFixed(2))).toEqual([
      "3.33",
      "3.33",
      "3.34",
    ]);
    // Specifically the last item is .34, not .33.
    expect(result[result.length - 1].toFixed(2)).toBe("3.34");
  });

  it("handles 50/50 split with zero residual", () => {
    const result = splitCostBatch([100, 100], 12500);
    expect(result.map((v) => v.toFixed(2))).toEqual(["6250.00", "6250.00"]);
  });

  it("preserves sum invariant for awkward proportional ratios", () => {
    const cases: ReadonlyArray<[number[], number]> = [
      [[7, 11, 13], 100],
      [[17, 19, 23], 999.99],
      [[1, 3, 9, 27], 1234.56],
    ];
    for (const [itemValues, certCost] of cases) {
      const shares = splitCostBatch(itemValues, certCost);
      let sum = 0;
      for (const s of shares) {
        sum += s;
      }
      expect(
        sum.toFixed(2),
        `sum invariant: items=${JSON.stringify(itemValues)} cert=${certCost}`,
      ).toBe(certCost.toFixed(2));
    }
  });
});

// ---------------------------------------------------------------------------
// roundHalfUp2 — explicit shim sanity (parity guard against Math.round drift).
// ---------------------------------------------------------------------------

describe("roundHalfUp2", () => {
  it("rounds .005 up to .01 (not banker's-round to .00)", () => {
    expect(roundHalfUp2(0.005)).toBe(0.01);
  });

  it("rounds .015 up to .02", () => {
    expect(roundHalfUp2(0.015)).toBe(0.02);
  });

  it("rounds .025 up to .03", () => {
    expect(roundHalfUp2(0.025)).toBe(0.03);
  });

  it("leaves already-aligned values unchanged", () => {
    expect(roundHalfUp2(12.34)).toBe(12.34);
    expect(roundHalfUp2(0)).toBe(0);
  });

  it("rounds-down values strictly below the .5 boundary", () => {
    expect(roundHalfUp2(0.004)).toBe(0);
    expect(roundHalfUp2(12.344)).toBe(12.34);
  });
});
