import { describe, it, expect } from "vitest";
import {
  deriveKanbanColumn,
  isCardVisibleToUser,
  type WorkspaceKanbanColumnKey,
} from "../model/types";

/**
 * Column predicate derivation (REQ-2) and «В работе» visibility (REQ-5/6).
 * These are the pure rules behind `fetchKanbanInvoices` — the network query
 * itself is verified on localhost per reference_localhost_browser_test.md.
 */
describe("deriveKanbanColumn — column predicates (REQ-2)", () => {
  it("returns «completed» when the domain completion timestamp is set", () => {
    expect(
      deriveKanbanColumn({
        completedAt: "2026-05-10T12:00:00Z",
        assignedUserId: "u1",
      }),
    ).toBe("completed");
  });

  it("«completed» wins even when there is no assignee", () => {
    // A completed invoice with a cleared assignee still belongs in «Завершено».
    expect(
      deriveKanbanColumn({
        completedAt: "2026-05-10T12:00:00Z",
        assignedUserId: null,
      }),
    ).toBe("completed");
  });

  it("returns «in_progress» when assigned and not completed", () => {
    expect(
      deriveKanbanColumn({ completedAt: null, assignedUserId: "u1" }),
    ).toBe("in_progress");
  });

  it("returns «unassigned» when no assignee and not completed", () => {
    expect(
      deriveKanbanColumn({ completedAt: null, assignedUserId: null }),
    ).toBe("unassigned");
  });
});

describe("isCardVisibleToUser — «В работе» visibility (REQ-5/6)", () => {
  const SELF = "user-self";
  const OTHER = "user-other";

  it("a member sees their own «В работе» card", () => {
    expect(isCardVisibleToUser("in_progress", SELF, SELF, false)).toBe(true);
  });

  it("a member does NOT see another member's «В работе» card", () => {
    expect(isCardVisibleToUser("in_progress", OTHER, SELF, false)).toBe(false);
  });

  it("a head sees every «В работе» card regardless of assignee", () => {
    expect(isCardVisibleToUser("in_progress", OTHER, SELF, true)).toBe(true);
  });

  it("«Нераспределено» is visible to every domain user (member)", () => {
    expect(isCardVisibleToUser("unassigned", null, SELF, false)).toBe(true);
  });

  it("«Завершено» is visible to every domain user (member)", () => {
    // Even a card completed by another member shows in «Завершено».
    expect(isCardVisibleToUser("completed", OTHER, SELF, false)).toBe(true);
  });

  it("visibility only ever restricts the «В работе» column", () => {
    const nonRestricted: WorkspaceKanbanColumnKey[] = [
      "unassigned",
      "completed",
    ];
    for (const col of nonRestricted) {
      expect(isCardVisibleToUser(col, OTHER, SELF, false)).toBe(true);
    }
  });
});
