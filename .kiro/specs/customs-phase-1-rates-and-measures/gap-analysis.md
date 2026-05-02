# Gap Analysis — Customs Phase 1: ставки + меры

**Date:** 2026-05-01
**Spec:** `customs-phase-1-rates-and-measures`
**Architecture:** Alta-only (H1)
**Scope:** Анализ existing OneStack codebase для информирования design phase. Только factual findings — без implementation decisions.

---

## TL;DR

Brownfield-проект уже имеет существенную customs infrastructure: `api/customs.py` handler module, `api/routers/customs.py` thin router, `services/customs_declaration_service.py`, `frontend/src/features/quotes/ui/customs-step/` (11 компонентов), `frontend/src/features/customs-autofill/`. Phase 1 не строит с нуля — **интегрируется в established patterns**.

**🚨 Критическая правка:** Migration **296 ЗАНЯТА** (`296_update_vat_rates_by_country.sql` из procurement-bugs-fix spec). Наша миграция становится **297**. Также 295 имеет коллизию (два файла с тем же номером — известная race-condition deploy).

**Ключевые reuse-возможности:**
- `_CUSTOMS_ROLES`, `_resolve_dual_auth(request)` — уже в api/customs.py:25,52, импортируем не передекларируем
- `_AUTOFILL_FIELDS` tuple — backwards-compat surface, **расширяем** (добавляем `country_of_origin_oksm`, `customs_rates_snapshot_summary`), **не меняем** semantics существующих полей
- Phase 0 функции (`sign_request`, `build_request_xml`, `parse_response`, `AltaApiError`) — lift в `services/alta_client.py` с минимальной адаптацией (sync→async wrapping через `httpx.AsyncClient`, function→class encapsulation)
- Cron pattern: handler в `api/cron.py` + thin router в `api/routers/cron.py` + `_validate_cron_secret` + `PUBLIC_API_PATHS`
- `services/calculation_helpers.py` уже знает про `customs_duty_per_kg` — REQ-4 интегрируется, не дублирует

**Ключевые conflicts/риски:**
- `services/workflow_service.py:1779` валидирует `hs_code` присутствие как gate для customs-step completion — ALTER COLUMN'ы должны это сохранить
- `frontend/src/features/customs-autofill/types.ts` — TypeScript interface `CustomsAutofillSuggestion` зеркалирует `_AUTOFILL_FIELDS`. Любое изменение Python tuple **обязано** синхронизировать TS interface (auto-codegen `npm run db:types` помогает только для DB-полей)
- procurement-bugs-fix spec параллельно работает с `country_code` на suppliers/buyers — наш новый `country_of_origin_oksm` на quote_items это разные вещи (буквенный ISO vs цифровой ОКСМ), нужно явно различать в design

---

## REQ × Status × Files × Risks

