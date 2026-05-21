/**
 * МОЗ-109..114 — Handsontable cell-click jumps to wrong row.
 *
 * Reproduction: on /quotes/{id}?step=procurement the user opens a КПП card
 * and clicks an editable cell. The selection lands on a row roughly 441px
 * ABOVE the click point (e.g. clicked at viewport y=1127.5, selection
 * landed at y=686). Six spreadsheet rows reported the same symptom — all
 * traced to the procurement-handsontable's parent layout.
 *
 * Root cause: the table sits inside a chain of sticky/scrollable parents:
 *
 *   QuoteDetailShell:    <div class="flex-1 ... overflow-y-auto">  (page scroll)
 *     ProcurementActionBar: <div class="sticky top-[52px] z-[5]">  (52+N px sticky)
 *     QuoteStickyHeader:    <div class="sticky top-0 z-10">         (top sticky)
 *     ...
 *     InvoiceCard:        <div class="overflow-x-auto">             (←HoT picks
 *       ProcurementHandsontable                                       this as
 *                                                                     scrollable)
 *
 * Handsontable's `getScrollableElement` walks up the DOM and returns the
 * first ancestor with overflow:auto/scroll on ANY axis (line 6033 of the
 * v17 dist). It picks the `overflow-x-auto` wrapper — but that element's
 * vertical scroll never moves. The user actually scrolls the OUTER
 * `overflow-y-auto`. HoT then renders the column header overlay relative
 * to the wrong scroll container, so the visual click→selection mapping is
 * shifted by exactly the outer container's scrollTop.
 *
 * Fix: pass `preventOverflow: 'horizontal'` to HoT. With this flag the TOP
 * overlay (column header) always uses the window as its scrollable element
 * regardless of intermediate `overflow-x-auto` parents (see line 24095 of
 * the dist — `preventOverflow === 'horizontal' && type === CLONE_TOP →
 * mainTableScrollableElement = rootWindow`).
 *
 * This regression test asserts that the prop is in place. We don't try to
 * jsdom-render the full Handsontable widget (jsdom doesn't implement layout,
 * so click-coordinate behavior can't be reproduced) — instead we capture
 * the props passed to `<HotTable />` and assert the config flag is set.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { renderToString } from "react-dom/server";
import { createElement } from "react";
import { cleanup, render } from "@testing-library/react";

// Capture every props bag passed to <HotTable />.
const hotTableCalls: Array<Record<string, unknown>> = [];

vi.mock("@handsontable/react", () => ({
  HotTable: (props: Record<string, unknown>) => {
    hotTableCalls.push(props);
    return null;
  },
}));

vi.mock("handsontable", () => ({
  default: {
    renderers: {
      NumericRenderer: () => {},
      TextRenderer: () => {},
    },
  },
  renderers: {
    NumericRenderer: () => {},
    TextRenderer: () => {},
  },
}));

vi.mock("handsontable/registry", () => ({
  registerAllModules: () => {},
}));
vi.mock("handsontable/styles/handsontable.css", () => ({}));
vi.mock("handsontable/styles/ht-theme-main.css", () => ({}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    refresh: () => {},
    push: () => {},
    replace: () => {},
    back: () => {},
    forward: () => {},
    prefetch: () => {},
  }),
}));

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    from: () => ({
      select: () => ({ eq: async () => ({ data: [], error: null }) }),
      update: () => ({ eq: async () => ({ data: null, error: null }) }),
    }),
  }),
}));

vi.mock("@/entities/quote/mutations", () => ({
  updateInvoiceItem: async () => ({}),
  unassignInvoiceItem: async () => ({}),
}));

vi.mock("sonner", () => ({
  toast: {
    success: () => {},
    error: () => {},
    info: () => {},
  },
}));

import { ProcurementHandsontable } from "../procurement-handsontable";

const sampleItem = {
  id: "ii-1",
  invoice_id: "inv-1",
  position: 1,
  product_name: "Test product",
  supplier_sku: "SKU-1",
  brand: "TestBrand",
  quantity: 10,
  purchase_price_original: 100,
  purchase_currency: "USD",
  minimum_order_quantity: 1,
  production_time_days: 7,
  weight_in_kg: 2,
  dimension_height_mm: 100,
  dimension_width_mm: 50,
  dimension_length_mm: 25,
};

describe("procurement-handsontable — cell-click coordinate offset (МОЗ-109..114)", () => {
  it("passes preventOverflow='horizontal' so column header sticky tracks window scroll, not the overflow-x-auto wrapper", () => {
    hotTableCalls.length = 0;

    renderToString(
      createElement(ProcurementHandsontable, {
        items: [sampleItem],
        invoiceId: "inv-1",
        procurementCompleted: false,
      })
    );

    expect(hotTableCalls.length).toBeGreaterThan(0);
    const props = hotTableCalls[0];
    // The fix is a single config flag. With `preventOverflow: 'horizontal'`
    // HoT v17 sets `mainTableScrollableElement = rootWindow` for the TOP
    // overlay (column header), bypassing the auto-detection that picks
    // up the parent `overflow-x-auto` wrapper as the scroll context.
    expect(props.preventOverflow).toBe("horizontal");
  });
});

/**
 * Testing 2 row 20 — «Таблица прыгает при сохранении данных в каждой ячейке».
 *
 * Symptom: every cell autosave on the КПП Handsontable triggered the parent
 * invoice-card to re-fetch invoice_items, which produced a new `items`
 * reference. The old `useMemo(..., [items, salesByItemId])` recomputed
 * `initialData` on each items change, handing a NEW array to `<HotTable />`.
 * The React wrapper forwarded it via `updateSettings({ data })` → HoT
 * internally calls `updateData` → datamap rebuild + `selection.refresh()`.
 * The user saw the table "jump" — scroll resets and selection clears mid-edit.
 *
 * Contract: when the user edits a single cell and the parent re-renders with
 * a fresh `items` reference of the SAME row IDs in the SAME order, the
 * reference handed to `<HotTable data={…} />` MUST stay the same. Value
 * updates flow into HoT through `setDataAtRowProp` instead (verified
 * separately by the in-place imperative-sync effect — jsdom can't observe
 * Handsontable internals here).
 */
