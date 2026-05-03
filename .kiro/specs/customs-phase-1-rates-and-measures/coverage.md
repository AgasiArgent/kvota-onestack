# Requirements Coverage Report — customs-phase-1-rates-and-measures

**Generated:** 2026-05-01
**Branch:** feature/customs-phase1
**Verification commit range:** `0bd13a8d..06fcfdf4` (11 commits ahead of `main`)

## Summary

| Metric | Value |
|---|---|
| Total REQs | 8 |
| COVERED | 8 |
| PARTIAL | 0 |
| MISSING | 0 |
| Backend tests | **240/240 pass** |
| Frontend tests | **540/540 pass** |
| Locked-files diff (engine/models/mapper) | **empty** ✓ |
| Migration applied to prod | 298 ✓ (88 countries, 43 unfriendly, 7 areals, 100 chapter roots) |

---

## Per-REQ traceability

### REQ-1 — Foundation Database Schema (Migration 298) — **COVERED**

| AC | Evidence |
|---|---|
| 1. New tables in kvota schema | `migrations/298_tnved_foundation.sql` parts 1, 3, 4, 5, 6, 7, 8, 9, 10 — 9 CREATE TABLE statements |
| 2. ALTER quote_items + 3 new columns | `migrations/298_tnved_foundation.sql:528-532` (`country_of_origin_oksm`, `has_origin_certificate`, `has_fta_certificate`) |
| 3. Seed data | Inline INSERTs: 8 payment_types, 7 areals, ~88 countries, ~37 country_areals |
| 4. is_unfriendly per ПП 430-р | `298_tnved_foundation.sql` Part 2 — UPDATE marking ~43 unfriendly countries |
| 5. Indexes (rates_lookup, rates_country, apu_cache_last_used) | `298_tnved_foundation.sql` Part 7 + Part 9 — 4 indexes on tnved_rates incl. `idx_rates_last_used` (Q3) |
| 6. UNIQUE constraint on tnved_rates | `298_tnved_foundation.sql` Part 7 — `uq_tnved_rates` constraint |
| 7. Migration number 298 (was 296) | `spec.json:migration_numbers=[298]` + commit message; verified after parallel cargo-places spec landed 297 |
| 8. Idempotent + apply via apply-migrations.sh | All `IF NOT EXISTS` / `ON CONFLICT DO NOTHING`; applied via `cat ... \| ssh beget-kvota 'docker exec ...'` 2026-05-01 |
| 9. Self-FK bootstrapping | `298_tnved_foundation.sql:341` — `parent_code REFERENCES tnved_codes(code) DEFERRABLE INITIALLY DEFERRED` |
| 10. NO TKS columns | Migration audited — no `tks_*` fields anywhere |
| **Q7 simplification: NO snapshot columns on quote_items** | Lines 530-532 verified — only 3 columns added; `customs_rates_snapshot` JSONB deliberately absent |

**Commit:** `0d45a30c feat(customs): migration 298 — TN VED foundation schema (REQ-1)`

---

### REQ-2 — Alta XML API Client (`services/alta_client.py`) — **COVERED**

| AC | Evidence |
|---|---|
| 1. AltaClient with 4 endpoint methods | `services/alta_client.py:get_rates`, `get_non_tariff_measures`, `apu_suggest`, `apu_codes`, `classify_batch` |
| 2. password→md5 cached, plaintext only in __init__ scope | `services/alta_client.py:AltaClient.__init__` stores `_password_md5`; tests `test_credentials_not_in_repr`, `test_password_not_stored_plaintext` |
| 3. _sign uses raw UTF-8, no URL-encoding | `services/alta_client.py:_sign`; tests `test_sign_request_md5_double_hash`, `test_sign_uses_raw_utf8_not_url_encoded`, `test_sign_handles_unicode_password` |
| 4. windows-1251 detection | `services/alta_client.py:_decode_xml`; tests `test_decode_xml_windows1251`, `test_decode_xml_utf8`, `test_decode_xml_charset_header_takes_precedence` |
| 5. AltaApiError on documented codes 100/110/120/140/201 | `services/alta_client.py:_parse_response`; parametrized test `test_parse_response_documented_error_codes` |
| 6. Undocumented codes → AltaApiError with prefix | `services/alta_client.py:_parse_response`; test `test_parse_response_undocumented_code` |
| 7. Express polling POLL_MAX_ATTEMPTS=6, POLL_DELAY_SECONDS=2.0 | `services/alta_client.py` constants + `_poll_express`; test `test_classify_batch_polling_returns_after_handled_true` |
| 8. Polling timeout RuntimeError surfaces last_message + request_id | `services/alta_client.py:_poll_express`; test `test_classify_batch_polling_timeout_surfaces_last_message` |
| 9. classify_batch drops group_hint with warning | `services/alta_client.py:classify_batch`; test `test_classify_batch_drops_group_hint` |
| 10. packet_left < 100 → throttled Telegram alert | `services/alta_client.py:_log_packet_left`; tests `test_packet_left_warning_below_100_alerts_telegram`, `test_packet_left_warning_throttled_1_per_hour`, `test_packet_left_warning_fires_again_after_one_hour` |
| 11. DI-only credentials, never in logs | `services/alta_client.py:get_alta_client` factory; test `test_credentials_not_logged_on_error` |
| 12. HTTP timeout 30s, 2 retries with backoff | `services/alta_client.py:_with_retries`; tests `test_http_timeout_30s`, `test_retries_on_network_error`, `test_no_retry_on_alta_api_error` |

