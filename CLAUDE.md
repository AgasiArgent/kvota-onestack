# OneStack Project - Development Notes

**Last Updated:** 2026-01-20
**Current Work:** Admin Section UI Improvements & Bug Fixes

---

## 🐛 Current Issues (Admin Section)

### 1. Buyer/Seller Company Creation Errors

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

### 2. Roles Cleanup

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

### 3. Users Table UI Improvements

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

### Database Schema
- **Schema:** Always use `kvota` prefix, never `public`
- **Role column:** Use `r.slug` not `r.code` in RLS policies
- **Migrations:** Sequential numbering (latest: 111)

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

### 4. Seller Company Selection Bug

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

## 🎯 Next Steps

### Immediate (Current Work)
1. ~~Fix buyer/seller company creation bug~~ ✅
2. ~~Fix seller company selection bug~~ ✅
3. Clean up roles table (reduce from 86 to relevant ones)
4. Review and improve quote creation form (remove currency, payment_terms, add delivery location fields)

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
