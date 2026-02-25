BROWSER TEST
timestamp: 2026-02-15T15:00:00Z
session: 2026-02-14 #5 (invoice fix)
base_url: https://kvotaflow.ru

TASK: [86afdkuzq] Invoice horizontal layout (fix retry)
URL: /procurement/74aa8aba-09ec-4e78-8f89-216e633d6210 (Q-202601-0013)
STEPS:
1. Login as admin (admin@test.kvota.ru / Test123!)
2. Navigate to /procurement/74aa8aba-09ec-4e78-8f89-216e633d6210
3. Scroll to ИНВОЙСЫ section
4. Verify invoice cards are full-width (NOT in a 280px sidebar)
5. Verify cards display in horizontal grid (side-by-side if multiple)
6. Verify ПОЗИЦИИ table is below invoices (stacked, not side-by-side)
7. Check that invoice card click/expand still works
8. Check console for errors
EXPECT:
- Invoice cards take full page width
- Grid layout: repeat(auto-fit, minmax(280px, 1fr))
- NOT a narrow sidebar — previous bug was 280px sidebar column
- Items table below invoices, also full width
- No console errors

REPORT_TO: .claude/test-ui-reports/report-20260215-1500-invoice-fix.md
