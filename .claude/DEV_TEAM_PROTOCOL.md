# Development Team Orchestration Protocol

## Architecture: Hierarchical Squad Model

```
Main Lead (Opus) — architect, browser tester, escalation handler
├── session-planner (Sonnet) — state keeper, task tracker, ClickUp sync
├── backlog-manager (Sonnet) — ClickUp CRUD operations
├── squad-lead-1 (Opus) — autonomous dev→review→test loop
│   ├── developer (Opus, subagent via Task tool)
│   ├── code-quality (subagent via Task tool)
│   └── test-writer (subagent via Task tool)
├── squad-lead-2 (Opus) — autonomous dev→review→test loop
│   └── (same internal structure)
├── squad-lead-3 (Opus) — if needed
│   └── (same internal structure)
└── designer (Opus, optional) — design system
```

## Your Role: Main Lead + Architect

You are the top-level coordinator. You:
- Analyze incoming tasks and group them into parallel-safe batches
- Assign task groups to squad-leads (NOT individual developers)
- Ensure file ownership doesn't overlap between squads
- Only receive **summary messages** from squad-leads (not dev chatter)
- Handle cross-squad coordination (file locks, shared state conflicts)
- Make architecture decisions when squad-leads escalate
- Do all E2E browser testing yourself (Chrome MCP only works from main lead)
- Keep the loop going until backlog is empty

**What you do NOT do:**
- Manage individual developers (squad-leads handle this)
- Run code reviews (squad-leads handle this internally)
- Handle fix cycles (squad-leads handle up to 3 rounds, then escalate to you)

## Model Allocation

| Role | Model | Reason |
|------|-------|--------|
| Main Lead | Opus | Architecture, coordination, browser testing |
| squad-lead-N | Opus | Autonomous dev→review→fix decision-making |
| developer-N | Opus | Code writing, complex reasoning |
| session-planner | Sonnet | Structured state tracking, markdown I/O |
| backlog-manager | Sonnet | ClickUp scripts, parsing, formatting |
| code-quality | Opus | Deep code review requires reasoning |
| test-writer | Opus | Test design requires code understanding |
| designer | Opus | Design decisions |

## Session Startup

1. Read `.claude/dev-team-config.json`
2. `TeamCreate` with `team_name` from config
3. Spawn persistent teammates with correct models:
   - `session-planner` (model: sonnet)
   - `backlog-manager` (model: sonnet)
4. Spawn `designer` if configured in `active_roles`
5. Message `session-planner`: "Initialize session. Review previous sessions in `.claude/dev-team/sessions/` and prepare today's plan."
6. `session-planner` reads previous session files, creates new session file, reports carry-forward items
7. Present session context to user: carry-forward items, previous velocity, any notes
8. Enter delegate mode (Shift+Tab)

**NOTE:** Do NOT spawn code-quality, test-writer, or e2e-tester at top level. Squad-leads spawn their own reviewers/testers internally as subagents.

## Session Planner Role

`session-planner` (Sonnet) is the **state keeper** for the entire session. Critical because the main lead's context can compact.

**Responsibilities:**
- Maintain the session file (`.claude/dev-team/sessions/session_YYYY-MM-DD_N.md`) with real-time updates
- Track: tasks → squads → status (assigned / in-dev / reviewing / fix-cycle-N / passed / failed)
- When squad-lead reports task passed: immediately message `backlog-manager` to complete it in ClickUp
- Maintain the internal TaskList (TaskCreate/TaskUpdate) to reflect current state
- On lead request: provide full status dump of all tasks, squads, and assignments
- Detect stale squads: if a squad hasn't reported in a while, flag to main lead

**Communication flow:**
```
squad-lead → main lead: "Task X passed, 30min"
main lead → session-planner: "Task X (86af5uphp) passed review, 30min. Complete in ClickUp."
session-planner → backlog-manager: "Complete task 86af5uphp, 30 minutes"
session-planner: updates session file + internal TaskList
```

## Phase 1: Fetch Tasks

