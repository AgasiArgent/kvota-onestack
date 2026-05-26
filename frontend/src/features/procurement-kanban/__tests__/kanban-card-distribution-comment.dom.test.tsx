// @vitest-environment jsdom
/**
 * Testing 2 row 67 follow-up (FB-260525) — surface МОП «Контрольный список»
 * distribution_comment on the procurement kanban card.
 *
 * Tester report: when МОП fills the comment in the «Контрольный список»
 * modal at sales→procurement hand-off (e.g. «Срочно к Алейне, клиент
 * знакомый»), the hint was visible only on the quote detail page (context
 * panel sales-checklist block) — РОЗ / СтМОЗ / МОЗ had to open every card
 * to read it.
 *
 * Fix mirrors the workspace-kanban pattern (`kanban-card-distribution-
 * comment.dom.test.tsx` under `workspace-kanban/__tests__`): when the
 * `distribution_comment` field on the card is non-empty after trim, render
 * an amber-tinted block with the comment so МОЗ reads the hint inline.
 *
 * Unlike the workspace-kanban variant which gates on `!assigned && !completed`
 * (the hint loses signal once МОЛ/МОТ picked the КПП up), this surface keeps
 * the comment visible at every substatus — even «Готово» — because the
 * distribution decision context is still useful for retrospective audit on
 * the procurement board (МОЗ may need to remember why they took this case).
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { DndContext } from "@dnd-kit/core";

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
    procurement_substatus: "prices_ready",
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

describe("KanbanCard — МОП distribution_comment (Testing 2 row 67 follow-up)", () => {
  it("renders the comment block when distribution_comment is set", () => {
    renderCard({
      card: makeCard({
        distribution_comment: "Срочно к Алейне, клиент знакомый",
      }),
    });

    const block = screen.getByTestId("kanban-card-distribution-comment");
    expect(block).toBeInTheDocument();
    expect(block).toHaveTextContent("Срочно к Алейне, клиент знакомый");
  });

  it("does NOT render the block when distribution_comment is null", () => {
    renderCard({
      card: makeCard({ distribution_comment: null }),
    });
    expect(
      screen.queryByTestId("kanban-card-distribution-comment"),
    ).not.toBeInTheDocument();
  });

  it("does NOT render the block when distribution_comment is undefined (pre-rollout API)", () => {
    renderCard({
      // No distribution_comment field — simulates a response from a backend
      // that has not been redeployed with the row 67 follow-up yet.
      card: makeCard({}),
    });
    expect(
      screen.queryByTestId("kanban-card-distribution-comment"),
    ).not.toBeInTheDocument();
  });

  it("does NOT render the block when distribution_comment is whitespace-only", () => {
    renderCard({
      card: makeCard({ distribution_comment: "   \n  " }),
    });
    expect(
      screen.queryByTestId("kanban-card-distribution-comment"),
    ).not.toBeInTheDocument();
  });

  it("renders the comment alongside «Тендер» badge (both signals must coexist)", () => {
    renderCard({
      card: makeCard({
        distribution_comment: "Поторопить — клиент знакомый",
        tender_type: "tender",
      }),
    });

    expect(screen.getByText("Тендер")).toBeInTheDocument();
    expect(
      screen.getByTestId("kanban-card-distribution-comment"),
    ).toHaveTextContent("Поторопить — клиент знакомый");
  });

  it("renders the comment on «Готово» cards too (audit context still useful)", () => {
    renderCard({
      card: makeCard({
        distribution_comment: "Конкуренция за заказ — обогнали",
        procurement_completed_at: "2026-05-25T10:00:00Z",
      }),
    });

    expect(screen.getByText("Готово")).toBeInTheDocument();
    expect(
      screen.getByTestId("kanban-card-distribution-comment"),
    ).toHaveTextContent("Конкуренция за заказ — обогнали");
  });

  it("preserves newlines via whitespace-pre-wrap so multi-line comments render as authored", () => {
    renderCard({
      card: makeCard({
        distribution_comment: "Срочно\nКлиент знакомый",
      }),
    });

    const block = screen.getByTestId("kanban-card-distribution-comment");
    // The Tailwind class drives the visual behaviour; we assert the class is
    // present so a future refactor that drops it triggers the test.
    expect(block.className).toContain("whitespace-pre-wrap");
    expect(block.textContent).toContain("Срочно");
    expect(block.textContent).toContain("Клиент знакомый");
  });
});
