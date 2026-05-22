import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * Testing 2 row 79 (FB-260522) — МОЗ "когда привязали" timestamp in the
 * Участники inf-panel of `/quotes/{id}`.
 *
 * Regression chain:
 *   - Row 2 (FB-260513-100338-a778, May 13) surfaced МОЗ in the Участники
 *     block, back-filling «когда привязали» from the user's own earliest
 *     `workflow_transitions` row.
 *   - Row 79 (May 22) re-reports the missing date for freshly distributed
 *     quotes (РОЗ / СтМОЗ / МОЗ): a just-assigned МОЗ has not yet authored
 *     any workflow_transitions row, so the back-fill returned null and the
 *     panel rendered ФИО without a date.
 *
 * Fix: derive «когда привязали» from `status_history` rows with
 *      reason='auto: all items routed' (inserted by the kanban auto-advance
 *      helper the moment every item of a (quote, brand) slice is routed —
 *      i.e. the exact moment the МОЗ became responsible for that brand).
 *      Map each МОЗ user to the brands they cover on the quote and surface
 *      the earliest routed timestamp across those brands. Fall back to the
 *      old workflow_transitions back-fill only when status_history has no
 *      matching row (legacy quotes / partially routed slices).
 *
 * These tests mock the supabase server client and exercise
 * `fetchQuoteContextData` end-to-end to pin the behaviour.
 */

interface ProcurementItemRow {
  assigned_procurement_user: string | null;
  brand: string | null;
}

interface InvoiceRow {
  assigned_logistics_user: string | null;
  logistics_assigned_at: string | null;
  assigned_customs_user: string | null;
  customs_assigned_at: string | null;
}

interface StatusHistoryRow {
  brand: string | null;
  transitioned_at: string;
}

interface WorkflowTransitionRow {
  id: string;
  from_status: string | null;
  to_status: string | null;
  actor_id: string | null;
  actor_role: string | null;
  created_at: string | null;
}

interface UserProfileRow {
  user_id: string;
  full_name: string;
  phone?: string | null;
}

interface FakeSupabase {
  quoteRow: {
    sales_checklist: unknown;
    created_by: string | null;
    contact_person_id: string | null;
  } | null;
  procurementItems: ProcurementItemRow[];
  invoices: InvoiceRow[];
  statusHistory: StatusHistoryRow[];
  workflowTransitions: WorkflowTransitionRow[];
  userProfiles: UserProfileRow[];
  // Spy: tracks which tables were queried and with what filters so we can
  // assert that status_history is filtered correctly (reason + quote_id).
  statusHistoryFilters: Array<{ col: string; val: unknown }>;
  from(table: string): unknown;
}

let fake: FakeSupabase;

vi.mock("@/shared/lib/supabase/server", () => ({
  createClient: async () => fake,
  // Admin client is only used to look up the МОП auth email; we let it throw
  // so the catch-block in queries.ts substitutes null. Email is irrelevant to
  // the timestamp tests.
  createAdminClient: () => {
    throw new Error("admin client disabled in tests");
  },
}));

function makeFake(): FakeSupabase {
  const state: FakeSupabase = {
    quoteRow: null,
    procurementItems: [],
    invoices: [],
    statusHistory: [],
    workflowTransitions: [],
    userProfiles: [],
    statusHistoryFilters: [],

    from(table: string) {
      if (table === "quotes") {
        const builder = {
          select: () => builder,
          eq: () => builder,
          is: () => builder,
          single: () => Promise.resolve({ data: state.quoteRow }),
        };
        return builder;
      }

      if (table === "customer_contacts") {
        const builder = {
          select: () => builder,
          eq: () => builder,
          maybeSingle: () => Promise.resolve({ data: null }),
        };
        return builder;
      }

      if (table === "user_profiles") {
        const builder = {
          select: () => builder,
          eq: (col: string, val: unknown) => {
            // Used by the МОП lookup (maybeSingle) — narrow by user_id.
            const single = state.userProfiles.find(
              (p) => col === "user_id" && p.user_id === val
            );
            return {
              maybeSingle: () => Promise.resolve({ data: single ?? null }),
              in: () => builder,
            };
          },
          in: (col: string, values: unknown[]) => {
            // Batch lookup for transition actors + МОЗ + МОЛ + МОТ.
            const ids = values as string[];
            const rows = state.userProfiles.filter((p) =>
              ids.includes(p.user_id)
            );
            return Promise.resolve({ data: rows });
          },
        };
        return builder;
      }

      if (table === "workflow_transitions") {
        const builder = {
          select: () => builder,
          eq: () => builder,
          order: () =>
            Promise.resolve({ data: state.workflowTransitions, error: null }),
        };
        return builder;
      }

      if (table === "invoices") {
        const builder = {
          select: () => builder,
          eq: () =>
            Promise.resolve({ data: state.invoices, error: null }),
        };
        return builder;
      }

      if (table === "quote_items") {
        const builder = {
          select: () => builder,
          eq: () =>
            Promise.resolve({
              data: state.procurementItems,
              error: null,
            }),
        };
        return builder;
      }

      if (table === "status_history") {
        // Two .eq() calls in sequence — return chainable that resolves on the
        // second .eq() so the caller's await receives the rows.
        const builder = {
          select: () => builder,
          eq: (col: string, val: unknown) => {
            state.statusHistoryFilters.push({ col, val });
            if (state.statusHistoryFilters.length >= 2) {
              return Promise.resolve({
                data: state.statusHistory,
                error: null,
              });
            }
            return builder;
          },
        };
        return builder;
      }

      throw new Error(`Unexpected table: ${table}`);
    },
  };
  return state;
}

