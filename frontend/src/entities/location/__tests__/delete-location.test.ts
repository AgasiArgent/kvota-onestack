/**
 * Testing 2 row 77 — Server-action unit tests for `deleteLocation`.
 *
 * Locks the two-layer defense: scope check (org id) + FK pre-check across
 * every table that references kvota.locations. The action must
 *   - return `{ success: true }` when no FK row points at the location;
 *   - return `{ success: false, usage: [...] }` listing each referencing
 *     table when at least one row blocks the delete;
 *   - never call .delete() in the blocked path (no orphans, no leaks).
 *
 * FK table list mirrors migrations 029 / 167 / 288 / 309:
 *   - quote_items.pickup_location_id
 *   - supplier_invoices.pickup_location_id
 *   - logistics_route_segments.from_location_id / to_location_id
 *   - logistics_route_template_segments.from_location_id / to_location_id
 *
 * If a future migration adds another FK, the implementation's
 * LOCATION_REFERENCE_TABLES list will need widening — the «no FK rows»
 * happy path test still passes, but only because we mock every table
 * the implementation probes.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";

// ---------------------------------------------------------------------------
// Fake Supabase admin client capturing every probe + the final delete call
// ---------------------------------------------------------------------------

interface ProbeKey {
  table: string;
  column: string;
}

interface FakeSupabase {
  /** Whether the org-scoped locations row exists. */
  locationExists: boolean;
  /** Map of `${table}|${column}` → row count returned by count: "exact" probe. */
  fkCounts: Map<string, number>;
  /** Set when .delete() should report an error. */
  deleteError: Error | null;
  /** Captured probe calls — order matters for assertions on parallelism. */
  probes: ProbeKey[];
  /** True once .delete() has actually been chained through to a resolved eq(). */
  deleteCalled: boolean;
  /** Captured .eq() args on the delete chain. */
  deleteEqCalls: Array<[string, unknown]>;
  /** Captured .eq() args on the scope-check select. */
  scopeEqCalls: Array<[string, unknown]>;
  from: (table: string) => unknown;
}

let fakeSupabase: FakeSupabase;

function makeFakeSupabase(): FakeSupabase {
  const state: FakeSupabase = {
    locationExists: true,
    fkCounts: new Map(),
    deleteError: null,
    probes: [],
    deleteCalled: false,
    deleteEqCalls: [],
    scopeEqCalls: [],
    from(table: string) {
      return {
        // The scope check uses .select("id, organization_id") on locations;
        // every FK probe uses .select("id", { count: "exact", head: true })
        // on its respective table.
        select(_cols: string, opts?: { count?: string; head?: boolean }) {
          if (opts?.count === "exact") {
            // FK probe path: returns `{ count }` after the first .eq().
            const probeChain: Record<string, unknown> = {
              eq(col: string) {
                state.probes.push({ table, column: col });
                const key = `${table}|${col}`;
                const count = state.fkCounts.get(key) ?? 0;
                return Promise.resolve({ count });
              },
            };
            return probeChain;
          }
          // Scope-check path on locations: .eq().eq().limit().maybeSingle().
          const scopeChain: Record<string, unknown> = {
            eq(col: string, val: unknown) {
              state.scopeEqCalls.push([col, val]);
              return scopeChain;
            },
            limit() {
              return scopeChain;
            },
            maybeSingle: async () => {
              if (!state.locationExists) return { data: null, error: null };
              return {
                data: { id: "loc-1", organization_id: "org-1" },
                error: null,
              };
            },
          };
          return scopeChain;
        },
        delete() {
          const deleteChain: Record<string, unknown> = {
            eq(col: string, val: unknown) {
              state.deleteEqCalls.push([col, val]);
              state.deleteCalled = true;
              return Promise.resolve({ error: state.deleteError });
            },
          };
          return deleteChain;
        },
      };
    },
  };
  return state;
}

// ---------------------------------------------------------------------------
// Mocked modules — must be set up BEFORE importing server-actions
// ---------------------------------------------------------------------------

interface FakeSession {
  id: string;
  orgId: string | null;
  roles: string[];
}
let fakeSession: FakeSession | null = null;

vi.mock("@/shared/lib/supabase/server", () => ({
  createClient: () => fakeSupabase,
  createAdminClient: () => fakeSupabase,
}));

vi.mock("@/entities/user", () => ({
  getSessionUser: async () => fakeSession,
}));

vi.mock("@/shared/lib/roles", () => ({
  canCreateLocation: (roles: string[]) =>
    roles.includes("admin") ||
    roles.includes("head_of_logistics") ||
    roles.includes("head_of_customs"),
}));

vi.mock("next/cache", () => ({
  revalidatePath: vi.fn(),
}));

const { deleteLocation } = await import("../server-actions");

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("deleteLocation — auth + role gating", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
    fakeSession = { id: "u-1", orgId: "org-1", roles: ["admin"] };
  });

  it("rejects when unauthenticated (no session)", async () => {
    fakeSession = null;
    const res = await deleteLocation("loc-1");
    expect(res.success).toBe(false);
    expect(res.error).toBe("Unauthorized");
    expect(fakeSupabase.deleteCalled).toBe(false);
  });

  it("rejects when session has no orgId", async () => {
    fakeSession = { id: "u-1", orgId: null, roles: ["admin"] };
    const res = await deleteLocation("loc-1");
    expect(res.success).toBe(false);
    expect(res.error).toBe("Unauthorized");
    expect(fakeSupabase.deleteCalled).toBe(false);
  });

  it.each([["admin"], ["head_of_logistics"], ["head_of_customs"]])(
    "permits delete for %s",
    async (role) => {
      fakeSession = { id: "u-1", orgId: "org-1", roles: [role] };
      const res = await deleteLocation("loc-1");
      expect(res.success).toBe(true);
      expect(fakeSupabase.deleteCalled).toBe(true);
    },
  );

  it.each([
    ["sales"],
    ["procurement"],
    ["customs"],
    ["logistics"],
    ["finance"],
    ["head_of_sales"],
    ["head_of_procurement"],
  ])("rejects delete for %s", async (role) => {
    fakeSession = { id: "u-1", orgId: "org-1", roles: [role] };
    const res = await deleteLocation("loc-1");
    expect(res.success).toBe(false);
    expect(res.error).toBe("Нет прав на редактирование локаций");
    expect(fakeSupabase.deleteCalled).toBe(false);
  });
});

