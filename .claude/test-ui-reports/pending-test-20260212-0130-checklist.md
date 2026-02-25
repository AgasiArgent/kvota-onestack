BROWSER TEST
timestamp: 2026-02-12T01:30:00
session: 2026-02-11 #2
base_url: https://kvotaflow.ru

LOGIN: Use admin account (Test123!)

TASK: [checklist-modal] Sales checklist modal appears before submitting to procurement
URL: https://kvotaflow.ru/quotes
STEPS:
1. Login as admin
2. Navigate to /quotes and find a quote in ЧЕРНОВИК (draft) status with at least 1 item
3. Open the quote detail page
4. Click "Передать в закупки" button
5. Verify a MODAL dialog appears (not immediate submission)
6. Modal should contain:
   - Title: "Контрольный список перед передачей в закупки" or similar
   - Checkbox: "Это проценка?"
   - Checkbox: "Это тендер?"
   - Checkbox: "Запрашивал ли клиент напрямую?"
   - Checkbox: "Запрашивал ли клиент через торгующих организаций?"
   - Textarea: "Что это за оборудование и для чего оно необходимо?" (required)
   - Cancel and Submit buttons
7. Try clicking Submit WITHOUT filling textarea — should show validation error
8. Fill in: check "Это тендер", check "Запрашивал ли клиент напрямую", type "Тестовое оборудование для проверки системы" in textarea
9. Click Submit
10. Verify quote status changes to "Ожидает закупки" or similar pending_procurement status
11. Check console for errors
EXPECT: Modal gates transition, validation works, status changes on submit

TASK: [checklist-procurement-view] Procurement sees checklist answers
URL: https://kvotaflow.ru/procurement
STEPS:
1. Navigate to the procurement page for the quote submitted in previous test
2. Look for a yellow info card with title like "Информация от отдела продаж"
3. Verify it shows:
   - Проценка: Нет
   - Тендер: Да
   - Прямой запрос: Да
   - Через торгующую организацию: Нет
   - Описание оборудования: "Тестовое оборудование для проверки системы"
4. Check console for errors
EXPECT: Yellow card visible with all checklist answers correctly displayed

REPORT_TO: .claude/test-ui-reports/report-20260212-0130-checklist.md
