# Logistics & Customs Redesign — Design Spec

**Date:** 2026-04-22
**Status:** Draft — awaiting user review
**Owners:** Andrey (product), Claude (architect)
**Related ТЗ:** FB-260415-190332-ee01 (logistics), WhatsApp conversation 2026-04-16 (customs)
**Wireframes:** `.superpowers/brainstorm/72929-1776845947/content/*.html` (5 screens)

---

## 1. Overview

Single redesign of the **logistics** and **customs** stages of the quote → deal pipeline, covering four user-visible surfaces:

1. **Workspace** for logistics and customs teams — assignment-based "Мои заявки" with SLA timers, "Неназначенные" escalation for heads
2. **Route Constructor** — per-invoice visual timeline for building logistics cost routes
3. **Customs handsontable** — column consolidation + autofill from history + table views
4. **Admin routing** — head-only UI for configuring auto-assignment patterns (currently missing)

The redesign touches schema (≈10 migrations), FastAPI endpoints (≈20 new), Next.js pages (3 new routes + 2 rework'd quote-detail steps), and introduces 4 new cross-cutting primitives: `entity_notes`, `table_views`, `location_type` enum, and `logistics_operational_events`.

### Why now

Two ТЗ сошлись в одну точку:
- **Logistics** ТЗ (FB-260415-190332-ee01) просит пересмотреть модель сегментов, добавить workspace-уровень очередь, разделить operational от pricing, ввести комментарии от смежных отделов.
- **Customs** ТЗ (WhatsApp 2026-04-16) просит консолидировать колонки handsontable, внедрить автозаполнение по истории, добавить per-item и per-quote доп.расходы, зафиксировать RUB-only ввод.

Оба ТЗ упираются в одни и те же примитивы (`locations`, `entity_notes`, `invoice_items`-triggers), поэтому решаем вместе как один design.

### Parallel work

Ветка `/procurement` работает параллельно над смежным доменом (invoices, suppliers, items). **Три под-проекта** из этого spec'а координируем с procurement-веткой (см. §10). Остальные 14 идут в собственной ветке `feat/logistics-customs-redesign` без конфликтов.

---

## 2. Goals and Non-Goals

### Goals

- **G1** Убрать "лимбо" состояние заявок — авто-назначение сразу после `pending_logistics_and_customs`, SLA-таймер с момента назначения.
- **G2** Разделить **operational events** (ГТД загружена, таможня прошла) от **pricing segments** (сколько стоит довезти). Сейчас они в одной таблице `logistics_stages`.
- **G3** Сделать модель сегментов **per-invoice** + гибкий конструктор (не фиксированный набор этапов). Поддерживает "2 КП поставщика" из ТЗ.
- **G4** Customs autofill по `(brand, product_code)` — если товар уже проходил таможню, предложить прошлые значения. Bulk-accept с обязательной проверкой сертификатов.
- **G5** Smart delta: procurement меняет invoice items — система знает, что именно нужно пересмотреть (логистике / таможне / обоим / никому).
- **G6** Закрыть UI-дыру: `/admin/routing` для логистики (backend существует с m027, frontend отсутствует).
- **G7** Единая модель комментариев (`entity_notes`) с polymorphic FK, RBAC через `visible_to[]` — МОЗ/МОП/логист/таможенник/customer-level заметки.
- **G8** Table views (saved column configs) для широких таблиц — в первую очередь customs, переиспользуется в других местах.

### Non-Goals

- **NG1** Не трогаем calculation engine. Адаптируем старый контракт через view `v_logistics_plan_fact_items`.
- **NG2** Не вводим 2 типа логиста (external/internal) — отложено до execution phase.
- **NG3** Не делаем реестр перевозчиков (пользователь явно сказал "сейчас можно пропустить").
- **NG4** Не делаем carrier-aware routing (страна → перевозчик) — future work.
- **NG5** Не мигрируем существующие сделки в "стадии логистика в работе" автоматически. Breaking rewrite принят осознанно (см. §5.2).

---

## 3. Design Decisions (fixed during brainstorming)

Каждое решение — с обоснованием и отброшенной альтернативой. Решения приняты в интерактивной сессии 2026-04-21/22.

### 3.1 Сегменты маршрута — **per-invoice конструктор**

**Решение:** `logistics_route_segments` with `invoice_id FK`, freeform `logistics_segment_expenses` внутри сегмента. Гибкий набор сегментов (не enum), сборка через UI-конструктор.

**Обоснование:** реальная бизнес-логика: разные поставщики могут идти разными путями (из Китая и Турции), физическая посылка "одна на инвойс". Даже если клиент получает несколько партий, расценка на уровне invoice.

**Отброшено:**
- Per-deal (как сейчас в `logistics_stages`) — ломается на "2 КП от разных поставщиков".
- Hybrid split at customs (до таможни per-invoice, после — per-deal) — overcomplicate для текущих объёмов.

### 3.2 Operational vs Pricing — разные таблицы

**Решение:** отдельная таблица `logistics_operational_events (deal_id, event_type, status, event_date, notes)` для статусов "ГТД загружена / таможня прошла / доставлено". Сегменты (pricing) живут в `logistics_route_segments`.

**Обоснование:** сейчас в `logistics_stages` смешаны `first_mile`-`gtd_upload`-`last_mile` (миграция 163), с костылём `stage_allows_expenses()` для отключения расходов на operational этапах. Это leaking abstraction — два разных concept'а в одной таблице.

### 3.3 Auto-assignment логиста — existing backend + new UI

**Решение:** используем существующий `services/route_logistics_assignment_service.py` (1157 строк, полный CRUD) и `workflow_service.assign_logistics_to_invoices()` (уже вызывается при переходе в `pending_logistics_and_customs`). Достраиваем **UI вкладку "Логистика" в `/admin/routing`**.

**Обоснование:** backend работает в проде (написан ещё в FastHTML-эру), но после Phase 6C (uvicorn-switch) остался без Next.js UI. Head_of_logistics сейчас конфигурирует patterns либо напрямую в БД, либо не конфигурирует вовсе.

### 3.4 Auto-assignment таможни — least-loaded

**Решение:** без отдельной `route_customs_assignments` таблицы. Функция `assign_customs_to_invoices(quote_id)` выбирает пользователя с ролью `customs` и наименьшим количеством открытых `invoices.assigned_customs_user = user AND customs_completed_at IS NULL`.

**Обоснование:** 1-2 таможенника сейчас в команде — полноценный routing с patterns избыточен. Least-loaded самоадаптивен (если один в отпуске и не закрывает заявки, система им не подсовывает новые).

**Отброшено:** round-robin counter (плох при разной скорости работы), mirror `route_customs_assignments` (overkill для двух человек).

### 3.5 Workspace — assigned-based, без pull

**Решение:** вкладки "Мои заявки" / "Завершённые" для рядовых; head видит дополнительно "Неназначенные" (fallback для unmatched routing) и "Все заявки". Никакой кнопки "Взять в работу".

**Обоснование:** pull-based "общий котёл" создаёт лимбо, где заявки могут висеть ничьи. Assignment-based + fallback через head — нет ничьих состояний.

### 3.6 SLA timers — один таймер от `assigned_at`

**Решение:** три поля на `invoices`: `logistics_assigned_at`, `logistics_deadline_at (= assigned_at + sla_hours * interval)`, `logistics_completed_at`. Аналогично для customs. SLA hours настраиваемо per-org (default 72h).

**Обоснование:** убираем "Начать работу" — второй статус = второе лимбо. Один таймер, одно состояние "в работе". Производность: `NOW() < deadline_at AND completed_at IS NULL` → зелёный; `NOW() > deadline_at AND completed_at IS NULL` → красный.

### 3.7 Comments — `entity_notes` с polymorphic FK

**Решение:** единая таблица `entity_notes (id, entity_type, entity_id, author_id, author_role, visible_to[], body, pinned, created_at)`. Используется для quote-level, customer-level, invoice-level комментариев.

**Обоснование:**
- Один концепт — одна таблица. Ранее в проекте были две параллельные схемы для одного понятия (customs_ds_sgr vs license_ds_*, logistics_additional_expenses vs deal_logistics_expenses) — не повторяем этот паттерн.
- Authorship + timestamp + threading бесплатно.
- RBAC через `visible_to[]` проще чем матрица полей по сущностям.

**Trade-off:** нет database-level integrity для polymorphic FK. Компенсируется проверкой в application layer + существующий soft-delete pattern.

### 3.8 Smart delta — DB trigger с явной матрицей

**Решение:** AFTER INSERT/UPDATE/DELETE trigger на `kvota.invoice_items`. Матрица, какие изменения триггерят какие review-флаги:

| Что поменялось | `logistics_needs_review_since` | `customs_needs_review_since` |
|----------------|-------------------------------|------------------------------|
| `price_original` (скидка) | — | — |
| `product_code` (артикул) | — | — |
| `product_name` (наименование) | — | — |
| `brand` | — | — |
| `quantity` / `total_weight` / `total_volume` / `packages_count` | ✅ | — |
| `supplier_id` (смена поставщика → другая страна) | ✅ | ✅ |
| INSERT row (новая позиция) | ✅ | ✅ |
| DELETE row (удалённая позиция) | ✅ | ✅ |

**Обоснование:** DB trigger срабатывает независимо от пути обновления (Python API, Next.js Server Action, admin SQL). Application-layer detection пропустил бы случаи.

**Отброшено:**
- Hard invalidate (стирает segments при любом изменении) — теряет работу логиста на копеечных правках
- Soft flag без правил (помечает всё стейлом) — игнорирует нюанс customs vs logistics
- Lock-after-pricing — блокирует procurement unnecessary

### 3.9 Customs autofill — `(brand, product_code)` + LATERAL JOIN

**Решение:** endpoint `/api/customs/autofill` принимает массив items, возвращает suggestions. Под капотом — LATERAL join на `quote_items` WHERE `hs_code IS NOT NULL` + самая свежая запись по `(brand, product_code)`. Bulk-accept UI с обязательным checkbox'ом "Сертификаты ДС/СС/СГР актуальны".

**Обоснование:** нет separate knowledge base — используем существующие quote_items как источник истины. Индекс `idx_quote_items_brand_product_code_for_autofill` для performance. LATERAL join решает N+1 одним запросом.

### 3.10 Table views — generic `table_views`

**Решение:** таблица `table_views (id, org_id, user_id NULL|uuid, table_key, name, is_default, config jsonb)`. `user_id IS NULL` = org-wide view (создаёт head_of_customs / head_of_logistics), `user_id = X` = personal. `config` хранит `visible_columns[]`, `column_order[]`, `column_widths{}`.

**Обоснование:** customs handsontable имеет 20+ колонок, без column visibility управлять невозможно. Generic структура (не customs-specific) — переиспользуется для logistics cargo, quotes list и прочих широких таблиц. Empty start — seed-пресеты не делаем, head создаёт сам.

### 3.11 Роли — добавляем `head_of_customs`

**Решение:** миграция создаёт новую системную роль `head_of_customs` (симметрично существующему `head_of_logistics`). Один человек может иметь обе head-роли одновременно.

**Обоснование:** сейчас в проекте есть `head_of_logistics`, `head_of_procurement`, `head_of_sales` — нет `head_of_customs`. Добавляем для симметрии. User_roles уже many-to-many, комбинация ролей естественна.

### 3.12 Calc engine — не трогаем, адаптер через view

**Решение:** SQL view `v_logistics_plan_fact_items` агрегирует `logistics_route_segments` + `logistics_segment_expenses` в формат, совместимый со старыми `plan_fact_items.logistics_stage_id`-строками. Calc engine читает view, не зная об изменении модели.

**Обоснование:** calc engine locked (правило пользователя: `CalcEngine.py` / `calculation_models.py` / `calculation_mapper.py` — не модифицировать). Read-side адаптация — стандартный паттерн (expand-contract без contract-stage, потому что expand = vista).

**Side effect:** view readonly — все writer'ы форсированно работают только с новой моделью. Это хорошо (предотвращает двойные writable API).

### 3.13 Preset маршрутов — CRUD для логистов

**Решение:** таблица `logistics_route_templates` + `logistics_route_template_segments`. CRUD доступен ролям `logistics`, `head_of_logistics`, `admin`. Все видят read-only при выборе пресета в конструкторе.

**Обоснование:** логисты знают реальные маршруты лучше чем админ. Self-service CRUD снижает нагрузку на head'а.

---

## 4. Architecture Overview

### 4.1 Stack reminder (after Phase 6C)

- **Backend:** FastAPI (uvicorn), `api/` folder with per-domain routers
- **Frontend:** Next.js 15 App Router, FSD (features/entities/shared)
- **DB:** Supabase Postgres, schema `kvota`
- **UI kit:** shadcn/ui + Tailwind v4 + Plus Jakarta Sans
- **Calc engine:** locked, read-only contract via view
- **No FastHTML:** archived in `legacy-fasthtml/`

### 4.2 Layer boundaries

```
┌────────────────────────────────────────────────────────┐
│  Next.js (frontend/src/)                               │
│  ├─ app/(app)/workspace/{logistics,customs}/           │  ← new routes
│  ├─ app/(app)/quotes/[id]/  — logistics & customs tabs │  ← rework
│  ├─ app/(app)/admin/routing/  — logistics & customs tabs  ← extend
│  ├─ features/quotes/ui/{logistics,customs}-step/       │
│  ├─ entities/{route-segment,customs-autofill,           │
│  │             table-view,entity-note}/                │
│  └─ shared/ui/  — reuses shadcn primitives             │
└────────────────────────────────────────────────────────┘
                          ↕ HTTP (JSON)
┌────────────────────────────────────────────────────────┐
│  FastAPI (api/)                                        │
│  ├─ routers/logistics.py   — CRUD segments, expenses   │
│  ├─ routers/customs.py     — autofill, expenses        │
│  ├─ routers/workflow.py    — assigned→complete         │
│  ├─ routers/notes.py       — entity_notes CRUD         │
│  ├─ routers/table_views.py — table_views CRUD          │
│  └─ routers/admin_routing.py — route_logistics_assignments │
└────────────────────────────────────────────────────────┘
                          ↕ Supabase client
┌────────────────────────────────────────────────────────┐
│  Postgres (kvota.*)                                    │
│  ├─ tables: logistics_route_segments, *_expenses,       │
│  │           operational_events, route_templates,      │
│  │           entity_notes, table_views, ...            │
│  ├─ triggers: invoice_items_change → review flags      │
│  ├─ views: v_logistics_plan_fact_items (→ calc engine) │
│  └─ RLS: role-based per entity                          │
└────────────────────────────────────────────────────────┘
```

### 4.3 Data flow: typical logistics lifecycle

1. Quote → workflow reaches `pending_logistics_and_customs`.
2. `assign_logistics_to_invoices(quote_id)` + `assign_customs_to_invoices(quote_id)` срабатывают синхронно в одном workflow step.
3. Invoices получают `assigned_logistics_user`, `assigned_customs_user`, timestamps (`*_assigned_at`, `*_deadline_at`). Unmatched → `assigned_logistics_user IS NULL`.
4. Telegram-уведомления рассылаются новым assignee (через `telegram_service`).
5. Workspace `/workspace/logistics` показывает каждому свои invoice (SELECT WHERE `assigned_logistics_user = me AND completed_at IS NULL`).
6. Логист открывает quote → этап Логистика → конструктор маршрута для invoice #N.
7. Сегменты и expenses сохраняются в `logistics_route_segments` + `logistics_segment_expenses`.
8. Логист жмёт "Завершить расценку" → `invoices.logistics_completed_at = NOW()`, view обновляется, calc engine увидит новые плановые цифры при следующем запросе.
9. Аналогично для customs + autofill-bulk-accept flow.
10. Когда и логистика и таможня завершены (каждый invoice) — workflow переход в следующий state.

---

## 5. Data Model

### 5.1 New tables

#### `kvota.logistics_route_segments`

```sql
CREATE TABLE kvota.logistics_route_segments (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id        UUID NOT NULL REFERENCES kvota.invoices(id) ON DELETE CASCADE,
    sequence_order    INT  NOT NULL,
    from_location_id  UUID NOT NULL REFERENCES kvota.locations(id),
    to_location_id    UUID NOT NULL REFERENCES kvota.locations(id),
    label             TEXT,
    transit_days      INT,
    main_cost_rub     DECIMAL(15, 2) NOT NULL DEFAULT 0,
    carrier           TEXT,
    notes             TEXT,
    created_at        TIMESTAMPTZ DEFAULT now(),
    updated_at        TIMESTAMPTZ DEFAULT now(),
    created_by        UUID REFERENCES auth.users(id),
    UNIQUE (invoice_id, sequence_order)
);
CREATE INDEX ON kvota.logistics_route_segments (invoice_id);
-- RLS: org_members + logistics/head_of_logistics/admin
```

#### `kvota.logistics_segment_expenses`

```sql
CREATE TABLE kvota.logistics_segment_expenses (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    segment_id UUID NOT NULL REFERENCES kvota.logistics_route_segments(id) ON DELETE CASCADE,
    label      TEXT NOT NULL,          -- "СВХ Шанхай", "Переоформление"
    cost_rub   DECIMAL(15, 2) NOT NULL DEFAULT 0,
    days       INT,                    -- optional (для хранения)
    notes      TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON kvota.logistics_segment_expenses (segment_id);
```

#### `kvota.logistics_operational_events`

```sql
CREATE TABLE kvota.logistics_operational_events (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id    UUID NOT NULL REFERENCES kvota.deals(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,   -- 'gtd_uploaded', 'customs_cleared', 'delivered', ...
    status     VARCHAR(20) NOT NULL DEFAULT 'pending',
    event_date TIMESTAMPTZ,
    notes      TEXT,
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON kvota.logistics_operational_events (deal_id);
```

#### `kvota.logistics_route_templates` + `kvota.logistics_route_template_segments`

```sql
CREATE TABLE kvota.logistics_route_templates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES kvota.organizations(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    created_by      UUID REFERENCES auth.users(id),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (organization_id, name)
);

CREATE TABLE kvota.logistics_route_template_segments (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id       UUID NOT NULL REFERENCES kvota.logistics_route_templates(id) ON DELETE CASCADE,
    sequence_order    INT  NOT NULL,
    from_location_type VARCHAR(30) NOT NULL,  -- 'supplier', 'hub', 'customs', 'warehouse', 'client'
    to_location_type   VARCHAR(30) NOT NULL,
    default_label      TEXT,
    default_days       INT,
    UNIQUE (template_id, sequence_order)
);
```

Note: template stores **location types**, not concrete locations. Concrete locations выбираются логистом при применении шаблона.

#### `kvota.customs_item_expenses` + `kvota.customs_quote_expenses`

```sql
CREATE TABLE kvota.customs_item_expenses (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_item_id UUID NOT NULL REFERENCES kvota.quote_items(id) ON DELETE CASCADE,
    label         TEXT NOT NULL,
    amount_rub    DECIMAL(15, 2) NOT NULL DEFAULT 0,
    notes         TEXT,
    created_at    TIMESTAMPTZ DEFAULT now(),
    created_by    UUID REFERENCES auth.users(id)
);
CREATE INDEX ON kvota.customs_item_expenses (quote_item_id);

CREATE TABLE kvota.customs_quote_expenses (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id   UUID NOT NULL REFERENCES kvota.quotes(id) ON DELETE CASCADE,
    label      TEXT NOT NULL,
    amount_rub DECIMAL(15, 2) NOT NULL DEFAULT 0,
    notes      TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    created_by UUID REFERENCES auth.users(id)
);
CREATE INDEX ON kvota.customs_quote_expenses (quote_id);
```

#### `kvota.entity_notes`

```sql
CREATE TABLE kvota.entity_notes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(20) NOT NULL,       -- 'quote' | 'customer' | 'invoice' | ...
    entity_id   UUID NOT NULL,
    author_id   UUID NOT NULL REFERENCES auth.users(id),
    author_role VARCHAR(30) NOT NULL,       -- 'sales' | 'procurement' | 'logistics' | 'customs' | ...
    visible_to  TEXT[] NOT NULL DEFAULT '{"*"}',  -- array of role slugs or '*'
    body        TEXT NOT NULL,
    pinned      BOOLEAN DEFAULT false,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON kvota.entity_notes (entity_type, entity_id);
CREATE INDEX ON kvota.entity_notes USING GIN (visible_to);
-- RLS: see §9.1
```

#### `kvota.table_views`

```sql
CREATE TABLE kvota.table_views (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES kvota.organizations(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES auth.users(id) ON DELETE CASCADE,  -- NULL = org-wide
    table_key       VARCHAR(50) NOT NULL,
    name            VARCHAR(100) NOT NULL,
    is_default      BOOLEAN DEFAULT false,
    config          JSONB NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    created_by      UUID REFERENCES auth.users(id),
    UNIQUE (organization_id, user_id, table_key, name)
);
CREATE INDEX ON kvota.table_views (user_id, table_key);
CREATE INDEX ON kvota.table_views (organization_id, table_key) WHERE user_id IS NULL;
```

### 5.2 Changes to existing tables

#### `kvota.invoices` (ALTER)

```sql
ALTER TABLE kvota.invoices
  -- Customs assignment
  ADD COLUMN assigned_customs_user UUID REFERENCES auth.users(id),
  -- Logistics timers
  ADD COLUMN logistics_assigned_at TIMESTAMPTZ,
  ADD COLUMN logistics_deadline_at TIMESTAMPTZ,
  ADD COLUMN logistics_completed_at TIMESTAMPTZ,
  ADD COLUMN logistics_sla_hours INT DEFAULT 72,
  -- Customs timers
  ADD COLUMN customs_assigned_at TIMESTAMPTZ,
  ADD COLUMN customs_deadline_at TIMESTAMPTZ,
  ADD COLUMN customs_completed_at TIMESTAMPTZ,
  ADD COLUMN customs_sla_hours INT DEFAULT 72,
  -- Smart delta review flags
  ADD COLUMN logistics_needs_review_since TIMESTAMPTZ,
  ADD COLUMN customs_needs_review_since TIMESTAMPTZ;

CREATE INDEX ON kvota.invoices (assigned_customs_user) WHERE assigned_customs_user IS NOT NULL;
CREATE INDEX ON kvota.invoices (logistics_completed_at) WHERE logistics_completed_at IS NULL;
CREATE INDEX ON kvota.invoices (customs_completed_at) WHERE customs_completed_at IS NULL;
```

#### `kvota.locations` (ALTER)

```sql
ALTER TABLE kvota.locations
  ADD COLUMN location_type VARCHAR(20) DEFAULT 'hub' NOT NULL;
-- check constraint: 'supplier' | 'hub' | 'customs' | 'own_warehouse' | 'client'
ALTER TABLE kvota.locations
  ADD CONSTRAINT locations_location_type_check
  CHECK (location_type IN ('supplier', 'hub', 'customs', 'own_warehouse', 'client'));

-- Backfill old is_hub / is_customs_point into location_type
UPDATE kvota.locations SET location_type = 'customs' WHERE is_customs_point = true AND location_type = 'hub';
UPDATE kvota.locations SET location_type = 'hub' WHERE is_hub = true AND location_type = 'hub' AND is_customs_point = false;
-- Default 'hub' pre-filled; reviewers set client/supplier/warehouse by hand
```

**Note:** keeping `is_hub` / `is_customs_point` booleans for backwards compat with seed script (м024) and `search_locations()` RPC. Deprecated in favor of `location_type`. Cleanup — separate migration after 6 months.

#### `kvota.quote_items` (ALTER — dropping consolidated columns)

```sql
-- В рамках Wave 1 sub-project B
ALTER TABLE kvota.quote_items DROP COLUMN customs_ds_sgr;   -- дубль license_*_*
ALTER TABLE kvota.quote_items DROP COLUMN customs_marking;  -- дубль customs_honest_mark
ALTER TABLE kvota.quote_items RENAME COLUMN customs_psn_pts TO customs_psm_pts;  -- typo fix
-- license_ds/ss/sgr_required + _cost остаются
```

#### `kvota.roles` (INSERT)

```sql
-- Sub-project J
INSERT INTO kvota.roles (slug, name, description, is_system_role, organization_id)
SELECT 'head_of_customs',
       'Руководитель таможни',
       'Назначает таможенников, видит все заявки таможни, управляет правилами',
       false,
       o.id
FROM kvota.organizations o
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.roles r
    WHERE r.slug = 'head_of_customs' AND r.organization_id = o.id
);
```

### 5.3 Triggers

#### `invoice_items_change_trigger` — smart delta

Полный SQL в §3.8 обоснование. Ключевая логика:
- AFTER INSERT/UPDATE/DELETE on `invoice_items`
- Match changed fields против матрицы (quantity/weight/supplier_id/...)
- UPDATE `invoices` flags only if `logistics_completed_at IS NOT NULL` (нет смысла flag'ать если ещё не расценено)
- INSERT в `logistics_operational_events` для audit trail с diff в JSON

### 5.4 Views

#### `v_logistics_plan_fact_items` — calc engine адаптер

```sql
CREATE OR REPLACE VIEW kvota.v_logistics_plan_fact_items AS
SELECT
    gen_random_uuid() AS id,
    d.id AS deal_id,
    pfc.id AS category_id,
    COALESCE(rs.label, rs.sequence_order::text) AS description,
    rs.main_cost_rub AS planned_amount,
    'RUB' AS planned_currency,
    NULL::timestamptz AS planned_date,
    rs.created_by,
    'v_logistics'::text AS source
FROM kvota.logistics_route_segments rs
JOIN kvota.invoices i ON i.id = rs.invoice_id
JOIN kvota.deals d ON d.id = i.deal_id  -- via spec
JOIN kvota.plan_fact_categories pfc
     ON pfc.code = 'logistics_segment'
     -- Simplified: exact UNION/JOIN logic deferred to sub-project H implementation.
     -- Will map segment (from_location_type, to_location_type) → plan_fact_category code
     -- based on final category taxonomy decided during H PR review.
UNION ALL
SELECT
    gen_random_uuid() AS id,
    d.id AS deal_id,
    pfc.id AS category_id,
    se.label AS description,
    se.cost_rub AS planned_amount,
    'RUB' AS planned_currency,
    NULL::timestamptz AS planned_date,
    NULL AS created_by,
    'v_logistics_expense'::text AS source
FROM kvota.logistics_segment_expenses se
JOIN kvota.logistics_route_segments rs ON rs.id = se.segment_id
JOIN kvota.invoices i ON i.id = rs.invoice_id
JOIN kvota.deals d ON d.id = i.deal_id
JOIN kvota.plan_fact_categories pfc
     ON pfc.code = 'logistics_additional_expense';
```

**Read-only view.** Calc engine reads from `plan_fact_items` + this view merged (through adapter query). Adapter location: `services/calc_engine_logistics_adapter.py` (new file). Calc engine itself unchanged.

---

## 6. API Endpoints

### 6.1 Logistics

```
POST   /api/logistics/segments
GET    /api/logistics/segments?invoice_id=<uuid>
PATCH  /api/logistics/segments/{id}
DELETE /api/logistics/segments/{id}
POST   /api/logistics/segments/{id}/reorder  { new_sequence_order }

POST   /api/logistics/expenses
DELETE /api/logistics/expenses/{id}

GET    /api/logistics/templates
POST   /api/logistics/templates
DELETE /api/logistics/templates/{id}
POST   /api/logistics/templates/{id}/apply?invoice_id=<uuid>  — material­ise segments

POST   /api/logistics/complete  { invoice_id }  — check no pending review, set completed_at
POST   /api/logistics/acknowledge-review  { invoice_id }  — clear review_since flag
```

### 6.2 Customs

```
POST   /api/customs/autofill  { items: [{id, brand, product_code}, ...] }
       → { suggestions: [{item_id, source_quote_id, hs_code, customs_duty, ...}] }

POST   /api/customs/items/{item_id}/expenses
DELETE /api/customs/items/expenses/{id}

POST   /api/customs/quotes/{quote_id}/expenses
DELETE /api/customs/quotes/expenses/{id}

POST   /api/customs/complete  { invoice_id, accept_autofill_bulk: bool, certificates_checked: bool }
POST   /api/customs/acknowledge-review  { invoice_id }
```

### 6.3 Workflow

```
POST /api/workflow/assign-logistics  { quote_id }   — triggers existing service
POST /api/workflow/assign-customs    { quote_id }   — new (least-loaded)
POST /api/workflow/reassign  { invoice_id, type: 'logistics'|'customs', new_user_id }
     — head-only, for unassigned-fallback
```

### 6.4 Notes

```
GET    /api/notes?entity_type=<str>&entity_id=<uuid>
POST   /api/notes
PATCH  /api/notes/{id}
DELETE /api/notes/{id}
```

RLS enforces `visible_to` filtering on GET.

### 6.5 Table views

```
GET    /api/table-views?table_key=<str>
POST   /api/table-views
PATCH  /api/table-views/{id}
DELETE /api/table-views/{id}
```

### 6.6 Admin routing — existing + new tab

Extend existing admin routing endpoints (from `services/route_logistics_assignment_service.py`):

```
GET    /api/admin/routing/logistics           — list all patterns
POST   /api/admin/routing/logistics           — create
PATCH  /api/admin/routing/logistics/{id}      — update
DELETE /api/admin/routing/logistics/{id}      — remove
GET    /api/admin/routing/logistics/coverage  — uncovered countries + unassigned invoice count
```

(Customs tab optional — see §7.4; 1-2 customs users doesn't need routing config UI yet.)

---

## 7. UI Structure

### 7.1 New routes (Next.js)

```
frontend/src/app/(app)/
├── workspace/
│   ├── logistics/page.tsx       — "Мои заявки" + head tabs
│   └── customs/page.tsx         — analogous
├── admin/routing/page.tsx       — existing, add Logistics + Customs tabs
└── quotes/[id]/page.tsx         — existing, rework logistics-step + customs-step content
```

### 7.2 New features (FSD)

```
frontend/src/features/
├── workspace-logistics/         — workspace page widgets
├── workspace-customs/
├── route-constructor/           — timeline + segment editor
├── customs-autofill/            — banner + bulk-accept modal
├── admin-routing-logistics/     — patterns table + create panel
├── entity-notes/                — shared notes component
└── table-views/                 — column visibility + saved views
```

### 7.3 New entities

```
frontend/src/entities/
├── route-segment/               — queries, mutations, types
├── route-template/
├── operational-event/
├── customs-autofill-suggestion/
├── customs-expense/
├── entity-note/
├── table-view/
└── (existing: invoice, quote, deal, customer, supplier, ...)
```

### 7.4 Wireframe references

Reference wireframes committed to `docs/superpowers/wireframes/2026-04-22-logistics-customs/` (4 final screens, HTML with inline CSS matching the design system):

| # | File | Screen |
|---|------|--------|
| 1 | `01-workspace.html` | `/workspace/logistics` — assigned invoices, SLA timers, head tabs |
| 2 | `02-route-constructor.html` | Route Constructor — drag&drop timeline + details panel |
| 3 | `03-customs-table.html` | Customs handsontable + autofill bulk-accept |
| 4 | `04-admin-routing.html` | `/admin/routing` — Logistics tab + unassigned inbox |

Draft/iteration wireframes available at `.superpowers/brainstorm/72929-1776845947/content/` (gitignored).

---

## 8. Sub-project breakdown (19 items)

Each sub-project is an independently shippable PR unless marked "coord" (needs coordination with `/procurement` branch).

### Wave 1 (P0) — foundation, 7 sub-projects

| ID | Name | Summary | Depends on |
|----|------|---------|-----------|
| **A** | Locations → `location_type` | Add enum column, backfill from is_hub/is_customs_point, validation | — |
| **B** | Customs columns cleanup | DROP customs_ds_sgr, DROP customs_marking, RENAME psn→psm, RUB disclaimer | Handsontable update |
| **F** | Customs expenses | New `customs_item_expenses` + `customs_quote_expenses` tables + UI below handsontable | B |
| **H** | Logistics route constructor | New segments model + expenses + operational events + templates + timeline UI + calc adapter view | A |
| **I** | Logistics client-info + entity_notes | Rename labels, add страна/responsible fields, full `entity_notes` implementation with RBAC | — |
| **J** | Logistics RBAC + head_of_customs role | Hide finance tab from logistics role, add head_of_customs, update permission checks | migration for role |
| **N** | Workspace pages | `/workspace/logistics` and `/workspace/customs`, assigned-based, Неназначенные fallback | timers (invoices alters) |

### Wave 2 (P1) — UX improvements, 6 sub-projects

| ID | Name | Summary | Depends on |
|----|------|---------|-----------|
| **C** | Customs row modal | "Развёрнутый ввод" expand button per row | B |
| **D** | Customs autofill | LATERAL join endpoint + UI highlight + bulk-accept modal with cert-checkbox | B |
| **K** | Logistics cargo items UX | Readability fixes, numbering, currency display | I |
| **L** | Logistics invoice-comment | entity_notes on invoice (comment to procurement) | I |
| **O** | SLA timers + Telegram pings | 24h before deadline + after overdue → head | N, existing telegram_service |
| **S** | Table views | Generic `table_views` + column visibility UI for customs handsontable | B |

### Wave 3 (P2) — coordinated with `/procurement` branch

| ID | Name | Summary | Coord |
|----|------|---------|-------|
| **E** | Customs sync (smart delta trigger) | DB trigger on invoice_items | yes — procurement writes invoice_items |
| **G** | Suppliers contacts with roles | Contact list per supplier with role (procurement/logistics/finance) | **IN procurement branch** |
| **M** | Logistics auto-assignment admin UI | `/admin/routing` → Logistics + Customs tabs, patterns table, create panel | yes — extending existing procurement routing UI |
| **P** | Analytics "кто сколько отработал" | Dashboard for heads, queries on completed_at/assigned_at | — |
| **Q** | Hub/warehouse registry UI | Extend locations UI with location_type filtering | A |

### Wave 4 (deferred)

| ID | Name | Status |
|----|------|--------|
| **R** | Carriers registry | Deferred — user said "сейчас можно пропустить" |
| — | External/internal МОЛ split | Deferred to execution phase (beyond pricing phase) |

---

## 9. Cross-Cutting Concerns

### 9.1 RBAC

| Role | workspace/logistics | workspace/customs | admin/routing | finance tab |
|------|---------------------|-------------------|---------------|-------------|
| `sales` | — | — | — | — |
| `procurement` | — | — | — | — |
| `logistics` | "Мои", "Завершённые" | — | — | **hidden** (sub-project J) |
| `customs` | — | "Мои", "Завершённые" | — | **hidden** |
| `head_of_logistics` | + "Неназначенные", "Все заявки", "Маршруты" | — | Logistics tab | hidden |
| `head_of_customs` | — | + "Неназначенные", "Все заявки" | Customs tab (if enabled) | hidden |
| `admin` | all tabs | all tabs | all tabs | — |
| `finance` | — | — | — | full |
| `top_manager` | read all | read all | read | full |

#### `entity_notes` visibility rules

- Customer-level note (`entity_type='customer'`, `visible_to=['logistics','customs','sales','admin','top_manager']`) — read by listed roles, write by `logistics`, `customs`, `admin`.
- Quote-level note from MOZ/MOП addressed to logistics (`visible_to=['logistics','customs','head_of_logistics']`) — read by any named role, write only by author's role.
- Invoice-level note from логиста для КП (`visible_to=['procurement','head_of_procurement']`) — visible to procurement for feedback loop.

### 9.2 Observability

- All new FastAPI endpoints emit structured JSON logs (ISO 8601 UTC, correlation_id, level).
- Key events for Telegram push:
  - `logistics.assigned` → notify assignee
  - `logistics.deadline_warning_24h` → notify assignee
  - `logistics.overdue` → notify assignee + head_of_logistics
  - `logistics.smart_delta_triggered` → notify assignee (optional, debounced)
  - Analogous for customs
- Sentry alerts on: assign_*_to_invoices returning errors (silent fails historically — see memory FB-260410-110450)
- Stats queries (sub-project P): time-in-queue (created_at→assigned_at), time-in-work (assigned_at→completed_at), completion rate per user.

### 9.3 Backwards compatibility

**Breaking changes accepted:**
- `logistics_stages` data not migrated — existing in-progress deals reset to new model. Per memory `feedback_oneshot_migrations_when_engine_locked.md` pattern.
- `customs_ds_sgr` and `customs_marking` dropped — backfill into `license_*` structured columns + `customs_honest_mark` where possible before DROP.

**Non-breaking:**
- Old `is_hub` / `is_customs_point` booleans preserved alongside `location_type` (dropped in 6 months).
- Old `plan_fact_items.logistics_stage_id` values remain readable (for historical reports) but new writes go through view.
- `route_logistics_assignments` schema unchanged — only adds UI.

### 9.4 Performance

- `entity_notes` polymorphic — covered by `(entity_type, entity_id)` index.
- `logistics_route_segments` — `(invoice_id)` index for per-invoice loads, most common query.
- Customs autofill — `idx_quote_items_brand_product_code_for_autofill` partial index (only rows with `hs_code IS NOT NULL`).
- LATERAL join performance tested on projected data volume (~50k `quote_items` historical): single query returns 10-20 suggestions in <100ms.
- Workspace queries — aggregate count by `(assigned_*_user, *_completed_at IS NULL)` — indexed partial.

### 9.5 Migration strategy

**Big-bang per sub-project.** Not expand-contract. Reasons:
1. Calc engine is locked, and new view (v_logistics_plan_fact_items) doesn't coexist cleanly with old `logistics_stage_id` references.
2. User policy on calc-engine-impacting changes: `feedback_oneshot_migrations_when_engine_locked.md`.
3. Active deals in `pending_logistics` are few (verify before migration); cost of re-estimation is lower than cost of maintaining dual write-paths.

**Rollback:** each migration reversible (DOWN scripts written). Data loss possible on DOWN of H (segments → old stages) — documented.

### 9.6 Testing

- Per sub-project: unit tests (service layer), integration tests (API), E2E for critical flows (Playwright):
  - Logistics assignment end-to-end
  - Customs autofill bulk-accept
  - Smart delta trigger effects
- Regression: existing `test_logistics_service.py`, `test_logistics_invoice_assignment.py` kept; adapter tests added for v_logistics_plan_fact_items matching old behaviour on simple cases.
- Coverage target: 80% on new code.

---

## 10. Coordination with `/procurement` parallel branch

Three sub-projects require explicit coord to avoid merge conflicts:

| ID | Area of conflict | Resolution |
|----|------------------|------------|
| **E** | `invoice_items` trigger | Decide trigger ownership. Likely lives in this branch (domain = logistics/customs reaction), procurement branch adds `pickup_country` validation at write-site. |
| **G** | Suppliers entity | **Move to procurement branch entirely.** They add `supplier_contacts (supplier_id, name, email, role)` table. We don't touch supplier schema. |
| **M** | Admin routing UI | Existing procurement routing page must not be broken. We only **add** tabs, not restructure. Shared component: tab host. |

Sync cadence: before each merge to main on either side, both branches diff shared files (`invoice_items`, `admin/routing/page.tsx`, `suppliers` schema) with rebase plan.

---

## 11. Open UX Items (recommendations — reviewed post-spec)

These are not architectural blockers; decisions documented, reviewer may change during spec review or Wave 1 PR review.

### 11.1 Customs "Пошлина" column composition

**Recommendation:** single column `customs_duty` with composite UI — numeric value + inline chip `%` / `₽/кг` / `₽/шт`. Underlying storage: two columns (`customs_duty` pct, `customs_duty_per_kg` decimal) as today, UI chooses which to populate based on chip.

**Alternative:** three parallel columns visible (current state pre-B).

**Why recommendation:** UX simpler, data model unchanged. Chip-switching validates only one of two values is set.

### 11.2 `customs_item_expenses` vs JSON on `quote_items`

**Recommendation:** separate table (as in §5.1).

**Why:** auditable (`created_by`, `created_at` per expense), queryable ("all expenses > 5000 this month"), no migration pain if schema evolves. JSON on row would require re-writing whole row on any edit.

### 11.3 Customs row "expand" modal

**Recommendation:** per-row icon button (↗ in actions col as seen in wireframe 05) opens modal with **all** fields (including hidden-by-table-view columns + item-level expenses). Saves back to same `quote_items` + `customs_item_expenses`.

**Why:** Handsontable can't natively show large textareas (нотификация, причина запрета) in a cell. Modal fills this gap without breaking the primary excel-like flow.

---

## 12. Design system application

Before Wave 1 UI PRs start, run **`frontend-design` skill** over the 4 reference wireframes (02/04/05/06) to:
- Translate HTML mocks into shadcn/ui components (Button, Card, Table, Dialog, Select, Checkbox, Tabs, Sheet).
- Apply exact design system tokens from `design-system.md` (warm stone palette, Plus Jakarta Sans, radius 6/8/12, comfortable density).
- Validate anti-patterns absent (no `transition: all`, no emoji icons except country flags, no cold grays).
- Generate reusable component inventory (e.g. `LocationChip`, `SlaTimerBadge`, `SegmentCard`, `AutofillBanner`, `EntityNotesPanel`, `TableViewsDropdown`).

Output of `frontend-design` pass → per-component spec files in `frontend/docs/components/` which feed writing-plans implementation tasks.

---

## 13. Next steps

After reviewer approval of this spec:

1. **Apply `frontend-design` skill** on wireframes 02/04/05/06 (visual polish + component mapping).
2. **Invoke `writing-plans` skill** to turn sub-projects A-R into a scheduled implementation plan with ClickUp task breakdown.
3. **Execute Wave 1 via `/lean-tdd`** — 7 sub-projects in parallel where possible, otherwise sequential based on file-level conflicts.
4. **Graphify update** after each merged sub-project — `graphify update .` (AST-only, no LLM cost) to keep knowledge graph fresh.

Sync point with `/procurement` branch before E/G/M touched.

---

## 14. References

### Internal
- `services/route_logistics_assignment_service.py` — existing auto-assign logic (Wave 3 sub-project M wraps it)
- `services/workflow_service.py:assign_logistics_to_invoices()` — existing
- `services/logistics_service.py` — old 7-stage model, deprecated after Wave 1 H
- `migrations/163_create_logistics_stages_table.sql` — old model (superseded)
- `migrations/024_create_locations_table.sql` — locations (extended with location_type)
- `migrations/197_add_logistics_assignment_to_invoices.sql` — invoice.assigned_logistics_user
- `frontend/src/features/quotes/ui/customs-step/customs-handsontable.tsx` — current 26-col customs table (refactored in B + S)
- `design-system.md` — UI tokens source of truth

### Historical context
- memory/feedback_oneshot_migrations_when_engine_locked.md — migration strategy for calc-engine-touching changes
- memory/feedback_lean_tdd_workflow.md — implementation workflow
- memory/project_phase_5c_invoice_items.md — invoice_items + invoice_item_coverage architecture (procurement-side)
- memory/project_phase_5d_legacy_refactor.md — phase 5d legacy column refactor

### ТЗ
- FB-260415-190332-ee01 (logistics, stored in Supabase `feedback_items`)
- WhatsApp messages 2026-04-16 10:45-11:32 (customs TZ, transcribed above in §3)

### Wireframes
See §7.4. Active reference set: screens 02, 04, 05, 06.

---

## 15. Review log

| Date | Reviewer | Notes |
|------|----------|-------|
| 2026-04-22 | Andrey | Pending |

---

*End of design spec.*
