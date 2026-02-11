# Project Manager Memory

## Velocity Metrics
- Session 1 (2026-02-06): 10 tasks, 4 parallel devs, 0 fix cycles
- Session 2 (2026-02-06): 3 tasks, ~30min, squad model, 1 fix cycle
- Session 3 (2026-02-07): 5 tasks, 3 features + 2 bugs
- Session 4 (2026-02-08): 2 tasks, lean mode, route audit focus
- Session 5 (2026-02-08): 2 tasks, TDD DaData + city autocomplete
- Session 6 (2026-02-08): 2 tasks, TDD customer modal + HERE city autocomplete, 0 fix cycles
- Session 7 (2026-02-09): 4 VERIFY tasks deployed, then post-session rework (1 reverted: payments)
- Session 8 (2026-02-10): 15 tasks, marathon session, core flow validation + P2 features + bugs + design audit
- Session 9 (2026-02-11): 2 tasks, FK null-safety fix (44 patterns, 61 tests) + migration 168 roles cleanup (86->12)
- Running average: 5.0 tasks/session (45 total / 9 sessions)

## ClickUp Patterns
- kvota list ID: 901324690894 (45 tasks, ~30 open after session 8 completions)
- sprint 2 list ID: 901325258087 (6 tasks)
- sprint list is empty
- No shell scripts exist; use direct ClickUp API calls per skill.md
- find-task.sh does NOT exist; search by listing tasks and filtering client-side
- Time tracking: use start/end timestamps (not just duration); response only returns entry ID
- Task IDs are alphanumeric (e.g., 86af5uphp)
- **CRITICAL PROCESS**: Do NOT mark tasks complete until team-lead explicitly confirms after browser testing. Flow: dev implements -> tests pass -> code review PASS -> team-lead browser tests -> THEN complete in ClickUp.

## Session Patterns
- Sessions file at: .claude/dev-team/sessions/session_YYYY-MM-DD_N.md
- Current latest migration: 168
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
- 86af8hc87 (P1.1 Quote creation IDN) -- COMPLETE
- 86af8hcea (P1.2 Procurement pricing) -- COMPLETE
- 86af8hcmv (P1.3 Janna checklist) -- COMPLETE
- 86af8hcyx (P1.4 PDF generation IDN) -- COMPLETE
- 86af8hdah (P1.5 2-stage approval) -- COMPLETE
- 86af8hdcx (P1.6 Spec IDN-SKU + ERPS) -- COMPLETE
- 86af8hdg2 (P1.7 Spec signing -> Deal) -- COMPLETE
- 86af972h9 (BUG: spec form persistence) -- COMPLETE, 180min
- 86af972k0 (BUG: deal creation admin signing) -- COMPLETE, 60min
- 86af972nv (BUG: ERPS spec_sum_usd) -- COMPLETE, 30min
- 86af972pq (BUG: spec-control duplicate) -- COMPLETE, 30min
- 86af972qz (BUG: deal visibility FK) -- COMPLETE, 30min
- 86af8hdkh (P1.8 payment indicators) -- COMPLETE, 30min
- 86af8hdrv (P2.2 IDN-SKU validation) -- COMPLETE, 20min
- 86af8hdvm (P2.3 cost analysis dashboard) -- COMPLETE, 30min
- 86af8hdxw (P2.4+P2.5 payments tab) -- COMPLETE, 40min
- 86af8hedb (P2.6+P2.10 document chain) -- COMPLETE, 30min
- 86af8he4g (P2.7 logistics stages) -- COMPLETE, 20min
- 86af8he6t (P2.8 logistics payments) -- COMPLETE, 20min
- 86af9jptd (Design audit 27 items) -- CREATED+COMPLETE, 60min
- 86af9jpu6 (Invoice architecture revert) -- CREATED+COMPLETE, 30min
- 86af9jpuz (BUG-2 city save fix) -- CREATED+COMPLETE, 15min
- 86afac4p5 (FK null-safety crash fix) -- CREATED+COMPLETE, 90min
- 86afac4t0 (Migration 168 roles cleanup) -- CREATED+COMPLETE, 30min
