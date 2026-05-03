# Design Decisions — customs-phase-1-rates-and-measures

**Date resolved:** 2026-05-01
**Status:** finalized, fed into `/kiro:spec-design`

7 open questions из gap-analysis.md закрыты (Andrey, 2026-05-01) + одна архитектурная находка от Q7 explorer.

---

## Q1. Combined rate semantics conflict — **Option B**

**Решение:** Параллельные системы. Existing `services/calculation_helpers.py:269+` formula (адвалорная_pct + per_kg→pct conversion) остаётся для backwards-compat существующих quote_items. Новая `services/customs_calc.py` `max(адвалорная, специфическая)` формула применяется **только** для свежих Alta-resolved rates (identified by `tnved_rates.source ∈ {'alta-live', 'alta-revalidate'}`).

**Critical constraint (Andrey reminder 2026-05-01):** **Calc engine — `calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py` — НЕ модифицируем.** Customs_calc.py подключается через `build_calculation_inputs()` адаптер-слой. customs_calc сам по себе не вызывает engine — он вычисляет суммы и передаёт их обратно в engine как ready inputs.

**Implication для design:**
- `customs_calc.calculate_duty(rate, ...)` — pure-functional, возвращает Decimal
- Switch logic — в `build_calculation_inputs()`: если `rate.source ∈ alta-*` → call `customs_calc.calculate_duty()`, иначе fallback на existing `calculation_helpers` formula
- Documented technical debt: legacy formula path помечается comment'ом «legacy combined-rate, sunset когда все quote_items переведены на Alta-resolved rates (Phase 5+)»

---

## Q2. Alerting infrastructure — **Option A**

**Решение:** Telegram-only в Phase 1 через existing `services/telegram_service.py`. Канал — admin-channel (не customs-юзеры). Sentry откладываем как отдельный setup-task.

**Implication для design:**
- `services/alta_client.py` packet warning при `left_count < 100` → `telegram_service.notify_admin(message)`
- `api/cron.py` revalidate-rates failure / Alta unavailable → `telegram_service.notify_admin(message)`
- Reuse existing channel ID (тот же что overdue/SLA notifications)
- Throttle: max 1 alert на packet warning per hour (избегаем spam если cron срабатывает каждые 10 мин)

---

## Q3. `tnved_rates.last_used_at` — **Option A**

**Решение:** Колонка `last_used_at TIMESTAMPTZ` на `tnved_rates`, UPDATE на каждый успешный resolve.

**Implication для design:**
- REQ-1: добавить `last_used_at TIMESTAMPTZ NOT NULL DEFAULT now()` в `tnved_rates` schema
- REQ-3 `rate_resolver.py`: после успешного lookup — `UPDATE tnved_rates SET last_used_at = now() WHERE id = $1`. Можно batch'ить или fire-and-forget (не блокировать response).
- REQ-6 cron: `ORDER BY last_used_at DESC NULLS LAST LIMIT 1000` — даёт топ-1000 hot pairs

---

## Q4. Freeze fallback при Alta unavailable — **Option C + user notifications**

**Решение:** Three-tier graceful degradation:
1. Live Alta call — preferred
2. Fallback на `tnved_rates` cache не старше 30 дней — если Alta down
3. Abort если cache пуст или stale > 30 дней — message «Не удалось получить актуальные ставки для freeze»

**+ User notification на каждом fallback level:**
- Tier 1 (live success) — silent
- Tier 2 (cache fallback used) — UI toast «⚠️ Используется кэш ставок от {fetched_at}, Alta API временно недоступна. Snapshot создан, но проверьте актуальность ставок.»
- Tier 3 (abort) — UI modal «🛑 Не удалось зафиксировать ставки. Попробуйте через несколько минут. Если проблема повторяется — обратитесь к администратору.» + admin-channel Telegram alert

**Implication для design:**
- `customs_freeze_service.capture_snapshot(quote_id)` возвращает `{success, source_at_freeze, items, warnings}` где `source_at_freeze ∈ {'alta-live', 'cache-stale', 'abort'}`
- Frontend handler различает три tier'а — разный UX

---

## Q5. Re-freeze audit log — **Option B**

**Решение:** Existing `services/changelog_service.py` — customs-snapshot-replaced становится event type. Старая snapshot в audit log через standard changelog API.

**Implication для design:**
- Reuse existing changelog infrastructure
- Event type: `customs_rates_snapshot_replaced`
- Event payload: `{quote_id, old_version_id, new_version_id, replaced_by_user_id, reason, replaced_at}`
- Changelog query API уже работает в админке — visibility free

---

## Q6. ALTA_LOGIN/ALTA_PASSWORD lookup — **Option B**

**Решение:** FastAPI `Depends(get_alta_client)` инъекция в каждый endpoint, testable через `app.dependency_overrides`.

**Implication для design:**
- `services/alta_client.py` экспортирует:
  - `class AltaClient` — основной класс
  - `def get_alta_client() -> AltaClient` — factory с lazy singleton init из env (`ALTA_LOGIN`, `ALTA_PASSWORD`)
