# Анализ разрывов реализации — `control-spec-workspace`

## 1. Резюме

- **Объём — средний-крупный.** 12 требований распадаются на 5 рабочих областей: экран спец-контроля (4 блока), workflow «Отправить на подписание», фаза «На подписании» + структурная сверка, аддитивная миграция (FK на `seller_companies`/`locations` + `signing_fx_mode`/`signing_fx_rate`), второй workspace `/workspace/control` с двумя канбанами + сайдбар, и ролевое разграничение (tier-based). Бэкенд (Python модель + PDF/DOCX экспорт + `/api/deals` + workflow-переходы) уже почти всё умеет — основной труд во фронтенде.
- **Главные выигрыши переиспользования:** `SearchableCombobox` (стандарт проекта, 5+ потребителей) для всех дропдаунов реквизитов; движок канбана `KanbanBoard`/`KanbanColumn` (dnd-kit, оптимистичный move+rollback); готовый workflow-переход `pending_spec_control → pending_signature` в `workflow_service.py:541-546`; полностью готовая цепочка `confirmSignatureAndCreateDeal → POST /api/deals` (spec→signed, 7 логистических этапов, инвойсы); готовый паттерн checklist `useControlChecks`/`VerificationStrip` для структурной сверки; помощники-ролей в `shared/lib/roles.ts`, где контролёры уже перечислены во всех нужных массивах.
- **Главные разрывы (что строим):** ~24 «мёртвых» колонки спецификации, которые есть в БД и Python-модели, но Next.js их не пишет/не читает; блок «Из расчёта» (read-only) полностью отсутствует на экране; кнопка «Отправить на подписание» не подключена ни к одному UI-контролу; нет страницы `/workspace/control` с двумя канбанами + control-карточек + фетчеров под quotes/specs; нет хелперов `isSpecController`/`isQuoteController`/`canEditSpecControl`; нет fail-closed гарда на workspace-страницах; нужна аддитивная миграция (`signing_fx_mode`, `signing_fx_rate` + FK-колонки под реквизиты).
- **Главные риски:** **две параллельные машины состояний** — `quotes.workflow_status` (через `workflow_service`) и `specifications.status` (draft/approved/signed). Сейчас UI ведёт `specifications.status` и `create_deal` ставит `quotes.workflow_status='deal'` напрямую, минуя `pending_signature` — то есть `pending_signature` фактически мёртв в проде. Это центральное проектное решение для `/kiro:spec-design`.
- **Риск номеров миграций:** `CLAUDE.md` говорит «Latest migration: 283», но в `migrations/` уже есть 318 и 319. Истинный следующий номер подтвердить на VPS (`kvota.schema_migrations`) ДО написания ALTER.
- **Риск устаревшей документации:** `database.md:114` рекомендует `total_amount_quote` «для отображения» — колонка **удалена** в m318/m319. Канонический столбец суммы для блока «Из расчёта» — `total_quote_currency`. Не следовать таблице.

---

## 2. Что уже есть (переиспользуем)

### Экран спецификации + схема
| Возможность | Где (evidence) |
|---|---|
| 3-шаговый поток: export PDF/DOCX → upload скана → create deal | `specification-step.tsx:614-699`; `mutations.ts:74-100` POST `/deals` |
| Полный набор колонок `specifications` (~30), включая все «реквизитные»: `validity_period`, `exchange_rate_to_ruble`, `client_payment_terms`, `cargo_pickup_country`, `goods_shipment_country`, `delivery_city_russia`, `our_legal_entity`, `client_legal_entity`, `supplier_payment_country`, `created_by` | `migrations/006:19-62`, 036/126/145/148/149/160 |
| Python-модель round-trip-ит почти все «мёртвые» колонки (экспорт + `specification_service`) — колонки write-gapped в Next.js, не orphaned | `services/specification_service.py:36-137`; `contract_spec_export.py:412-431`; `contract_spec_docx.py:214-231` |
| Канонический столбец суммы quote = `total_quote_currency` + `total_profit_usd`; курс `quotes.exchange_rate_to_usd` DECIMAL(12,6) | `entities/quote/queries.ts:37,377-379`; `migrations/012` |
| Запрос spec уже фильтрует soft-delete (`deleted_at`) | `specification-step.tsx:107` |

