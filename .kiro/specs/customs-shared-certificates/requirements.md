# Requirements Document — customs-shared-certificates (Phase B)

## Introduction

Phase B вводит **общие сертификаты** в OneStack: новую сущность `kvota.quote_certificates` с many-to-many привязкой к позициям КП через `kvota.quote_certificate_items`. Сертификаты прикрепляются к нескольким позициям сразу, стоимость распределяется **всегда пропорционально** RUB-стоимости товара (без UI выбора). Параллельно появляется тип «Свой расход» — таможенные расходы, не связанные с конкретным сертификатом, но требующие распределения на позиции (услуги декларанта, экспертизы и т.п.). UI секции «Сертификаты на КП» (Phase A — `<QuoteCustomsExpenses />`) и «Общие расходы по таможне» (Phase A — `<ItemCustomsExpenses />`) объединяются в одну секцию **«Расходы по таможне»** с двумя кнопками. Per-item dialog получает read-only список «привязок» и popover «Привязать к существующему». Phase B также использует **уже интегрированный** `TableViewsDropdown` компонент (`customs-step.tsx:383-397`) и добавляет 4 системных вида как **виртуальные client-side строки** + hint-баннер.

**UI source-of-truth:** `docs/mockups/customs-after-phases.html` v3 (утверждён 2026-05-03; Phase B секции на строках 111, 881-1000).
**Lineage:** Phase A (customs-tariff-completeness, merged 2026-05-03 — 12 tasks, миграции 304/305) → Phase B наследует pattern history-banner и `formatDateRussian` helper, переиспользует FSD-структуру `frontend/src/features/customs-history/`.
**Architecture:** UI/API only — НИКАКИХ изменений в `calculation_engine.py` / `calculation_models.py` / `calculation_mapper.py`. Phase B практически не задействует calc-engine (cost split — отдельный helper, attribution считается в API/frontend).

**Key terminology:**
- **Общий сертификат (shared certificate)** — запись в `kvota.quote_certificates` с `is_custom_expense=FALSE`, описывающая документ соответствия (ДС ТР ТС, СС, СГР, ОТТС, EUR.1 и т.п.). Прикрепляется к ≥1 позиций через M2M.
- **Свой расход (custom expense)** — запись в той же таблице с `is_custom_expense=TRUE` и заполненным `display_name` (вместо `type`/`number`). Используется для расходов без сертификата: услуги декларанта, дополнительная экспертиза.
- **Cost split (распределение стоимости)** — алгоритм пропорционального распределения `cert.cost_rub` на привязанные позиции по их **RUB cost basis**. RUB cost basis вычисляется через Python helper `services/calculation_helpers.py:_customs_value_in_rub()` (calc-engine source-of-truth) — это **производное значение** из `purchase_price_original × quantity × currency_rate_to_rub`, **НЕ** колонка БД. Реализуется ОДНОЙ функцией: `split_cost(item_value, total_items_value, cert_cost) → share_rub` где параметры — уже готовые RUB-суммы. Sign-of-truth implementation в `services/cost_split.py` + параллельная TS-копия `frontend/src/shared/lib/cost-split.ts` с parity-тестами.
- **Loose history match** — поиск похожего сертификата в прошлых КП той же организации за последние 12 месяцев по ≥2 из 3 критериев: `hs_code`, `brand`, `supplier_id`.
- **`is_actual` флаг** — вычисляемое поле в `HistoryCertMatch`: `valid_until > today` (или `valid_until IS NULL` — бессрочный). Если `false` — UI показывает баннер «истёк, нужен новый» с кнопкой «Создать новый», а НЕ «Применить».
- **Системный вид (system view)** — preset для `customs-handsontable`, описывающий какие колонки видны. В Phase B — 4 **виртуальных client-side** вида (`Все колонки`, `Тарифы и НДС`, `Документы и сертификаты`, `Только идентификация`) с синтетическими ID `system:*`; user-editable views (через `user_table_views`) отложены на Phase C.
- **`formatDateRussian(iso)`** — существующий helper из `frontend/src/features/customs-history/lib/format-date.ts` (Phase A). Возвращает `DD.MM.YYYY`. **REUSE** — не реимплементируется.

**Locked decisions:** см. секцию «Locked Decisions» в конце документа.

---

## Requirements

### Requirement 1: DB-схема — `kvota.quote_certificates` + `kvota.quote_certificate_items` (migration 306, atomic schema + backfill)

**Objective:** Как разработчик, я хочу единую таблицу для сертификатов и custom-расходов с M2M-привязкой к позициям И атомарную миграцию данных из существующих `customs_*_expenses` таблиц, чтобы поддерживать оба сценария (общие сертификаты + свои расходы) без дублирования логики и без потери production-данных Phase A.

#### Acceptance Criteria

