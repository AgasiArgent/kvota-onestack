BROWSER TEST
timestamp: 2026-02-11T02:30:00+03:00
session: 2026-02-10 #1 (invoices revert + BUG-2 fix)
base_url: https://kvotaflow.ru

TASK: [REVERT] Procurement invoice creation works
URL: /procurement/{quote_id}

TEST 1: Procurement page loads without errors
STEPS:
1. Find any quote with items — try /quotes to see the list, pick one with status in procurement
2. Navigate to /procurement/{quote_id}
3. Check that the page loads — procurement workspace should render
4. Check if there's an existing invoice list or "Создать инвойс" button
5. Check console for errors — no 500 errors, no "column does not exist"
EXPECT:
- Procurement workspace page loads
- No server errors
- 0 console errors

TEST 2: Create a new procurement invoice
STEPS:
1. On the procurement page, find the invoice creation section
2. Select a supplier from dropdown
3. Select a buyer company from dropdown
4. Set currency (e.g., USD)
5. Enter total weight (e.g., 10 kg)
6. Check one or more items to include in the invoice
7. Click the create/submit button
8. Check if the invoice appears in the list
9. Check console for errors
EXPECT:
- Invoice creates without error (HTTP 200, no 500)
- Invoice appears in the invoices list on the procurement page
- Invoice status shows a workflow status (e.g., "В работе" / "Ожидает"), NOT a payment status
- 0 console errors

TEST 3: Invoice details are visible after creation
STEPS:
1. After creating the invoice in TEST 2, find it in the list
2. Click to expand/view the invoice details
3. Check that the assigned items are listed
4. Check that supplier, currency, weight are displayed correctly
5. Check console for errors
EXPECT:
- Invoice shows assigned items with quantities
- Supplier name displayed (not UUID)
- Currency and weight visible
- 0 console errors

---

TASK: [REVERT] Finance Инвойсы tab shows invoices from procurement
URL: /finance?tab=invoices

TEST 4: Инвойсы tab loads and shows data
STEPS:
1. Navigate to /finance
2. Click the "Инвойсы" tab (should be 4th tab: Рабочая зона, ERPS, Платежи, Инвойсы)
3. Check if invoices from procurement are displayed in the table
4. Verify columns: №, invoice number, supplier, currency, status, date
5. If the invoice from TEST 2 was just created, verify it appears here
6. Check console for errors
EXPECT:
- Инвойсы tab renders without errors
- Table shows procurement invoices (from `invoices` table)
- If invoices exist, they show with proper data
- Status column shows workflow statuses (pending_procurement, pending_logistics, etc.)
- 0 console errors

---

TASK: [RETEST] BUG-2 Delivery city persists after save
URL: /quotes/ba4a486f-d2cb-4356-8832-db9db3c54246

TEST 5: City autocomplete saves and persists
STEPS:
1. Navigate to quote Q-202602-0073 at /quotes/ba4a486f-d2cb-4356-8832-db9db3c54246
2. Scroll to the ДОСТАВКА section
3. Find the city combobox (delivery-city-input)
4. Clear the field if it has a value
5. Type "Москва" in the city field
6. Wait for autocomplete suggestions to appear
7. Select "Москва" from the suggestions (click it or press Enter)
8. Click outside the field (blur) — this triggers the save via fetch PATCH
9. Wait 2-3 seconds for the save to complete
10. Reload the page (F5 / Ctrl+R)
11. Check if "Москва" is still in the city field after reload
12. Check console for errors — look for any PATCH requests and their status codes
EXPECT:
- Autocomplete works (suggestions appear, no TypeError)
- After blur, a PATCH request fires to /quotes/{id}/inline
- City value "Москва" persists after page reload
- 0 console errors

---

TASK: [RETEST] Design fixes still working
URL: /finance?tab=erps

TEST 6: Quick regression check on design fixes
STEPS:
1. Navigate to /finance?tab=erps
2. Check dates are DD.MM.YYYY format (e.g., "10.02.2026")
3. Check profit columns: green for positive, dash "—" for zero
4. Navigate to /suppliers
5. Check country filter dropdown: no duplicates, all Russian
6. Check console for errors
EXPECT:
- Dates: DD.MM.YYYY (not ISO)
- Profit: green for positive, gray dash for zero
- Countries: Russian names, no duplicates
- 0 console errors

REPORT_TO: .claude/test-ui-reports/report-20260211-0230-invoices-bug2.md