describe("deleteLocation — scope check", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
    fakeSession = { id: "u-1", orgId: "org-1", roles: ["admin"] };
  });

  it("returns «не найдена» when the row is not in caller's org", async () => {
    fakeSupabase.locationExists = false;
    const res = await deleteLocation("loc-99");
    expect(res.success).toBe(false);
    expect(res.error).toBe("Локация не найдена");
    expect(fakeSupabase.deleteCalled).toBe(false);
  });

  it("scopes the existence check by id + organization_id", async () => {
    await deleteLocation("loc-42");
    expect(fakeSupabase.scopeEqCalls).toEqual([
      ["id", "loc-42"],
      ["organization_id", "org-1"],
    ]);
  });
});

describe("deleteLocation — FK guard (blocks delete when used by КП)", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
    fakeSession = { id: "u-1", orgId: "org-1", roles: ["admin"] };
  });

  it("returns usage breakdown when location is used by quote_items", async () => {
    fakeSupabase.fkCounts.set("quote_items|pickup_location_id", 3);
    const res = await deleteLocation("loc-1");
    expect(res.success).toBe(false);
    expect(res.error).toBe("Локация используется и не может быть удалена");
    expect(res.usage).toEqual([{ label: "позиции КП", count: 3 }]);
    expect(fakeSupabase.deleteCalled).toBe(false);
  });

  it("returns usage breakdown when location is used by supplier_invoices", async () => {
    fakeSupabase.fkCounts.set("supplier_invoices|pickup_location_id", 2);
    const res = await deleteLocation("loc-1");
    expect(res.success).toBe(false);
    expect(res.usage).toEqual([{ label: "КП поставщиков", count: 2 }]);
    expect(fakeSupabase.deleteCalled).toBe(false);
  });

  it("returns usage breakdown when location is used by route segments (from)", async () => {
    fakeSupabase.fkCounts.set(
      "logistics_route_segments|from_location_id",
      1,
    );
    const res = await deleteLocation("loc-1");
    expect(res.success).toBe(false);
    expect(res.usage).toEqual([
      { label: "сегменты маршрутов (откуда)", count: 1 },
    ]);
  });

  it("returns usage breakdown when location is used by route segments (to)", async () => {
    fakeSupabase.fkCounts.set("logistics_route_segments|to_location_id", 4);
    const res = await deleteLocation("loc-1");
    expect(res.success).toBe(false);
    expect(res.usage).toEqual([
      { label: "сегменты маршрутов (куда)", count: 4 },
    ]);
  });

  it("aggregates multiple usage sources when several FK tables reference the location", async () => {
    fakeSupabase.fkCounts.set("quote_items|pickup_location_id", 3);
    fakeSupabase.fkCounts.set("supplier_invoices|pickup_location_id", 1);
    fakeSupabase.fkCounts.set("logistics_route_segments|to_location_id", 2);
    const res = await deleteLocation("loc-1");
    expect(res.success).toBe(false);
    expect(res.usage).toBeDefined();
    expect(res.usage).toHaveLength(3);
    // Order depends on Promise.all resolution; assert by content.
    const byLabel = new Map(res.usage!.map((u) => [u.label, u.count]));
    expect(byLabel.get("позиции КП")).toBe(3);
    expect(byLabel.get("КП поставщиков")).toBe(1);
    expect(byLabel.get("сегменты маршрутов (куда)")).toBe(2);
    expect(fakeSupabase.deleteCalled).toBe(false);
  });

  it("probes every known FK reference table (6 tables × 1 column each)", async () => {
    await deleteLocation("loc-1");
    const probedKeys = new Set(
      fakeSupabase.probes.map((p) => `${p.table}|${p.column}`),
    );
    expect(probedKeys).toEqual(
      new Set([
        "quote_items|pickup_location_id",
        "supplier_invoices|pickup_location_id",
        "logistics_route_segments|from_location_id",
        "logistics_route_segments|to_location_id",
        "logistics_route_template_segments|from_location_id",
        "logistics_route_template_segments|to_location_id",
      ]),
    );
  });
});

describe("deleteLocation — happy path", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
    fakeSession = { id: "u-1", orgId: "org-1", roles: ["admin"] };
  });

  it("deletes the row and returns success when no FK references exist", async () => {
    const res = await deleteLocation("loc-1");
    expect(res).toEqual({ success: true });
    expect(fakeSupabase.deleteCalled).toBe(true);
    expect(fakeSupabase.deleteEqCalls).toEqual([["id", "loc-1"]]);
  });

  it("propagates Supabase delete errors", async () => {
    fakeSupabase.deleteError = new Error("network down");
    const res = await deleteLocation("loc-1");
    expect(res.success).toBe(false);
    expect(res.error).toBe("network down");
  });
});