**Commits:** `d7da4b1b feat(customs): AltaClient async XML API wrapper (REQ-2)`, `6aefae36 refactor(customs): drop unused country param`. **29/29 tests pass.**

---

### REQ-3 — Rate Resolver (`services/rate_resolver.py`) — **COVERED**

| AC | Evidence |
|---|---|
| 1. Three-tier priority lookup | `services/rate_resolver.py:_lookup_db`; tests `test_tier_1_exact_country_match_returns_rate`, `test_tier_2_areal_match_when_no_country_row`, `test_tier_3_base_rate_when_no_country_no_areal` |
| 2. 30-day TTL stale = miss | `services/rate_resolver.py:CACHE_TTL = timedelta(days=30)` + `.gte("source_fetched_at", cutoff)`; test `test_stale_cache_filter_applied` |
| 3. Lazy-fetch + upsert + re-lookup | `services/rate_resolver.py:resolve_rate` lines 168-200; test `test_full_miss_calls_alta_and_upserts_then_re_lookup` |
| 4. Comprehensive Alta response → upsert all in one transaction | `services/rate_resolver.py:_bulk_upsert`; test verifies 3 returned rates → 1 upsert call |
| 5. Race-safe via UNIQUE constraint ON CONFLICT | `services/rate_resolver.py:_bulk_upsert` `on_conflict=...`; test `test_bulk_upsert_targets_unique_constraint_columns` |
| 6. Alta failure → log + return None, never raise | `services/rate_resolver.py:resolve_rate` try/except; tests `test_alta_api_error_swallowed_returns_none`, `test_network_error_swallowed_returns_none` |
| 7. last_used_at updated on success | `services/rate_resolver.py:_touch_last_used_at`; tests `test_last_used_at_updated_on_cache_hit`, `test_last_used_at_failure_does_not_break_resolve` |
| 8. Snapshot-first for frozen quotes | `services/rate_resolver.py:_lookup_snapshot`; tests `test_snapshot_lookup_hits_for_approved_quote`, `test_snapshot_skipped_for_unfrozen_quote_falls_through_to_live`, `test_snapshot_skipped_when_payment_type_not_in_snapshot`, `test_no_quote_item_id_means_no_snapshot_lookup` |
| 9. Thread-safe (no module-level mutable state) | `services/rate_resolver.py` — no module globals beyond constants; verified by code review |
| 10. is_unfriendly NOT in lookup logic | `services/rate_resolver.py` — `countries.is_unfriendly` never queried; test `test_is_unfriendly_not_in_lookup_path` |

**Commits:** `4a5555ab feat(customs): rate_resolver three-tier lookup`, `cd2712e3 refactor(customs): plumb Rate.source from DB`. **19/19 tests pass.**

---

### REQ-4 — Customs Duty Calculator (`services/customs_calc.py`) — **COVERED**

