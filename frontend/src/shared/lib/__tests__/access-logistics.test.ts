import { describe, expect, it, vi } from "vitest";

import { getAssignedQuoteIds } from "../access";

type ChainResult<T> = { data: T | null };

/**
 * Builds a Supabase-shaped mock whose chain methods return the same builder
 * (so `.from(...).select(...).eq(...).is(...)` is awaitable). The terminal
 * `then` resolves with the per-table data the test supplies.
 */
function makeSupabase(handlers: {
  quotes?: ChainResult<{ id: string }[]>;
  invoices?: ChainResult<{ quote_id: string | null }[]>;
  quote_items?: ChainResult<{ quote_id: string | null }[]>;
}) {
  return {
    from(table: string) {
      const builder = {
        select: vi.fn(() => builder),
        eq: vi.fn(() => builder),
        in: vi.fn(() => builder),
        is: vi.fn(() => builder),
        then(resolve: (r: ChainResult<unknown>) => unknown) {
          if (table === "quotes") {
            return Promise.resolve(handlers.quotes ?? { data: [] }).then(resolve);
          }
          if (table === "invoices") {
            return Promise.resolve(handlers.invoices ?? { data: [] }).then(resolve);
          }
          if (table === "quote_items") {
            return Promise.resolve(handlers.quote_items ?? { data: [] }).then(resolve);
          }
          return Promise.resolve({ data: [] }).then(resolve);
        },
      };
      return builder;
    },
  };
}

describe("getAssignedQuoteIds — logistics tier (Testing 2 rows 76+78)", () => {
  it("returns invoice-assigned quotes when the legacy quote-level column is null", async () => {
    // Regression: МОЛ (milana.d@masterbearing.ru) was assigned to КП at
    // invoice-level only — quotes.assigned_logistics_user was NULL — so the
    // helper returned [] and /quotes showed «Всего: 0».
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const supabase = makeSupabase({
      quotes: { data: [] },
      invoices: { data: [{ quote_id: "quote-from-invoice" }] },
    }) as any;

    const ids = await getAssignedQuoteIds(supabase, {
      id: "logistics-user-1",
      orgId: "org-1",
      roles: ["logistics"],
    });

    expect(ids).toEqual(["quote-from-invoice"]);
  });

  it("dedupes quote IDs across legacy quote-level and per-invoice sources", async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const supabase = makeSupabase({
      quotes: { data: [{ id: "quote-shared" }] },
      invoices: { data: [{ quote_id: "quote-shared" }] },
    }) as any;

    const ids = await getAssignedQuoteIds(supabase, {
      id: "logistics-user-1",
      orgId: "org-1",
      roles: ["logistics"],
    });

    expect(ids).toEqual(["quote-shared"]);
  });

  it("unions both sources when each contributes distinct quotes", async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const supabase = makeSupabase({
      quotes: { data: [{ id: "quote-legacy" }] },
      invoices: { data: [{ quote_id: "quote-invoice" }] },
    }) as any;

    const ids = await getAssignedQuoteIds(supabase, {
      id: "logistics-user-1",
      orgId: "org-1",
      roles: ["logistics"],
    });

    expect(ids.sort()).toEqual(["quote-invoice", "quote-legacy"]);
  });

  it("returns [] when the user has no assignments on either source", async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const supabase = makeSupabase({
      quotes: { data: [] },
      invoices: { data: [] },
    }) as any;

    const ids = await getAssignedQuoteIds(supabase, {
      id: "logistics-user-1",
      orgId: "org-1",
      roles: ["logistics"],
    });

    expect(ids).toEqual([]);
  });

  it("skips null invoice.quote_id rows (defensive guard against FK gaps)", async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const supabase = makeSupabase({
      quotes: { data: [] },
      invoices: {
        data: [
          { quote_id: "quote-real" },
          { quote_id: null },
        ],
      },
    }) as any;

    const ids = await getAssignedQuoteIds(supabase, {
      id: "logistics-user-1",
      orgId: "org-1",
      roles: ["logistics"],
    });

    expect(ids).toEqual(["quote-real"]);
  });

  it("does not query invoices for procurement-only users", async () => {
    // procurement role goes through quote_items, not invoices — the invoices
    // table should not be queried at all for that role. We assert this by
    // returning a poison value from invoices and confirming it is ignored.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const supabase = makeSupabase({
      quote_items: { data: [{ quote_id: "quote-proc" }] },
      invoices: { data: [{ quote_id: "POISON-should-not-appear" }] },
    }) as any;

    const ids = await getAssignedQuoteIds(supabase, {
      id: "proc-user-1",
      orgId: "org-1",
      roles: ["procurement"],
    });

    expect(ids).toEqual(["quote-proc"]);
  });

  it("combines procurement (quote_items) + logistics (invoices + quotes) for dual-role users", async () => {
    // A user with both roles should see the union of all three sources.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const supabase = makeSupabase({
      quote_items: { data: [{ quote_id: "quote-proc" }] },
      quotes: { data: [{ id: "quote-legacy" }] },
      invoices: { data: [{ quote_id: "quote-invoice" }] },
    }) as any;

    const ids = await getAssignedQuoteIds(supabase, {
      id: "multi-user-1",
      orgId: "org-1",
      roles: ["procurement", "logistics"],
    });

    expect(ids.sort()).toEqual(["quote-invoice", "quote-legacy", "quote-proc"]);
  });
});
