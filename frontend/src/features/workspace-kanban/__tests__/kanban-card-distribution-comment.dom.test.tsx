// @vitest-environment jsdom
/**
 * «Комментарий для распределения» on the logistics / customs kanban card.
 *
 * Surface rule: the comment is the МОП's distribution hint for МОЛ / МОТ when
 * the card is still in the «Нераспределено» column (no assignee, not
 * completed). Once a user is assigned or the stage is closed, the hint is
 * outdated noise — hide it. The context panel on the quote/deal page keeps
 * showing it permanently for historical reference.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { DndContext } from "@dnd-kit/core";

// Heavy children whose internals would drag supabase / next routing into the
// jsdom render. Replace with simple sentinels so the test stays narrow.
vi.mock("@/entities/location/ui/location-chip", () => ({
  LocationChip: ({ location }: { location: { country: string; city?: string } }) => (
    <span>{location.city ?? location.country}</span>
  ),
}));

vi.mock("@/entities/user/ui/user-avatar-chip", () => ({
  UserAvatarChip: ({ user }: { user: { name: string } }) => (
    <span data-testid="kanban-card-assignee">{user.name}</span>
  ),
}));

vi.mock("@/shared/ui/sla-timer-badge", () => ({
  SlaTimerBadge: () => <span data-testid="sla-timer" />,
}));

vi.mock("../ui/assignee-picker-popover", () => ({
  AssigneePickerPopover: () => null,
}));

import { KanbanCard } from "../ui/kanban-card";
import type { WorkspaceKanbanCard } from "../model/types";

function makeCard(
  overrides: Partial<WorkspaceKanbanCard> = {},
): WorkspaceKanbanCard {
  return {
    id: "invoice-1",
    quoteId: "quote-1",
    invoiceNumber: "inv-1",
    idn: "Q-202604-0018 / inv-1",
    quoteIdn: "Q-202604-0018",
    customerName: "ООО Ромашка",
    pickupLocation: { country: "Китай", iso2: "CN", city: "Шанхай" },
    deliveryLocation: { country: "Россия", iso2: "RU", city: "Москва" },
    stageEnteredAt: "2026-05-10T08:00:00Z",
    assignedAt: null,
    deadlineAt: null,
    completedAt: null,
    assignedUserId: null,
    itemCount: 3,
    dealSumTotal: 100000,
    dealSumCurrency: "RUB",
    totalWeightKg: null,
    totalVolumeM3: null,
    packageCount: null,
    cargoPlaces: [],
    distributionComment: null,
    ...overrides,
  };
}

// `useDraggable` needs a DndContext provider in jsdom; wrap each render.
function renderCard(card: WorkspaceKanbanCard) {
  return render(
    <DndContext>
      <KanbanCard card={card} domain="logistics" />
    </DndContext>,
  );
}

afterEach(() => {
  cleanup();
});

describe("KanbanCard — distribution_comment surface", () => {
  it("renders the comment when the card is unassigned (Нераспределено)", () => {
    renderCard(
      makeCard({
        distributionComment: "Срочно к Алейне, клиент знакомый",
        assignedUserId: null,
        completedAt: null,
      }),
    );

    const surface = screen.getByTestId("kanban-card-distribution-comment");
    expect(surface).toBeInTheDocument();
    expect(surface).toHaveTextContent("Срочно к Алейне, клиент знакомый");
  });

  it("does NOT render the comment when the card has been assigned (В работе)", () => {
    renderCard(
      makeCard({
        distributionComment: "Срочно к Алейне",
        assignedUserId: "u-2",
        assignedAt: "2026-05-11T10:00:00Z",
      }),
    );

    expect(
      screen.queryByTestId("kanban-card-distribution-comment"),
    ).not.toBeInTheDocument();
  });

  it("does NOT render the comment when the card is completed (Завершено)", () => {
    renderCard(
      makeCard({
        distributionComment: "Срочно к Алейне",
        completedAt: "2026-05-12T15:00:00Z",
      }),
    );

    expect(
      screen.queryByTestId("kanban-card-distribution-comment"),
    ).not.toBeInTheDocument();
  });

  it("renders nothing extra when distribution_comment is null", () => {
    renderCard(makeCard({ distributionComment: null }));

    expect(
      screen.queryByTestId("kanban-card-distribution-comment"),
    ).not.toBeInTheDocument();
  });

  it("renders nothing extra when distribution_comment is an empty string", () => {
    renderCard(makeCard({ distributionComment: "   " }));

    expect(
      screen.queryByTestId("kanban-card-distribution-comment"),
    ).not.toBeInTheDocument();
  });
});
