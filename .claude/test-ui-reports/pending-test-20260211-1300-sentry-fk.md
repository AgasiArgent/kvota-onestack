BROWSER TEST
timestamp: 2026-02-11T13:02:00Z
session: 2026-02-11
base_url: https://kvotaflow.ru

TASK: [SENTRY] Fix NoneType .get() on PostgREST FK joins
URL: /quote-control/{quote_id}
STEPS:
1. Navigate to https://kvotaflow.ru and log in as admin
2. Go to Quotes list, find any quote with status that has a quote-control page
3. Navigate to /quote-control/{quote_id} for that quote
4. Verify page loads without 500 error
5. Check that customer name displays correctly (or "---" if no customer linked)
6. Check console for any JavaScript errors
7. Navigate to /deals and open a deal detail page
8. Check the plan-fact / payments section loads without errors
9. Navigate to /admin?tab=users
10. Verify roles display correctly (should show ~10 unique roles, not 86)
11. Try editing a user's roles - verify save works
EXPECT:
- No 500 errors on quote-control page
- Customer name shows correctly or "---" fallback
- Plan-fact section loads without errors
- Admin users tab shows deduplicated roles (~10)
- Role editing works without wiping all roles

TASK: [MIGRATION-168] Roles cleanup verification
URL: /admin?tab=users
STEPS:
1. Navigate to /admin?tab=users
2. Count the number of available roles in any user's role editor
3. Verify deprecated roles are gone: ceo, cfo, customs_manager, financial_admin, financial_manager, logistics_manager, marketing_director, procurement_manager, top_sales_manager
4. Verify active roles are present: admin, sales, finance, procurement, logistics, customs, quote_controller, top_manager, sales_manager
EXPECT:
- ~10 unique roles available (not 86)
- No deprecated role names visible
- Users who had deprecated roles now have their remapped equivalents

REPORT_TO: .claude/test-ui-reports/report-20260211-1300-sentry-fk.md
