-- Customer Journey Map — seed flows (Task 28).
--
-- Migration 500 (500_journey_map.sql) defined the table kvota.journey_flows;
-- this script loads the initial four flows that Req 18.8 mandates.
--
-- This is a SEED script, NOT a schema migration. Do NOT register it in the
-- kvota.migrations tracking table — it carries data, not DDL, and may be
-- re-run whenever the curated flow content needs to be refreshed.
--
-- Idempotent: every flow INSERT uses ON CONFLICT (slug) DO UPDATE so re-runs
-- update the existing rows rather than error on the UNIQUE slug constraint.
--
-- Source: docs/superpowers/mockups/journey/flows.js (Claude Design mockup).
-- Node ids below are taken from frontend/public/journey-manifest.json — every
-- one resolves to an existing route at the time this seed shipped. If a route
-- is later renamed the flows view degrades gracefully per Req 18.10
-- ("Узел недоступен" warning on missing node_id).
--
-- Apply with:
--   ssh beget-kvota "docker exec -i supabase-db psql -U postgres -d postgres" \
--     < scripts/seed-journey-flows.sql

SET search_path TO kvota, public;

-- ---------------------------------------------------------------------------
-- Flow 1 — sales-full: Sales lead → quote control handoff.
-- ---------------------------------------------------------------------------
INSERT INTO kvota.journey_flows
    (slug, title, role, persona, description, est_minutes, steps, display_order, is_archived)
VALUES
    (
        'sales-full',
        'Sales: лид → одобрение КП',
        'sales',
        'А. Петров · менеджер продаж',
        'Полный путь от первого контакта с клиентом до отправки КП на контроль.',
        12,
        '[
            {"node_id": "app:/dashboard",                   "action": "Открыть обзор",         "note": "Проверка входящих задач на день"},
            {"node_id": "app:/customers",                   "action": "Найти клиента в реестре", "note": "Фильтр по статусу «активный»"},
            {"node_id": "app:/customers/[id]",              "action": "Открыть карточку клиента", "note": "Проверка истории заказов и лимита"},
            {"node_id": "app:/quotes",                      "action": "Создать новое КП",       "note": "Кнопка «+ КП» в шапке реестра"},
            {"node_id": "app:/quotes/[id]",                 "action": "Заполнить позиции",      "note": "Добавить SKU, указать количество"},
            {"node_id": "app:/quotes/[id]/cost-analysis",   "action": "Проверить себестоимость", "note": "Только для head_of_sales"},
            {"node_id": "app:/quotes/[id]",                 "action": "Отправить на контроль",  "note": "Статус → pending_quote_control"},
            {"node_id": "app:/tasks",                       "action": "Вернуться к задачам",    "note": "Ожидание решения контроллёра"}
        ]'::jsonb,
        1,
        false
    )
ON CONFLICT (slug) DO UPDATE SET
    title         = EXCLUDED.title,
    role          = EXCLUDED.role,
    persona       = EXCLUDED.persona,
    description   = EXCLUDED.description,
    est_minutes   = EXCLUDED.est_minutes,
    steps         = EXCLUDED.steps,
    display_order = EXCLUDED.display_order,
    is_archived   = EXCLUDED.is_archived,
    updated_at    = now();

-- ---------------------------------------------------------------------------
-- Flow 2 — procurement-flow: Procurement receives items → buys from supplier.
-- ---------------------------------------------------------------------------
INSERT INTO kvota.journey_flows
    (slug, title, role, persona, description, est_minutes, steps, display_order, is_archived)