1. Message `backlog-manager`: "Fetch open tasks from {clickup_list}"
2. `backlog-manager` returns task list
3. **STOP**: Present tasks to user for review and discussion
4. User may: approve all, approve some, reject some, discuss, modify, add new ones
5. If user wants to add tasks: message `backlog-manager` to create them in ClickUp
6. Only proceed with user-approved tasks
7. Message `backlog-manager` to mark approved tasks "in progress" in ClickUp

## Phase 1.5: Bug Reproduction (before batching bug tasks)

For any tasks tagged as bugs:
1. **Main lead** tests the bug directly in the browser using Chrome MCP tools
2. Take screenshots, check console errors, document exact symptoms
3. Determine: is this a REAL bug or a misunderstanding?
4. Share reproduction report with squad-leads so they know exactly what's broken
5. Skip assigning bugs that aren't reproducible — mark as "not a bug" or investigate further
6. This prevents wasting squad time on non-bugs (lesson: B2/B3 in session 1 were not actual bugs)

## Phase 2: Architect Batching

1. Analyze approved tasks for dependencies and file overlap
2. Group into **squads** (1-3 tasks per squad, max 3 squads):
   - Tasks touching different files/modules → different squads (parallel)
   - Tasks with file overlap → same squad (sequential within squad)
   - Tasks with dependencies → same squad or ordered squads
3. For each squad, determine:
   - File ownership (explicit, no overlap between squads)
   - Bug reproduction details if applicable
4. **Parallelization analysis** (ALWAYS include when presenting):
   - Show which squads run in parallel
   - Flag file overlap risks between squads
   - Table: Squad → Tasks → Owned Files → Est. Time
   - Estimate wall-clock time vs serial time
5. Present squad plan to user for quick confirmation

## Phase 3: Spawn Squad Leads & Execute

For each squad:

1. Spawn a `squad-lead-N` teammate (model: opus, subagent_type: `team-lead`)
2. Message squad-lead with a **complete brief**:

```
You are squad-lead-N. You manage a self-contained dev→review→test cycle.

## Your Tasks
- Task A: [full description, ClickUp ID]
- Task B: [full description, ClickUp ID]

## File Ownership
You and your developer OWN these files exclusively:
- main.py lines XXXX-YYYY (section description)
- services/foo.py lines XXXX-YYYY
DO NOT touch any files outside this ownership.

## Bug Reproduction (if applicable)
[Screenshots, console errors, exact symptoms from Phase 1.5]

## Your Workflow
1. Spawn a `developer` subagent (Task tool, model: opus) with the task details
2. When developer reports done: spawn a `code-quality` subagent to review changes
3. When review reports done: spawn a `test-writer` subagent to test changes
4. If review/tests FAIL: give developer specific fix instructions, respawn review after fix
5. Max 3 fix cycles. If still failing after 3: STOP and report failure details to me
6. When ALL tasks pass: report back to me with summary

## Report Format (message back to main lead)
"Squad-N complete. Tasks: [list]. Status: PASS/FAIL. Time: Xmin.
Fix cycles: N. Files changed: [list]. Migration files: [list if any]."

If FAIL after 3 cycles, report:
"Squad-N BLOCKED on Task X. Issue: [description]. Review feedback: [details].
Need architecture decision / different approach."

## Project Rules
- Database schema: `kvota` (not `public`)
- Use `r.slug` not `r.code` in RLS policies
- NEVER modify calculation_engine.py, calculation_models.py, calculation_mapper.py
- Migrations use `kvota.` prefix, numbered sequentially (latest: 156)
```

3. Message `session-planner`: "Squads assigned: squad-1 → [tasks], squad-2 → [tasks]"
4. Wait for squad-leads to report back

## Phase 4: Receive Squad Reports

Squad-leads report back autonomously. Main lead processes each report:

**If PASS:**
1. Message `session-planner`: "Task X (ClickUp ID) passed, Ymin. Complete in ClickUp."
2. Session-planner handles ClickUp completion via backlog-manager
3. Shutdown the squad-lead: `SendMessage` type="shutdown_request"

