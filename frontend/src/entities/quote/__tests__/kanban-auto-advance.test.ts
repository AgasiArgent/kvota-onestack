import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * Tests for the kanban auto-advance helper. Three triggers, three rules,
 * one helper. The DB layer is mocked via a fluent fake-supabase admin
 * client that records calls and replays scripted responses.
 */

vi.mock("@/shared/lib/supabase/server", () => ({
  createAdminClient: () => fakeAdmin,
}));

interface UpdateRecord {
  table: string;
  patch: Record<string, unknown>;
  filters: Record<string, unknown>;
  affected: number;
}

interface InsertRecord {
  table: string;
  row: Record<string, unknown>;
}

interface FakeAdmin {
  // Configurable response state
  substatusByKey: Record<string, string | null>;
  itemsByQuote: Record<string, Array<{
    id: string;
    brand: string | null;
    assigned_procurement_user: string | null;
    is_unavailable: boolean | null;
  }>>;
  coverageRows: Array<{
    quote_item_id: string;
    invoice_items: { invoices: { procurement_completed_at: string | null } };
  }>;
  failOnUpdate: boolean;
  updateAffectedRows: number;
  // Recorded calls
  updates: UpdateRecord[];
  inserts: InsertRecord[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  from(table: string): any;
}

let fakeAdmin: FakeAdmin;

function makeFakeAdmin(): FakeAdmin {
  const state: FakeAdmin = {
    substatusByKey: {},
    itemsByQuote: {},
    coverageRows: [],
    failOnUpdate: false,
    updateAffectedRows: 1,
    updates: [],
    inserts: [],
    from(table: string) {
      if (table === "quote_brand_substates") {
        return {
          select: () => ({
            eq: (col1: string, val1: string) => ({
              eq: (_col2: string, val2: string) => ({
                maybeSingle: async () => {
                  const key = `${val1}|${val2}`;
                  const sub = state.substatusByKey[key];
                  return sub
                    ? { data: { substatus: sub }, error: null }
                    : { data: null, error: null };
                },
              }),
            }),
          }),
          update: (patch: Record<string, unknown>) => ({
            eq: (col1: string, val1: string) => ({
              eq: (col2: string, val2: string) => ({
                eq: (col3: string, val3: string) => ({
                  select: () => {
                    const filters = {
                      [col1]: val1,
                      [col2]: val2,
                      [col3]: val3,
                    };
                    state.updates.push({
                      table,
                      patch,
                      filters,
                      affected: state.updateAffectedRows,
                    });
                    if (state.failOnUpdate) {
                      return Promise.resolve({
                        data: null,
                        error: new Error("update failed"),
                      });
                    }
                    if (state.updateAffectedRows === 0) {
                      return Promise.resolve({ data: [], error: null });
                    }
                    return Promise.resolve({
                      data: [
                        {
                          quote_id: val1,
                          brand: val2,
                          substatus: patch.substatus,
                        },
                      ],
                      error: null,
                    });
                  },
                }),
              }),
            }),
          }),
        };
      }
      if (table === "quote_items") {
        return {
          select: () => ({
            eq: (_col: string, val: string) => Promise.resolve({
              data: state.itemsByQuote[val] ?? [],
              error: null,
            }),
          }),
        };
      }
      if (table === "invoice_item_coverage") {
        return {
          select: () => ({
            in: () => Promise.resolve({
              data: state.coverageRows,
              error: null,
            }),
          }),
        };
      }
      if (table === "status_history") {
        return {
          insert: (row: Record<string, unknown>) => {
            state.inserts.push({ table, row });
            return Promise.resolve({ data: null, error: null });
          },
        };
      }
      throw new Error(`Unexpected table: ${table}`);
    },
  };
  return state;
}

describe("maybeAdvanceBrandSlices — distribution trigger", () => {
  beforeEach(() => {
    fakeAdmin = makeFakeAdmin();
  });

  it("advances when all items are routed (МОЗ assigned)", async () => {
    fakeAdmin.substatusByKey["q-1|ABB"] = "distributing";
    fakeAdmin.itemsByQuote["q-1"] = [
      { id: "i-1", brand: "ABB", assigned_procurement_user: "u-1", is_unavailable: false },
      { id: "i-2", brand: "ABB", assigned_procurement_user: "u-2", is_unavailable: false },
    ];
    const { maybeAdvanceBrandSlices } = await import("../kanban-auto-advance");
    const res = await maybeAdvanceBrandSlices({
      trigger: "distribution",
      slices: [{ quote_id: "q-1", brand: "ABB" }],
      userId: "actor",
    });
    expect(res.advanced).toEqual([
      { quote_id: "q-1", brand: "ABB", to: "searching_supplier" },
    ]);
    expect(fakeAdmin.updates[0].patch.substatus).toBe("searching_supplier");
    expect(fakeAdmin.inserts[0].row).toMatchObject({
      from_substatus: "distributing",
      to_substatus: "searching_supplier",
      transitioned_by: "actor",
    });
  });

  it("treats is_unavailable items as routed", async () => {
    fakeAdmin.substatusByKey["q-1|ABB"] = "distributing";
    fakeAdmin.itemsByQuote["q-1"] = [
      { id: "i-1", brand: "ABB", assigned_procurement_user: "u-1", is_unavailable: false },
      { id: "i-2", brand: "ABB", assigned_procurement_user: null, is_unavailable: true },
    ];
    const { maybeAdvanceBrandSlices } = await import("../kanban-auto-advance");
    const res = await maybeAdvanceBrandSlices({
      trigger: "distribution",
      slices: [{ quote_id: "q-1", brand: "ABB" }],
      userId: "actor",
    });
    expect(res.advanced).toHaveLength(1);
  });

  it("does NOT advance when one item lacks МОЗ", async () => {
    fakeAdmin.substatusByKey["q-1|ABB"] = "distributing";
    fakeAdmin.itemsByQuote["q-1"] = [
      { id: "i-1", brand: "ABB", assigned_procurement_user: "u-1", is_unavailable: false },
      { id: "i-2", brand: "ABB", assigned_procurement_user: null, is_unavailable: false },
    ];
    const { maybeAdvanceBrandSlices } = await import("../kanban-auto-advance");
    const res = await maybeAdvanceBrandSlices({
      trigger: "distribution",
      slices: [{ quote_id: "q-1", brand: "ABB" }],
      userId: "actor",
    });
    expect(res.advanced).toEqual([]);
    expect(fakeAdmin.updates).toHaveLength(0);
  });

  it("idempotent — does NOT advance when already past distributing", async () => {
    fakeAdmin.substatusByKey["q-1|ABB"] = "searching_supplier";
    fakeAdmin.itemsByQuote["q-1"] = [
      { id: "i-1", brand: "ABB", assigned_procurement_user: "u-1", is_unavailable: false },
    ];
    const { maybeAdvanceBrandSlices } = await import("../kanban-auto-advance");
    const res = await maybeAdvanceBrandSlices({
      trigger: "distribution",
      slices: [{ quote_id: "q-1", brand: "ABB" }],
      userId: "actor",
    });
    expect(res.advanced).toEqual([]);
  });

  it("only touches the requested brand in a multi-brand quote", async () => {
    fakeAdmin.substatusByKey["q-1|ABB"] = "distributing";
    fakeAdmin.substatusByKey["q-1|SKF"] = "distributing";
    fakeAdmin.itemsByQuote["q-1"] = [
      { id: "i-1", brand: "ABB", assigned_procurement_user: "u-1", is_unavailable: false },
      { id: "i-2", brand: "SKF", assigned_procurement_user: null, is_unavailable: false },
    ];
    const { maybeAdvanceBrandSlices } = await import("../kanban-auto-advance");
    const res = await maybeAdvanceBrandSlices({
      trigger: "distribution",
      slices: [
        { quote_id: "q-1", brand: "ABB" },
        { quote_id: "q-1", brand: "SKF" },
      ],
      userId: "actor",
    });
    expect(res.advanced).toEqual([
      { quote_id: "q-1", brand: "ABB", to: "searching_supplier" },
    ]);
  });

  it("dedupes repeated slices in the input", async () => {
    fakeAdmin.substatusByKey["q-1|ABB"] = "distributing";
    fakeAdmin.itemsByQuote["q-1"] = [
      { id: "i-1", brand: "ABB", assigned_procurement_user: "u-1", is_unavailable: false },
    ];
    const { maybeAdvanceBrandSlices } = await import("../kanban-auto-advance");
    await maybeAdvanceBrandSlices({
      trigger: "distribution",
      slices: [
        { quote_id: "q-1", brand: "ABB" },
        { quote_id: "q-1", brand: "ABB" },
      ],
      userId: "actor",
    });
    // One read, one update, one history insert — not two
    expect(fakeAdmin.updates).toHaveLength(1);
    expect(fakeAdmin.inserts).toHaveLength(1);
  });

  it("swallows DB update errors without throwing", async () => {
    fakeAdmin.substatusByKey["q-1|ABB"] = "distributing";
    fakeAdmin.itemsByQuote["q-1"] = [
      { id: "i-1", brand: "ABB", assigned_procurement_user: "u-1", is_unavailable: false },
    ];
    fakeAdmin.failOnUpdate = true;
    const { maybeAdvanceBrandSlices } = await import("../kanban-auto-advance");
    await expect(
      maybeAdvanceBrandSlices({
        trigger: "distribution",
        slices: [{ quote_id: "q-1", brand: "ABB" }],
        userId: "actor",
      })
    ).resolves.toEqual({ advanced: [] });
  });
});

describe("maybeAdvanceBrandSlices — send trigger", () => {
  beforeEach(() => {
    fakeAdmin = makeFakeAdmin();
  });

  it("advances searching_supplier → waiting_prices without item gate", async () => {
    fakeAdmin.substatusByKey["q-1|ABB"] = "searching_supplier";
    const { maybeAdvanceBrandSlices } = await import("../kanban-auto-advance");
    const res = await maybeAdvanceBrandSlices({
      trigger: "send",
      slices: [{ quote_id: "q-1", brand: "ABB" }],
      userId: "actor",
    });
    expect(res.advanced).toEqual([
      { quote_id: "q-1", brand: "ABB", to: "waiting_prices" },
    ]);
  });

  it("does NOT advance from distributing (wrong starting state)", async () => {
    fakeAdmin.substatusByKey["q-1|ABB"] = "distributing";
    const { maybeAdvanceBrandSlices } = await import("../kanban-auto-advance");
    const res = await maybeAdvanceBrandSlices({
      trigger: "send",
      slices: [{ quote_id: "q-1", brand: "ABB" }],
      userId: "actor",
    });
    expect(res.advanced).toEqual([]);
  });

  it("idempotent — does NOT advance from waiting_prices", async () => {
    fakeAdmin.substatusByKey["q-1|ABB"] = "waiting_prices";
    const { maybeAdvanceBrandSlices } = await import("../kanban-auto-advance");
    const res = await maybeAdvanceBrandSlices({
      trigger: "send",
      slices: [{ quote_id: "q-1", brand: "ABB" }],
      userId: "actor",
    });
    expect(res.advanced).toEqual([]);
  });
});

describe("maybeAdvanceBrandSlices — procurement_complete trigger", () => {
  beforeEach(() => {
    fakeAdmin = makeFakeAdmin();
  });

  it("advances waiting_prices → prices_ready when all non-unavailable items are covered by completed invoices", async () => {
    fakeAdmin.substatusByKey["q-1|ABB"] = "waiting_prices";
    fakeAdmin.itemsByQuote["q-1"] = [
      { id: "i-1", brand: "ABB", assigned_procurement_user: "u-1", is_unavailable: false },
      { id: "i-2", brand: "ABB", assigned_procurement_user: "u-1", is_unavailable: false },
    ];
    fakeAdmin.coverageRows = [
      {
        quote_item_id: "i-1",
        invoice_items: { invoices: { procurement_completed_at: "2026-04-30" } },
      },
      {
        quote_item_id: "i-2",
        invoice_items: { invoices: { procurement_completed_at: "2026-04-30" } },
      },
    ];
    const { maybeAdvanceBrandSlices } = await import("../kanban-auto-advance");
    const res = await maybeAdvanceBrandSlices({
      trigger: "procurement_complete",
      slices: [{ quote_id: "q-1", brand: "ABB" }],
      userId: "actor",
    });
    expect(res.advanced).toEqual([
      { quote_id: "q-1", brand: "ABB", to: "prices_ready" },
    ]);
  });

  it("does NOT advance when one item is in an uncompleted invoice", async () => {
    fakeAdmin.substatusByKey["q-1|ABB"] = "waiting_prices";
    fakeAdmin.itemsByQuote["q-1"] = [
      { id: "i-1", brand: "ABB", assigned_procurement_user: "u-1", is_unavailable: false },
      { id: "i-2", brand: "ABB", assigned_procurement_user: "u-1", is_unavailable: false },
    ];
    fakeAdmin.coverageRows = [
      {
        quote_item_id: "i-1",
        invoice_items: { invoices: { procurement_completed_at: "2026-04-30" } },
      },
      {
        quote_item_id: "i-2",
        invoice_items: { invoices: { procurement_completed_at: null } },
      },
    ];
    const { maybeAdvanceBrandSlices } = await import("../kanban-auto-advance");
    const res = await maybeAdvanceBrandSlices({
      trigger: "procurement_complete",
      slices: [{ quote_id: "q-1", brand: "ABB" }],
      userId: "actor",
    });
    expect(res.advanced).toEqual([]);
  });

  it("excludes is_unavailable items from coverage requirement", async () => {
    fakeAdmin.substatusByKey["q-1|ABB"] = "waiting_prices";
    fakeAdmin.itemsByQuote["q-1"] = [
      { id: "i-1", brand: "ABB", assigned_procurement_user: "u-1", is_unavailable: false },
      { id: "i-2", brand: "ABB", assigned_procurement_user: null, is_unavailable: true },
    ];
    fakeAdmin.coverageRows = [
      {
        quote_item_id: "i-1",
        invoice_items: { invoices: { procurement_completed_at: "2026-04-30" } },
      },
    ];
    const { maybeAdvanceBrandSlices } = await import("../kanban-auto-advance");
    const res = await maybeAdvanceBrandSlices({
      trigger: "procurement_complete",
      slices: [{ quote_id: "q-1", brand: "ABB" }],
      userId: "actor",
    });
    expect(res.advanced).toHaveLength(1);
  });

  it("idempotent — already prices_ready", async () => {
    fakeAdmin.substatusByKey["q-1|ABB"] = "prices_ready";
    const { maybeAdvanceBrandSlices } = await import("../kanban-auto-advance");
    const res = await maybeAdvanceBrandSlices({
      trigger: "procurement_complete",
      slices: [{ quote_id: "q-1", brand: "ABB" }],
      userId: "actor",
    });
    expect(res.advanced).toEqual([]);
  });
});
