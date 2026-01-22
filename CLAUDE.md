# OneStack Project - Development Notes

**Last Updated:** 2026-01-22
**Current Work:** Hub-and-Spoke Navigation Implementation

---

## ⚠️ CRITICAL RULE - DO NOT MODIFY CALCULATION ENGINE

**Rule:** NEVER make changes to the calculation engine or calculation models.

**Files to NEVER modify:**
- `calculation_engine.py`
- `calculation_models.py`
- `calculation_mapper.py`

**Reason:** Calculation engine is complex, tested, and working correctly. Any changes risk breaking critical business logic.

**If data schema changes:** Adapt data in `build_calculation_inputs()` (main.py) to match calculation engine expectations. Transform new field names to old field names that calculation engine expects.

**Example:**
- Old schema: `base_price_vat`
- New schema: `purchase_price_original`
- **Solution:** `'base_price_vat': item.get('purchase_price_original')` in build_calculation_inputs()

---

## 🐛 Current Issues

### 1. Product Entry Form - HTMX Initialization Issue

**Status:** 🔴 CRITICAL - Form not submitting via HTMX

**Issue:**
- Simplified product entry form displays correctly (only name, SKU, brand, quantity)
- HTMX не отправляет форму - требуется ручной вызов `htmx.process(form)`
- Root cause: HTMX загружается ПОСЛЕ построения DOM в FastHTML

**Temporary Workaround:**
- User can submit form via standard POST (without HTMX)
- Form will redirect to products page, but item will be added

**Proper Fix Needed:**
- Add HTMX initialization script in page footer
- OR use FastHTML's built-in HTMX loading mechanism
- OR move product form to use standard form submission without HTMX

**Commits:**
- a333b68 "Simplify product entry form for sales role"
- 88651ca "Fix HTMX form submission for product creation"

---

## 🐛 Current Issues (Admin Section)

### 1. Sales Product Entry Form Simplification

**Status:** ✅ COMPLETED (2026-01-21)

**User Request:**
- "IDN-SKU не должно быть поля для ввода, потому что присваивается автоматически"
- "Продажник может внести только название, SKU, бренд, количество"
- "Поставщика, компанию покупателя, точку отгрузки, цену, страну - он не знает"
- "Он ввел товары и передал дальше следующему отделу"

**Changes Made:**
1. ✅ Removed from form:
   - IDN-SKU field (auto-generated, not editable)
   - Price field (filled by procurement)
   - Weight field (filled by procurement)
   - Country field (filled by procurement)
   - Customs code field (filled by procurement)
   - Supplier dropdown (filled by procurement)
   - Buyer company dropdown (filled by procurement)
   - Pickup location dropdown (filled by procurement)

2. ✅ Sales form now only has:
   - Product name * (required)
   - SKU / Product Code (optional)
   - Brand (optional)
   - Quantity * (required, default=1)
   - Help text: "Остальные поля заполняются отделом закупок"

3. ✅ Updated display:
   - Shows "Не указана" for empty prices
   - Shows SKU and brand inline
   - Quote detail table: replaced IDN-SKU column with Brand column

**Workflow:**
- Sales manager adds basic product info (name, SKU, brand, qty)
- Procurement team fills rest (supplier, price, weight, country, etc.)

**Known Issue:**
- HTMX doesn't auto-initialize form on page load (see Current Issues #1)
- Form works via standard POST, just no inline HTMX update

**Commits:**
- a333b68 "Simplify product entry form for sales role"
- 88651ca "Fix HTMX form submission for product creation"

---

### 2. Buyer/Seller Company Creation Errors

**Status:** ✅ FIXED (2026-01-20)

**Issue:**
- Clicking "+ Добавить компанию-покупателя" showed "компания не найдена" error
- Root cause: Route order issue - `/buyer-companies/{company_id}` was defined BEFORE `/buyer-companies/new`
- FastHTML/FastAPI matched "new" as a company_id parameter