### Реестры + searchable-select
| Возможность | Где (evidence) |
|---|---|
| `seller_companies` org-scoped fetch + полная схема реквизитов (inn/kpp/ogrn/bank/...) | `features/companies/api/server-queries.ts:4-18`; `database.types.ts:4983-5013` |
| `locations` org-scoped fetch + type-filtered вариант; `country` — plain text (НЕ FK) | `entities/location/queries.ts:46-89`; `database.types.ts:1995-2027` |
| `SearchableCombobox` — канонический generic picker (стандарт проекта); чистые `filterItems`/`computeNextFocusedIndex` для тестов | `shared/ui/searchable-combobox.tsx:140-395`; экспорт из `index.ts:4-9` |
| `customer_contracts` read/create/update/delete + inline-создание в spec-step | `entities/customer/queries.ts:372-383`; `specification-step/mutations.ts:102-124`; `specification-step.tsx:287-316` |
| `get_next_specification_number` RPC (атомарный счётчик per-contract) | `migrations/022:91-104` |

### Канбан + сайдбар
| Возможность | Где (evidence) |
|---|---|
| Generic 3-колоночный канбан с dnd-kit (drag/drop, оптимистичный move+rollback, DragOverlay) | `workspace-kanban/ui/kanban-board.tsx:64-346` |
| Серверный паттерн страницы: `getSessionUser` → orgId redirect → isHead → `Promise.all` → render `KanbanPage` | `app/(app)/workspace/logistics/page.tsx:22-67` (и customs — почти идентично) |
| Workflow-статусы контроля уже смоделированы: `pending_quote_control`/`pending_spec_control`/`pending_signature` с RU-метками | `shared/lib/workflow-statuses.ts:27-35`; `entities/quote/status-labels.ts:23-24` |
| Control-колонки в quotes: `quote_controller_id`, `spec_controller_id`, `*_control_completed_at` | `database.types.ts:4556-4559` |
| Builder сайдбара с `hasRole`-гейтингом; существующие «Очередь логистики/таможни» | `widgets/sidebar/sidebar-menu.ts:137-164` |
| Filtered-queue прецедент (single `workflow_status` → list) | `app/(app)/approvals/page.tsx:26-40` |

### Workflow + deal + docs
| Возможность | Где (evidence) |
|---|---|
| Generic переход POST `/api/quotes/{id}/workflow/transition` (dual JWT/session, role-check в `workflow_service`) | `api/quotes.py:895-987` |
| Переход `pending_spec_control → pending_signature` (roles spec_controller/admin) | `workflow_service.py:541-546` |
| Переход `pending_signature → deal` (spec_controller/sales/head_of_sales/admin) | `workflow_service.py:561-578` |
| Frontend caller `callWorkflowTransition()` | `entities/quote/mutations.ts:19-44` |
| `create_deal`: spec→signed, deal insert, quote→'deal', 7 логистических этапов, инвойсы | `api/deals.py:89-292` |
| Скан хранится в `kvota-documents`, пишет `signed_scan_url`+status='approved', строка в `documents` | `specification-step.tsx:211-258`; `migrations/143/144/151` |
| Прецедент сверки: `useControlChecks` → `CheckResult[]` (ok/warning/error/info) + `VerificationStrip` | `control-step/use-control-checks.ts:117-324`; `verification-strip.tsx:41-97` |

### RLS + роли
| Возможность | Где (evidence) |
|---|---|
| Role-tier хелперы (единый источник) | `shared/lib/roles.ts:36,48,125,137,157` |
| `quote_controller`/`spec_controller` уже в `BROAD_QUOTE_ACCESS_ROLES`, `QUOTE_FINANCIALS_ROLES`, `COMPOSITION_EDIT_ROLES` | `roles.ts:105-116,204-213,174-185` |
| `canAccessQuote`: контролёры → full org visibility (`return true`) | `entities/quote/queries.ts:908,961` |
| `ROLE_ALLOWED_STEPS` для контролёров определены (spec_controller → [specification, control, ...]) | `entities/quote/types.ts` |
| `specifications` RLS — org-level (роли делегированы app-слою «by design») | `migrations/006:103-160` |

---

## 3. Чего не хватает (строим)

