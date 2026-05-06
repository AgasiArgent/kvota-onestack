import { describe, expect, it, vi, beforeEach } from "vitest";

/**
 * Regression test for G1 (РОП-1, 2026-05-05): head_of_sales must be able
 * to open the customer detail page for any customer assigned to a member
 * of their sales group.
 *
 * Bug context:
 *   kravtsova.e@masterbearing.ru (head_of_sales, Группа Кравцовой) clicked
 *   on a customer that was assigned to her subordinate makarova.e@... and
 *   got the global 404 page.
 *
 * Root cause:
 *   `canAccessCustomer` defines the assigned-customers gate via
 *   `getAssignedCustomerIds`, which expands to all sales-group members
 *   only when given a `salesGroupId`. The customer detail page in
 *   `app/(app)/customers/[id]/page.tsx` was passing user.{id, roles, orgId}
 *   to `canAccessCustomer` WITHOUT `salesGroupId` — `salesGroupId` was
 *   resolved in parallel and never reached the access check. So РОП always
 *   fell through to the "just self" branch and never saw subordinate
 *   customers.
 *
 * Fix:
 *   Resolve `salesGroupId` BEFORE the `canAccessCustomer` call and forward
 *   it. The access function itself was already correct — this test guards
 *   the contract (head_of_sales + salesGroupId → can see group members'
 *   customers).
 */

type ChainResult<T> = { data: T | null };

/**
 * Mini Supabase test double that honours `.in("user_id", [...])` and
 * `.in("manager_id", [...])` filters. The real bug we're guarding against
 * is filter narrowness — fakes that ignore filters mask exactly the
 * privilege-escalation regressions this suite is here to catch.
 */
function makeFakeSupabase(rows: {
  customerAssigneesRows?: { customer_id: string; user_id: string }[];
  customersRows?: {
    id: string;
    manager_id?: string;
    organization_id?: string;
  }[];
  userProfilesRows?: {
    user_id: string;
    sales_group_id: string;
    organization_id: string;
  }[];
}) {
  return {
    from(table: string) {
      const filters: { col: string; values: string[] | string }[] = [];
      const builder = {
        select: vi.fn(() => builder),
        eq: vi.fn((col: string, value: string) => {
          filters.push({ col, values: value });
          return builder;
        }),
        in: vi.fn((col: string, values: string[]) => {
          filters.push({ col, values });
          return builder;
        }),
        is: vi.fn(() => builder),
        single: vi.fn(() => Promise.resolve({ data: null, error: null })),
        then(resolve: (r: ChainResult<unknown>) => unknown) {
          const matches = (
            row: Record<string, unknown>,
            f: { col: string; values: string[] | string }
          ) => {
            if (Array.isArray(f.values))
              return f.values.includes(row[f.col] as string);
            return row[f.col] === f.values;
          };
          if (table === "customer_assignees") {
            const data = (rows.customerAssigneesRows ?? []).filter((r) =>
              filters.every((f) => matches(r as Record<string, unknown>, f))
            );
            return Promise.resolve({ data }).then(resolve);
          }
          if (table === "customers") {
            const data = (rows.customersRows ?? []).filter((r) =>
              filters.every((f) => matches(r as Record<string, unknown>, f))
            );
            return Promise.resolve({ data }).then(resolve);
          }
          if (table === "user_profiles") {
            const data = (rows.userProfilesRows ?? []).filter((r) =>
              filters.every((f) => matches(r as Record<string, unknown>, f))
            );
            return Promise.resolve({ data }).then(resolve);
          }
          return Promise.resolve({ data: [] }).then(resolve);
        },
      };
      return builder;
    },
  };
}

let fakeSupabase: ReturnType<typeof makeFakeSupabase>;

vi.mock("@/shared/lib/supabase/server", () => ({
  createClient: async () => fakeSupabase,
  createAdminClient: () => fakeSupabase,
}));

