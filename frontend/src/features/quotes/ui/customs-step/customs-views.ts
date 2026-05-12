/**
 * `customs-views.ts` — Phase B Wave 4 Task 8 / REQ-11.
 *
 * Source-of-truth for the **4 virtual client-side "system" views** of the
 * customs items registry. The views live as constants here (NOT as rows in
 * `kvota.user_table_views`) per LD-16 — synthetic IDs prefixed `system:`
 * cannot collide with the UUID primary keys of real `user_table_views`
 * rows, so URL persistence (`?customs_view=<id>`) keeps working without
 * any DB migration.
 *
 * Wired by:
 *   - `customs-step.tsx` (Wave 4 Task 9) — concats `[...CUSTOMS_SYSTEM_VIEWS,
 *     ...userViews]` before passing to `<TableViewsDropdown />`.
 *   - `customs-handsontable.tsx` (Wave 4 Task 11) — resolves the active view
 *     via `isSystemViewId(id) ? resolveSystemView(id) : userViews.find(...)`,
 *     defaulting to `system:all` when no active view is set (REQ-11 AC#7).
 *   - `<CustomsViewHintBanner />` (Wave 4 Task 8 — same commit) — shows the
 *     "💡 Сейчас активен вид «X» — скрыты колонки: …" prompt above the
 *     Handsontable when the active view is a non-default system view
 *     (REQ-11 AC#9).
 *
 * Column ids are verified against
 * `frontend/src/features/quotes/ui/customs-step/customs-columns.ts`
 * (`CUSTOMS_AVAILABLE_COLUMNS` — 24 entries; see the test file for the
 * structural assertion that every visible id resolves to a known column).
 *
 * Design references:
 *   - `.kiro/specs/customs-shared-certificates/design.md` §4.11 — view defs
 *   - `.kiro/specs/customs-shared-certificates/requirements.md` REQ-11 AC#2
 *     — concrete 4-view column-id pick (mirrored verbatim below).
 *   - LD-16 — synthetic `system:*` ID rationale.
 */

import type { SystemView } from "@/features/customs-certificates";

import { CUSTOMS_AVAILABLE_COLUMNS } from "./customs-columns";

/**
 * 4 virtual system views — order matches the dropdown rendering order
 * (REQ-11 AC#4: «Системные» group above «Личные» / «Общие»). The first
 * entry (`system:all`) is the implicit default returned by
 * `defaultSystemViewId()` and used as the fallback in
 * `customs-handsontable.tsx` when no active view is resolved (REQ-11 AC#7).
 *
 * Column-id picks come straight from REQ-11 AC#2. Each entry's
 * `visibleColumnIds` is asserted against `CUSTOMS_AVAILABLE_COLUMNS` in
 * `__tests__/customs-views.test.ts` so a typo here fails CI immediately.
 */
export const CUSTOMS_SYSTEM_VIEWS: readonly SystemView[] = [
  {
    id: "system:all",
    label: "Все колонки",
    is_system: true,
    visibleColumnIds: [
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
      "customs_antidumping",
      "customs_psm_pts",
      "customs_notification",
      "customs_licenses",
      "customs_eco_fee",
      "customs_honest_mark",
      "import_banned",
      "import_ban_reason",
      "license_ds_required",
      "license_ss_required",
      "license_sgr_required",
    ],
  },
  {
    id: "system:tariffs-nds",
    label: "Тарифы и НДС",
    is_system: true,
    visibleColumnIds: [
      "position",
      "product_code",
      "product_name",
      "hs_code",
      "supplier_country",
      "customs_duty_composite",
      "customs_antidumping",
      "customs_excise",
      "customs_util_fee",
      "customs_psm_pts",
    ],
  },
  {
    id: "system:documents",
    label: "Документы и сертификаты",
    is_system: true,
    visibleColumnIds: [
      "position",
      "product_code",
      "product_name",
      "hs_code",
      "supplier_country",
      "license_ds_required",
      "license_ss_required",
      "license_sgr_required",
      "customs_notification",
      "customs_licenses",
      "customs_eco_fee",
      "customs_honest_mark",
    ],
  },
  {
    id: "system:identification",
    label: "Только идентификация",
    is_system: true,
    visibleColumnIds: [
      "position",
      "brand",
      "product_code",
      "product_name",
      "quantity",
      "hs_code",
    ],
  },
] as const;

/**
 * Type guard — `true` when `id` follows the `system:*` synthetic-ID
 * pattern (REQ-11 AC#5 — URL parser uses this to choose between the
 * virtual constant lookup and the real `user_table_views` query).
 *
 * Accepts `null` / `undefined` so callers can forward URL params without
 * pre-checking — those simply collapse to `false`.
 */
export function isSystemViewId(
  id: string | null | undefined,
): id is `system:${string}` {
  return typeof id === "string" && id.startsWith("system:");
}

/**
 * Lookup a virtual system view by its synthetic ID. Returns `null` for
 * anything that isn't a known `system:*` row — including UUID rows from
 * `user_table_views` (callers must combine this with the real-views
 * `find(...)` in `customs-handsontable.tsx`).
 */
export function resolveSystemView(
  id: string | null | undefined,
): SystemView | null {
  if (!isSystemViewId(id)) return null;
  return CUSTOMS_SYSTEM_VIEWS.find((v) => v.id === id) ?? null;
}

/**
 * Default synthetic-view ID — used by the table resolver when no
 * `?customs_view=…` URL param is present (REQ-11 AC#7).
 *
 * Always points to `system:all` so the user sees every column on first
 * load. Returning the literal type lets TypeScript narrow callers that
 * compare against `'system:all'` directly.
 */
export function defaultSystemViewId(): "system:all" {
  return "system:all";
}

/**
 * Map a list of "visible" column ids back to the human-readable Russian
 * labels of the **hidden** columns — i.e. every entry in
 * `CUSTOMS_AVAILABLE_COLUMNS` whose key is not in `view.visibleColumnIds`.
 *
 * Output order follows the column order in `CUSTOMS_AVAILABLE_COLUMNS` so
 * the rendered hint stays stable as users switch views (REQ-11 AC#9 —
 * "comma-separated русские лейблы скрытых колонок").
 *
 * The `allColumns` parameter is injected (defaults to
 * `CUSTOMS_AVAILABLE_COLUMNS`) so tests can pass synthetic registries
 * without re-importing the production constant.
 */
export function getHiddenColumnLabels(
  view: SystemView,
  allColumns: ReadonlyArray<{ key: string; label: string }> = CUSTOMS_AVAILABLE_COLUMNS,
): string[] {
  const visible = new Set(view.visibleColumnIds);
  return allColumns
    .filter((col) => !visible.has(col.key))
    .map((col) => col.label);
}