**Fix:**
- Moved `/buyer-companies/new` GET and POST routes to be BEFORE `/buyer-companies/{company_id}` route
- Now matches correct pattern used in seller-companies routes
- Commit: 18837e5 "Fix buyer-companies routing: move /new routes before /{company_id}"

---

### 3. Roles Cleanup

**Status:** 🟡 MEDIUM - Too many roles displayed

**Issue:**
- Currently showing 86 roles in users tab
- Many old/unused roles cluttering the interface
- User feedback: "непонятно почему у нас доступных роли 86 тут наверное какие-то вообще старые не нужны нам"

**Action Required:**
- Audit kvota.roles table
- Identify and remove old/unused roles
- Keep only active roles relevant to current operations

---

### 4. Users Table UI Improvements

**Status:** ✅ COMPLETED (2026-01-20)

**Changes Made:**
1. ✅ Changed "ID пользователя" header to "ФИО"
2. ✅ Removed "Действия" column with "Роли" button
3. ✅ Removed role legend section (saved vertical space)
4. ✅ Implemented inline role editing:
   - Click on role badges → inline editor opens
   - Checkboxes for all available roles (21 roles)
   - Color-coded role badges in editor
   - Save/Cancel buttons with HTMX
   - No page reload - instant updates

**Commits:**
- 704e536 "Improve admin users table UI"
- b3126f8 "Add inline role editing with clickable badges"

---

## 📋 Recent Changes (2026-01-20)

### Customer Detail Page Enhancements

**Added 4 new tabs:**
1. **Договоры** - Customer contracts
2. **КП** - Commercial quotes with Сумма and Профит columns
3. **Спецификации** - Specifications with Сумма and Профит columns
4. **Запрашиваемые позиции** - All requested items with Количество, Цена, Продан status

**Enhanced General Info tab:**
- Added manager field
- Added creation/update dates
- Added statistics cards:
  * КП count and total sum
  * Specs count and total sum

**Enhanced Addresses tab:**
- Added postal_address field (migration 111)
- Shows when postal address differs from actual address

### Admin Section Restructuring

**Converted to tabbed interface:**
- Tab 1: Пользователи (Users)
- Tab 2: Юрлица-продажи (Seller Companies)
- Tab 3: Юрлица-закупки (Buyer Companies)

**Navigation:**
- Added "Поставщики" link (for procurement + admin roles)
- "Админ" link now points to `/admin` with tabs
- Redirect from old `/admin/users` to `/admin?tab=users`

---

## 🔧 Technical Decisions

### Navigation Architecture

**ВАЖНО:** Перед созданием новых страниц обязательно прочитай:
→ **`.claude/NAVIGATION_ARCHITECTURE.md`** - принципы построения дерева страниц

**Ключевые принципы:**
- **Hub-and-Spoke модель:** `/tasks` - единая точка входа для всех задач
- **Object-oriented URLs:** URL строится от сущности (noun), не от действия
- **Role-based tabs:** Вместо отдельных workspace страниц используй табы на `/quotes/{id}`
- **Sidebar structure:** Главное → Реестры → Финансы → Администрирование

**НЕ ДЕЛАЙ:**
- ❌ Отдельные workspace routes типа `/new-department/{quote_id}`
- ❌ Глубокую вложенность URL
- ❌ Дублирование данных в разных местах

### Database Schema
- **Schema:** Always use `kvota` prefix, never `public`
- **Role column:** Use `r.slug` not `r.code` in RLS policies
- **Migrations:** Sequential numbering (latest: 122)
- **Automated Migrations:** Use `scripts/apply-migrations.sh` via SSH

### Code Organization
- **Service functions:** `services/customer_service.py`
- **Main routes:** `main.py`
- **Inline editing:** HTMX-based, similar pattern across all forms

### Statistics Calculation
- Quotes sum: Aggregated from `quote_items` table
- Specifications sum: Aggregated from `specification_items` table
- Requested items: Deduplicated from all customer quotes and specs

---

## ✅ Deployment Checklist

