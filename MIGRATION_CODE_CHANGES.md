# Изменения в коде для работы со схемой kvota

> **Дата:** 2026-01-20
> **Цель:** Перевести приложение на работу с PostgreSQL схемой `kvota`
> **Затронутые компоненты:** Backend (FastAPI), Frontend (Next.js + Supabase client)

---

## 📋 Оглавление

1. [Backend изменения](#backend-изменения)
2. [Frontend изменения](#frontend-изменения)
3. [Переменные окружения](#переменные-окружения)
4. [Проверка после миграции](#проверка-после-миграции)

---

## Backend изменения

### 1. Настройка подключения к базе данных

#### Файл: `backend/app/config/database.py` (или settings.py)

**До:**
```python
from supabase import create_client, Client

supabase: Client = create_client(
    supabase_url=settings.SUPABASE_URL,
    supabase_key=settings.SUPABASE_SERVICE_ROLE_KEY
)
```

**После:**
```python
from supabase import create_client, Client
from postgrest.base_request_builder import APIResponse

# Создаем клиента с указанием схемы
supabase: Client = create_client(
    supabase_url=settings.SUPABASE_URL,
    supabase_key=settings.SUPABASE_SERVICE_ROLE_KEY,
    options={
        "schema": "kvota",  # Указываем схему
        "headers": {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY
        }
    }
)
```

### 2. Альтернативный способ - через asyncpg/psycopg

Если используете прямое подключение к PostgreSQL (asyncpg или psycopg):

#### Файл: `backend/app/db/session.py`

**До:**
```python
DATABASE_URL = "postgresql://user:password@host:5432/db"

engine = create_async_engine(DATABASE_URL)
```

**После:**
```python
DATABASE_URL = "postgresql://user:password@host:5432/db?options=-c search_path=kvota,public"

# Или с явным указанием search_path:
engine = create_async_engine(
    DATABASE_URL,
    connect_args={
        "server_settings": {"search_path": "kvota, public"}
    }
)
```

### 3. Обновление SQL запросов (если есть явные схемы)

#### Файл: `backend/app/services/*.py`

**До:**
```python
# Прямой SQL
query = "SELECT * FROM quotes WHERE id = $1"

# Или через Supabase
result = supabase.table('quotes').select('*').execute()
```

**После:**
```python
# Вариант 1: Без явного указания схемы (рекомендуется)
query = "SELECT * FROM quotes WHERE id = $1"  # search_path найдет в kvota
result = supabase.table('quotes').select('*').execute()  # схема указана в клиенте

# Вариант 2: С явным указанием схемы (если нужно)
query = "SELECT * FROM kvota.quotes WHERE id = $1"
```

### 4. SQLAlchemy модели (если используются)

#### Файл: `backend/app/models/quote.py`

**До:**
```python
class Quote(Base):
    __tablename__ = "quotes"

    id = Column(UUID(as_uuid=True), primary_key=True)
    # ...
```

**После:**
```python
class Quote(Base):
    __tablename__ = "quotes"
    __table_args__ = {'schema': 'kvota'}  # Добавить схему

    id = Column(UUID(as_uuid=True), primary_key=True)
    # ...
```

### 5. Alembic миграции (если используются)

#### Файл: `alembic/env.py`

**До:**
```python
target_metadata = Base.metadata
```

**После:**
```python
target_metadata = Base.metadata

# В функции run_migrations_online():
def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Устанавливаем search_path
        connection.execute(text("SET search_path TO kvota, public"))

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema='kvota'  # Alembic версии тоже в kvota
        )

        with context.begin_transaction():
            context.run_migrations()
```

---

## Frontend изменения

### 1. Supabase клиент

#### Файл: `frontend/lib/supabase.ts` или `frontend/utils/supabase.ts`

**До:**
```typescript
import { createClient } from '@supabase/supabase-js'

export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)
```

**После:**
```typescript
import { createClient } from '@supabase/supabase-js'

export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  {
    db: {
      schema: 'kvota'  // Указываем схему
    }
  }
)
```

### 2. Запросы к базе данных

#### Файлы: `frontend/app/api/**/*.ts`, `frontend/lib/queries/*.ts`

**До:**
```typescript
// Запросы без изменений
const { data, error } = await supabase
  .from('quotes')
  .select('*')
```

**После:**
```typescript
// Запросы остаются БЕЗ изменений!
// Схема указана при создании клиента
const { data, error } = await supabase
  .from('quotes')
  .select('*')
```

### 3. TypeScript типы (если есть кодогенерация)

Если используете автогенерацию типов из Supabase:

```bash
# Обновить типы с учетом новой схемы
npx supabase gen types typescript --project-id YOUR_PROJECT_ID --schema kvota > types/database.ts
```

---

## Переменные окружения

### Backend: `.env`

**Добавить:**
```bash
# Database schema
DATABASE_SCHEMA=kvota
POSTGRES_SCHEMA=kvota

# Supabase (существующие переменные остаются)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_ANON_KEY=your-anon-key
```

### Frontend: `.env.local`

```bash
# Схема не нужна в .env - указывается в коде
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

---

## Проверка после миграции

### 1. Проверка подключения к БД

```python
# backend/scripts/test_connection.py
from app.config.database import supabase

def test_connection():
    try:
        # Попробуем получить таблицы
        result = supabase.table('quotes').select('id').limit(1).execute()
        print(f"✅ Connection successful! Found {len(result.data)} quotes")
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    test_connection()
```

### 2. Проверка SQL запросов

```sql
-- Подключиться к базе данных
psql -U postgres -d postgres

-- Проверить search_path
SHOW search_path;

-- Установить search_path
SET search_path TO kvota, public;

-- Проверить доступность таблиц
SELECT COUNT(*) FROM quotes;
SELECT COUNT(*) FROM customers;
SELECT COUNT(*) FROM suppliers;
```

### 3. Проверка RLS политик

```sql
-- Проверить, что RLS политики работают
SELECT tablename, policyname
FROM pg_policies
WHERE schemaname = 'kvota';
```

### 4. Проверка функций

```sql
-- Проверить, что функции перенесены
SELECT n.nspname as schema, p.proname as function
FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
WHERE n.nspname = 'kvota';
```

---

## Откат изменений (если что-то пошло не так)

### Вернуть таблицы обратно в public:

```sql
-- Откат миграции 101
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'kvota'
    ) LOOP
        EXECUTE format('ALTER TABLE kvota.%I SET SCHEMA public', r.tablename);
        RAISE NOTICE 'Moved table back: %', r.tablename;
    END LOOP;
END $$;
```

### Откатить изменения в коде:

1. Убрать `schema: 'kvota'` из настроек клиентов
2. Убрать `search_path` из строки подключения
3. Откатить коммит в git

---

## Частые ошибки и решения

### Ошибка: "relation does not exist"

**Причина:** search_path не включает схему kvota

**Решение:**
```python
# Явно установить search_path при подключении
connection.execute("SET search_path TO kvota, public")
```

### Ошибка: "permission denied for schema kvota"

**Причина:** Роли не имеют прав на схему

**Решение:**
```sql
GRANT USAGE ON SCHEMA kvota TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA kvota TO authenticated;
```

### Ошибка: RLS политики не работают

**Причина:** После переноса нужно обновить ссылки в политиках

**Решение:**
```sql
-- Пересоздать политики для критичных таблиц
-- Обычно PostgreSQL обновляет ссылки автоматически
```

---

## Чек-лист перед применением к production

- [ ] Миграция 100 (создание схемы) протестирована локально
- [ ] Миграция 101 (перенос таблиц) протестирована локально
- [ ] Backend код обновлен и протестирован
- [ ] Frontend код обновлен и протестирован
- [ ] .env файлы обновлены
- [ ] Все тесты проходят
- [ ] RLS политики работают
- [ ] Функции перенесены и работают
- [ ] Создан backup production базы
- [ ] План отката подготовлен

---

## Дополнительные ресурсы

- [PostgreSQL Schemas Documentation](https://www.postgresql.org/docs/current/ddl-schemas.html)
- [Supabase Schema Support](https://supabase.com/docs/guides/database/schemas)
- [PostgREST Schema Isolation](https://postgrest.org/en/stable/references/schema_isolation.html)

---

**Создано:** 2026-01-20
**Версия:** 1.0
**Статус:** Ready for review