**Req 1 — экран спец-контроля, 4 блока:**
- **Блок «Из расчёта» (read-only)** — `specification-step.tsx` сейчас читает только item count, ни одной суммы quote. Строим блок из уже переданного prop `quote: QuoteDetailRow`: `total_quote_currency`, `total_with_vat_quote`, `total_profit_usd`, `currency`, `exchange_rate_to_usd`. (Markup — item-level, не quote-level; см. флаги.)
- **Блок реквизитов (searchable dropdowns)** — нет UI write/read path для ~24 существующих колонок (`our_legal_entity`, `client_legal_entity`, `client_payment_terms`, `cargo_pickup_country`, `goods_shipment_country`, `delivery_city_russia`, `supplier_payment_country`, `validity_period`, `specification_currency` и т.д.). Колонки и Python-сериализация есть — нет только Next.js слоя.
- **Блок условий спецификации** — те же «мёртвые» колонки + контракт-дропдаун (сейчас plain shadcn `<Select>` на `:422-441` — нарушает стандарт «все дропдауны searchable»).
- **Control-stamp + signing FX** — колонки `signing_fx_mode` / `signing_fx_rate` **отсутствуют** (0 совпадений в `.sql/.py/.ts/.tsx`). Новая миграция.

**Req 2 — реквизиты (источники данных):**
- Нет async/load-on-search picker — `SearchableCombobox` чисто клиентский (фильтрует pre-loaded `items`, не фетчит). Под реквизиты родитель должен pre-load-ить `seller_companies`/`locations`/`contracts` server-side.
- `seller_companies`/`buyer_companies` живут только в `features/companies/`, не в `entities/`. Для cross-feature использования — promote в `entities/seller-company`.
- **Нет таблицы `customer_legal_entities`.** Юрлицо клиента сейчас = денормализованные реквизиты на `customers` + free-text snapshot `specifications.client_legal_entity`. Multi-entity дропдаун потребовал бы новой таблицы (см. флаги).

**Req 9/10/11 — workspace `/workspace/control`:**
- Нет страницы, хостящей ДВА канбана (прецедента «два board на одном route» нет).
- Нет control-словаря колонок «На контроле»/«На подписании» (`KANBAN_COLUMNS` — hard-coded const, не prop).
- Нет card-типа под quotes/specs (`WorkspaceKanbanCard` invoice-shaped) и рендерера.
- Нет фетчера control-board (`fetchKanbanInvoices` читает `invoices`; нужен quotes-by-workflow_status).
- Нет sidebar-секции «Контроль» → `/workspace/control`.

**Req 5 — «Отправить на подписание»:**
- Переход есть в `workflow_service`, но **не подключён** к UI. `specification-step.tsx` ведёт `specifications.status`, не вызывает `callWorkflowTransition`. Ни одна кнопка не постит `to_status='pending_signature'`.

**Req 6 — структурная сверка скан↔система:**
- Нет spec-level reconciliation UI. Единственная scan-vs-data проверка — invoice-scan coverage в `useControlChecks` (control-step), по `invoice_id`. Сверки подписанной спеки (sign_date / signatory / contract / total против системы) нет.

**Req 11 — роли:**
- Нет хелперов `isSpecController`/`isQuoteController` + `canSeeControlBoard` selector.
- Нет `canEditSpecControl` (top_manager read-only): сейчас `ROLE_EDITABLE_STEPS` оверрайдит только `procurement_senior`, поэтому контролёры/top_manager получают editableSteps=allowedSteps (т.е. EDIT, не read-only).
- Нет fail-closed гарда на `/workspace/*` (сейчас fail-OPEN: пустой board + скрытие в nav).

---

## 4. Точки интеграции

**Spec-экран (Req 1, 2):**
- `specification-step.tsx:158-166` (handleCreate insertData) и `:191-197` (handleSave update) — расширить payload новыми + «мёртвыми» колонками; добавить `created_by` (сейчас опущен).
- Widen SELECT в **обоих** дублированных call-site: `specification-step.tsx:104-105` и `queries.ts:41` + тип `SpecificationRow` (`queries.ts:3-15`) — держать в синхроне.
- Блок «Из расчёта»: prop `quote: QuoteDetailRow` уже передан (`specification-step.tsx:44`); читать суммы с него или расширить entity-select, если не хватает `total_with_vat_quote`/`exchange_rate_to_usd`.
- `loadData()` (`specification-step.tsx:98-147`) — естественный дом для pre-load `seller_companies` + `locations` (или hoist в server `queries.ts`, где уже есть `fetchCustomerContracts`/`fetchCustomerContacts`).
- Заменить plain `<Select>` контракта (`specification-step.tsx:422-441`) на `SearchableCombobox` (контракты уже в state на `:130`).

