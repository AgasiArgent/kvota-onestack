# Control Spec Workspace — Технический дизайн

Экран контроля спецификации (двухфазный) + воркспейс `/workspace/control` с двумя
канбанами. **Extension** существующей системы: переиспользуем максимум, новой модели
данных не вводим, калькулятор не трогаем. Трассировка к требованиям — по числовым ID
(`requirements.md`). Полная карта переиспользования и флаги — `gap-analysis.md`.

## Архитектурное решение

**Единый источник истины воркфлоу — `quotes.workflow_status`.** Реактивируем мёртвый в
проде статус `pending_signature`. `specifications.status` остаётся производным/для
отображения — **третий writer не вводим**.

```
ТЕКУЩЕЕ (баг):  pending_spec_control ──(create_deal пишет 'deal' напрямую)──► deal
ЦЕЛЕВОЕ:        pending_spec_control
                   │ [Отправить на подписание]  callWorkflowTransition(pending_signature)
                   ▼
                pending_signature                ← колонка канбана «На подписании»
                   │ [Пометить подписанной]  (после структурной сверки)
                   │   confirmSignatureAndCreateDeal → POST /api/deals
                   │   + transition_quote_status(pending_signature → deal)  (аудит+роли)
                   ▼
                 deal  (цепочка табов КП завершена)
```

Переходы — через Python API (`POST /api/quotes/{id}/workflow/transition`, `api/quotes.py:895`,
роли в `workflow_service.py`); deal-side-effects — через существующий `POST /api/deals`.
Никакой бизнес-логики в Server Actions (api-first).

## Архитектурный паттерн и карта границ

| Слой (FSD / backend) | Что добавляем/меняем |
|---|---|
| `app/(app)/workspace/control` | Новая server-страница (фетч двух board, role-guard, fail-closed) |
| `features/quotes/.../specification-step` | Апгрейд экрана: 4 блока, дропдауны, сверка, «Отправить на подписание» |
| `features/workspace-control` (новый) или extend `workspace-kanban` | Control-карточки + два board (column-config prop) |
| `entities/workspace-control` (новый) | Фетчеры board (quotes by workflow_status / specs) |
| `entities/seller-company` (promote) | Тип+fetch наше-юрлицо (из `features/companies`) |
| `shared/lib/roles.ts` | Хелперы контролёров + edit-gate |
| `services/workflow_service.py` | (без изменений — переход уже есть) deal-handoff роутим через него |
| `migrations/<NEXT>` | Аддитивная: `signing_fx_mode`, `signing_fx_rate`, `seller_company_id` FK |

## Технологический стек

Reuse без новых зависимостей: Next.js 15 App Router (FSD), `SearchableCombobox`
(`shared/ui/searchable-combobox.tsx`), `KanbanBoard` dnd-kit
(`features/workspace-kanban`), `VerificationStrip`/`useControlChecks`-паттерн
(`features/quotes/.../control-step`), Supabase JS (schema `kvota`), Python API
(`callWorkflowTransition`, `confirmSignatureAndCreateDeal`).

---

## Компоненты и контракты

### 1. Экран контроля спецификации (Req 1–5)

Апгрейд `specification-step.tsx`. Четыре блока (макет: `docs/plans/2026-05-29-control-spec-workspace-design.png`).

**Блок «Из расчёта» (read-only) — Req 1.1–1.4.** Читается из переданного prop
`quote: QuoteDetailRow`:
```ts
// канон (database.md confusable + m318/319): НЕ total_amount_quote
type CalcReadonly = {
  currency: string;            // quote.currency
  totalWithVat: number | null; // quote.total_with_vat_quote
  total: number | null;        // quote.total_quote_currency
  profitUsd: number | null;    // quote.total_profit_usd
  fxToUsd: number | null;      // quote.exchange_rate_to_usd
};
```
Если расчёта нет → пометка «нет данных расчёта». Markup — item-level (`divergent_markups`),
показываем агрегат из calc-summary read-only (флаг 13 — уточнить точный источник на impl).

**Блок «Реквизиты» (searchable ▼) — Req 2.1–2.7.**
- Наше юрлицо → `SearchableCombobox<SellerCompany>`, источник `fetchSellerCompanies(orgId)`,
  persist **FK** `seller_company_id` + dual-write snapshot имени в `our_legal_entity`
  (совместимость экспорта `contract_spec_docx.py:214`).
