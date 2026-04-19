import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * Phase 5d Group 5 Appendix — Item 3 (CRITICAL save-path fix).
 *
 * After Task 14 (commit 8283a90), procurement-handsontable rows are sourced
 * from kvota.invoice_items. Their `id` is invoice_items.id. But the editor's
 * afterChange hook was still calling legacy `updateQuoteItem(rowId, ...)`
 * and `unassignItemFromInvoice(rowId)` — both targeting kvota.quote_items
 * WHERE id = rowId. Since rowId is an invoice_items.id, these writes matched
 * zero rows, producing silent save failures.
 *
 * This module adds the correct save-path mutations:
 *   - updateInvoiceItem(invoice_item_id, updates) → UPDATE kvota.invoice_items
 *   - unassignInvoiceItem(invoice_item_id) → DELETE kvota.invoice_items
 *       (cascades invoice_item_coverage) + clear composition pointer where
 *       the quote_item no longer has coverage in the original invoice.
 *
 * The legacy `updateQuoteItem` + `unassignItemFromInvoice` remain for callers
 * that legitimately operate on quote_items (sales + customs handsontables).
 */

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => fakeSupabase,
}));

interface FakeSupabase {
  // Data fixtures
  invoiceItemCoverage: Array<{
    invoice_item_id: string;
    quote_item_id: string;
    invoice_items: { invoice_id: string };
  }>;
  existingInvoiceItemsByInvoice: Record<string, string[]>; // invoice_id → invoice_item ids

  // Captured mutations
  wroteToTable: string[];
  invoiceItemsUpdates: Array<{ id: string; updates: Record<string, unknown> }>;
  invoiceItemsDeletedIds: string[];
  quoteItemsUpdates: Array<{ where: Record<string, unknown>; updates: Record<string, unknown> }>;

  // Guards against regression
  wroteUpdatesToQuoteItems: boolean;

  from(table: string): unknown;
}

let fakeSupabase: FakeSupabase;

function makeFakeSupabase(): FakeSupabase {
  const state: FakeSupabase = {
    invoiceItemCoverage: [],
    existingInvoiceItemsByInvoice: {},
    wroteToTable: [],
    invoiceItemsUpdates: [],
    invoiceItemsDeletedIds: [],
    quoteItemsUpdates: [],
    wroteUpdatesToQuoteItems: false,
    from(table: string) {
      state.wroteToTable.push(table);
      if (table === "invoice_items") {
        return {
          update: (updates: Record<string, unknown>) => ({
            eq: (_col: string, id: string) => ({
              select: () => ({
                single: async () => {
                  state.invoiceItemsUpdates.push({ id, updates });
                  return { data: { id, ...updates }, error: null };
                },
              }),
            }),
          }),
          delete: () => ({
            eq: async (_col: string, id: string) => {
              state.invoiceItemsDeletedIds.push(id);
              // Simulate ON DELETE CASCADE: drop coverage rows for this
              // invoice_item so the follow-up "remaining coverage" check
              // sees the real post-delete state.
              state.invoiceItemCoverage = state.invoiceItemCoverage.filter(
                (r) => r.invoice_item_id !== id
              );
              return { error: null };
            },
          }),
        };
      }
      if (table === "invoice_item_coverage") {
        return {
          select: (_cols: string) => ({
            eq: (_col: string, iiId: string) => ({
              // Used by unassignInvoiceItem to find which quote_items are
              // covered by this invoice_item, and in which invoice.
              then: async (resolve: (v: { data: unknown; error: null }) => void) => {
                const rows = state.invoiceItemCoverage.filter(
                  (r) => r.invoice_item_id === iiId
                );
                resolve({ data: rows, error: null });
              },
            }),
            in: async (_col: string, qiIds: string[]) => {
              // Used to check remaining coverage after deletion.
              const rows = state.invoiceItemCoverage.filter((r) =>
                qiIds.includes(r.quote_item_id)
              );
              return { data: rows, error: null };
            },
          }),
        };
      }
      if (table === "quote_items") {
        return {
          update: (updates: Record<string, unknown>) => {
            state.wroteUpdatesToQuoteItems = true;
            return {
              eq: async (_col: string, qiId: string) => {
                state.quoteItemsUpdates.push({
                  where: { id: qiId },
                  updates,
                });
                return { error: null };
              },
              in: async (_col: string, qiIds: string[]) => {
                state.quoteItemsUpdates.push({
                  where: { ids: qiIds },
                  updates,
                });
                return { error: null };
              },
            };
          },
        };
      }
      throw new Error(`Unexpected table: ${table}`);
    },
  };
  return state;
}

describe("updateInvoiceItem — writes to kvota.invoice_items, not quote_items", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
  });

  it("updates kvota.invoice_items WHERE id = invoiceItemId", async () => {
    const { updateInvoiceItem } = await import("../mutations");
    await updateInvoiceItem("ii-1", {
      purchase_price_original: 42.5,
      purchase_currency: "USD",
    });

    expect(fakeSupabase.invoiceItemsUpdates).toHaveLength(1);
    expect(fakeSupabase.invoiceItemsUpdates[0].id).toBe("ii-1");
    expect(fakeSupabase.invoiceItemsUpdates[0].updates).toEqual({
      purchase_price_original: 42.5,
      purchase_currency: "USD",
    });
  });

  it("never writes updates to quote_items (legacy mistake)", async () => {
    const { updateInvoiceItem } = await import("../mutations");
    await updateInvoiceItem("ii-1", { weight_in_kg: 5.5 });

    expect(fakeSupabase.wroteUpdatesToQuoteItems).toBe(false);
  });
});

describe("unassignInvoiceItem — deletes invoice_item and manages composition pointer", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
  });

  it("deletes the invoice_item row (cascades invoice_item_coverage)", async () => {
    fakeSupabase.invoiceItemCoverage = [
      {
        invoice_item_id: "ii-1",
        quote_item_id: "qi-1",
        invoice_items: { invoice_id: "inv-A" },
      },
    ];

    const { unassignInvoiceItem } = await import("../mutations");
    await unassignInvoiceItem("ii-1");

    expect(fakeSupabase.invoiceItemsDeletedIds).toContain("ii-1");
  });

  it("clears quote_items.composition_selected_invoice_id when no other coverage remains in that invoice", async () => {
    // Single 1:1 coverage in inv-A: after deleting ii-1 the quote_item no
    // longer has any coverage in inv-A → pointer must reset.
    fakeSupabase.invoiceItemCoverage = [
      {
        invoice_item_id: "ii-1",
        quote_item_id: "qi-1",
        invoice_items: { invoice_id: "inv-A" },
      },
    ];

    const { unassignInvoiceItem } = await import("../mutations");
    await unassignInvoiceItem("ii-1");

    // Expect pointer cleared for qi-1 where composition_selected_invoice_id
    // currently = inv-A.
    const clearUpdate = fakeSupabase.quoteItemsUpdates.find(
      (u) => u.updates.composition_selected_invoice_id === null
    );
    expect(clearUpdate).toBeDefined();
  });

  it("does not write to quote_items at all when coverage fetch is empty (orphan invoice_item)", async () => {
    // No coverage rows for ii-orphan → delete the row, nothing else to do.
    fakeSupabase.invoiceItemCoverage = [];

    const { unassignInvoiceItem } = await import("../mutations");
    await unassignInvoiceItem("ii-orphan");

    expect(fakeSupabase.invoiceItemsDeletedIds).toContain("ii-orphan");
    expect(fakeSupabase.quoteItemsUpdates).toHaveLength(0);
  });
});
