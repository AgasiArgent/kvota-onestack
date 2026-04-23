"use client";

import { useRef, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { HotTable } from "@handsontable/react";
import { registerAllModules } from "handsontable/registry";
import Handsontable from "handsontable";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { updateQuoteItem } from "@/entities/quote/mutations";
import type { QuoteItemRow } from "@/entities/quote/queries";
import type { CustomsAutofillSuggestion } from "@/features/customs-autofill";

import "handsontable/styles/handsontable.css";
import "handsontable/styles/ht-theme-main.css";

registerAllModules();

function ext<T>(row: unknown): T {
  return row as T;
}

// ---------------------------------------------------------------------------
// Row model — mirrors DB columns after migration 293:
//   dropped: customs_ds_sgr, customs_marking
//   renamed: customs_psn_pts → customs_psm_pts
// ---------------------------------------------------------------------------

type ItemExtras = {
  hs_code?: string | null;
  customs_duty?: number | null;
  customs_duty_per_kg?: number | null;
  customs_util_fee?: number | null;
  customs_excise?: number | null;
  customs_psm_pts?: string | null;
  customs_notification?: string | null;
  customs_licenses?: string | null;
  customs_eco_fee?: number | null;
  customs_honest_mark?: string | null;
  import_banned?: boolean | null;
  import_ban_reason?: string | null;
  license_ds_required?: boolean | null;
  license_ds_cost?: number | null;
  license_ss_required?: boolean | null;
  license_ss_cost?: number | null;
  license_sgr_required?: boolean | null;
  license_sgr_cost?: number | null;
};

/** Logical column keys (order matches HoT column array below). */
const COLUMN_KEYS = [
  "expand",
  "position",
  "brand",
  "product_code",
  "product_name",
  "quantity",
  "supplier_country",
  "hs_code",
  "customs_duty_composite",
  "customs_util_fee",
  "customs_excise",
  "customs_psm_pts",
  "customs_notification",
  "customs_licenses",
  "customs_eco_fee",
  "customs_honest_mark",
  "import_banned",
  "import_ban_reason",
  "license_ds_required",
  "license_ds_cost",
  "license_ss_required",
  "license_ss_cost",
  "license_sgr_required",
  "license_sgr_cost",
] as const;

type DutyMode = "pct" | "perKg";

interface RowData {
  id: string;
  position: number;
  brand: string;
  product_code: string;
  product_name: string;
  quantity: number | null;
  supplier_country: string;
  hs_code: string;

  /** Composite display value — mode determined by which storage column is set. */
  customs_duty_composite: number | null;
  /** Actual storage — only one of these is non-null per row. */
  customs_duty: number | null;
  customs_duty_per_kg: number | null;

  customs_util_fee: number | null;
  customs_excise: number | null;
  customs_psm_pts: string;
  customs_notification: string;
  customs_licenses: string;
  customs_eco_fee: number | null;
  customs_honest_mark: string;
  import_banned: boolean;
  import_ban_reason: string;
  license_ds_required: boolean;
  license_ds_cost: number | null;
  license_ss_required: boolean;
  license_ss_cost: number | null;
  license_sgr_required: boolean;
  license_sgr_cost: number | null;
}

function resolveDutyMode(
  _duty: number | null | undefined,
  dutyPerKg: number | null | undefined,
): DutyMode {
  return dutyPerKg != null ? "perKg" : "pct";
}

function itemToRow(
  item: QuoteItemRow,
  invoiceCountryMap: Map<string, string>,
  supplierByQi: Map<
    string,
    { supplier_country: string | null; invoice_id: string | null }
  >,
): RowData {
  const extras = ext<ItemExtras>(item);
  const supplier = supplierByQi.get(item.id) ?? null;
  const country =
    supplier?.supplier_country ??
    (supplier?.invoice_id
      ? invoiceCountryMap.get(supplier.invoice_id) ?? ""
      : "");

  const duty = extras.customs_duty ?? null;
  const dutyPerKg = extras.customs_duty_per_kg ?? null;
  const composite = dutyPerKg != null ? dutyPerKg : duty;

  return {
    id: item.id,
    position: item.position ?? 0,
    brand: item.brand ?? "",
    product_code: item.product_code ?? "",
    product_name: item.product_name ?? "",
    quantity: item.quantity,
    supplier_country: country,
    hs_code: extras.hs_code ?? "",

    customs_duty_composite: composite,
    customs_duty: duty,
    customs_duty_per_kg: dutyPerKg,

    customs_util_fee: extras.customs_util_fee ?? null,
    customs_excise: extras.customs_excise ?? null,
    customs_psm_pts: extras.customs_psm_pts ?? "",
    customs_notification: extras.customs_notification ?? "",
    customs_licenses: extras.customs_licenses ?? "",
    customs_eco_fee: extras.customs_eco_fee ?? null,
    customs_honest_mark: extras.customs_honest_mark ?? "",
    import_banned: extras.import_banned ?? false,
    import_ban_reason: extras.import_ban_reason ?? "",
    license_ds_required: extras.license_ds_required ?? false,
    license_ds_cost: extras.license_ds_cost ?? null,
    license_ss_required: extras.license_ss_required ?? false,
    license_ss_cost: extras.license_ss_cost ?? null,
    license_sgr_required: extras.license_sgr_required ?? false,
    license_sgr_cost: extras.license_sgr_cost ?? null,
  };
}

const NUMERIC_FIELDS = new Set([
  "customs_util_fee",
  "customs_excise",
  "customs_eco_fee",
  "license_ds_cost",
  "license_ss_cost",
  "license_sgr_cost",
]);

const BOOLEAN_FIELDS = new Set([
  "import_banned",
  "license_ds_required",
  "license_ss_required",
  "license_sgr_required",
]);

const TEXT_FIELDS = new Set([
  "hs_code",
  "customs_psm_pts",
  "customs_notification",
  "customs_licenses",
  "customs_honest_mark",
  "import_ban_reason",
]);

function headerWithTooltip(label: string, tooltip: string): string {
  return `<span title="${tooltip}">${label}</span>`;
}

const numericTooltip = "Значение за единицу товара";

/**
 * Static column headers — defined at module level to prevent
 * Handsontable re-initialization issues on React re-renders.
 */
const COL_HEADERS: string[] = [
  "",
  "No",
  "Бренд",
  "Артикул",
  "Наименование",
  "Кол-во",
  "Страна",
  "Код ТН ВЭД",
  headerWithTooltip("Пошлина", "Процент / ₽ за кг (₽ за шт требует миграции)"),
  headerWithTooltip("Утильсбор", numericTooltip),
  headerWithTooltip("Акциз", numericTooltip),
  "ПСМ/ПТС",
  "Нотификация",
  "Лицензии",
  headerWithTooltip("Экосбор", numericTooltip),
  "Честный знак",
  "Запрет ввоза",
  "Причина запрета",
  "ДС",
  headerWithTooltip("Ст-ть ДС", numericTooltip),
  "СС",
  headerWithTooltip("Ст-ть СС", numericTooltip),
  "СГР",
  headerWithTooltip("Ст-ть СГР", numericTooltip),
];

/**
 * Composite "Пошлина" cell renderer.
 *
 * Draws the value + an inline chip selector (%, ₽/кг). The chip toggles
 * mode — writing to customs_duty (%) or customs_duty_per_kg (₽/кг) —
 * via an afterChange-compatible event dispatch.
 *
 * ₽/шт variant is shown disabled with a tooltip since the
 * customs_duty_per_pc column does not yet exist in the DB.
 */
function dutyCompositeRenderer(
  instance: Handsontable,
  td: HTMLTableCellElement,
  row: number,
  col: number,
  prop: string | number,
  value: unknown,
  cellProperties: Handsontable.CellProperties,
) {
  // Let the default numeric renderer format the numeric value first.
  Handsontable.renderers.NumericRenderer(
    instance,
    td,
    row,
    col,
    prop,
    value,
    cellProperties,
  );

  td.classList.add("customs-duty-cell");

  // Strip any previously appended chip UI to avoid duplicates on re-render.
  const existing = td.querySelector(".customs-duty-chip");
  if (existing) existing.remove();

  const duty = instance.getDataAtRowProp(row, "customs_duty") as
    | number
    | null
    | undefined;
  const dutyPerKg = instance.getDataAtRowProp(row, "customs_duty_per_kg") as
    | number
    | null
    | undefined;
  const mode: DutyMode = resolveDutyMode(duty, dutyPerKg);

  const chip = document.createElement("span");
  chip.className = "customs-duty-chip";
  chip.setAttribute("role", "group");
  chip.setAttribute("aria-label", "Тип пошлины");

  function mkBtn(
    label: string,
    targetMode: DutyMode | "perPc",
    disabled = false,
  ): HTMLButtonElement {
    const b = document.createElement("button");
    b.type = "button";
    b.className =
      "customs-duty-chip__btn" +
      (targetMode === mode ? " customs-duty-chip__btn--active" : "");
    b.textContent = label;
    if (disabled) {
      b.disabled = true;
      b.title = "Требуется миграция: колонка customs_duty_per_pc";
      b.classList.add("customs-duty-chip__btn--disabled");
    } else if (targetMode !== mode) {
      b.onclick = (e) => {
        e.stopPropagation();
        // Stash the current composite value under the new mode and clear the other.
        const rowId = instance.getDataAtRowProp(row, "id") as string;
        const event = new CustomEvent<
          { rowId: string; mode: "pct" | "perKg" }
        >("kvota:duty-mode-change", {
          bubbles: true,
          detail: {
            rowId,
            mode: targetMode === "perKg" ? "perKg" : "pct",
          },
        });
        td.dispatchEvent(event);
      };
    }
    return b;
  }

  chip.appendChild(mkBtn("%", "pct"));
  chip.appendChild(mkBtn("₽/кг", "perKg"));
  chip.appendChild(mkBtn("₽/шт", "perPc", /* disabled */ true));
  td.appendChild(chip);
}

/**
 * Expand-action cell renderer — draws a small `↗` button that opens the
 * per-row customs dialog (Task 8). The click is handled via event delegation
 * on the scrolling wrapper to avoid re-binding listeners on each render.
 */
function expandRenderer(
  _instance: Handsontable,
  td: HTMLTableCellElement,
): HTMLTableCellElement {
  td.innerHTML = "";
  td.classList.add("customs-expand-cell");
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "customs-expand-btn";
  btn.setAttribute("data-customs-expand", "1");
  btn.title = "Открыть карточку позиции";
  btn.setAttribute("aria-label", "Открыть карточку позиции");
  btn.textContent = "↗";
  td.appendChild(btn);
  return td;
}

/**
 * Number renderer that adds a sparkle icon into the cell for autofilled rows.
 * Used on the `position` (№) column; the icon tooltip cites the source Q-number.
 */
function makePositionRenderer(
  autofillByRowId: Map<string, CustomsAutofillSuggestion>,
) {
  return function positionRenderer(
    instance: Handsontable,
    td: HTMLTableCellElement,
    row: number,
    col: number,
    prop: string | number,
    value: unknown,
    cellProperties: Handsontable.CellProperties,
  ) {
    Handsontable.renderers.NumericRenderer(
      instance,
      td,
      row,
      col,
      prop,
      value,
      cellProperties,
    );

    const existing = td.querySelector(".customs-sparkle");
    if (existing) existing.remove();

    const rowId = instance.getDataAtRowProp(row, "id") as string | null;
    if (!rowId) return;
    const suggestion = autofillByRowId.get(rowId);
    if (!suggestion) return;

    const sparkle = document.createElement("span");
    sparkle.className = "customs-sparkle";
    const idn = suggestion.source_quote_idn?.trim();
    sparkle.title = idn
      ? `Автозаполнено из КП ${idn}`
      : "Автозаполнено из истории";
    sparkle.innerHTML =
      // Small sparkle svg — matches lucide Sparkles at 12px.
      `<svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/></svg>`;
    td.prepend(sparkle);
    td.classList.add("customs-autofill-row");
  };
}

/**
 * Static column definitions — defined at module level so Handsontable
 * always receives the same column count regardless of React re-render timing.
 * The `readOnly` for import_banned is handled dynamically in the cells callback.
 *
 * Column at index 7 ("Пошлина") is a composite backed by a virtual
 * `customs_duty_composite` key — writes are intercepted in handleAfterChange
 * and mirrored onto either customs_duty or customs_duty_per_kg depending on
 * the active mode.
 */
const COLUMNS: Handsontable.ColumnSettings[] = [
  { data: "expand", type: "text", width: 36, readOnly: true },
  { data: "position", type: "numeric", width: 42, readOnly: true },
  { data: "brand", type: "text", width: 70, readOnly: true, wordWrap: false },
  { data: "product_code", type: "text", width: 100, readOnly: true, wordWrap: false },
  { data: "product_name", type: "text", width: 200, readOnly: true, wordWrap: false },
  { data: "quantity", type: "numeric", width: 55, readOnly: true },
  { data: "supplier_country", type: "text", width: 70, readOnly: true },
  { data: "hs_code", type: "text", width: 90 },
  {
    data: "customs_duty_composite",
    type: "numeric",
    width: 130,
    allowEmpty: true,
  },
  { data: "customs_util_fee", type: "numeric", width: 70, allowEmpty: true },
  { data: "customs_excise", type: "numeric", width: 65, allowEmpty: true },
  { data: "customs_psm_pts", type: "text", width: 75 },
  { data: "customs_notification", type: "text", width: 90 },
  { data: "customs_licenses", type: "text", width: 80 },
  { data: "customs_eco_fee", type: "numeric", width: 65, allowEmpty: true },
  { data: "customs_honest_mark", type: "text", width: 85 },
  { data: "import_banned", type: "checkbox", width: 50 },
  { data: "import_ban_reason", type: "text", width: 120 },
  { data: "license_ds_required", type: "checkbox", width: 30 },
  { data: "license_ds_cost", type: "numeric", width: 55, allowEmpty: true },
  { data: "license_ss_required", type: "checkbox", width: 30 },
  { data: "license_ss_cost", type: "numeric", width: 55, allowEmpty: true },
  { data: "license_sgr_required", type: "checkbox", width: 30 },
  { data: "license_sgr_cost", type: "numeric", width: 55, allowEmpty: true },
];

interface CustomsHandsontableProps {
  items: QuoteItemRow[];
  invoiceCountryMap: Map<string, string>;
  supplierByQuoteItemId: Map<
    string,
    { supplier_country: string | null; invoice_id: string | null }
  >;
  userRoles: string[];
  /** Per-row autofill suggestions (keyed by quote_item_id). Optional. */
  autofillSuggestions?: CustomsAutofillSuggestion[];
  /** Called when user selects a row (for the item-level expenses card). */
  onSelectRow?: (rowId: string | null) => void;
  /** Called when the per-row `↗` expand button is clicked (opens the dialog). */
  onExpandRow?: (rowId: string) => void;
}

export function CustomsHandsontable({
  items,
  invoiceCountryMap,
  supplierByQuoteItemId,
  userRoles,
  autofillSuggestions = [],
  onSelectRow,
  onExpandRow,
}: CustomsHandsontableProps) {
  const router = useRouter();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const hotRef = useRef<any>(null);
  const pendingOps = useRef(new Set<string>());
  const rowIdsRef = useRef<string[]>(items.map((i) => i.id));

  const initialData = useMemo(
    () =>
      items.map((item) =>
        itemToRow(item, invoiceCountryMap, supplierByQuoteItemId),
      ),
    [items, invoiceCountryMap, supplierByQuoteItemId],
  );

  if (rowIdsRef.current.length !== initialData.length) {
    rowIdsRef.current = initialData.map((r) => r.id);
  }

  const autofillByRowId = useMemo(() => {
    const m = new Map<string, CustomsAutofillSuggestion>();
    for (const s of autofillSuggestions) m.set(s.item_id, s);
    return m;
  }, [autofillSuggestions]);

  const positionRenderer = useMemo(
    () => makePositionRenderer(autofillByRowId),
    [autofillByRowId],
  );

  const handleAfterChange = useCallback(
    (changes: Handsontable.CellChange[] | null, source: string) => {
      if (!changes || source === "loadData") return;

      const hot = hotRef.current?.hotInstance;
      if (!hot) return;

      // Group per-row patches, translating customs_duty_composite into either
      // customs_duty or customs_duty_per_kg based on the row's current mode.
      const changedRows = new Map<number, Map<string, unknown>>();
      for (const [row, prop, , newVal] of changes) {
        const field =
          typeof prop === "number"
            ? COLUMN_KEYS[prop]
            : typeof prop === "string"
              ? prop
              : undefined;
        if (!field || field === "id" || field === "position") continue;

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
          if (field === "customs_duty_composite") {
            const parsed = parseFloat(String(val));
            const num = Number.isNaN(parsed) ? null : parsed;
            const curDutyPerKg = hot.getDataAtRowProp(
              rowIndex,
              "customs_duty_per_kg",
            ) as number | null | undefined;
            const mode: DutyMode = curDutyPerKg != null ? "perKg" : "pct";
            if (mode === "perKg") {
              updates.customs_duty_per_kg = num;
              updates.customs_duty = null;
            } else {
              updates.customs_duty = num;
              updates.customs_duty_per_kg = null;
            }
            // Sync the mirror fields into HoT state so the renderer
            // sees the latest value immediately.
            hot.setDataAtRowProp(rowIndex, "customs_duty", updates.customs_duty, "internal-mirror");
            hot.setDataAtRowProp(
              rowIndex,
              "customs_duty_per_kg",
              updates.customs_duty_per_kg,
              "internal-mirror",
            );
            continue;
          }
          if (NUMERIC_FIELDS.has(field)) {
            const parsed = parseFloat(String(val));
            updates[field] = isNaN(parsed) ? null : parsed;
          } else if (BOOLEAN_FIELDS.has(field)) {
            updates[field] = Boolean(val);
          } else if (TEXT_FIELDS.has(field)) {
            updates[field] = val || null;
          }
        }

        if (Object.keys(updates).length === 0) continue;

        const lockKey = `update-${rowId}`;
        if (pendingOps.current.has(lockKey)) continue;
        pendingOps.current.add(lockKey);

        updateQuoteItem(rowId, updates)
          .then(() => router.refresh())
          .catch(() => toast.error("Не удалось сохранить"))
          .finally(() => pendingOps.current.delete(lockKey));
      }
    },
    [router],
  );

  /**
   * Handle mode chip clicks via a synthetic CustomEvent dispatched by the
   * composite renderer. Flips the row's duty storage column.
   */
  const handleDutyModeChange = useCallback(
    (e: Event) => {
      const custom = e as CustomEvent<{ rowId: string; mode: DutyMode }>;
      const { rowId, mode } = custom.detail;
      const hot = hotRef.current?.hotInstance;
      if (!hot) return;
      const rowIndex = rowIdsRef.current.indexOf(rowId);
      if (rowIndex < 0) return;

      const currentComposite = hot.getDataAtRowProp(
        rowIndex,
        "customs_duty_composite",
      ) as number | null | undefined;
      const val = currentComposite ?? 0;

      const updates: Record<string, unknown> =
        mode === "perKg"
          ? { customs_duty_per_kg: val, customs_duty: null }
          : { customs_duty: val, customs_duty_per_kg: null };

      // Mirror into HoT state so the renderer picks up the mode switch.
      hot.setDataAtRowProp(
        rowIndex,
        "customs_duty",
        updates.customs_duty,
        "internal-mirror",
      );
      hot.setDataAtRowProp(
        rowIndex,
        "customs_duty_per_kg",
        updates.customs_duty_per_kg,
        "internal-mirror",
      );

      const lockKey = `update-${rowId}`;
      if (pendingOps.current.has(lockKey)) return;
      pendingOps.current.add(lockKey);
      updateQuoteItem(rowId, updates)
        .then(() => router.refresh())
        .catch(() => toast.error("Не удалось сохранить"))
        .finally(() => pendingOps.current.delete(lockKey));
    },
    [router],
  );

  const canToggleBan = useMemo(
    () => userRoles.some((r) => ["customs", "head_of_customs", "admin"].includes(r)),
    [userRoles],
  );

  /** Per-cell config: banned row, composite renderer, autofill sparkle. */
  const cellsCallback = useCallback(
    function (
      this: Handsontable.CellProperties,
      row: number,
      col: number,
    ): Handsontable.CellMeta {
      const meta: Handsontable.CellMeta = {};
      const data = initialData[row];
      if (!data) return meta;

      if (data.import_banned) {
        meta.className = (meta.className ?? "") + " row-import-banned";
      }

      const prop = COLUMN_KEYS[col];

      if (prop === "position") {
        meta.renderer = positionRenderer;
      } else if (prop === "customs_duty_composite") {
        meta.renderer = dutyCompositeRenderer;
      } else if (prop === "expand") {
        meta.renderer = expandRenderer;
      }

      if (prop === "import_banned" && !canToggleBan) {
        meta.readOnly = true;
      }
      if (prop === "import_ban_reason" && !data.import_banned) {
        meta.readOnly = true;
      }

      return meta;
    },
    [initialData, canToggleBan, positionRenderer],
  );

  const handleAfterSelectionEnd = useCallback(
    (rowStart: number) => {
      const rowId = rowIdsRef.current[rowStart] ?? null;
      onSelectRow?.(rowId);
    },
    [onSelectRow],
  );

  /**
   * Delegated click handler for the per-row `↗` expand button. Uses
   * HoT's getCoords(td) to resolve the row index rather than relying on
   * walking DOM attributes, because Handsontable does not expose a stable
   * data-row attribute on all render paths.
   */
  const handleExpandClick = useCallback(
    (e: Event) => {
      const target = e.target as HTMLElement | null;
      if (!target) return;
      const btn = target.closest<HTMLElement>("[data-customs-expand]");
      if (!btn) return;
      e.stopPropagation();
      e.preventDefault();
      const td = btn.closest<HTMLTableCellElement>("td");
      const hot = hotRef.current?.hotInstance;
      if (!td || !hot) return;
      const coords = hot.getCoords(td);
      if (!coords || coords.row < 0) return;
      const rowId = rowIdsRef.current[coords.row];
      if (!rowId) return;
      onExpandRow?.(rowId);
    },
    [onExpandRow],
  );

  if (items.length === 0) {
    return (
      <div className="py-6 text-center text-sm text-muted-foreground">
        Нет позиций для таможенного оформления
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <Badge
          variant="secondary"
          className="bg-accent/10 text-accent border border-accent/20"
        >
          Все суммы в таблице — в рублях ₽
        </Badge>
        <span className="text-xs text-muted-foreground">
          Числовые столбцы — значение за единицу товара.
        </span>
      </div>

      <div className="ht-theme-main">
        <style>{`
          .row-import-banned td {
            background-color: color-mix(in oklch, var(--destructive) 8%, transparent) !important;
          }
          .customs-duty-cell {
            position: relative;
            padding-right: 70px !important;
          }
          .customs-duty-chip {
            position: absolute;
            right: 4px;
            top: 50%;
            transform: translateY(-50%);
            display: inline-flex;
            border-radius: var(--radius-sm);
            overflow: hidden;
            border: 1px solid var(--border);
            background: var(--card);
          }
          .customs-duty-chip__btn {
            padding: 2px 5px;
            font-size: 10px;
            line-height: 1;
            font-weight: 600;
            color: var(--muted-foreground);
            background: transparent;
            border: 0;
            cursor: pointer;
          }
          .customs-duty-chip__btn + .customs-duty-chip__btn {
            border-left: 1px solid var(--border);
          }
          .customs-duty-chip__btn--active {
            background: var(--accent);
            color: var(--accent-foreground);
          }
          .customs-duty-chip__btn--disabled {
            opacity: 0.45;
            cursor: not-allowed;
          }
          .customs-sparkle {
            display: inline-flex;
            vertical-align: middle;
            margin-right: 4px;
            color: var(--accent);
          }
          .customs-autofill-row {
            background-color: color-mix(in oklch, var(--accent) 5%, transparent);
          }
          .customs-expand-cell {
            padding: 0 !important;
            text-align: center;
          }
          .customs-expand-btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 24px;
            height: 24px;
            margin: 2px auto;
            padding: 0;
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            background: var(--card);
            color: var(--muted-foreground);
            font-size: 13px;
            line-height: 1;
            cursor: pointer;
          }
          .customs-expand-btn:hover {
            color: var(--foreground);
            border-color: var(--accent);
          }
        `}</style>
        <div
          style={{ overflowX: "auto" }}
          ref={(el) => {
            if (!el) return;
            // Attach a single delegated listener for the custom duty-mode event.
            el.removeEventListener(
              "kvota:duty-mode-change",
              handleDutyModeChange as EventListener,
            );
            el.addEventListener(
              "kvota:duty-mode-change",
              handleDutyModeChange as EventListener,
            );
            el.removeEventListener(
              "click",
              handleExpandClick as EventListener,
            );
            el.addEventListener(
              "click",
              handleExpandClick as EventListener,
            );
          }}
        >
          <HotTable
            ref={hotRef}
            data={initialData}
            licenseKey="non-commercial-and-evaluation"
            colHeaders={COL_HEADERS}
            columns={COLUMNS}
            cells={cellsCallback}
            rowHeaders={false}
            stretchH="none"
            autoWrapRow={true}
            autoWrapCol={true}
            manualColumnResize={true}
            contextMenu={false}
            minSpareRows={0}
            height="auto"
            afterChange={handleAfterChange}
            afterSelectionEnd={handleAfterSelectionEnd}
            className="htLeft"
          />
        </div>
      </div>
    </div>
  );
}