| REQ | Status | Files (новые/touched) | Главный риск |
|-----|--------|----------------------|--------------|
| 1 — Migration | NONE → новая 297 | `migrations/297_tnved_foundation.sql` (новый) | **Номер изменён 296→297**. Self-FK на tnved_codes требует DEFERRABLE или batch-order. ОКСМ seed ~250 строк. |
| 2 — AltaClient | NONE → новый | `services/alta_client.py` (новый, ~600 строк) | Async-wrapping Phase 0 sync-функций. windows-1251 detection при HTTP-парсинге. Packet-limit alerting нужен alerting infrastructure (Sentry? Telegram?) — выяснить в design |
| 3 — RateResolver | NONE → новый | `services/rate_resolver.py` (новый, ~250 строк) | Race-safe upsert через UNIQUE constraint. Lazy-fetch latency на cache miss (~500ms-2s) — UI должен показать spinner. |
| 4 — CustomsCalc | PARTIAL → новый wrapper | `services/customs_calc.py` (новый, ~200 строк) | **Существующий `customs_duty_per_kg` mechanism** в calculation_helpers.py. Не дублировать — wrap или extend. Координация с Decimal-precision rules. |
| 5 — API endpoints | EXTENDS existing | `api/customs.py` +~300 строк, `api/routers/customs.py` +~30 строк | Backwards-compat `_AUTOFILL_FIELDS` tuple → frontend `CustomsAutofillSuggestion` interface. **Все новые поля optional** в TS, **никогда** не менять semantics существующих. |
| 6 — Cron revalidate | NONE → новый | `api/cron.py` +~80 строк, `api/routers/cron.py` +~10 строк, VPS crontab (out-of-spec) | Alerting на packet_left < 50: использовать существующий Telegram-канал? Sentry alert? Спецификация design phase. |
| 7 — Frontend UI | EXTENDS existing | `frontend/src/features/quotes/ui/customs-step/` +2-3 компонента, `frontend/src/features/customs-autofill/` +~50 строк | Country dropdown через searchable Input (memory `feedback_searchable_select.md`). Existing `customs-handsontable.tsx` — bulk grid editing уже работает. Меры нетарифного — новый компонент UI. |
| 8 — Freeze snapshot | NONE → новая логика | Логика freeze в `services/workflow_service.py` или новый `services/customs_freeze_service.py` | Где именно вызывается freeze? Workflow transitions в workflow_service. Снимок при `quote.status` transition в frozen-state. **Дизайн-вопрос:** что если Alta недоступна на момент freeze (REQ-8 AC#5) — abort или stale-cache? |

---

## Detailed findings per REQ

### REQ-1: Foundation Database Schema

**Existing state:**
- Migrations 290-296 заняты. Recent customs-related: 292 (`head_of_customs` role), 293 (`customs_cleanup_and_expenses` — Wave 1 logistics-customs-redesign), 296 (`update_vat_rates_by_country` — procurement-bugs-fix REQ-4).
- `kvota.quote_items` уже имеет: `hs_code VARCHAR(20)`, `customs_duty DECIMAL(15,4)`, `customs_duty_per_kg`, `customs_duty_percent` (legacy?), `customs_util_fee`, `customs_excise`, `customs_eco_fee`, `customs_extra_cost`, `customs_honest_mark`, `customs_psm_pts` (renamed in 293), license fields (ds/ss/sgr × required/cost), `customs_processing_total`. Полный schema → `frontend/src/shared/types/database.types.ts` (auto-generated).
- НЕТ: `country_of_origin_oksm`, `has_origin_certificate`, `has_fta_certificate`, `customs_rates_snapshot`, `customs_rates_snapshot_date`. Все добавляются в новой миграции через `ADD COLUMN IF NOT EXISTS`.
- `kvota.suppliers` и `kvota.buyer_companies` уже имеют `country_code CHAR(2)` (migration 295 procurement-bugs-fix). **Это другое поле** — буквенный ISO для контрагентов, не цифровой ОКСМ для страны происхождения товара. Не путать.
- Существующий `kvota.customs_item_expenses` и `kvota.customs_quote_expenses` (migration 293) — отдельные таблицы доп. расходов. Не пересекаются с tnved_rates.

**Files (new):**
- `migrations/297_tnved_foundation.sql` (~400 строк: 9 CREATE TABLE + 5 ALTER quote_items + 4 seeds + indexes)
- `migrations/297_seed_oksm_countries.csv` (опционально — отдельный CSV для импорта 250 стран Росстандарта)

**Risks:**
1. **Self-FK на tnved_codes(parent_code → code)** — bootstrapping вставки иерархии. Решение: DEFERRABLE INITIALLY DEFERRED constraint, либо seed только 2-знаковых корневых кодов, остальное — органически из Alta Такса.
2. Подтверждение что migration 297 свободен на момент применения — нужно проверить `git log --oneline migrations/` непосредственно перед merge (memory `feedback_parallel_deploys_container_conflict.md`).
3. Seed `is_unfriendly` фиксируется на дату миграции — нужен явный комментарий в SQL «дата фиксации: YYYY-MM-DD, обновлять вручную» (gotcha #11).

**Reuse opportunities:**
- Migration template style: см. `migrations/293_customs_cleanup_and_expenses.sql` — DO blocks, idempotent ALTER, NOTICE для observability.
- Seed CSV pattern: см. `migrations/295_add_country_code_to_suppliers_and_buyers.sql` — hardcoded mapping inline или separate seed file.

---

### REQ-2: Alta XML API Client

**Existing state:**
- НЕТ `services/alta_client.py`.
- Есть `services/dadata_service.py`, `services/here_service.py`, `services/cbr_rates_service.py` — паттерн external API client (sync через `requests` или async через `httpx`).
- Phase 0 standalone-скрипт `phase0_eval_alta_express.py` (worktree onestack-customs-phase0) уже имеет:
  - `sign_request(request_id, login, password)` — MD5 двойной hash, точно по spec
  - `build_request_xml(items)` — XML payload constructor
  - `parse_response(xml_text)` — парсер с error code recognition (100/110/120/140/201)
  - `AltaApiError(code, message)` exception class
  - Polling loop с `POLL_MAX_ATTEMPTS=6` (1 initial + 5 retries)
  - `call_alta_express(items, login, password, dry_run)` — sync httpx call
  - 13/13 pytest tests passing

**Files (new):**
- `services/alta_client.py` (~600 строк): класс `AltaClient` с 4 методами (Такса, xml_nodes, АПУ stage1+2, Express batch). Внутри — async-wrapped lifted Phase 0 functions.
- `tests/services/test_alta_client.py` (~300 строк): unit-тесты (signing correctness, XML parsing, error handling) + integration-тест с mock httpx (без реальных Alta calls).

**Risks:**
1. **Sync→async lift:** Phase 0 использовал `httpx.Client` sync. Phase 1 production должен быть async (`httpx.AsyncClient`) для совместимости с FastAPI handlers. Чисто механический rewrite — функции pure, не зависят от sync-state.
2. **windows-1251 detection** (gotcha #2): `httpx.Response.text` декодирует через `Content-Type charset` header. Если Alta не указывает charset, `httpx` defaults to UTF-8 — что неверно для Такса. Phase 0 работает с UTF-8 fixture, не сталкивался с этим. Решение: явный `resp.content.decode('windows-1251')` если `response.encoding` не указан и XML declaration говорит windows-1251.
3. **Packet-limit alerting** (REQ-2 AC#10): нужно решить в design phase — Sentry, Telegram bot (`services/telegram_service.py` существует), email? Память `reference_vps_cron_endpoints.md` упоминает что cron endpoints отправляют alerts через Telegram.
4. **Credentials в DI vs env:** Phase 0 принимал login/password как аргументы конструктора. Production может потребовать factory-функцию `get_alta_client()` которая читает env. **Решение в design:** где именно env lookup — в module-level singleton или в FastAPI dependency.

**Reuse opportunities:**
- 80% Phase 0 functions переносятся as-is. Только `call_alta_express` нужен async-wrapper.
- Existing pattern для async external API: `services/cbr_rates_service.py` (читать в design phase).

---

### REQ-3: Rate Resolver

**Existing state:**
- НЕТ `services/rate_resolver.py`.
- Существующий autofill (`api/customs.py:autofill_handler`) — это **historical lookup в своей истории**, не live Alta call. Логика: `SELECT FROM quote_items WHERE brand=$1 AND product_code=$2 AND hs_code IS NOT NULL ORDER BY created_at DESC LIMIT 1`. Не пересекается с rate_resolver, но дополняет: handoff section «Update api/customs.py» говорит «при отсутствии исторических данных — live-запрос к Alta».

**Files (new):**
- `services/rate_resolver.py` (~250 строк): функция `resolve_rate(...)` + helper `_lookup(...)` + `_alta_fetch_and_cache(...)`.
- `tests/services/test_rate_resolver.py` (~150 строк).

**Risks:**
1. **Concurrent upsert race:** 2 запроса на одну `(code, country, date)` → потенциально дубликаты. Решение через `ON CONFLICT (UNIQUE constraint) DO UPDATE` — REQ-1 AC#6 предусматривает constraint.
2. **`last_used_at` update на rate row:** добавить колонку в `tnved_rates`, либо считать через `tnved_classification_log`. **Дизайн-вопрос.**
3. **Lazy-fetch latency:** при cache miss UI ждёт 500-2000ms на live Alta. Решение через async + spinner в UI (REQ-7).
4. **Date в прошлом + snapshot:** REQ-3 AC#8 говорит «сначала искать в `customs_rates_snapshot` quote_item». Зависит от как resolver узнаёт quote_item context. **Дизайн-вопрос:** функция принимает `quote_item_id` как опциональный context?

**Reuse opportunities:**
- Pattern lookup-with-fallback: см. `services/cbr_rates_service.py` (currency rates с CBR API + cache в DB).
- UPSERT pattern: см. recent migrations с `ON CONFLICT DO UPDATE`.

---

### REQ-4: Customs Duty Calculator

**Existing state:**
- ЧАСТИЧНО существует в `services/calculation_helpers.py:269+`:
  ```python
  # Formula: customs_duty + (customs_duty_per_kg * weight_in_kg / base_price * 100)
  # Falls back to customs_duty only when weight or price is missing/zero.
  # Falls back to legacy import_tariff field when customs_duty is absent.
  ```
- Это **уже партиальная поддержка комбинированной ставки** (адвалорная % + специфическая per-kg). Однако формула нестандартная — она конвертирует per-kg в дополнительный процент к адвалорной (а не `max()` из gotcha #3).
- НЕТ `services/customs_calc.py` как отдельного модуля.
- НЕТ ПП 342 step-функции таможенного сбора.
- НЕТ ПП 81 утилизационного сбора.

**Files (new):**
- `services/customs_calc.py` (~200 строк): `calculate_duty()`, `calculate_customs_fee()`, `calculate_util_fee()`.
- `tests/services/test_customs_calc.py` (~150 строк): test cases для каждого rate type + ПП 342 bands.

**Risks:**
1. **🚨 Конфликт логики комбинированной ставки!** Существующая формула в calculation_helpers.py делает «percent + per-kg как доп.процент к адвалорной», handoff gotcha #3 требует `max(адвалорная, специфическая)`. **Это разная семантика.** Дизайн phase должен решить: (a) refactor calculation_helpers.py чтобы использовать новый customs_calc.py (рискует нарушить существующие quotes), (b) оставить legacy formula для backwards-compat и применить новую только для Alta-resolved rates.
2. **calculation_engine.py локирован** — никаких модификаций. customs_calc.py подключается через `build_calculation_inputs()` адаптер (REQ-4 AC#7).
3. **ПП 342 bands могут устареть** — постановление обновляется. Решение: hardcode latest bands + комментарий «verified YYYY-MM-DD, проверять раз в год».
4. **Decimal precision:** существующий код активно использует `Decimal` через `safe_decimal()` helper в calculation_helpers.py — переиспользовать.

**Reuse opportunities:**
- `services/calculation_helpers.py:safe_decimal()` — существующий decimal-handling helper.
- Test pattern: `tests/services/test_calculation_helpers.py` (если существует — проверить в design).

---

### REQ-5: API Endpoints

**Existing state:**
- `api/customs.py` существует — 606 строк, 5 handler functions: `bulk_update_items`, `autofill_handler`, `create_item_expense`, `delete_item_expense`, `create_quote_expense`, `delete_quote_expense`.
- `api/routers/customs.py` thin wrapper, 7 routes mounted.
- `_resolve_dual_auth(request)` — DRY auth helper, использовать.
- `_CUSTOMS_ROLES = {"customs", "admin", "head_of_customs"}` — global constant, импортировать.
- `_AUTOFILL_FIELDS` tuple — backwards-compat surface (см. ниже).
- Existing autofill response envelope: `{"success": true, "data": {"suggestions": [{...}]}}` — следовать тому же envelope.

**Files (touched):**
- `api/customs.py` — добавить 2 новых async handler: `resolve_rates_handler`, `non_tariff_measures_handler`. Расширить `autofill_handler` (опциональный `force_live` flag, новые поля в response).
- `api/routers/customs.py` — добавить 2 новых route: `POST /resolve-rates`, `POST /non-tariff-measures`.

**Risks:**
1. **🚨 Backwards-compat `_AUTOFILL_FIELDS`** (REQ-5 AC#3): существующий frontend `CustomsAutofillSuggestion` interface зеркалирует tuple. Adding new fields → safe (TS optional). Renaming or changing semantics → breaking. **Расширяем только строго additive.**
2. **Handler vs router split** — следовать существующему паттерну: handler в `api/customs.py`, router wrapper в `api/routers/customs.py`. Не смешивать.
3. **Side effects в `resolve-rates` AC#7:** опциональный `quote_item_id` параметр триггерит UPDATE quote_items. Это side effect — должен быть явно в docstring (api-first.md convention) и логироваться.
4. **503 на Alta unavailable:** UI должен показать retry button (REQ-7), но не падать. Backend должен различать «Alta down» vs «invalid input» — разные error codes.

**Reuse opportunities:**
- `_resolve_dual_auth` — copy pattern.
- Response envelope `{success, data?, error?}` — established.
- Error codes в стиле `UNAUTHORIZED`/`FORBIDDEN`/`BAD_REQUEST` — добавить `ALTA_UNAVAILABLE`, `INVALID_TNVED_CODE`, `INVALID_OKSM`.

---

### REQ-6: Weekly Cache Revalidation Cron

**Existing state:**
- `api/cron.py` — handler module, 397 строк. Existing endpoints: `cron_check_overdue` (GET), `cron_sla_check` (POST).
- `api/routers/cron.py` — thin router, 2 mounted routes.
- Auth: `_validate_cron_secret(request)` через `X-Cron-Secret` header (env var `CRON_SECRET`). Listed в `PUBLIC_API_PATHS` (no JWT middleware).
- VPS crontab management — manual (memory `reference_vps_cron_endpoints.md`).

**Files (touched):**
- `api/cron.py` — новый handler `cron_revalidate_rates` (~80 строк).
- `api/routers/cron.py` — новый route `POST /api/cron/revalidate-rates`.
- `api/auth.py` (если PUBLIC_API_PATHS там) — добавить новый path в whitelist.

**Risks:**
1. **Long-running endpoint timeout** (REQ-6 AC#7): 30 минут timeout. FastAPI default — может потребоваться явный `request.scope` setting или streaming response (`yield` progress logs).
2. **Idempotency** (REQ-6 AC#6): SQL filter `source_fetched_at < now() - interval '7 days'` уже idempotent.
3. **Alerting infrastructure** для packet_left < 50: см. REQ-2 risk #3. Использовать `services/telegram_service.py`?
4. **Concurrent runs** (cron triggered twice by accident): UPDATE через unique constraint безопасен, но lock на batch-level не нужен — каждый запуск обработает свой subset.

**Reuse opportunities:**
- Полностью копировать pattern `cron_sla_check` (POST + secret validate + structured logging).

---

### REQ-7: Frontend UI

**Existing state:**
- 🚨 **Существует целое feature `frontend/src/features/quotes/ui/customs-step/`** с 11 компонентами:
  - `customs-action-bar.tsx` — bulk actions toolbar
  - `customs-columns.ts` — column definitions for grid
  - `customs-expenses.tsx` — expenses block
  - `customs-handsontable.tsx` — bulk editor (Handsontable)
  - `customs-info-block.tsx` — info display
  - `customs-item-dialog.tsx` — per-item edit dialog
  - `customs-items-editor.tsx` — items list editor
  - `customs-notes.tsx` — notes
  - `customs-step.tsx` — main step component
  - `item-customs-expenses.tsx` — per-item expense
  - `quote-customs-expenses.tsx` — per-quote expense
- `frontend/src/features/customs-autofill/` — separate feature для autofill UX (button + suggestions list).
- `frontend/src/features/customs-declarations/` — DT export feature.
- `frontend/src/entities/customs-declaration/` — entity layer (queries, types).
- FSD architecture confirmed: features → entities → shared.

**Files (touched/new):**
- `frontend/src/features/quotes/ui/customs-step/customs-item-dialog.tsx` — расширить: country dropdown + certificate checkboxes.
- `frontend/src/features/quotes/ui/customs-step/customs-handsontable.tsx` — расширить columns с `country_of_origin_oksm` (и Alta-fetched fields в read-only mode).
- `frontend/src/features/customs-autofill/ui/` — новый компонент `auto-resolve-rates-button.tsx` (отдельный от existing autofill-from-history button).
- Новый feature: `frontend/src/features/customs-rate-breakdown/` — компонент breakdown UI с tooltip raw_value, source_fetched_at timestamp, retry button.
- Новый feature: `frontend/src/features/customs-non-tariff-measures/` — компонент списка мер с pull-trigger button (3₽ aware).
- `frontend/src/entities/customs-declaration/types.ts` — расширить если нужно.
- `frontend/src/features/customs-autofill/types.ts` — расширить `CustomsAutofillSuggestion` (additive only).

**Risks:**
1. **Searchable select для countries dropdown** (memory `feedback_searchable_select.md`): не использовать plain `<Select>`. shadcn `Combobox` + `Command` — проверить если уже используется в проекте.
2. **Bulk grid editing** в Handsontable — добавление новых колонок может требовать backend-side validation (REQ-5).
3. **Validation UX** (memory `feedback_validation_ux.md`): error states должны явно подсвечивать поля.
4. **Type generation**: после migration 297 → `cd frontend && npm run db:types` обновляет `database.types.ts` (memory `feedback_regen_types_before_schema_drop.md`).
5. **Localhost testing flow** (memory `reference_localhost_browser_test.md`): user wants every UI change verified on `localhost:3000` + prod Supabase.

**Reuse opportunities:**
- Existing `customs-step.tsx` — extend, не replace.
- shadcn/ui Combobox если уже используется (grep подтвердит).
- Existing `customs-autofill` feature — model для нового `auto-resolve-rates` UX.

---

### REQ-8: Freeze Behavior

**Existing state:**
- НЕТ `customs_rates_snapshot` field на quote_items (добавляется в REQ-1).
- Freeze workflow существует — `services/workflow_service.py` управляет transitions. `quote.status = 'frozen'` или связанные статусы (нужно проверить в design phase).
- НЕТ existing snapshot logic для customs.

**Files (touched/new):**
- `services/workflow_service.py` или новый `services/customs_freeze_service.py` — снимок при freeze transition.
- Possibly `api/quotes.py` — если freeze endpoint там.

**Risks:**
1. **Where именно вызывается freeze:** unknown без design phase deep-dive в workflow_service. **Дизайн-вопрос.**
2. **Alta unavailable на момент freeze** (REQ-8 AC#5): abort или stale-cache? **Требует решения от Andrey.**
3. **Audit log для re-freeze** (REQ-8 AC#4): новая таблица `quote_items_history`? Существующая `services/changelog_service.py`? **Дизайн-вопрос.**

**Reuse opportunities:**
- `services/workflow_service.py:1856+` уже имеет customs validation pattern (validates hs_code present before customs-step completion) — добавить snapshot capture в той же транзакции.

---

## Сross-cutting concerns

### Alerting infrastructure

REQ-2 (packet alerts) и REQ-6 (cron failures) нуждаются в alerting channel. Existing options:
- `services/telegram_service.py` — Telegram bot, используется для overdue/SLA notifications (api/cron.py)
- Sentry — упоминается в `~/.claude/skills/sentry/`, может быть установлен
- Logging only — `logger.error(...)` в structured logs

**Дизайн-вопрос:** какой channel предпочесть для customs-alerts?

### Existing customs taxonomy collisions

Procurement-bugs-fix spec ввёл:
- `kvota.suppliers.country_code CHAR(2)` — буквенный ISO для контрагентов
- `kvota.buyer_companies.country_code CHAR(2)` — буквенный ISO
- `kvota.vat_rates_by_country` — domestic VAT (НЕ import VAT)

Phase 1 вводит:
- `kvota.quote_items.country_of_origin_oksm SMALLINT` — цифровой ОКСМ для страны происхождения товара
- `kvota.countries.iso_alpha2 CHAR(2)` — буквенный ISO для customs countries

**Не конфликт, но требует ясности в design:** связь между `quote_items.country_of_origin_oksm` и `suppliers.country_code` — отдельные понятия (origin vs supplier). Документировать.

### Type generation pipeline

После migration 297 → REQ-7 frontend требует `npm run db:types` ДО реализации UI (memory `feedback_regen_types_before_schema_drop.md`). Это критично — без свежих types TypeScript не увидит новые колонки.

### Localhost-first verification

User strongly prefers localhost browser test before commit (memory `reference_localhost_browser_test.md`). Phase 1 — production code, должен проходить через localhost:3000 с prod Supabase до push.

### Migration deploy serialization

Memory `feedback_parallel_deploys_container_conflict.md` — back-to-back PR merges race deploy. Phase 1 PR должен мержиться с `concurrency` group или 90s spacing после предыдущего merge.

---

## Recommended implementation order (dependency-aware)

```
Phase 1 wave 1 (foundation):
  ┌─ REQ-1: migration 297 + types regen
  └─ REQ-2: AltaClient (parallel — нет DB-зависимости)

Phase 1 wave 2 (services layer):
  REQ-3: rate_resolver (depends on REQ-1 + REQ-2)
  REQ-4: customs_calc (depends on REQ-1 schema awareness, otherwise independent)

Phase 1 wave 3 (API layer):
  REQ-5: api endpoints (depends on REQ-3 + REQ-4)

Phase 1 wave 4 (frontend):
  REQ-7: UI (depends on REQ-5 + types regen)

Phase 1 wave 5 (operational):
  REQ-6: cron (depends on REQ-3 + REQ-2)
  REQ-8: freeze snapshot (depends on REQ-3 — нужен resolver чтобы фиксировать snapshot)
```

Total estimated: 4 параллелизуемых wave'a + 1 финальный. Совпадает с handoff'ным «~3 недели для Phase 1» при 1 разработчике.

---

## Open questions для design phase

1. **Combined rate semantics conflict** — refactor `calculation_helpers.py:269+` или сохранить legacy formula параллельно с новым customs_calc? (REQ-4)
2. **Alerting channel** — Telegram, Sentry, оба, или log-only? (REQ-2 packet, REQ-6 failures)
3. **`tnved_rates.last_used_at`** — добавить колонку или derive из classification_log? (REQ-3 AC#7)
4. **Freeze fallback** при Alta unavailable — abort или stale-cache snapshot с warning? (REQ-8 AC#5)
5. **Re-freeze audit log** — новая таблица или changelog_service? (REQ-8 AC#4)
6. **`ALTA_LOGIN`/`ALTA_PASSWORD` lookup** — module-singleton или FastAPI Depends? (REQ-2)
7. **Where именно вызывается freeze в workflow_service** — нужен deep-dive в design.

---

## Next phase

Run `/kiro:spec-design customs-phase-1-rates-and-measures -y` (auto-approve requirements) для генерации technical design документа. Design phase должен resolve все 7 open questions выше.
