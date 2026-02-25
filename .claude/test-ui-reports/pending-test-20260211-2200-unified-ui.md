BROWSER TEST
timestamp: 2026-02-11T22:00:00
session: 2026-02-11 #2
base_url: https://kvotaflow.ru

LOGIN: Use admin account (Test123!) or existing session

TASK: [B5-retest] Logistics expense creation no longer crashes
URL: https://kvotaflow.ru/finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742
STEPS:
1. Navigate to deal detail page (DEAL-2026-0002)
2. Go to "План-факт" tab
3. Click green "+ Добавить платёж" button (should load form inline via HTMX, NOT navigate to broken page)
4. In the form, select mode "Новый платёж" (ad-hoc)
5. Select a logistics category (e.g. "Логистика: Первая миля")
6. Fill in: actual amount=100, currency=RUB, date=today, description="Test logistics expense"
7. Submit the form
8. Verify the new expense appears in the plan-fact table
9. Check console for errors
EXPECT: Form loads inline, expense saves successfully, appears in plan-fact table. No UUID error, no NOT NULL constraint error.

TASK: [UI-unified] Single payment button replaces two duplicate sections
URL: https://kvotaflow.ru/finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742
STEPS:
1. Navigate to deal detail page
2. Scroll to payment area
3. Verify there is ONLY ONE payment section "ПЛАН-ФАКТ ПЛАТЕЖЕЙ" (NOT two sections)
4. Verify there is NO separate "ПЛАТЕЖИ" section with blue "Зарегистрировать платёж" button
5. The green "+ Добавить платёж" button should load a form via HTMX (inline, not navigate away)
6. The form should have two modes: "Зарегистрировать факт" (for existing planned items) and "Новый платёж" (ad-hoc)
7. Check console for errors
EXPECT: Single unified payment section, one button, inline HTMX form with plan/fact modes

TASK: [UI-logistics-tab] Logistics tab no longer has inline expense forms
URL: https://kvotaflow.ru/finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742
STEPS:
1. Navigate to deal detail page
2. Go to "Логистика" tab
3. Verify stages are visible (Первая миля, Хаб, etc.) with status badges
4. Verify there are NO expandable "+ Добавить расход" forms on each stage
5. Instead, there should be help text like "Добавить → вкладка План-факт"
6. Stage expense summaries should still show (count + total if any)
7. Check console for errors
EXPECT: Stages visible with statuses, NO inline expense forms, help text pointing to plan-fact tab

TASK: [UI-role-filter] Category filtering works for logistics role
URL: https://kvotaflow.ru/finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742
STEPS:
1. Login as admin (admin@test.kvota.ru / Test123!)
2. Navigate to deal detail, click "+ Добавить платёж"
3. Open the category dropdown — should show ALL categories (logistics, client payments, supplier payments, etc.)
4. NOTE: To fully test logistics role filtering, would need a logistics-only user account. For now just verify admin sees all categories.
5. Check console for errors
EXPECT: Admin user sees all categories in dropdown

REPORT_TO: .claude/test-ui-reports/report-20260211-2200-unified-ui.md