**Workflow (Req 5, 7):**
- Кнопка «Отправить на подписание»: `callWorkflowTransition(quoteId, {to_status:'pending_signature'})` → `entities/quote/mutations.ts:19-44` → `api/quotes.py:895` → `workflow_service.py:541-546`. Backend-изменений не нужно, только UI-контрол.
- Deal-handoff: либо роутить `quote→'deal'` через `workflow_service.transition_quote_status` (enforce `pending_signature→deal` + audit + roles) вместо прямой записи `api/deals.py:251`, либо оставить прямую запись и логировать.

**Сверка (Req 6):**
- Клонировать shape `useControlChecks` → `CheckResult[]`, рендерить через `VerificationStrip`. Загрузка скан-документа через `Map<…, DocumentRow>` (`use-control-data.ts:104-120`). Источник скана — `specifications.signed_scan_url` + строка `documents` (`entity_type='specification'`, `document_type='specification_signed_scan'`).

**Канбан + сайдбар (Req 9–11):**
- Новый route `app/(app)/workspace/control/page.tsx` — зеркало `workspace/logistics/page.tsx:22-67`.
- Параметризовать `KANBAN_COLUMNS` (сейчас module const в `kanban-board.tsx:21-22,227` + `model/types.ts:23-34`) → в prop/column-config. **Blast radius:** const используется в `kanban-page` (normalizeBoard), `kanban-board` (KanbanColumn map, findColumn) и тестах — проверить отсутствие регрессии для logistics/customs.
- Control card type + fetcher в `entities` слое (новый `entities/workspace-control` или extend `workspace-invoice`).
- Линк карточки: `/quotes/{id}?step=specification` (или `?step=control`) — `default-step.ts:18-19,41` уже маппит `pending_*_control → control`.
- Sidebar: push секции/item гейтнутый `hasRole('quote_controller','spec_controller','top_manager')` + isAdmin bypass — shape как Truck/Anchor entries (`sidebar-menu.ts:137-164,173`).

**Роли (Req 11):**
- Хелперы `isSpecController`/`isQuoteController`/`canEditSpecControl`/`canSeeControlBoard` — в `shared/lib/roles.ts` рядом с `isCustomsOnly`/`canEditComposition`.
- Read-only enforcement: `quotes/[id]/page.tsx:129-132` (editableSteps/isReadOnly) + extend `ROLE_EDITABLE_STEPS`.
- Field-write гейт spec-control — в Python API (api-first + `access-control.md:148`), НЕ в RLS. `specifications` RLS остаётся org-level.

**Миграция-гейт:**
- После ALTER `kvota.specifications` → `cd frontend && npm run db:types` ДО ссылок на новые колонки (`database.md:96`).
- Любой information_schema guard ОБЯЗАН фильтровать `table_schema='kvota'` (m036 создал колонки в `public`, фикс m160).

---

## 5. Опции реализации

**Поверхность «мёртвых» колонок спеки (реквизиты, юрлица, валюта, payment terms) — EXTEND.**
Колонки + Python-сериализация (`specification_service.py:36-137`) уже есть; не хватает только Next.js write/read. Widen SELECT (оба call-site + `SpecificationRow`) и insert/update в `specification-step.tsx`. Без schema-работы. Следить за дублированием `readiness_period` vs `delivery_days`/`delivery_days_type`.

**Signing FX mode/rate (Req 4.5/control-stamp) — NEW.**
Добавить `signing_fx_mode VARCHAR` с extensible CHECK (`cbr_on_payment_day` | `fixed`) + `signing_fx_rate DECIMAL(15,6)` (precision как `exchange_rate_to_ruble`). **Рекомендация:** выделенная пара лучше, чем перегрузка `specification_currency`+`exchange_rate_to_ruble`, которые несут display-семантику, а не lock-at-signing.

