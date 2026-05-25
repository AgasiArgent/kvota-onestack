// @vitest-environment jsdom
/**
 * Testing 2 row 75 v2 — «Переназначить» button visibility on procurement
 * kanban cards.
 *
 * PR #217 introduced the button but gated it behind `canReassign` (which in
 * turn was equal to `canDistribute`) — only admin / head_of_procurement /
 * procurement_senior could see it. v2 expands the scope so regular МОЗ
 * (`procurement`) can ALSO reassign their own brand-slices to colleagues.
 *
 * The button has to be visible directly on the card, not hidden inside a
 * dropdown or overflow menu — clicking the button itself opens the
 * assignment popover (same UX as for the head_of_procurement tier).
 *
 * Surface rule: render the button when (1) the caller passes
 * `canReassign={true}` AND (2) the card is past the distribution column.
 * In the distributing column the assign popover takes precedence — no
 * reassign needed there yet.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { DndContext } from "@dnd-kit/core";

// next/link works in jsdom but useRouter does not — neither the card nor the
// popover trigger uses navigation hooks, so no mock is needed here.

// Stub the reassign popover content so the test focuses on visibility of the
// trigger button rather than the full picker (UserSearchSelect + supabase).
// The trigger button itself is rendered by the popover, but is part of the
// card's body and visible without any user interaction.
vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    from: () => ({
      select: () => ({
        eq: () => ({
          neq: () => ({
            eq: () => Promise.resolve({ data: [], error: null }),
            is: () => Promise.resolve({ data: [], error: null }),
          }),
        }),
      }),
    }),
  }),
}));

vi.mock("@/entities/quote/server-actions", () => ({
  reassignBrandGroup: vi.fn().mockResolvedValue({ success: true }),
}));

import { KanbanCard } from "../ui/kanban-card";
import type { KanbanBrandCard } from "../model/types";
import type { ProcurementUserWorkload } from "@/shared/types/procurement-user";

function makeCard(overrides: Partial<KanbanBrandCard> = {}): KanbanBrandCard {
  return {
    quote_id: "q-1",
    brand: "ABB",
    idn_quote: "Q-202604-0001",
    customer_id: "cust-1",
    customer_name: "Acme",
    days_in_state: 2,
    updated_at: "2026-05-20T10:00:00Z",
    latest_reason: null,
    procurement_substatus: "searching_supplier",
    manager_id: "mgr-1",
    manager_name: "Иванов И.И.",
    procurement_user_ids: ["mz-1"],
    procurement_user_names: ["Петров П.П."],
    invoice_sums: [],
    tender_type: null,
    ...overrides,
  };
}

const WORKLOAD: ProcurementUserWorkload[] = [
  { user_id: "mz-1", full_name: "Петров П.П.", active_quotes: 3 },
  { user_id: "mz-2", full_name: "Сидоров С.С.", active_quotes: 1 },
];

function renderCard(props: Partial<Parameters<typeof KanbanCard>[0]> = {}) {
  return render(
    <DndContext>
      <KanbanCard
        card={makeCard()}
        onClick={() => {}}
        workload={WORKLOAD}
        orgId="org-1"
        {...props}
      />
    </DndContext>,
  );
}

afterEach(() => {
  cleanup();
});

/**
 * The card's outermost wrapper is itself a `role="button"` for keyboard +
 * a11y on the draggable surface, so its computed accessible name picks up
 * the «Переназначить» label from any descendant. To target ONLY the
 * popover trigger we query by its `title="Переназначить МОЗ"` attribute —
 * unique to the reassign button.
 */
const REASSIGN_TITLE = /Переназначить МОЗ/i;

describe("KanbanCard — «Переназначить» button visibility (Testing 2 row 75 v2)", () => {
  it("renders the button when canReassign=true and the card is past «Распределение»", () => {
    // МОЗ (regular procurement) calling case — v2 expands the gate to
    // include the assignee themselves.
    renderCard({ canReassign: true });

    const button = screen.getByTitle(REASSIGN_TITLE);
    expect(button).toBeInTheDocument();
    expect(button.tagName).toBe("BUTTON");
  });

  it("renders the button when canReassign=true and the card is in «Поиск поставщика»", () => {
    renderCard({
      canReassign: true,
      card: makeCard({ procurement_substatus: "searching_supplier" }),
    });

    expect(screen.getByTitle(REASSIGN_TITLE)).toBeInTheDocument();
  });

  it("renders the button when canReassign=true and the card is in «Ожидание цен»", () => {
    renderCard({
      canReassign: true,
      card: makeCard({ procurement_substatus: "waiting_prices" }),
    });

    expect(screen.getByTitle(REASSIGN_TITLE)).toBeInTheDocument();
  });

  it("renders the button when canReassign=true and the card is in «Цены готовы»", () => {
    renderCard({
      canReassign: true,
      card: makeCard({ procurement_substatus: "prices_ready" }),
    });

    expect(screen.getByTitle(REASSIGN_TITLE)).toBeInTheDocument();
  });

  it("renders the button when canReassign=true and the card is on «На паузе»", () => {
    renderCard({
      canReassign: true,
      card: makeCard({ procurement_substatus: "paused" }),
    });

    expect(screen.getByTitle(REASSIGN_TITLE)).toBeInTheDocument();
  });

  it("does NOT render the button when canReassign=false (e.g. sales / non-procurement viewer)", () => {
    // Regression guard: МОП (sales) and other non-procurement roles must
    // not be offered the reassign button.
    renderCard({ canReassign: false });

    expect(screen.queryByTitle(REASSIGN_TITLE)).not.toBeInTheDocument();
  });

  it("does NOT render the button on a «Распределение» card (assign popover takes over there)", () => {
    // In the distribute column the regular «Назначить» popover is the
    // primary action — reassign is for already-routed cards only.
    renderCard({
      canReassign: true,
      card: makeCard({ procurement_substatus: "distributing" }),
    });

    expect(screen.queryByTitle(REASSIGN_TITLE)).not.toBeInTheDocument();
  });

  it("renders the button label «Переназначить» directly on the trigger (no overflow menu)", () => {
    // Acceptance criterion #2: button is visible directly in the card,
    // not hidden in a dropdown/menu requiring an extra click to reveal.
    renderCard({ canReassign: true });

    const button = screen.getByTitle(REASSIGN_TITLE);
    // The visible button label itself must contain the Russian text — the
    // user reads it on the card without opening anything.
    expect(button).toHaveTextContent(/Переназначить/);
    expect(button).toBeVisible();
  });

  it("places the trigger inside the card body, not behind a sibling overflow toggle", () => {
    renderCard({ canReassign: true });

    const button = screen.getByTitle(REASSIGN_TITLE);
    // The card's outermost container is a div[role=button] (the draggable
    // surface). The reassign trigger must be a descendant — confirms it
    // lives inside the same card and not in a portal-only menu.
    const cardSurface = button.closest('[role="button"][aria-roledescription="draggable"]');
    expect(cardSurface).not.toBeNull();
  });

  it("does NOT render the button when canReassign prop is omitted (defaults to false)", () => {
    // Defaulting omitted prop to false matches the existing assign popover
    // behaviour — keeps the type-level default safe for callers that never
    // wire the gate.
    renderCard({});

    expect(screen.queryByTitle(REASSIGN_TITLE)).not.toBeInTheDocument();
  });
});