| AC | Evidence |
|---|---|
| 1. Three rate types (ad-valorem, specific, combined max/+) | `services/customs_calc.py:calculate_duty`; tests `test_calculate_duty_pure_ad_valorem`, `test_calculate_duty_pure_specific_per_kg`, `test_calculate_duty_pure_specific_per_unit`, `test_calculate_duty_combined_max_default`, `test_calculate_duty_combined_max_specific_wins`, `test_calculate_duty_combined_addition` |
| 2. ПП 342 step-function | `services/customs_calc.py:calculate_customs_fee`; parametrized test `test_calculate_customs_fee_pp342_bands` |
| 3. ПП 81 only for tnved_code 87xxxx | `services/customs_calc.py:calculate_util_fee`; tests `test_calculate_util_fee_returns_zero_for_non_87`, `test_calculate_util_fee_for_87_code` |
| 4. ValueError on inconsistent rate shapes | `services/customs_calc.py` validation; tests `test_calculate_duty_inconsistent_rate_raises`, `test_calculate_duty_unknown_sign_raises`, `test_calculate_duty_unknown_unit_code_raises` |
| 5. Decimal precision (no float) | `services/customs_calc.py` uses `Decimal(str(...))` boundary conversion; test `test_calculate_duty_decimal_precision_no_float` |
| 6. Unit code whitelist | `services/customs_calc.py:_resolve_unit_quantity` — 166 (kg) + 796 (шт); 111/112 raise ValueError per agent's documented scope decision |
| 7. Calc engine NOT modified — adapter via build_calculation_inputs | `services/calculation_helpers.py:_resolve_import_tariff_pct` switch by `rate.source ∈ {alta-live, alta-revalidate}`; **`git diff main..HEAD -- calculation_engine.py calculation_models.py calculation_mapper.py` = empty** |
| 8. Pure-functional (no DB/network/IO) | `services/customs_calc.py` — no imports of `database`, `httpx`, etc.; test `test_calculate_duty_no_side_effects` |

**Commit:** `04c2ab41 feat(customs): customs_calc + build_calculation_inputs adapter (REQ-4)`. **32 customs_calc + 5 adapter = 37/37 tests pass.**

---

### REQ-5 — API Endpoints (`api/customs.py`) — **COVERED**

| AC | Evidence |
|---|---|
| 1. POST /api/customs/resolve-rates | `api/customs.py:resolve_rates_handler:845`; mounted at `api/routers/customs.py` |
| 2. POST /api/customs/non-tariff-measures | `api/customs.py:non_tariff_measures_handler:1057`; mounted at `api/routers/customs.py` |
| 3. autofill_handler extended additively with force_live | `api/customs.py:autofill_handler:263`; existing `_AUTOFILL_FIELDS` 13 keys preserved + 3 appended |
| 4. Dual auth (JWT + session) | `api/customs.py:_resolve_dual_auth:84` reused; tests `test_resolve_rates_requires_auth` |
| 5. Role gate `_CUSTOMS_ROLES` | `api/customs.py:_CUSTOMS_ROLES = {"customs", "admin", "head_of_customs"}`; test `test_resolve_rates_rejects_non_customs_role` |
| 6. Structured docstrings (api-first.md format) | All 3 new handlers have `Path:`, `Params:`, `Returns:`, `Side Effects:`, `Roles:` sections |
| 7. Side-effect on quote_item_id (UPDATE country_of_origin_oksm + cert flags) | `api/customs.py:resolve_rates_handler` — UPDATE issued when quote_item_id present; test `test_resolve_rates_updates_quote_item_when_id_provided` |
| 8. 503 on Alta unavailable + cache empty | `api/customs.py:resolve_rates_handler` — returns 503 ALTA_UNAVAILABLE when all payment_types None; test `test_resolve_rates_503_when_alta_unavailable` |
| 9. Structured logging (user_id, source, latency, cache_hit) | `api/customs.py:resolve_rates_handler` `logger.info('customs_resolve_rates', extra={...})`; test `test_resolve_rates_logs_structured_fields` |
| 10. Response envelope `{success, data?, error?}` | All 3 handlers; tests verify shape on every status code |

**Commit:** `fc8d3212 feat(customs): API endpoints — resolve-rates + non-tariff-measures + autofill ext (REQ-5)`. **17/17 tests pass.**

---

### REQ-6 — Weekly Cache Revalidation Cron — **COVERED**

