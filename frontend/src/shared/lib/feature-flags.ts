/**
 * Centralised feature flags.
 *
 * Read from build-time env vars so flips require a redeploy. Cheap and
 * explicit — no runtime config service for now.
 */

/**
 * Master switch for ALL Alta-driven customs automation UI — direct Alta calls
 * AND the project-history suggestion banners that surface prior Alta-resolved
 * choices for re-use:
 *
 * Direct Alta API surfaces:
 *   - "По названию"            (POST /api/customs/classify)        — Phase 2
 *   - "Автоподбор ставок"      (POST /api/customs/resolve-rates)   — Phase 1
 *   - "Регуляторная справка"   (POST /api/customs/non-tariff-measures) — Phase 1
 *   - "Обновить" force-live refresh on rate timestamp                  — Phase 1
 *   - Auto/Manual rate-entry mode toggle (`showAutoToggle`)            — Phase 1
 *
 * Suggestion UI (reads project history; not direct Alta calls, but the copy
 * literally mentions Alta and the workflow is conceptually paired):
 *   - `<AutofillBanner>` — top-of-table "N из M автозаполнены из истории"
 *   - `<HistoryBanner>`  — per-item "Заполнено из истории от {date} ({email})"
 *   - `customs-autofill-row` — handsontable row highlight for items with
 *                              autofill suggestions (driven by the empty
 *                              `autofillSuggestions` array when this flag is off)
 *
 * When `false`, the customs flow is purely manual — no Alta calls fire, no
 * suggestion banners render, no row highlights appear. The country-of-origin
 * dropdown, certificate checkboxes, and Phase B `<CertificatesSection>`
 * (cost_rub / valid_until / M:N junction) remain — they're static / manual
 * data layers and still useful without the automation layer.
 *
 * Flip via `NEXT_PUBLIC_ALTA_FEATURES_ENABLED=true` in the deploy env.
 * Default off so a fresh deploy doesn't accidentally surface broken UI
 * during Alta outages, packet-pool exhaustion, or staged rollout.
 */
export const ALTA_FEATURES_ENABLED =
  process.env.NEXT_PUBLIC_ALTA_FEATURES_ENABLED === "true";
