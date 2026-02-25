BROWSER TEST
timestamp: 2026-02-12T04:00:00
session: 2026-02-11 #3
base_url: https://kvotaflow.ru

LOGIN: Use admin account (Test123!)

TASK: [#8] Contract type tags + end date
URL: https://kvotaflow.ru/customers/5befe69e-bb12-4221-bb0e-8d1ba17cc0a2?tab=contracts
STEPS:
1. Login as admin
2. Navigate to customer Test Company E2E → Договоры tab
3. Check if contracts list shows TYPE column (Тип) with colored tags:
   - "Единоразовый" (one-time) — should be some color
   - "Пролонгируемый" (renewable) — should be different color
4. Check if contracts list shows END DATE column (Дата окончания)
5. Click "Создать договор" button (or edit existing contract)
6. Verify the contract form has:
   - "Тип договора" dropdown with options: Единоразовый, Пролонгируемый
   - "Дата окончания" date input field
7. Create a new test contract:
   - Number: "TEST-CONTRACT-TYPE"
   - Type: Пролонгируемый
   - End date: 2026-12-31
   - Save
8. Verify the new contract shows in list with green "Пролонгируемый" tag and end date
9. Take screenshot of contracts list showing type tags and end date
EXPECT: Contract type tags (colored badges) + end date visible on list AND form

TASK: [currency-fix] Deal card currency display
URL: https://kvotaflow.ru/quotes/ba4a486f-d2cb-4356-8832-db9db3c54246?tab=finance_main
STEPS:
1. Navigate to quote with RUB currency (the one from earlier session)
2. Click "Сделка" tab (finance_main)
3. Check the deal info card — should show amounts in RUB (₽), NOT USD
4. Check sticky header — should also show ₽ with same currency
5. Both should match: same currency symbol, consistent formatting
6. Navigate to another quote with deal if available to verify
7. Take screenshot showing deal card with correct currency
EXPECT: Deal card shows ₽ amounts (matching quote currency), NOT USD

TASK: [cosmetic] Impersonation banner/sidebar translations
URL: https://kvotaflow.ru/admin/impersonate?role=head_of_sales
STEPS:
1. Navigate to impersonate head_of_sales
2. Check the YELLOW BANNER at top — should say "Вы просматриваете как: Начальник отдела продаж" (NOT raw "head_of_sales")
3. Check the SIDEBAR DROPDOWN — role names should be in Russian (Начальник отдела продаж, etc.)
4. Exit impersonation
5. Try head_of_procurement: /admin/impersonate?role=head_of_procurement
6. Check banner shows "Начальник отдела закупок" (NOT raw "head_of_procurement")
7. Take screenshot of banner with Russian translation
EXPECT: Both banner and sidebar show Russian role names, not raw English slugs

REPORT_TO: .claude/test-ui-reports/report-20260212-0400-contracts-currency.md
