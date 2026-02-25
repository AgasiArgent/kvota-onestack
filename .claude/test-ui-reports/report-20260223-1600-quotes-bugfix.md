# Browser Test Report

**Timestamp:** 2026-02-23T12:05:00+03:00
**Session:** 2026-02-23 #1
**Base URL:** https://kvotaflow.ru
**Overall:** 2/3 PASS

## Task: [86afmrkh9] Ретест багов из report-20260223-1530-quotes-filters.md

---

### RETEST 1: Dropdown синхронизация с URL
**URL:** /quotes?status=draft, /quotes?status=pending_procurement, /quotes
**Login:** admin
**Status:** PASS

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | /quotes?status=draft → dropdown shows "Черновик" | PASS | "Черновик" [selected] — previously showed "Все статусы" |
| 2 | /quotes?status=pending_procurement → dropdown shows "Закупки" | PASS | "Закупки" [selected] |
| 3 | /quotes (no params) → dropdown shows "Все статусы" | PASS | "Все статусы" [selected] |
| 4 | "Сбросить" link present on filtered views | PASS | Appears when any filter is active |

**Console Errors:** none
**Bug status:** FIXED

---

### RETEST 2: Sales — менеджер-dropdown скрыт
**URL:** /quotes
**Login:** Продажи (impersonation)
**Status:** PARTIAL FAIL

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Impersonation as "Продажи" works | PASS | Banner: "Вы просматриваете как: Продажи" |
| 2 | Only 2 dropdowns visible (Статус + Клиент) | **PASS** | "Менеджер" dropdown is gone — previously had 3 dropdowns |
| 3 | Shows own КП | PASS | 2 КП visible (both created by impersonated user admin@test) |
| 4 | URL hack: ?manager_id=fake ignored | **FAIL** | Navigating to ?manager_id=00000000-0000-0000-0000-000000000000 shows 0 КП instead of 2. The manager_id URL param is still being processed server-side for sales users. Expected: param ignored, same 2 КП shown. |

**Bug status:**
- "Менеджер" dropdown hidden: **FIXED**
- manager_id URL param blocked: **NOT FIXED** — server still accepts and applies manager_id from URL even for sales-only users

**Screenshots:** retest-sales-url-hack-still-works.png

---

### RETEST 3: Procurement — всё работает
**URL:** /quotes
**Login:** Закупки (impersonation)
**Status:** PASS

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Sidebar "Коммерческие предложения" visible | PASS | Present in Реестры section |
| 2 | All 3 dropdowns visible (Статус, Клиент, Менеджер) | PASS | All present |
| 3 | Status filter "Черновик" via dropdown | PASS | Dropdown shows "Черновик" [selected], URL updated to ?status=draft |
| 4 | Dropdown synced with URL after filter | PASS | "Черновик" correctly selected after page reload |
| 5 | "Сбросить" works | PASS | URL reset to /quotes, dropdown back to "Все статусы" |
| 6 | All КП visible (org-wide) | PASS | 2 КП shown, same as admin |
| 7 | No JS errors | PASS | 0 errors in console |

**Console Errors:** none

---

## Console Errors (all tasks)
None (only Tailwind CDN warning and favicon 404 — both non-critical)

## Summary for Terminal 1
PASS: RETEST 1 (dropdown sync), RETEST 3 (procurement)
FAIL: RETEST 2 (sales URL hack)

**Fixed bugs:**
- Dropdown now syncs with URL query params on page load
- "Менеджер" dropdown hidden for sales role

**Remaining bug:**
- `manager_id` URL parameter is still processed server-side for sales users. When a sales user navigates to `/quotes?manager_id=<any_uuid>`, the server applies this filter instead of ignoring it. This allows sales users to manipulate results via URL (security issue — they could potentially view quotes by specifying a real manager's UUID).

**ACTION:**
1. In GET /quotes handler: if user is sales-only (no admin/head roles), force `manager_id = None` regardless of URL params. The created_by filter should be the ONLY filter applied for sales users' manager scope.
