/**
 * IDN search filter for the workspace (logistics / customs) kanban board
 * (Testing 2 row 66). Verifies the case-insensitive substring match against
 * both the composite `idn` and the bare `quoteIdn`, plus graceful handling
 * of empty queries.
 */

import { describe, expect, it } from "vitest";

import type { WorkspaceKanbanCard } from "@/entities/workspace-invoice";

import {
  cardPassesFilters,
  emptyWorkspaceFilters,
  hasActiveWorkspaceFilters,
} from "../lib/filter-board";

const NOW = new Date("2026-05-24T12:00:00Z");

function makeCard(overrides: Partial<WorkspaceKanbanCard>): WorkspaceKanbanCard {
  return {
    id: "inv-1",
    quoteId: "q-1",
    invoiceNumber: "inv-1",
    idn: "Q-202604-0018 / inv-1",
    quoteIdn: "Q-202604-0018",
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

describe("workspace: hasActiveWorkspaceFilters with idnSearch", () => {
  it("treats null / empty / whitespace idnSearch as inactive", () => {
    expect(
      hasActiveWorkspaceFilters({
        ...emptyWorkspaceFilters(),
        idnSearch: null,
      })
    ).toBe(false);
    expect(
      hasActiveWorkspaceFilters({
        ...emptyWorkspaceFilters(),
        idnSearch: "",
      })
    ).toBe(false);
    expect(
      hasActiveWorkspaceFilters({
        ...emptyWorkspaceFilters(),
        idnSearch: "   ",
      })
    ).toBe(false);
  });

  it("reports active when idnSearch has non-empty content", () => {
    expect(
      hasActiveWorkspaceFilters({
        ...emptyWorkspaceFilters(),
        idnSearch: "Q-2026",
      })
    ).toBe(true);
  });
});

describe("workspace: cardPassesFilters — idnSearch", () => {
  it("matches against the composite display IDN", () => {
    const filters = { ...emptyWorkspaceFilters(), idnSearch: "inv-1" };
    expect(
      cardPassesFilters(
        makeCard({
          idn: "Q-202604-0018 / inv-1",
          quoteIdn: "Q-202604-0018",
        }),
        filters,
        NOW
      )
    ).toBe(true);
  });

  it("matches against the bare quoteIdn", () => {
    const filters = { ...emptyWorkspaceFilters(), idnSearch: "Q-202604-0018" };
    expect(
      cardPassesFilters(
        makeCard({
          idn: "Q-202604-0018 / inv-7",
          quoteIdn: "Q-202604-0018",
        }),
        filters,
        NOW
      )
    ).toBe(true);
  });

  it("is case-insensitive", () => {
    const filters = { ...emptyWorkspaceFilters(), idnSearch: "q-202604" };
    expect(
      cardPassesFilters(
        makeCard({
          idn: "Q-202604-0018 / inv-1",
          quoteIdn: "Q-202604-0018",
        }),
        filters,
        NOW
      )
    ).toBe(true);
  });

  it("rejects cards whose IDN does not contain the substring", () => {
    const filters = { ...emptyWorkspaceFilters(), idnSearch: "Q-999" };
    expect(
      cardPassesFilters(
        makeCard({
          idn: "Q-202604-0018 / inv-1",
          quoteIdn: "Q-202604-0018",
        }),
        filters,
        NOW
      )
    ).toBe(false);
  });

  it("is a no-op when idnSearch is whitespace-only", () => {
    const filters = { ...emptyWorkspaceFilters(), idnSearch: "   " };
    expect(
      cardPassesFilters(
        makeCard({
          idn: "Q-202604-0018 / inv-1",
          quoteIdn: "Q-202604-0018",
        }),
        filters,
        NOW
      )
    ).toBe(true);
  });

  it("AND-combines with other slots — customer & idn", () => {
    const filters = {
      ...emptyWorkspaceFilters(),
      customerIds: ["cust-2"] as readonly string[],
      idnSearch: "Q-202604",
    };
    // customer mismatch, idn matches — fails
    expect(
      cardPassesFilters(
        makeCard({ customerId: "cust-1", quoteIdn: "Q-202604-0018" }),
        filters,
        NOW
      )
    ).toBe(false);
    // customer matches, idn mismatches — fails. Override BOTH idn fields so
    // the substring search hits neither.
    expect(
      cardPassesFilters(
        makeCard({
          customerId: "cust-2",
          idn: "Q-999999-0001 / inv-1",
          quoteIdn: "Q-999999-0001",
        }),
        filters,
        NOW
      )
    ).toBe(false);
    // both match — passes
    expect(
      cardPassesFilters(
        makeCard({
          customerId: "cust-2",
          idn: "Q-202604-0018 / inv-1",
          quoteIdn: "Q-202604-0018",
        }),
        filters,
        NOW
      )
    ).toBe(true);
  });
});
