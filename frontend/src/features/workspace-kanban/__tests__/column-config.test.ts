import { describe, it, expect } from "vitest";
import {
  DEFAULT_KANBAN_COLUMNS,
  KANBAN_COLUMNS,
  KANBAN_COLUMN_LABELS,
} from "../model/types";

/**
 * Regression guard for control-spec-workspace task 4.1 — parameterizing the
 * kanban board's columns into a `columns` prop MUST NOT change the
 * logistics/customs layout. The dnd `KanbanBoard` falls back to
 * `DEFAULT_KANBAN_COLUMNS` when no prop is passed (which is exactly how the
 * logistics + customs pages render today), so this asserts that default is
 * still the same three columns in the same order with the same Russian labels.
 */
describe("DEFAULT_KANBAN_COLUMNS — logistics/customs layout unchanged (task 4.1)", () => {
  it("is exactly the three columns in fixed order with their labels", () => {
    expect(DEFAULT_KANBAN_COLUMNS).toEqual([
      { key: "unassigned", label: "Нераспределено" },
      { key: "in_progress", label: "В работе" },
      { key: "completed", label: "Завершено" },
    ]);
  });

  it("stays derived from the single-source-of-truth constants", () => {
    expect(DEFAULT_KANBAN_COLUMNS.map((c) => c.key)).toEqual([
      ...KANBAN_COLUMNS,
    ]);
    for (const col of DEFAULT_KANBAN_COLUMNS) {
      expect(col.label).toBe(KANBAN_COLUMN_LABELS[col.key]);
    }
  });
});
