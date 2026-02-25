BROWSER TEST
timestamp: 2026-02-11T21:00:00
session: 2026-02-11 #2
base_url: https://kvotaflow.ru

LOGIN: Use admin account (Test123!) or existing session

TASK: [D7-fix] ERPS "+" payment button now visible
URL: https://kvotaflow.ru/finance?tab=erps
STEPS:
1. Navigate to /finance?tab=erps (tab should say "Контроль платежей")
2. Look for "+" button as the 3RD column (right after IDN and Клиент) — should be sticky/always visible
3. Click "+" on any row with a deal — modal should open with payment form
4. Verify modal has fields: amount, currency, date, category, description
5. Close modal (click outside or X)
6. Check page subtitle says "Сделки, Контроль платежей и календарь платежей" (not "ERPS")
7. Check console for errors
EXPECT: Green "+" button visible without scrolling, modal opens with payment form, subtitle updated

TASK: [D9-fix] Dashboard sales blocks visible for admin
URL: https://kvotaflow.ru/dashboard?tab=overview
STEPS:
1. Login as admin (admin@test.kvota.ru / Test123!)
2. Navigate to /dashboard?tab=overview
3. Look for "Мои показатели" section with 3 blocks:
   - Мои запросы (в работе) — count + sum in RUB
   - Мои СП — count + sum in RUB
   - Мои КП — count + sum in RUB
4. Check date range filter (from/to) is present above blocks
5. Change a date — blocks should update
6. Click "Посмотреть все" on any block — should navigate to filtered page
7. Check console for errors
EXPECT: 3 summary blocks visible for admin user, date filter works

TASK: [B1-fix] Customer profile tabs now show data
URL: https://kvotaflow.ru/customers/5befe69e-bb12-4221-bb0e-8d1ba17cc0a2
STEPS:
1. Navigate to customer profile (Test Company E2E or CRUD Test Company)
2. Check General tab — statistics cards should show non-zero КП count and sum
3. Click "КП" tab — should show quotes (not "Всего: 0 КП")
4. Click "Спецификации" tab — should show specs if customer has any
5. Click "Позиции" tab — should show requested items if customer has quotes
6. Click "Договоры" tab — should still work (was working before)
7. Try a second customer to confirm it's not customer-specific
8. Check console for errors
EXPECT: КП tab shows quotes, Спеки tab shows specs, Позиции shows items, stats are non-zero

REPORT_TO: .claude/test-ui-reports/report-20260211-2100-fixes.md
