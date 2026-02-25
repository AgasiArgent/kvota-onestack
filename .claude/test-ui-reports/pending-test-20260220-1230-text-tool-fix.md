BROWSER TEST
timestamp: 2026-02-20T12:30:00+03:00
session: 2026-02-20 #1 (text annotation tool fix)
base_url: https://kvotaflow.ru

CONTEXT: Fixed text annotation tool that was not producing visible text on canvas.
Changes: guard against double-creation, delayed focus, stopPropagation on input click,
better styling with placeholder. Committed 71e4f2f, pushed to main.
IMPORTANT: Hard-refresh the page (Ctrl+Shift+R) to clear cached JS before testing.

TASK: Text annotation tool
URL: /tasks
STEPS:
1. Login as admin@test.kvota.ru / Test123!
2. Hard-refresh page (Ctrl+Shift+R) to load new JS
3. Click bug icon (floating bottom-right)
4. Type "Тест текстового инструмента" in description
5. Click "Добавить скриншот"
6. Verify annotation editor opens (fullscreen overlay)
7. Select "Текст" (Text) tool from toolbar
8. Click on the canvas at some point
9. Verify: a red-bordered text input appears at click location with placeholder "Введите текст..."
10. Type "Hello тест" into the input
11. Press Enter
12. Verify: red bold text "Hello тест" appears on the canvas at the click location
13. Select "Текст" tool again
14. Click a different location on canvas
15. Type "Second text" and click away (blur the input)
16. Verify: text committed on blur too (not just Enter)
17. Click "Готово" to save screenshot
18. Verify modal shows screenshot thumbnail with both text annotations visible
19. Click "Отправить"
20. Verify success toast appears
21. Check console — no errors
EXPECT: Text tool creates visible text input, text appears on canvas on Enter and on blur

TASK: Text tool edge cases
URL: /tasks
STEPS:
1. Click bug icon
2. Click "Добавить скриншот"
3. Select "Текст" tool
4. Click on canvas — input appears
5. Press Escape — input should disappear without adding text
6. Click on canvas again — new input should appear (not blocked)
7. Type something, press Enter — text should appear
8. Also try: click "Текст", click canvas, type text, then switch to "Кисть" (Brush) tool — text should commit
9. Click "Готово" to save
10. Click "Отправить" (or Cancel)
EXPECT: Escape cancels, re-clicking works after cancel, tool switch commits text

REPORT_TO: .claude/test-ui-reports/report-20260220-1230-text-tool-fix.md