1. Migration `migrations/306_quote_certificates.sql` shall создавать таблицу `kvota.quote_certificates` со следующими колонками: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `quote_id UUID NOT NULL REFERENCES kvota.quotes(id) ON DELETE CASCADE`, `type TEXT NOT NULL`, `number TEXT`, `issuer TEXT`, `legal_doc TEXT`, `issued_at DATE`, `valid_until DATE`, `cost_rub NUMERIC(14,2) NOT NULL DEFAULT 0`, `notes TEXT`, `display_name TEXT` (используется ТОЛЬКО для `is_custom_expense=TRUE` записей — хранит человеко-читаемое название custom-расхода вместо type/number), `is_custom_expense BOOLEAN NOT NULL DEFAULT FALSE`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, `created_by UUID REFERENCES auth.users(id)`.
2. Migration shall создавать таблицу `kvota.quote_certificate_items` со следующими колонками: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `certificate_id UUID NOT NULL REFERENCES kvota.quote_certificates(id) ON DELETE CASCADE`, `item_id UUID NOT NULL REFERENCES kvota.quote_items(id) ON DELETE CASCADE`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, и UNIQUE constraint `(certificate_id, item_id)`.
3. Migration shall добавлять CHECK constraint `quote_certificates_cost_rub_nonneg CHECK (cost_rub >= 0)` на таблицу `quote_certificates`.
4. Migration shall создавать индексы: `idx_quote_certificates_quote_id ON quote_certificates(quote_id)`, `idx_quote_certificate_items_cert ON quote_certificate_items(certificate_id)`, `idx_quote_certificate_items_item ON quote_certificate_items(item_id)`.
5. Migration shall быть **идемпотентной**: использовать `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, `ALTER TABLE … ADD CONSTRAINT IF NOT EXISTS` (либо guard через `pg_constraint` lookup).
6. Migration shall включать RLS-политики на обеих таблицах (паттерн миграции 293 — multi-table JOIN через `organization_members` + `user_roles` + `roles`, **НЕ** JWT-claim паттерн миграции 304):
   - **WRITE** (INSERT/UPDATE/DELETE) разрешён только пользователям с `r.slug IN ('customs', 'admin', 'head_of_customs')`.
   - **READ** (SELECT) разрешён `r.slug IN ('customs', 'admin', 'head_of_customs', 'sales', 'quote_controller', 'spec_controller', 'finance', 'top_manager')`.
   - Обе политики используют именно `r.slug` (НЕ `r.code`).
   - SELECT policy фильтрует через `organization_members.status = 'active'` (паттерн 293).
   - В заголовке SQL-файла должен быть комментарий, объясняющий почему выбран 293-паттерн (а не 304 JWT-claim) — для предотвращения copy-paste путаницы будущими миграциями.
7. Migration shall **АТОМАРНО** (в той же транзакции, после создания таблиц и до коммита) выполнять backfill данных из существующих Phase A таблиц:
   - **Из `kvota.customs_quote_expenses`**: для каждой строки INSERT INTO `kvota.quote_certificates` с маппингом `customs_quote_expenses.label → quote_certificates.display_name`, `amount_rub → cost_rub`, `notes → notes`, `quote_id → quote_id`, `created_by → created_by`, `created_at → created_at`, `is_custom_expense=TRUE`, `type='custom_expense'`, остальные cert-поля (`number`, `issuer`, `legal_doc`, `issued_at`, `valid_until`) = NULL. Затем INSERT INTO `kvota.quote_certificate_items` по одной строке per `quote_item` в этом КП (расход на КП → распределяется на ВСЕ позиции КП).
   - **Из `kvota.customs_item_expenses`**: для каждой строки INSERT INTO `kvota.quote_certificates` с тем же маппингом (`label → display_name`, `amount_rub → cost_rub`, и т.д.), но `quote_id` берётся из JOIN-а на `quote_items.quote_id`. Затем INSERT INTO `kvota.quote_certificate_items` ОДНУ строку с `item_id = customs_item_expenses.quote_item_id` (per-item расход → одна привязка). Если несколько строк `customs_item_expenses` имеют одинаковый `label` в рамках одного КП и относятся к разным `quote_item_id`, **multi-attach** — создать ОДИН `quote_certificates` row с `display_name=label` и N `quote_certificate_items` строк (по одной на каждый item).
   - Backfill SQL должен использовать `INSERT INTO ... SELECT ...` без отдельных application-side скриптов — всё в одном SQL-файле.
8. Migration shall **НЕ** удалять старые таблицы `customs_item_expenses` и `customs_quote_expenses` — drop-migration отложен на отдельный последующий релиз после production-верификации целостности данных. Phase B сохраняет обе схемы кратковременно coexisting.
9. Where сертификат с привязками удаляется, FK `ON DELETE CASCADE` shall автоматически удалять все строки `quote_certificate_items`. Where позиция КП (`kvota.quote_items`) удаляется, FK shall автоматически удалять её привязки в `quote_certificate_items` (но НЕ сам сертификат).
10. Migration shall применяться через `scripts/apply-migrations.sh` (стандартный путь проекта; ручной `psql` запрещён по проектной конвенции).
11. После применения migration `cd frontend && npm run db:types` shall быть выполнен — `frontend/src/database.types.ts` обновляется и tsc остаётся зелёным.

---

### Requirement 2: Backend API — CRUD endpoints для сертификатов

**Objective:** Как frontend / AI-агент, я хочу получать атомарные REST-эндпоинты для создания, чтения, привязки/отвязки, удаления сертификатов, чтобы UI и автоматизация имели одну точку доступа без дублирования логики.

#### Acceptance Criteria

1. `POST /api/customs/certificates` shall принимать body `{quote_id: UUID, type: string, number?: string, issuer?: string, legal_doc?: string, issued_at?: string (ISO date), valid_until?: string (ISO date), cost_rub: number, notes?: string, display_name?: string, is_custom_expense?: boolean (default false), item_ids: UUID[]}` и атомарно создавать одну запись `quote_certificates` + N записей `quote_certificate_items` (где N = `item_ids.length`).
2. Endpoint shall возвращать в `response.data` полный сертификат с вычисленным `attached_items: [{item_id: UUID, share_rub: number, share_percent: number}]` массивом, где `share_rub` рассчитан через helper из Requirement 3.
3. `GET /api/customs/certificates?quote_id={uuid}` shall возвращать массив всех сертификатов и custom-расходов для указанного КП с тем же `attached_items` per cert (та же структура, что POST response).
4. `POST /api/customs/certificates/{cert_id}/items` shall принимать body `{item_id: UUID}` и создавать одну запись `quote_certificate_items`. Endpoint shall возвращать в `response.data` обновлённый сертификат с пересчитанным `attached_items` (доли всех привязанных позиций пересобираются).
5. `DELETE /api/customs/certificates/{cert_id}/items/{item_id}` shall удалять одну запись `quote_certificate_items`. Endpoint shall возвращать в `response.data` обновлённый сертификат с пересчитанным `attached_items` (или с пустым массивом, если последняя привязка снята).
6. `DELETE /api/customs/certificates/{cert_id}` shall каскадно удалять сертификат и все его привязки (через FK `ON DELETE CASCADE`). Endpoint shall возвращать `{success: true, data: {deleted_id: UUID}}`.
7. `GET /api/customs/certificates/history?hs_code={code}&brand={brand}&supplier_id={uuid}` shall искать предыдущий сертификат по loose-match алгоритму (Requirement 5) и возвращать `{success: true, data: {match: HistoryCertMatch | null}}` где `HistoryCertMatch = {cert_id: UUID, type: string, number: string | null, issuer: string | null, legal_doc: string | null, issued_at: string | null, valid_until: string | null, cost_rub: number, created_at: string, source_quote_id: UUID, source_item_id: UUID, is_actual: boolean}`.
8. Все endpoints shall использовать **dual auth**: проверять `request.state.api_user` (JWT через ApiAuthMiddleware) ИЛИ legacy session — стандартный паттерн strangler-fig migration.
9. Где user не авторизован, endpoints shall возвращать HTTP 401 с `{success: false, error: {code: "UNAUTHORIZED", message: "..."}}`.
10. Where user авторизован но не имеет роли `customs/admin/head_of_customs` для write-операций (POST/DELETE), endpoints shall возвращать HTTP 403 с `{success: false, error: {code: "FORBIDDEN", message: "..."}}`. READ-операции (GET) допускают расширенный список ролей per Requirement 1 AC#6. Write-role gate использует существующую константу `_CUSTOMS_ROLES = {"customs", "admin", "head_of_customs"}` определённую в `api/customs.py:36`.
11. Where `cert.quote_id` НЕ совпадает с `item.quote_id` при попытке привязки (POST `/items`), endpoint shall возвращать HTTP 422 с `{code: "NOT_IN_QUOTE", message: "Позиция не принадлежит КП сертификата"}`. Cross-quote isolation — критичная защита целостности данных.
12. Where validation падает (например `cost_rub < 0`, отсутствует `quote_id`), endpoints shall возвращать HTTP 400 с `{code: "VALIDATION_ERROR", message: "...", field: "cost_rub"}`.
13. Where `cert_id` или `item_id` не существует, endpoints shall возвращать HTTP 404 с `{code: "NOT_FOUND", message: "..."}`.
14. POST endpoint shall выполнять создание cert + всех item_ids в **одной транзакции** — если хотя бы одна привязка падает (например, item_id из чужого КП), отмена всей операции (rollback).
15. Все endpoints shall возвращать стандартный envelope `{success: boolean, data?: object, error?: {code, message, field?}}` совместимый с остальными `/api/customs/*` эндпоинтами Phase A.
16. Существующие endpoints `POST/PATCH/DELETE /api/customs/expenses/*` (Phase A — `customs_item_expenses` + `customs_quote_expenses` CRUD из `api/customs.py:605-797`) shall быть **удалены в том же PR** что и UI-секции (Requirement 6 AC#9) — для предотвращения накопления dead-code путей. Старые таблицы остаются в БД временно (Requirement 1 AC#8), но кодовых путей записи в них больше нет.

---

### Requirement 3: Shared cost-split helper (Python + TypeScript parity)

**Objective:** Как разработчик, я хочу одну функцию пропорционального распределения, реализованную в Python и TypeScript с **parity-тестами на общих фикстурах**, чтобы backend (`response.data.attached_items`) и frontend (live-preview в модалке/popover) выдавали идентичные числа без drift.

#### Acceptance Criteria

1. Файл `services/cost_split.py` shall экспортировать чистую функцию `split_cost(item_value: Decimal, total_items_value: Decimal, cert_cost: Decimal) -> Decimal` использующую `decimal.Decimal` для точности. Параметр `item_value` — это **RUB cost basis позиции** (уже вычисленная сумма в рублях, НЕ колонка БД). Возвращаемое значение округляется до 2 знаков (копейки) через `Decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`.
2. Backend callers shall вычислять `item_value` через существующий Python helper `services/calculation_helpers.py:_customs_value_in_rub(item, quote_currency, convert_amount)` (calc-engine source-of-truth). Helper берёт `purchase_price_original × quantity` и конвертирует в RUB через `convert_amount`. Helper остаётся в `calculation_helpers.py`; Phase B импортирует его (или re-export через `services/cost_split.py` для удобства). Calc-engine модули (`calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py`) **не модифицируются** — `_customs_value_in_rub` живёт в `calculation_helpers.py` и не входит в их состав.
3. Файл `frontend/src/shared/lib/cost-split.ts` shall экспортировать чистую функцию `splitCost(itemValue: number, totalItemsValue: number, certCost: number): number` округляющую до 2 знаков через explicit half-up shim `Math.floor(value * 100 + 0.5) / 100` (НЕ `Math.round` — JS Math.round использует banker's rounding на половинных значениях, что несовместимо с Python `ROUND_HALF_UP`).
4. Frontend callers shall вычислять `itemValue` идентичной формулой: `purchase_price_original × quantity × currency_rate_to_rub`. `currency_rate_to_rub` берётся из существующего quote-level rate context, уже доступного в state модалок/popover-ов (`customs-item-dialog.tsx` уже читает rate в текущем состоянии — никаких новых fetch-вызовов Phase B не вводит). Frontend helper НЕ имитирует backend `convert_amount` логику для multi-step конверсий — для Phase B достаточно одношаговой конвертации `src_currency → RUB`.
5. Where `total_items_value === 0` (deg-case: все позиции с нулевой стоимостью или единственная позиция со стоимостью 0), helper shall использовать **fallback equal-split**: `cert_cost / N` где N — количество привязанных позиций. Это единственное исключение из «пропорционально стоимости» правила.
6. Where `N === 1` (один привязанный item), helper shall возвращать `cert_cost` целиком (100%).
7. При суммировании всех `share_rub` для нескольких позиций может возникнуть rounding residual (sum != cert_cost из-за округления). API shall гарантировать что `sum(shares) == cert_cost` копейка-в-копейку: **последняя позиция в массиве (отсортированном по `created_at`) поглощает residual**: `last_share = cert_cost - sum(others)`.
8. Helper shall использоваться backend в `GET /api/customs/certificates` и `POST /api/customs/certificates/{cert_id}/items` для вычисления `attached_items[].share_rub` (Requirement 2 AC#2/AC#4).
9. Helper shall использоваться frontend для live-preview в модалке «+ Добавить сертификат» (Requirement 7), popover «Привязать к существующему» (Requirement 8) и read-only display в per-item dialog (Requirement 9).
10. Файл `tests/services/test_cost_split.py` shall покрывать минимум 6 сценариев:
    (a) одна позиция → 100%,
    (b) две равные позиции → 50/50,
    (c) три позиции с разной стоимостью (150к / 350к / 90к от 590к total, cert_cost=12500) → точные доли,
    (d) `total_items_value = 0` → equal split fallback,
    (e) rounding residual (cert_cost=10₽, 3 позиции) → последняя поглощает остаток,
    (f) большие числа (cert_cost=999999.99, N позиций) — округление без drift.
11. Файл `frontend/src/shared/lib/__tests__/cost-split.test.ts` shall покрывать те же 6 сценариев с **идентичными фикстурами**.
12. Файл `tests/fixtures/cost_split_fixtures.json` shall содержать массив объектов `{name, purchase_price_original, purchase_currency, quantity, currency_rate_to_rub, cert_cost, n_items, expected_share}`. Оба теста (Python + TS) загружают этот файл, **идентичной формулой** вычисляют RUB cost basis (`purchase_price_original × quantity × currency_rate_to_rub`), затем передают в `split_cost`/`splitCost` и сравнивают output с `expected_share`. Любое расхождение между Python и TS падает в CI.

---

### Requirement 4: `valid_until` expiry — explicit user prompt

**Objective:** Как customs-специалист, я хочу что система **явно** уведомляла когда сертификат истёк (а не silent-применяла или скрывала), чтобы я осознанно создавал новый и не использовал устаревший документ для оформления ДТ.

#### Acceptance Criteria

1. Where `cert.valid_until IS NULL`, UI shall интерпретировать сертификат как **бессрочный** — никакой warning, прикрепляется как обычно, рендерится в обычной (emerald) рамке.
2. Where `cert.valid_until > today` (today = `CURRENT_DATE` в backend, `new Date()` в frontend, обе нормализованы к началу дня UTC), UI shall интерпретировать сертификат как **актуальный** — рендерится в обычной (emerald) рамке, доступен для привязки новых позиций.
3. Where `cert.valid_until <= today`, UI shall:
   - Рендерить cert-card в секции «Расходы по таможне» с **красной рамкой** (через design-system красный токен; НИКАКОГО hex-кодирования вроде `#ef4444`).
   - **Блокировать** action «Привязать к существующему» в popover Requirement 8 для этого cert (radio disabled с tooltip «Сертификат истёк {DD.MM.YYYY}»).
   - Показывать дату истечения отформатированную через `formatDateRussian(cert.valid_until)` (формат `DD.MM.YYYY`).
4. Where в response от `GET /api/customs/certificates/history` (Requirement 5) поле `match.is_actual === false`, баннер в per-item dialog shall использовать копию: **«Прежний сертификат истёк {DD.MM.YYYY}, нужен новый ~{cost_rub}₽»** где `{DD.MM.YYYY}` — `formatDateRussian(match.valid_until)`, `{cost_rub}` — `match.cost_rub` отформатированный как «12 500».
5. Where `match.is_actual === false`, primary action button shall быть **«Создать новый»** (НЕ «Применить»). Click открывает модалку Requirement 7 с pre-filled полями `type` (из `match.type`) и `cost_rub` (из `match.cost_rub`); пользователь сам заполняет новые `number`, `issued_at`, `valid_until`.
6. Where `match.is_actual === true`, primary action button shall быть **«Применить»** (Requirement 5). Никакого preset cost — переиспользуем существующий cert через POST `/certificates/{cert_id}/items`.
7. Date formatting shall использовать существующий helper `formatDateRussian` из `frontend/src/features/customs-history/lib/format-date.ts` — **REUSE**, реимплементация запрещена.
8. Where backend сравнивает `valid_until <= today`, сравнение shall выполняться в SQL `(valid_until IS NOT NULL AND valid_until <= CURRENT_DATE)` — для консистентности с frontend нормализацией.

---

### Requirement 5: Cost-aware history autofill

**Objective:** Как customs-специалист, я хочу что при заполнении новой позиции с уже встречавшимся `(hs_code, brand, supplier)` система предлагала переиспользовать предыдущий сертификат (если актуален) или создать новый по тому же шаблону (если истёк) — чтобы не вводить одно и то же десять раз и не пропустить дополнительные расходы на просроченные документы.

#### Acceptance Criteria

1. Endpoint `GET /api/customs/certificates/history?hs_code={code}&brand={brand}&supplier_id={uuid}` shall искать сертификаты в `kvota.quote_certificates` JOIN `quote_certificate_items` JOIN `quote_items` со следующими фильтрами:
   - `quote_certificates.created_at >= NOW() - INTERVAL '12 months'` (12-месячное окно).
   - `quotes.organization_id = current_user.organization_id` (multi-tenant isolation — никогда не возвращать сертификаты других организаций).
   - **Loose match**: минимум 2 из 3 критериев совпадают: `quote_items.hs_code = :hs_code`, `quote_items.brand = :brand`, `quote_items.supplier_id = :supplier_id`. Логика реализуется через CASE WHEN-сумму счётчика matches.
   - `quotes.id != current_quote_id` (исключаем тот же КП — пользователь видит существующие сертификаты КП через секцию «Расходы по таможне»).
2. Endpoint shall возвращать **последний** match (`ORDER BY quote_certificates.created_at DESC LIMIT 1`) либо `null` если ничего не найдено.
3. `is_actual` shall вычисляться в SQL: `(valid_until IS NULL OR valid_until > CURRENT_DATE) AS is_actual`.
4. Где запрос пришёл от пользователя без `organization_id` или с невалидным token, endpoint shall возвращать HTTP 401.
5. Frontend per-item dialog (`customs-item-dialog.tsx`) shall **в фоне** вызывать `fetchCertificateHistory(hs_code, brand, supplier_id)` при открытии диалога для НОВОЙ позиции с уже заполненным `hs_code` — debounce 300мс если поля редактируются.
6. Where `match` non-null И `is_actual === true`, frontend shall рендерить баннер над секцией «Сертификация» (синий info-border через design-system токен): **«Возможно подойдёт сертификат {type} №{number} от {DD.MM.YYYY}, ~{cost_rub}₽»** + button **«Применить»**.
7. Where `match` non-null И `is_actual === false`, frontend shall рендерить баннер с amber/warning border: **«Прежний сертификат истёк {DD.MM.YYYY}, нужен новый ~{cost_rub}₽»** + button **«Создать новый»** (Requirement 4 AC#5).
8. Click на «Применить» shall вызвать `POST /api/customs/certificates/{match.cert_id}/items {item_id: current_item_id}` — переиспользование существующего сертификата.
9. Click на «Создать новый» shall открыть модалку Requirement 7 с pre-filled `type` и `cost_rub` из match.
10. Where ни «Применить», ни «Создать новый» не нажат (пользователь закрывает баннер через «×»), shall не выполняться никаких автоматических действий — **NO silent autofill, NO auto-apply**.
11. Where в течение сессии пользователь редактирует `hs_code` / `brand` / `supplier_id`, frontend shall повторно дёргать endpoint с новыми значениями (или скрыть баннер если match теперь null).

---

### Requirement 6: Unified UI section «Расходы по таможне»

**Objective:** Как customs-специалист, я хочу видеть все таможенные расходы (сертификаты + свои расходы) в одной секции с двумя кнопками добавления, чтобы не путаться между «Сертификатами на КП» и «Общими расходами по таможне» (Phase A разделение).

#### Acceptance Criteria

1. Страница `customs-step.tsx` (`frontend/src/features/quotes/ui/customs-step/customs-step.tsx`) shall иметь **одну** секцию с заголовком «Расходы по таможне», **заменяющую** существующие компоненты `<QuoteCustomsExpenses />` (`customs-step.tsx:419`) и `<ItemCustomsExpenses />` (`customs-step.tsx:411`). Компонент `<CustomsExpenses />` (`customs-step.tsx:421` — calc-engine variables form для «Таможенный сбор / Сертификат происхождения / Документация / Брокерские расходы», подключённый к `quote_versions.input_variables`) **остаётся untouched** — это разные концепции.
2. Header секции shall содержать заголовок + две кнопки справа:
   - **«+ Добавить сертификат»** — открывает модалку Requirement 7 с `is_custom_expense=false`. Реализуется через shadcn `<Button variant="default">` из `@/components/ui/button`.
   - **«+ Добавить расход»** — открывает модалку Requirement 10 (упрощённая) с `is_custom_expense=true`. Реализуется через shadcn `<Button variant="secondary">`.
3. Body секции shall рендерить вертикальный stack карточек, по одной на каждую запись `quote_certificates` для текущего КП. Сертификаты и расходы перемешаны (single feed), сортировка `ORDER BY created_at DESC`.
4. Cert-card (`is_custom_expense=false`) shall содержать:
   - Бейджик с `type` (через design-system tokens; цвет — emerald/success).
   - Номер `№{number}` (если задан).
   - `cost_rub` отформатированный как «12 500 ₽».
   - Counter «{N} из {M} позиций» где N — `attached_items.length`, M — общее количество `quote_items` в КП.
   - `total_attributed = cost_rub` (вся стоимость распределена).
   - Дата `valid_until` форматированная через `formatDateRussian` если задана; красная рамка если истекла (Requirement 4 AC#3).
5. Custom-expense card (`is_custom_expense=true`) shall содержать:
   - Бейджик **«Расход»** (нейтральный gray цвет — design-system token, **НЕ** hex).
   - `display_name` (вместо номера сертификата) — это реальная колонка таблицы `quote_certificates` (Requirement 1 AC#1).
   - `cost_rub` отформатированный как «12 500 ₽».
   - Counter «{N} из {M} позиций».
   - **БЕЗ** `valid_until` строки, **БЕЗ** `type` бейджика, **БЕЗ** `legal_doc` ссылки.
6. Click на cert-card shall:
   - Open edit-modal (Requirement 7) если user имеет роль `customs/admin/head_of_customs`.
   - Open read-only details modal (Requirement 9 footer) если user имеет одну из read-ролей.
7. Where в КП нет ни сертификатов, ни расходов, секция shall рендерить empty state: текст **«Расходов нет»** + helper-текст **«Нажмите ➕ чтобы добавить сертификат или расход»** + (опционально) центрированную пару кнопок дублирующих header.
8. Все цвета карточек, отступы, шрифты shall использовать design-system токены / Tailwind классы (`bg-accent`, `text-text-muted`, `border-border-light`, `bg-success-bg` и т.п. из `design-system.md`). Inline `style=` для colors/fonts/spacing запрещён. Hex-коды запрещены — только токены.
9. Существующие компоненты `<QuoteCustomsExpenses />` + `<ItemCustomsExpenses />` shall быть **удалены** из `customs-step.tsx` (НЕ закомментированы — полное удаление per code-quality правил «no dead code»). Их данные перенесены в `quote_certificates` через atomic backfill в migration 306 (Requirement 1 AC#7). Старые таблицы `customs_*_expenses` остаются в БД временно (drop отложен — Requirement 1 AC#8). API endpoints `POST/PATCH/DELETE /api/customs/expenses/*` shall быть удалены в том же PR (Requirement 2 AC#16).

---

### Requirement 7: Modal «+ Добавить сертификат» с multi-select + live preview

**Objective:** Как customs-специалист, я хочу одну модалку для создания сертификата, выбора N позиций и видеть **в реальном времени** как распределится стоимость, чтобы не угадывать доли и не перепроверять расчёт после сохранения.

#### Acceptance Criteria

1. Модалка `frontend/src/features/customs-certificates/ui/certificate-modal.tsx` shall иметь заголовок **«Новый сертификат»** при создании или **«Редактирование сертификата»** при edit-flow.
2. Layout: **two-column** на desktop (форма ~60% ширины слева, live-preview панель ~40% справа), single-column на узких viewport (`< 768px`).
3. Form fields (top to bottom, **в указанном порядке**):
   - **`type`** — searchable Combobox (REQUIRED). Initial options seeded constants: `["ДС ТР ТС", "СС", "СГР", "ОТТС", "EUR.1", "Form A", "CT-1", "CT-2", "CT-3", "A.TR"]`. User может ввести custom value (Combobox `creatable`).
   - **`number`** — TEXT input (optional).
   - **`issuer`** — TEXT input (optional, e.g. «Сертэксперт ЦСМ»).
   - **`legal_doc`** — TEXT input (optional, e.g. «ТР ТС 010/2011»).
   - **`issued_at`** — date picker (optional, формат отображения `DD.MM.YYYY`).
   - **`valid_until`** — date picker (optional, NULLABLE = бессрочный, helper-текст «Оставьте пустым для бессрочного»).
   - **`cost_rub`** — numeric input с suffix «₽» (REQUIRED, validate `>= 0`).
   - **`notes`** — multiline textarea (optional, 3 rows default).
4. Под формой — multi-select панель с заголовком «Прикрепить к позициям»:
   - Список `quote_items` для текущего КП с checkbox per row.
   - Каждая строка отображает: `№{position} {item.name}` + правым колонок **derived RUB cost basis** (вычисленный per Requirement 3 AC#4: `purchase_price_original × quantity × currency_rate_to_rub`) отформатированный как «150 000 ₽».
   - Поверх списка — search input («🔎 Поиск по названию/SKU») фильтрующий список case-insensitive.
   - Кнопка **«Выбрать все»** / **«Снять все»** (toggle).
5. Live preview панель (правая колонка) shall рендерить:
   - Header: «Распределение стоимости».
   - Для каждой выбранной позиции — строку `№{position} {item.name} → {share_rub} ₽ ({share_percent}%)` где `share_rub`/`share_percent` рассчитаны через helper Requirement 3 на основе **derived RUB cost basis** (НЕ литеральное чтение `cost_rub` колонки — её на `quote_items` не существует).
   - Итоговую строку «Всего: {sum_shares} ₽» (равно `cost_rub` целиком).
   - Empty state «Выберите позиции для распределения» если ни одна позиция не выбрана.
   - Recalculation triggers on every: toggle позиции, изменение `cost_rub`. Debounce 0мс (мгновенный пересчёт — расчёт дешёвый).
6. Submit (кнопка **«Сохранить»**) shall вызывать `POST /api/customs/certificates` с body из формы + `item_ids` из multi-select.
7. Where API возвращает success, модалка shall закрыться, секция «Расходы по таможне» (Requirement 6) обновиться (через `revalidatePath` или RSC re-fetch).
8. Where API возвращает error, модалка shall **остаться открытой** с сохранёнными значениями + рендерить toast c `error.message` (через design-system toast component). Поле с ошибкой (если `error.field` указан) shall быть подсвечено красной рамкой + inline error-text.
9. **ALL dropdowns/selects** в модалке shall быть searchable Combobox (project-wide standard re-confirmed 2026-05-01, memory `feedback_searchable_select.md`). NO plain `<select>`, NO unsearchable shadcn `<Select>`. Реализация — паттерн `frontend/src/shared/ui/geo/country-combobox.tsx` (Popover + Input + filtered list; cmdk не требуется).
10. Compliance: shadcn `<Button variant="default">` и `<Button variant="secondary">` из `@/components/ui/button`. Inter font. Constrained scales (font 11/12/14/16/18/20/24px, space 4/6/8/12/16/20/24/32/48px). Design tokens (Slate/Copper system из `design-system.md`). NO `transition: all`. NO `transform: translateY()` on hover. NO inline `style=` для colors/fonts/spacing.
11. Кнопки footer: **«Отмена»** (`<Button variant="ghost">`) + **«Сохранить»** (`<Button variant="default">`). Tab-order: form fields → multi-select → buttons.

---

### Requirement 8: Popover «Привязать к существующему» в per-item dialog

**Objective:** Как customs-специалист, я хочу из карточки конкретной позиции быстро привязать её к УЖЕ существующему сертификату КП без открытия большой модалки, чтобы не пересоздавать сертификат который уже есть для других позиций этого же КП.

#### Acceptance Criteria

1. В `customs-item-dialog.tsx` (`frontend/src/features/quotes/ui/customs-step/customs-item-dialog.tsx`) shall появиться секция **«Сертификация»** (НИЖЕ существующих секций тарифов/НДС из Phase A; UPPERCASE заголовок через `.text-xs uppercase` design-system класс).
2. Секция shall быть видима ТОЛЬКО когда `item.hs_code` задан (без HS-кода нет смысла привязывать сертификат).
3. Where позиция НЕ имеет привязанных сертификатов (`item.attached_certificates.length === 0`), секция shall рендерить amber-bordered card (мокап строки 901-910) c копией: **«Сертификат соответствия не оформлен»** (точная копия из мокапа line 904) и двумя кнопками снизу:
   - **«Привязать к существующему»** — открывает popover.
   - **«Создать новый»** (`<Button variant="default">`) — открывает модалку Requirement 7 с pre-selected текущей позицией.
4. Click «Привязать к существующему» shall открывать `shadcn` Popover (из `@/components/ui/popover`) anchored на кнопке. Width ~360px.
5. Header popover'а shall содержать копию: **«Привязать позицию №{N} «{item.name}» к сертификату»** (точная копия из мокапа line 948) где `{N}` — порядковый номер позиции в КП, `{item.name}` — `item.name`.
6. Body popover'а shall содержать:
   - Search input «🔎 Поиск по типу/номеру» фильтрующий список case-insensitive.
   - Radio-list существующих сертификатов **только из этого же КП** (`quote_id` совпадает). Каждая строка — radio + блок с текстом:
     - Line 1: type + space + number (e.g. «ДС ТР ТС 010/2011»).
     - Line 2 (mono, smaller): полный `number` (e.g. «ЕАЭС N RU Д-CN.РА04.B.12345/26»).
     - Line 3 (smallest, neutral): `cost_rub` + «уже на N позициях» где N = `cert.attached_items.length`.
   - Истёкшие сертификаты (`valid_until <= today` per Requirement 4) shall быть disabled с tooltip «Сертификат истёк {DD.MM.YYYY}».
7. Where в popover выбран радио, **after-attach preview block** shall появиться над кнопками footer (мокап lines 968-977): info-border-blue card с текстом:
   - Line 1: «После привязки к {selected.type} (выбрано):»
   - Line 2 (subtle): «Стоимость распределится на N позиций по новой пропорции:» где N = `selected.attached_items.length + 1`.
   - Block per item: «№{position} ({item_rub_basis} ₽ / {total_rub_basis} ₽) → **{new_share}** ₽» (текущая item highlighted amber per мокап line 974). `item_rub_basis` и `total_rub_basis` — **derived RUB-суммы** (per Requirement 3 AC#4: `purchase_price_original × quantity × currency_rate_to_rub`), **НЕ** прямое чтение `cost_rub` колонки (её не существует на `quote_items`).
   - `new_share` рассчитывается через helper Requirement 3 БЕЗ POST на backend (frontend pure compute).
8. Footer popover'а shall содержать кнопки: **«Отмена»** (`<Button variant="ghost">`) + **«Привязать»** (`<Button variant="default">`).
9. Click «Привязать» shall:
   - Optimistic update: locally append item к `cert.attached_items` (UI обновляется мгновенно).
   - В фоне POST `/api/customs/certificates/{cert_id}/items` body `{item_id}`.
   - On success — popover закрывается, dialog rerenders Requirement 9 list section.
   - On error — rollback optimistic update, toast с error.message.
10. Where в КП ещё НЕТ ни одного сертификата (empty list), popover shall рендерить empty state: «В этом КП ещё нет сертификатов. Создайте новый.» + link открывающий Requirement 7 modal.
11. **Search input** в popover shall быть реализован через searchable Combobox-pattern (project-wide standard) — composition `Popover + Input + filtered list`, **НЕ** plain `<input type="search">`.

---

### Requirement 9: Per-item dialog read-only certificate coverage list

**Objective:** Как customs-специалист, я хочу видеть из карточки конкретной позиции **все** прикреплённые к ней сертификаты с моей долей (в рублях и процентах), чтобы понимать: какие документы покрывают эту позицию и сколько рублей будет добавлено в landed-cost.

#### Acceptance Criteria

1. Секция **«Сертификация»** в `customs-item-dialog.tsx` shall рендерить список emerald-bordered cards (мокап lines 887-900), по одной на каждый `attached_certificate` для текущей позиции.
2. Cert-card (когда cert является сертификатом, `is_custom_expense=false`) shall содержать:
   - Top row: бейджик с `cert.type` (success/emerald цвет) + копия **«Покрыта общим сертификатом»** (точная из мокапа line 890).
   - Sub row (subtle): `№{cert.number} · доля **{share_rub}** ₽ ({share_percent}% пропорционально стоимости {item_rub_basis} / {total_rub_basis})` где `share_rub`/`share_percent` рассчитаны через helper Requirement 3, а `item_rub_basis` / `total_rub_basis` — **derived RUB-суммы** (Requirement 3 AC#4: `purchase_price_original × quantity × currency_rate_to_rub`). Внутренняя документация ссылается на helper `services/calculation_helpers.py:_customs_value_in_rub()`; пользовательский текст остаётся без изменений по сути — просто больше не привязан к несуществующей колонке.
   - Footer buttons: **«Открыть сертификат»** (открывает read-only details modal — AC#7) + **«Отвязать»** (visible ТОЛЬКО для `customs/admin/head_of_customs`).
3. Custom-expense card (`is_custom_expense=true`) shall рендериться с **gray-bordered** card (вместо emerald) и содержать:
   - Top row: бейджик **«Расход»** (gray цвет — design-system token) + `cert.display_name`.
   - Sub row: `доля **{share_rub}** ₽ ({share_percent}%)` (БЕЗ строки «Покрыта общим сертификатом»).
   - Footer buttons: **«Подробнее»** (open read-only details — AC#7) + **«Отвязать»** (role-gated).
4. Where позиция имеет несколько прикреплённых cert/expenses, cards shall рендериться stack (вертикально), отсортированные `ORDER BY cert.created_at DESC`.
5. Где `cert.valid_until <= today` (истёк), card shall иметь **красную рамку** (Requirement 4 AC#3) поверх обычной emerald — визуальный приоритет: красный border > emerald.
6. Click **«Отвязать»** shall:
   - Optimistic: удалить cert из локального `item.attached_certificates`.
   - Background DELETE `/api/customs/certificates/{cert_id}/items/{item_id}`.
   - On error: rollback + toast.
   - **Visible только для customs/admin/head_of_customs** — кнопка скрыта для read-ролей (sales, finance и т.п.).
7. Click **«Открыть сертификат»** / **«Подробнее»** shall открывать **read-only details modal** содержащую:
   - Все поля cert: `type`, `number`, `issuer`, `legal_doc`, `issued_at`, `valid_until`, `cost_rub`, `notes`, `created_at`, `created_by`.
   - Таблицу «Прикреплено к {N} позициям» со строками `№{position} {item.name} → {share_rub} ₽ ({share_percent}%)` где `share_rub` приходит уже pre-rounded из API (вычислен через helper Requirement 3 на backend).
   - НЕТ edit-формы (редактирование только через cert-card click в Requirement 6).
   - Кнопка footer: **«Закрыть»** (`<Button variant="ghost">`).
8. Where позиция НЕ имеет привязанных сертификатов (`attached_certificates.length === 0`), вместо списка cards shall рендериться amber-bordered card из Requirement 8 AC#3 (с кнопками «Привязать к существующему» / «Создать новый»).
9. Все share-числа (rub + percent) shall рассчитываться через helper Requirement 3 — backend возвращает их в `attached_items[]`, frontend не пересчитывает.

---

### Requirement 10: «Свой расход» — упрощённая модалка для custom-expense

**Objective:** Как customs-специалист, я хочу добавить **расход без сертификата** (услуги декларанта, дополнительная экспертиза, нестандартный платёж) и распределить его на N позиций так же пропорционально, как обычный сертификат — но без обязательных полей сертификата (`type`, `number`, `valid_until`).

#### Acceptance Criteria

1. Кнопка **«+ Добавить расход»** в header секции «Расходы по таможне» (Requirement 6 AC#2) shall открывать упрощённую модалку с заголовком **«Новый расход»**.
2. Form fields (упрощённые vs Requirement 7):
   - **`display_name`** — TEXT input (REQUIRED, e.g. «Услуги декларанта», «Дополнительная экспертиза»). Placeholder подсказывает примеры.
   - **`notes`** — multiline textarea (optional, описание услуги).
   - **`cost_rub`** — numeric input с suffix «₽» (REQUIRED, `>= 0`).
   - Multi-select позиций (идентичный Requirement 7 AC#4) + live-preview panel (идентичный Requirement 7 AC#5).
3. Модалка shall **НЕ** содержать поля: `type`, `number`, `issuer`, `legal_doc`, `issued_at`, `valid_until` (эти поля останутся `NULL` в DB).
4. Submit shall вызывать `POST /api/customs/certificates` с body:
   ```
   {
     quote_id, display_name, notes?, cost_rub,
     is_custom_expense: true,
     type: "custom_expense",
     item_ids
   }
   ```
   Backend сохраняет в **ту же таблицу** `kvota.quote_certificates` с `is_custom_expense=true` и `type='custom_expense'`.
5. Section list rendering (Requirement 6 AC#5) shall различать custom-expense через бейджик «Расход» (gray цвет — design-system token, **НЕ** hex) + `display_name` (реальная колонка `quote_certificates.display_name` per Requirement 1 AC#1) вместо type/number, БЕЗ `valid_until` row.
6. Per-item dialog read-only list (Requirement 9 AC#3) shall рендерить custom-expense как **gray-bordered card** с **«Подробнее»** вместо «Открыть сертификат».
7. Edit-flow для существующего custom-expense shall открывать ту же упрощённую модалку (НЕ Requirement 7) — UI определяет вариант по флагу `is_custom_expense`.
8. Compliance: те же design-system правила что и Requirement 7 (searchable Combobox, shadcn `<Button variant="…">`, Inter font, design tokens, NO `transition: all`, NO `transform: translateY()`).

---

### Requirement 11: TableViewsDropdown — 4 виртуальных системных вида (компонент уже интегрирован)

**Objective:** Как customs-специалист, я хочу быстро переключаться между preset-видами таблицы (все колонки / только тарифы / только сертификаты / минимальный набор), чтобы не скроллить горизонтально и сосредоточиться на нужных данных.

#### Acceptance Criteria

1. Phase B shall **REUSE** существующий компонент `TableViewsDropdown` из `frontend/src/features/table-views/index.ts` — он **уже интегрирован** в `customs-step.tsx:383-397` с props `views`, `activeViewId`, `onViewChange`, `tableKey`, `availableColumns`, `userId`, `orgId`, `canCreateShared`. Phase B **НЕ** добавляет новый component и НЕ меняет интеграцию — Phase B только определяет 4 системных вида и добавляет hint-баннер.
2. Файл `frontend/src/features/quotes/ui/customs-step/customs-views.ts` (новый) shall экспортировать константу `CUSTOMS_SYSTEM_VIEWS: SystemView[]` где `SystemView = {id: string, label: string, visibleColumnIds: string[], is_system: true}`. Все 4 вида — **виртуальные client-side строки** (НЕ записи `user_table_views` таблицы) с синтетическими ID `system:*`. Column ids взяты из существующего `frontend/src/features/quotes/ui/customs-step/customs-columns.ts:CUSTOMS_AVAILABLE_COLUMNS` (24 entry — verified). Конкретные определения видов:
   - **«Все колонки»** (id=`system:all`) — visibleColumnIds: ВСЕ 24 column ids (`position, brand, product_code, product_name, quantity, supplier_country, hs_code, customs_duty_composite, customs_util_fee, customs_excise, customs_antidumping, customs_psm_pts, customs_notification, customs_licenses, customs_eco_fee, customs_honest_mark, import_banned, import_ban_reason, license_ds_required, license_ds_cost, license_ss_required, license_ss_cost, license_sgr_required, license_sgr_cost`).
   - **«Тарифы и НДС»** (id=`system:tariffs-nds`) — visibleColumnIds: `position, product_code, product_name, hs_code, supplier_country, customs_duty_composite, customs_antidumping, customs_excise, customs_util_fee, customs_psm_pts`.
   - **«Документы и сертификаты»** (id=`system:documents`) — visibleColumnIds: `position, product_code, product_name, hs_code, supplier_country, license_ds_required, license_ss_required, license_sgr_required, customs_notification, customs_licenses, customs_eco_fee, customs_honest_mark`.
   - **«Только идентификация»** (id=`system:identification`) — visibleColumnIds: `position, brand, product_code, product_name, quantity, hs_code`.
3. Каждый view = `{id: string, label: string, visibleColumnIds: string[], is_system: true}`. Constants хранятся в `customs-views.ts` (read-only — Phase B не позволяет user-editable views для системных). Customs-step parent component инжектит виртуальные строки в `views` prop `<TableViewsDropdown />` ДО реальных персональных/общих views (которые приходят из `user_table_views` через `fetchAllAvailable`).
4. Toolbar `customs-step.tsx:383-397` (область с `<TableViewsDropdown />`) shall рендерить виртуальные системные виды в отдельной группе «Системные» (выше существующих групп «Личные» / «Общие» в dropdown menu — расширяет grouping в `table-views-dropdown.tsx` lines 124-167).
5. User selection shall **persist через существующий URL parameter `?customs_view=<id>`** (уже wired в `customs-step.tsx:170-194` — без изменений). Для системных видов URL value = `system:tariffs-nds` и т.п.; frontend парсит обратно в виртуальную строку из `CUSTOMS_SYSTEM_VIEWS`. User-defined views (создаваемые через существующий settings dialog) сохраняются в `user_table_views` таблицу как раньше — это **не Phase B scope**. Системные виды НЕ записываются в `user_table_views`.
6. **Migration 307 ОТМЕНЕНА.** Никакой новой DB-схемы для хранения системных видов не создаётся — таблица `kvota.user_table_views` (migration 261) достаточна для user-defined views; системные виды живут только client-side.
7. Where у user отсутствует `?customs_view` URL param, default shall быть **«Все колонки»** (id=`system:all`).
8. Где user меняет вид через dropdown, frontend shall:
   - Update local state мгновенно (handsontable rerenders с filtered columns через существующий `visibleColumns` prop).
   - Update URL param `?customs_view=<id>` через `router.push` (существующая логика).
   - Для системных видов — никаких DB-операций. Для user-defined views — существующий persistence путь через `mutations.ts` (Phase B scope).
9. Where `currentViewId !== 'system:all'` AND `currentViewId.startsWith('system:')` (т.е. активен системный вид, кроме «Все колонки»), `customs-handsontable.tsx` shall рендерить hint-баннер над таблицей (мокап lines 95-98): **«💡 Сейчас активен вид «{view.label}» — скрыты колонки: {hidden_list}.»** где `hidden_list` — comma-separated русские лейблы скрытых колонок (из `CUSTOMS_AVAILABLE_COLUMNS[i].label`). User-defined views (если активны) баннер не показывают (либо могут показывать свою копию — отдельный scope).
10. Hint-banner shall содержать link **«Создать свой вид: Колонки → Сохранить как...»** (мокап line 97) — но в Phase B этот link **disabled / not clickable** с tooltip «Доступно в следующей фазе» (drag-and-drop user-editable views отложены, мокап line 994 confirms).
11. Phase B shall **НЕ** позволять «Сохранить как...» для системных видов (никакого превращения системного в user-defined). User-defined views через TableViewsDropdown settings dialog продолжают работать как раньше (запись в `user_table_views`) — это поведение Phase B не меняет.
12. Tests shall проверять: переключение между 4 системными видами обновляет visible columns, URL param синхронизируется, дефолт `system:all` при отсутствии URL param, hint-баннер появляется на view ≠ `system:all`, виртуальные системные строки **не попадают** в `user_table_views`.

---

## Locked Decisions

| ID | Decision | Rationale |
|---|---|---|
| LD-1 | Cost split — **ВСЕГДА** proportional к стоимости товара (RUB cost basis). NO override, NO custom split, NO equal-split UI option (только fallback при `total_items_value=0`) | Customs-специалист не должен ломать логику «справедливого» распределения; все попытки override создают inconsistency между КП. Equal-split — только safety-fallback. |
| LD-2 | Custom expense использует **ту же** таблицу `kvota.quote_certificates`, отличается флагом `is_custom_expense=TRUE` + `type='custom_expense'` + `display_name` колонкой | Избегаем дублирования таблиц для семантически близких сущностей. M2M-логика, RLS, history — всё переиспользуется. |
| LD-3 | Loose history match — минимум 2 из 3 критериев (`hs_code`, `brand`, `supplier_id`). Cross-quote within organization, 12-month window. Excluded: тот же КП | 2-of-3 даёт sweet-spot между «слишком строго» (все 3 совпадают редко) и «слишком слабо» (только 1 = шум). 12 месяцев — typical срок действия сертификатов. |
| LD-4 | `valid_until` истёк → **EXPLICIT** user prompt («Создать новый» button) — НЕ silent autofill, НЕ auto-apply expired cert | Просроченный сертификат = реальная статья расходов на новый документ. Customs должен принять решение осознанно. |
| LD-5 | **ALL dropdowns** в Phase B UI — searchable Combobox (project-wide standard since 2026-05-01, memory `feedback_searchable_select.md`) | Re-confirmed; никаких exceptions. Аудит на каждое UI-изменение. Реализация — паттерн `country-combobox.tsx` (Popover + Input + filtered list). |
| LD-6 | Cost split helper существует в **ДВУХ синхронизированных** файлах: `services/cost_split.py` + `frontend/src/shared/lib/cost-split.ts` с shared JSON fixtures и parity-тестами. TS-сторона использует explicit half-up shim (`Math.floor(value * 100 + 0.5) / 100`), НЕ `Math.round` | Backend (API attribution) и frontend (live preview) обязаны выдавать идентичные числа копейка-в-копейку; parity tests предотвращают drift при future изменениях. JS Math.round — banker's-style на половинах, несовместимо с Python ROUND_HALF_UP. |
| LD-7 | TableViewsDropdown — **REUSE** существующий компонент `frontend/src/features/table-views/`. **УЖЕ ИНТЕГРИРОВАН** в `customs-step.tsx:383-397`. Phase B = определить 4 системных вида как **виртуальные client-side строки** с синтетическими ID `system:*`. User-editable views (записи в `user_table_views`) — Phase C | Component уже существует и интегрирован; build new = waste. Виртуальные системные виды избегают per-org seed loop и дают immutability by construction. User-editable views требуют отдельный UX scope (validation, sharing, права) — Phase C. |
| LD-8 | Запрещено модифицировать calc-engine: `calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py`. Phase B практически не задействует calc-engine — cost split отдельный helper, RUB cost basis из `services/calculation_helpers.py` (НЕ часть calc-engine модулей) | Phase B — UI/API only. Calc-engine integration понадобится только если landed-cost обновится (потенциально Phase C). |
| LD-9 | Schema `kvota` (НЕ `public`). Role column `r.slug` (НЕ `r.code`) во всех RLS policies. RLS-паттерн миграции 293 (multi-table JOIN), НЕ 304 (JWT-claim) | Project-wide convention; нарушения ловятся в production. 293-паттерн обязателен для primary entities с role-based mutation rights; 304-паттерн только для write-only audit logs. |
| LD-10 | Existing `/api/customs/resolve-rates` API response shape **unchanged** — Phase B добавляет НОВЫЕ endpoints без breaking changes | Phase A clients не должны ломаться. API evolution: только additive changes. |
| LD-11 | Date format **DD.MM.YYYY** через **существующий** `formatDateRussian` helper из `frontend/src/features/customs-history/lib/format-date.ts` (Phase A) — REUSE, не реимплементировать | Single source of truth для российского формата дат; Phase A уже покрыл тесты. |
| LD-12 | **Одна** новая миграция: **306** (`quote_certificates` + `quote_certificate_items` schemas + ATOMIC data backfill from `customs_*_expenses`). Drop migration для `customs_*_expenses` таблиц — **ОТЛОЖЕНА** на отдельный последующий релиз после production-верификации Phase B. Migration 307 **ОТМЕНЕНА** — `user_table_views` (миграция 261) покрывает persistence; системные виды живут client-side | Sequential numbering (после Phase A 304/305). Idempotent (CREATE IF NOT EXISTS). Atomic backfill — паттерн `feedback_oneshot_migrations_when_engine_locked.md`: surface area small, ships atomically with code (REQ-6 AC#9 удаляет UI в том же PR). Drop отложен для safety — данные сохраняются в исходных таблицах временно. |
| LD-13 | Design-system compliance — read `design-system.md` (Slate & Copper tokens) перед любой UI-работой. Use shadcn `<Button variant="…">` from `@/components/ui/button`. Inter font. Constrained scales (font 11/12/14/16/18/20/24px, space 4/6/8/12/16/20/24/32/48px). NO `transition: all`. NO `transform: translateY()` on hover. NO inline `style=` для colors/fonts/spacing — use Tailwind classes mapped to tokens (`bg-accent`, `text-text-muted`, `border-border-light`, etc.) | Project-wide convention; нарушения видны на review. `.btn` BEM классы в codebase отсутствуют (verified: 0 matches) — проект использует shadcn Button. |
| LD-14 | RLS by `r.slug` для новых таблиц: WRITE (`customs/admin/head_of_customs`), READ (`+ sales/quote_controller/spec_controller/finance/top_manager`) | Стандартная many-tenant защита; sales должен видеть сертификаты но не редактировать (роль customs). Реализация через существующую константу `_CUSTOMS_ROLES` в `api/customs.py:36`. |
| LD-15 | **Cost-split input = derived RUB cost basis** computed via Python helper `services/calculation_helpers.py:_customs_value_in_rub()` (calc-engine source-of-truth — формула `purchase_price_original × quantity × convert_amount(src→RUB)`). Frontend computes the same value from `purchase_price_original × quantity × currency_rate_to_rub` (формула, derived from helper). **NEVER read a literal `quote_items.cost_rub` column — it does not exist.** Колонка `customs_value_rub` существует только на `customs_declaration_items` / `customs_declarations` (отдельная сущность ДТ, миграция 191) — это **НЕ** источник для cost split | Колонка `customs_value_rub` на `quote_items` отсутствует (refuted by code-validation 2026-05-04). Cost basis — производное Decimal-значение, вычисляемое helper-ом. Frontend не делает новых fetch-ов — `currency_rate_to_rub` уже доступен в state модалок/popover-ов. Backend resolves invoice_items payload server-side; frontend оперирует на pre-resolved RUB values. |
| LD-16 | Системные виды (`Все колонки`, `Тарифы и НДС`, `Документы и сертификаты`, `Только идентификация`) — **ВИРТУАЛЬНЫЕ client-side строки** с синтетическими ID `system:*` — они живут в `customs-views.ts` constants, **НЕ** в `user_table_views` таблице. URL persistence через существующий `?customs_view=<id>` параметр работает as-is (синтетические ID просто строки). User-defined views (Phase C scope) используют `user_table_views` строки как обычно | Avoid per-org seed loop, immutability by construction, no schema change. `user_table_views` (миграция 261) не имеет `is_system` концепции — синтетика на уровне frontend проще и чище. |

---

## Out of Scope (Phase C / отложено)

- Расширенные нетарифные требования (санитарный / ветеринарный / фитосанитарный контроль, IP / параллельный импорт) — Phase C
- Тип сертификата происхождения как **enum** (CT-1 / CT-2 / CT-3 / EUR.1 / Form A / A.TR) — Phase C; в Phase B `type` свободный TEXT с seeded options
- «Честный знак» selectbox групп товаров — Phase C
- ОТТС / ОТТС МУ (для авто) — Phase C
- User-editable / shared / personal views в TableViewsDropdown (записи в `user_table_views`) — отложено на Phase C; Phase B = только 4 виртуальных системных вида
- Drag-and-drop reordering колонок в customs-handsontable — отложено
- Mobile UI для секции «Расходы по таможне» — Phase B desktop-only
- Россельхознадзор, Минкульт, военка — Phase D
- Cert-attachment audit-log таблица (history of attach/detach actions) — отложено; Phase B — minimum viable
- **Drop migration для `customs_item_expenses` + `customs_quote_expenses` таблиц** — отложено до production-верификации Phase B; backfill в migration 306 non-destructive (исходные данные сохраняются в старых таблицах кратковременно для safety)

---

## Acceptance Gates

После реализации Phase B:

- [ ] **Migration 306** (atomic schema + backfill) создаёт `quote_certificates` + `quote_certificate_items` с RLS (293-паттерн), индексами, CHECK, и **АТОМАРНО** backfill-ит данные из `customs_quote_expenses` + `customs_item_expenses` (Req 1)
- [ ] **API** — POST/GET/DELETE/history endpoints работают через dual auth, role-gate enforced через существующую `_CUSTOMS_ROLES` константу (Req 2)
- [ ] **Старые `customs_*_expenses` CRUD endpoints удалены** из `api/customs.py` в том же PR (Req 2 AC#16)
- [ ] **Cost split helper** реализован в Python + TypeScript с parity-тестами на shared JSON fixtures, использующих derived RUB cost basis (НЕ литеральное чтение колонок) (Req 3)
- [ ] **Expired cert UI** — красная рамка через design-system токен + блокировка привязки + копия «Прежний сертификат истёк..., нужен новый» (Req 4)
- [ ] **History autofill** — endpoint `GET /certificates/history` возвращает loose-match за 12 месяцев в той же организации, frontend рендерит баннер «Применить» / «Создать новый» (Req 5)
- [ ] **Unified UI section** «Расходы по таможне» с двумя кнопками заменяет `<QuoteCustomsExpenses />` + `<ItemCustomsExpenses />` (Req 6); `<CustomsExpenses />` calc-engine форма остаётся untouched
- [ ] **UI секции `<QuoteCustomsExpenses />` и `<ItemCustomsExpenses />` удалены** из `customs-step.tsx` (Req 6 AC#9); backfill-миграция верифицирована non-destructive (исходные данные сохранены до отдельного drop-релиза)
- [ ] **Modal** «+ Добавить сертификат» с multi-select + live-preview работает; все displayed RUB-суммы — derived (Req 7)
- [ ] **Popover** «Привязать к существующему» из per-item dialog с radio-list + after-attach preview (derived RUB-суммы) (Req 8)
- [ ] **Per-item read-only** список emerald-cards (cert) / gray-cards (расход) с share rub + role-gated «Отвязать» (Req 9)
- [ ] **«Свой расход»** — упрощённая модалка использует ту же таблицу с `is_custom_expense=true` + `display_name` колонкой (Req 10)
- [ ] **TableViewsDropdown** — 4 виртуальных системных вида с `system:*` ID, hint-баннер на view ≠ `system:all`, компонент НЕ переинтегрируется (уже в `customs-step.tsx:383-397`) (Req 11)
- [ ] **`npm run db:types`** обновил `database.types.ts`, tsc green
- [ ] **Tests** — unit (cost-split parity, history match, RLS), integration (API endpoints), UI (modal/popover flows, virtual system views toggle)
- [ ] **Browser test** через localhost:3000 + prod Supabase verifies end-to-end на app.kvotaflow.ru post-deploy
- [ ] **Все displayed RUB-суммы** в UI Phase B (multi-select position list, live-preview, after-attach preview, read-only sub rows) — **derived** через формулу `purchase_price_original × quantity × currency_rate_to_rub` (helper Requirement 3 AC#4), НЕ литеральное чтение `cost_rub` колонки

---

## Next Phase

После approval этих requirements:

```bash
/kiro:validate-gap customs-shared-certificates    # gap-analysis vs existing codebase
/kiro:spec-design customs-shared-certificates     # technical design (требует approval)
/kiro:spec-tasks customs-shared-certificates      # task breakdown (auto-approve)
/lean-tdd skip-to-impl .kiro/specs/customs-shared-certificates/
```

Approval — мандатная фаза перед design. Если есть corrections — отвечайте на этот документ, я обновлю и перегенерирую.
