# Overnight Session — OneStack Workflow Extension

## Your Reference Files

1. **Specification**: `.claude/autonomous/app_spec.xml` — contains complete technical spec:
   - Database schema (11 new tables + 2 extensions)
   - 15 workflow statuses and transitions
   - 9 roles with permissions
   - API endpoints (~30)
   - UI screens (10)
   - Implementation phases

2. **Features**: `.claude/autonomous/features.json` — 88 features to implement with pass/fail tracking

3. **Protocol**: `.claude/autonomous/SESSION_PROTOCOL.md` — mandatory checklist for each session

4. **Progress Log**: `.claude/autonomous/claude-progress.txt` — notes from previous sessions

## Instructions

1. **START EVERY SESSION** by reading and following `.claude/autonomous/SESSION_PROTOCOL.md`
   - This is MANDATORY — do not skip this step
   - It includes environment setup, git checks, and finding the next feature

2. **Reference app_spec.xml** when implementing:
   - Database tables: exact field names and types
   - Workflow: allowed status transitions
   - Roles: what each role can do
   - API: endpoint paths and methods
   - UI: what each screen contains

3. **Work through features.json** one by one:
   - Find first feature where `passes: false` and `in_progress: false`
   - Mark it `in_progress: true` before starting
   - Implement the feature
   - Test it works
   - Mark `passes: true` when done
   - Commit with descriptive message

4. **Update claude-progress.txt** after each feature:
   ```
   ## Session [date] - Feature #[id]: [name]
   - What was implemented
   - Files changed
   - Any issues or notes
   ```

5. **Commit frequently** — after each completed feature

## Implementation Order

Features are ordered by dependency:
1. Database tables (features 1-16) — must be first
2. Role system (features 17-22)
3. Workflow engine (features 23-32)
4. UI for each role (features 33-72)
5. Telegram bot (features 52-66)
6. Specifications & Deals (features 67-76)
7. Plan-Fact (features 77-83)
8. Admin & Polish (features 84-88)

## Key Technical Notes

- **Stack**: Python FastHTML + HTMX + Supabase PostgreSQL
- **Main file**: `main.py` (2100+ lines) — add new routes here
- **Services**: `services/` folder — add new services here
- **Migrations**: `migrations/` folder — put SQL files here
- **Supabase**: Use SQL Editor in Supabase dashboard to run migrations

## Completion Signal

Output `OVERNIGHT_COMPLETE` when:
- All 88 features have `passes: true` in features.json, OR
- Stuck on same issue after 5+ attempts (document blocker first in progress log)

## Environment

Run `./.claude/autonomous/init.sh` to start the dev server.
App runs at http://localhost:5001

---

## Progress Tracking

### Completed Features
- [x] Feature #1: Create roles table (2025-01-15)
- [x] Feature #2: Create user_roles table (2025-01-15)
- [x] Feature #3: Create brand_assignments table (2025-01-15)
- [x] Feature #4: Create workflow_transitions table (2025-01-15)
- [x] Feature #5: Create approvals table (2025-01-15)
- [x] Feature #6: Create specifications table (2025-01-15)
- [x] Feature #7: Create deals table (2025-01-15)

### Next Up
- Feature #8: Create plan_fact_categories table
- Feature #9: Create plan_fact_items table
- Feature #10: Create telegram_users table
