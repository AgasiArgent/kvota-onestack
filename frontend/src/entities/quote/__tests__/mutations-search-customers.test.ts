import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * Bug FB-260503-mop-rop fail #4 — "Новый КП" customer typeahead leaked the
 * full org-wide customer list to МОПы. The /customers list is correctly
 * scoped to assigned customers via fetchCustomersList; the modal version was
 * not. searchCustomers must apply the same access gate.
 *
 * Plus: input must be trimmed BEFORE both the .ilike filter and the DaData
 * lookup, otherwise " 7707083893" sails through as a not-found query and
 * triggers a duplicate-creation suggestion.
 */

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => fakeSupabase,
}));

interface CapturedQuery {
  /** Last column.string passed to .or() — captured to assert ilike search ran. */
  orFilter: string | null;
  /** Last (column, ids[]) pair passed to .in() — captured to assert .in scoping. */
  inFilter: { column: string; ids: string[] } | null;
}

interface FakeSupabase {
  // Returned rows for the customers query (the caller never looks at the
  // actual rows in our access-control assertions, only the filter chain).
  customerRows: Array<{ id: string; name: string; inn: string | null }>;
  // Rows returned by customer_assignees.in('user_id', ...) — drives
  // getAssignedCustomerIds. Map by user_id so head_of_sales group expansion
  // can be modelled by membersByGroup below.
  assigneesByUser: Map<string, string[]>;
  // Rows returned by customers.in('manager_id', ...) — manager fallback in
  // getAssignedCustomerIds.
  managedByUser: Map<string, string[]>;
  // Rows returned by user_profiles.eq(sales_group_id) — head_of_sales group
  // expansion. Empty group → fallback to self.
  membersByGroup: Map<string, string[]>;

  captured: CapturedQuery;

  from(table: string): unknown;
}

let fakeSupabase: FakeSupabase;

function makeFakeSupabase(): FakeSupabase {
  const state: FakeSupabase = {
    customerRows: [],
    assigneesByUser: new Map(),
    managedByUser: new Map(),
    membersByGroup: new Map(),
    captured: { orFilter: null, inFilter: null },

    from(table: string) {
      if (table === "customers") {
        // The chain we model:
        //   .from('customers')
        //     .select(...)
        //     .eq('organization_id', orgId)
        //     .or(filter)
        //     .order(...)
        //     .limit(...)
        //     [.in('id', ids)]   // sales-only branch
        //   = thenable returning { data, error }
        // OR (manager-fallback branch in getAssignedCustomerIds):
        //   .from('customers')
        //     .select('id')
        //     .in('manager_id', ids)
        //     .eq('organization_id', orgId)
        //   = thenable returning rows of { id }
        const builder = {
          select: vi.fn(() => builder),
          eq: vi.fn(() => builder),
          or: vi.fn((filter: string) => {
            state.captured.orFilter = filter;
            return builder;
          }),
          order: vi.fn(() => builder),
          limit: vi.fn(() => builder),
          in: vi.fn((col: string, ids: string[]) => {
            // Disambiguate by column: 'manager_id' = manager fallback;
            // 'id' = sales-only scoping on the search query.
            if (col === "manager_id") {
              const allIds = ids.flatMap((u) => state.managedByUser.get(u) ?? []);
              return {
                eq: vi.fn(() => ({
                  then(resolve: (r: { data: { id: string }[] }) => unknown) {
                    return Promise.resolve({
                      data: allIds.map((id) => ({ id })),
                    }).then(resolve);
                  },
                })),
              };
            }
            // sales-only .in('id', ids) on the search query
            state.captured.inFilter = { column: col, ids };
            return builder;
          }),
          then(resolve: (r: { data: typeof state.customerRows; error: null }) => unknown) {
            // Apply the captured .in('id', ids) filter to the returned rows
            // so tests can assert the modal really restricted to assigned IDs.
            let rows = state.customerRows;
            if (
              state.captured.inFilter &&
              state.captured.inFilter.column === "id"
            ) {
              const allowed = new Set(state.captured.inFilter.ids);
              rows = rows.filter((r) => allowed.has(r.id));
            }
            return Promise.resolve({ data: rows, error: null }).then(resolve);
          },
        };
        return builder;
      }
      if (table === "customer_assignees") {
        // .select('customer_id').in('user_id', ids) → rows
        const builder = {
          select: vi.fn(() => builder),
          in: vi.fn((_col: string, ids: string[]) => {
            const all = ids.flatMap(
              (uid) => state.assigneesByUser.get(uid) ?? []
            );
            return {
              then(
                resolve: (r: { data: { customer_id: string }[] }) => unknown
              ) {
                return Promise.resolve({
                  data: all.map((cid) => ({ customer_id: cid })),
                }).then(resolve);
              },
            };
          }),
        };
        return builder;
      }
      if (table === "user_profiles") {
        // head_of_sales group expansion:
        //   .select('user_id').eq('sales_group_id', g).eq('organization_id', o)
        const builder = {
          select: vi.fn(() => builder),
          eq: vi.fn((col: string, value: string) => {
            if (col === "sales_group_id") {
              const members = state.membersByGroup.get(value) ?? [];
              const next = {
                eq: vi.fn(() => ({
                  then(
                    resolve: (r: { data: { user_id: string }[] }) => unknown
                  ) {
                    return Promise.resolve({
                      data: members.map((uid) => ({ user_id: uid })),
                    }).then(resolve);
                  },
                })),
              };
              return next;
            }
            return builder;
          }),
        };
        return builder;
      }
      throw new Error(`Unexpected table: ${table}`);
    },
  };
  return state;
}