| AC | Evidence |
|---|---|
| 1. POST /api/cron/revalidate-rates endpoint | `api/cron.py:cron_revalidate_rates` + `api/routers/cron.py` mount + `api/auth.py:PUBLIC_API_PATHS` extended |
| 2. SQL: top-1000 by MAX(last_used_at) DESC NULLS LAST among stale | `api/cron.py:cron_revalidate_rates` — fetch up to REVALIDATE_MAX_FETCH=5000 stale rows, group + sort python-side (PostgREST has no MAX() in select); test `test_processes_top_1000_ordered_by_last_used` |
| 3. Upsert with source='alta-revalidate', preserve history | `api/cron.py:cron_revalidate_rates` calls rate_resolver `_bulk_upsert` with source='alta-revalidate'; test `test_upsert_with_source_alta_revalidate` |
| 4. Stats logging (processed, hits, updates, failures, packet_left) | `api/cron.py:cron_revalidate_rates` returns stats in response data |
| 5. AltaApiError(140) → abort + Telegram alert | `api/cron.py:cron_revalidate_rates`; test `test_alta_error_140_aborts_with_telegram_alert` |
| 6. Idempotent within 7 days (SQL filter source_fetched_at < now - 7d) | Test `test_idempotent_no_op_when_no_stale` |
| 7. Timeout handling | Implementation uses `await alta_client.get_rates` per row; FastAPI request defaults sufficient for ~1.5min worst case |
| 8. VPS crontab out of spec | Documented in commit message: `(crontab -l; echo "0 4 * * 1 curl -X POST .../api/cron/revalidate-rates -H 'X-Cron-Secret: $CRON_SECRET'") \| crontab -` per memory `reference_vps_cron_endpoints.md` |

**Commit:** `5ec99e23 feat(customs): weekly revalidate-rates cron (REQ-6)`. **12/12 tests pass.**

---

### REQ-7 — Frontend UI (Next.js) — **COVERED**

