BROWSER TEST
timestamp: 2026-02-12T01:15:00
session: 2026-02-11 #2
base_url: https://kvotaflow.ru

LOGIN: Use admin account (Test123!)

TASK: [impersonation-content] Impersonation filters page content, not just sidebar
URL: https://kvotaflow.ru/dashboard
STEPS:
1. Login as admin
2. In sidebar, find role dropdown and select "sales"
3. Yellow banner should appear: "Вы просматриваете как: sales"
4. Navigate to /tasks page
5. Verify main content ONLY shows sales-relevant sections (e.g. "Мои задачи")
6. Verify admin-only sections are HIDDEN: "Ожидают согласования", "Спецификации: требуют внимания", "Финансы: активные сделки"
7. Navigate to /dashboard (or wherever it redirects)
8. Verify dashboard content is filtered for sales role too
9. Click "Выйти" in banner to exit impersonation
10. Navigate back to /tasks — verify ALL admin sections return
11. Check console for errors
EXPECT: Both sidebar AND main content filter by impersonated role. No admin sections visible when impersonating sales.

TASK: [impersonation-procurement] Impersonation as procurement shows procurement content
URL: https://kvotaflow.ru/admin/impersonate?role=procurement
STEPS:
1. Login as admin
2. Navigate to /admin/impersonate?role=procurement
3. Navigate to /tasks
4. Verify content shows procurement-relevant sections only
5. Verify sales-only and admin-only sections are hidden
6. Exit impersonation via banner
7. Check console for errors
EXPECT: Procurement impersonation shows procurement tasks/content only

REPORT_TO: .claude/test-ui-reports/report-20260212-0115-impersonation-content.md
