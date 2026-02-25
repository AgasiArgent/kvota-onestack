# Browser Test Report

**Timestamp:** 2026-02-12T00:15:00
**Session:** 2026-02-11 #2
**Base URL:** https://kvotaflow.ru
**Overall:** 3/3 PASS

## Task: [consolidation] Finance tabs visible on quote detail page when deal exists
**URL:** /quotes/1f3440d7-33e0-41bd-aadb-2c17edd42008 (Q-202601-0004, status СДЕЛКА)
**Status:** PASS

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Navigate to /quotes list | PASS | Page loads, 87 quotes shown |
| 2 | Find quote with deal status | PASS | Q-202601-0004 has СДЕЛКА status |
| 3 | Open quote detail | PASS | Tabs render correctly |
| 4 | Verify finance tabs exist | PASS | 3 finance tabs in DOM: Сделка, План-факт, Логистика (сделка) — off-screen to the right of Цепочка документов |
| 5 | Click "Сделка" tab | PASS | Shows deal info (DEAL-2026-0004) + plan-fact summary card |
| 6 | Click "План-факт" tab | PASS | Shows "ПЛАН-ФАКТ ПЛАТЕЖЕЙ" with empty state, buttons: Сгенерировать из КП, + Добавить вручную |
| 7 | Click "Логистика (сделка)" tab | PASS | Shows 7 logistics stages grid: Первая миля, Хаб, Хаб–Хаб, Транзит, Пост-транзит, Загрузка ГТД, Последняя миля |
| 8 | "Сделки" NOT in sidebar | PASS | Sidebar under ФИНАНСЫ shows only: Контроль платежей, Календарь |
| 9 | Console errors | PASS | None |

**Note:** Finance tabs (Сделка, План-факт, Логистика (сделка)) are in the DOM but visually off-screen to the right — user needs to scroll the tab bar horizontally to see them. Consider this a minor UX issue: with 11 tabs total, the last 3 finance tabs are not immediately visible.

**Console Errors:** none

---

## Task: [consolidation-redirect] /finance/{deal_id} redirects to /quotes/{quote_id}
**URL:** /finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742
**Status:** PASS

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Navigate to /finance/{deal_id} | PASS | Navigated to /finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742 |
| 2 | Verify redirect to /quotes/{uuid}?tab=finance_main | PASS | Redirected to /quotes/ba4a486f-d2cb-4356-8832-db9db3c54246?tab=finance_main |
| 3 | Page shows quote with finance tab active | PASS | Shows Q-202602-0073 (СПЕЦИФИКАЦИЯ status), deal DEAL-2026-0002, plan-fact summary with data |
| 4 | Console errors | PASS | None |

**Console Errors:** none

---

## Task: [consolidation-no-deal] Quote without deal shows no finance tabs
**URL:** /quotes/d227979d-ed50-4986-bc71-c4681897e8c7 (Q-202602-0087, draft)
**Status:** PASS

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Navigate to /quotes, find draft quote | PASS | Q-202602-0087 has ЧЕРНОВИК status |
| 2 | Open draft quote | PASS | Page loads correctly |
| 3 | Verify NO finance tabs | PASS | Only 8 tabs: Продажи, Закупки, Логистика, Таможня, Контроль, Кост-анализ, Документы, Цепочка документов. No Сделка/План-факт/Логистика (сделка) tabs |
| 4 | Console errors | PASS | None |

**Note:** "Сделка" text appears only in the progress stepper (step 9), not as a tab.

**Console Errors:** none

---

## Console Errors (all tasks)
None

## Summary for Terminal 1
PASS: consolidation, consolidation-redirect, consolidation-no-deal
FAIL: (none)
ACTION: none — all tests pass

**Minor UX observation:** The 3 finance tabs (Сделка, План-факт, Логистика (сделка)) on quotes with deals are off-screen to the right due to having 11 total tabs. Users must scroll the tab bar horizontally. Consider making tab names shorter or adding a visual indicator that more tabs exist.
