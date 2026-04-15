# Requirements: Cascade Soft-Delete for Quote → Spec → Deal

**Feature:** `soft-delete-entity-lifecycle`
**ClickUp:** [86agwr801](https://app.clickup.com/t/86agwr801)
**Status:** approved (plan reviewed by user 2026-04-15)

## Background

Per `CLAUDE.md`: *"Quote → Specification → Deal = same business entity at different stages. They share data via `deals.specification_id` (1:1)."* Currently `deleted_at` exists only on `kvota.quotes`. Specifications and deals have no soft-delete column, and the FKs `deals → quotes` / `deals → specifications` are RESTRICT. Soft-deleting a quote that has a spec/deal therefore leaves orphaned downstream rows that still appear in UI via readers that don't filter `deleted_at IS NULL`.

This was discovered on 2026-04-15 during cleanup of 33 АО "ВАЛЕНТА ФАРМ" test quotes (32 quotes soft-deleted + 1 spec/deal hard-deleted as a one-off because the columns didn't exist yet). The one-off exception proves the rule: we need a standard.

## Requirements

### REQ-001: Schema evolution

The system SHALL add soft-delete columns to all three entities in the lifecycle:
- WHEN migration 279 applies, `kvota.specifications` and `kvota.deals` SHALL each have `deleted_at timestamptz` (nullable) and `deleted_by uuid REFERENCES auth.users(id)` (nullable)
- WHEN migration 279 applies, `kvota.quotes` SHALL gain `deleted_by uuid REFERENCES auth.users(id)` (`deleted_at` already exists)
- WHEN migration 279 applies, partial indexes filtering `WHERE deleted_at IS NULL` SHALL exist on the primary lookup keys: `quotes(customer_id)`, `specifications(quote_id)`, `deals(specification_id)`

### REQ-002: Atomic cascade soft-delete

The system SHALL provide a single transactional entry point for soft-deleting the lifecycle:
- WHEN `kvota.soft_delete_quote(p_quote_id uuid, p_actor_id uuid)` is called, it SHALL mark the quote, its active spec (if any), and the active deal linked to that spec (if any) with `deleted_at = now()` and `deleted_by = p_actor_id` **atomically** (one transaction, all-or-nothing)
- WHEN called on an already-soft-deleted quote, the function SHALL be idempotent (no error, no state change for rows already having `deleted_at IS NOT NULL`)
- WHEN called with a non-existent `p_quote_id`, the function SHALL return zero affected rows without error
- The function SHALL return a row reporting `quote_affected`, `spec_affected`, `deal_affected` counts (0 or 1 each)

### REQ-003: Restore

The system SHALL support reversing a soft-delete within the retention window:
- WHEN `kvota.restore_quote(p_quote_id uuid)` is called, it SHALL set `deleted_at = NULL, deleted_by = NULL` on the quote and its formerly-linked spec/deal atomically
- The function SHALL only restore rows whose `deleted_at` is non-NULL (idempotent)

### REQ-004: API endpoints

The system SHALL expose the DB functions via HTTP:
- `POST /api/quotes/{quote_id}/soft-delete` SHALL call `soft_delete_quote` and return `{success, data: {quote_affected, spec_affected, deal_affected}}`
- `POST /api/quotes/{quote_id}/restore` SHALL call `restore_quote` and return success envelope
- Both endpoints SHALL accept JWT auth via `request.state.api_user` (primary) with `require_login(session)` fallback (per `.claude/rules/api-first.md` and `feedback_dual_auth_api.md`)
- Endpoints SHALL require role: `admin` **only** (not sales/head_of_sales/top_manager — soft-delete is an administrative operation with cross-org impact)
- Endpoints SHALL return `404` when quote doesn't exist, `401` without auth, `403` for any non-admin authenticated user

### REQ-005: Read-side invisibility

The system SHALL ensure soft-deleted entities are invisible to all read paths by default:
- Views `kvota.active_quotes`, `kvota.active_specs`, `kvota.active_deals` SHALL exist with built-in `WHERE deleted_at IS NULL` filter
- All reads in `main.py`, `api/*.py`, and `frontend/src/**/*.ts{,x}` that query `kvota.quotes|specifications|deals` SHALL filter `deleted_at IS NULL` either directly or via the `active_*` view
- RLS policies on the three tables SHALL include `deleted_at IS NULL` as an additional gate (defense-in-depth)
- Exception: reads that intentionally surface soft-deleted rows (the Trash page) SHALL explicitly query the base tables with `deleted_at IS NOT NULL`

### REQ-006: Delete UI

The system SHALL present a Delete action to admin users only on entity detail pages (Quote, Specification, Deal):
- Each entity detail page header SHALL render an overflow menu button (⋯) at the end of the actions group
- The menu item "🗑 Удалить квоту" SHALL be rendered in red/destructive styling and SHALL be visible **only to users with role = `admin`** (hidden for all other roles via early return in the component — not disabled, fully absent)
- Clicking the menu item SHALL open a shadcn `AlertDialog` that names what will be cascaded ("квоту, спецификацию если есть, сделку если есть") and states the 365-day restore window
- Action hierarchy in dialog: "Отмена" is the primary (filled) button; "Удалить" is outlined/destructive red — inverted to give visual weight to the safe option
- On confirm, UI SHALL call `POST /api/quotes/{id}/soft-delete`, show a success toast, and redirect to `/quotes` (or revalidate current list path)
- On failure, UI SHALL show an error toast with the server's message
- The same menu + dialog pattern SHALL appear on Spec and Deal detail pages — all three call the same endpoint because Quote/Spec/Deal is one entity lifecycle

### REQ-007: Trash page

The system SHALL provide a recovery interface:
- `/quotes/trash` (Next.js) SHALL list all soft-deleted quotes with columns: IDN, customer, deleted_at, deleted_by (name), age_days, days_until_purge (= 365 - age_days)
- Each row SHALL have a "Восстановить" button that calls `POST /api/quotes/{id}/restore`
- The page SHALL be reachable from the sidebar under "Администрирование" → "Корзина"
- Access gate: **admin only** (not original owner — consistent with REQ-004 delete authority)
- Non-admin navigating directly to `/quotes/trash` SHALL receive a 403-style "Нет доступа" page

### REQ-008: Retention + hard-purge

The system SHALL permanently delete soft-deleted data after the retention window:
- A daily job SHALL hard-delete quotes where `deleted_at < now() - interval '365 days'`
- The hard-delete SHALL rely on existing FK CASCADEs to clean up `quote_items`, `plan_fact_items`, `logistics_stages`, `currency_invoices`, and other downstream tables
- The job SHALL log purged quote IDs and row counts (stdout + optionally audit log)
- The job SHALL support `--dry-run` mode for safety verification
- The job SHALL run on the VPS (docker cron or systemd timer on beget-kvota)

## Out of Scope

- Soft-delete at the customer level (future work)
- Hard-deleting specs/deals that have no parent quote (edge case — in current model specs/deals exist only via quote)
- UI indicator for "items with pending hard-purge" (stretch goal)
- Soft-delete for historical quotes already hard-deleted (destructive; no recovery possible)

## Non-Functional Requirements

- **Performance**: partial indexes SHALL keep list-page queries at current latency (no regression)
- **Security**: `soft_delete_quote` / `restore_quote` SHALL be `SECURITY DEFINER` with explicit role checks via RLS; direct `UPDATE kvota.quotes SET deleted_at = ...` from JS client SHALL be blocked by RLS when function is available
- **Idempotency**: repeated calls to soft_delete / restore SHALL be no-ops, not errors
- **Reversibility**: restore SHALL work for any quote within 365 days of deletion

## Verification

- 33 ВАЛЕНТА ФАРМ quotes (already soft-deleted 2026-04-15) remain invisible in the UI after Read-audit (subtask 3) completes
- Creating a new test quote, adding a deal, then calling soft-delete via the new UI button makes all three invisible atomically
- Restore from `/quotes/trash` brings everything back
- Regression test suite covers: no-spec case, spec-no-deal case, full-cascade case, double-delete idempotency, restore, view visibility, RLS block

## References

- CLAUDE.md — entity lifecycle + migration conventions
- `.claude/rules/api-first.md` — API endpoint patterns
- `.claude/rules/database.md` — migration + query discipline
- `.kiro/steering/database.md` — confusable columns + schema norms
- Memory: `feedback_dual_auth_api.md`, `feedback_quotes_access_control_cascade.md`, `feedback_migrations_never_scp.md`, `reference_localhost_browser_test.md`
