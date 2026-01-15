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
- [x] Feature #34: Список КП с моими брендами (2025-01-15)
- [x] Feature #35: Форма ввода закупочных данных (2025-01-15)
- [x] Feature #36: Скачивание списка для оценки (2025-01-15)
- [x] Feature #37: Кнопка завершения оценки (2025-01-15)
- [x] Feature #38: Страница /logistics (2025-01-15)
- [x] Feature #39: Список КП на этапе логистики (2025-01-15) - Already in #38
- [x] Feature #40: Форма ввода логистики (2025-01-15)
- [x] Feature #41: Кнопка завершения логистики (2025-01-15) - In #40
- [x] Feature #42: Страница /customs (2025-01-15)
- [x] Feature #43: Список КП на этапе таможни (2025-01-15) - In #42
- [x] Feature #44: Форма ввода таможенных данных (2025-01-15)
- [x] Feature #45: Кнопка завершения таможни (2025-01-15) - In #44
- [x] Feature #46: Страница /quote-control (2025-01-15)
- [x] Feature #47: Список КП на проверке (2025-01-15) - In #46
- [x] Feature #48: Чек-лист проверки КП (2025-01-15)
- [x] Feature #49: Форма возврата на доработку (2025-01-15)
- [x] Feature #50: Кнопка отправки на согласование (2025-01-15)
- [x] Feature #51: Кнопка одобрения КП (2025-01-15)
- [x] Feature #52: Создание Telegram-бота (2025-01-15) - Created telegram_service.py with bot infrastructure
- [x] Feature #53: Webhook endpoint (2025-01-15) - POST /api/telegram/webhook with update processing
- [x] Feature #54: Команда /start (2025-01-15) - Welcome message with account linking instructions
- [x] Feature #55: Верификация аккаунта (2025-01-15) - Telegram account verification via code
- [x] Feature #56: UI генерации кода верификации (2025-01-15) - /settings/telegram page with verification code
- [x] Feature #57: Команда /status (2025-01-15) - Shows user's tasks by role with formatted Telegram message
- [x] Feature #58: Отправка уведомления task_assigned (2025-01-15) - send_task_assigned_notification() with Telegram + DB recording
- [x] Feature #59: Отправка уведомления approval_required (2025-01-15) - send_approval_required_notification() with inline buttons
- [x] Feature #60: Inline-кнопка Согласовать (2025-01-15) - handle_approve_callback() validates user, transitions quote to approved, updates Telegram message
- [x] Feature #61: Inline-кнопка Отклонить (2026-01-15) - handle_reject_callback() validates user, transitions quote to rejected, updates Telegram message
- [x] Feature #62: Уведомление status_changed (2026-01-15) - StatusChangedNotification dataclass, send_status_changed_notification(), notify_quote_creator_of_status_change(), notify_assigned_users_of_status_change()
- [x] Feature #63: Уведомление returned_for_revision (2026-01-15) - ReturnedForRevisionNotification dataclass, send_returned_for_revision_notification(), notify_creator_of_return(), integrated into /quote-control/{quote_id}/return handler
- [x] Feature #64: Сервис согласований (2026-01-15) - approval_service.py with full CRUD: Approval dataclass, create_approval, create_approvals_for_role, get_approval, get_approval_by_quote, get_approvals_for_quote, get_pending_approval_for_quote, get_pending_approvals_for_user, get_approvals_requested_by, get_approvals_with_details, count_pending_approvals, update_approval_status, approve_quote_approval, reject_quote_approval, cancel_pending_approvals_for_quote, has_pending_approval, get_latest_approval_decision, get_approval_stats_for_user
- [x] Feature #65: Создание запроса на согласование (2026-01-15) - request_approval() function with ApprovalRequestResult dataclass. Complete workflow: validates status, transitions to pending_approval, creates approval records for top_manager/admin, sends Telegram notifications. Updated main.py POST handler.
- [x] Feature #66: Обработка решения согласования (2026-01-15) - process_approval_decision() function with ApprovalDecisionResult dataclass. Complete workflow: validates approval exists and is pending, validates quote status, updates approval record, transitions quote to approved/rejected, cancels other pending approvals, sends notifications to creator and requester.
- [x] Feature #67: Страница /spec-control (2026-01-15) - Created /spec-control workspace page for spec_controller role. Shows quotes pending specification creation (pending_spec_control status), specifications grouped by status (draft, pending_review, approved, signed). Added 'Спецификации' link to nav_bar. Stats cards, status filter, action buttons.
- [x] Feature #68: Список спецификаций на проверке (2026-01-15) - Already in #67: dedicated section showing specs at pending_review status with filtering.
- [x] Feature #69: Форма ввода данных спецификации (2026-01-15) - Complete spec data entry form with all 18 fields in 5 sections. Routes: /spec-control/create/{quote_id} (GET/POST), /spec-control/{spec_id} (GET/POST). Pre-fills from quote data, supports status transitions draft→pending_review→approved.
- [x] Feature #70: Preview PDF спецификации (2026-01-15) - Full PDF preview functionality using all 18 spec fields. Enhanced specification_export.py with SpecificationData, fetch_specification_data(), generate_spec_pdf_html(), generate_spec_pdf_from_spec_id(). Route: /spec-control/{spec_id}/preview-pdf. Added "Предпросмотр PDF" button to spec edit page.
- [x] Feature #71: Загрузка подписанного скана (2026-01-15) - Upload signed scan endpoint /spec-control/{spec_id}/upload-signed. Accepts PDF/JPG/PNG up to 10MB. Stores in Supabase Storage bucket 'specifications'. Updates signed_scan_url field. UI section added to spec edit page (visible when status is approved/signed). Migration 017 documents storage bucket setup.
- [x] Feature #72: Кнопка подтверждения подписи (2026-01-15) - Confirm signature button and deal creation. Added 'Подтвердить подпись' button to spec edit page (visible when status=approved + signed_scan exists). POST /spec-control/{spec_id}/confirm-signature endpoint creates deal record with auto-generated deal_number (DEAL-YYYY-NNNN), updates spec status to 'signed', optionally transitions quote to deal_signed.
- [x] Feature #73: Сервис спецификаций (2026-01-15) - Created services/specification_service.py with full CRUD operations: Specification dataclass with all 18 fields, SPEC_STATUSES/SPEC_STATUS_NAMES/SPEC_STATUS_COLORS/SPEC_TRANSITIONS constants, status helpers, create_specification(), get_specification(), get_specification_by_quote(), get_specifications_by_status(), get_all_specifications(), get_specifications_with_details(), count_specifications_by_status(), specification_exists_for_quote(), update_specification(), update_specification_status(), set_signed_scan_url(), delete_specification(), generate_specification_number(), get_specification_stats(), get_specifications_for_signing(), get_recently_signed_specifications().
- [x] Feature #74: Создание спецификации из КП (2026-01-15) - Created create_specification_from_quote() function in specification_service.py with CreateSpecFromQuoteResult dataclass. Function fetches quote data, optionally uses specific version data, pre-fills 15+ specification fields from quote and calculation variables (proposal_idn, currency, exchange rate, payment terms, countries, legal entities, periods). Returns result with success flag, specification object, error message, and prefilled_fields dict. Updated services/__init__.py with exports.
- [x] Feature #75: Сервис сделок (2026-01-15) - Created services/deal_service.py with full CRUD operations: Deal dataclass with all fields, DEAL_STATUSES/DEAL_STATUS_NAMES/DEAL_STATUS_COLORS/DEAL_TRANSITIONS constants, status helpers, create_deal(), get_deal(), get_deal_by_specification(), get_deal_by_quote(), get_deals_by_status(), get_all_deals(), get_deals_with_details(), count_deals_by_status(), deal_exists_for_specification(), deal_exists_for_quote(), update_deal(), update_deal_status(), complete_deal(), cancel_deal(), update_deal_amount(), delete_deal(), generate_deal_number(), get_deal_stats(), get_active_deals(), get_recent_deals(), get_deals_by_date_range(), search_deals(). Updated services/__init__.py with all exports.
- [x] Feature #76: Создание сделки из спецификации (2026-01-15) - Created create_deal_from_specification() function in deal_service.py with CreateDealFromSpecResult dataclass. Function fetches specification with quote/customer details, validates spec status (approved/signed) and signed_scan, extracts financial data (total_amount, currency), generates deal_number, creates deal record in 'active' status, optionally updates spec status to 'signed'.

### Next Up
- Feature #77: Страница /finance (Finance manager workspace)

### Progress
- **76 of 88 features completed** (86%)
- **TELEGRAM BOT PHASE STARTED** (Feature #52 complete: bot service infrastructure)
- **DATABASE PHASE COMPLETE** (all 16 features done)
- **ROLE SERVICE PHASE COMPLETE** (all 6 features done: 17-22)
- **WORKFLOW ENGINE PHASE COMPLETE** (all 10 features done: 23-32)
- **LOGISTICS UI PHASE COMPLETE** (all 4 features done: 38-41)
- **CUSTOMS UI PHASE COMPLETE** (all 4 features done: 42-45)
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
