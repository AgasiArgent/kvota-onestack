/**
 * Filter logic for the workspace (logistics / customs) kanban board
 * (Testing 2 rows 64-65). Verifies:
 *  - Empty filter set lets every card through.
 *  - Multi-value filters AND across slots, OR within a slot.
 *  - Stage-entered date range respects inclusive day boundaries.
 *  - Cards missing the filtered field are excluded (no «match by absence»).
 */

import { describe, expect, it } from "vitest";

import type {
  WorkspaceKanbanBoard,
  WorkspaceKanbanCard,
} from "@/entities/workspace-invoice";

import {
  cardPassesFilters,
  emptyWorkspaceFilters,
  filterWorkspaceBoard,
  hasActiveWorkspaceFilters,
  totalCardCount,
  type WorkspaceFilterState,
} from "../lib/filter-board";

const NOW = new Date("2026-05-24T12:00:00Z");

function makeCard(overrides: Partial<WorkspaceKanbanCard>): WorkspaceKanbanCard {
  return {
    id: "inv-1",
    quoteId: "q-1",
    invoiceNumber: "inv-1",
    idn: "Q-202604-0001 / inv-1",
    quoteIdn: "Q-202604-0001",
    customerName: "Coca-Cola",
    customerId: "cust-1",
    pickupLocation: { country: "Italy", type: "supplier" },
    deliveryLocation: { country: "Russia", type: "client" },
    stageEnteredAt: "2026-05-20T09:00:00Z",
    assignedAt: "2026-05-21T09:00:00Z",
    deadlineAt: "2026-05-26T09:00:00Z",
    completedAt: null,
    assignedUserId: "user-1",
    assignedUser: undefined,
    itemCount: 5,
    dealSumTotal: 1000,
    dealSumCurrency: "USD",
    totalWeightKg: 100,
    totalVolumeM3: 1.5,
    packageCount: 2,
    cargoPlaces: [],
    ...overrides,
  };
}

describe("hasActiveWorkspaceFilters", () => {
  it("reports false on an empty filter set", () => {
    expect(hasActiveWorkspaceFilters(emptyWorkspaceFilters())).toBe(false);
  });

  it("reports true when any slot is populated", () => {
    expect(
      hasActiveWorkspaceFilters({
        ...emptyWorkspaceFilters(),
        customerIds: ["cust-1"],
      })
    ).toBe(true);
    expect(
      hasActiveWorkspaceFilters({
        ...emptyWorkspaceFilters(),
        urgency: "overdue",
      })
    ).toBe(true);
    expect(
      hasActiveWorkspaceFilters({
        ...emptyWorkspaceFilters(),
        stageFrom: "2026-05-20",
      })
    ).toBe(true);
  });
});

