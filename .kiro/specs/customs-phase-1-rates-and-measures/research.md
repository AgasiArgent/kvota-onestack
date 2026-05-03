# Research Log — customs-phase-1-rates-and-measures

**Updated:** 2026-05-01
**Discovery type:** Light (extension of existing customs infrastructure)

## Summary

Phase 1 — extension brownfield-проекта, не greenfield. Основной discovery уже проведён через gap-analysis.md и Q7 explorer; формальный research-phase сводится к каталогизации найденного.

**Discovery scope:**
- Existing customs infrastructure в `api/customs.py` + `api/routers/customs.py` + 11-компонентная customs-step UI feature + 2 customs feature folders + customs_declaration_service
- Phase 0 reference implementation (sync-функции для lift'а в production async-классы)
- Existing snapshot pattern в `services/quote_version_service.py` — заменяет наш изначальный план с per-item snapshot columns
- Workflow transitions в `services/workflow_service.py` — точка hook'а для freeze logic
- Existing alerting/changelog/cron infrastructure — переиспользуем

**Key insights:**
1. **Architectural simplification (Q7 explorer):** Вместо `customs_rates_snapshot JSONB` + `customs_rates_snapshot_date DATE` колонок в `quote_items` — extend существующую `quote_versions.input_variables` JSONB. Single snapshot infrastructure для всего quote, customs становится одним из ключей.
2. **Combined-rate semantics conflict (Q1):** `services/calculation_helpers.py:269+` уже имеет partial implementation отличающуюся от handoff gotcha #3. Решение — параллельные системы по `tnved_rates.source` field, calc engine остаётся неизменным.
3. **Migration номер 296 → 297:** procurement-bugs-fix спека мерджнулась с migration 296 (`update_vat_rates_by_country`). Phase 1 customs становится 297.

---

## Research Log

### Topic 1: Existing customs infrastructure

**Findings:**
- `api/customs.py` (606 строк) — handler module: `bulk_update_items`, `autofill_handler`, `create_item_expense`, `delete_item_expense`, `create_quote_expense`, `delete_quote_expense`
- `api/routers/customs.py` — thin FastAPI APIRouter wrapper, mounted at `/api/customs/*`
- `_resolve_dual_auth(request)` helper at line 52 — DRY auth (JWT + legacy session)
- `_CUSTOMS_ROLES = {"customs", "admin", "head_of_customs"}` constant at line 25
- `_AUTOFILL_FIELDS` tuple at line 36 — backwards-compat surface mirrored in TS `frontend/src/features/customs-autofill/types.ts`

**Source:** `gap-analysis.md` REQ-5 detailed findings

**Implication:** Pattern handler+router split established. New endpoints следуют тому же контуру, не изобретаем новых паттернов.

---

### Topic 2: Existing snapshot pattern (Q7 finding — architectural impact)

**Findings (от Explore agent):**
- `services/quote_version_service.py:81-150`: `create_quote_version(quote_id, calculated_vars)` — immutable snapshot в `quote_versions` table
- Структура snapshot: `products_snapshot` (array всех quote_items на момент snapshot) + `input_variables` (calculated vars)
- Запись atomic, новая row на каждый snapshot — versioning встроено
- Hook point для freeze: `services/workflow_service.py:1343-1352` внутри `transition_quote_status()`, при `to_status == WorkflowStatus.APPROVED`
- Frozen boundary = `WorkflowStatus.APPROVED` и далее (SENT_TO_CLIENT, CLIENT_NEGOTIATION, PENDING_SPEC_CONTROL, PENDING_SIGNATURE, DEAL, REJECTED, CANCELLED)

**Source:** Q7 explorer report (2026-05-01)

**Implication:**
- DROP `customs_rates_snapshot JSONB` and `customs_rates_snapshot_date DATE` columns from REQ-1 ALTER quote_items
- Extend `quote_versions.input_variables` с новым ключом `customs_rates: {item_id: {rates, measures, fetched_at, source_at_freeze}}`
- Re-freeze создаёт новую row в quote_versions (history saved автоматически)
- `changelog_service.log_event('customs_rates_snapshot_replaced', ...)` для audit trail (REQ-8 Q5)

---

### Topic 3: Combined-rate formula conflict (Q1)

**Findings:**
- Existing `services/calculation_helpers.py:269+`:
  ```
  customs_duty_pct + (customs_duty_per_kg × weight_kg / base_price × 100)
  ```
  → специфическая часть конвертируется в additional pct к адвалорной
- Handoff gotcha #3 предписывает:
  ```
  max(адвалорная_от_стоимости, специфическая_от_веса)
  ```
- **Different semantics.** На многих товарах разница ~2x. Cannot silent-replace.

**Source:** `gap-analysis.md` REQ-4 + handoff doc gotcha #3

**Decision:** Параллельные системы (decisions.md Q1 = Option B):
- Legacy formula остаётся в `calculation_helpers.py` для backwards-compat существующих quote_items
- Новый `services/customs_calc.py` `max()` formula применяется ТОЛЬКО для свежих rates с `source ∈ {'alta-live', 'alta-revalidate'}`
- Switch logic в `build_calculation_inputs()` адаптер-слое (calc_engine.py НЕ модифицируется — Andrey explicit reminder 2026-05-01)
- Documented technical debt: legacy formula sunset когда все quote_items на Alta-resolved rates (Phase 5+)

---

### Topic 4: Phase 0 lift candidates

**Findings (Phase 0 worktree `/Users/andreynovikov/workspace/tech/projects/kvota/onestack-customs-phase0/scripts/phase0_eval_alta_express.py`):**
- `sign_request(request_id, login, password)` — MD5 двойной hash, точно по spec
- `build_request_xml(items)` — XML payload constructor через ET
- `parse_response(xml_text)` — error-code-aware parser (100/110/120/140/201)
- `AltaApiError(code, message)` exception class
- `POLL_MAX_ATTEMPTS = 6` polling logic
- 13 pytest tests (calibrated fixture)

**Source:** Phase 0 implementation completed 2026-04-28

**Implication:** Lift в `services/alta_client.py` с минимальной адаптацией:
- Sync → async (httpx.AsyncClient вместо httpx.Client)
- Function → class encapsulation (AltaClient + AltaExpressClient)
- 4 endpoints (Такса /tnved/xml/, xml_nodes /tnved/xml_nodes/, АПУ /tnved/xml_apu/ stage 1+2, Express /tools/autotnved/v2/)
- Credentials через FastAPI Depends (decisions.md Q6)

---

### Topic 5: Existing alerting + changelog + cron infrastructure

**Findings:**
- `services/telegram_service.py` — Telegram bot, используется для overdue/SLA notifications в `api/cron.py`
- `services/changelog_service.py` — generic project-wide changelog с event types
- `api/cron.py` + `api/routers/cron.py` — handler/router split, X-Cron-Secret header через `_validate_cron_secret`, listed в `PUBLIC_API_PATHS`
- VPS crontab — manual management через `(crontab -l; echo "...") | crontab -` (memory `reference_vps_cron_endpoints.md`)

**Source:** `gap-analysis.md` cross-cutting concerns

**Implication:**
- REQ-2 packet alerts → `telegram_service.notify_admin()`
- REQ-6 cron failures → same telegram channel
- REQ-8 audit (re-freeze) → `changelog_service.log_event('customs_rates_snapshot_replaced', ...)`
- New cron endpoint `/api/cron/revalidate-rates` следует existing pattern: handler в `api/cron.py`, route в `api/routers/cron.py`, X-Cron-Secret + PUBLIC_API_PATHS

---

### Topic 6: Migration numbering

**Findings:**
- 295 имеет collision (два файла: `295_add_country_code_to_suppliers_and_buyers.sql` + `295_sla_notifications_dedupe.sql`) — known issue (memory `feedback_parallel_deploys_container_conflict.md`)
- 296 ЗАНЯТО — `296_update_vat_rates_by_country.sql` from procurement-bugs-fix spec
- 297 — следующий свободный

**Source:** Direct `ls migrations/` (gap-analysis verification)

**Implication:** Phase 1 миграция = **297** (handoff doc устарел в этой части).

---

## Architecture Pattern Evaluation

| Pattern | Considered | Selected? | Rationale |
|---|---|---|---|
| Per-item JSONB snapshot column on quote_items | REQ-1 original | ❌ | Replaced by extending quote_versions.input_variables (Q7 finding) |
| Whole-quote snapshot in quote_versions table | gap-analysis Q7 | ✅ | Single source of truth, atomic versioning, integrates with existing flow |
| TKS bulk-sync + Alta fallback | Pre-2026-04-24 H3 | ❌ | Excluded by Andrey 2026-04-24 — Alta-only H1 final |
| Custom LLM fallback in MVP | handoff Phase 4A | ❌ | Deferred to Phase 4 if eval-gate fails |
| `last_used_at` column vs derive from log | decisions Q3 | Column ✅ | Simple UPDATE, write overhead negligible vs Alta call cost |
| Module-singleton vs FastAPI Depends for credentials | decisions Q6 | Depends ✅ | Idiomatic for FastAPI, testable via dependency_overrides |
| Sentry vs Telegram for alerts | decisions Q2 | Telegram-only ✅ | Existing infrastructure, no new setup needed |
| Per-quote vs per-item freeze hook | decisions Q7 | Whole-quote at APPROVED ✅ | Aligns with quote_versions pattern, semantically correct |

## Identified Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Migration 297 conflict if procurement-bugs-fix мерджит ещё миграции до нашего PR | Med | Verify `ls migrations/` непосредственно перед merge; bumping номера тривиально |
| Alta API outage during freeze (legal-critical workflow) | High | Q4 three-tier graceful degradation: live → 30-day cache → abort with UI notification + admin Telegram alert |
| Packet exhaustion на Alta Express (paid API, 1000/30days) | Med | Q2 Telegram alerts при `left_count < 100`, throttle 1/hour против spam, log `left_count` после каждого вызова |
| Combined-rate formula divergence — quote totals меняются между legacy и new path | High | Q1 explicit switch by `rate.source` field; legacy quote_items остаются на legacy formula до Phase 5+ sunset; documented technical debt |
| windows-1251 XML decoding в Alta Такса response | Low | Detect через response charset header или XML declaration; explicit `resp.content.decode('windows-1251')` fallback |
| Backwards-compat `_AUTOFILL_FIELDS` tuple → frontend `CustomsAutofillSuggestion` interface | Med | Strict additive-only changes, никогда не renaming/changing semantics |

## Parallelization for Tasks Phase

**Wave 1 (parallel — independent files):**
- Migration 297 + types regen
- AltaClient skeleton

**Wave 2 (parallel — independent services):**
- rate_resolver
- customs_calc

**Wave 3 (sequential — depends on services):**
- API endpoints (resolve-rates, non-tariff-measures, refresh-customs-snapshot)

**Wave 4 (parallel with Wave 3 backend done):**
- Frontend (country dropdown, autofill button, breakdown UI, freeze notifications)
- Cron revalidate endpoint

**Wave 5 (sequential):**
- customs_freeze_service
- workflow_service hook integration