**Блок «Из расчёта» — EXTEND.**
Читать из уже переданного prop `quote`. Канон: `total_quote_currency`, `total_with_vat_quote`, `total_profit_usd`, `currency`, `exchange_rate_to_usd`. **НЕ использовать** `total_amount_quote` — удалён в m318/m319. Расширить `QuoteDetailRow` select, если не хватает `total_with_vat_quote`/`exchange_rate_to_usd`.

**Seller-company дропдаун — HYBRID.**
Reuse `fetchSellerCompanies` + `SearchableCombobox<SellerCompany>` (`getLabel=name`, `getSecondary=supplier_code`, `getSearchableExtras=[inn,kpp,country]`). NEW: опционально promote `SellerCompany` type/fetch из `features/companies` в `entities/seller-company`, чтобы spec-step не cross-import-ил соседнюю feature. Без DB-изменений.

**Страна реквизита — решено использовать locations registry (NEW/HYBRID).**
`fetchLocations` возвращает `country` текстом. Варианты: (a) reuse `CountryCombobox` (статичный ISO) для чистого country-value; (b) derive distinct countries через `fetchLocationCountries`; (c) выбор полной location-строки через `SearchableCombobox` + `formatLocationLabel` (как `add-segment-dialog`). **Рекомендация:** уточнить семантику в дизайне (см. флаги) — нормализованный ISO vs free-text country.

**Юрлицо клиента — EXTEND (если одно) / NEW (если множество).**
Сейчас данные модели поддерживают только один набор реквизитов на `customers` + free-text snapshot. Если одно юрлицо — рендерить реквизиты read-only. True multi-entity searchable дропдаун требует НОВОЙ таблицы `customer_legal_entities` (миграция) — сейчас отсутствует.

**Контракт-дропдаун + нумерация — EXTEND.**
Swap plain `<Select>` → `SearchableCombobox`. Опционально подключить неиспользуемый `get_next_specification_number` RPC взамен ad-hoc `SP-${idn_quote}` (`specification-step.tsx:156`) — меняет формат spec-номера и требует выбранного контракта.

**Канбан-страница (два board) — NEW.**
`app/(app)/workspace/control/page.tsx` фетчит два board (calc-control quotes + spec-control specs) и рендерит две секции `KanbanBoard` stacked. Server-skeleton переиспользуется verbatim; новые только фетчеры и второй board.

**Board/колонки — HYBRID.**
Reuse `KanbanBoard`/`KanbanColumn` rendering+dnd, но lift hard-coded `KANBAN_COLUMNS`/labels в column-config prop, чтобы передать control-config (`на_контроле`/`на_подписании`). Альтернатива (fork `ControlKanbanBoard`) отвергнута — дублирует dnd-логику, нарушает DRY.

**Card shape — HYBRID.**
Ввести `ControlKanbanCard` type (`idn_quote`, customer, total, controller, workflow_status) + `ControlCard` renderer; шарить `cardKey`/draggable wiring. Не полировать invoice-card опциональными control-полями.

**Drag vs read-only — HYBRID (решить в дизайне).**
Если интерактивно — `resolveControlDragAction` + server action штампующий `quote_controller_id`/`spec_controller_id` (reuse `approveQuote`-style `mutations.ts:1828`). Если статус-очереди — read-only карточки с линком на control-step. **Рекомендация:** read-only очереди проще и соответствуют реальной поверхности действий контролёра (действие — на control-step странице).

**Workflow «Отправить на подписание» — EXTEND.**
Подключить существующий переход к кнопке через `callWorkflowTransition`. Backend-изменений нет. Решить: spec UI гейтит на `quotes.workflow_status` (workflow-истина) vs `specifications.status` (текущая истина).

**Deal-handoff — HYBRID.**
Оставить POST `/api/deals` как side-effect orchestrator, но роутить `quote→'deal'` через `workflow_service.transition_quote_status` (enforce + audit + roles) вместо прямой записи `deals.py:251`. Опционально обернуть multi-table writes в транзакцию (фикс partial-failure gap).

**Структурная сверка (Req 6) — EXTEND.**
Клонировать shape `useControlChecks` (`CheckResult[]`), рендерить через `VerificationStrip`. Проверки: scan существует + `sign_date`/signatory/contract/total против quote/spec-системы. Reuse documents-Map из `use-control-data`.

