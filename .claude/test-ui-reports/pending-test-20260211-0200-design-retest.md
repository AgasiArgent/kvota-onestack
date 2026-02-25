BROWSER TEST
timestamp: 2026-02-11T02:00:00+03:00
session: 2026-02-10 #1 (design retest)
base_url: https://kvotaflow.ru

TASK: [RETEST] Date format DD.MM.YYYY across all pages
URL: /finance?tab=erps, /finance/{deal_id}

TEST 1: ERPS table dates use DD.MM.YYYY
STEPS:
1. Navigate to /finance?tab=erps
2. Find date columns in the ERPS table (Дата создания, Дата изменения, Крайний срок поставки, Крайний срок оплаты аванса)
3. Check date format — should be DD.MM.YYYY (e.g., "10.02.2026"), NOT ISO (e.g., "2026-02-10")
4. Check console for errors
EXPECT:
- All dates in ERPS table use DD.MM.YYYY format
- No ISO format dates (YYYY-MM-DD) visible in date columns
- 0 console errors

TEST 2: Deal detail page dates use DD.MM.YYYY
STEPS:
1. Navigate to /finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742 (DEAL-2026-0002)
2. Find "Дата подписания" field — should be DD.MM.YYYY
3. Find plan-fact table — "План. дата" and "Факт. дата" columns should use DD.MM.YYYY
4. Check console for errors
EXPECT:
- "Дата подписания" shows DD.MM.YYYY (e.g., "10.02.2026")
- Plan-fact table dates show DD.MM.YYYY
- 0 console errors

---

TASK: [RETEST] Profit column color coding
URL: /finance?tab=erps

TEST 3: Positive profit shows green, zero shows gray
STEPS:
1. Navigate to /finance?tab=erps
2. Find "Профит USD" column (spec_profit_usd)
3. Check color of positive values (e.g., $228.04, $1,853.17) — should be GREEN (#059669 or similar)
4. Check color of zero values — should be GRAY (#6b7280 or similar)
5. Check if zero amounts show "—" (dash) instead of "$0.00"
6. Find "Фактический профит USD" column (actual_profit_usd) — same coloring rules
7. Check console for errors
EXPECT:
- Positive profit: green text color
- Zero/null profit: gray text, displayed as "—" (dash)
- Negative profit (if any): red text color
- No more plain dark gray for all values
- 0 console errors

---

TASK: [RETEST] Supplier country names in Russian (no duplicates)
URL: /suppliers

TEST 4: Supplier filter dropdown has no duplicates
STEPS:
1. Navigate to /suppliers
2. Open the country filter dropdown
3. Check that "Германия" appears ONCE (not both "Германия" and "Germany")
4. Check that all countries are in Russian: Германия, Италия, Китай, Турция, etc.
5. Check supplier table — TST supplier should show "Германия" (not "Germany")
6. Check console for errors
EXPECT:
- No duplicate country entries in filter dropdown
- TST supplier location shows "Германия" in Russian
- All country names in Russian
- 0 console errors

---

TASK: [RETEST] BUG-2 Delivery city persists after save
URL: /quotes/ba4a486f-d2cb-4356-8832-db9db3c54246

TEST 5: City autocomplete saves and persists
STEPS:
1. Navigate to Q-202602-0073
2. Find the city combobox in ДОСТАВКА section
3. Type "Москва" in the city field
4. Select "Москва" from autocomplete suggestions (or wait for it to appear)
5. Click outside the field (blur) — this should trigger save
6. Wait 2 seconds for HTMX save to complete
7. Reload the page (Ctrl+R / navigate away and back)
8. Check if "Москва" is still in the city field after reload
9. Check console for errors
EXPECT:
- Autocomplete works without TypeError
- City value persists after page reload
- 0 console errors

---

TASK: [REVERT] Procurement invoices workflow works correctly
URL: /procurement/{any_quote_with_items}

TEST 6: Create a procurement invoice
STEPS:
1. Navigate to any quote that has items (e.g., find one via /dashboard or /quotes)
2. Go to procurement workspace: /procurement/{quote_id}
3. If there are unassigned items, try creating a new invoice:
   - Select a supplier from dropdown
   - Select a buyer company
   - Set currency (e.g., USD)
   - Enter total weight (e.g., 10)
   - Select items to include
   - Click create/save button
4. Check if invoice appears in the invoices list on the page
5. Check console for errors — should be NO 500 errors or "column does not exist" errors
EXPECT:
- Invoice creates successfully (no server error)
- Invoice appears in the procurement workspace invoices list
- Status shows "Ожидает закупки" or similar workflow status (NOT "pending" payment status)
- 0 console errors

TEST 7: Finance Инвойсы tab shows procurement invoices
STEPS:
1. Navigate to /finance?tab=invoices (or click "Инвойсы" tab on /finance)
2. Check if any invoices are displayed in the table
3. If invoices exist, verify columns: invoice number, supplier, currency, status
4. Check console for errors
EXPECT:
- Инвойсы tab loads without errors
- If there are procurement invoices in the system, they appear here
- Status values are workflow statuses (e.g., pending_procurement), not payment statuses
- 0 console errors

REPORT_TO: .claude/test-ui-reports/report-20260211-0200-design-retest.md
