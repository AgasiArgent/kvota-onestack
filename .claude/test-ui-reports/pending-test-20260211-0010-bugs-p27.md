BROWSER TEST
timestamp: 2026-02-11T00:10:00+03:00
session: 2026-02-10 #1
base_url: https://kvotaflow.ru

TASK: [BUG-2] Delivery city saves correctly
URL: /quotes/{any_quote}

TEST 1: City field saves on blur
STEPS:
1. Navigate to /quotes and open any quote (e.g., Q-202602-0073)
2. Find the delivery city field (inline editable)
3. Click the city field, type a new value or change existing
4. Click outside the field (blur)
5. Reload the page
6. Verify the city value persisted after reload
7. Check console for errors
EXPECT:
- City saves on blur without needing to click a separate save button
- No console errors
- Value persists after page reload

---

TASK: [BUG-3] Procurement invoice expand/collapse
URL: /procurement/{any_quote_with_invoices}

TEST 2: Invoice card expands to show items
STEPS:
1. Navigate to /quotes and find a quote with procurement data (e.g., Q-202602-0073)
2. Go to the procurement tab/page for that quote
3. Find an invoice card in the list
4. Look for a clickable expand/chevron icon on the invoice card
5. Click the chevron/expand button
6. Verify invoice items (product lines) appear below the card
7. Click again to collapse
8. Verify items hide
9. Check console for errors
EXPECT:
- Invoice card has a clickable chevron/expand icon
- Clicking expands to show invoice items with details
- Clicking again collapses the details
- No console errors

---

TASK: [BUG-4] Customs shows АРТИКУЛ column
URL: /customs/{any_quote_with_items}

TEST 3: Customs Handsontable has АРТИКУЛ column
STEPS:
1. Navigate to /quotes and find a quote with items (e.g., Q-202602-0073)
2. Go to the customs page for that quote
3. Look at the Handsontable spreadsheet
4. Verify there is an "Артикул" column header (product code / SKU)
5. Verify existing items show their product_code in that column
6. Verify the column is read-only (cannot edit product codes in customs)
7. Check console for errors
EXPECT:
- "Артикул" column visible in the customs Handsontable
- Product codes displayed for items that have them
- Column is read-only
- No console errors

TEST 4: Customs completion blocked without HS codes
STEPS:
1. On the customs page, find an item without an HS code
2. Try to complete customs (click the complete button)
3. Verify an error/warning appears about missing HS codes
4. Fill in HS codes for all items
5. Try to complete again
6. Verify it succeeds
EXPECT:
- Cannot complete customs without HS codes on all items
- Clear error message about which items are missing HS codes
- Completes successfully when all HS codes are filled

---

TASK: [BUG-5] Supplier invoices appear in registry
URL: /procurement/{any_quote} and then /finance (invoices tab)

TEST 5: Invoice created in procurement appears in registry
STEPS:
1. Navigate to /quotes and find a quote ready for procurement
2. Go to procurement page
3. Create a new invoice (add supplier, items, save)
4. Navigate to /finance → look for an "Инвойсы" or supplier invoices tab/section
5. Verify the invoice you just created appears in the registry list
6. Check console for errors
EXPECT:
- Newly created invoice appears in the finance/invoices registry
- Invoice data matches what was entered (supplier, amounts)
- No console errors

---

TASK: [P2.7+P2.8] Logistics stages on deal detail page
URL: /finance/{deal_id}

TEST 6: Logistics section visible on deal detail
STEPS:
1. Navigate to /deals (or /finance → deals section)
2. Open any deal (e.g., DEAL-2026-0001 or DEAL-2026-0002)
3. Look for a "ЛОГИСТИКА" section or tab on the deal detail page
4. Verify 7 logistics stages are displayed:
   - FIRST MILE (Первая миля)
   - HUB (Хаб консолидации)
   - CUSTOMS CLEARANCE (Таможенное оформление)
   - LAST MILE (Последняя миля)
   - GTD UPLOAD (Загрузка ГТД)
   - DELIVERY (Доставка клиенту)
   - COMPLETION (Завершение)
5. Each stage should show: name, status badge (ожидание/в процессе/завершён)
6. Check console for errors
EXPECT:
- "ЛОГИСТИКА" section visible on deal page
- 7 stages listed with Russian names
- Each stage has a status indicator
- No console errors

TEST 7: Stage status can be updated
STEPS:
1. On the deal detail page, find a logistics stage in "ожидание" status
2. Look for a way to change status (dropdown, button, or click)
3. Change status to "В процессе"
4. Verify the status badge updates
5. Verify started_at timestamp appears
6. Change status to "Завершён"
7. Verify completed_at timestamp appears
8. Check console for errors
EXPECT:
- Status can be changed via UI control
- started_at appears when moved to "В процессе"
- completed_at appears when moved to "Завершён"
- Changes persist after page reload

TEST 8: Expense can be added to a stage
STEPS:
1. On the deal detail page, find the FIRST MILE stage
2. Look for "Добавить расход" button or similar
3. Click to add an expense
4. Fill in: description, amount, currency
5. Save the expense
6. Verify it appears under the stage
7. Check console for errors
EXPECT:
- Add expense button exists on expense-eligible stages
- Form accepts description, amount, currency
- Saved expense appears in stage's expense list
- No console errors

TEST 9: /deals/{deal_id} redirects to /finance/{deal_id}
STEPS:
1. Navigate directly to /deals/{deal_id} (e.g., /deals/ad66b5c0-93b7-44e7-8a83-18ad6ea33742)
2. Verify you are redirected to /finance/{deal_id}
3. Verify the full deal detail page loads with all sections
EXPECT:
- 301 redirect from /deals/ to /finance/
- All deal sections load correctly after redirect

---

## Regression Check

After all tests, verify these pages still work:
- /quotes (list loads, no errors)
- /quotes/{id} (detail page with all tabs)
- /finance (main finance page)
- /deals (deals list, if separate from finance)

REPORT_TO: .claude/test-ui-reports/report-20260211-0010-bugs-p27.md
