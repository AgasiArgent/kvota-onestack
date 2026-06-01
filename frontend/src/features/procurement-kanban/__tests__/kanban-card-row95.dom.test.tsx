// @vitest-environment jsdom
/**
 * Testing 2 row 95b + 95c — procurement kanban card.
 *
 * 95b: «Цены готовы» cards surface the КПП procurement-stage deadline
 *      (`procurement_deadline_at`, formatted ДД.ММ.ГГ) so the МОЗ sees it
 *      without opening the deal. Other columns don't render the deadline row.
 *
 * 95c: the inline pause reason on «На паузе» cards is rendered in the
 *      design-system danger color (`text-destructive`) so a paused card is
 *      spotted at a glance.
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

describe("KanbanCard — КПП deadline on «Цены готовы» (Testing 2 row 95b)", () => {
  it("renders the deadline label + formatted date on prices_ready cards", () => {
    renderCard({
      card: makeCard({
        procurement_substatus: "prices_ready",
        // 2026-06-15 12:00 MSK → formatted 15.06.26.
        procurement_deadline_at: "2026-06-15T09:00:00Z",
      }),
    });
    const row = screen.getByTestId("kanban-card-procurement-deadline");
    expect(row).toBeInTheDocument();
    expect(row.textContent).toContain("Дедлайн КПП:");
    expect(row.textContent).toContain("15.06.26");
  });

  it("renders an em-dash when prices_ready card has no deadline", () => {
    renderCard({
      card: makeCard({
        procurement_substatus: "prices_ready",
        procurement_deadline_at: null,
      }),
    });
    const row = screen.getByTestId("kanban-card-procurement-deadline");
    expect(row.textContent).toContain("Дедлайн КПП:");
    expect(row.textContent).toContain("—");
  });

  it("does NOT render the deadline row on non-prices_ready columns", () => {
    renderCard({
      card: makeCard({
        procurement_substatus: "searching_supplier",
        procurement_deadline_at: "2026-06-15T09:00:00Z",
      }),
    });
    expect(
      screen.queryByTestId("kanban-card-procurement-deadline"),
    ).not.toBeInTheDocument();
  });
});

describe("KanbanCard — red pause reason (Testing 2 row 95c)", () => {
  it("renders the inline pause reason in the danger color", () => {
    renderCard({
      card: makeCard({
        procurement_substatus: "paused",
        pause_log: {
          id: "p-1",
          paused_at: "2026-05-25T10:00:00Z",
          paused_by_name: "Иванов И.И.",
          reason: "Ждём подтверждения клиента",
        },
      }),
    });
    const reasonNode = screen.getByText(/Ждём подтверждения клиента/);
    // The pause reason uses the design-system danger token, not muted gray.
    expect(reasonNode.className).toContain("text-destructive");
    expect(reasonNode.className).not.toContain("text-muted-foreground");
  });
});
