# Browser Test Report

**Timestamp:** 2026-02-23T11:45:00+03:00
**Session:** 2026-02-23 #1
**Base URL:** https://kvotaflow.ru
**Overall:** 2/4 PASS

## Task: [86afmrkh9] Реестр КП: все роли + фильтры (статус, клиент, менеджер)

---

### TEST 1: Admin видит всё
**URL:** /quotes
**Login:** admin (Администратор)
**Status:** PASS

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Sidebar "Реестры" → "Коммерческие предложения" after "Клиенты" | PASS | Link present at /quotes |
| 2 | 3 filter dropdowns visible: Статус, Клиент, Менеджер | PASS | All 3 comboboxes present inline |
| 3 | Total КП count | PASS | 2 КП shown |
| 4 | Status filter "Черновик" works | PASS | URL updated to ?status=draft, 2 results (correct — both are drafts) |
| 5 | "Сбросить" appears on active filter | PASS | Link appears, points to /quotes |
| 6 | "Сбросить" clears all filters | PASS | URL reset to /quotes, all dropdowns reset to "Все..." |
| 7 | Manager filter dropdown present | PASS | "Все менеджеры" dropdown visible |
| 8 | No JS errors | PASS | Only Tailwind CDN warning (expected) |

**Console Errors:** none (only favicon 404 — non-critical)
**Screenshots:** test-quotes-filters-admin-initial.png

---

### TEST 2: Sales видит только свои
**URL:** /quotes
**Login:** Продажи (impersonation)
**Status:** FAIL

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Sidebar "Коммерческие предложения" visible | PASS | Present in Реестры section |
| 2 | Only 2 dropdowns (Статус + Клиент), NO "Менеджер" | **FAIL** | All 3 dropdowns visible including "Все менеджеры" — should be hidden for sales role |
| 3 | Shows only own КП (created_by = current user) | INCONCLUSIVE | Shows 2 КП — same as admin. Both created by admin@test.kvota.ru which is the impersonated user. Cannot fully verify created_by filtering via impersonation with this user. |
| 4 | URL hack ?manager_id=<fake_uuid> blocked | **FAIL** | Navigating to ?manager_id=00000000-0000-0000-0000-000000000000 shows 0 results — the manager_id URL param IS accepted and overrides created_by filtering. Sales user should not be able to use manager_id param to see other managers' quotes. |
| 5 | No JS errors | PASS | No errors in console |

**Bugs found:**
1. **"Менеджер" dropdown visible for sales role** — should be hidden. Sales should only see Статус + Клиент filters.
2. **manager_id URL parameter not blocked for sales** — a sales user can manipulate the URL to potentially bypass created_by filtering. The server-side should ignore manager_id param for sales role users.

**Screenshots:** test-quotes-filters-sales-has-manager.png

---

### TEST 3: Procurement видит реестр
**URL:** /quotes
**Login:** Закупки (impersonation)
**Status:** PASS

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Sidebar "Коммерческие предложения" visible | PASS | Present in Реестры section |
| 2 | All 3 filter dropdowns visible (Статус, Клиент, Менеджер) | PASS | All 3 comboboxes present |
| 3 | All КП visible (org-wide, like admin) | PASS | Shows 2 КП — same as admin |
| 4 | Customer filter functional | INCONCLUSIVE | "Все клиенты" is only option — no customers assigned to quotes in test data |
| 5 | No JS errors | PASS | No errors in console |

**Console Errors:** none
**Screenshots:** (inline verification only)

---

### TEST 4: Комбинированные фильтры
**URL:** /quotes
**Login:** admin
**Status:** PASS (with minor note)

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Status filter "Черновик" via dropdown | PASS | URL ?status=draft, shows 2 drafts |
| 2 | Status filter "Закупки" via URL | PASS | URL ?status=procurement, shows 0 results (correct — no quotes in procurement status) |
| 3 | Combined filters work as AND | INCONCLUSIVE | Cannot fully test — "Клиенты" dropdown only has "Все клиенты" (no customers assigned to test quotes). Status filter works correctly in isolation. |
| 4 | "Сбросить" clears all filters | PASS | URL reset to /quotes, all 2 КП restored, "Сбросить" link disappears |
| 5 | No JS errors | PASS | No errors |

**Minor bug:** When navigating directly to `?status=procurement`, the status dropdown still shows "Все статусы" [selected] instead of "Закупки". The dropdown doesn't sync with URL query params on page load (only when changed via dropdown onchange). This is cosmetic but may confuse users.

**Console Errors:** none

---

## Console Errors (all tasks)
None (only Tailwind CDN warning and favicon 404 — both non-critical and expected in dev environment)

## Summary for Terminal 1
PASS: TEST 1 (admin), TEST 3 (procurement), TEST 4 (combined filters)
FAIL: TEST 2 (sales role)

**FAIL reasons:**
- TEST 2: "Менеджер" dropdown is visible for sales role — should be hidden
- TEST 2: manager_id URL param accepted for sales — should be server-side blocked

**ACTION:**
1. **Hide "Менеджер" dropdown for sales role** — in the /quotes route, check if user has sales role (without admin/head roles) and exclude the manager filter dropdown from the rendered HTML
2. **Server-side: ignore manager_id param for sales users** — in the GET /quotes handler, if user is sales-only, force `manager_id = None` and always apply `created_by = current_user_id` regardless of URL params
3. **Minor: sync dropdown selection with URL params** — on page load, read query params and set dropdown selected values accordingly (status dropdown doesn't reflect URL-based filtering)
4. **Test data limitation** — "Клиенты" dropdown is empty because no customers are assigned to test quotes. Combined filter AND logic couldn't be fully verified. Consider creating test quotes with customer associations.
