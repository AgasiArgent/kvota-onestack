/**
 * Centralised feature flags.
 *
 * Read from build-time env vars so flips require a redeploy. Cheap and
 * explicit — no runtime config service for now.
 */

/**
 * Master switch for the Alta-Soft API integrations:
 *   - "По названию"            (POST /api/customs/classify)        — Phase 2
 *   - "Автоподбор ставок"      (POST /api/customs/resolve-rates)   — Phase 1
 *   - "Регуляторная справка"   (POST /api/customs/non-tariff-measures) — Phase 1
 *
 * When `false`, the UI hides every Alta-driven control so customs-specialist
 * doesn't see broken buttons during Alta-side outages or when the prepaid
 * packet pool is empty. The country-of-origin dropdown and certificate
 * checkboxes remain — they're static data and still useful for manual entry.
 *
 * Flip via `NEXT_PUBLIC_ALTA_FEATURES_ENABLED=true` in the deploy env.
 * Default off so a fresh deploy doesn't accidentally surface broken UI.
 */
export const ALTA_FEATURES_ENABLED =
  process.env.NEXT_PUBLIC_ALTA_FEATURES_ENABLED === "true";
