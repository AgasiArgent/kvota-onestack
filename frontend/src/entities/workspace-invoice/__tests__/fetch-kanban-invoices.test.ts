import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * Tests for fetchKanbanInvoices — the kanban board fetcher.
 *
 * Two regressions covered (Testing 2 rows 40/41/43/57):
 *  - The ACTIVE query must gate on the parent quote having transitioned to
 *    `workflow_status = 'pending_logistics_and_customs'`, so a single
 *    completed КП of a multi-invoice quote does NOT surface while the quote
 *    is still at pending_procurement.
 *  - The card assignee must show the ФИО from `user_profiles.full_name`, not
 *    the auth email.
 *
 * The DB layer is mocked via a fluent fake-supabase admin client that records
 * the filter chain applied to the `invoices` SELECT.
 */

// `queries.ts` is a server-only module; the `server-only` guard package is
// not installed in the test runtime, so stub it to an empty module.
vi.mock("server-only", () => ({}));

vi.mock("@/shared/lib/supabase/server", () => ({
  createAdminClient: () => fakeAdmin,
}));

interface QueryRecord {
  filters: Array<{ op: string; col: string; val: unknown }>;
}

interface FakeAdmin {
  /** Rows the `invoices` SELECT resolves to (same for active + completed). */
  invoiceRows: unknown[];
  /** user_profiles rows keyed implicitly by user_id. */
  profiles: Array<{ user_id: string; full_name: string | null }>;
  /** auth.users emails by id (fallback name source). */
  emailsById: Record<string, string>;
  /** Recorded filter chains for every `invoices` query (active first). */
  invoiceQueries: QueryRecord[];
  auth: { admin: { getUserById(id: string): Promise<unknown> } };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  from(table: string): any;
}

let fakeAdmin: FakeAdmin;

function makeFakeAdmin(): FakeAdmin {
  const state: FakeAdmin = {
    invoiceRows: [],
    profiles: [],
    emailsById: {},
    invoiceQueries: [],
    auth: {
      admin: {
        getUserById: async (id: string) => {
          const email = state.emailsById[id];
          if (!email) return { data: { user: null } };
          return {
            data: { user: { id, email, user_metadata: {} } },
          };
        },
      },
    },
    from(table: string) {
      if (table === "invoices") {
        const record: QueryRecord = { filters: [] };
        state.invoiceQueries.push(record);
        // A PostgREST-like builder: every method returns the builder, and the
        // builder itself is thenable — resolving to the scripted rows. This
        // matches both the active query (`…order()`) and the completed query
        // (`…order().limit()`), without caring about the terminal method.
        const result = { data: state.invoiceRows, error: null };
        const builder: Record<string, unknown> = {
          then: (onFulfilled: (v: typeof result) => unknown) =>
            Promise.resolve(result).then(onFulfilled),
        };
        const chain = (op: string) => (col: string, val?: unknown) => {
          record.filters.push({ op, col, val });
          return builder;
        };
        builder.select = () => builder;
        builder.eq = chain("eq");
        builder.is = chain("is");
        builder.not = (col: string, op: string, val: unknown) => {
          record.filters.push({ op: `not.${op}`, col, val });
          return builder;
        };
        builder.gte = chain("gte");
        builder.limit = () => builder;
        builder.order = () => builder;
        return builder;
      }
      if (table === "quote_items") {
        return {
          select: () => ({
            in: async () => ({ data: [], error: null }),
          }),
        };
      }
      if (table === "user_profiles") {
        return {
          select: () => ({
            in: async () => ({ data: state.profiles, error: null }),
          }),
        };
      }
      throw new Error(`Unexpected table: ${table}`);
    },
  };
  return state;
}

