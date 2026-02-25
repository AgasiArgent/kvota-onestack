BROWSER TEST
timestamp: 2026-02-12T00:00:00
session: 2026-02-11 #2
base_url: https://kvotaflow.ru

LOGIN: Use admin account (Test123!) or existing session

TASK: [consolidation] Finance tabs visible on quote detail page when deal exists
URL: https://kvotaflow.ru/quotes
STEPS:
1. Navigate to /quotes list page
2. Find a quote that has a deal (e.g. one with status "Спецификация подписана" or similar advanced status)
3. Click on it to open quote detail
4. Verify tabs include: Обзор, Позиции, Закупки, Таможня, Логистика, Финансы (Сделка), Финансы (План-факт), Финансы (Логистика)
5. Click "Финансы (Сделка)" tab — should show deal info + plan-fact summary
6. Click "Финансы (План-факт)" tab — should show plan-fact table with payments
7. Click "Финансы (Логистика)" tab — should show logistics stages grid
8. Verify "Сделки" link is NOT in sidebar navigation
9. Check console for errors
EXPECT: Finance tabs render correctly on quote page, no "Сделки" in sidebar

TASK: [consolidation-redirect] /finance/{deal_id} redirects to /quotes/{quote_id}
URL: https://kvotaflow.ru/finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742
STEPS:
1. Navigate directly to /finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742
2. Verify browser redirects to /quotes/{some-uuid}?tab=finance_main
3. Page should show the quote detail with finance tab active
4. Check console for errors
EXPECT: Redirect works, lands on quote page with finance tab

TASK: [consolidation-no-deal] Quote without deal shows no finance tabs
URL: https://kvotaflow.ru/quotes/new
STEPS:
1. Navigate to /quotes and find a quote in "Черновик" (draft) status
2. Open it
3. Verify finance tabs are NOT shown (only Обзор, Позиции, Закупки, etc.)
4. Check console for errors
EXPECT: Draft quotes without deals don't show finance tabs

REPORT_TO: .claude/test-ui-reports/report-20260212-0000-consolidation.md
