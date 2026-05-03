import { describe, it, expect } from "vitest";

import { columnsDefaultVisible } from "@/shared/lib/data-table";
import type { DataTableColumn } from "@/shared/ui/data-table/types";

/**
 * Regression tests for Q3/RQ3 — when the user clears the active saved view
 * (selects "Все" preset), the table must restore the full default column set
 * rather than carry over the previously-active view's subset.
 *
 * `columnsDefaultVisible` is the shared helper feeding both the initial state
 * and the "Все" preset reset path in `data-table.tsx::handleClearView`.
 */

function col(
  key: string,
  overrides: Partial<DataTableColumn<unknown>> = {}
): DataTableColumn<unknown> {
  return {
    key,
    label: key,
    accessor: () => null,
    ...overrides,
  };
}

describe("columnsDefaultVisible", () => {
  it("returns all column keys when none have defaultVisible=false", () => {
    const columns = [col("date"), col("idn"), col("customer"), col("status")];
    expect(columnsDefaultVisible(columns)).toEqual([
      "date",
      "idn",
      "customer",
      "status",
    ]);
  });

  it("excludes columns explicitly marked defaultVisible=false", () => {
    const columns = [
      col("date"),
      col("idn"),
      col("internal_id", { defaultVisible: false }),
      col("customer"),
    ];
    expect(columnsDefaultVisible(columns)).toEqual([
      "date",
      "idn",
      "customer",
    ]);
  });

  it("includes columns with defaultVisible=true and undefined alike (default is true)", () => {
    const columns = [
      col("a"),
      col("b", { defaultVisible: true }),
      col("c", { defaultVisible: false }),
    ];
    expect(columnsDefaultVisible(columns)).toEqual(["a", "b"]);
  });

  it("preserves config order (the source of truth for column ordering)", () => {
    const columns = [col("z"), col("a"), col("m")];
    expect(columnsDefaultVisible(columns)).toEqual(["z", "a", "m"]);
  });

  it("returns a fresh array — caller may mutate without affecting source", () => {
    const columns = [col("a"), col("b")];
    const first = columnsDefaultVisible(columns);
    const second = columnsDefaultVisible(columns);
    expect(first).not.toBe(second);
  });

  it("returns empty array when every column is hidden by default", () => {
    const columns = [
      col("hidden_a", { defaultVisible: false }),
      col("hidden_b", { defaultVisible: false }),
    ];
    expect(columnsDefaultVisible(columns)).toEqual([]);
  });

  it("returns empty array for empty column config", () => {
    expect(columnsDefaultVisible([])).toEqual([]);
  });

  /**
   * Q3/RQ3 scenario: user saves a custom view with a subset of columns, then
   * picks "Все". The reset must produce the full default set — *not* whatever
   * subset the saved view stored. This helper is the single source for that
   * full set, so it must NOT consult any persisted/saved state.
   */
  it("ignores any previously-saved subset — the full set is purely a function of column config", () => {
    const columns = [
      col("date"),
      col("idn"),
      col("customer"),
      col("brand"),
      col("status"),
    ];
    // Even if upstream state stored only ["idn"], the helper must still
    // return every defaultVisible column.
    expect(columnsDefaultVisible(columns)).toEqual([
      "date",
      "idn",
      "customer",
      "brand",
      "status",
    ]);
  });
});