- Юрлицо клиента → read-only из данных клиента (один набор; snapshot в `client_legal_entity`).
- Договор → `SearchableCombobox`, источник `customer_contracts` где `customer_id` = клиент КП
  и `status='active'`; заменяет plain `<Select>` (`specification-step.tsx:422-441`);
  inline-create сохраняем.
- Страны (забора/отгрузки/оплаты поставщику) → `SearchableCombobox` из distinct
  `locations.country`, persist строкой в существующие `cargo_pickup_country` /
  `goods_shipment_country` / `supplier_payment_country` (без FK на адрес-строку).

**Блок «Условия спецификации» (ввод) — Req 3.1–3.4.** Маппинг на существующие колонки:
`sign_date`, `validity_period`, `readiness_period`, `logistics_period`, `cargo_type`,
`delivery_city_russia`. Read-only, если роль без edit-права (Req 11.2/11.3).

**Блок «Контроль» — Req 4.1–4.5.**
```ts
type SigningFx =
  | { mode: 'cbr_on_payment_day' }            // default; signing_fx_rate = null
  | { mode: 'fixed'; rate: number };          // signing_fx_rate = rate
```
Ответственный контролёр = текущий пользователь; «Дата контроля» = серверное время при
«Отправить на подписание». Курс — selector режима (default `cbr_on_payment_day`).

**Действие «Отправить на подписание» — Req 5.1–5.4.**
`callWorkflowTransition(quoteId, { to_status: 'pending_signature' })`
(`entities/quote/mutations.ts:19`). Перед переходом — валидация обязательных реквизитов
(договор, наше юрлицо): при незаполнении блокировать + назвать/подсветить поля (без тихих
отказов). `created_by` дописать в insert (сейчас опущен).

### 2. Фаза «На подписании»: загрузка скана + структурная сверка (Req 6, 7)

**Сверка — Req 6.1–6.5 (ручной чек-лист, без OCR).** Клон shape `useControlChecks`:
```ts
type ReconCheck = {
  id: string;            // 'scan_uploaded' | 'spec_number' | 'contract' | 'parties' | 'totals' | 'dates' | 'signatory'
  label: string;
  systemValue: string;   // значение из системы (показываем рядом)
  confirmed: boolean;    // контролёр подтверждает совпадение со сканом глазами
};
```
Рендер через `VerificationStrip`-паттерн + сайд-бай-сайд (скан слева, значения системы
справа). Скан — `specifications.signed_scan_url` + строка `documents`
(`entity_type='specification'`, `document_type='specification_signed_scan'`), загрузка уже
есть (`specification-step.tsx:211-258`); дописать `uploaded_by` (флаг 18). ПОКА не
подтверждены все пункты И не загружен скан — «Пометить подписанной» disabled. Факт
прохождения сверки (кто/когда) фиксируем для прослеживаемости.

**Завершение — Req 7.1–7.4.** «Пометить подписанной» → `confirmSignatureAndCreateDeal(specId)`
(существующий, `mutations.ts`); deal-handoff `quote → 'deal'` роутим через
`workflow_service.transition_quote_status(pending_signature → deal)` вместо прямой записи
`api/deals.py:251` (аудит + проверка ролей). При ошибке — спека остаётся в
`pending_signature` (без частичного перехода). Воркфлоу сделки после создания — вне скоупа.

### 3. Воркспейс `/workspace/control` (Req 9, 10)

**Страница** `app/(app)/workspace/control/page.tsx` — зеркало
`workspace/logistics/page.tsx:22-67` (server: `getSessionUser` → orgId redirect →
role-guard → `Promise.all(два board)` → render). **Один route, переключатель** между двумя
канбанами (Req 9.1).

**Канбан «Контроль расчёта» (Req 9.2):** карточки = quotes в `pending_quote_control` /
`pending_approval`. Колонки по статусу.
**Канбан «Контроль спецификации» (Req 9.3):** карточки = quotes в `pending_spec_control`
(колонка «На контроле») и `pending_signature` (колонка «На подписании»).

**Column-config (Req 9, HYBRID):** параметризовать hard-coded `KANBAN_COLUMNS`
(`kanban-board.tsx:21`, `model/types.ts:23`) → prop `columns: ColumnConfig[]`. Regress-тест
logistics/customs (флаг 16).

