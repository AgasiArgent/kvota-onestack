BROWSER TEST
timestamp: 2026-02-11T23:00:00
session: 2026-02-11 #2
base_url: https://kvotaflow.ru

LOGIN: Use admin account (Test123!) or existing session

TASK: [deal-tabs] Deal page has 3 tabs
URL: https://kvotaflow.ru/finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742
STEPS:
1. Navigate to deal detail page (DEAL-2026-0002)
2. Verify 3 tabs visible: "Основное", "План-факт платежей", "Логистика"
3. Default tab should be "Основное" showing ИНФОРМАЦИЯ О СДЕЛКЕ + СВОДКА ПЛАН-ФАКТ cards
4. Click "План-факт платежей" tab — should show plan-fact table with payments
5. Click "Логистика" tab — should show 7 stages with statuses
6. Tab switching should work via URL params (?tab=main, ?tab=plan-fact, ?tab=logistics)
7. Check console for errors
EXPECT: 3 working tabs, content switches correctly, no errors

TASK: [deal-modal] Payment form opens as modal
URL: https://kvotaflow.ru/finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742?tab=plan-fact
STEPS:
1. Navigate to deal page, click "План-факт платежей" tab
2. Click green "+ Добавить платёж" button
3. A modal dialog should appear (overlay on page, not inline or new page)
4. Modal should have payment form with two modes: selecting existing planned item OR creating new ad-hoc payment
5. Fill in a test payment: mode="Новый платёж", category=any, amount=50, currency=RUB, date=today
6. Submit — modal should close, page should reload showing new payment in table
7. Check console for errors
EXPECT: Modal opens, form works, payment saves, modal closes after submit

TASK: [deal-logistics-expense] Logistics stage has expense button opening modal
URL: https://kvotaflow.ru/finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742?tab=logistics
STEPS:
1. Navigate to deal page, click "Логистика" tab
2. Verify stages are visible with statuses (Первая миля, Хаб, etc.)
3. Find a stage with a "Добавить расход" button (any except Загрузка ГТД)
4. Click "Добавить расход" on a stage (e.g. Хаб-Хаб)
5. Modal should open with payment form, category should be PRE-SELECTED to the stage's logistics category
6. Fill in amount=75, currency=RUB, date=today
7. Submit — modal closes, page reloads to logistics tab
8. Verify the expense appears (stage summary should update)
9. Check console for errors
EXPECT: Modal opens with pre-selected category, expense saves, returns to logistics tab

TASK: [deal-no-duplicate] No duplicate payment sections
URL: https://kvotaflow.ru/finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742?tab=plan-fact
STEPS:
1. Navigate to deal page, Plan-fact tab
2. Verify there is ONLY the plan-fact table section
3. There should be NO separate "ПЛАТЕЖИ" section with blue button
4. Only ONE "Добавить платёж" button (green)
5. Check console for errors
EXPECT: Single unified payment section, no duplicates

REPORT_TO: .claude/test-ui-reports/report-20260211-2300-deal-tabs.md