function makeInvoiceRow(overrides: Record<string, unknown> = {}) {
  return {
    id: "inv-1",
    quote_id: "q-1",
    invoice_number: "INV-1",
    pickup_country: "Китай",
    pickup_country_code: "CN",
    pickup_city: "Шанхай",
    total_weight_kg: 10,
    total_volume_m3: 1,
    package_count: 2,
    procurement_completed_at: "2026-05-10T10:00:00Z",
    logistics_assigned_at: "2026-05-10T11:00:00Z",
    logistics_deadline_at: null,
    logistics_completed_at: null,
    assigned_logistics_user: "user-aleyna",
    customs_assigned_at: null,
    customs_deadline_at: null,
    customs_completed_at: null,
    assigned_customs_user: null,
    created_at: "2026-05-09T00:00:00Z",
    cargo_places: [],
    quote: {
      id: "q-1",
      idn_quote: "Q-202605-0001",
      organization_id: "org-1",
      workflow_status: "pending_logistics_and_customs",
      delivery_city: "Москва",
      delivery_country: "Россия",
      deleted_at: null,
      total_amount: 1000,
      currency: "USD",
      customer: { id: "c-1", name: "Заказчик", country: "RU", city: "Москва" },
    },
    ...overrides,
  };
}

describe("fetchKanbanInvoices — active query gating (Bug 2)", () => {
  beforeEach(() => {
    fakeAdmin = makeFakeAdmin();
  });

  it("gates the ACTIVE query on quote.workflow_status = pending_logistics_and_customs", async () => {
    fakeAdmin.invoiceRows = [makeInvoiceRow()];
    const { fetchKanbanInvoices } = await import("../queries");
    await fetchKanbanInvoices("logistics", "user-x", "org-1", true);

    // First `invoices` query is the active one.
    const active = fakeAdmin.invoiceQueries[0];
    const wfFilter = active.filters.find(
      (f) => f.op === "eq" && f.col === "quote.workflow_status"
    );
    expect(wfFilter).toBeDefined();
    expect(wfFilter?.val).toBe("pending_logistics_and_customs");
  });

  it("does NOT gate the COMPLETED query on workflow_status", async () => {
    fakeAdmin.invoiceRows = [];
    const { fetchKanbanInvoices } = await import("../queries");
    await fetchKanbanInvoices("logistics", "user-x", "org-1", true);

    // Second `invoices` query is the completed one — must not carry the gate
    // (a completed invoice whose quote later advanced must still show).
    const completed = fakeAdmin.invoiceQueries[1];
    const wfFilter = completed.filters.find(
      (f) => f.col === "quote.workflow_status"
    );
    expect(wfFilter).toBeUndefined();
  });
});

describe("fetchKanbanInvoices — assignee ФИО (Bug 3)", () => {
  beforeEach(() => {
    fakeAdmin = makeFakeAdmin();
  });

  it("shows the ФИО from user_profiles, not the email", async () => {
    fakeAdmin.invoiceRows = [makeInvoiceRow()];
    fakeAdmin.profiles = [
      { user_id: "user-aleyna", full_name: "Алейна Логистик" },
    ];
    fakeAdmin.emailsById = { "user-aleyna": "aleynasevimd@gmail.com" };

    const { fetchKanbanInvoices } = await import("../queries");
    const board = await fetchKanbanInvoices("logistics", "user-x", "org-1", true);

    const card = board.in_progress[0];
    expect(card).toBeDefined();
    expect(card.assignedUser?.name).toBe("Алейна Логистик");
  });

  it("falls back to email when no ФИО exists in user_profiles", async () => {
    fakeAdmin.invoiceRows = [makeInvoiceRow()];
    fakeAdmin.profiles = []; // no profile row
    fakeAdmin.emailsById = { "user-aleyna": "aleynasevimd@gmail.com" };

    const { fetchKanbanInvoices } = await import("../queries");
    const board = await fetchKanbanInvoices("logistics", "user-x", "org-1", true);

    expect(board.in_progress[0]?.assignedUser?.name).toBe(
      "aleynasevimd@gmail.com"
    );
  });
});
