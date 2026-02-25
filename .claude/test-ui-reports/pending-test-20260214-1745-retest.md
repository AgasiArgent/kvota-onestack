BROWSER TEST (RETEST — deployment confirmed on VPS, previous test may have hit stale cache)
timestamp: 2026-02-14T17:45:00Z
session: 2026-02-14 #1
base_url: https://kvotaflow.ru

IMPORTANT: Force-refresh pages (Ctrl+Shift+R) or use incognito to avoid cached responses.
Deployment confirmed: commit d4c531b is live on VPS container.

TASK: [86afdkuux] Re-verify quote_items.name bug fix
URL: /procurement/482c0486-cebe-410e-a670-364a32feecb4
STEPS:
1. Login as admin (admin@test.kvota.ru / Test123!)
2. Navigate to /procurement/482c0486-cebe-410e-a670-364a32feecb4
3. Click "Редактировать" on existing invoice
4. Click "Сохранить" without changes
5. Verify NO error "column quote_items.name does not exist"
EXPECT:
- Invoice saves without 500 error
- Fix: select query now uses product_name instead of name

TASK: [86afdkuva] Conditional download button visibility
URL: /quotes/{id} — check multiple quotes
NOTE: The buttons are in the RIGHT side of the action bar (below quote title, above items table).
Look for specific button text: "Валидация Excel", "КП PDF", "Счёт PDF".
The "Скачать" button (generic download) is a DIFFERENT button — may exist separately.
STEPS:
1. Open a quote in "draft" (Черновик) status — check action bar
   - EXPECT: "Валидация Excel" visible, NO "КП PDF", NO "Счёт PDF"
2. Open a quote in procurement/logistics/customs status
   - EXPECT: "Валидация Excel" visible, NO "КП PDF", NO "Счёт PDF"
3. Open a quote in "approved" or "sent_to_client" status (if any exist)
   - EXPECT: "КП PDF" visible, NO "Валидация Excel", NO "Счёт PDF"
4. Open a quote in deal status
   - EXPECT: "КП PDF" AND "Счёт PDF" visible, NO "Валидация Excel"
5. Confirm NO "Спецификация DOC" button anywhere
EXPECT:
- Button visibility changes based on workflow status
- If button names differ from expected, note the actual names

TASK: [86afdkuvh] Logistics cost display on Продажи tab
URL: /quotes/74aa8aba-09ec-4e78-8f89-216e633d6210?tab=overview
NOTE: The "Логистика:" row is inside the ИТОГО table at the bottom of the Продажи tab.
It shows format_money output (number with currency symbol, or "—" for zero).
STEPS:
1. Open Q-202601-0013 (has logistics invoice data)
2. Click on "Продажи" tab (tab=overview)
3. Scroll down to find ИТОГО table (should be near the bottom)
4. Look for "Логистика:" row in that table
5. Note what value is displayed
EXPECT:
- "Логистика:" row exists in ИТОГО table
- Shows a number or "—" (dash) if logistics costs are zero
- If ИТОГО table structure is different, describe what you see

REPORT_TO: .claude/test-ui-reports/report-20260214-1745-retest.md
