"use client";

import { useRef, useCallback, useMemo, useEffect } from "react";
import { useRouter } from "next/navigation";
import { HotTable } from "@handsontable/react";
import { registerAllModules } from "handsontable/registry";
import Handsontable from "handsontable";
import { toast } from "sonner";
import { extractErrorMessage } from "@/shared/lib/errors";
import { updateInvoiceItem, unassignInvoiceItem } from "@/entities/quote/mutations";
import { isMoqViolation } from "./moq-warning";

import "handsontable/styles/handsontable.css";
import "handsontable/styles/ht-theme-main.css";

registerAllModules();

/**
 * Phase 5d Group 5 Appendix — supplier-side row shape bound by the editor.
 *
 * Mirrors the `kvota.invoice_items` columns the handsontable COLUMN_KEYS
 * read. Declared locally (and re-exported via `procurement-items-editor`)
 * so callers can type their rows without reaching into the handsontable
 * internals.
 */
export interface ProcurementEditorItem {
  id: string;
  invoice_id: string;
  position: number;
  product_name: string;
  supplier_sku: string | null;
  brand: string | null;
  quantity: number;
  purchase_price_original: number | null;
  purchase_currency: string;
  minimum_order_quantity: number | null;
  production_time_days: number | null;
  weight_in_kg: number | null;
  dimension_height_mm: number | null;
  dimension_width_mm: number | null;
  dimension_length_mm: number | null;
}

/**
 * Phase 5d Task 14 — column keys rebound to `invoice_items` schema.
 *
 * Post-migration 284 drops the following from `quote_items`:
 *   purchase_price_original, weight_in_kg, production_time_days,
 *   minimum_order_quantity, dimension_*_mm
 * The editor therefore binds these supplier-side keys to `invoice_items`.
 * Customer-side columns (product_code, manufacturer_product_name, name_en,
 * is_unavailable, supplier_sku_note) remain on quote_items but are NOT
 * exposed through this editor — the handsontable is supplier-side only.
 */
export const PROCUREMENT_COLUMN_KEYS = [
  "brand",
  "supplier_sku",
  "product_name",
  "quantity",
  "minimum_order_quantity",
  "purchase_price_original",
  "production_time_days",
  "weight_in_kg",
  "dimensions",
] as const;

// Back-compat alias for internal array math.
const COLUMN_KEYS = PROCUREMENT_COLUMN_KEYS;

interface RowData {
  id: string;
  brand: string;
  // Sales-side display columns joined from quote_items via
  // invoice_item_coverage. Read-only — procurement sees what sales recorded
  // alongside their own supplier-side fields.
  sales_product_code: string;
  sales_product_name: string;
  /** Unit of measure (Ед. Изм) joined from quote_items.unit. Read-only. */
  sales_unit: string;
  supplier_sku: string;
  product_name: string;
  quantity: number | null;
  minimum_order_quantity: number | null;
  purchase_price_original: number | null;
  purchase_currency: string;
  production_time_days: number | null;
  weight_in_kg: number | null;
  dimensions: string;
}

function formatDimensions(
  height: number | null | undefined,
  width: number | null | undefined,
  length: number | null | undefined
): string {
  if (height == null && width == null && length == null) return "";
  return `${height ?? 0}\u00D7${width ?? 0}\u00D7${length ?? 0}`;
}

function parseDimensions(
  value: string
): { height: number | null; width: number | null; length: number | null } {
  if (!value || !value.trim()) {
    return { height: null, width: null, length: null };
  }
  // Accept "H\u00D7W\u00D7L", "HxWxL", "H*W*L", "H W L"
  const parts = value.split(/[\u00D7xX*\s]+/).map((p) => {
    const n = parseFloat(p.trim());
    return isNaN(n) ? null : n;
  });
  return {
    height: parts[0] ?? null,
    width: parts[1] ?? null,
    length: parts[2] ?? null,
  };
}

