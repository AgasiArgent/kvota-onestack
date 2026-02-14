BROWSER TEST
timestamp: 2026-02-14T17:00:00Z
session: 2026-02-14 #1
base_url: https://kvotaflow.ru

TASK: [86afdkuux] Verify quote_items.name bug fixed on production
URL: /procurement
STEPS:
1. Login as procurement user (or admin)
2. Navigate to any quote with items in procurement stage (e.g. find one via /quotes list)
3. Open the procurement tab on a quote detail page
4. Try to create/edit a procurement invoice — click "Добавить счёт" or similar
5. Fill in minimal invoice data and attempt to save
6. Check for error "column quote_items.name does not exist" in the page or console
7. If no error — verify the invoice was created successfully
8. Also check: navigate to /supplier-invoices and verify the list loads without errors
EXPECT:
- No "column quote_items.name does not exist" error
- Procurement invoice creation works end-to-end
- /supplier-invoices page loads correctly
- If bug IS still present: note the exact error message and which action triggers it

REPORT_TO: .claude/test-ui-reports/report-20260214-1700-bug-verify.md