**Card-тип + фетчер (entities):**
```ts
type ControlKanbanCard = {
  quoteId: string; idnQuote: string; customerName: string;
  total: number | null; currency: string;
  workflowStatus: string;       // → колонка
  controllerName: string | null;
};
async function fetchControlBoard(
  domain: 'calc' | 'spec',
  user: { id: string; roles: string[]; orgId: string },
): Promise<ControlKanbanCard[]>;   // org-scoped; статусы по domain
```
**Навигация (Req 10):** клик → `/quotes/{id}?step=control` (calc) /
`?step=specification` (spec). Карточки **кликабельные, без drag** (решение владельца).
Таб `control` (`control-step.tsx`) не меняем (Req 10.3).

**Сайдбар (Req 9.4):** пункт «Контроль» → `/workspace/control` в
`widgets/sidebar/sidebar-menu.ts` (shape как «Очередь логистики», гейт
`hasRole('quote_controller','spec_controller','top_manager')` + isAdmin).

### 4. Доступ и роли (Req 11)

`shared/lib/roles.ts` — новые чистые хелперы:
```ts
isQuoteController(roles): boolean
isSpecController(roles): boolean
canSeeControlBoard(roles): { calc: boolean; spec: boolean }  // admin/top_manager → оба
canEditSpecControl(roles): boolean   // spec_controller || admin
```
- Видимость канбанов (Req 11.1): `quote_controller`→calc, `spec_controller`→spec,
  `admin`/`top_manager`→оба.
- `top_manager` read-only (Req 11.2): extend `ROLE_EDITABLE_STEPS` (`entities/quote/types.ts`)
  — `top_manager: []`, контролёрам — только их control-шаг; работает через существующую
  `isReadOnly`-машинерию (`quotes/[id]/page.tsx:129-132`). Один источник истины.
- Edit-gate полей (Req 11.3): `canEditSpecControl` в компоненте + field-scope в Python API.
- 404-on-denial (Req 11.4): `canAccess*` гард; проверить, что `fetchQuoteDetail` сам
  фильтрует `organization_id` (флаг 17 — иначе cross-org existence leak).
- Fail-closed (Req 11.5): страница `/workspace/control` редиректит/`notFound()` для
  неавторизованных (сознательная дивергенция от fail-open logistics/customs, флаг 8).

---

## Модель данных / миграция (Req 4.5, 8)

Одна **аддитивная** миграция к `kvota.specifications`. Номер — **подтвердить на VPS**
(`kvota.schema_migrations`) до написания (CLAUDE.md=283 vs `migrations/`=318/319).

```sql
-- migrations/<NEXT>_control_spec_signing_fx_and_seller_fk.sql
BEGIN;
ALTER TABLE kvota.specifications
  ADD COLUMN IF NOT EXISTS signing_fx_mode VARCHAR(32)
    CHECK (signing_fx_mode IS NULL OR signing_fx_mode IN ('cbr_on_payment_day','fixed')),
  ADD COLUMN IF NOT EXISTS signing_fx_rate DECIMAL(15,6),               -- как exchange_rate_to_ruble
  ADD COLUMN IF NOT EXISTS seller_company_id UUID
    REFERENCES kvota.seller_companies(id) ON DELETE SET NULL;
COMMIT;
```
- **Страны и юрлицо клиента — без новых колонок** (используем существующие VARCHAR
  `*_country` / `client_legal_entity`).
- **Наше юрлицо:** FK `seller_company_id` (канон выбора) + dual-write snapshot имени в
  существующий `our_legal_entity` (совместимость экспорта).
- **Backfill не требуется** (все nullable). `signing_fx_mode` NULL до явного выбора
  (fail-loud, без тихого дефолта в БД; default в UI).
- Калькулятор эти колонки **не читает** (проверено: совпадения только в
  `specification_service.py` + `contract_spec_docx.py`) → «calc-engine LOCKED» соблюдён.
- После применения: `cd frontend && npm run db:types`, `tsc` green,
  `tools/check_select_columns.py`; применить на VPS **до** мержа PR, читающего колонки;
  reset `/root/onestack` на main после применения с ветки.

---

## План файлов

