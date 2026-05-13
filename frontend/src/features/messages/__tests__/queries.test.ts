import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * Bug Batch M row 12 — МВЭД (customs / head_of_customs) opened /messages and
 * saw zero chat cards. Root cause: `fetchAllChats` had branches only for
 * `isSalesOnly` and `isAssignedItemsOnly` — a pure `customs` user fell into
 * `isAssignedItemsOnly`, which filters by
 *   or(assigned_logistics_user.eq.{id}, assigned_customs_user.eq.{id})
 * but there is no per-user customs assignment, so the result was always 0
 * quotes. `head_of_customs` is even worse: it fell through to "see all org
 * quotes" — broader than the stage-only customs tier the user expects.
 *
 * Fix: insert a customs-tier branch BEFORE `isAssignedItemsOnly` that
 * restricts the query to quotes in customs workflow stages
 * (pending_customs, pending_logistics_and_customs) for the org. Mirrors the
 * tier routing in `fetchQuotesList` (entities/quote/queries.ts) and the
 * `isCustomsOnly` semantics documented in shared/lib/roles.ts.
 *
 * The mock captures the chained Supabase calls so we can assert the right
 * filter is applied for each role combination.
 */

interface CapturedFilter {
  type: "in" | "or" | "eq" | "is";
  args: unknown[];
}

interface FakeSupabase {
  /** Captured .from() targets in order. */
  fromCalls: string[];
  /** Captured filter calls on the quotes query (in invocation order). */
  quotesFilters: CapturedFilter[];
  /** Rows returned by the quotes query. */
  quoteRows: Array<{
    id: string;
    idn_quote: string;
    customer_id: string | null;
    created_by: string;
  }>;
  /** Rows returned by quote_items lookups (procurement-assigned subquery). */
  procurementItemRows: Array<{ quote_id: string }>;
  from(table: string): unknown;
}

let fakeSupabase: FakeSupabase;

vi.mock("@/shared/lib/supabase/server", () => ({
  createClient: async () => fakeSupabase,
}));

// Access helper is invoked for sales-only users — mock returns empty so the
// non-sales branches stay focused on workflow_status filtering.
vi.mock("@/shared/lib/access", () => ({
  getAssignedCustomerIds: async () => [],
}));

function makeFakeSupabase(): FakeSupabase {
  const state: FakeSupabase = {
    fromCalls: [],
    quotesFilters: [],
    quoteRows: [],
    procurementItemRows: [],

    from(table: string) {
      state.fromCalls.push(table);

      if (table === "quote_items") {
        // The procurement subquery: .from('quote_items').select('quote_id')
        //   .eq('assigned_procurement_user', user.id) — thenable.
        const builder = {
          select: () => builder,
          eq: () => builder,
          then(resolve: (r: { data: typeof state.procurementItemRows }) => unknown) {
            return Promise.resolve({ data: state.procurementItemRows }).then(
              resolve
            );
          },
        };
        return builder;
      }

      if (table === "quotes") {
        const builder = {
          select: () => builder,
          eq: (col: string, val: unknown) => {
            state.quotesFilters.push({ type: "eq", args: [col, val] });
            return builder;
          },
          is: (col: string, val: unknown) => {
            state.quotesFilters.push({ type: "is", args: [col, val] });
            return builder;
          },
          in: (col: string, values: unknown[]) => {
            state.quotesFilters.push({ type: "in", args: [col, values] });
            return builder;
          },
          or: (filter: string) => {
            state.quotesFilters.push({ type: "or", args: [filter] });
            return builder;
          },
          then(resolve: (r: { data: typeof state.quoteRows; error: null }) => unknown) {
            return Promise.resolve({
              data: state.quoteRows,
              error: null,
            }).then(resolve);
          },
        };
        return builder;
      }

      if (table === "quote_comments") {
        // Returns no comments — empty chat list is fine for these tests.
        const builder = {
          select: () => builder,
          in: () => builder,
          order: () => Promise.resolve({ data: [], error: null }),
        };
        return builder;
      }

      if (table === "customers" || table === "user_profiles") {
        const builder = {
          select: () => builder,
          in: () => Promise.resolve({ data: [], error: null }),
        };
        return builder;
      }

      throw new Error(`Unexpected table: ${table}`);
    },
  };
  return state;
}

