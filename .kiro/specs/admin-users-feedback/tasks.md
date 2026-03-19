# Implementation Plan

- [ ] 1. Entity layer
- [ ] 1.1 Define types and queries for users and feedback
  - OrgMember (id, full_name, email, roles[], telegram_username, joined_at)
  - FeedbackItem (short_id, type, description, user_name, user_email, status, clickup_task_id, created_at)
  - FeedbackDetail extends FeedbackItem (source_url, screenshot_url, debug_context)
  - fetchOrgMembers(orgId, search?) — members with roles + telegram + profiles
  - fetchFeedbackList(orgId, status?, search?, page?) — paginated feedback
  - fetchFeedbackDetail(shortId, orgId) — single item with full data
  - updateUserRoles(userId, orgId, roleIds[]) — assign/remove roles
  - updateFeedbackStatus(shortId, status) — via Python API for ClickUp sync
  - _Requirements: 1.1, 2.1, 3.1_

- [ ] 2. Users page
- [ ] 2.1 Build /admin/users page with search and role modal
  - Server component with admin role check
  - 2 summary cards (total users, with Telegram)
  - Search input (filters by name/email)
  - Table: ФИО, Email, Роли (badges), Telegram, Дата
  - Click roles → modal with checkboxes, save button
  - Validation: min 1 role, can't remove own admin
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 4.1, 4.2_

- [ ] 3. Feedback pages
- [ ] 3.1 Build /admin/feedback list page
  - Server component with admin role check
  - Status filter tabs (Все/Новые/В работе/Решено/Закрыто)
  - Search input
  - Paginated table with clickable ClickUp links
  - Row click → detail page
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 4.1, 4.2_

- [ ] 3.2 (P) Build /admin/feedback/[id] detail page
  - Full feedback display with screenshot (zoomable)
  - Status update dropdown → calls legacy API
  - Debug context display
  - _Requirements: 3.1, 3.2, 3.3, 3.4_