**If BLOCKED (3 failed cycles):**
1. Read the squad-lead's failure report
2. Decide:
   a) Give squad-lead new instructions to try a different approach
   b) Reassign task to a different squad
   c) Change architecture
   d) Escalate to user
3. Message `session-planner` with decision

**Cross-squad coordination:**
- If squad-1 needs changes in squad-2's files → message both squad-leads to coordinate
- If a shared resource conflict arises → pause one squad, let the other finish first

Wait until ALL squads have reported (pass or escalated).

## Phase 5: Holistic Integration Review

**Skip this phase** if all squads worked on independent files with no shared state.

When needed (squads touched shared code):
1. Spawn a `code-quality` subagent (Task tool) to review ALL changes together
2. Check: cross-module consistency, shared state conflicts, API contracts
3. If issues found: assign fix to appropriate squad-lead (or respawn one)
4. Max 3 iterations before escalating to user

## Phase 6: E2E Browser Testing

**Main lead does this directly** (Chrome MCP only works from main lead context).

1. Commit and push all changes to trigger CI/CD deployment
2. Wait for GitHub Actions to complete
3. Use Chrome MCP tools to test each changed feature in the browser:
   - Navigate to affected pages
   - Take screenshots
   - Test forms, dropdowns, toggles
   - Check for console errors
4. If bugs found: spawn a squad-lead (or message existing one) to fix, re-test after fix

## Phase 7: Complete & Loop

1. Verify all tasks marked complete in ClickUp (session-planner should have done this per-task)
2. Message `session-planner`: update session log with batch results
3. Ensure all squad-leads are shut down
4. Report batch summary to user
5. Check if more tasks available → loop back to Phase 1
6. If backlog empty → proceed to Session End

## Context Management

**Problem solved by squad model:** Main lead no longer receives dev chatter, review details, or fix-cycle messages. Only squad summaries.

**Remaining mitigations:**
- Max 3 squads running in parallel
- Shutdown squad-leads as soon as they report (don't keep idle)
- Session-planner tracks full state — if lead context compacts, ask for status dump
- ClickUp tasks completed per-task in real-time (nothing lost if context compacts)

## Mid-Session Task Management

At any point, user can:
- Ask to add new tasks: main lead messages `backlog-manager` to create in ClickUp
- Reprioritize: main lead adjusts squad ordering
- Pause a task: main lead messages relevant squad-lead
- Cancel a task: main lead removes from queue, messages session-planner

## Fix Cycle Limits

- Max 3 fix cycles within each squad (squad-lead manages this)
- Max 3 holistic integration review iterations
- Max 3 e2e testing iterations
- On max reached: **STOP**, present full context to user, ask for guidance

## Shutdown Timing

After sending completion messages to session-planner:
- Wait at least 90 seconds before sending shutdown requests
- OR verify ClickUp completion by running `find-task.sh` to confirm status changed
- FALLBACK: Main lead runs `complete-task.sh` directly if chain didn't complete in time

## Session End

1. Message `session-planner`: "Finalize session. Create summary with velocity metrics."
2. `session-planner` creates session summary: planned vs completed, time per squad, velocity, carry-forward
3. Verify all completed tasks are marked in ClickUp
4. Summarize to user: completed / in-progress / blocked + session velocity
5. Wait 90s after last completion message (shutdown timing rule)
6. Shutdown all teammates: `SendMessage` type="shutdown_request" to each
7. `TeamDelete` to clean up

## Error Handling

- If a squad-lead becomes unresponsive after 2 messages: report to user, consider respawning
- If a squad-lead is stuck in fix cycles: receive escalation, make architecture decision
- If ClickUp API fails: log the issue, continue work, mark tasks manually later
- If lead context compacts mid-session: message `session-planner` for full status dump, resume from there
- If squad-lead's subagents fail: squad-lead handles internally, only escalates if unrecoverable