**Control-роли (Req 11.1/11.5) — NEW.**
`isQuoteController`/`isSpecController` + `canSeeControlBoard` selector в `roles.ts`. admin/top_manager → оба board; quote_controller → calc; spec_controller → spec. Fail-closed: unknown role → no board.

**Spec-control edit-gate (Req 11.2/11.3) — HYBRID.**
`canEditSpecControl(roles)=spec_controller||admin` в `roles.ts` И extend `ROLE_EDITABLE_STEPS` (`top_manager: []` для read-only + restricted записи контролёров), чтобы существующая `isReadOnly`-машинерия (`quotes/[id]/page.tsx:129-132`) работала без второго источника истины.

**Workspace page guard (Req 11.1/11.5) — EXTEND.**
Клонировать `workspace/logistics/page.tsx` (orgId redirect + role allow-list). **Дивергенция:** logistics/customs fail-OPEN (пустой board); `access-control.md` требует fail-closed — решить, должен ли control-index redirect/notFound для неавторизованных (см. флаги).

**DB/RLS для spec-control полей — EXTEND (без миграции под RLS).**
`specifications` RLS остаётся org-level (m006); field-scope enforce в Python API per api-first. Req 11 не вводит новой модели данных.

---

## 6. Данные / миграция

Одна **аддитивная** миграция к `kvota.specifications` (schema-additive, применить на VPS **до** мержа PR, который ссылается на новые колонки — паттерн из `reference_expand_contract_migration_workflow.md`).

**Перед написанием:** подтвердить истинный следующий номер на VPS (`kvota.schema_migrations` / `apply-migrations.sh`) — `CLAUDE.md` (283) расходится с `migrations/` (318, 319).

```sql
-- migrations/<NEXT>_control_spec_workspace_signing_fx_and_requisite_fks.sql
BEGIN;

ALTER TABLE kvota.specifications
  -- Signing FX lock (Req 4.5 / control-stamp)
  ADD COLUMN IF NOT EXISTS signing_fx_mode VARCHAR(32)
    CHECK (signing_fx_mode IS NULL OR signing_fx_mode IN ('cbr_on_payment_day','fixed')),
  ADD COLUMN IF NOT EXISTS signing_fx_rate DECIMAL(15,6);  -- precision как exchange_rate_to_ruble

-- ОПЦИОНАЛЬНО (если дизайн решит FK вместо free-text snapshot):
--   seller_company_id UUID REFERENCES kvota.seller_companies(id) ON DELETE SET NULL
--   pickup_location_id / shipment_location_id UUID REFERENCES kvota.locations(id) ON DELETE SET NULL
-- ВНИМАНИЕ: эти колонки могут питать calc-engine — проверить constraint "не менять calc-engine".

COMMIT;
```

**Точность:** `signing_fx_rate DECIMAL(15,6)` (как `exchange_rate_to_ruble`). Сравнение precision в проекте: spec rate DECIMAL(15,6); quote rate DECIMAL(12,6); ERPS percent DECIMAL(5,2).

**Backfill:** не требуется — обе колонки nullable, существующие спеки остаются с NULL (режим/курс задаётся при штампе контроля). При желании дефолта — `signing_fx_mode` оставить NULL до явного выбора контролёром (fail-loud вместо тихого дефолта).

**FK-решение (Req 8) — нужно подтвердить в дизайне:** persist выбранного `seller_company`/`location` как FK id ИЛИ как существующий free-text snapshot (`our_legal_entity`/`client_legal_entity` — VARCHAR). Текущие колонки — VARCHAR-снимки. Добавление FK-колонок требует миграции и **может конфликтовать с calc-engine «do not modify»**, если эти колонки питают расчёт — проверить `build_calculation_inputs()`.

**После применения:** `cd frontend && npm run db:types`, `tsc` green, прогнать `tools/check_select_columns.py` (merge-gate) до ссылок на новые колонки. Reset `/root/onestack` обратно на main после применения с feature-ветки (иначе `git pull` aborts на divergent branches).

---

## 7. Риски и флаги для дизайна

Разрешить в `/kiro:spec-design`:

