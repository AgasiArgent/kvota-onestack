import { describe, expect, it, vi } from "vitest";

import { getAssignedCustomerIds } from "../access";

type ChainResult<T> = { data: T | null };

function makeSupabase(handlers: {
  customer_assignees?: ChainResult<{ customer_id: string }[]>;
  customers?: ChainResult<{ id: string }[]>;
  user_profiles?: ChainResult<{ user_id: string }[]>;
}) {
  return {
    from(table: string) {
      const builder = {
        select: vi.fn(() => builder),
        eq: vi.fn(() => builder),
        in: vi.fn(() => builder),
        is: vi.fn(() => builder),
        then(resolve: (r: ChainResult<unknown>) => unknown) {
          if (table === "customer_assignees") {
            return Promise.resolve(handlers.customer_assignees ?? { data: [] }).then(
              resolve
            );
          }
          if (table === "customers") {
            return Promise.resolve(handlers.customers ?? { data: [] }).then(resolve);
          }
          if (table === "user_profiles") {
            return Promise.resolve(handlers.user_profiles ?? { data: [] }).then(
              resolve
            );
          }
          return Promise.resolve({ data: [] }).then(resolve);
        },
      };
      return builder;
    },
  };
}

describe("getAssignedCustomerIds — broadened to include manager_id", () => {
  it("returns junction rows when only assignees exist", async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const supabase = makeSupabase({
      customer_assignees: { data: [{ customer_id: "cust-1" }, { customer_id: "cust-2" }] },
      customers: { data: [] },
    }) as any;

    const ids = await getAssignedCustomerIds(supabase, {
      id: "user-1",
      orgId: "org-1",
      roles: ["sales"],
    });

    expect(ids.sort()).toEqual(["cust-1", "cust-2"]);
  });

  it("returns manager_id rows even when no assignees exist", async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const supabase = makeSupabase({
      customer_assignees: { data: [] },
      customers: { data: [{ id: "cust-3" }] },
    }) as any;

    const ids = await getAssignedCustomerIds(supabase, {
      id: "user-1",
      orgId: "org-1",
      roles: ["sales"],
    });

    expect(ids).toEqual(["cust-3"]);
  });

  it("dedupes when a customer appears in both assignees and as manager", async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const supabase = makeSupabase({
      customer_assignees: { data: [{ customer_id: "cust-1" }] },
      customers: { data: [{ id: "cust-1" }] },
    }) as any;

    const ids = await getAssignedCustomerIds(supabase, {
      id: "user-1",
      orgId: "org-1",
      roles: ["sales"],
    });

    expect(ids).toEqual(["cust-1"]);
  });

  it("returns [] when neither source has rows", async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const supabase = makeSupabase({
      customer_assignees: { data: [] },
      customers: { data: [] },
    }) as any;

    const ids = await getAssignedCustomerIds(supabase, {
      id: "user-1",
      orgId: "org-1",
      roles: ["sales"],
    });

    expect(ids).toEqual([]);
  });
});