/**
 * Phase 5d Group 5 Appendix: rows are sourced from `invoice_items` (the
 * supplier side of the КП). The `items` prop is typed to the supplier-side
 * row shape so callers cannot accidentally pass customer-side quote_items.
 *
 * Fields read from the row map 1:1 onto `invoice_items` columns:
 *   brand, supplier_sku, product_name, quantity, purchase_price_original,
 *   purchase_currency, production_time_days, weight_in_kg,
 *   dimension_*_mm, minimum_order_quantity
 */
function itemToRow(
  item: ProcurementEditorItem,
  sales:
    | { product_code: string; product_name: string; unit: string }
    | undefined
): RowData {
  // Manufacturer-substitution semantics: "Артикул производителя" /
  // "Наименование производителя" are filled by procurement ONLY when the
  // supplier replies with a substitute (e.g., the requested product was
  // discontinued and replaced with a different SKU/name). Downstream
  // consumers (calc engine, exports, KP letters) fall back to the sales
  // fields when these are blank.
  //
  // The DB copies quote_items.product_name into invoice_items.product_name
  // at assignment time (NOT NULL constraint forces a value). To honor the
  // user-facing "blank until substituted" semantic, we display the
  // supplier copy as empty whenever it still matches the joined sales
  // source. As soon as procurement edits the cell to anything different,
  // the substituted value surfaces. Same idea for supplier_sku — though
  // that field is nullable and typically already blank by default.
  const supplierProductName =
    sales && item.product_name === sales.product_name
      ? ""
      : item.product_name ?? "";
  const supplierSku =
    sales && item.supplier_sku && item.supplier_sku === sales.product_code
      ? ""
      : item.supplier_sku ?? "";

  return {
    id: item.id,
    brand: item.brand ?? "",
    sales_product_code: sales?.product_code ?? "",
    sales_product_name: sales?.product_name ?? "",
    sales_unit: sales?.unit ?? "",
    supplier_sku: supplierSku,
    product_name: supplierProductName,
    quantity: item.quantity,
    minimum_order_quantity: item.minimum_order_quantity ?? null,
    purchase_price_original: item.purchase_price_original ?? null,
    purchase_currency: item.purchase_currency ?? "",
    production_time_days: item.production_time_days ?? null,
    weight_in_kg: item.weight_in_kg ?? null,
    dimensions: formatDimensions(
      item.dimension_height_mm,
      item.dimension_width_mm,
      item.dimension_length_mm
    ),
  };
}

interface ProcurementHandsontableProps {
  items: ProcurementEditorItem[];
  invoiceId: string;
  procurementCompleted: boolean;
  salesByItemId?: Record<
    string,
    { product_code: string; product_name: string; unit: string }
  >;
  /**
   * Per-row eligibility for the inline split action. Indexed by
   * invoice_item.id. Rows present in this map render a "↧" split icon next
   * to the unassign button; rows missing from it don't.
   */
  splitableByItemId?: Record<
    string,
    {
      sourceQuoteItemId: string;
      sourceQuantity: number;
      sourceProductName: string;
    }
  >;
  /**
   * Per-row "this is a split child" info. Indexed by invoice_item.id. Rows
   * present in this map render a "↪" undo-split icon (clicking it
   * collapses the entire split back to a 1:1 row).
   */
  splitChildByItemId?: Record<
    string,
    { sourceQuoteItemId: string; sourceProductName: string }
  >;
  /**
   * Per-row merge eligibility. Indexed by invoice_item.id. Rows present in
   * this map render a "⋃" merge icon (clicking it opens MergeInlineDialog
   * with this row pre-selected as the initiator).
   */
  mergeableByItemId?: Record<
    string,
    {
      sourceQuoteItemId: string;
      sourceProductName: string;
      sourceQuantity: number;
    }
  >;
  /**
   * Per-row "this is a merge result" map. Indexed by invoice_item.id.
   * Drives the inline ↩ undo-merge icon (clicking it splits the merged
   * row back into its N source 1:1 invoice_items).
   */
  mergeResultByItemId?: Record<string, true>;
  /** Fired when the user clicks the row's split icon. */
  onSplitRow?: (invoiceItemId: string) => void;
  /** Fired when the user clicks the row's undo-split icon. */
  onUndoSplitRow?: (invoiceItemId: string) => void;
  /** Fired when the user clicks the row's merge icon. */
  onMergeRow?: (invoiceItemId: string) => void;
  /** Fired when the user clicks the row's undo-merge icon. */
  onUndoMergeRow?: (invoiceItemId: string) => void;
  /**
   * Fired after a successful inline edit / unassign. The parent invoice-card
   * uses this to bump its local refreshKey so the supabase-backed
   * ``invoice_items`` useEffect re-fires — ``router.refresh()`` alone
   * does not retrigger client-side effects keyed on stable
   * ``invoice.id``. См. МОЗ Тест 2026-05-01 fail #91 + Notes 92, 128,
   * 140-142 (one cluster of "изменения только после reload" symptoms).
   */
  onMutated?: () => void;
}

