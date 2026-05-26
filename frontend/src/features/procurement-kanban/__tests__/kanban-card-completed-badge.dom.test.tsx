// @vitest-environment jsdom
/**
 * Testing 2 row 83 — «Готово» badge visibility on procurement kanban cards.
 *
 * Tester report: when a quote completed procurement (the last invoice was
 * marked done and the workflow advanced past `pending_procurement`) the
 * slice disappeared from /procurement for РОЗ / СтМОЗ / МОЗ. Backend fix
 * widens the kanban filter to include quotes with `procurement_completed_at
 * IS NOT NULL` (see `api/procurement.py`); this DOM test guards the UI side
 * of the visibility contract — every card whose parent quote carries a
 * `procurement_completed_at` timestamp renders a «Готово» badge so the user
 * understands the slice is no longer actionable from this screen.
 *
 * The badge appears regardless of caller role because authorization is
 * enforced server-side. The card body itself is identical to the in-progress
 * variant — only the badge differentiates it.
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

describe("KanbanCard — «Готово» badge (Testing 2 row 83)", () => {
  it("does NOT render «Готово» when procurement_completed_at is null (in-progress)", () => {
    renderCard({
      card: makeCard({ procurement_completed_at: null }),
    });
    expect(screen.queryByText("Готово")).not.toBeInTheDocument();
  });

  it("does NOT render «Готово» when procurement_completed_at is undefined (pre-rollout API)", () => {
    renderCard({
      card: makeCard({ procurement_completed_at: undefined }),
    });
    expect(screen.queryByText("Готово")).not.toBeInTheDocument();
  });

  it("renders «Готово» when procurement_completed_at is set — visible for РОЗ", () => {
    renderCard({
      card: makeCard({
        procurement_completed_at: "2026-05-25T10:00:00Z",
      }),
      canReassign: true, // head_of_procurement has broader scope
    });
    expect(screen.getByText("Готово")).toBeInTheDocument();
  });

  it("renders «Готово» when procurement_completed_at is set — visible for СтМОЗ", () => {
    renderCard({
      card: makeCard({
        procurement_completed_at: "2026-05-25T10:00:00Z",
      }),
      canReassign: true, // procurement_senior has broader scope
    });
    expect(screen.getByText("Готово")).toBeInTheDocument();
  });

  it("renders «Готово» when procurement_completed_at is set — visible for МОЗ", () => {
    renderCard({
      card: makeCard({
        procurement_completed_at: "2026-05-25T10:00:00Z",
      }),
      canReassign: true, // regular procurement (МОЗ)
    });
    expect(screen.getByText("Готово")).toBeInTheDocument();
  });

  it("renders «Готово» alongside «Тендер» without one excluding the other", () => {
    renderCard({
      card: makeCard({
        tender_type: "tender",
        procurement_completed_at: "2026-05-25T10:00:00Z",
      }),
    });
    expect(screen.getByText("Тендер")).toBeInTheDocument();
    expect(screen.getByText("Готово")).toBeInTheDocument();
  });
});