**User instruction:** "преджде чем сказать что деплорй завершен обязательно проверяй гитхаб и тестирую в браузере"

Before confirming deployment:
1. ✅ Check GitHub Actions - ensure CI/CD passed
2. ✅ Test in browser at https://kvotaflow.ru
3. ✅ Verify all functionality works
4. ✅ Check for console errors
5. ✅ Test all tabs and forms

---

### 5. Seller Company Selection Bug

**Status:** ✅ FIXED (2026-01-20)

**Issue:**
- Seller companies dropdown was empty when creating new quotes
- Error in logs: "Could not find the table 'public.seller_companies'"
- Root cause: `seller_company_service.py` wasn't configured to use kvota schema

**Fix (3 commits):**
1. **Uncommented seller_company_id saving** - Enabled saving seller_company_id in POST /quotes/new handler
2. **Applied migration 028** - Added seller_company_id and idn columns to kvota.quotes table with foreign keys and indexes
3. **Fixed schema configuration** - Added `ClientOptions(schema="kvota")` to seller_company_service.py Supabase client initialization

**Verification:**
- Tested through UI at https://kvotaflow.ru/quotes/new
- Successfully created quote with seller company TST
- Verified seller_company_id saved in database: `39fd9760-a1ee-4196-8449-1df1402344f2`

**Commits:**
- e68ed85 "Fix seller company selection: enable seller_company_id saving"
- 3eb572c "Fix seller_company_service to use kvota schema"
- 0290721 "Fix seller_company_service to use ClientOptions for schema"

---

### 6. Quote Creation Form Improvements

**Status:** ✅ COMPLETED (2026-01-20)

**Changes Made:**
1. **Removed from creation form:**
   - Currency selector (now set during calculation)
   - Payment Terms field (now set during calculation)

2. **Added to creation form:**
   - Delivery City field
   - Delivery Country field
   - Default currency set to RUB on quote creation

3. **Added to calculate page:**
   - Quote Currency selector in Pricing section (RUB/USD/EUR)
   - Currency is saved to quote after calculation completes

4. **Database changes:**
   - Added delivery_country column to kvota.quotes table (migration 118)

**Workflow:**
- Sales manager creates quote with basic info (customer, seller company, delivery location)
- Currency and payment terms are decided during markup/calculation phase
- More logical flow: location first, pricing later

**Verification:**
- Tested quote creation with delivery location fields
- Verified currency selector on calculate page works
- Confirmed delivery_city and delivery_country save correctly

**Commit:** 97f1b9c "Improve quote creation form and calculation page"

---

### 7. Delivery Method Selection

**Status:** ✅ COMPLETED (2026-01-21)

**Changes Made:**
1. **Added delivery_method dropdown to quote creation form** with 4 options:
   - Авиа (Air) - value: "air"
   - Авто (Auto) - value: "auto"
   - Море (Sea) - value: "sea"
   - Мультимодально (все) (Multimodal - all) - value: "multimodal"

2. **Database changes:**
   - Added delivery_method column to kvota.quotes table (migration 120)
   - Column type: TEXT (nullable)

3. **UI integration:**
   - Added dropdown to create quote form (main.py:1297-1309)
   - Added dropdown to edit quote form (main.py:2517-2529)
   - Added display on quote detail page with Russian translations (main.py:1476-1480)
   - Updated POST handlers to save/update delivery_method

4. **Automated migration system created:**
   - Created `scripts/apply-migrations.sh` - Simple bash script using docker exec
   - Tracks migrations in `kvota.migrations` table
   - Handles errors gracefully (continues on non-critical errors like "already exists")
   - Updated `.claude/skills/db-kvota/skill.md` with migration instructions

**Verification:**
- ✅ Migration #120 applied successfully via automated script
- ✅ delivery_method column exists in kvota.quotes table
- ✅ All 4 dropdown options work correctly in UI
- ✅ Form saves delivery_method value to database
- ✅ GitHub Actions CI/CD passed
- ✅ Tested through UI at https://kvotaflow.ru/quotes/new

