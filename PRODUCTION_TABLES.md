# OneStack - Таблицы в Production БД

> **Дата проверки:** 2026-01-20
> **Всего таблиц OneStack:** 45
> **Схема:** public (планируется переход на `kvota`)

---

## ✅ Таблицы в Production (45 штук)

### 1️⃣ Коммерческие Предложения (Quotes) - 10 таблиц

```
✓ quotes
✓ quote_items
✓ quote_versions
✓ quote_approval_history
✓ quote_calculation_products_versioned
✓ quote_calculation_results
✓ quote_calculation_summaries
✓ quote_calculation_summaries_versioned
✓ quote_calculation_variables
✓ quote_export_settings
✓ quote_timeline_events
✓ quote_workflow_transitions
```

### 2️⃣ План-Факт (Finance) - 7 таблиц

```
✓ plan_fact_categories
✓ plan_fact_items
✓ plan_fact_financing_recalculated
✓ plan_fact_logistics_stages
✓ plan_fact_permissions
✓ plan_fact_products
✓ plan_fact_sections
```

### 3️⃣ Организации - 5 таблиц

```
✓ organizations
✓ organization_members
✓ organization_currency_history
✓ organization_exchange_rates
✓ organization_invitations
✓ organization_workflow_settings
```

### 4️⃣ Клиенты - 4 таблицы

```
✓ customers
✓ customer_contacts
✓ customer_contracts
✓ customer_delivery_addresses
```

### 5️⃣ Поставщики - 2 таблицы

```
✓ suppliers
✓ supplier_countries
```

### 6️⃣ Спецификации и Сделки - 3 таблицы

```
✓ specifications
✓ specification_exports
✓ deals
```

### 7️⃣ Workflow и Роли - 5 таблиц

```
✓ roles
✓ user_roles
✓ brand_assignments
✓ approvals
✓ workflow_transitions
```

### 8️⃣ Уведомления - 2 таблицы

```
✓ notifications
✓ telegram_users
```

### 9️⃣ Компании - 2 таблицы

```
✓ seller_companies
✓ purchasing_companies
```

### 🔟 Настройки и Справочники - 2 таблицы

```
✓ calculation_settings
✓ exchange_rates
```

### 1️⃣1️⃣ Продукты - 1 таблица

```
? products - НЕ НАЙДЕНА! (нужна базовая таблица)
```

---

## ❌ Таблицы из миграций, которых НЕТ в Production (9+ таблиц)

### Миграции 018-034 (Supply Chain v3.0)

```
❌ buyer_companies          (миграция 019)
❌ bank_accounts            (миграция 023)
❌ locations                (миграция 024)
❌ brand_supplier_assignments (миграция 025)
❌ route_logistics_assignments (миграция 027)
❌ supplier_invoices        (миграция 032)
❌ supplier_invoice_items   (миграция 033)
❌ supplier_invoice_payments (миграция 034)
```

### Расширения таблиц

```
⚠️ quotes - возможно не все поля из миграции 028
⚠️ quote_items - возможно не все поля из миграций 029-031
⚠️ specifications - возможно не все поля из миграции 036
⚠️ deals - возможно не все поля из миграции 037
```

---

## 🎯 План действий

### Шаг 1: Создать схему `kvota`

```sql
CREATE SCHEMA kvota;
GRANT USAGE ON SCHEMA kvota TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA kvota TO authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA kvota GRANT ALL ON TABLES TO authenticated;
```

### Шаг 2: Перенести существующие 45 таблиц

```sql
-- Quotes
ALTER TABLE quotes SET SCHEMA kvota;
ALTER TABLE quote_items SET SCHEMA kvota;
ALTER TABLE quote_versions SET SCHEMA kvota;
-- ... и так далее для всех 45 таблиц
```

### Шаг 3: Применить недостающие миграции