describe("searchCustomers — sales-only access gate", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
  });

  it("restricts the query to assigned customer ids when user is sales-only", async () => {
    // МОП scenario: Bokov sees customers cust-1 and cust-2 only.
    fakeSupabase.assigneesByUser.set("user-bokov", ["cust-1", "cust-2"]);
    fakeSupabase.customerRows = [
      { id: "cust-1", name: "ООО Альфа", inn: "1234567890" },
      { id: "cust-2", name: "ООО Бета", inn: "0987654321" },
      { id: "cust-system-99", name: "ООО Системный", inn: "1111111111" },
    ];

    const { searchCustomers } = await import("../mutations");
    const results = await searchCustomers("ООО", {
      id: "user-bokov",
      roles: ["sales"],
      orgId: "org-1",
    });

    expect(fakeSupabase.captured.inFilter).not.toBeNull();
    expect(fakeSupabase.captured.inFilter!.column).toBe("id");
    expect(new Set(fakeSupabase.captured.inFilter!.ids)).toEqual(
      new Set(["cust-1", "cust-2"])
    );
    // System-wide customer must NOT leak through.
    expect(results.map((r) => r.id).sort()).toEqual(["cust-1", "cust-2"]);
  });

  it("returns [] for a sales-only user with no assigned customers (uses sentinel UUID)", async () => {
    // No assignees, no managed customers — the fix must scope to the sentinel
    // UUID so Postgres returns zero rows instead of treating .in([]) as a no-op.
    fakeSupabase.customerRows = [
      { id: "cust-1", name: "ООО Альфа", inn: "1234567890" },
    ];

    const { searchCustomers } = await import("../mutations");
    const results = await searchCustomers("ООО", {
      id: "user-bokov",
      roles: ["sales"],
      orgId: "org-1",
    });

    expect(fakeSupabase.captured.inFilter).not.toBeNull();
    // Sentinel UUID, not an empty array.
    expect(fakeSupabase.captured.inFilter!.ids).toEqual([
      "00000000-0000-0000-0000-000000000000",
    ]);
    expect(results).toEqual([]);
  });

  it("expands head_of_sales scope to all sales-group members", async () => {
    // РОП scenario: Petrov is head_of_sales, leads group "g-1" containing
    // user-bokov and user-ivanov. He must see customers assigned to either.
    fakeSupabase.membersByGroup.set("g-1", [
      "user-bokov",
      "user-ivanov",
      "user-petrov",
    ]);
    fakeSupabase.assigneesByUser.set("user-bokov", ["cust-1"]);
    fakeSupabase.assigneesByUser.set("user-ivanov", ["cust-2"]);
    fakeSupabase.customerRows = [
      { id: "cust-1", name: "ООО Альфа", inn: "1" },
      { id: "cust-2", name: "ООО Бета", inn: "2" },
      { id: "cust-3", name: "ООО Гамма", inn: "3" },
    ];

    const { searchCustomers } = await import("../mutations");
    const results = await searchCustomers("ООО", {
      id: "user-petrov",
      roles: ["head_of_sales"],
      salesGroupId: "g-1",
      orgId: "org-1",
    });

    expect(fakeSupabase.captured.inFilter).not.toBeNull();
    expect(new Set(fakeSupabase.captured.inFilter!.ids)).toEqual(
      new Set(["cust-1", "cust-2"])
    );
    expect(results.map((r) => r.id).sort()).toEqual(["cust-1", "cust-2"]);
  });

  it("does not apply the .in() id filter for non-sales roles (admin sees everything)", async () => {
    fakeSupabase.customerRows = [
      { id: "cust-1", name: "ООО Альфа", inn: "1" },
      { id: "cust-2", name: "ООО Бета", inn: "2" },
      { id: "cust-system-99", name: "ООО Системный", inn: "3" },
    ];

    const { searchCustomers } = await import("../mutations");
    const results = await searchCustomers("ООО", {
      id: "user-admin",
      roles: ["admin"],
      orgId: "org-1",
    });

    // No id-restriction → all rows are returned.
    expect(fakeSupabase.captured.inFilter).toBeNull();
    expect(results.map((r) => r.id).sort()).toEqual([
      "cust-1",
      "cust-2",
      "cust-system-99",
    ]);
  });

  it("does not apply the .in() id filter for users with mixed roles (e.g. sales + admin)", async () => {
    // isSalesOnly is false when any non-sales role is present, so the gate
    // must not engage. Defends against accidentally hiding admin's customers.
    fakeSupabase.customerRows = [
      { id: "cust-1", name: "ООО Альфа", inn: "1" },
    ];

    const { searchCustomers } = await import("../mutations");
    await searchCustomers("ООО", {
      id: "user-mixed",
      roles: ["sales", "admin"],
      orgId: "org-1",
    });

    expect(fakeSupabase.captured.inFilter).toBeNull();
  });
});