**Commits:**
- da813d9 "Add delivery method dropdown to quote forms (migration 120)"
- 3a8b28e "Improve migration script: handle errors gracefully and track migrations separately"

---

### 8. Procurement Workflow Enhancement

**Status:** ✅ COMPLETED (2026-01-21)

**User Requirements:**
1. Procurement must enter price in supplier's currency (not base_price_vat)
2. Auto-conversion to quote currency will be implemented later
3. Payment terms NOT needed from procurement (stored in supplier record)
4. Production time - YES, needed
5. Weight and volume per item - NOT mandatory, but need TOTAL weight/volume fields at quote level
6. Typically procurement knows total weight (always), sometimes total volume
7. HS code - NO, filled by customs department
8. Menu access: Hide "Quotes", "Customers", "New Quote" from procurement-only users

**Changes Made:**

1. **Database changes (migrations 121, 122):**
   - Added `purchase_currency` column to quote_items (VARCHAR(3), default 'USD')
   - Added `procurement_total_weight_kg` to quotes (DECIMAL(10,3))
   - Added `procurement_total_volume_m3` to quotes (DECIMAL(10,4))
   - Added check constraints and indexes

2. **Procurement form simplified (main.py:5354-5631):**
   - **Replaced:** base_price_vat → purchase_price_original + purchase_currency
   - **Removed:** per-item weight, per-item volume, advance_percent, payment_terms, notes
   - **Added:** Currency dropdown (USD/EUR/RUB/CNY/TRY)
   - **Added:** Supplier country dropdown (required)
   - **Kept:** Production time (required)
   - **Kept:** Supply chain fields (supplier_id, buyer_company_id, pickup_location_id)

3. **Total weight/volume section added:**
   - Yellow card section "📦 Общие показатели"
   - Total weight in kg (required) - "Вес всегда известен"
   - Total volume in m³ (optional) - "Необязательно (если известно)"
   - Values entered at quote level, not per item

4. **POST handler updated (main.py:5728-5804):**
   - Saves purchase_price_original and purchase_currency per item
   - Saves supplier_country per item
   - Saves procurement_total_weight_kg and procurement_total_volume_m3 to quotes table

5. **Menu access control (main.py:142-165):**
   - Detects procurement-only users (no admin/sales/sales_manager roles)
   - Hides "Quotes", "Customers", "New Quote" from navigation
   - Keeps "Dashboard" and "Закупки" visible

**Workflow:**
- Sales enters basic product info (name, SKU, brand, quantity)
- Procurement enters: price (in supplier's currency), currency, country, production time, supply chain info
- Procurement enters total weight/volume for all priced items
- System will later auto-convert prices to quote currency

**Verification:**
- ✅ Migrations 121, 122 applied successfully
- ✅ GitHub Actions CI/CD passed
- ✅ Tested deployment at https://kvotaflow.ru
- ✅ Procurement page loads without errors
- ✅ Menu items hidden correctly based on role

**Commit:**
- 4f28d32 "Complete procurement workspace form with currency-based pricing"

---

## 🎯 Next Steps

### Immediate (Current Work)
1. ~~Fix buyer/seller company creation bug~~ ✅
2. ~~Fix seller company selection bug~~ ✅
3. ~~Improve quote creation form~~ ✅
4. Clean up roles table (reduce from 86 to relevant ones)
5. Implement sales manager workspace features (quote registry, exports, customer creation)

### Future Enhancements
- Consider adding filters to requested items tab
- Add export functionality for quotes/specs statistics
- Improve performance of statistics calculation

---

## 📝 Notes

- **Domain:** kvotaflow.ru
- **VPS:** beget-kvota
- **Container:** kvota-onestack
- **Framework:** FastHTML + HTMX
- **Database:** Supabase PostgreSQL (kvota schema)

**Always refer to `.claude/skills/db-kvota/skill.md` for database operations.**