describe("cardPassesFilters", () => {
  it("lets every card through when no filters are active", () => {
    const card = makeCard({});
    expect(cardPassesFilters(card, emptyWorkspaceFilters(), NOW)).toBe(true);
  });

  it("customer: matches when card customerId is in the selected list", () => {
    const filters: WorkspaceFilterState = {
      ...emptyWorkspaceFilters(),
      customerIds: ["cust-1", "cust-2"],
    };
    expect(cardPassesFilters(makeCard({ customerId: "cust-1" }), filters, NOW)).toBe(
      true
    );
    expect(cardPassesFilters(makeCard({ customerId: "cust-3" }), filters, NOW)).toBe(
      false
    );
    expect(cardPassesFilters(makeCard({ customerId: null }), filters, NOW)).toBe(
      false
    );
  });

  it("assignee: only matches cards with a matching assignedUserId", () => {
    const filters: WorkspaceFilterState = {
      ...emptyWorkspaceFilters(),
      assigneeIds: ["user-1"],
    };
    expect(cardPassesFilters(makeCard({ assignedUserId: "user-1" }), filters, NOW)).toBe(
      true
    );
    expect(cardPassesFilters(makeCard({ assignedUserId: "user-2" }), filters, NOW)).toBe(
      false
    );
    expect(cardPassesFilters(makeCard({ assignedUserId: null }), filters, NOW)).toBe(
      false
    );
  });

  it("stage date range: inclusive day boundaries (UTC)", () => {
    const filters: WorkspaceFilterState = {
      ...emptyWorkspaceFilters(),
      stageFrom: "2026-05-20",
      stageTo: "2026-05-22",
    };
    // 2026-05-19 23:59 — below the lower bound (May 20 00:00:00)
    expect(
      cardPassesFilters(
        makeCard({ stageEnteredAt: "2026-05-19T23:00:00Z" }),
        filters,
        NOW
      )
    ).toBe(false);
    // 2026-05-22 23:59 — within the upper-bound end-of-day
    expect(
      cardPassesFilters(
        makeCard({ stageEnteredAt: "2026-05-22T23:00:00Z" }),
        filters,
        NOW
      )
    ).toBe(true);
    // 2026-05-23 — after the upper bound (when treated as end-of-day on 22nd)
    expect(
      cardPassesFilters(
        makeCard({ stageEnteredAt: "2026-05-23T00:00:00Z" }),
        filters,
        NOW
      )
    ).toBe(false);
  });

  it("urgency: overdue selects cards with past deadlines", () => {
    const filters: WorkspaceFilterState = {
      ...emptyWorkspaceFilters(),
      urgency: "overdue",
    };
    expect(
      cardPassesFilters(
        makeCard({ deadlineAt: "2026-05-23T00:00:00Z" }),
        filters,
        NOW
      )
    ).toBe(true);
    expect(
      cardPassesFilters(
        makeCard({ deadlineAt: "2026-05-25T00:00:00Z" }),
        filters,
        NOW
      )
    ).toBe(false);
    expect(
      cardPassesFilters(makeCard({ deadlineAt: null }), filters, NOW)
    ).toBe(false);
  });

  it("combines filters with AND across slots", () => {
    const filters: WorkspaceFilterState = {
      customerIds: ["cust-1"],
      assigneeIds: ["user-1"],
      stageFrom: null,
      stageTo: null,
      urgency: null,
    };
    // Both slots match
    expect(
      cardPassesFilters(
        makeCard({ customerId: "cust-1", assignedUserId: "user-1" }),
        filters,
        NOW
      )
    ).toBe(true);
    // Customer matches but assignee does not
    expect(
      cardPassesFilters(
        makeCard({ customerId: "cust-1", assignedUserId: "user-2" }),
        filters,
        NOW
      )
    ).toBe(false);
  });
});

describe("filterWorkspaceBoard", () => {
  const board: WorkspaceKanbanBoard = {
    unassigned: [
      makeCard({ id: "a", customerId: "cust-1", assignedUserId: null }),
      makeCard({ id: "b", customerId: "cust-2", assignedUserId: null }),
    ],
    in_progress: [
      makeCard({ id: "c", customerId: "cust-1", assignedUserId: "user-1" }),
      makeCard({ id: "d", customerId: "cust-2", assignedUserId: "user-2" }),
    ],
    completed: [
      makeCard({
        id: "e",
        customerId: "cust-1",
        assignedUserId: "user-1",
        completedAt: "2026-05-01",
      }),
    ],
  };

  it("returns the full board when no filters are active", () => {
    const result = filterWorkspaceBoard(board, emptyWorkspaceFilters());
    expect(totalCardCount(result)).toBe(5);
  });

  it("filters every column when a slot is active", () => {
    const result = filterWorkspaceBoard(board, {
      ...emptyWorkspaceFilters(),
      customerIds: ["cust-1"],
    });
    expect(result.unassigned.map((c) => c.id)).toEqual(["a"]);
    expect(result.in_progress.map((c) => c.id)).toEqual(["c"]);
    expect(result.completed.map((c) => c.id)).toEqual(["e"]);
  });

  it("returns empty columns when nothing matches — caller renders empty state", () => {
    const result = filterWorkspaceBoard(board, {
      ...emptyWorkspaceFilters(),
      customerIds: ["cust-999"],
    });
    expect(totalCardCount(result)).toBe(0);
  });
});
