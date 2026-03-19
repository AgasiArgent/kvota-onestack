# Requirements Document

## Introduction
Migrate /admin users and feedback pages to Next.js. Users page: member list with search, email column, role editing via modal. Feedback page: feedback list with pagination, search, clickable ClickUp links, detail view with screenshot.

## Requirements

### Requirement 1: Users List
**Objective:** As an admin, I want to manage organization members and their roles.

#### Acceptance Criteria
1. The Users Page shall display a table with columns: ФИО, Email, Роли (colored badges), Telegram (✓ @username or —), Дата.
2. The Users Page shall show 2 summary cards: Всего пользователей, С Telegram.
3. The Users Page shall provide a search input filtering by name or email.
4. When an admin clicks a user's role badges, the Users Page shall open a modal dialog with role checkboxes.
5. The role modal shall prevent removing all roles (minimum 1 required).
6. The role modal shall prevent admin from removing "admin" role from themselves.
7. When roles are saved, the Users Page shall update the badges without full page reload.

### Requirement 2: Feedback List
**Objective:** As an admin, I want to review user feedback with filtering and pagination.

#### Acceptance Criteria
1. The Feedback Page shall display a table with columns: ID (short_id), Тип (badge), Описание (truncated), Пользователь, Статус (badge), ClickUp (clickable link), Дата.
2. The Feedback Page shall provide status filter tabs: Все, Новые, В работе, Решено, Закрыто.
3. The Feedback Page shall paginate results (20 per page).
4. The Feedback Page shall provide a search input filtering by description or user.
5. When ClickUp task ID exists, it shall render as a clickable link opening ClickUp in a new tab.

### Requirement 3: Feedback Detail
**Objective:** As an admin, I want to view full feedback details and update status.

#### Acceptance Criteria
1. The Detail Page shall show: type badge, status badge, submitter (name + email), source URL, full description, screenshot (if exists), debug context.
2. The Detail Page shall provide a status dropdown to update feedback status.
3. When status is updated, the Detail Page shall call the Python API endpoint for ClickUp sync + Telegram notification.
4. The screenshot shall be zoomable (click to enlarge).

### Requirement 4: Access Control
**Objective:** Only admins can access these pages.

#### Acceptance Criteria
1. Both pages shall be accessible only to users with admin role.
2. While the user lacks admin role, navigation shall redirect to /quotes.
