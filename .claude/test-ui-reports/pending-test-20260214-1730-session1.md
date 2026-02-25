BROWSER TEST
timestamp: 2026-02-14T17:30:00Z
session: 2026-02-14 #1
base_url: https://kvotaflow.ru

TASK: [86afdkuux] Re-verify quote_items.name bug fix
URL: /procurement/482c0486-cebe-410e-a670-364a32feecb4
STEPS:
1. Login as admin (admin@test.kvota.ru / Test123!)
2. Navigate to /procurement/482c0486-cebe-410e-a670-364a32feecb4
3. Click "Редактировать" on existing invoice (INV-01-Q-202602-0092)
4. Click "Сохранить" without changes
5. Verify NO error "column quote_items.name does not exist"
6. Check console for 500 errors
EXPECT:
- Invoice saves successfully (no 500 error)
- Page re-renders invoices list correctly
- Item names display correctly in invoice details

TASK: [86afdkuva] Conditional download button visibility
URL: /quotes (find quotes at different statuses)
STEPS:
1. Find a quote in "draft" status → open detail page
   - EXPECT: Only "Валидация Excel" button visible (no КП PDF, no Счёт PDF)
2. Find a quote in "pending_procurement" or similar prep status
   - EXPECT: Only "Валидация Excel" button visible
3. Find a quote in "approved" or "sent_to_client" status
   - EXPECT: Only "КП PDF" button visible (no Валидация Excel, no Счёт PDF)
4. Find a quote in "pending_spec_control" or "pending_signature" status
   - EXPECT: Only "КП PDF" button visible
5. Find a quote in "deal" status (check via /deals page if needed)
   - EXPECT: "КП PDF" AND "Счёт PDF" buttons both visible
6. Verify NO "Спецификация DOC" button anywhere (was removed)
EXPECT:
- Buttons appear/disappear correctly based on workflow status
- No JavaScript errors in console

TASK: [86afdkuvh] Logistics cost display on Продажи tab
URL: /quotes/{id}?tab=overview (find a quote with logistics data)
STEPS:
1. Find a quote that has logistics costs filled (check Логистика tab has data)
2. Switch to Продажи (overview) tab
3. Look at the "Итого" block at the bottom
4. Check if "Логистика:" row shows an actual number (not "—")
5. If no quote has logistics data: check a quote without logistics → should show "—" or 0
6. Check console for errors
EXPECT:
- Logistics cost shows calculated amount (not "—") when invoices have logistics data
- Shows "—" when no logistics data exists
- No console errors

REPORT_TO: .claude/test-ui-reports/report-20260214-1730-session1.md
