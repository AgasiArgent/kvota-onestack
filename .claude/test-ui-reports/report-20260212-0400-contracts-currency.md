# Browser Test Report

**Timestamp:** 2026-02-12T04:15:00
**Session:** 2026-02-11 #3
**Base URL:** https://kvotaflow.ru
**Overall:** 3/3 PASS

## Task: [#8] Contract type tags + end date
**URL:** /customers/5befe69e-bb12-4221-bb0e-8d1ba17cc0a2?tab=contracts
**Status:** PASS

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Navigate to customer contracts tab | PASS | Page loaded, Договоры tab active |
| 2 | ТИП column exists in contracts list | PASS | Column header visible |
| 3 | ОКОНЧАНИЕ column exists in contracts list | PASS | Column header visible |
| 4 | Contract creation form has "Тип договора" dropdown | PASS | Options: -- Не указан --, Единоразовый, Пролонгируемый |
| 5 | Contract creation form has "Дата окончания" date input | PASS | Date picker with "Необязательно" hint |
| 6 | Create test contract with type + end date | PASS | Created TEST-CONTRACT-TYPE with Пролонгируемый, end 31.12.2026 |
| 7 | New contract shows colored type tag in list | PASS | "Пролонгируемый" displayed as green colored badge |
| 8 | New contract shows end date in list | PASS | "31.12.2026" visible in ОКОНЧАНИЕ column |
| 9 | Old contract without type shows dash | PASS | ДП-20260201 shows "—" for type and end date |

**Console Errors:** none
**Screenshots:** contracts-list-initial, contract-form-filled, contracts-list-with-type-tag

---

## Task: [currency-fix] Deal card currency display
**URL:** /quotes/ba4a486f-d2cb-4356-8832-db9db3c54246?tab=finance_main
**Status:** PASS

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Navigate to quote finance/deal tab | PASS | Page loaded, Сделка tab active |
| 2 | Sticky header shows ₽ currency | PASS | "₽581,840" in header |
| 3 | Deal info card shows ₽ amounts | PASS | "Сумма сделки: 581,839.50 ₽" |
| 4 | Plan-fact summary shows ₽ | PASS | All amounts: 0.00 ₽, 27,482.00 ₽, 260.00 ₽ etc. |
| 5 | No USD symbols visible | PASS | All amounts consistently use ₽, no $ anywhere |

**Console Errors:** none
**Screenshots:** deal-card-rub-currency

---

## Task: [cosmetic] Impersonation banner/sidebar translations
**URL:** /admin/impersonate?role=head_of_sales
**Status:** PASS

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Impersonate head_of_sales | PASS | Redirected to /tasks |
| 2 | Banner shows Russian role name | PASS | "Вы просматриваете как: Нач. продаж" (abbreviated Russian) |
| 3 | Sidebar dropdown shows Russian | PASS | "Нач. продаж" selected in dropdown |
| 4 | Roles badge shows full Russian name | PASS | "НАЧАЛЬНИК ОТДЕЛА ПРОДАЖ" badge on page |
| 5 | Impersonate head_of_procurement | PASS | Redirected to /tasks |
| 6 | Banner shows Russian for procurement | PASS | "Вы просматриваете как: Нач. закупок" |
| 7 | Sidebar dropdown shows Russian | PASS | "Нач. закупок" selected in dropdown |
| 8 | Roles badge shows full Russian name | PASS | "НАЧАЛЬНИК ОТДЕЛА ЗАКУПОК" badge on page |
| 9 | No raw English slugs visible | PASS | No "head_of_sales" or "head_of_procurement" anywhere |

**Note:** Banner and sidebar use abbreviated forms ("Нач. продаж", "Нач. закупок") while role badges use full names ("НАЧАЛЬНИК ОТДЕЛА ПРОДАЖ", "НАЧАЛЬНИК ОТДЕЛА ЗАКУПОК"). Both are valid Russian translations.

**Console Errors:** none
**Screenshots:** impersonate-head-of-sales, impersonate-head-of-procurement

---

## Console Errors (all tasks)
None

## Summary for Terminal 1
PASS: #8, currency-fix, cosmetic
FAIL: (none)
ACTION: none
