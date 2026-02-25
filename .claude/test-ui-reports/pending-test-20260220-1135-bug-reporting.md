BROWSER TEST
timestamp: 2026-02-20T11:35:00+03:00
session: 2026-02-20 #1
base_url: https://kvotaflow.ru

TASK: Enhanced bug reporting widget with screenshot annotation
URL: /tasks (any page with the feedback widget)
STEPS:
1. Login as admin@test.kvota.ru / Test123!
2. Navigate to /tasks page
3. Click the bug icon (floating bottom-right, grey circle)
4. Verify modal opens with: category dropdown (Ошибка/Предложение/Вопрос), description textarea, "Добавить скриншот" button
5. Type "Тестовое обращение" in description
6. Click "Добавить скриншот" button
7. Verify fullscreen annotation editor opens with toolbar: Кисть (brush), Стрелка (arrow), Текст (text), Отменить (undo), Готово (save), X (cancel)
8. Draw something with the brush tool (click and drag on canvas)
9. Click "Готово" to save annotation
10. Verify modal now shows screenshot thumbnail preview
11. Click "Отправить" to submit feedback
12. Verify success message appears
13. Check browser console for errors (F12 → Console)
EXPECT: Modal opens, annotation editor works, screenshot preview shows, submission succeeds

TASK: Admin feedback management page
URL: /admin/feedback
STEPS:
1. Stay logged in as admin@test.kvota.ru
2. Navigate to /admin/feedback (via sidebar "Обращения" link under Администрирование)
3. Verify "Обращения" link exists in sidebar under Администрирование section
4. Verify feedback list page loads with table of feedback entries
5. Check the test submission from previous task appears in the list
6. Click on the test submission row to open detail page
7. Verify detail page shows: description, screenshot (if attached), debug context info, status form, ClickUp link (if configured)
8. Change status from "Новый" to "В работе" using the dropdown
9. Click save/update button
10. Verify status updates successfully
11. Navigate back to /admin/feedback
12. Verify status filter dropdown works (filter by "В работе")
13. Check browser console for errors
EXPECT: Admin page loads, shows feedback entries, status management works, screenshot displays

TASK: Backward compatibility — text-only feedback
URL: /tasks
STEPS:
1. Click bug icon
2. Type "Тестовый баг без скриншота" in description
3. Do NOT click "Добавить скриншот"
4. Click "Отправить"
5. Verify submission succeeds without screenshot
6. Go to /admin/feedback and verify new entry appears without screenshot
EXPECT: Text-only feedback still works (backward compatible)

REPORT_TO: .claude/test-ui-reports/report-20260220-1135-bug-reporting.md
