BROWSER TEST
timestamp: 2026-02-12T03:00:00
session: 2026-02-11 #3
base_url: https://kvotaflow.ru

LOGIN: Use admin account (Test123!)

NOTE: This is a VERIFICATION test — checking if these items are already working before we implement anything. Report honestly what works and what doesn't.

TASK: [verify-6] Button layout 2 columns on quote detail
URL: https://kvotaflow.ru/quotes/1f3440d7-33e0-41bd-aadb-2c17edd42008
STEPS:
1. Login as admin
2. Navigate to quote Q-202601-0004
3. Look at the Сводка tab (default tab)
4. Check if action buttons ("Отправить на проверку", "Скачать", etc.) are laid out in 2 columns:
   - LEFT side: workflow buttons (Отправить на проверку, Передать в закупки, etc.)
   - RIGHT side: export/download buttons (Скачать, etc.)
5. If buttons are all stacked vertically in one column = NOT done (needs implementation)
6. If buttons are in a horizontal 2-column layout = DONE
7. Take a screenshot showing button layout
EXPECT: Report current button layout — is it 1 column or 2 columns?

TASK: [verify-8] Contract profile — tags + end date
URL: https://kvotaflow.ru/customers
STEPS:
1. Navigate to /customers
2. Open any customer that has contracts (e.g., first customer in list)
3. Click "Договоры" tab
4. Check if contracts have:
   - Tags/labels showing type: "единоразовый" (one-time) or "пролонгируемый" (renewable)
   - End date field visible
5. If a contract creation form exists, check if it has tag selector and end date field
6. Take screenshot of contracts tab
EXPECT: Report what fields/tags are visible on contracts. Are type tags and end date present?

TASK: [verify-9] Customer profile — КП and Позиции tabs data
URL: https://kvotaflow.ru/customers
STEPS:
1. Navigate to /customers
2. Open a customer that has quotes (e.g., search for a customer with known KP)
3. Click "КП" tab — verify it shows list of quotes with Сумма and Профит columns
4. Click "Позиции" (or "Запрашиваемые позиции") tab — verify it shows items with quantities/prices
5. Click "Спецификации" tab — verify it shows specs if any exist
6. If tabs show data = DONE (was fixed as B1 earlier)
7. If tabs are empty or show error = NOT DONE
8. Take screenshots of each tab
EXPECT: All tabs should show data if customer has quotes. Report what loads.

TASK: [verify-cosmetic] Role display name translations
URL: https://kvotaflow.ru/admin/impersonate?role=head_of_sales
STEPS:
1. Navigate to impersonate head_of_sales
2. Check if role badge shows "Начальник отдела продаж" (translated) or raw "HEAD_OF_SALES" (not translated)
3. Exit impersonation
4. Try head_of_procurement: /admin/impersonate?role=head_of_procurement
5. Check if badge shows translated name or raw slug
6. Exit impersonation
EXPECT: Both should show Russian translations, not raw English slugs

TASK: [verify-15] ERPS payment day counter column
URL: https://kvotaflow.ru/erps
STEPS:
1. Navigate to /erps (Контроль платежей page)
2. Look for a column "Дней ожидания оплаты" in the table
3. Check that the column shows color-coded badges:
   - Green: <30 days or "Оплачено" (if remaining_payment = 0)
   - Yellow: 30-60 days
   - Red: >=60 days
   - "—" if no overdue payments
4. If no data visible, check compact columns toggle
5. Take screenshot of ERPS table showing the new column
EXPECT: New column visible with color-coded day counters

TASK: [verify-16] Quote header IDN + Client on all tabs
URL: https://kvotaflow.ru/quotes/1f3440d7-33e0-41bd-aadb-2c17edd42008
STEPS:
1. Navigate to quote Q-202601-0004
2. Check that a compact white header bar shows: "КП Q-202601-0004 | [status badge] | Test Company E2E | [sum]"
3. Click "Продажи" tab — verify same header persists
4. Click "Закупки" tab — verify same header persists
5. Click "Сделка" tab — verify same header persists
6. Take screenshot showing the compact header
EXPECT: Compact single-line header with IDN | status | client | sum visible on every tab

REPORT_TO: .claude/test-ui-reports/report-20260212-0300-verify-remaining.md
