# Browser Test Report

**Timestamp:** 2026-02-11T23:15:00
**Session:** 2026-02-11 #2
**Base URL:** https://kvotaflow.ru
**Overall:** 3/4 PASS, 1 PARTIAL

## Task: [deal-tabs] Deal page has 3 tabs
**URL:** /finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742
**Status:** PARTIAL (tabs work via URL, but HTMX click causes duplication)

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Navigate to deal detail page | PASS | Page loads correctly, shows DEAL-2026-0002 |
| 2 | 3 tabs visible: Основное, План-факт платежей, Логистика | PASS | All 3 tabs present with correct labels and icons |
| 3 | Default tab is Основное with deal info + plan-fact summary | PASS | Shows ИНФОРМАЦИЯ О СДЕЛКЕ + СВОДКА ПЛАН-ФАКТ cards |
| 4 | Click План-факт платежей tab | FAIL | **BUG: Page duplication.** Clicking tab renders full page nested inside existing page — double header, double sidebar, double tabs. Content is correct but layout is broken. |
| 5 | Click Логистика tab (via URL) | PASS | Shows 7 stages with correct statuses and expense buttons |
| 6 | Tab switching via URL params | PASS | ?tab=main, ?tab=plan-fact, ?tab=logistics all work correctly |
| 7 | Console errors | PASS | No console errors |

**BUG DETAILS — Tab Click Duplication:**
- **Repro:** Click any tab link on the deal detail page
- **Expected:** Tab content switches, page layout stays the same
- **Actual:** HTMX response contains full page layout (header + sidebar + tabs + content), which gets inserted INTO the existing page, creating a nested duplicate
- **Workaround:** Direct URL navigation works correctly (no duplication)
- **Root cause:** The tab links likely use HTMX (hx-get) but the server returns the full page HTML instead of just the tab content div. The hx-target/hx-swap configuration needs to either target the body for replacement OR the server needs to return only the tab content fragment.

**Console Errors:** none
**Screenshots:** initial-load (Основное tab), plan-fact-tab (via click, shows duplication), logistics-tab (via URL, correct)

---

## Task: [deal-modal] Payment form opens as modal
**URL:** /finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742?tab=plan-fact
**Status:** PASS

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Navigate to plan-fact tab | PASS | Loads correctly via direct URL |
| 2 | Click green "+ Добавить платёж" button | PASS | Modal overlay appears |
| 3 | Modal is overlay (not inline/new page) | PASS | Displays as centered dialog over dimmed background |
| 4 | Two modes: existing planned item / new ad-hoc | PASS | Dropdown: "По плану (существующая позиция)" and "Новый (внеплановый платёж)" |
| 5 | Fill test payment: mode=Новый, category=Прочее, amount=50, currency=RUB, date=today | PASS | All fields accept input correctly |
| 6 | Submit — modal closes, payment in table | PASS | Modal closed, page reloaded, "Browser test payment — 50.00 RUB — Оплачено" visible in table |
| 7 | Console errors | PASS | No console errors |

**Console Errors:** none
**Screenshots:** modal-open (По плану mode), modal-filled (Новый mode with test data), after-submit (payment in table)

---

## Task: [deal-logistics-expense] Logistics stage has expense button opening modal
**URL:** /finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742?tab=logistics
**Status:** PARTIAL (modal works, but redirects to wrong tab after submit)

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Navigate to Логистика tab | PASS | 7 stages visible with correct statuses |
| 2 | Stages with "Добавить расход" buttons | PASS | 6 of 7 stages have button (all except Загрузка ГТД — correct) |
| 3 | Click "Добавить расход" on Хаб-Хаб stage | PASS | Modal opens |
| 4 | Category pre-selected to stage's logistics category | PASS | Category dropdown shows "Логистика: Хаб-Хаб" (pre-selected) |
| 5 | Fill amount=75, currency=RUB, date=today | PASS | Fields accept input |
| 6 | Submit — modal closes | PASS | Modal closed, expense saved |
| 7 | Returns to logistics tab | FAIL | **BUG: Redirects to ?tab=plan-fact instead of ?tab=logistics.** Expense is visible in plan-fact table but user is not returned to the logistics tab where they started. |
| 8 | Expense appears in stage summary | SKIPPED | Cannot verify because page redirected to plan-fact tab |
| 9 | Console errors | PASS | No console errors |

**BUG DETAILS — Wrong Tab After Logistics Expense Submit:**
- **Repro:** From Logistics tab, click "Добавить расход" on any stage, fill and submit
- **Expected:** Page reloads to ?tab=logistics, showing updated stage summary
- **Actual:** Page redirects to ?tab=plan-fact, showing expense in plan-fact table
- **Fix:** The POST handler for logistics expense should redirect to `?tab=logistics` instead of `?tab=plan-fact`

**Console Errors:** none
**Screenshots:** logistics-stages, modal-with-preselected-category, after-submit-wrong-tab

---

## Task: [deal-no-duplicate] No duplicate payment sections
**URL:** /finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742?tab=plan-fact
**Status:** PASS

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Navigate to plan-fact tab | PASS | Single unified section displayed |
| 2 | Only plan-fact table section present | PASS | One "ПЛАН-ФАКТ ПЛАТЕЖЕЙ" heading |
| 3 | No separate "ПЛАТЕЖИ" section with blue button | PASS | No duplicate section found |
| 4 | Only ONE "Добавить платёж" button (green) | PASS | Single green button in header area |
| 5 | Console errors | PASS | No console errors |

**Console Errors:** none
**Screenshots:** plan-fact-unified (shows single section with 5 payment rows)

---

## Console Errors (all tasks)
None

## Summary for Terminal 1
PASS: [deal-modal], [deal-no-duplicate]
PARTIAL: [deal-tabs] — tabs work via URL navigation but HTMX tab click causes full page duplication (nested page within page)
PARTIAL: [deal-logistics-expense] — modal + pre-selected category + save all work, but redirects to ?tab=plan-fact instead of ?tab=logistics after submit
FAIL: none

ACTION:
- **BUG 1 (MEDIUM):** Fix HTMX tab switching — server returns full page in HTMX response causing duplication. Either return only tab content fragment, or configure hx-boost/hx-target to replace full body.
- **BUG 2 (LOW):** Fix logistics expense redirect — POST handler should redirect to `?tab=logistics` after saving logistics expense, not `?tab=plan-fact`.
