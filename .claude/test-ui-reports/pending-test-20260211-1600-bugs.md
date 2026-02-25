BROWSER TEST
timestamp: 2026-02-11T16:00:00
session: 2026-02-11
base_url: https://kvotaflow.ru

LOGIN: Use test sales account (Test123! password) or existing session

TASK: [B1] Customer Profile — tabs not loading data
URL: https://kvotaflow.ru/customers/b926bfd0-4934-46d9-8ff1-6ebdd07ee7d0?tab=general
STEPS:
1. Navigate to customer profile page
2. Click "КП" tab — check if quotes load
3. Click "Спецификации" tab — check if specs load
4. Click "Запрашиваемые позиции" tab — check if items load
5. Click "Договоры" tab — check if contracts load
6. Check console for errors on each tab
7. Try another customer if available to see if issue is customer-specific or global
EXPECT: Each tab should show data (or "Нет данных" if empty). Report any errors, blank screens, or loading failures.

TASK: [B2] Dashboard Закупки tab — crash
URL: https://kvotaflow.ru/dashboard?tab=overview
STEPS:
1. Navigate to dashboard
2. Click "Закупки" tab
3. Check if error message appears: "Ошибка загрузки данных закупок"
4. Check console for: "sequence item 0: expected str instance, NoneType found"
5. Take screenshot of the error
EXPECT: Report exact error message and console output. This may be a NoneType in a string join.

TASK: [B3] Seller Company edit — update fails
URL: https://kvotaflow.ru/seller-companies
STEPS:
1. Navigate to seller companies list
2. Click on any existing company to open edit page
3. Try to edit a field (e.g. change name slightly)
4. Click Save/Update
5. Check if error appears: "Не удалось обновить компанию. Возможно, код или ИНН уже используются другой компанией."
6. Check console for errors
7. ALSO test buyer companies: navigate to /admin?tab=buyer-companies
8. Try editing a buyer company similarly
9. Report if same error occurs
EXPECT: Report whether edit works or fails for both seller and buyer companies. Include exact error messages.

TASK: [B4] Deal Logistics tab — broken display
URL: https://kvotaflow.ru/finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742
STEPS:
1. Navigate to deal detail page
2. Look at the Logistics section/tab
3. Check if data entry fields and buttons are poorly laid out
4. Take screenshot of current state
5. Compare with other data entry sections (e.g. plan-fact tab) for reference
6. Check console for errors
EXPECT: Report what looks broken — field alignment, button placement, missing labels, overflow issues. Take screenshots.

REPORT_TO: .claude/test-ui-reports/report-20260211-1600-bugs.md