1. **Две машины состояний (центральный риск).** `quotes.workflow_status` (`pending_spec_control`→`pending_signature`→`deal` via `workflow_service`) vs `specifications.status` (draft/approved/signed). Сейчас `create_deal` (`deals.py:249-254`) ставит `workflow_status='deal'` напрямую, минуя `pending_signature` — переход фактически мёртв в проде (нет audit-log, нет role enforcement из матрицы). **Решить:** реактивировать `pending_signature` (через `callWorkflowTransition` на «Отправить на подписание» + `transition_quote_status` в deal-handoff) или формально его ретайрить. Гейтит ли spec UI на `workflow_status` или `specifications.status`? **Не плодить третий writer.**
2. **`spec_signed` vs `'deal'`.** Rail/header ссылаются на `spec_signed` (`quote-status-rail.tsx:74`), но `deals.py` флипает в `'deal'`, а `quotes.py:813` трактует оба как non-cancellable. Подтвердить, живой ли `spec_signed` workflow_status или legacy.
3. **«На подписании» column data semantics.** `pending_signature` есть в labels, но ни один query/mutation его не драйвит на spec-board. Подтвердить маппинг колонки «На подписании» → `pending_signature` и transition `pending_spec_control → pending_signature`.
4. **Card source для spec-board.** Control-карточки — это `quotes` rows для обоих board, или genuinely `specifications` rows для spec-board? `specifications` — отдельная таблица (FK `quote_id`) со своим `status`. Подтвердить: spec-cards читают `specifications.status` или `quotes.workflow_status='pending_spec_control'`.
5. **Drag vs read-only канбаны.** Определяет, нужен ли новый server action + `resolveControlDragAction` или просто кликабельные карточки на control-step.
6. **Read-only для top_manager / non-domain контролёров.** Сейчас `ROLE_EDITABLE_STEPS` оверрайдит только `procurement_senior` → top_manager получает EDIT. Выбрать ОДИН механизм: (a) extend `ROLE_EDITABLE_STEPS` (`top_manager:[]` + restricted controllers) или (b) дискретный `canEditSpecControl` гейт в spec-компоненте. Не плодить второй источник истины.
7. **Один vs два control-route.** Req 11.1 подразумевает два канбана. Это два route (`/workspace/control-calc` + `/workspace/control-spec`, зеркало logistics/customs) или табы на одной `/workspace/control`? Влияет на число page-guard + nav-entry.
8. **Fail-closed на workspace-index.** Logistics/customs fail-OPEN (пустой board, скрытие nav). `access-control.md` требует fail-closed (Req 11.5). Решить: redirect/notFound для неавторизованных vs пустой board — это сознательная дивергенция от прецедента.
9. **Юрлицо клиента — selectable список или один набор?** Сегодня модель поддерживает один набор реквизитов на `customers` + free-text snapshot. Multi-entity дропдаун → новая таблица `customer_legal_entities` + миграция.
10. **Семантика «страна» реквизита** — full location row / просто country string / static `CountryCombobox` ISO? `locations.country` — free text, выбор location даёт текстовый country, не нормализованный ISO.
11. **Persist реквизитов как FK id или free-text snapshot?** Текущие `our_legal_entity`/`client_legal_entity` — VARCHAR. FK-колонки требуют миграции и могут конфликтовать с calc-engine constraint.
12. **`get_next_specification_number` RPC** определён, но не вызывается из frontend (нумерация = `SP-${idn_quote}`). Подтвердить, переключаемся ли на contract-counter (меняет формат spec-номера, требует выбранного контракта).
13. **Markup для блока «Из расчёта» — item-level, не quote-level** (`entities/quote/types.ts:27-31` `divergent_markups`). Определить, какой markup показывать (первого item / `markup_percent`/`profit_amount` из `QuoteItemRow`) и источник (calc summary?).
14. **Req 6 scope сверки:** сравнение содержимого скана vs система (требует OCR/ручного ввода) ИЛИ только подтверждение, что скан существует + метаданные совпадают? `useControlChecks` сейчас проверяет только EXISTENCE для invoices, не content equality.
15. **Роль deal-creation:** server action бежит как 'sales, admin' (`deals.py` docstring), минуя матрицу `pending_signature→deal` (которая также допускает spec_controller). Подтвердить intended approver для confirmation-шага.
16. **Column-config refactor blast radius.** `KANBAN_COLUMNS` — module const в `kanban-page` (normalizeBoard), `kanban-board` (KanbanColumn map, findColumn) + тесты. Параметризация трогает shared logistics/customs движок — верифицировать отсутствие регрессии.
17. **`fetchQuoteDetail` org-scoping.** `canAccessQuote` возвращает true для контролёров без перепроверки `organization_id` (`queries.ts:961`). Org-boundary enforced на LIST-уровне; верифицировать, что `fetchQuoteDetail` сам фильтрует `organization_id`, иначе контролёр может открыть cross-org quote по URL (existence leak).
18. **`uploaded_by` на signed-scan documents row** опущен (`specification-step.tsx:236-247`) хотя колонка есть (m143:36) — minor audit-gap, не блокер. Заодно подтвердить, что RLS разрешает client-side Supabase-direct insert в `documents` (или перенести в API per api-first).
19. **`total_amount` latent bug (`deals.py:218`).** calc пишет `total_amount` И `total_quote_currency` в одно значение, но uncalculated quote может дать 0/NULL. Рекомендация: читать `total_quote_currency` или assert calculation freshness перед deal-creation.
20. **`database.md:114` устарел** — рекомендует `total_amount_quote` (удалён m318/m319). Не следовать; флаг на обновление steering-doc.
21. **Номера миграций:** `CLAUDE.md` (283) vs `migrations/` (318/319) — подтвердить на VPS до ALTER.
22. **m006 RLS DELETE policy** использует `r.code='admin'` (`006:158`) вместо `r.slug` — pre-existing latent bug, релевантно только если новый экран трогает spec-deletion RLS.

