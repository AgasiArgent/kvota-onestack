BROWSER TEST
timestamp: 2026-02-20T13:00:00+03:00
session: 2026-02-20 #1 (ClickUp integration + bidirectional status sync)
base_url: https://kvotaflow.ru

CONTEXT: Added ClickUp env vars on VPS (CLICKUP_API_KEY, CLICKUP_BUG_LIST_ID=901324690894 — Kvota list).
Implemented bidirectional status sync: admin→ClickUp on status change, ClickUp→admin via sync button.
Fixed initial task status from "Open" to "to do" (matching Kvota list).
Committed 6499888, pushed. Wait for CI/CD to deploy before testing.
IMPORTANT: Hard-refresh the page (Ctrl+Shift+R) to clear cached JS.

TASK: ClickUp ticket creation on bug submission
URL: /tasks
STEPS:
1. Login as admin@test.kvota.ru / Test123!
2. Hard-refresh page (Ctrl+Shift+R)
3. Click bug icon (floating bottom-right)
4. Type "Тест ClickUp тикета" in description
5. Click "Отправить" (without screenshot, to keep it simple)
6. Verify success toast appears
7. Navigate to /admin/feedback
8. Find "Тест ClickUp тикета" entry at top (should be FB-YYMMDD...)
9. Verify ClickUp column shows a task ID (NOT "—")
10. Click the task ID link — it should open ClickUp in new tab
11. Verify ClickUp task exists with title "[Bug] Тест ClickUp тикета #FB-..."
12. Verify ClickUp task status is "to do"
13. Check console — no errors
EXPECT: ClickUp ticket auto-created with correct title, priority, and "to do" status

TASK: Admin→ClickUp status sync (close in admin → closes in ClickUp)
URL: /admin/feedback
STEPS:
1. Navigate to /admin/feedback
2. Click the entry from previous task ("Тест ClickUp тикета")
3. On detail page, verify ClickUp link is visible with sync button
4. Change status dropdown to "Закрыто"
5. Click "Сохранить"
6. Verify message shows "Сохранено: Закрыто (ClickUp обновлён)"
7. Click the ClickUp link to open the task in ClickUp
8. Verify ClickUp task status changed to "complete"
9. Check console — no errors
EXPECT: Changing status to "Закрыто" in admin syncs to "complete" in ClickUp

TASK: ClickUp→Admin status sync (change in ClickUp → sync button pulls change)
URL: ClickUp + /admin/feedback
STEPS:
1. In ClickUp (the task from previous test), change status from "complete" back to "in progress"
2. Return to /admin/feedback detail page for the same entry
3. Note the current status shows "Закрыто"
4. Click "Синхронизировать из ClickUp" button
5. Verify message shows "Синхронизировано: Закрыто → В работе"
6. Verify status dropdown updated to "В работе"
7. Reload the page to confirm status persisted
8. Check console — no errors
EXPECT: ClickUp→Admin sync pulls updated status correctly

TASK: Status sync with no ClickUp task (old entries)
URL: /admin/feedback
STEPS:
1. Navigate to /admin/feedback
2. Click on an older entry that has "—" in ClickUp column (e.g. FB-260130...)
3. Verify there is NO "Синхронизировать из ClickUp" button (since no task_id)
4. Change status to "В работе" and save
5. Verify "Сохранено: В работе" (no ClickUp sync message since no task_id)
6. Check console — no errors
EXPECT: Old entries without ClickUp task_id work normally, no sync attempts

REPORT_TO: .claude/test-ui-reports/report-20260220-1300-clickup-sync.md