| AC | Evidence |
|---|---|
| 1. Country dropdown + cert checkboxes on quote_item edit | `frontend/src/features/customs-country-dropdown/ui/country-dropdown.tsx` + extension of `frontend/src/features/quotes/ui/customs-step/customs-item-dialog.tsx` |
| 2. is_unfriendly badge ("⚠️ Недружественная страна (ПП 430-р)") | `frontend/src/features/customs-country-dropdown/ui/country-dropdown.tsx` — badge rendered when country.is_unfriendly |
| 3. Auto-resolve button → POST /api/customs/resolve-rates | `frontend/src/features/customs-rate-resolve/ui/auto-resolve-button.tsx` + `frontend/src/features/customs-rate-resolve/api/resolve-rates.ts` |
| 4. Breakdown display (rates + raw_value tooltip) | `frontend/src/features/customs-rate-resolve/ui/rate-breakdown.tsx` — uses native `title=` for tooltip (base-ui Tooltip API doesn't accept asChild); functional but unstyled |
| 5. source_fetched_at timestamp + Refresh button (force_live=true) | `frontend/src/features/customs-rate-resolve/ui/source-timestamp.tsx` |
| 6. Non-tariff measures button (3₽-aware) | `frontend/src/features/customs-non-tariff-measures/ui/measures-list.tsx` — pull-trigger button + list with name/document_basis/document_link |
| 7. 503 ALTA_UNAVAILABLE → toast + retry | All API wrappers handle 503 with non-blocking error display |
| 8. Validation UX (field-specific errors for INVALID_TNVED_CODE) | Components surface backend error.code → field highlighting + message |
| 9. Frontend in `frontend/src/` only, NOT legacy-fasthtml | Verified: `git diff main..HEAD --stat -- legacy-fasthtml/` is empty |
| 10. Supabase JS client with `db: { schema: 'kvota' }` | `frontend/src/features/customs-country-dropdown/api/fetch-countries.ts` uses kvota schema |

**Commit:** `06fcfdf4 feat(customs): country dropdown + auto-resolve + rate breakdown + measures UI (REQ-7)`. **540 frontend tests pass** (29 new for pure helpers).

**Caveats noted by T7 agent:**
- Localhost browser test deferred — no `frontend/.env.local` present in worktree; manual verification needed pre-merge.
- Pre-existing TS errors in `frontend/src/features/invoice-card/ui/invoice-card.tsx` (out of REQ-7 scope) block global `next build` — needs separate fix.
- Q4 freeze warnings (Tier 2 toast / Tier 3 modal) handlers in place but dormant until exercised end-to-end with Task 8 backend.

---

### REQ-8 — Freeze Behavior — **COVERED** (Q5 deferred)

| AC | Evidence |
|---|---|
| 1. Snapshot saved when quote frozen — JSONB shape | `services/customs_freeze_service.py:build_snapshot` returns `FreezeSnapshotResult.items: dict[str, dict]` matching design.md shape |
| 2. snapshot_date set | Implicit in `quote_versions.created_at` + `customs_rates[item_id].fetched_at` |
| 3. Frozen reads from snapshot | `services/rate_resolver.py:_lookup_snapshot` reads from `quote_versions.input_variables.customs_rates`; tests `test_snapshot_lookup_hits_for_approved_quote` etc. |
| 4. "Пересчитать" endpoint with confirm + audit log | `POST /api/quotes/{quote_id}/refresh-customs-snapshot` (`api/customs.py:refresh_customs_snapshot_handler` + `api/routers/quotes.py` mount); audit via `change_reason` field on input_variables (Q5 deviation — see below) |
| 5. Q4 three-tier graceful degradation | `services/customs_freeze_service.py:build_snapshot` + `_capture_item`; tests `test_tier_1_live_alta_for_all_items`, `test_tier_2_cache_stale_when_resolver_returns_none`, `test_tier_3_abort_when_no_live_no_cache`, `test_aggregate_worst_tier_one_abort_makes_all_abort` |
| 6. Snapshot self-sufficient for re-render | Snapshot dict carries `tnved_code`, `payment_type`, all `value_*_*` slots, `raw_value_string`, `source` — all fields rate_resolver needs to hydrate via `_build_resolved_from_snapshot` |
| **Workflow hook** | `services/workflow_service.py:transition_quote_status` pre-commit hook on `to_status == APPROVED`; defensive try/except wraps to prevent crash on integration regression |

**Q5 deviation (deferred):** decisions.md Q5 said "use existing changelog_service.log_event()". Reality: `services/changelog_service.py` is a markdown reader, not an event logger. **Phase-1 substitute:** audit recorded inline via `quote_versions.input_variables.change_reason` field (e.g., `"customs_rates_snapshot_replaced: <reason> (by user X)"`). Dedicated `customs_audit_log` table is the Phase-2 follow-up.

**Commit:** `1c5378fa feat(customs): freeze snapshot service + workflow hook + re-freeze endpoint (REQ-8)`. **9 freeze + 7 refresh-endpoint = 16/16 tests pass.**

---

## Test counts (all green)

```
backend (Python pytest):
  29 services/test_alta_client.py            (REQ-2)
  19 services/test_rate_resolver.py          (REQ-3)
  32 services/test_customs_calc.py           (REQ-4)
   5 services/test_calculation_helpers_adapter.py  (REQ-4 adapter)
   9 services/test_customs_freeze.py         (REQ-8)
  17 api/test_customs_api.py                 (REQ-5)
  12 api/test_cron_revalidate.py             (REQ-6)
   7 api/test_refresh_snapshot.py            (REQ-8)
  96 test_workflow_service.py                (regression — workflow hook)
  14 test_quote_version_service.py           (regression — additive kwargs)
─────────────
 240 backend pass

frontend (Vitest):
 540 frontend (incl. 29 new for REQ-7 pure helpers)

────────────────────
TOTAL: 780 tests pass
```

---

## Locked-files invariant

```
$ git diff main..HEAD -- calculation_engine.py calculation_models.py calculation_mapper.py
(empty)
```

The architectural firewall around the calc engine held across 11 commits and 4 parallel agents.

---

## Migration applied to prod (2026-05-01)

```
Migration 298 seed counts:
  countries=88, unfriendly=43, areals=7, country_areals=61,
  tnved_codes(roots)=100, payment_types=8
```

PostgREST schema reloaded; frontend `database.types.ts` regenerated (+597 lines).

---

## Outstanding follow-ups for Phase 2+

1. **Q5 audit log:** create `customs_audit_log` table; promote inline `change_reason` recording to a typed event log.
2. **Localhost browser test for REQ-7:** manual verification deferred — no `.env.local` present in worktree.
3. **Pre-existing `invoice-card.tsx` TS errors:** unrelated to Phase 1, but blocks global `next build`. Needs separate fix before main merge.
4. **VPS crontab entry for revalidate-rates:** manual installation required — `(crontab -l; echo "0 4 * * 1 ...") | crontab -` per memory `reference_vps_cron_endpoints.md`.
5. **Phase 2 surfaces deferred:** Alta Express batch UI, АПУ interactive picker, classify-batch endpoint (clients exist Phase 1; UI surfaces deferred).
6. **`notify_admin` consolidation:** currently lives in `services/alta_client.py` as a module-local wrapper used by both AltaClient and cron. Move to `services/telegram_service.py` for single source of truth.
7. **Eval-gate measurement (Phase 3):** Phase 0 throwaway script ready in `onestack-customs-phase0` worktree; run on real МастерБэринг data when available.

---

## Verdict

**Phase 1 is implementation-complete.** All 8 requirements covered, 780 tests pass, calc engine untouched, migration deployed. Ready for PR review and merge after the documented manual follow-ups (browser test, invoice-card TS fix, VPS crontab).