describe("procurement-handsontable — autosave preserves scroll (Testing 2 row 20)", () => {
  afterEach(() => {
    cleanup();
    hotTableCalls.length = 0;
  });

  it("keeps the same `data` reference across re-renders when row IDs don't change (cell value autosave path)", () => {
    hotTableCalls.length = 0;

    // First render — initial mount.
    const { rerender } = render(
      createElement(ProcurementHandsontable, {
        items: [sampleItem],
        invoiceId: "inv-1",
        procurementCompleted: false,
      })
    );

    expect(hotTableCalls.length).toBeGreaterThan(0);
    const firstData = hotTableCalls[0].data;

    // Simulate the parent re-fetch path: same row, freshly-fetched item
    // object (different REFERENCE, but same `id` and a new value in one of
    // the editable cells — like the user just saved a new purchase price).
    const refreshedItem = { ...sampleItem, purchase_price_original: 123 };
    rerender(
      createElement(ProcurementHandsontable, {
        items: [refreshedItem],
        invoiceId: "inv-1",
        procurementCompleted: false,
      })
    );

    // Sanity — HotTable was re-rendered (componentDidUpdate ran).
    expect(hotTableCalls.length).toBeGreaterThan(1);

    // The fix: `data` MUST be the SAME array reference. If this fails,
    // HotTable's componentDidUpdate will call updateSettings({data}) which
    // triggers updateData → datamap rebuild → selection.refresh → scroll
    // jumps. Reference-equality is the load-bearing contract.
    const lastData = hotTableCalls[hotTableCalls.length - 1].data;
    expect(lastData).toBe(firstData);
  });

  it("hands a NEW `data` reference when row structure changes (split/merge/unassign path)", () => {
    hotTableCalls.length = 0;

    const itemA = { ...sampleItem, id: "ii-1" };
    const itemB = { ...sampleItem, id: "ii-2" };

    const { rerender } = render(
      createElement(ProcurementHandsontable, {
        items: [itemA, itemB],
        invoiceId: "inv-1",
        procurementCompleted: false,
      })
    );

    expect(hotTableCalls.length).toBeGreaterThan(0);
    const firstData = hotTableCalls[0].data;

    // Simulate a structural change — one row removed (unassign).
    rerender(
      createElement(ProcurementHandsontable, {
        items: [itemA],
        invoiceId: "inv-1",
        procurementCompleted: false,
      })
    );

    expect(hotTableCalls.length).toBeGreaterThan(1);
    const lastData = hotTableCalls[hotTableCalls.length - 1].data;

    // Reference MUST differ — HoT needs to reload its dataset. The visible
    // scroll reset on structural changes is acceptable; structural ops are
    // user-initiated (icon click) and rare compared to per-cell autosaves.
    expect(lastData).not.toBe(firstData);
  });

  /**
   * PR #190 reviewer F3-2 — the in-place imperative sync `useEffect`'s
   * dependency array is `[items, salesByItemId, quoteItemMetadataByItemId]`.
   * Adding/changing `quoteItemMetadataByItemId` between renders DOES fire
   * the effect (which patches cells via `setDataAtRowProp("external")`),
   * but it MUST NOT change the `data` reference handed to `<HotTable />`.
   *
   * `initialData` is memoized on `rowIdSignature` only (the row-id join key),
   * with the metadata read through a ref. If the wrong dep is ever added to
   * the `initialData` memo, the `data` reference would churn on every
   * metadata fetch from the parent — that's the exact scroll-reset symptom
   * the rowIdSignature fix was designed to prevent.
   */
  it("keeps the same `data` reference when `quoteItemMetadataByItemId` is added between renders (PR #190 F3-2)", () => {
    hotTableCalls.length = 0;

    // First render — no metadata yet (parent is still fetching the coverage
    // join that produces the metadata map).
    const { rerender } = render(
      createElement(ProcurementHandsontable, {
        items: [sampleItem],
        invoiceId: "inv-1",
        procurementCompleted: false,
      })
    );

    expect(hotTableCalls.length).toBeGreaterThan(0);
    const firstData = hotTableCalls[0].data;

    // Second render — metadata map arrives from the parent's async fetch.
    // Same row IDs, same order; only the metadata prop went from undefined
    // to a populated map. The data reference MUST stay stable.
    const metadataMap = {
      "ii-1": {
        quoteItemIds: ["qi-1"],
        supplier_payment_terms: "30% advance, 70% before shipment",
        advance_to_supplier_percent: 30,
      },
    };
    rerender(
      createElement(ProcurementHandsontable, {
        items: [sampleItem],
        invoiceId: "inv-1",
        procurementCompleted: false,
        quoteItemMetadataByItemId: metadataMap,
      })
    );

    expect(hotTableCalls.length).toBeGreaterThan(1);
    const lastData = hotTableCalls[hotTableCalls.length - 1].data;

    // Load-bearing: if `quoteItemMetadataByItemId` ever leaks into the
    // `initialData` memo's dep array, this assertion fails and the table
    // jumps on every metadata fetch.
    expect(lastData).toBe(firstData);
  });

  it("keeps the same `data` reference when `quoteItemMetadataByItemId` values change (autosave of % аванса / условия оплаты)", () => {
    hotTableCalls.length = 0;

    const initialMetadata = {
      "ii-1": {
        quoteItemIds: ["qi-1"],
        supplier_payment_terms: "30% advance, 70% before shipment",
        advance_to_supplier_percent: 30,
      },
    };

    // First render — table mounts with a populated metadata map.
    const { rerender } = render(
      createElement(ProcurementHandsontable, {
        items: [sampleItem],
        invoiceId: "inv-1",
        procurementCompleted: false,
        quoteItemMetadataByItemId: initialMetadata,
      })
    );

    expect(hotTableCalls.length).toBeGreaterThan(0);
    const firstData = hotTableCalls[0].data;

    // Second render — user just edited the % аванса cell. The parent
    // re-fetched and produced a new metadata map (different reference,
    // updated values) for the same row IDs in the same order. The data
    // reference handed to `<HotTable />` MUST stay stable; value updates
    // flow into HoT through the imperative `setDataAtRowProp` effect, not
    // by re-handing `data`.
    const updatedMetadata = {
      "ii-1": {
        quoteItemIds: ["qi-1"],
        supplier_payment_terms: "50% advance, 50% on delivery",
        advance_to_supplier_percent: 50,
      },
    };
    rerender(
      createElement(ProcurementHandsontable, {
        items: [sampleItem],
        invoiceId: "inv-1",
        procurementCompleted: false,
        quoteItemMetadataByItemId: updatedMetadata,
      })
    );

    expect(hotTableCalls.length).toBeGreaterThan(1);
    const lastData = hotTableCalls[hotTableCalls.length - 1].data;

    // Same guarantee as the row-20 autosave path — different prop reference,
    // same data array reference, no scroll reset.
    expect(lastData).toBe(firstData);
  });
});
