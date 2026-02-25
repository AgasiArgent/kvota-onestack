BROWSER TEST
timestamp: 2026-02-12T00:30:00
session: 2026-02-11 #2
base_url: https://kvotaflow.ru

LOGIN: Use admin account (Test123!)

TASK: [impersonation] Admin can switch to different role via sidebar dropdown
URL: https://kvotaflow.ru/dashboard
STEPS:
1. Login as admin (Test123!)
2. Look in the sidebar below navigation links — find "Режим просмотра:" dropdown
3. Verify dropdown shows "Все роли (админ)" as default
4. Select "sales" from dropdown
5. Page should redirect to dashboard
6. Verify yellow warning banner appears at top: "Режим просмотра: sales" with "Выйти из режима" link
7. Verify sidebar now shows only sales-relevant links (no "Закупки", "Логистика" etc.)
8. Click "Выйти из режима" link in the yellow banner
9. Verify banner disappears, all admin navigation returns
10. Check console for errors
EXPECT: Role switching works, banner shows/hides, sidebar changes based on impersonated role

TASK: [impersonation-protection] Non-admin cannot use impersonation
URL: https://kvotaflow.ru/admin/impersonate?role=sales
STEPS:
1. Login as a non-admin user (e.g. sales-only user if available)
2. Navigate directly to /admin/impersonate?role=sales
3. Should redirect to / without setting impersonation
4. Verify NO yellow banner appears
5. Check console for errors
EXPECT: Non-admin gets redirected, no impersonation possible

TASK: [impersonation-invalid] Invalid role is rejected
URL: https://kvotaflow.ru/admin/impersonate?role=superadmin
STEPS:
1. Login as admin
2. Navigate directly to /admin/impersonate?role=superadmin
3. Should redirect to / without setting impersonation
4. Verify NO yellow banner appears (invalid role rejected)
5. Navigate to /admin/impersonate?role=procurement
6. Verify yellow banner DOES appear (valid role accepted)
7. Check console for errors
EXPECT: Invalid roles silently rejected, valid roles accepted

REPORT_TO: .claude/test-ui-reports/report-20260212-0030-impersonation.md
