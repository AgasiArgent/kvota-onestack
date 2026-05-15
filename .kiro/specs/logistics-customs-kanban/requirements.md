# Logistics & Customs Kanban — Requirements

Replace the table-based logistics and customs workspace pages with native kanban
boards, modeled on the procurement kanban. Removes auto-distribution; introduces
manual pull/assign. Fixes Testing 2 rows 40, 41, 43.

## Context (current state)

- `/workspace/logistics` and `/workspace/customs` render a shared table
  (`WorkspaceInvoicesTable`) with tabs My/Completed/Unassigned/All + analytics.
- Auto-distribution: `assign_logistics_to_invoices` (route-based) and
  `assign_customs_to_invoices` (least-loaded RPC) run inside `complete_procurement`.
- Stage timers live on `kvota.invoices`: `logistics_assigned_at/deadline_at/
  completed_at/sla_hours`, symmetric `customs_*`. SLA badge currently keys off
  `*_assigned_at`, falling back to `created_at`.
- Roles: members `logistics`/`customs`; heads `head_of_logistics`/`head_of_customs`
  (dual-hat — each head sees BOTH workspaces); `admin`/`top_manager` also heads.

## Requirements (EARS)

### REQ-1 — Two separate kanban boards
The system SHALL render a kanban board on `/workspace/logistics` and a separate
kanban board on `/workspace/customs`, each scoped to its own domain's invoices.
The old table + tab UI SHALL be fully removed (no toggle). A stats/analytics strip
MAY remain above the board.

### REQ-2 — Three columns
Each board SHALL have exactly three columns: «Нераспределено», «В работе»,
«Завершено».
- Нераспределено = invoices where `assigned_{domain}_user IS NULL` and the deal
  has reached the logistics/customs stage and is not completed.
- В работе = invoices with `assigned_{domain}_user` set and `{domain}_completed_at
  IS NULL`.
- Завершено = invoices where `{domain}_completed_at IS NOT NULL`.

### REQ-3 — No auto-distribution
WHEN a deal completes procurement and enters the logistics/customs stage, the
system SHALL NOT auto-assign a logistician/customs officer. Invoices SHALL land in
«Нераспределено». The `assign_logistics_to_invoices` / `assign_customs_to_invoices`
calls inside `complete_procurement` SHALL be removed (the route-based / least-loaded
functions may stay in code, just no longer invoked automatically).

### REQ-4 — Stage timer starts on stage entry
The card timer SHALL start when the deal enters the logistics/customs stage,
independent of whether an employee is assigned. The SLA/timer badge SHALL key off
the stage-entry timestamp (`{domain}_assigned_at` if set, else the stage-entry
time), NOT `created_at`. Unassigned cards SHALL show a running timer.

### REQ-5 — Unassigned cards visible to all
Every employee of the domain (members and heads) SHALL see all «Нераспределено»
cards of their domain.

### REQ-6 — «В работе» visibility
A member SHALL see in «В работе» only cards assigned to themselves. A head
(`head_of_*`, `admin`, `top_manager`) SHALL see all «В работе» cards of the domain,
each labeled with its assignee's name.

### REQ-7 — Member self-pull
WHEN a member drags a card from «Нераспределено» to «В работе», the system SHALL
assign that invoice to the dragging member (`assigned_{domain}_user = self`,
stamp `{domain}_assigned_at`). A member SHALL NOT be able to assign a card to
anyone else.

### REQ-8 — Head assign / reassign
A head SHALL be able to assign a «Нераспределено» card to any domain member, and
SHALL be able to reassign an already-assigned «В работе» card to a different
member (drag + assignee picker), to correct distribution errors.

### REQ-9 — Auto-completion
«Завершено» SHALL NOT be a manual drop target. A card SHALL move to «Завершено»
automatically when `{domain}_completed_at` is set by the existing stage-completion
flow.

### REQ-10 — Card content
Each card SHALL display: route/direction (Откуда→Куда / страна отгрузки), IDN/КПП
number + customer name, stage timer (SLA badge), deal sum + item count, and cargo
places count with their dimensions and weight.

### REQ-11 — Role access
Only domain employees (members + heads, dual-hat included) SHALL access the board.
Org scoping SHALL be enforced via the `quotes!inner` join, as in the current
queries.

## Open / assumed

- Drag library: `@dnd-kit/core`, matching procurement kanban.
- Assignment commit: server action writing `invoices.assigned_{domain}_user` +
  `{domain}_assigned_at` (extends existing `reassignInvoice`).
- Cargo places/dimensions/weight sourced from invoice cargo data (same source as
  the logistics cargo panel, Testing 2 row 14).
