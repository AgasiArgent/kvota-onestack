BROWSER TEST
timestamp: 2026-02-11T23:30:00
session: 2026-02-11 #2
base_url: https://kvotaflow.ru

LOGIN: Use admin account (Test123!) or existing session

TASK: [fix-tabs] Tab clicking no longer duplicates page
URL: https://kvotaflow.ru/finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742
STEPS:
1. Navigate to deal detail page (DEAL-2026-0002)
2. Click "План-факт платежей" tab
3. Page should switch to plan-fact tab WITHOUT duplicating header/sidebar/layout
4. Click "Логистика" tab — same, no duplication
5. Click "Основное" tab — same, no duplication
6. Check console for errors
EXPECT: Tab switching works via page navigation, no nested page duplication

TASK: [fix-redirect] Logistics expense redirects to logistics tab
URL: https://kvotaflow.ru/finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742?tab=logistics
STEPS:
1. Navigate to logistics tab
2. Click "Добавить расход" on any stage (e.g. Хаб-Хаб)
3. Modal opens with pre-selected category
4. Fill in amount=25, currency=RUB, date=today
5. Submit
6. After submit, page should reload to ?tab=logistics (NOT ?tab=plan-fact)
7. Check console for errors
EXPECT: After logistics expense submit, stays on logistics tab

TASK: [horizontal-cards] Logistics stage cards are horizontal grid
URL: https://kvotaflow.ru/finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742?tab=logistics
STEPS:
1. Navigate to logistics tab
2. Verify stage cards are displayed in a horizontal grid (not vertical stack)
3. Should be roughly 3-4 cards per row on desktop
4. Each card is compact: stage name, status badge, expense count, action buttons
5. Cards should NOT list individual expenses (just count + total)
6. Check console for errors
EXPECT: Compact horizontal cards in CSS grid, responsive layout

TASK: [file-upload] Payment modal has file upload field
URL: https://kvotaflow.ru/finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742?tab=plan-fact
STEPS:
1. Navigate to plan-fact tab
2. Click green "+ Добавить платёж" button
3. Modal opens
4. Switch to "Новый платёж" mode
5. Verify there is a "Файл документа" or similar file upload field
6. Select any small PDF or image file
7. Fill in: category=Прочее, amount=10, currency=RUB, date=today
8. Submit
9. Verify payment appears in table
10. Check console for errors
EXPECT: File upload field present in modal, payment saves with or without file

REPORT_TO: .claude/test-ui-reports/report-20260211-2330-fixes2.md