const USER_ID = "user-mvd-1";
const ORG_ID = "org-1";

function makeUser(roles: string[]) {
  return {
    id: USER_ID,
    roles,
    orgId: ORG_ID,
    salesGroupId: null,
  };
}

function pickInFilter(
  filters: CapturedFilter[],
  column: string
): CapturedFilter | undefined {
  return filters.find(
    (f) => f.type === "in" && (f.args[0] as string) === column
  );
}

function pickOrFilter(filters: CapturedFilter[]): CapturedFilter | undefined {
  return filters.find((f) => f.type === "or");
}

describe("fetchAllChats — customs tier (Batch M row 12)", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
  });

  it("pure `customs` user: filters quotes by customs workflow stages, not assigned-items OR clause", async () => {
    const { fetchAllChats } = await import("../queries");

    await fetchAllChats(makeUser(["customs"]), "all");

    const inFilter = pickInFilter(
      fakeSupabase.quotesFilters,
      "workflow_status"
    );
    expect(
      inFilter,
      "expected .in('workflow_status', [...]) on the quotes query"
    ).toBeDefined();
    expect(inFilter!.args[1]).toEqual([
      "pending_customs",
      "pending_logistics_and_customs",
    ]);

    // And must NOT use the assigned-items OR clause (which would pin to 0
    // results because no per-user customs assignment exists).
    const orFilter = pickOrFilter(fakeSupabase.quotesFilters);
    expect(
      orFilter,
      "customs tier must not fall through to the assigned-items OR clause"
    ).toBeUndefined();
  });

  it("pure `head_of_customs` user: filters quotes by customs workflow stages", async () => {
    const { fetchAllChats } = await import("../queries");

    await fetchAllChats(makeUser(["head_of_customs"]), "all");

    const inFilter = pickInFilter(
      fakeSupabase.quotesFilters,
      "workflow_status"
    );
    expect(
      inFilter,
      "head_of_customs alone must be scoped to customs stage, not 'see all org'"
    ).toBeDefined();
    expect(inFilter!.args[1]).toEqual([
      "pending_customs",
      "pending_logistics_and_customs",
    ]);
  });

  it("dual-hat `customs + head_of_customs`: still scoped to customs workflow stages", async () => {
    // This is the actual МВЭД case: oleg.k@masterbearing.ru holds both
    // customs (operational) and head_of_customs (head tier). The combo must
    // route to the customs-stage filter, not the assigned-items branch.
    const { fetchAllChats } = await import("../queries");

    await fetchAllChats(makeUser(["customs", "head_of_customs"]), "all");

    const inFilter = pickInFilter(
      fakeSupabase.quotesFilters,
      "workflow_status"
    );
    expect(inFilter).toBeDefined();
    expect(inFilter!.args[1]).toEqual([
      "pending_customs",
      "pending_logistics_and_customs",
    ]);

    const orFilter = pickOrFilter(fakeSupabase.quotesFilters);
    expect(orFilter).toBeUndefined();
  });

  it("`head_of_customs + admin`: falls through to broad access (no workflow_status filter)", async () => {
    // Admin is in BROAD_QUOTE_ACCESS_ROLES, so the customs guard
    // (`!some(broad)`) excludes the user. Admin sees all org quotes.
    const { fetchAllChats } = await import("../queries");

    await fetchAllChats(makeUser(["head_of_customs", "admin"]), "all");

    const inFilter = pickInFilter(
      fakeSupabase.quotesFilters,
      "workflow_status"
    );
    expect(
      inFilter,
      "admin override must not pin user to customs stage"
    ).toBeUndefined();
  });

  it("pure `customs` user with matching quotes: returns those chats", async () => {
    // Sanity check: with the workflow_status filter in place, the supabase
    // mock returns whatever quote rows we configure — the function must
    // surface them as chat list items rather than collapsing to [].
    fakeSupabase.quoteRows = [
      {
        id: "quote-1",
        idn_quote: "Q-202605-0001",
        customer_id: null,
        created_by: "someone-else",
      },
    ];
    const { fetchAllChats } = await import("../queries");

    const chats = await fetchAllChats(makeUser(["customs"]), "all");

    expect(chats).toHaveLength(1);
    expect(chats[0].quoteId).toBe("quote-1");
    expect(chats[0].idnQuote).toBe("Q-202605-0001");
  });
});
