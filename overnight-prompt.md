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
- [x] Feature #8: Create plan_fact_categories table (2025-01-15)
- [x] Feature #9: Create plan_fact_items table (2025-01-15)
- [x] Feature #10: Create telegram_users table (2025-01-15)
- [x] Feature #11: Create notifications table (2025-01-15)
- [x] Feature #12: Extend quotes table with workflow fields (2025-01-15)
- [x] Feature #13: Extend quote_items table with workflow fields (2025-01-15)
- [x] Feature #14: Seed roles data (2025-01-15) - Already in migration 001
- [x] Feature #15: Seed plan_fact_categories data (2025-01-15)
- [x] Feature #16: Configure RLS for new tables (2025-01-15)
- [x] Feature #17: Role service - get_user_roles (2025-01-15)
- [x] Feature #18: Role service - has_role, has_any_role, has_all_roles (2025-01-15)
- [x] Feature #19: Role service - assign_role function (2025-01-15)
- [x] Feature #20: Role service - remove_role function (2025-01-15)
- [x] Feature #21: Middleware require_role (2025-01-15)
- [x] Feature #22: Контекст пользователя с ролями (2025-01-15)
- [x] Feature #23: Enum статусов workflow (2025-01-15)
- [x] Feature #24: Матрица переходов статусов (2025-01-15)
- [x] Feature #25: Сервис перехода статуса (2025-01-15)
- [x] Feature #26: Валидация перехода статуса (2025-01-15) - Already in Feature #25
- [x] Feature #27: Логирование переходов (2025-01-15) - Already in Feature #25
- [x] Feature #28: Автопереход logistics+customs → sales_review (2025-01-15)
- [x] Feature #29: Назначение исполнителей при переходе (2025-01-15)
- [x] Feature #30: Сервис назначений брендов (2025-01-15)
- [x] Feature #31: Получение менеджера по бренду (2025-01-15)
- [x] Feature #32: Получение брендов менеджера (2025-01-15)
- [x] Feature #33: Страница /procurement (2025-01-15)

### Next Up
- Feature #34: Список КП с моими брендами

### Progress
- **33 of 88 features completed** (38%)
- **DATABASE PHASE COMPLETE** (all 16 features done)
- **ROLE SERVICE PHASE COMPLETE** (all 6 features done: 17-22)
- **WORKFLOW ENGINE PHASE COMPLETE** (all 10 features done: 23-32)
- All 11 new tables created with comprehensive RLS policies
- Extended quotes and quote_items tables with workflow fields
- Seed data for roles and plan_fact_categories inserted
- Helper functions added: user_has_role_in_org, user_organization_ids, user_is_admin_in_org
- Role service now includes:
  - get_user_roles, get_user_role_codes, get_all_roles, get_role_by_code
  - has_role, has_any_role, has_all_roles (role checking functions)
  - assign_role, remove_role (role management functions)
  - require_role, require_any_role, require_all_roles (route protection middleware)
  - get_session_user_roles (convenience function)
- Workflow service now includes:
  - WorkflowStatus enum with 15 statuses
  - ALLOWED_TRANSITIONS list with 26 transitions
  - STATUS_NAMES, STATUS_NAMES_SHORT, STATUS_COLORS dicts
  - get_allowed_transitions, can_transition, is_final_status helpers
  - Permission matrix functions (Feature #24):
    - get_transition_requirements, get_roles_for_transition
    - get_transitions_by_role, get_permission_matrix, get_permission_matrix_detailed
    - get_outgoing_transitions, get_incoming_transitions
    - is_comment_required, is_auto_transition
  - Transition execution functions (Feature #25):
    - transition_quote_status() - Main function to execute workflow transitions
    - TransitionResult dataclass - Structured return type
    - get_quote_workflow_status() - Get current status of a quote
    - get_quote_transition_history() - Get audit log of transitions
    - get_available_transitions_for_quote() - Get available transitions for UI
  - Auto-transition functions (Feature #28):
    - check_and_auto_transition_to_sales_review() - Auto-transition when both stages complete
    - complete_logistics() - Mark logistics complete and trigger auto-check
    - complete_customs() - Mark customs complete and trigger auto-check
    - get_parallel_stages_status() - Get completion status of parallel stages
  - Procurement assignment functions (Feature #29):
    - get_procurement_users_for_quote() - Get brand → user mapping
    - assign_procurement_users_to_quote() - Auto-assign users to items and quote
    - transition_to_pending_procurement() - Specialized transition with auto-assignment
    - get_quote_procurement_status() - Get detailed procurement status
- Brand assignment service (services/brand_service.py):
  - Full CRUD: create_brand_assignment, upsert_brand_assignment, bulk_create_assignments
  - Read: get_brand_assignment, get_brand_assignment_by_brand, get_all_brand_assignments
  - Update: update_brand_assignment, reassign_brand
  - Delete: delete_brand_assignment, delete_brand_assignment_by_brand, delete_all_user_assignments
  - Utilities: get_unique_brands_in_org, get_unassigned_brands, get_brand_manager_mapping, count_assignments_by_user, is_brand_assigned
  - Convenience: get_procurement_manager (Feature #31), get_assigned_brands (Feature #32)
- Added /unauthorized route in main.py
- Session now includes roles: session["user"]["roles"] = ["sales", "admin", ...]
- Added session-based helpers: user_has_role, user_has_any_role, get_user_roles_from_session
- **UI Phase started - Feature #33 complete: /procurement page**
- Procurement page includes:
  - Role check for procurement/admin access
  - Displays user's assigned brands
  - Lists quotes with items matching user's brands
  - Separates "pending" vs "other" quotes by workflow status
  - Color-coded workflow status badges
- Navigation updated with role-based links