**Новые:**
- `app/(app)/workspace/control/page.tsx` — страница воркспейса (server).
- `features/workspace-control/` (или extend `workspace-kanban`) — `ControlCard`, two-board shell.
- `entities/workspace-control/queries.ts` — `fetchControlBoard`, `ControlKanbanCard`.
- `entities/seller-company/` — promote типа+fetch из `features/companies`.
- `features/quotes/.../specification-step/reconciliation-strip.tsx` — сверка (Req 6).
- `migrations/<NEXT>_control_spec_signing_fx_and_seller_fk.sql`.

**Меняем:**
- `specification-step.tsx` — 4 блока, дропдауны, «Отправить на подписание», сверка.
- `specification-step/queries.ts` + `SpecificationRow` — widen SELECT (оба call-site!).
- `specification-step/mutations.ts` — insert/update новых полей, deal-handoff через workflow_service.
- `shared/lib/roles.ts` — хелперы контролёров.
- `entities/quote/types.ts` — `ROLE_EDITABLE_STEPS` (read-only top_manager).
- `widgets/sidebar/sidebar-menu.ts` — пункт «Контроль».
- `features/workspace-kanban/model/types.ts` + `kanban-board.tsx` — column-config prop.

## Последовательность сборки (4 PR)

**PR 1 — Миграция + проводка типов + роли (foundation).** Миграция (signing_fx + seller FK);
widen `SpecificationRow` + оба SELECT; сериализация в `specification_service.py` (если не
покрыта); хелперы ролей в `roles.ts` (чистые, тестируемые); `ROLE_EDITABLE_STEPS`.
db:types + tsc + check_select_columns. Применить миграцию на VPS первой.

**PR 2 — Экран контроля (4 блока).** Блок «Из расчёта»; реквизиты (pre-load
seller_companies/locations/contracts + `SearchableCombobox`, swap контракт-Select); условия;
control-stamp (signing FX selector); расширить insert/update + `created_by`; edit-gate.

**PR 3 — Workflow + фаза «На подписании» + сверка.** «Отправить на подписание»
(`callWorkflowTransition`); `ReconciliationStrip` (чек-лист), гейтит «Пометить подписанной»;
deal-handoff через `workflow_service.transition_quote_status`.

**PR 4 — Воркспейс + сайдбар + гарды.** Column-config prop (regress logistics/customs);
`ControlKanbanCard` + `ControlCard` + `fetchControlBoard`; страница `/workspace/control`
(два board); сайдбар; fail-closed guard.

PR 2 и PR 4 относительно независимы после PR 1 (могут идти параллельно при разнесении
shared-файлов). PR 3 зависит от PR 2. Между мержами ~90s (docker race).

## Трассируемость требований

| Req | Компонент |
|---|---|
| 1.1–1.4 | Блок «Из расчёта» (read-only из `quote` prop) |
| 2.1–2.7 | Блок «Реквизиты» (`SearchableCombobox` + FK seller / locations-country / contracts) |
| 3.1–3.4 | Блок «Условия спецификации» |
| 4.1–4.5 | Блок «Контроль» + миграция signing_fx |
| 5.1–5.4 | «Отправить на подписание» → `pending_signature` |
| 6.1–6.5 | `ReconciliationStrip` (ручной чек-лист) |
| 7.1–7.4 | «Пометить подписанной» → `confirmSignatureAndCreateDeal` + transition→`deal` |
| 8.1–8.5 | Аддитивная миграция (seller FK) + db:types гейт |
| 9.1–9.6 | Страница `/workspace/control`, два канбана, column-config, сайдбар |
| 10.1–10.3 | Навигация карточка → таб; control-step не трогаем |
| 11.1–11.5 | Хелперы ролей, `ROLE_EDITABLE_STEPS`, fail-closed гард |
| 12.1–12.5 | Reuse, api-first, нет новой модели/статусов |

## Риски

1. **Column-config blast radius** (`KANBAN_COLUMNS` shared с logistics/customs) → regress-тест
   обоих перед мержем PR 4.
2. **Номер миграции** — подтвердить на VPS до ALTER.
3. **Export-совместимость** — dual-write snapshot имени юрлица обязателен.
4. **`fetchQuoteDetail` org-scoping** (флаг 17) — проверить фильтр `organization_id`.
5. **`total_amount` latent bug** (`api/deals.py:218`) — при deal-handoff читать
   `total_quote_currency` / assert свежести расчёта (флаг 19, попутно).
6. **Уточнить на impl:** источник markup для блока «Из расчёта» (флаг 13); набор полей
   сверки (Req 6.2 — оставлен открытым владельцем).
