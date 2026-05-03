# Implementation Tasks — Customs Phase 1: ставки + меры

> **For agentic workers:** Execute tasks per dependency graph. Each task is independently commitable. Each commit touches ONLY the files its task explicitly changes — use `git add <explicit-paths>`, never `git add .` or `-A`. All commits include `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` footer.

**Spec references:**
- Requirements: `.kiro/specs/customs-phase-1-rates-and-measures/requirements.md`
- Design: `.kiro/specs/customs-phase-1-rates-and-measures/design.md`
- Decisions: `.kiro/specs/customs-phase-1-rates-and-measures/decisions.md`
- Research: `.kiro/specs/customs-phase-1-rates-and-measures/research.md`
- Gap analysis: `.kiro/specs/customs-phase-1-rates-and-measures/gap-analysis.md`
- Scope doc: `docs/plans/2026-04-22-customs-ved-integration-handoff.md`

**Locked files (NEVER modify):** `calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py`

**Parallel marker `(P)`:** Tasks marked `(P)` can run concurrently with the prior `(P)`-marked task in the same wave (no shared files, no sequential dependency).

**Worktree:** `/Users/andreynovikov/workspace/tech/projects/kvota/onestack-customs-phase1` on branch `feature/customs-phase1`.

---

## Wave 1 — Foundation (parallel)

### Task 1: Migration 298 — TN VED foundation schema (P)

**Requirements:** 1
**Dependencies:** none

**Files:**
- Create: `migrations/298_tnved_foundation.sql`
- Create: `migrations/298_seed_oksm_countries.csv` (~250 rows from Росстандарт ОКСМ)
- Modify: `frontend/src/shared/types/database.types.ts` (regenerated)

**Steps:**
- [x] Verify migration number 298 still free immediately before write: `ls migrations/29[0-9]*.sql migrations/30*.sql` — confirmed 2026-05-01 (297 was taken by `297_relax_cargo_places_constraints.sql` merged from cargo-places work; 298 is the first free slot)
- [ ] Write `migrations/298_tnved_foundation.sql` with full DDL from `design.md` § "Data Model — Migration 298":
  - 9 CREATE TABLE: `countries`, `areals`, `country_areals`, `tnved_codes`, `payment_types`, `tnved_rates` (with `last_used_at` per Q3), `tnved_non_tariff_measures`, `tnved_apu_cache`, `tnved_classification_log`
  - 3 ALTER quote_items: `country_of_origin_oksm`, `has_origin_certificate`, `has_fta_certificate` (DROPPED `customs_rates_snapshot` columns per Q7)
  - `parent_code` self-FK as `DEFERRABLE INITIALLY DEFERRED`
  - 4 indexes: `idx_rates_lookup`, `idx_rates_country`, `idx_rates_last_used`, `idx_apu_cache_last_used`
  - UNIQUE constraint on `tnved_rates(tnved_code, payment_type, country_or_areal, valid_from, certificate_required, sp_certificate_required)`
- [ ] Prepare `298_seed_oksm_countries.csv` from Росстандарт ОКСМ (oksm_digital, iso_alpha2, iso_alpha3, name_ru, name_en)
- [ ] Embed inline seeds in SQL: 8 `payment_types`, 7 `areals`, ~80 `country_areals` mappings, ~50 `is_unfriendly` UPDATEs per ПП 430-р with comment `-- дата фиксации: 2026-05-01, обновлять вручную`
- [ ] Apply via SSH: `cat migrations/298_tnved_foundation.sql | ssh beget-kvota 'docker exec -i supabase-db psql -U postgres -d postgres -v ON_ERROR_STOP=1'` then `\copy` for OKSM CSV
- [ ] Verify tables: `ssh beget-kvota "docker exec supabase-db psql -U postgres -d postgres -c '\\dt kvota.tnved_*'"` — expect 5 rows
- [ ] Verify seeds: COUNT queries on payment_types (=8), areals (=7), countries (~250)
- [ ] Verify quote_items columns: `\d kvota.quote_items | grep -E 'country_of_origin_oksm|has_(origin|fta)_certificate'` — expect 3 rows
- [ ] Verify NO `customs_rates_snapshot` columns added (Q7 simplification)
- [ ] Record in `kvota.migrations` tracking table
- [ ] Reload PostgREST: `NOTIFY pgrst, 'reload schema'`
- [ ] Regenerate frontend types: `cd frontend && npm run db:types`
- [ ] Verify type regen: `grep -q tnved_rates frontend/src/shared/types/database.types.ts && echo OK`
- [ ] Commit migration + CSV + regenerated types