const QUOTE_ID = "ef05f7ee-3ef7-4589-a751-87d1aa500a71";
const MOZ_USER = "072d5ddd-adbc-45e2-8cef-df268fe410aa";
const MOP_USER = "ad7eb9a1-fbc9-475a-9891-54db04fa7768";

beforeEach(() => {
  fake = makeFake();
});

describe("fetchQuoteContextData — МОЗ assigned_at (Testing 2 row 79)", () => {
  it("uses status_history.transitioned_at as the МОЗ assignment moment", async () => {
    fake.quoteRow = {
      sales_checklist: null,
      created_by: MOP_USER,
      contact_person_id: null,
    };
    fake.procurementItems = [
      { assigned_procurement_user: MOZ_USER, brand: "leroy" },
    ];
    fake.statusHistory = [
      { brand: "leroy", transitioned_at: "2026-05-20T12:30:24.082Z" },
    ];
    // Critically: NO workflow_transitions row for the МОЗ themselves —
    // they were just assigned and haven't acted yet.
    fake.workflowTransitions = [
      {
        id: "wt-1",
        from_status: "draft",
        to_status: "pending_procurement",
        actor_id: MOP_USER,
        actor_role: "sales",
        created_at: "2026-05-20T12:28:35.510Z",
      },
    ];
    fake.userProfiles = [
      { user_id: MOZ_USER, full_name: "Сергеева Анастасия", phone: null },
      { user_id: MOP_USER, full_name: "Пономарев Антон", phone: null },
    ];

    const { fetchQuoteContextData } = await import("../queries");
    const data = await fetchQuoteContextData(QUOTE_ID);

    expect(data.procurementAssignees).toHaveLength(1);
    expect(data.procurementAssignees[0]).toMatchObject({
      user_id: MOZ_USER,
      full_name: "Сергеева Анастасия",
      assigned_at: "2026-05-20T12:30:24.082Z",
    });
  });

  it("filters status_history by quote_id AND reason='auto: all items routed'", async () => {
    fake.quoteRow = {
      sales_checklist: null,
      created_by: null,
      contact_person_id: null,
    };

    const { fetchQuoteContextData } = await import("../queries");
    await fetchQuoteContextData(QUOTE_ID);

    expect(fake.statusHistoryFilters).toEqual([
      { col: "quote_id", val: QUOTE_ID },
      { col: "reason", val: "auto: all items routed" },
    ]);
  });

  it("picks the earliest routed timestamp when a МОЗ covers multiple brands", async () => {
    fake.quoteRow = {
      sales_checklist: null,
      created_by: null,
      contact_person_id: null,
    };
    fake.procurementItems = [
      { assigned_procurement_user: MOZ_USER, brand: "Bosch" },
      { assigned_procurement_user: MOZ_USER, brand: "GRACO" },
    ];
    fake.statusHistory = [
      { brand: "GRACO", transitioned_at: "2026-05-19T14:38:42.352Z" },
      { brand: "Bosch", transitioned_at: "2026-05-19T13:45:40.358Z" },
    ];
    fake.userProfiles = [
      { user_id: MOZ_USER, full_name: "Закупщик", phone: null },
    ];

    const { fetchQuoteContextData } = await import("../queries");
    const data = await fetchQuoteContextData(QUOTE_ID);

    // Bosch routed earlier than GRACO — that's the assignment moment.
    expect(data.procurementAssignees[0].assigned_at).toBe(
      "2026-05-19T13:45:40.358Z"
    );
  });

  it("treats null brand on quote_items as empty-string key (matches kanban convention)", async () => {
    fake.quoteRow = {
      sales_checklist: null,
      created_by: null,
      contact_person_id: null,
    };
    fake.procurementItems = [
      { assigned_procurement_user: MOZ_USER, brand: null },
    ];
    fake.statusHistory = [
      // status_history.brand can be null OR empty string when the slice has
      // no brand; we map both to the same key. (Production data tends to
      // be empty string due to JS coercion in kanban-auto-advance.)
      { brand: "", transitioned_at: "2026-05-21T10:00:00Z" },
    ];
    fake.userProfiles = [
      { user_id: MOZ_USER, full_name: "Закупщик", phone: null },
    ];

    const { fetchQuoteContextData } = await import("../queries");
    const data = await fetchQuoteContextData(QUOTE_ID);

    expect(data.procurementAssignees[0].assigned_at).toBe(
      "2026-05-21T10:00:00Z"
    );
  });

  it("falls back to workflow_transitions when status_history has no row for the МОЗ's brand", async () => {
    // Legacy quote that pre-dates kanban-auto-advance: no status_history rows
    // exist but the МОЗ did push the workflow forward at some point.
    fake.quoteRow = {
      sales_checklist: null,
      created_by: null,
      contact_person_id: null,
    };
    fake.procurementItems = [
      { assigned_procurement_user: MOZ_USER, brand: "LegacyBrand" },
    ];
    fake.statusHistory = [];
    fake.workflowTransitions = [
      {
        id: "wt-legacy",
        from_status: "pending_procurement",
        to_status: "pending_specification",
        actor_id: MOZ_USER,
        actor_role: "procurement",
        created_at: "2026-04-01T08:00:00Z",
      },
    ];
    fake.userProfiles = [
      { user_id: MOZ_USER, full_name: "Закупщик", phone: null },
    ];

    const { fetchQuoteContextData } = await import("../queries");
    const data = await fetchQuoteContextData(QUOTE_ID);

    expect(data.procurementAssignees[0].assigned_at).toBe(
      "2026-04-01T08:00:00Z"
    );
  });

  it("returns null assigned_at only when BOTH sources are empty (panel renders ФИО w/o date)", async () => {
    fake.quoteRow = {
      sales_checklist: null,
      created_by: null,
      contact_person_id: null,
    };
    fake.procurementItems = [
      { assigned_procurement_user: MOZ_USER, brand: "OrphanBrand" },
    ];
    // No status_history, no workflow_transitions for this user.
    fake.statusHistory = [];
    fake.workflowTransitions = [];
    fake.userProfiles = [
      { user_id: MOZ_USER, full_name: "Закупщик", phone: null },
    ];

    const { fetchQuoteContextData } = await import("../queries");
    const data = await fetchQuoteContextData(QUOTE_ID);

    expect(data.procurementAssignees[0]).toMatchObject({
      user_id: MOZ_USER,
      full_name: "Закупщик",
      assigned_at: null,
    });
  });

  it("deduplicates МОЗ users across multiple items", async () => {
    fake.quoteRow = {
      sales_checklist: null,
      created_by: null,
      contact_person_id: null,
    };
    fake.procurementItems = [
      { assigned_procurement_user: MOZ_USER, brand: "leroy" },
      { assigned_procurement_user: MOZ_USER, brand: "leroy" },
      { assigned_procurement_user: MOZ_USER, brand: "leroy" },
    ];
    fake.statusHistory = [
      { brand: "leroy", transitioned_at: "2026-05-20T12:30:24Z" },
    ];
    fake.userProfiles = [
      { user_id: MOZ_USER, full_name: "Закупщик", phone: null },
    ];

    const { fetchQuoteContextData } = await import("../queries");
    const data = await fetchQuoteContextData(QUOTE_ID);

    // One row per distinct user_id — never duplicated by item count.
    expect(data.procurementAssignees).toHaveLength(1);
  });
});
