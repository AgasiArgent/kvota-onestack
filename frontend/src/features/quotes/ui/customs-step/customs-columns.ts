/**
 * Canonical column catalog for the customs items registry.
 *
 * This list is the source of truth for both the Handsontable grid
 * (`customs-handsontable.tsx`) and the table-views settings dialog
 * (`features/table-views`). It lives in a dependency-free module so it
 * can be imported by server components and by the dynamically-loaded
 * Handsontable wrapper without pulling the grid library into the main
 * bundle.
 *
 * The `expand` (↗) column is intentionally omitted — it is always
 * rendered as the first column and is not user-configurable.
 */

export interface CustomsColumnSpec {
  /** Stable logical key, stored in `user_table_views.visible_columns`. */
  key: string;
  /** Plain-text Russian label (no HTML). */
  label: string;
}

export const CUSTOMS_AVAILABLE_COLUMNS: readonly CustomsColumnSpec[] = [
  { key: "position", label: "№" },
  { key: "brand", label: "Бренд" },
  { key: "product_code", label: "Артикул" },
  { key: "product_name", label: "Наименование" },
  { key: "quantity", label: "Кол-во" },
  { key: "supplier_country", label: "Страна" },
  { key: "hs_code", label: "Код ТН ВЭД" },
  { key: "customs_duty_composite", label: "Пошлина" },
  { key: "customs_util_fee", label: "Утильсбор" },
  { key: "customs_excise", label: "Акциз" },
  { key: "customs_psm_pts", label: "ПСМ/ПТС" },
  { key: "customs_notification", label: "Нотификация" },
  { key: "customs_licenses", label: "Лицензии" },
  { key: "customs_eco_fee", label: "Экосбор" },
  { key: "customs_honest_mark", label: "Честный знак" },
  { key: "import_banned", label: "Запрет ввоза" },
  { key: "import_ban_reason", label: "Причина запрета" },
  { key: "license_ds_required", label: "ДС" },
  { key: "license_ds_cost", label: "Ст-ть ДС" },
  { key: "license_ss_required", label: "СС" },
  { key: "license_ss_cost", label: "Ст-ть СС" },
  { key: "license_sgr_required", label: "СГР" },
  { key: "license_sgr_cost", label: "Ст-ть СГР" },
];

/** Stable registry key for the customs items table — matches `user_table_views.table_key`. */
export const CUSTOMS_TABLE_KEY = "quote_customs_items";