describe("canAccessCustomer — head_of_sales group expansion (G1 regression)", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase({});
  });

  it("returns true when head_of_sales has the customer via a group member assignment", async () => {
    // Setup:
    //   user-1 (head_of_sales, sales_group_id = group-A, org-1)
    //   user-2 (sales) is in group-A, org-1
    //   customer-X is assigned to user-2 (not user-1)
    fakeSupabase = makeFakeSupabase({
      userProfilesRows: [
        {
          user_id: "user-1",
          sales_group_id: "group-A",
          organization_id: "org-1",
        },
        {
          user_id: "user-2",
          sales_group_id: "group-A",
          organization_id: "org-1",
        },
      ],
      customerAssigneesRows: [
        { customer_id: "customer-X", user_id: "user-2" },
      ],
      customersRows: [],
    });

    const { canAccessCustomer } = await import("../queries");
    const allowed = await canAccessCustomer("customer-X", {
      id: "user-1",
      roles: ["head_of_sales"],
      orgId: "org-1",
      salesGroupId: "group-A",
    });

    expect(allowed).toBe(true);
  });

  it("returns false when head_of_sales has no salesGroupId (the bug shape)", async () => {
    // The original failure mode: customer detail page passed no salesGroupId,
    // so resolveScopedUserIds collapsed to [user-1] only. user-1 is not the
    // direct assignee → access denied.
    fakeSupabase = makeFakeSupabase({
      userProfilesRows: [],
      customerAssigneesRows: [
        { customer_id: "customer-X", user_id: "user-2" }, // assigned to subordinate
      ],
      customersRows: [],
    });

    const { canAccessCustomer } = await import("../queries");
    const allowed = await canAccessCustomer("customer-X", {
      id: "user-1",
      roles: ["head_of_sales"],
      orgId: "org-1",
      // salesGroupId omitted ⇒ access narrowed to self
    });

    expect(allowed).toBe(false);
  });

  it("does NOT leak access across organizations", async () => {
    // user_profiles is filtered by organization_id — a head_of_sales in
    // org-1 with group-A cannot expand into a different org's customers
    // even if their group_id collides with another org's group naming.
    fakeSupabase = makeFakeSupabase({
      userProfilesRows: [
        // Same group-A, but in org-2 → must NOT expand into.
        {
          user_id: "user-foreign",
          sales_group_id: "group-A",
          organization_id: "org-2",
        },
      ],
      customerAssigneesRows: [
        { customer_id: "customer-foreign", user_id: "user-foreign" },
      ],
      customersRows: [],
    });

    const { canAccessCustomer } = await import("../queries");
    const allowed = await canAccessCustomer("customer-foreign", {
      id: "user-1",
      roles: ["head_of_sales"],
      orgId: "org-1", // querying as org-1
      salesGroupId: "group-A",
    });

    expect(allowed).toBe(false);
  });

  it("regular sales user still only sees own assigned customers (no privilege escalation)", async () => {
    // Critical regression guard: the fix only affects head_of_sales group
    // expansion. A regular `sales` user must NOT inherit group access.
    fakeSupabase = makeFakeSupabase({
      userProfilesRows: [
        {
          user_id: "user-1",
          sales_group_id: "group-A",
          organization_id: "org-1",
        },
        {
          user_id: "user-2",
          sales_group_id: "group-A",
          organization_id: "org-1",
        },
      ],
      customerAssigneesRows: [
        { customer_id: "customer-mine", user_id: "user-1" },
        { customer_id: "customer-other-mop", user_id: "user-2" },
      ],
      customersRows: [],
    });

    const { canAccessCustomer } = await import("../queries");

    // user-1 (regular sales, even with a salesGroupId provided) sees own
    const ownAccess = await canAccessCustomer("customer-mine", {
      id: "user-1",
      roles: ["sales"],
      orgId: "org-1",
      salesGroupId: "group-A",
    });
    expect(ownAccess).toBe(true);

    // user-1 must NOT see other group member's customer (different from РОП)
    const otherAccess = await canAccessCustomer("customer-other-mop", {
      id: "user-1",
      roles: ["sales"],
      orgId: "org-1",
      salesGroupId: "group-A",
    });
    expect(otherAccess).toBe(false);
  });

  it("non-sales roles bypass the gate entirely (admin, finance, etc.)", async () => {
    // Per access-control.md, FULL_VIEW_EDIT/FULL_VIEW_READONLY/FULL_SCOPED_EDIT
    // tiers see all customers in their org. canAccessCustomer short-circuits
    // for them via isSalesOnly === false.
    fakeSupabase = makeFakeSupabase({});

    const { canAccessCustomer } = await import("../queries");
    for (const role of ["admin", "finance", "top_manager", "quote_controller"]) {
      const allowed = await canAccessCustomer("any-customer", {
        id: "user-1",
        roles: [role],
        orgId: "org-1",
      });
      expect(allowed, `role=${role} should bypass the assigned gate`).toBe(true);
    }
  });
});
