# Project Manager Memory

## Velocity Metrics
- Session 1 (2026-02-06): 10 tasks, 4 parallel devs, 0 fix cycles
- Session 2 (2026-02-06): 3 tasks, ~30min, squad model, 1 fix cycle
- Session 3 (2026-02-07): 5 tasks, 3 features + 2 bugs
- Session 4 (2026-02-08): 2 tasks, lean mode, route audit focus
- Session 5 (2026-02-08): 2 tasks, TDD DaData + city autocomplete
- Session 6 (2026-02-08): 2 tasks, TDD customer modal + HERE city autocomplete, 0 fix cycles
- Session 7 (2026-02-09): 4 VERIFY tasks deployed, then post-session rework (1 reverted: payments)
- Running average: 4.0 tasks/session (28 total / 7 sessions, but 1 reverted)

## ClickUp Patterns
- kvota list has 56 tasks (39 existing + 17 new as of session 8 init)
- sprint list is empty
- Scripts work reliably: list-tasks.sh, start-work.sh, complete-task.sh
- Task IDs are alphanumeric (e.g., 86af5uphp)
- **CRITICAL PROCESS**: Do NOT mark tasks complete until team-lead explicitly confirms after browser testing. Flow: dev implements -> tests pass -> code review PASS -> team-lead browser tests -> THEN complete in ClickUp.

## Session Patterns
- Sessions file at: .claude/dev-team/sessions/session_YYYY-MM-DD_N.md
- Current latest migration: 159
- Session 7 had first revert: spec payments removed post-session (payments belong on deals, not specs)
- ClickUp scripts path changed: no shell scripts, use direct API calls per skill.md
- create-task.sh exists at ~/.claude/skills/clickup-backlog/create-task.sh (but API is more flexible)
- list-tasks.sh does NOT exist; use direct API: curl to /api/v2/list/{LIST_ID}/task

## Completed ClickUp Task IDs (do not re-assign)
- 86af5uphp, 86af5upkw, 86af5upn7, 86af5up7z, 86af5upd9
- 86af5upf7, 86af5uq32, 86af5uq44, 86af5wenr, 86af5wenz
- 86af5wepg, 86af5up5y, 86af5upax, 86af5upq7
- 86af5wqng, 86aezuyvy (route audit, clickable rows)
- 86af159nn (INN autofill / customer modal) -- COMPLETE
- 86aezuyvw (city autocomplete / HERE geocoding) -- COMPLETE