```bash
# Применить миграции 018-034
cd migrations
psql -U postgres -d postgres < 018_create_suppliers_table.sql  # (уже есть suppliers, пропустить)
psql -U postgres -d postgres < 019_create_buyer_companies_table.sql
psql -U postgres -d postgres < 023_create_bank_accounts_table.sql
psql -U postgres -d postgres < 024_create_locations_table.sql
psql -U postgres -d postgres < 025_create_brand_supplier_assignments_table.sql
psql -U postgres -d postgres < 027_create_route_logistics_assignments_table.sql
psql -U postgres -d postgres < 032_create_supplier_invoices_table.sql
psql -U postgres -d postgres < 033_create_supplier_invoice_items_table.sql
psql -U postgres -d postgres < 034_create_supplier_invoice_payments_table.sql
```

### Шаг 4: Обновить код backend

```python
# В config/settings.py или database.py
SUPABASE_DB_SCHEMA = "kvota"

# В создании клиента Supabase
supabase = create_client(
    supabase_url=settings.SUPABASE_URL,
    supabase_key=settings.SUPABASE_KEY,
    options=ClientOptions(
        schema="kvota",
        # или в строке подключения:
        # postgrest_client_timeout=10,
        # search_path="kvota,public"
    )
)
```

### Шаг 5: Обновить .env

```bash
DATABASE_SCHEMA=kvota
SUPABASE_SCHEMA=kvota
```

---

## 📊 Дополнительные таблицы в Production

Эти таблицы есть в production, но отсутствуют в папке `migrations/`:

```
+ quote_approval_history
+ quote_calculation_products_versioned
+ quote_calculation_results
+ quote_calculation_summaries
+ quote_calculation_summaries_versioned
+ quote_calculation_variables
+ quote_export_settings
+ quote_timeline_events
+ quote_workflow_transitions
+ specification_exports
+ organization_currency_history
+ organization_exchange_rates
+ organization_invitations
+ organization_workflow_settings
+ plan_fact_financing_recalculated
+ plan_fact_logistics_stages
+ plan_fact_permissions
+ plan_fact_products
+ plan_fact_sections
+ supplier_countries
+ purchasing_companies
+ calculation_settings
+ customer_delivery_addresses
```

**Действие:** Нужно создать дамп этих таблиц и добавить в папку миграций.

---

## 🚨 Важные замечания

1. **Базовая таблица `products` отсутствует** - нужно создать
2. **22 таблицы** существуют в production, но нет миграций - нужно задокументировать
3. **8 миграций** (018-034) не применены - нужно применить с учетом схемы `kvota`
4. После переноса в схему `kvota` нужно обновить все RLS политики
5. Нужно обновить search_path в PostgreSQL для схемы kvota

---

## 🔄 Скрипт переноса всех таблиц

```sql
-- Создать схему
CREATE SCHEMA IF NOT EXISTS kvota;
GRANT USAGE ON SCHEMA kvota TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA kvota TO authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA kvota TO authenticated;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA kvota TO authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA kvota GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA kvota GRANT ALL ON SEQUENCES TO authenticated;

-- Перенести все 45 таблиц OneStack
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
        AND (
            tablename LIKE 'quote%'
            OR tablename LIKE 'plan_fact%'
            OR tablename LIKE 'organization%'
            OR tablename LIKE 'customer%'
            OR tablename LIKE 'supplier%'
            OR tablename LIKE 'specification%'
            OR tablename IN (
                'approvals', 'workflow_transitions', 'roles', 'user_roles',
                'brand_assignments', 'deals', 'notifications', 'telegram_users',
                'seller_companies', 'purchasing_companies', 'calculation_settings',
                'exchange_rates'
            )
        )
    ) LOOP
        EXECUTE format('ALTER TABLE public.%I SET SCHEMA kvota', r.tablename);
        RAISE NOTICE 'Moved table: %', r.tablename;
    END LOOP;
END $$;
```

---

**Создано:** 2026-01-20
**Следующий шаг:** Создать миграцию для переноса в схему `kvota`
