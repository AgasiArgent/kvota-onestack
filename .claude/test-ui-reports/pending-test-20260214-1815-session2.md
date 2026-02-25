BROWSER TEST
timestamp: 2026-02-14T18:15:00Z
session: 2026-02-14 #2
base_url: https://kvotaflow.ru

TASK: [86afdkuvy] Reorder tabs + merge Documents tab
URL: /quotes/74aa8aba-09ec-4e78-8f89-216e633d6210 (Q-202601-0013, has data across tabs)
STEPS:
1. Login as admin (admin@test.kvota.ru / Test123!)
2. Navigate to /quotes/74aa8aba-09ec-4e78-8f89-216e633d6210
3. Check tab order in the tab bar:
   - EXPECT order: Сводка, Продажи, Закупки, Таможня, Логистика, Контроль, Документы
   - IMPORTANT: Таможня should be BEFORE Логистика (was reversed before)
4. Click "Документы" tab
5. Scroll down — look for a section titled "Цепочка документов по стадиям"
   - EXPECT: Section exists with 5 stage cards (КП, Спецификация, Инвойс, ГТД, УПД)
   - Each card shows document count
6. Verify there is NO separate "Цепочка документов" tab in the tab bar
7. Check console for errors
EXPECT:
- Tab order: Сводка → Продажи → Закупки → Таможня → Логистика → Контроль → Документы
- Document chain section visible inside Documents tab (below file list)
- No separate document chain tab
- No console errors

TASK: [86afdkuwh] Workflow tracking columns (verification)
URL: /quote-control (find a quote to approve)
NOTE: This test verifies that approval handlers don't crash after adding tracking columns.
The actual column values are written to DB silently — we're testing no 500 errors occur.
STEPS:
1. Navigate to /quote-control
2. If any quotes are pending control, click one to open detail
3. If you can test an approval action (clicking approve/reject) — verify no error
4. Otherwise, just verify quote control page loads without errors
5. Check console for errors
EXPECT:
- Quote control page loads without errors
- If approval action is tested: no 500 errors, redirect works correctly
- Console clean (no new errors related to tracking columns)

REPORT_TO: .claude/test-ui-reports/report-20260214-1815-session2.md
