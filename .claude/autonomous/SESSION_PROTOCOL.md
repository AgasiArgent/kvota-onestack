# Session Protocol

**MANDATORY: Execute this checklist at the START of every session.**

## Before Starting Work

1. [ ] **Verify location**: Run `pwd` - must be `/Users/andreynovikov/workspace/tech/projects/kvota/onestack`
2. [ ] **Read specification**: `cat .claude/autonomous/app_spec.xml` (first session, or if confused about requirements)
3. [ ] **Read progress**: `cat .claude/autonomous/claude-progress.txt | tail -50`
4. [ ] **Check git state**: `git log --oneline -5` and `git status`
5. [ ] **Review features**: Read `.claude/autonomous/features.json`
6. [ ] **Find next feature**: First item where `passes: false` and `in_progress: false`
7. [ ] **Mark in_progress**: Update features.json with `in_progress: true` and `started_at`
8. [ ] **Start environment**: `./.claude/autonomous/init.sh`
9. [ ] **Health check**: Open http://localhost:5001 and verify app responds

## Project Context

**Stack:** Python FastHTML + HTMX + Supabase PostgreSQL + python-telegram-bot

**Key Files:**
- `main.py` - All routes and views (2100+ lines)
- `calculation_engine.py` - 13-phase pricing calculator
- `services/` - Database, exports, versions
- `.claude/autonomous/app_spec.xml` - Full specification

**Existing Functionality:**
- Quote CRUD with products
- Calculation engine with 42 variables
- Version snapshots
- PDF/Excel exports
- Basic authentication (no roles yet)

**What We're Adding:**
- 9 roles (sales, procurement, logistics, customs, quote_controller, spec_controller, finance, top_manager, admin)
- Multi-step workflow with status transitions
- Telegram notifications and approvals
- Specifications and deals as separate entities
- Plan-fact financial tracking

## During Work

- Work on **ONE feature only** at a time
- Reference `app_spec.xml` for:
  - Database schema (new tables, field names)
  - Workflow statuses and transitions
  - Role permissions
  - API endpoints
  - UI screens
- Run server and test manually after changes
- Commit after meaningful progress with descriptive messages
- Update `claude-progress.txt` with session notes

## Database Changes

When creating new tables or modifying existing ones:
1. Write SQL migration in `migrations/` folder
2. Test migration in Supabase SQL Editor first
3. Document migration in progress log
4. Consider RLS policies for new tables

## Testing Checklist

After implementing a feature:
- [ ] Server starts without errors
- [ ] No Python syntax errors
- [ ] Feature works as expected in browser
- [ ] Existing functionality not broken
- [ ] Database queries return expected data

## After Completing Feature

1. [ ] Test the feature manually
2. [ ] Update `features.json`: `passes: true`, `in_progress: false`, `completed_at: now`
3. [ ] Append summary to `claude-progress.txt`:
   ```
   ## Session [date] - Feature [id]: [name]
   - What was done
   - Any issues encountered
   - Next steps
   ```
4. [ ] Git commit with message referencing feature ID
5. [ ] Continue to next feature or report completion

## If Stuck

After 3-5 failed attempts on a feature:
1. Document the blocker in `claude-progress.txt`
2. Set feature `in_progress: false` (keep `passes: false`)
3. Add note about what was tried
4. Move to next feature that doesn't depend on this one
5. OR stop and report blocker to user

## Commit Message Format

```
feat(category): short description

- Detail 1
- Detail 2

Feature #[id] from features.json
```

Example:
```
feat(database): add roles and user_roles tables

- Created roles table with 9 predefined roles
- Created user_roles junction table
- Added RLS policies

Feature #1, #2 from features.json
```

## Reference Files

- **Spec**: `.claude/autonomous/app_spec.xml`
- **Features**: `.claude/autonomous/features.json`
- **Progress**: `.claude/autonomous/claude-progress.txt`
- **Main app**: `main.py`
- **Calc engine**: `calculation_engine.py`
