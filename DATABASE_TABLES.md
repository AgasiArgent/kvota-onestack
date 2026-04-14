# База Данных OneStack - Список Таблиц

> **Проект:** kvota/onestack
> **Дата создания:** 2026-01-20
> **Назначение:** Справочник всех таблиц БД для работы с Supabase

---

## 📋 Оглавление

1. [Базовые Таблицы (Supabase)](#базовые-таблицы-supabase)
2. [Система Ролей и Доступа](#система-ролей-и-доступа)
3. [Коммерческие Предложения (КП)](#коммерческие-предложения-кп)
4. [Workflow и Согласования](#workflow-и-согласования)
5. [Спецификации и Сделки](#спецификации-и-сделки)
6. [Supply Chain (Поставщики и Компании)](#supply-chain-поставщики-и-компании)
7. [Клиенты](#клиенты)
8. [Справочники и Локации](#справочники-и-локации)
9. [Счета Поставщиков](#счета-поставщиков)
10. [Финансовый Учет (План-Факт)](#финансовый-учет-план-факт)
11. [Уведомления](#уведомления)

---

## Базовые Таблицы (Supabase)

### 1. `organizations`
**Описание:** Организации (компании) в системе
**Поля:** Название компании, настройки
**Источник:** Базовая таблица Supabase

### 2. `organization_members`
**Описание:** Пользователи в организациях (связь многие-ко-многим)
**Поля:** user_id, organization_id
**Источник:** Базовая таблица Supabase

### 3. `customers`
**Описание:** Клиенты (компании-покупатели)
**Поля:** Название, ИНН, КПП, контактная информация
**Источник:** Базовая таблица приложения

### 4. `products`
**Описание:** Каталог товаров
**Поля:** Название, артикул (SKU), бренд, единица измерения
**Источник:** Базовая таблица приложения

---

## Система Ролей и Доступа

### 5. `roles`
**Описание:** Роли пользователей в системе
**Поля:**
- `id` - UUID
- `code` - Уникальный код роли (sales, procurement, logistics, customs, quote_controller, spec_controller, finance, top_manager, admin)
- `name` - Название роли (рус.)
- `description` - Описание обязанностей

**Миграция:** 001_create_roles_table.sql

### 6. `user_roles`
**Описание:** Назначение ролей пользователям (многие-ко-многим)
**Поля:**
- `user_id` - Ссылка на auth.users
- `organization_id` - Ссылка на organizations
- `role_id` - Ссылка на roles
- `created_by` - Кто назначил роль

**Уникальный ключ:** (user_id, organization_id, role_id)
**Миграция:** 002_create_user_roles_table.sql

### 7. `brand_assignments`
**Описание:** Назначение брендов менеджерам по закупкам
**Поля:**
- `organization_id` - Организация
- `brand` - Название бренда
- `user_id` - Менеджер по закупкам
- `created_by` - Кто создал назначение

**Уникальный ключ:** Один бренд = один менеджер в организации
**Миграция:** 003_create_brand_assignments_table.sql

---

## Коммерческие Предложения (КП)

### 8. `quotes`
**Описание:** Коммерческие предложения (КП)
**Основные поля:**
- `id` - UUID
- `organization_id` - Организация
- `idn` - Уникальный номер КП
- `customer_id` - Клиент
- `workflow_status` - Статус в workflow (draft, pending_procurement, pending_logistics, pending_customs, pending_sales_review, pending_quote_control, pending_approval, approved, sent_to_client, client_negotiation, pending_spec_control, pending_signature, deal, rejected, cancelled)
- `deal_type` - Тип сделки (supply/transit)
- `assigned_logistics_user` - Логист
- `assigned_customs_user` - Менеджер ТО
- `current_version_id` - Текущая версия КП

**Миграция:** 012_extend_quotes_table.sql

### 9. `quote_items`
**Описание:** Позиции в коммерческом предложении
**Основные поля:**
- `quote_id` - Ссылка на quotes
- `product_id` - Ссылка на products
- `quantity` - Количество
- `unit_price` - Цена за единицу
- `brand` - Бренд товара
- `assigned_procurement_user` - Менеджер по закупкам (назначается автоматически по бренду)
- `procurement_status` - Статус закупки (pending, in_progress, completed)
- `hs_code` - Код ТН ВЭД
- `customs_duty` - Таможенная пошлина
- Поля закупки: supplier_city, production_time_days, supplier_payment_terms, payer_company, advance_to_supplier_percent
- Поля логистики: pickup_location_id, delivery_location_id, logistics_period, logistics_cost
- Поля таможни: customs_duty, customs_extra

**Миграция:** 013_extend_quote_items_table.sql, 016_add_procurement_data_fields.sql

### 10. `quote_versions`
**Описание:** Версии коммерческих предложений
**Поля:** Версия КП, дата создания, изменения
**Источник:** Упоминается в full_schema

---

## Workflow и Согласования

### 11. `workflow_transitions`
**Описание:** Аудит-лог переходов статусов КП
**Поля:**
- `quote_id` - КП
- `from_status` - Из какого статуса
- `to_status` - В какой статус
- `actor_id` - Кто изменил
- `actor_role` - Роль актора
- `comment` - Комментарий
- `created_at` - Время перехода

**Миграция:** 004_create_workflow_transitions_table.sql

### 12. `approvals`
**Описание:** Запросы на согласование КП
**Поля:**
- `quote_id` - КП для согласования
- `requested_by` - Кто запросил
- `approver_id` - Кто согласовывает
- `approval_type` - Тип согласования (top_manager, department, etc.)
- `reason` - Причина запроса
- `status` - Статус (pending, approved, rejected)
- `decision_comment` - Комментарий решения
- `requested_at` - Время запроса
- `decided_at` - Время решения

**Миграция:** 005_create_approvals_table.sql, 035_add_modifications_to_approvals.sql

---

## Спецификации и Сделки

### 13. `specifications`
**Описание:** Спецификации к договорам поставки
**Поля:**
- `quote_id` - Связанное КП
- `quote_version_id` - Версия КП
- `specification_number` - Номер спецификации
- `proposal_idn` - IDN предложения
- `sign_date` - Дата подписания
- `validity_period` - Срок действия
- `specification_currency` - Валюта
- `client_payment_terms` - Условия оплаты от клиента
- `cargo_pickup_country` - Страна забора груза
- `delivery_city_russia` - Город доставки в РФ
- `our_legal_entity` - Наше юрлицо (продавец)
- `client_legal_entity` - Юрлицо клиента
- `signed_scan_url` - URL подписанного скана
- `status` - Статус (draft, pending_review, approved, signed)

**Миграция:** 006_create_specifications_table.sql, 036_extend_specifications_v3.sql

### 14. `deals`
**Описание:** Сделки (подписанные спецификации)
**Поля:**
- `specification_id` - Ссылка на спецификацию
- `quote_id` - Ссылка на КП
- `deal_number` - Номер сделки
- `signed_at` - Дата подписания
- `total_amount` - Сумма сделки
- `currency` - Валюта
- `status` - Статус (active, completed, cancelled)

**Миграция:** 007_create_deals_table.sql, 037_extend_deals_v3.sql

---

## Supply Chain (Поставщики и Компании)

### 15. `suppliers`
**Описание:** Внешние поставщики товаров
**Поля:**
- `name` - Название поставщика
- `supplier_code` - 3-буквенный код (например, CMT, RAR)
- `country` - Страна
- `city` - Город
- `inn` - ИНН (для российских поставщиков)
- `kpp` - КПП
- `contact_person` - Контактное лицо
- `contact_email`, `contact_phone` - Контакты
- `default_payment_terms` - Условия оплаты по умолчанию
- `is_active` - Активен ли поставщик

**Миграция:** 018_create_suppliers_table.sql

### 16. `buyer_companies`
**Описание:** Наши юридические лица для закупки
**Поля:**
- `name` - Название компании
- `company_code` - 3-буквенный код
- `country` - Страна
- `inn`, `kpp`, `ogrn` - Реквизиты
- `registration_address` - Юридический адрес
- `general_director_name` - ФИО генерального директора
- `general_director_position` - Должность директора
- `is_active` - Активна ли компания

**Миграция:** 019_create_buyer_companies_table.sql

### 17. `seller_companies`
**Описание:** Наши юридические лица для продажи
**Поля:**
- `name` - Название компании
- `supplier_code` - 3-буквенный код (MBR, RAR, CMT, GES, TEX)
- `country` - Страна
- `inn`, `kpp`, `ogrn` - Реквизиты
- `registration_address` - Юридический адрес
- `general_director_name` - ФИО генерального директора
- `general_director_position` - Должность директора
- `is_active` - Активна ли компания

**Миграция:** 020_create_seller_companies_table.sql

### 18. `brand_supplier_assignments`
**Описание:** Связь брендов и поставщиков (какой поставщик поставляет какой бренд)
**Поля:**
- `brand` - Название бренда
- `supplier_id` - Поставщик
- `is_primary` - Основной ли поставщик для бренда
- `notes` - Примечания

**Миграция:** 025_create_brand_supplier_assignments_table.sql

### 19. `bank_accounts`
**Описание:** Банковские реквизиты (полиморфная таблица для всех типов компаний)
**Поля:**
- `entity_type` - Тип сущности (supplier, buyer_company, seller_company, customer)
- `entity_id` - ID сущности
- `bank_name` - Название банка
- `account_number` - Расчётный счёт
- `bik` - БИК (РФ)
- `correspondent_account` - Корр. счёт
- `swift` - SWIFT/BIC
- `iban` - IBAN
- `currency` - Валюта счёта
- `is_default` - Основной счёт
- `is_active` - Активен ли

**Миграция:** 023_create_bank_accounts_table.sql

---

## Клиенты

### 20. `customer_contacts`
**Описание:** Контактные лица клиентов (ЛПР)
**Поля:**
- `customer_id` - Ссылка на customers
- `name` - ФИО контакта
- `position` - Должность
- `email`, `phone` - Контакты
- `is_signatory` - Является ли подписантом спецификаций
- `is_primary` - Основной контакт
- `notes` - Примечания

**Миграция:** 021_create_customer_contacts_table.sql

### 21. `customer_contracts`
**Описание:** Договоры поставки с клиентами
**Поля:**
- `customer_id` - Клиент
- `contract_number` - Номер договора
- `contract_date` - Дата договора
- `status` - Статус (active, suspended, terminated)
- `next_specification_number` - Счётчик для нумерации спецификаций
- `notes` - Примечания

**Уникальный ключ:** (organization_id, contract_number)
**Миграция:** 022_create_customer_contracts_table.sql

---

## Справочники и Локации

### 22. `locations`
**Описание:** Справочник локаций (города/страны) для выбора в формах
**Поля:**
- `country` - Страна
- `city` - Город
- `code` - Короткий код (MSK, SPB, SH)
- `address` - Полный адрес (опционально)
- `is_hub` - Логистический хаб?
- `is_customs_point` - Пункт таможенной очистки?
- `is_active` - Активна ли локация
- `display_name` - Вычисляемое поле для UI
- `search_text` - Lowercase текст для поиска

**Функции:** `search_locations()`, `create_default_locations()`
**Миграция:** 024_create_locations_table.sql

### 23. `route_logistics_assignments`
**Описание:** Назначение логистов на маршруты
**Источник:** 027_create_route_logistics_assignments_table.sql

---

## Счета Поставщиков

### 24. `supplier_invoices`
**Описание:** Реестр счетов от поставщиков
**Поля:**
- `supplier_id` - Поставщик
- `invoice_number` - Номер счёта
- `invoice_date` - Дата счёта
- `due_date` - Срок оплаты
- `total_amount` - Сумма счёта
- `currency` - Валюта
- `status` - Статус (pending, partially_paid, paid, overdue, cancelled)
- `notes` - Примечания
- `invoice_file_url` - URL скана счёта

**Функции:**
- `update_overdue_supplier_invoices()` - Автоматическая отметка просроченных
- `get_invoice_payment_summary()` - Сводка по оплатам
- `get_supplier_invoices_summary()` - Сводка по организации

**Миграция:** 032_create_supplier_invoices_table.sql

### 25. `supplier_invoice_items`
**Описание:** Позиции в счетах поставщиков
**Поля:**
- `invoice_id` - Ссылка на supplier_invoices
- `quote_item_id` - Ссылка на quote_items (опционально)
- `description` - Описание товара
- `quantity` - Количество
- `unit_price` - Цена за единицу
- `total_price` - Общая сумма (автовычисляемая)
- `unit` - Единица измерения

**Триггеры:** Автоматический пересчёт total_amount в parent invoice
**Миграция:** 033_create_supplier_invoice_items_table.sql

### 26. `supplier_invoice_payments`
**Описание:** Платежи по счетам поставщиков
**Поля:**
- `invoice_id` - Счёт
- `payment_date` - Дата платежа
- `amount` - Сумма платежа
- `currency` - Валюта
- `exchange_rate` - Курс к рублю
- `payment_type` - Тип платежа (advance, partial, final, refund)
- `buyer_company_id` - Наше юрлицо, которое платило
- `payment_document` - Номер платёжного документа
- `notes` - Примечания

**Триггеры:** Автоматическое обновление статуса invoice при добавлении платежа
**Функции:**
- `get_invoice_payments_summary()` - Сводка по платежам
- `get_payments_for_invoice()` - Все платежи по счёту
- `get_payments_by_buyer_company()` - Платежи по юрлицу
- `get_supplier_payment_summary()` - Сводка по поставщику

**Миграция:** 034_create_supplier_invoice_payments_table.sql

---

## Финансовый Учет (План-Факт)

### 27. `plan_fact_categories`
**Описание:** Категории платежей (справочник)
**Поля:**
- `code` - Код категории (client_payment, supplier_payment, logistics, customs, tax, finance_commission, other)
- `name` - Название (рус.)
- `is_income` - Является ли доходом
- `sort_order` - Порядок сортировки

**Миграция:** 008_create_plan_fact_categories_table.sql, 014_seed_plan_fact_categories.sql

### 28. `plan_fact_items`
**Описание:** Плановые и фактические платежи по сделкам
**Поля:**
- `deal_id` - Сделка
- `category_id` - Категория платежа
- `description` - Описание
- `planned_amount` - Плановая сумма
- `planned_currency` - Валюта плана
- `planned_date` - Плановая дата
- `actual_amount` - Фактическая сумма
- `actual_currency` - Фактическая валюта
- `actual_date` - Фактическая дата
- `actual_exchange_rate` - Курс обмена
- `variance_amount` - Отклонение (автовычисляемое)
- `payment_document` - Платёжный документ
- `notes` - Примечания

**Триггеры:** Автоматический расчёт variance_amount
**Миграция:** 009_create_plan_fact_items_table.sql

---

## Уведомления

### 29. `telegram_users`
**Описание:** Связь аккаунтов Telegram с пользователями
**Поля:**
- `user_id` - Ссылка на auth.users
- `telegram_id` - ID в Telegram
- `telegram_username` - Username в Telegram
- `is_verified` - Верифицирован ли
- `verification_code` - Код верификации
- `verification_code_expires_at` - Срок действия кода
- `verified_at` - Время верификации

**Функции:**
- `generate_telegram_verification_code()` - Генерация кода
- `request_telegram_verification()` - Запрос верификации
- `verify_telegram_account()` - Верификация аккаунта

**Миграция:** 010_create_telegram_users_table.sql

### 30. `notifications`
**Описание:** История всех уведомлений пользователям
**Поля:**
- `user_id` - Получатель
- `quote_id` - Связанное КП (опционально)
- `deal_id` - Связанная сделка (опционально)
- `type` - Тип (task_assigned, approval_required, approval_decision, status_changed, returned_for_revision, comment_added, deadline_reminder, system_message)
- `title` - Заголовок
- `message` - Текст
- `channel` - Канал (telegram, email, in_app)
- `status` - Статус (pending, sent, delivered, read, failed)
- `telegram_message_id` - ID сообщения в Telegram
- `email_message_id` - ID email
- `error_message` - Сообщение об ошибке
- `sent_at` - Время отправки
- `delivered_at` - Время доставки
- `read_at` - Время прочтения

**Функции:**
- `create_notification()` - Создание уведомления
- `mark_notification_sent()` - Отметить как отправленное
- `mark_notification_failed()` - Отметить как провалившееся
- `mark_notification_read()` - Отметить как прочитанное
- `get_pending_notifications()` - Получить ожидающие отправки

**Миграция:** 011_create_notifications_table.sql, 041_extend_notifications_v3.sql

---

## 📊 Статистика

**Всего таблиц в миграциях:** 30
**Реально в Production:** 45 таблиц ✅
**Отсутствуют (из миграций):** 8 таблиц ❌
**Дополнительные (нет в миграциях):** 22 таблицы ℹ️
**Вспомогательных функций:** 40+
**Представлений (views):** 3+
**Основных workflow статусов:** 15

> **⚠️ ВАЖНО:** Файл `PRODUCTION_TABLES.md` содержит актуальный список таблиц в production БД

---

## 🔗 Связи между таблицами

### Основные цепочки связей:

1. **Quote Flow:**
   ```
   quotes → quote_items → quote_versions
                ↓
         specifications → deals → plan_fact_items
   ```

2. **Supply Chain:**
   ```
   suppliers → supplier_invoices → supplier_invoice_items → quote_items
                      ↓
          supplier_invoice_payments
   ```

3. **Companies:**
   ```
   buyer_companies ←─┐
   seller_companies  ├─→ bank_accounts (polymorphic)
   suppliers ←───────┤
   customers ←───────┘
   ```

4. **Workflow:**
   ```
   quotes → workflow_transitions
              ↓
           approvals
   ```

---

## 💡 Советы по работе

1. **Поиск по названию таблицы в Supabase:**
   - Используйте Search/Filter в Table Editor
   - Все таблицы имеют префикс организации через RLS

2. **Проверка данных:**
   - `quotes` - основная таблица для КП
   - `quote_items` - позиции КП с закупочными/логистическими данными
   - `suppliers` + `supplier_invoices` - работа со счетами поставщиков

3. **Frequently Used Tables:**
   - `quotes`, `quote_items` - ежедневная работа
   - `specifications` - подготовка к отправке клиенту
   - `deals` + `plan_fact_items` - финансовый учёт
   - `approvals` - согласования

---

## 📝 Примечания

- Все таблицы используют UUID для ID
- Все таблицы имеют RLS (Row Level Security)
- Все даты хранятся в формате TIMESTAMPTZ (UTC)
- Все суммы используют DECIMAL(15,2) для точности
- Коды валют в формате ISO 4217 (3 буквы)

---

**Создано:** 2026-01-20
**Автор:** Claude Code
**Версия:** 1.0