VALUES
    (
        'procurement-flow',
        'Procurement: распределение → закупка',
        'procurement',
        'С. Голиков · закупщик',
        'Получение позиций после одобрения КП, работа с поставщиками.',
        8,
        '[
            {"node_id": "app:/procurement/distribution", "action": "Получить позиции",     "note": "Автораспределение по бренду"},
            {"node_id": "app:/procurement/kanban",       "action": "Открыть канбан",       "note": "Новые карточки в колонке «RFQ»"},
            {"node_id": "app:/suppliers/[id]",           "action": "Выбрать поставщика",   "note": "Сравнение цен и сроков"},
            {"node_id": "app:/quotes/[id]",              "action": "Внести цены закупки",  "note": "В валюте поставщика"}
        ]'::jsonb,
        2,
        false
    )
ON CONFLICT (slug) DO UPDATE SET
    title         = EXCLUDED.title,
    role          = EXCLUDED.role,
    persona       = EXCLUDED.persona,
    description   = EXCLUDED.description,
    est_minutes   = EXCLUDED.est_minutes,
    steps         = EXCLUDED.steps,
    display_order = EXCLUDED.display_order,
    is_archived   = EXCLUDED.is_archived,
    updated_at    = now();

-- ---------------------------------------------------------------------------
-- Flow 3 — qa-onboarding: Junior QA's 5 key screens (Req 17.8 acceptance).
-- ---------------------------------------------------------------------------
INSERT INTO kvota.journey_flows
    (slug, title, role, persona, description, est_minutes, steps, display_order, is_archived)
VALUES
    (
        'qa-onboarding',
        'QA onboarding: 5 ключевых экранов',
        'spec_controller',
        'Junior QA · первая неделя',
        'Минимальный набор для проверки основных потоков после онбординга.',
        15,
        '[
            {"node_id": "app:/quotes",                   "action": "Реестр КП",          "note": "6 пинов — фильтры, сортировка, действия"},
            {"node_id": "app:/quotes/[id]",              "action": "Карточка КП",        "note": "22 пина — весь workflow"},
            {"node_id": "app:/customers/[id]",           "action": "Карточка клиента",   "note": "14 пинов — вкладки, CRM"},
            {"node_id": "app:/procurement/distribution", "action": "Распределение",      "note": "7 пинов"},
            {"node_id": "app:/finance",                  "action": "Контроль платежей",  "note": "10 пинов"}
        ]'::jsonb,
        1,
        false
    )
ON CONFLICT (slug) DO UPDATE SET
    title         = EXCLUDED.title,
    role          = EXCLUDED.role,
    persona       = EXCLUDED.persona,
    description   = EXCLUDED.description,
    est_minutes   = EXCLUDED.est_minutes,
    steps         = EXCLUDED.steps,
    display_order = EXCLUDED.display_order,
    is_archived   = EXCLUDED.is_archived,
    updated_at    = now();

-- ---------------------------------------------------------------------------
-- Flow 4 — finance-monthly: Finance month-end reconciliation.
-- ---------------------------------------------------------------------------
INSERT INTO kvota.journey_flows
    (slug, title, role, persona, description, est_minutes, steps, display_order, is_archived)
VALUES
    (
        'finance-monthly',
        'Finance: месячное закрытие',
        'finance',
        'Н. Соколова · финансист',
        'Ежемесячный контроль платежей и календарь.',
        6,
        '[
            {"node_id": "app:/finance",             "action": "Открыть контроль платежей", "note": "Сверка входящих и исходящих"},
            {"node_id": "app:/payments/calendar",   "action": "Календарь на месяц",        "note": "Планирование cash-flow"},
            {"node_id": "app:/dashboard",           "action": "Сверить с обзором",         "note": "Итоговые метрики за период"}
        ]'::jsonb,
        1,
        false
    )
ON CONFLICT (slug) DO UPDATE SET
    title         = EXCLUDED.title,
    role          = EXCLUDED.role,
    persona       = EXCLUDED.persona,
    description   = EXCLUDED.description,
    est_minutes   = EXCLUDED.est_minutes,
    steps         = EXCLUDED.steps,
    display_order = EXCLUDED.display_order,
    is_archived   = EXCLUDED.is_archived,
    updated_at    = now();