- Endpoints:
  ```python
  from fastapi import Depends
  from services.alta_client import get_alta_client, AltaClient
  
  async def resolve_rates_handler(request: Request, client: AltaClient = Depends(get_alta_client)):
      ...
  ```
- Tests:
  ```python
  app.dependency_overrides[get_alta_client] = lambda: MockAltaClient()
  ```

---

## Q7. Freeze hook point — **Option A (centralized in workflow_service)**

**Explorer findings:**
- Frozen boundary = `WorkflowStatus.APPROVED` (services/workflow_service.py:26-52)
- Transition function: `transition_quote_status(quote_id, from_status, to_status, user, reason)` at services/workflow_service.py:1231
- Hook point: services/workflow_service.py:1343-1352 (after status update commit)
- **Existing snapshot pattern:** `services/quote_version_service.py:81-150` `create_quote_version(quote_id, calculated_vars)` — stores `products_snapshot` + `input_variables` в `quote_versions` table

### 🚨 Архитектурное упрощение (от Q7 finding)

**REQ-1 changes:**
- ❌ **DROP:** `quote_items.customs_rates_snapshot JSONB` and `customs_rates_snapshot_date DATE` columns. Не добавляем эти колонки в migration 297.
- ✅ **USE INSTEAD:** Существующий `quote_versions.input_variables JSONB` extend'ится новым ключом `customs_rates`:
  ```json
  {
    "products": [...],
    "calculated_vars": {...},
    "customs_rates": {
      "{item_id}": {
        "rates": [{"payment_type": "IMP", "value_1_number": 5, "value_1_unit": "percent", "calculated_amount_rub": 50000, ...}, ...],
        "measures": [{"measure_type": "certification", "name": "...", ...}, ...],
        "fetched_at": "2026-05-01T12:34:56+00:00",
        "source_at_freeze": "alta-live"
      }
    }
  }
  ```

**REQ-3 changes:**
- AC#8 «retroactive calc reads from snapshot first» — теперь читает из `quote_versions.input_variables.customs_rates[item_id]` для frozen quotes (status >= APPROVED), live-resolve иначе

**REQ-8 implementation:**
- Hook point: `services/workflow_service.py:1343-1352` внутри `transition_quote_status()`
- Trigger: `to_status == WorkflowStatus.APPROVED`
- Action:
  ```python
  if to_status == WorkflowStatus.APPROVED:
      customs_data = await customs_freeze_service.build_snapshot(quote_id)  # Q4 three-tier
      if customs_data["status"] == "abort":
          # Q4 tier 3 — block transition
          raise FreezeAbortedError(customs_data["message"])
      
      # Extend existing quote_version creation
      quote_version_service.create_quote_version(
          quote_id,
          calculated_vars=existing_vars,
          customs_rates=customs_data["items"],
          source_at_freeze=customs_data["source_at_freeze"]  # Q4 tier 1/2
      )
  ```
- Re-freeze (explicit «Пересчитать по текущим ставкам» button):
  - Endpoint: `POST /api/quotes/{quote_id}/refresh-customs-snapshot`
  - Action: same `customs_freeze_service.build_snapshot()` → `quote_version_service.create_quote_version()` (новый row, не UPDATE) → `changelog_service.log_event('customs_rates_snapshot_replaced', ...)` (Q5b)

**Benefits архитектурного упрощения:**
- Single source of truth для всех snapshot needs (products + customs + calculated_vars в одной квартире)
- Не дублируем versioning логику — re-freeze просто новый quote_version row, history автоматически
- Меньше migration surface (2 column меньше)
- Existing audit/changelog flow покрывает customs события без новых таблиц

---

## Сводка изменений в существующих REQ

| REQ | Изменение |
|-----|-----------|
| REQ-1 | DROP `customs_rates_snapshot`, `customs_rates_snapshot_date` columns. ADD `last_used_at` to `tnved_rates`. |
| REQ-3 | AC#8 reads snapshot from `quote_versions.input_variables.customs_rates`, не из quote_items column. AC#7 use new `last_used_at` column. |
| REQ-4 | Switch legacy/new formula по `rate.source` — в `build_calculation_inputs()` адаптер-слое, НЕ в calc_engine |
| REQ-8 | Полная переработка: hook в workflow_service.transition_quote_status() при APPROVED. Использование existing quote_version_service. Three-tier fallback (Q4) + changelog audit (Q5). |
| REQ-2 | Telegram alerts через telegram_service. Throttle 1/hour для packet warnings. |
| REQ-2/REQ-5 | FastAPI Depends(get_alta_client) pattern для credentials lookup |

---

## Готовность к design phase

✅ Все 7 open questions из gap-analysis закрыты
✅ Архитектурное упрощение (Q7) задокументировано
✅ Calc engine constraint (Andrey 2026-05-01) явно зафиксирован
✅ Project-wide standards (telegram_service, changelog_service, quote_version_service, FastAPI Depends) учтены

**Next:** `/kiro:spec-design customs-phase-1-rates-and-measures -y`