/**
 * Module-scoped singleton tooltip manager for the Handsontable action icons.
 *
 * Earlier the row renderer attached a per-button closure over a tooltip
 * element appended to `document.body`. When Handsontable re-rendered a cell
 * mid-hover (data updates, sort, scroll virtualisation) the trigger was
 * detached from the DOM but `mouseleave` never fired — so the cleanup
 * branch in the closure never ran and the tooltip stayed orphaned in
 * `<body>` indefinitely. Each subsequent hover compounded the leak.
 *
 * One reused element + a `gc()` sweep that hides the tooltip when the
 * active trigger is no longer connected restores a self-healing invariant:
 * the renderer itself can clear stale state, regardless of which event
 * handlers ran or didn't.
 */
const tooltipMgr = (() => {
  let el: HTMLDivElement | null = null;
  let activeBtn: HTMLElement | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;

  const ensureEl = (): HTMLDivElement => {
    if (el) return el;
    el = document.createElement("div");
    el.style.cssText =
      "position:fixed;z-index:9999;background:#1f2937;color:#fff;font-size:11px;font-weight:400;padding:3px 6px;border-radius:4px;pointer-events:none;white-space:nowrap;box-shadow:0 2px 4px rgba(0,0,0,0.15);display:none;";
    document.body.appendChild(el);
    return el;
  };

  const show = (btn: HTMLElement, text: string) => {
    const tip = ensureEl();
    tip.textContent = text;
    tip.style.display = "block";
    const r = btn.getBoundingClientRect();
    // Anchor below the button, horizontally centred. Falls back above when
    // the row is near the viewport bottom — simple, no Floating-UI.
    const y = r.bottom + 6;
    tip.style.left = `${r.left + r.width / 2 - tip.offsetWidth / 2}px`;
    tip.style.top = `${y + tip.offsetHeight > window.innerHeight ? r.top - tip.offsetHeight - 6 : y}px`;
    activeBtn = btn;
  };

  const hide = () => {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    if (el) el.style.display = "none";
    activeBtn = null;
  };

  const attach = (btn: HTMLButtonElement, text: string) => {
    btn.addEventListener("mouseenter", () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        if (btn.isConnected) show(btn, text);
      }, 250);
    });
    btn.addEventListener("mouseleave", () => {
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
      if (activeBtn === btn) hide();
    });
  };

  // Call from the row renderer before re-painting buttons. If Handsontable
  // yanked the active trigger out of the DOM without firing mouseleave,
  // this is what unsticks the tooltip.
  const gc = () => {
    if (activeBtn && !activeBtn.isConnected) hide();
  };

  return { attach, gc };
})();

