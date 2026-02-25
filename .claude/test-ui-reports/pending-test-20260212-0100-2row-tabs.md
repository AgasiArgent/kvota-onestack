BROWSER TEST
timestamp: 2026-02-12T01:00:00
session: 2026-02-11 #2
base_url: https://kvotaflow.ru

LOGIN: Use admin account (Test123!)

TASK: [2row-tabs-with-deal] Quote with deal shows 2-row tab layout
URL: https://kvotaflow.ru/quotes/1f3440d7-33e0-41bd-aadb-2c17edd42008
STEPS:
1. Login as admin
2. Navigate to /quotes/1f3440d7-33e0-41bd-aadb-2c17edd42008 (Q-202601-0004, has deal)
3. Verify tabs are split into TWO rows (not one long scrollable row)
4. Row 1 should have core tabs: Продажи, Закупки, Логистика, Таможня, Контроль, Кост-анализ, Документы, Цепочка документов
5. Row 2 should start with "Финансы:" label, followed by: Сделка, План-факт, Логистика (сделка)
6. Both rows should have bottom border line
7. NO horizontal scrolling needed — all tabs visible
8. Click a finance tab (e.g. "Сделка") — verify it activates correctly
9. Click a core tab (e.g. "Продажи") — verify it activates correctly
10. Check console for errors
EXPECT: 2 rows of tabs, no horizontal scroll, both rows functional

TASK: [2row-tabs-no-deal] Quote without deal shows single row
URL: https://kvotaflow.ru/quotes
STEPS:
1. Navigate to /quotes and find a quote in ЧЕРНОВИК status
2. Open it
3. Verify tabs are in a SINGLE row (no second row, no "Финансы:" label)
4. All tabs visible without scrolling (should be ~8 tabs max)
5. Check console for errors
EXPECT: Single row of tabs, no finance row visible

REPORT_TO: .claude/test-ui-reports/report-20260212-0100-2row-tabs.md
