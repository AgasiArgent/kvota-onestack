BROWSER TEST
timestamp: 2026-02-15T14:00:00Z
session: 2026-02-14 #5
base_url: https://kvotaflow.ru

TASK: [86afdkuzq] Invoice horizontal layout
URL: /procurement/74aa8aba-09ec-4e78-8f89-216e633d6210 (Q-202601-0013, has invoices)
STEPS:
1. Login as admin (admin@test.kvota.ru / Test123!)
2. Navigate to a procurement page that has multiple invoices (try /procurement/{quote_id} for a quote with invoices)
3. Scroll to invoices section
4. Verify invoice cards display horizontally in a grid (side-by-side), NOT stacked vertically
5. If only 1 invoice, it should take full width
6. Check console for errors
EXPECT:
- Invoice cards in horizontal grid layout
- Cards wrap to next row if more than fit
- No layout breakage
- No console errors

TASK: [86afdkv0t] CBR exchange rates on Сводка tab
URL: /quotes/74aa8aba-09ec-4e78-8f89-216e633d6210 (Q-202601-0013)
STEPS:
1. Navigate to quote detail page
2. Click "Сводка" tab (should be default/first tab)
3. Find "ПОРЯДОК РАСЧЕТОВ" block (right side)
4. Check "Курс USD/RUB на дату КП" — should show actual rate (e.g. "88.1234 ₽"), NOT "—"
5. Check "Курс USD/RUB на дату СП" — shows rate if spec exists, or "—" if no spec
6. Check "Курс USD/RUB на дату УПД" — should show "—" (not implemented yet)
7. Check console for errors
EXPECT:
- At least the КП date rate shows a real number (not "—")
- Format: "XX.XXXX ₽" or similar
- No errors in console
- Page loads without delay (rates fetched quickly)

REPORT_TO: .claude/test-ui-reports/report-20260215-1400-session5.md
