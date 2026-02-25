BROWSER TEST
timestamp: 2026-02-12T02:00:00
session: 2026-02-11 #2
base_url: https://kvotaflow.ru

LOGIN: Use admin account (Test123!)

TASK: [impersonation-logistics] Impersonate logistics role
URL: https://kvotaflow.ru/admin/impersonate?role=logistics
STEPS:
1. Login as admin
2. Navigate to /admin/impersonate?role=logistics
3. Verify yellow banner: "Вы просматриваете как: logistics"
4. Check sidebar — should show logistics-relevant links only
5. Navigate to /tasks — verify content is logistics-filtered (no sales/finance/admin sections)
6. Take screenshot of /tasks page
7. Exit impersonation via banner
8. Check console for errors
EXPECT: Sidebar + content filtered for logistics

TASK: [impersonation-customs] Impersonate customs role
URL: https://kvotaflow.ru/admin/impersonate?role=customs
STEPS:
1. Navigate to /admin/impersonate?role=customs
2. Verify yellow banner
3. Check sidebar — should show customs-relevant links
4. Navigate to /tasks — verify content filtered
5. Take screenshot
6. Exit impersonation
7. Check console for errors
EXPECT: Sidebar + content filtered for customs

TASK: [impersonation-finance] Impersonate finance role
URL: https://kvotaflow.ru/admin/impersonate?role=finance
STEPS:
1. Navigate to /admin/impersonate?role=finance
2. Verify yellow banner
3. Check sidebar — should show finance-relevant links (Контроль платежей, Календарь, etc.)
4. Navigate to /tasks — verify content shows finance sections only
5. Take screenshot
6. Exit impersonation
7. Check console for errors
EXPECT: Sidebar + content filtered for finance

TASK: [impersonation-quote_controller] Impersonate quote_controller role
URL: https://kvotaflow.ru/admin/impersonate?role=quote_controller
STEPS:
1. Navigate to /admin/impersonate?role=quote_controller
2. Verify yellow banner
3. Check sidebar — should show quote control links
4. Navigate to /tasks — verify content filtered
5. Take screenshot
6. Exit impersonation
7. Check console for errors
EXPECT: Sidebar + content filtered for quote_controller

TASK: [impersonation-top_manager] Impersonate top_manager role
URL: https://kvotaflow.ru/admin/impersonate?role=top_manager
STEPS:
1. Navigate to /admin/impersonate?role=top_manager
2. Verify yellow banner
3. Check sidebar — should show management-level links (approvals, overview, etc.)
4. Navigate to /tasks — verify content filtered
5. Take screenshot
6. Exit impersonation
7. Check console for errors
EXPECT: Sidebar + content filtered for top_manager

TASK: [impersonation-head_of_sales] Impersonate head_of_sales role
URL: https://kvotaflow.ru/admin/impersonate?role=head_of_sales
STEPS:
1. Navigate to /admin/impersonate?role=head_of_sales
2. Verify yellow banner
3. Check sidebar
4. Navigate to /tasks — verify content filtered
5. Take screenshot
6. Exit impersonation
7. Check console for errors
EXPECT: Sidebar + content filtered for head_of_sales

REPORT_TO: .claude/test-ui-reports/report-20260212-0200-impersonation-allroles.md
