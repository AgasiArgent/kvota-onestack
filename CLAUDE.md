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

**Status:** 🟡 MEDIUM - UX issues

**Current Problems:**
1. **No ФИО column** - showing user ID instead of full name
2. **"Действия" column with "Роли" button** - unnecessary, takes up space
3. **Role legend section** - not needed, clutters UI
4. **Non-interactive role badges** - should be clickable for inline role management

**Required Changes:**
1. ✅ Add "ФИО" column to users table
2. ✅ Remove "Действия" column
3. ✅ Remove role legend section
4. ✅ Make role badges clickable:
   - Click on badge → inline role editor
   - Add/remove/change roles without separate modal
   - Similar UX to customer contacts inline editing

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

## 🎯 Next Steps

### Immediate (Current Work)
1. Fix buyer/seller company creation bug
2. Clean up roles table (reduce from 86 to relevant ones)
3. Implement users table UI improvements
4. Test all changes thoroughly before deployment

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
