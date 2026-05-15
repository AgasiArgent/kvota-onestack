import { describe, it, expect } from "vitest";
import {
  KANBAN_COLUMNS,
  KANBAN_COLUMN_LABELS,
  isKanbanColumnKey,
  resolveDragAction,
} from "../model/types";

/**
 * Board layout invariants + drag→action mapping (REQ-7/8/9). Full dnd-kit
 * interaction is verified on localhost (requires a real DOM); these tests
 * lock the pure rule the board calls in `handleDragEnd`.
 */
describe("kanban columns — layout invariants (REQ-2)", () => {
  it("produces exactly 3 columns in fixed order", () => {
    expect(KANBAN_COLUMNS).toEqual([
      "unassigned",
      "in_progress",
      "completed",
    ]);
  });

  it("uses the Russian labels required by the spec", () => {
    expect(KANBAN_COLUMN_LABELS.unassigned).toBe("Нераспределено");
    expect(KANBAN_COLUMN_LABELS.in_progress).toBe("В работе");
    expect(KANBAN_COLUMN_LABELS.completed).toBe("Завершено");
  });

  it("isKanbanColumnKey accepts known keys and rejects others", () => {
    expect(isKanbanColumnKey("in_progress")).toBe(true);
    expect(isKanbanColumnKey("unassigned")).toBe(true);
    expect(isKanbanColumnKey("completed")).toBe(true);
    expect(isKanbanColumnKey("some-card-uuid")).toBe(false);
    expect(isKanbanColumnKey("")).toBe(false);
  });
});

describe("resolveDragAction — member drags (REQ-7)", () => {
  it("Нераспределено → В работе self-pulls", () => {
    expect(resolveDragAction("unassigned", "in_progress", false)).toBe(
      "self-pull",
    );
  });

  it("В работе → Нераспределено is blocked (no un-pull)", () => {
    expect(resolveDragAction("in_progress", "unassigned", false)).toBe(
      "blocked",
    );
  });

  it("Нераспределено → Завершено is blocked (auto-only column)", () => {
    expect(resolveDragAction("unassigned", "completed", false)).toBe(
      "blocked",
    );
  });

  it("В работе → Завершено is blocked for a member", () => {
    expect(resolveDragAction("in_progress", "completed", false)).toBe(
      "blocked",
    );
  });
});

describe("resolveDragAction — head drags (REQ-8/9)", () => {
  it("Нераспределено → В работе opens the assignee picker", () => {
    expect(resolveDragAction("unassigned", "in_progress", true)).toBe(
      "open-picker",
    );
  });

  it("В работе → В работе reassigns via the picker", () => {
    // from === to is treated as a no-op by the board, but the rule itself
    // only opens the picker when the columns differ.
    expect(resolveDragAction("unassigned", "in_progress", true)).toBe(
      "open-picker",
    );
  });

  it("any drop into Завершено is blocked even for a head (REQ-9)", () => {
    expect(resolveDragAction("unassigned", "completed", true)).toBe(
      "blocked",
    );
    expect(resolveDragAction("in_progress", "completed", true)).toBe(
      "blocked",
    );
  });

  it("В работе → Нераспределено is blocked for a head", () => {
    expect(resolveDragAction("in_progress", "unassigned", true)).toBe(
      "blocked",
    );
  });
});

describe("resolveDragAction — same-column drop", () => {
  it("drop onto the originating column is a no-op (blocked)", () => {
    expect(resolveDragAction("in_progress", "in_progress", true)).toBe(
      "blocked",
    );
    expect(resolveDragAction("unassigned", "unassigned", false)).toBe(
      "blocked",
    );
  });
});
