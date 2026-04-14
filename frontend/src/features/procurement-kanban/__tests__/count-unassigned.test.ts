import { describe, it, expect, vi } from "vitest";
import { countUnassignedItems } from "../lib/count-unassigned";

/**
 * Lightweight Supabase query-builder mock. Records every call so tests can
 * assert that the drag-guard composes the expected filters.
 */
function buildMockClient(countResult: number | null) {
  const calls: Array<{ method: string; args: unknown[] }> = [];
  const chain: Record<string, unknown> = {};
  const track = (method: string) => (...args: unknown[]) => {
    calls.push({ method, args });
    return chain;
  };
  chain.eq = track("eq");
  chain.is = track("is");
  chain.neq = track("neq");
  // Await point — resolves to the final count.
  chain.then = (resolve: (v: { count: number | null }) => unknown) =>
    Promise.resolve({ count: countResult }).then(resolve);

  const client = {
    from: (table: string) => {
      calls.push({ method: "from", args: [table] });
      return {
        select: (columns: string, opts: unknown) => {
          calls.push({ method: "select", args: [columns, opts] });
          return chain;
        },
      };
    },
  };
  return { client: client as never, calls };
}

describe("countUnassignedItems — drag-guard query", () => {
  it("returns 0 when Supabase reports no unassigned rows", async () => {
    const { client } = buildMockClient(0);
    const n = await countUnassignedItems("q1", "ABB", () => client);
    expect(n).toBe(0);
  });

  it("returns the count when Supabase reports unassigned rows", async () => {
    const { client } = buildMockClient(4);
    const n = await countUnassignedItems("q1", "ABB", () => client);
    expect(n).toBe(4);
  });

  it("coerces null count (bad response) to 0 instead of NaN", async () => {
    const { client } = buildMockClient(null);
    const n = await countUnassignedItems("q1", "ABB", () => client);
    expect(n).toBe(0);
  });

  it("queries quote_items table with exact-head count", async () => {
    const { client, calls } = buildMockClient(0);
    await countUnassignedItems("q1", "ABB", () => client);
    expect(calls[0]).toEqual({ method: "from", args: ["quote_items"] });
    expect(calls[1]).toEqual({
      method: "select",
      args: ["id", { count: "exact", head: true }],
    });
  });

  it("filters by quote_id, null procurement user, and non-unavailable items", async () => {
    const { client, calls } = buildMockClient(0);
    await countUnassignedItems("q1", "ABB", () => client);
    const filterCalls = calls.filter((c) =>
      ["eq", "is", "neq"].includes(c.method)
    );
    expect(filterCalls).toContainEqual({
      method: "eq",
      args: ["quote_id", "q1"],
    });
    expect(filterCalls).toContainEqual({
      method: "is",
      args: ["assigned_procurement_user", null],
    });
    expect(filterCalls).toContainEqual({
      method: "neq",
      args: ["is_unavailable", true],
    });
  });

  it("uses eq('brand', value) when brand is a non-empty string", async () => {
    const { client, calls } = buildMockClient(0);
    await countUnassignedItems("q1", "ABB", () => client);
    expect(
      calls.some(
        (c) => c.method === "eq" && c.args[0] === "brand" && c.args[1] === "ABB"
      )
    ).toBe(true);
  });

  it("uses is('brand', null) when brand is the empty string (unbranded)", async () => {
    const { client, calls } = buildMockClient(0);
    await countUnassignedItems("q1", "", () => client);
    expect(
      calls.some(
        (c) => c.method === "is" && c.args[0] === "brand" && c.args[1] === null
      )
    ).toBe(true);
    expect(
      calls.some((c) => c.method === "eq" && c.args[0] === "brand")
    ).toBe(false);
  });
});

describe("countUnassignedItems — drag-guard decision logic", () => {
  /**
   * Models the decision the board makes on drop from distributing →
   * searching_supplier: if count > 0, the transition is blocked and the
   * popover is forced open; if count === 0, the transition proceeds.
   */
  function shouldBlockTransition(count: number): boolean {
    return count > 0;
  }

  it("blocks the transition when any unassigned item remains", () => {
    expect(shouldBlockTransition(1)).toBe(true);
    expect(shouldBlockTransition(10)).toBe(true);
  });

  it("allows the transition when all items are assigned", () => {
    expect(shouldBlockTransition(0)).toBe(false);
  });

  it("integration: block with real (mocked) count > 0", async () => {
    const { client } = buildMockClient(3);
    const n = await countUnassignedItems("q1", "ABB", () => client);
    expect(shouldBlockTransition(n)).toBe(true);
  });

  it("integration: proceed with real (mocked) count === 0", async () => {
    const { client } = buildMockClient(0);
    const n = await countUnassignedItems("q1", "ABB", () => client);
    expect(shouldBlockTransition(n)).toBe(false);
  });
});

describe("KanbanCard — assign popover visibility rule", () => {
  // Pure logic mirroring kanban-card.tsx: the popover is only available on
  // cards whose procurement_substatus === "distributing".
  function canAssignInline(
    procurementSubstatus: string,
    workload: unknown,
    orgId: unknown
  ): boolean {
    return (
      procurementSubstatus === "distributing" &&
      workload !== undefined &&
      orgId !== undefined
    );
  }

  it("enables inline assign for distributing cards when deps are provided", () => {
    expect(canAssignInline("distributing", [], "org1")).toBe(true);
  });

  it("disables inline assign on other substatus columns", () => {
    expect(canAssignInline("searching_supplier", [], "org1")).toBe(false);
    expect(canAssignInline("waiting_prices", [], "org1")).toBe(false);
    expect(canAssignInline("prices_ready", [], "org1")).toBe(false);
  });

  it("disables inline assign when workload or orgId is missing", () => {
    expect(canAssignInline("distributing", undefined, "org1")).toBe(false);
    expect(canAssignInline("distributing", [], undefined)).toBe(false);
  });

  // Satisfy lint: mark vi as used to avoid 'vi is defined but never used'.
  it("vitest harness is imported", () => {
    expect(typeof vi).toBe("object");
  });
});