export function ProcurementHandsontable({
  items,
  procurementCompleted,
  salesByItemId,
  splitableByItemId,
  splitChildByItemId,
  mergeableByItemId,
  mergeResultByItemId,
  onSplitRow,
  onUndoSplitRow,
  onMergeRow,
  onUndoMergeRow,
  onMutated,
}: ProcurementHandsontableProps) {
  const router = useRouter();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const hotRef = useRef<any>(null);
  const pendingOps = useRef(new Set<string>());
  const rowIdsRef = useRef<string[]>(items.map((i) => i.id));

  const initialData = useMemo(
    () => items.map((it) => itemToRow(it, salesByItemId?.[it.id])),
    [items, salesByItemId]
  );

  // Refs let the cell renderer read fresh prop values without us having to
  // remount HotTable when split/undo eligibility maps change. Direct closure
  // capture in `useCallback` was masking later prop updates — the renderer
  // saw an empty `splitChildByItemId` from first mount and never noticed
  // the populated map that arrived after the coverage query resolved.
  const splitableRef = useRef(splitableByItemId);
  const splitChildRef = useRef(splitChildByItemId);
  const mergeableRef = useRef(mergeableByItemId);
  const mergeResultRef = useRef(mergeResultByItemId);
  const onSplitRowRef = useRef(onSplitRow);
  const onUndoSplitRowRef = useRef(onUndoSplitRow);
  const onMergeRowRef = useRef(onMergeRow);
  const onUndoMergeRowRef = useRef(onUndoMergeRow);
  splitableRef.current = splitableByItemId;
  splitChildRef.current = splitChildByItemId;
  mergeableRef.current = mergeableByItemId;
  mergeResultRef.current = mergeResultByItemId;
  onSplitRowRef.current = onSplitRow;
  onUndoSplitRowRef.current = onUndoSplitRow;
  onMergeRowRef.current = onMergeRow;
  onUndoMergeRowRef.current = onUndoMergeRow;
  const onMutatedRef = useRef(onMutated);
  onMutatedRef.current = onMutated;

  // Refs are read imperatively at cell-render time, but Handsontable doesn't
  // re-render cells just because the React parent re-rendered. Tell it to
  // repaint when the maps change so the ↧ / ⋃ / ↪ / ↩ icons appear/disappear.
  useEffect(() => {
    hotRef.current?.hotInstance?.render();
  }, [
    splitableByItemId,
    splitChildByItemId,
    mergeableByItemId,
    mergeResultByItemId,
  ]);

  // Keep rowIds in sync with items
  if (rowIdsRef.current.length !== initialData.length) {
    rowIdsRef.current = initialData.map((r) => r.id);
  }

  const rowActionsRenderer = useCallback(
    (
      _instance: Handsontable,
      td: HTMLTableCellElement,
      row: number,
    ) => {
      td.innerHTML = "";
      td.style.textAlign = "center";
      td.style.verticalAlign = "middle";
      td.style.cursor = "default";
      td.style.padding = "0";
      td.style.whiteSpace = "nowrap";

      // Sweep stale tooltip state — Handsontable removes the previous
      // buttons by clearing innerHTML, but if a button was being hovered,
      // mouseleave never fires on a detached node.
      tooltipMgr.gc();

      const rowId = rowIdsRef.current[row];

      // SVG glyphs styled via currentColor — replaces opaque unicode arrows
      // (↧ ⋃ ↪ ↩) for split/merge/undo with explicit "diverging" / "converging"
      // line drawings that read at a glance. Stroke inherits btn.style.color
      // so the existing hover treatment still applies.
      const SVG_OPEN =
        '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:block;">';
      const SVG_CLOSE = "</svg>";
      // Split = «one path branches out into two». Lucide-style: a vertical
      // trunk that forks into two arrow-tipped diagonals at the top.
      const SPLIT_SVG = `${SVG_OPEN}<path d="M12 21V11"/><path d="M12 11l-5 -5"/><path d="M12 11l5 -5"/><path d="M3 6h6"/><path d="M21 6h-6"/>${SVG_CLOSE}`;
      // Merge = «two paths converge into one». Inverse: two diagonals come
      // together at the top of a single vertical trunk.
      const MERGE_SVG = `${SVG_OPEN}<path d="M12 21V11"/><path d="M12 11l-5 5"/><path d="M12 11l5 5"/><path d="M3 16h6"/><path d="M21 16h-6"/>${SVG_CLOSE}`;
      // Undo-split = «two siblings collapse back to one» — visually the same
      // shape as merge, but rotated 180° (heads at bottom). Keeps the action
      // legible without confusing it with the regular merge icon.
      const UNDO_SPLIT_SVG = `${SVG_OPEN}<path d="M12 3v10"/><path d="M12 13l-5 5"/><path d="M12 13l5 5"/><path d="M3 18h6"/><path d="M21 18h-6"/>${SVG_CLOSE}`;
      // Undo-merge = inverse: a single source diverges back into N children.
      const UNDO_MERGE_SVG = `${SVG_OPEN}<path d="M12 3v10"/><path d="M12 13l-5 -5"/><path d="M12 13l5 -5"/><path d="M3 8h6"/><path d="M21 8h-6"/>${SVG_CLOSE}`;

      // Action buttons carry their identity via `data-action` + `data-row-id`
      // attributes. Click is delegated to the wrapper (см. below), so each
      // button is a pure DOM marker — no closure binding the click handler
      // to `rowId` captured at render-time. This is the same pattern customs-
      // handsontable uses (`data-customs-expand`).
      //
      // МОЗ-108: the previous closure-bound `btn.onclick` made the ✕ button
      // dead — Handsontable detaches and rebuilds td contents on every
      // re-render (incl. the explicit `hot.render()` we trigger when the
      // split/merge maps load), which can leave stale buttons in DOM with
      // closures that early-return because their captured `rowId` no longer
      // matches the current row index. Reading `data-row-id` from the
      // clicked element at click time avoids the entire stale-closure class.
      const makeIcon = (
        content: string,
        title: string,
        hoverColor: string,
        hoverBg: string,
        action: string,
        rowIdAttr: string
      ): HTMLButtonElement => {
        const btn = document.createElement("button");
        btn.type = "button";
        // `content` is either plain text (the unicode ✕ for unassign) or an
        // SVG string. innerHTML covers both cases — there's no untrusted
        // input mixed in.
        btn.innerHTML = content;
        btn.style.cssText =
          "border:none;background:none;color:#a1a1aa;cursor:pointer;font-size:14px;padding:2px 4px;margin-right:2px;border-radius:4px;display:inline-flex;align-items:center;justify-content:center;";
        btn.dataset.action = action;
        btn.dataset.rowId = rowIdAttr;
        btn.dataset.hoverColor = hoverColor;
        btn.dataset.hoverBg = hoverBg;
        btn.addEventListener("mouseenter", () => {
          btn.style.color = hoverColor;
          btn.style.backgroundColor = hoverBg;
        });
        btn.addEventListener("mouseleave", () => {
          btn.style.color = "#a1a1aa";
          btn.style.backgroundColor = "transparent";
        });
        tooltipMgr.attach(btn, title);
        return btn;
      };

      // Split icon — visible only when this row is a 1:1 candidate.
      if (rowId && splitableRef.current?.[rowId] && onSplitRowRef.current) {
        td.appendChild(
          makeIcon(
            SPLIT_SVG,
            "Разделить позицию",
            "#1f2937",
            "#e5e7eb",
            "split",
            rowId
          )
        );
      }

      // Merge icon — only when ≥ 2 1:1 candidates exist in this invoice.
      if (rowId && mergeableRef.current?.[rowId] && onMergeRowRef.current) {
        td.appendChild(
          makeIcon(
            MERGE_SVG,
            "Объединить с другими позициями",
            "#1f2937",
            "#e5e7eb",
            "merge",
            rowId
          )
        );
      }

      // Undo-split icon — visible on any row that's a split child.
      if (rowId && splitChildRef.current?.[rowId] && onUndoSplitRowRef.current) {
        td.appendChild(
          makeIcon(
            UNDO_SPLIT_SVG,
            "Отменить разделение",
            "#1f2937",
            "#e5e7eb",
            "undo-split",
            rowId
          )
        );
      }

      // Undo-merge icon — visible on any row that IS a merge result
      // (covers ≥ 2 quote_items).
      if (
        rowId &&
        mergeResultRef.current?.[rowId] &&
        onUndoMergeRowRef.current
      ) {
        td.appendChild(
          makeIcon(
            UNDO_MERGE_SVG,
            "Отменить объединение",
            "#1f2937",
            "#e5e7eb",
            "undo-merge",
            rowId
          )
        );
      }

      // Unassign — always last, distinctive red hover. Only render when we
      // have a valid rowId to bind to; without one the button can't dispatch
      // anything useful, and rendering it would just create a dead element.
      if (rowId) {
        const unassignBtn = makeIcon(
          "✕",
          "Убрать из КП",
          "#dc2626",
          "#fee2e2",
          "unassign",
          rowId
        );
        // Distinctive padding for the unassign vs the structural icons.
        unassignBtn.style.padding = "2px 6px";
        td.appendChild(unassignBtn);
      }
    },
    // The renderer reads from refs (kept fresh above), so its own deps stay
    // minimal. Capturing the maps directly here was the source of the
    // stale-closure bug that hid the ↪ icon after data loaded.
    []
  );

  /**
   * Delegated click handler for action buttons inside the row-actions cell.
   * Reads the action and row id from data-attributes on the clicked
   * element — bypassing any stale closure on the button itself. Mirrors
   * the `data-customs-expand` pattern in customs-handsontable.
   *
   * МОЗ-108: switching from `btn.onclick = (...) => {...}` (closure-captured
   * rowId) to delegated dispatch via DOM data-attributes fixes the dead ×
   * button. The previous closure could read a stale rowId after re-renders;
   * the new dispatch reads the current rowId from the DOM at click time.
   */
  const handleRowActionClick = useCallback(
    (e: Event) => {
      const target = e.target as HTMLElement | null;
      if (!target) return;
      const btn = target.closest<HTMLElement>("button[data-action][data-row-id]");
      if (!btn) return;
      e.stopPropagation();
      const action = btn.dataset.action;
      const rowId = btn.dataset.rowId;
      if (!action || !rowId) return;

      switch (action) {
        case "split":
          onSplitRowRef.current?.(rowId);
          break;
        case "merge":
          onMergeRowRef.current?.(rowId);
          break;
        case "undo-split":
          onUndoSplitRowRef.current?.(rowId);
          break;
        case "undo-merge":
          onUndoMergeRowRef.current?.(rowId);
          break;
        case "unassign": {
          const lockKey = `unassign-${rowId}`;
          if (pendingOps.current.has(lockKey)) return;
          pendingOps.current.add(lockKey);
          unassignInvoiceItem(rowId)
            .then(() => {
              toast.success("Позиция убрана из КП");
              router.refresh();
              onMutatedRef.current?.();
            })
            .catch((err) => {
              console.error(
                "[procurement-handsontable] unassign failed:",
                err
              );
              toast.error(
                extractErrorMessage(err) ?? "Не удалось убрать позицию"
              );
            })
            .finally(() => pendingOps.current.delete(lockKey));
          break;
        }
      }
    },
    [router]
  );

  const moqWarningRenderer = useCallback(
    (
      instance: Handsontable,
      td: HTMLTableCellElement,
      row: number,
      col: number,
      prop: string | number,
      value: unknown,
      cellProperties: Handsontable.CellProperties
    ) => {
      // Delegate formatting to the default numeric renderer first
      Handsontable.renderers.NumericRenderer(
        instance,
        td,
        row,
        col,
        prop,
        value,
        cellProperties
      );

      const quantity = instance.getDataAtRowProp(row, "quantity") as
        | number
        | null
        | undefined;
      const violated = isMoqViolation({
        quantity: quantity ?? null,
        min_order_quantity:
          typeof value === "number"
            ? value
            : value == null || value === ""
              ? null
              : Number(value),
      });

      if (violated) {
        td.classList.add("moq-warning");
        td.title = "Количество ниже минимального заказа поставщика";
      } else {
        td.classList.remove("moq-warning");
        td.removeAttribute("title");
      }
    },
    []
  );

  const handleAfterChange = useCallback(
    (changes: Handsontable.CellChange[] | null, source: string) => {
      if (!changes || source === "loadData") return;

      const hot = hotRef.current?.hotInstance;
      if (!hot) return;

      // Group changes by row
      const changedRows = new Map<number, Map<string, unknown>>();
      for (const [row, prop, , newVal] of changes) {
        const field =
          typeof prop === "number"
            ? COLUMN_KEYS[prop]
            : typeof prop === "string"
              ? prop
              : undefined;
        if (!field || field === "id") continue;
        // Sales-side display columns are read-only; never persisted to
        // invoice_items. Defensive skip in case handsontable surfaces a
        // synthetic change (e.g., bulk paste over read-only cells).
        if (
          field === "sales_product_code" ||
          field === "sales_product_name" ||
          field === "sales_unit"
        ) {
          continue;
        }

        if (!changedRows.has(row)) {
          changedRows.set(row, new Map());
        }
        changedRows.get(row)!.set(field, newVal);
      }

      for (const [rowIndex, fieldChanges] of changedRows) {
        const rowId = rowIdsRef.current[rowIndex];
        if (!rowId) continue;

        const updates: Record<string, unknown> = {};

        for (const [field, val] of fieldChanges) {
          if (field === "dimensions") {
            // Parse "HxWxL" into three separate DB columns
            const dims = parseDimensions(String(val ?? ""));
            updates.dimension_height_mm = dims.height;
            updates.dimension_width_mm = dims.width;
            updates.dimension_length_mm = dims.length;
          } else if (
            field === "purchase_price_original" ||
            field === "weight_in_kg" ||
            field === "production_time_days" ||
            field === "minimum_order_quantity"
          ) {
            const parsed = parseFloat(String(val));
            updates[field] = isNaN(parsed) ? null : parsed;
          } else if (field === "purchase_currency") {
            updates[field] = val || null;
          } else {
            // Text fields: supplier_sku, product_name
            updates[field] = val || null;
          }
        }

        if (Object.keys(updates).length === 0) continue;

        const lockKey = `update-${rowId}`;
        if (pendingOps.current.has(lockKey)) continue;
        pendingOps.current.add(lockKey);

        updateInvoiceItem(rowId, updates)
          .then(() => {
            router.refresh();
            onMutatedRef.current?.();
          })
          .catch((err) => {
            console.error("[procurement-handsontable] update failed:", err);
            toast.error(extractErrorMessage(err) ?? "Не удалось сохранить");
          })
          .finally(() => pendingOps.current.delete(lockKey));
      }
    },
    [router]
  );

  // Visible column order in the rendered handsontable. Includes the two
  // sales-side read-only columns at indices 1-2 (which COLUMN_KEYS — bound
  // to invoice_items save targets — does NOT contain). Used to map field
  // names to actual rendered column positions for lockedColIndices.
  const VISIBLE_KEYS = [
    "brand",
    "sales_product_code",
    "sales_product_name",
    "supplier_sku",
    "product_name",
    "quantity",
    "sales_unit",
    "minimum_order_quantity",
    "purchase_price_original",
    "production_time_days",
    "weight_in_kg",
    "dimensions",
    "id",
  ] as const;

  const lockedColIndices = useMemo(() => {
    if (!procurementCompleted) return [];
    return [
      VISIBLE_KEYS.indexOf("supplier_sku"),
      VISIBLE_KEYS.indexOf("purchase_price_original"),
      VISIBLE_KEYS.indexOf("production_time_days"),
    ];
    // VISIBLE_KEYS is module-stable; no need to depend on it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [procurementCompleted]);

  const cellsCallback = useCallback(
    (_row: number, col: number) => {
      if (lockedColIndices.includes(col)) {
        return { className: "locked-cell" };
      }
      return {};
    },
    [lockedColIndices]
  );

  if (items.length === 0) {
    return (
      <div className="py-6 text-center text-sm text-muted-foreground">
        Нет позиций в этом КП
      </div>
    );
  }

  return (
    <div
      className="ht-theme-main"
      ref={(el) => {
        if (!el) return;
        // Single delegated click listener for all action-cell buttons.
        // Re-attached idempotently each callback ref invocation; remove first
        // to avoid duplicate handlers across React re-renders. Mirrors the
        // customs-handsontable wiring (см. ../customs-step/customs-handsontable
        // → handleExpandClick).
        el.removeEventListener(
          "click",
          handleRowActionClick as EventListener
        );
        el.addEventListener(
          "click",
          handleRowActionClick as EventListener
        );
      }}
    >
      <style>{`
        .locked-cell { background-color: var(--muted, #f4f4f5) !important; }
        .moq-warning { background-color: #fef3c7 !important; position: relative; }
        .moq-warning::after {
          content: "⚠";
          position: absolute;
          top: 2px;
          right: 4px;
          color: #b45309;
          font-size: 11px;
          line-height: 1;
          pointer-events: none;
        }
      `}</style>
      <HotTable
        ref={hotRef}
        data={initialData}
        licenseKey="non-commercial-and-evaluation"
        colHeaders={[
          "Бренд",
          "Артикул",
          "Наименование",
          "Артикул производителя",
          "Наименование производителя",
          "Кол",
          "Ед. Изм",
          "Мин. заказ",
          "Цена",
          "Срок, к.дн",
          "Вес, кг",
          "В×Ш×Д, мм",
          "",
        ]}
        columns={[
          { data: "brand", type: "text", width: 55, readOnly: true },
          // Sales-side columns: read-only, joined from quote_items.
          { data: "sales_product_code", type: "text", width: 70, readOnly: true },
          { data: "sales_product_name", type: "text", width: 140, readOnly: true },
          // Supplier-side columns: editable by procurement.
          {
            data: "supplier_sku",
            type: "text",
            width: 70,
            readOnly: procurementCompleted,
          },
          { data: "product_name", type: "text", width: 140, readOnly: procurementCompleted },
          { data: "quantity", type: "numeric", width: 35, readOnly: true },
          // Ед. Изм — joined from quote_items.unit; read-only because the
          // unit is set on the customer side and shouldn't be edited from the
          // supplier КП. Test-fail H.107.
          { data: "sales_unit", type: "text", width: 50, readOnly: true },
          {
            data: "minimum_order_quantity",
            type: "numeric",
            width: 45,
            renderer: moqWarningRenderer,
          },
          { data: "purchase_price_original", type: "numeric", width: 55, readOnly: procurementCompleted },
          { data: "production_time_days", type: "numeric", width: 45, readOnly: procurementCompleted },
          { data: "weight_in_kg", type: "numeric", width: 45 },
          { data: "dimensions", type: "text", width: 60 },
          { data: "id", readOnly: true, width: 96, renderer: rowActionsRenderer },
        ]}
        rowHeaders={false}
        stretchH="all"
        autoWrapRow={true}
        autoWrapCol={true}
        manualColumnResize={true}
        contextMenu={false}
        minSpareRows={0}
        height="auto"
        afterChange={handleAfterChange}
        cells={procurementCompleted ? cellsCallback : undefined}
        className="htLeft"
      />
    </div>
  );
}