---

## 8. Рекомендованный порядок PR

Скорректированная 4-PR нарезка (schema-additive миграция применяется на VPS до мержа PR 1):

**PR 1 — Миграция + бэкенд-проводка (schema-additive, foundation).**
- `signing_fx_mode` + `signing_fx_rate` (+ опционально FK-колонки — решить в дизайне) на `kvota.specifications`.
- Расширить `SpecificationRow` тип + оба SELECT call-site; `specification_service.py` сериализация новых полей (если не покрыта).
- `npm run db:types`, `tsc` green, `check_select_columns.py`. Применить на VPS первым.
- Хелперы ролей `isQuoteController`/`isSpecController`/`canEditSpecControl`/`canSeeControlBoard` в `roles.ts` (изолированы, тестируемы — `filterItems`-style чистые функции).

**PR 2 — Экран спец-контроля (4 блока).**
- Блок «Из расчёта» (read-only из `quote` prop).
- Блок реквизитов: pre-load `seller_companies`/`locations`/`contracts` + `SearchableCombobox` дропдауны; swap plain `<Select>` контракта.
- Блок условий + control-stamp (signing FX mode/rate selector).
- Расширить insert/update payload (`handleCreate`/`handleSave`) новыми + «мёртвыми» колонками; добавить `created_by`.
- Read-only enforcement (`canEditSpecControl` + `ROLE_EDITABLE_STEPS`).

**PR 3 — Workflow «Отправить на подписание» + фаза «На подписании» + сверка.**
- Кнопка «Отправить на подписание» → `callWorkflowTransition(to_status:'pending_signature')`.
- Структурная сверка (`useControlChecks`-clone + `VerificationStrip`), гейтящая «Пометить подписанной».
- «Пометить подписанной» → существующий `confirmSignatureAndCreateDeal` → `/api/deals`; роутить `quote→'deal'` через `workflow_service.transition_quote_status` (decision из флага 1).

**PR 4 — Workspace `/workspace/control` (два канбана) + сайдбар + гарды.**
- Параметризовать `KANBAN_COLUMNS` → column-config prop (verify logistics/customs регресс).
- `ControlKanbanCard` type + `ControlCard` renderer + `fetchControlBoard` фетчер(ы) в entities.
- Страница `/workspace/control` с двумя board (колонки «На контроле»/«На подписании»).
- Sidebar-секция «Контроль» гейтнутая `hasRole(...)` + isAdmin.
- Fail-closed page-guard (decision из флага 8).

**Замечание по порядку:** PR 1 — обязательный foundation (миграция + типы + хелперы). PR 2 и PR 4 относительно независимы после PR 1 и могут идти параллельно при условии разнесения миграционных номеров и shared-файлов (`KANBAN_COLUMNS` трогает только PR 4). PR 3 зависит от PR 2 (кнопка/сверка живут на spec-экране). Между back-to-back мержами выдерживать ~90s (race на reuse имени docker-контейнера).