# Research / Discovery Log — control-spec-workspace

**Discovery type:** Light (extension of existing system). Основная discovery выполнена
параллельным gap-анализом (5 проб по коду) — полные находки в `gap-analysis.md`.

## Summary

- Фича — **extension**, reuse-heavy. Бэкенд (Python spec-модель, PDF/DOCX экспорт,
  `/api/deals`, workflow-переходы) почти всё уже умеет; основной труд во фронтенде.
- Все ~25 рич-полей спецификации уже есть в БД (`migrations/006` + 036/126/145/148/149/160)
  и сериализуются `services/specification_service.py`. Разрыв — отсутствует Next.js
  read/write слой.
- Reusable: `SearchableCombobox` (`shared/ui`), `KanbanBoard` (dnd-kit), `useControlChecks`/
  `VerificationStrip` (паттерн чек-листа), `callWorkflowTransition` → `POST /api/quotes/{id}/workflow/transition`,
  `confirmSignatureAndCreateDeal` → `POST /api/deals`.

## Research Log

### Топик 1 — Калькулятор не читает спец-колонки реквизитов/курса (FK-safety)
- **Investigation:** grep `our_legal_entity|client_legal_entity|*_country|signing_fx|exchange_rate_to_ruble|validity_period`
  по `calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py`, `main.py`, `api/`, `services/`.
- **Finding:** совпадения ТОЛЬКО в `services/specification_service.py` (модель спеки) и
  `services/contract_spec_docx.py:214-215` (экспорт DOCX, free-text fallback). Ноль
  совпадений в calc-engine/mapper/models.
- **Implication:** FK-миграция реквизитов **безопасна** — не нарушает «calc-engine LOCKED»
  (флаг 6 gap-анализа закрыт). Но `contract_spec_docx.py` читает `spec.get("our_legal_entity")`
  как fallback → при переходе на FK надо **дозаписывать денормализованный snapshot имени**
  в существующую VARCHAR-колонку (dual-write), чтобы экспорт не сломался.

### Топик 2 — Две машины состояний / мёртвый `pending_signature`
- **Investigation:** `workflow_service.py:541-578`, `api/deals.py:249-254`, `specification-step.tsx`.
- **Finding:** `quotes.workflow_status` (workflow_service) и `specifications.status`
  (draft/approved/signed) — параллельны. `create_deal` ставит `workflow_status='deal'`
  напрямую, минуя `pending_signature`.
- **Decision (владелец):** **реактивировать `pending_signature`** — единый источник истины
  воркфлоу = `quotes.workflow_status`; deal-handoff через `workflow_service.transition_quote_status`.
- **Implication:** даёт колонку «На подписании»; убирает третий writer.

### Топик 3 — Источники дропдаунов реквизитов
- **Finding:** `seller_companies` (org-scoped fetch в `features/companies/api`), `locations`
  (`entities/location/queries.ts`, `country` — free text), `customer_contracts` (inline-create
  уже есть). `customer_legal_entities` таблицы НЕТ.
- **Decision:** наше юрлицо → FK `seller_company_id` → `seller_companies`. Страны →
  searchable-дропдаун из distinct `locations.country` (строкой в существующие `*_country`
  VARCHAR; БЕЗ awkward FK на адрес-строку location). Юрлицо клиента → один набор read-only
  (мульти-таблица отложена).

## Architecture Decisions

| Решение | Выбор | Обоснование |
|---|---|---|
| Источник истины воркфлоу | `quotes.workflow_status` | Реактивируем `pending_signature`; не плодим writer |
| Наше юрлицо | FK `seller_company_id` + snapshot имени | Чистый FK; dual-write для экспорта |
| Страны | строка из distinct `locations.country` | location-row FK семантически странна для «страны» |
| Юрлицо клиента | read-only, один набор | мульти отложено (флаг 9) |
| Курс на подписание | новые `signing_fx_mode` + `signing_fx_rate` | lock-at-signing ≠ display-семантика `exchange_rate_to_ruble` |
| Канбан | reuse `KanbanBoard`, column-config prop | DRY; без форка dnd-логики |
| Карточки канбана | кликабельные, без drag | действие — на экране шага |

## Risks (см. полный список — `gap-analysis.md` §7)

- Номер миграции: CLAUDE.md=283 vs `migrations/`=318/319 → подтвердить на VPS до ALTER.
- `KANBAN_COLUMNS` параметризация трогает shared logistics/customs движок → regress-тест.
- `total_amount_quote` удалён (m318/319) → читать `total_quote_currency`.
- `contract_spec_docx.py` fallback на VARCHAR snapshot → dual-write обязателен.