---

### Task 2: AltaClient skeleton (`services/alta_client.py`) (P)

**Requirements:** 2
**Dependencies:** none (can run parallel with Task 1)

**Files:**
- Create: `services/alta_client.py`
- Create: `tests/services/test_alta_client.py`

**Steps:**
- [ ] Write `tests/services/test_alta_client.py` red-tests covering REQ-2 acceptance criteria: MD5 sign correctness (raw UTF-8, NOT URL-encoded — gotcha #1), windows-1251 detection (gotcha #2), error code recognition (100/110/120/140/201), undocumented numeric code surfacing, polling timeout with `last_message` in RuntimeError, packet `left_count < 100` warning, credentials never in repr/logs/exceptions
- [ ] Lift Phase 0 functions from `/Users/andreynovikov/workspace/tech/projects/kvota/onestack-customs-phase0/scripts/phase0_eval_alta_express.py`: `sign_request` → `_sign`, `build_request_xml`, `parse_response`, `AltaApiError`, `POLL_MAX_ATTEMPTS = 6`, `POLL_DELAY_SECONDS = 2.0`
- [ ] Implement `class AltaClient` with async methods: `get_rates`, `get_non_tariff_measures`, `apu_suggest`, `apu_codes`, `classify_batch` — sync→async via `httpx.AsyncClient`
- [ ] Implement `_decode_xml(resp)` — windows-1251/UTF-8 detection through response charset → XML declaration → fallback windows-1251 for Такса
- [ ] Implement `_log_packet_left()` — emit warning at `left_count < 100`, throttle 1/hour, route through `services/telegram_service.notify_admin()` (Q2)
- [ ] Implement `def get_alta_client() -> AltaClient` factory — module-level lazy singleton from `os.environ['ALTA_LOGIN'/'ALTA_PASSWORD']`, plaintext password lives only in constructor scope (REQ-2 AC#2)
- [ ] Implement `classify_batch` ignoring XML `group=` attribute, log warning if `group_hint` passed (REQ-2 AC#9)
- [ ] HTTP timeout 30.0s, 2 max retries with backoff (1s, 2s) for network errors
- [ ] Run `pytest tests/services/test_alta_client.py -v` — expect all green
- [ ] Commit `services/alta_client.py` + tests

---

## Wave 2 — Service layer (parallel)

### Task 3: Rate resolver (`services/rate_resolver.py`) (P)

**Requirements:** 3
**Dependencies:** Task 1 (migration), Task 2 (AltaClient)

**Files:**
- Create: `services/rate_resolver.py`
- Create: `tests/services/test_rate_resolver.py`

**Steps:**
- [ ] Write red-tests: three-tier priority lookup (exact country → areal → base), 30-day TTL stale detection, race-safe `ON CONFLICT DO UPDATE`, comprehensive Alta response upserts all payment_types in one transaction, `last_used_at` updated on success, snapshot lookup for frozen quotes via `quote_versions.input_variables.customs_rates`, `is_unfriendly` NOT used in lookup (REQ-3 AC#10)
- [ ] Implement `async def resolve_rate(db, tnved_code, payment_type, country_oksm, date, has_certificate=False, *, alta_client, quote_item_id=None) -> Rate | None`
- [ ] Implement snapshot-first branch: if `quote_item_id` and `quote.status >= APPROVED`, read from `quote_versions.input_variables.customs_rates[quote_item_id]` (Q7 simplification)
- [ ] Implement Tier 1 (exact country `C:{oksm}`), Tier 2 (loop areals from `country_areals`), Tier 3 (base `country_or_areal IS NULL`)
- [ ] Implement lazy-fetch fallback: call `alta_client.get_rates(...)`, upsert all returned rows in one transaction with `ON CONFLICT (tnved_code, payment_type, country_or_areal, valid_from, certificate_required, sp_certificate_required) DO UPDATE`
- [ ] Implement fire-and-forget `UPDATE tnved_rates SET last_used_at = now() WHERE id = $1` after successful lookup (Q3)
- [ ] Return `None` on Alta network error / 5xx — log ERROR, never raise to caller (REQ-3 AC#6)
- [ ] Thread-safety: no module-level mutable state, use passed `db` connection only
- [ ] Run pytest, expect green
- [ ] Commit

---

### Task 4: Customs duty calculator (`services/customs_calc.py`) + adapter (P)

**Requirements:** 4
**Dependencies:** Task 1 (migration for Rate dataclass shape)

**Files:**
- Create: `services/customs_calc.py`
- Modify: `services/calculation_helpers.py` — extend `build_calculation_inputs()` ONLY (adapter switch by `rate.source`)
- Create: `tests/services/test_customs_calc.py`
- **DO NOT TOUCH:** `calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py` (project rule, verify diff is empty before commit)

**Steps:**
- [ ] Write red-tests: pure ad-valorem (`percent`), pure specific (per-kg/per-l/per-шт with currency conversion), combined `max(адвалорная, специфическая)` for `sign_1='>'` (gotcha #3), combined `+` for `sign_1='+'`, ПП 342 step-function bands, ПП 81 only for `tnved_code` starting with `87`, ValueError on inconsistent rate shapes, Decimal precision (no float), unit code whitelist (166/111/796)
- [ ] Implement `calculate_duty(rate, customs_value_rub, weight_kg, quantity, currency_rates) -> Decimal` — pure-functional, no side effects (REQ-4 AC#8)
- [ ] Implement `calculate_customs_fee(customs_value_rub) -> Decimal` — ПП 342 step-function with hardcoded bands, comment `# verified 2026-05-01, проверять раз в год`
- [ ] Implement `calculate_util_fee(tnved_code, engine_volume_cc, vehicle_age_years) -> Decimal` — return `Decimal('0')` if not `87xxxx`
- [ ] Modify `services/calculation_helpers.py:build_calculation_inputs()` — add Q1 switch: if `rate.source ∈ {'alta-live', 'alta-revalidate'}` → call `customs_calc.calculate_duty()` and set `inputs['customs_duty']`, `inputs['customs_duty_per_kg'] = Decimal('0')`. Else fall through to existing legacy formula. Comment legacy path: `# legacy combined-rate, sunset при переводе всех quote_items на Alta-resolved (Phase 5+)`
- [ ] Verify `git diff calculation_engine.py calculation_models.py calculation_mapper.py` is empty
- [ ] Run pytest, expect green
- [ ] Commit `services/customs_calc.py` + `services/calculation_helpers.py` + tests

---

## Wave 3 — API layer (sequential)

### Task 5: Customs API endpoints

**Requirements:** 5
**Dependencies:** Task 3 (rate_resolver), Task 4 (customs_calc adapter)

**Files:**
- Modify: `api/customs.py` — add `resolve_rates_handler`, `non_tariff_measures_handler`; extend `autofill_handler` with `force_live` flag and additive response fields
- Modify: `api/routers/customs.py` — mount `POST /resolve-rates`, `POST /non-tariff-measures`
- Modify: `frontend/src/features/customs-autofill/types.ts` — extend `CustomsAutofillSuggestion` (additive optional fields only)
- Create: `tests/api/test_customs_api.py`

**Steps:**
- [ ] Write red-tests: dual-auth (JWT `request.state.api_user` + legacy session), role gate via `_CUSTOMS_ROLES`, response envelope `{success, data?, error?}`, error codes `UNAUTHORIZED`/`FORBIDDEN`/`ALTA_UNAVAILABLE`/`INVALID_TNVED_CODE`/`INVALID_OKSM`, 503 on Alta down + cache empty, side-effect on `quote_item_id` updates `country_of_origin_oksm`+customs fields, structured logging with `(user_id, tnved_code, country_oksm, source, latency_ms, cache_hit)`, backwards-compat `_AUTOFILL_FIELDS` (only additive new keys, never rename existing)
- [ ] Implement `resolve_rates_handler` with `client: AltaClient = Depends(get_alta_client)` (Q6) — call `rate_resolver.resolve_rate()`, optionally UPDATE quote_items on `quote_item_id`, return rates + total_rub + source + fetched_at
- [ ] Implement `non_tariff_measures_handler` — call `alta_client.get_non_tariff_measures()`, return measures list. **Only invoked from explicit UI request** (gotcha #5: 3₽/call separate billing)
- [ ] Extend `autofill_handler`: optional `force_live: bool` body param — if True, bypass cache and call `rate_resolver` with fresh fetch; extend response with new optional fields (`country_of_origin_oksm`, `customs_rates_source`, `customs_rates_fetched_at`)
- [ ] Add structured docstrings (api-first.md format): `Path:`, `Params:`, `Returns:`, `Side Effects:`, `Roles:` for each new handler
- [ ] Mount routes in `api/routers/customs.py` — thin wrappers calling handlers
- [ ] Sync TS interface `frontend/src/features/customs-autofill/types.ts` — add new fields as `?:` optional, never rename existing
- [ ] Run pytest, expect green
- [ ] Commit

---

## Wave 4 — Cron + Frontend (parallel)

### Task 6: Weekly cache revalidation cron (P)

**Requirements:** 6
**Dependencies:** Task 2 (AltaClient), Task 3 (rate_resolver upsert helpers)

**Files:**
- Modify: `api/cron.py` — add `cron_revalidate_rates`
- Modify: `api/routers/cron.py` — mount `POST /revalidate-rates`
- Modify: `api/auth.py` — append `/api/cron/revalidate-rates` to `PUBLIC_API_PATHS`
- Create: `tests/api/test_cron_revalidate.py`

**Steps:**
- [ ] Write red-tests: `X-Cron-Secret` header validation, top-1000 selection ordered by `MAX(last_used_at) DESC NULLS LAST` filtered to `source_fetched_at < now() - interval '7 days'`, idempotent re-run within 7 days = no-op, `valid_to = now()` on changed rates (history preserved), abort on `AltaApiError(140)` (insufficient funds) with Telegram alert, abort on `packet_left < 50` with Telegram alert, structured logging of stats
- [ ] Implement `cron_revalidate_rates` handler — copy pattern from existing `cron_sla_check`, use `_validate_cron_secret(request)` and `client: AltaClient = Depends(get_alta_client)`
- [ ] SQL: `SELECT DISTINCT tnved_code, country_or_areal FROM kvota.tnved_rates WHERE source_fetched_at < now() - interval '7 days' GROUP BY ... ORDER BY MAX(last_used_at) DESC NULLS LAST LIMIT 1000`
- [ ] Loop: call `alta_client.get_rates(code, country, today)`, upsert with `source = 'alta-revalidate'`, set `valid_to = now()` on previous row if values changed (history preserved per REQ-6 AC#3), increment stats counters
- [ ] On `AltaApiError(140)` or `packet_left < 50` → call `telegram_service.notify_admin()` then break loop
- [ ] Set FastAPI request timeout 30 minutes (REQ-6 AC#7)
- [ ] Mount route + add to `PUBLIC_API_PATHS`
- [ ] Run pytest, expect green
- [ ] Commit
- [ ] **Out-of-spec follow-up (manual):** add VPS crontab entry `0 4 * * 1 curl -X POST https://kvotaflow.ru/api/cron/revalidate-rates -H 'X-Cron-Secret: $CRON_SECRET'` per memory `reference_vps_cron_endpoints.md` — note in commit body, do NOT block commit on this

---

### Task 7: Frontend UI — country dropdown + auto-resolve + breakdown + measures (P)

**Requirements:** 7
**Dependencies:** Task 5 (API endpoints live), Task 1 (types regen)

**Files:**
- Modify: `frontend/src/features/quotes/ui/customs-step/customs-item-dialog.tsx` — add country dropdown + certificate checkboxes
- Modify: `frontend/src/features/quotes/ui/customs-step/customs-handsontable.tsx` — add `country_of_origin_oksm` column
- Create: `frontend/src/features/customs-rate-resolve/` — feature folder (auto-resolve-button, rate-breakdown, source-timestamp + api/model/index.ts)
- Create: `frontend/src/features/customs-non-tariff-measures/` — feature folder (measures-list + api/index.ts)
- Modify: `frontend/src/features/customs-autofill/types.ts` — extend `CustomsAutofillSuggestion`

**Steps:**
- [ ] Build country dropdown using **shadcn Combobox + Command** (mandatory project standard from memory `feedback_searchable_select.md` — plain `<Select>` forbidden for entity-pickers). Reference: `features/customers/ui/tab-assignees.tsx`. Filter substring case-insensitive, show «Не найдено», close on outside click, `shrink-0` on adjacent buttons
- [ ] Show «⚠️ Недружественная страна (ПП 430-р)» badge when `is_unfriendly = TRUE` — UI-only signal (REQ-7 AC#2, gotcha #11)
- [ ] Add `has_origin_certificate` + `has_fta_certificate` checkboxes
- [ ] Build «Автоподбор ставок» button → `POST /api/customs/resolve-rates` with current `tnved_code`/`country_of_origin_oksm`/`date=today`/cert flags → fill `customs_duty`/`customs_duty_percent`/`customs_excise`/`customs_eco_fee`/`customs_extra_cost` without page reload
- [ ] Build breakdown component: «пошлина X% + НДС 20% + (акциз Y если ≠0) → итого N₽», `raw_value_string` in tooltip per rate
- [ ] Build source-timestamp display: «Обновлено N минут назад» + «Обновить ставки» button (force_live=true bypasses cache)
- [ ] Build «Показать меры нетарифного регулирования» button (separate trigger — 3₽/call awareness, gotcha #5) → list with `name`/`document_basis`/`document_link`
- [ ] Validation UX (memory `feedback_validation_ux.md`): on autofill error like invalid `tnved_code` (not 10 digits), highlight field + show specific message «Код ТН ВЭД должен быть 10 цифр», never silent fail
- [ ] Q4 freeze warnings UI: parse API response `warnings[]` and `error.code === 'FREEZE_ABORTED'` — show non-blocking toast (Tier 2 cache-stale) or modal (Tier 3 abort) per `design.md` § "Q4 freeze warnings UI"
- [ ] On 503 ALTA_UNAVAILABLE — non-blocking error toast + retry button, do NOT crash form
- [ ] Initialize Supabase JS client with `db: { schema: 'kvota' }` for countries direct read (REQ-7 AC#10) — business logic still through Python API
- [ ] Verify all changes in `frontend/src/`, NEVER `legacy-fasthtml/` (REQ-7 AC#9)
- [ ] Local browser test on `localhost:3000` with prod Supabase (memory `reference_localhost_browser_test.md`): dropdown search, autofill flow, breakdown render, measures pull, error states
- [ ] Commit

---

## Wave 5 — Freeze behavior (sequential)

### Task 8: Customs freeze service + workflow hook + re-freeze endpoint

**Requirements:** 8
**Dependencies:** Task 3 (rate_resolver), Task 5 (API endpoint pattern)

**Files:**
- Create: `services/customs_freeze_service.py`
- Modify: `services/workflow_service.py` — add hook in `transition_quote_status()` at `to_status == WorkflowStatus.APPROVED`
- Modify: `services/quote_version_service.py` — extend `create_quote_version()` to accept `customs_rates` + `source_at_freeze` kwargs (additive, default None for backwards-compat)
- Modify: `api/customs.py` + `api/routers/customs.py` (or `api/routers/quotes.py` if mounted there) — add `POST /api/quotes/{quote_id}/refresh-customs-snapshot` handler + route
- Create: `tests/services/test_customs_freeze.py`
- Create: `tests/api/test_refresh_snapshot.py`

**Steps:**
- [ ] Write red-tests for freeze service: Tier 1 (live success) returns `status='ok'`/`source_at_freeze='alta-live'`; Tier 2 (Alta down + cache available <30 days) returns `status='cache-stale'`/warnings populated; Tier 3 (cache empty or stale >30 days) returns `status='abort'` and emits Telegram admin alert; snapshot shape matches `design.md` § "Snapshot shape extending quote_versions.input_variables"
- [ ] Implement `services/customs_freeze_service.py`: `async def build_snapshot(db, quote_id, *, alta_client) -> FreezeSnapshotResult` with `@dataclass FreezeSnapshotResult(status, items, source_at_freeze, warnings, message)`
- [ ] Implement three-tier loop per quote_item: try `resolve_rate(force_live=True)` → fall to `tnved_rates` cache lookup with TTL 30 days → fall to abort with Telegram alert
- [ ] Modify `services/quote_version_service.py:create_quote_version()` — extend signature to accept `customs_rates: dict | None = None`, `source_at_freeze: str | None = None` and merge into `input_variables` JSONB under `customs_rates` key (Q7 simplification)
- [ ] Modify `services/workflow_service.py:transition_quote_status()` at lines 1343-1352 (after status update commit): when `to_status == WorkflowStatus.APPROVED` → `await customs_freeze_service.build_snapshot(...)` → if `status == 'abort'` raise `FreezeAbortedError(message)` (blocks transition) → call `quote_version_service.create_quote_version(..., customs_rates=..., source_at_freeze=...)` → propagate warnings to caller
- [ ] Implement `POST /api/quotes/{quote_id}/refresh-customs-snapshot` handler — dual-auth + `_CUSTOMS_ROLES`, accepts optional `reason: str` body, calls `customs_freeze_service.build_snapshot(...)` → `quote_version_service.create_quote_version()` (creates NEW row, does NOT update — history saved automatically) → `changelog_service.log_event('customs_rates_snapshot_replaced', payload={quote_id, old_version_id, new_version_id, replaced_by_user_id, reason, replaced_at})` (Q5)
- [ ] Add response error code `FREEZE_ABORTED` for Tier 3 in transition response
- [ ] Update `services/rate_resolver.py:resolve_rate()` snapshot-first branch (Task 3 already includes this — verify integration: read from `quote_versions.input_variables.customs_rates[item_id]` for frozen quotes)
- [ ] Run pytest, expect green
- [ ] Browser-test on localhost: approve a quote → verify `quote_versions` row created with `customs_rates` JSONB populated → click «Пересчитать по текущим ставкам» → confirm modal → verify new version row + changelog event visible in admin panel; simulate Alta down (mock) → verify Tier 2 toast and Tier 3 modal
- [ ] Commit

---

## Wave 6 — Integration verification + PR

### Task 9: End-to-end verification + PR

**Requirements:** all (1-8)
**Dependencies:** Tasks 1-8

**Files:**
- Create: `.kiro/specs/customs-phase-1-rates-and-measures/coverage.md` (REQ coverage report)

**Steps:**
- [ ] Run full test suite: `pytest tests/services/ tests/api/` — expect all green
- [ ] Run frontend build: `cd frontend && npm run build` + `npm run db:types` (idempotent re-run, expect no diff)
- [ ] Verify locked-files invariant: `git diff main..HEAD -- calculation_engine.py calculation_models.py calculation_mapper.py` MUST be empty
- [ ] Verify migration number 298 still unconflicted: `git fetch origin main && ls migrations/29[0-9]*.sql`
- [ ] Generate REQ coverage report at `coverage.md` — table `| REQ | Title | Status | Evidence |` mapping each requirement to file:line evidence
- [ ] Run quality review (`/lean-tdd` Phase 5a or `feature-dev:code-reviewer`) on full diff — address CRITICAL findings via Ralph Loop, document WARNINGS
- [ ] Run `/code-review` on PR if available
- [ ] Browser smoke test on localhost: full flow from quote_item edit → autofill → breakdown → measures → approve → re-freeze
- [ ] Push branch + open PR with body summarizing 8 REQs, decisions reference, test/browser-verification summary
- [ ] Wait 90s after any prior merge before requesting merge (memory `feedback_parallel_deploys_container_conflict.md` — back-to-back deploys race container reuse)

---

## Dependency Graph

```
Task 1 (migration) ─┐
                    ├─→ Task 3 (rate_resolver) ─┐
Task 2 (AltaClient)─┤                            ├─→ Task 5 (API) ─┬─→ Task 7 (Frontend)
                    └─→ Task 4 (customs_calc)  ─┘                  ├─→ Task 8 (Freeze) ─→ Task 9 (Verify+PR)
                                                Task 2 ────────────┤
                                                Task 3 ────────────┴─→ Task 6 (Cron)
```

Tasks 1+2 parallel (Wave 1). Tasks 3+4 parallel (Wave 2). Task 5 sequential (Wave 3). Tasks 6+7 parallel (Wave 4). Task 8 sequential (Wave 5). Task 9 final (Wave 6).

---

## Готовность к implementation phase

✅ All 8 REQs mapped to tasks (REQ-1 → T1, REQ-2 → T2, REQ-3 → T3, REQ-4 → T4, REQ-5 → T5, REQ-6 → T6, REQ-7 → T7, REQ-8 → T8, all → T9 verify)
✅ Each task independently commitable with explicit file scope
✅ Parallel markers `(P)` applied to genuinely independent tasks
✅ Test-first discipline (red-tests before implementation in every task)
✅ Locked-files invariant verified explicitly in T4 + T9
✅ Migration 298 verified as free at start of T1 + T9

**Next:** clear conversation → `/kiro:spec-impl customs-phase-1-rates-and-measures 1` to start Task 1 with fresh context.