describe("searchCustomers — query trimming", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
  });

  it("returns [] without hitting the DB for a whitespace-only query", async () => {
    fakeSupabase.customerRows = [
      { id: "cust-1", name: "ООО Альфа", inn: "1" },
    ];

    const { searchCustomers } = await import("../mutations");
    const results = await searchCustomers("   ", {
      id: "user-admin",
      roles: ["admin"],
      orgId: "org-1",
    });

    expect(results).toEqual([]);
    // No .or() filter means the query never ran.
    expect(fakeSupabase.captured.orFilter).toBeNull();
  });

  it("trims leading/trailing whitespace before building the ilike filter", async () => {
    // " 7707083893" must search for "7707083893" — without trimming, the
    // ilike would look for '% 7707083893%' which never matches an INN col.
    fakeSupabase.customerRows = [
      { id: "cust-sber", name: "ПАО СБЕРБАНК", inn: "7707083893" },
    ];

    const { searchCustomers } = await import("../mutations");
    const results = await searchCustomers(" 7707083893", {
      id: "user-admin",
      roles: ["admin"],
      orgId: "org-1",
    });

    expect(fakeSupabase.captured.orFilter).not.toBeNull();
    // Must contain the trimmed value, not the leading-space version.
    expect(fakeSupabase.captured.orFilter).toContain("7707083893");
    expect(fakeSupabase.captured.orFilter).not.toContain(" 7707083893");
    expect(results).toHaveLength(1);
    expect(results[0].id).toBe("cust-sber");
  });
});
