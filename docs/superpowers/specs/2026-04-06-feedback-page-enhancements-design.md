# Feedback Page Enhancements

**Date:** 2026-04-06
**Scope:** `/admin/feedback` list page UX improvements
**Reference:** garson-client feedback page (inline expand + inline status pattern)

## Problem

The current feedback list navigates to a separate detail page on row click. Triaging many tickets requires constant back-and-forth navigation. There's no way to change status without opening the detail page, and no bulk operations for batch triage.

## Goals

1. View ticket details inline (without page navigation)
2. Change status directly from the list (no detail page needed)
3. Select multiple tickets and change their status in bulk
4. Configurable page size (25/50/100, default 50)

## Non-Goals

- No changes to the feedback submission widget (`features/feedback/`)
- No new database migrations
- No changes to the detail page (`/admin/feedback/[id]`) — it stays as a deep link
- No bulk operations beyond status change (no bulk delete, no bulk ClickUp assign)

## Design

### Inline Row Expansion

Introduce TanStack React Table (`@tanstack/react-table`) to replace the current plain shadcn `<Table>`. TanStack provides built-in models for row expansion and row selection — both needed here.

**Behavior:**
- Click anywhere on a row (except interactive elements) → toggle expanded detail panel below the row
- Expanded panel shows: full description, page URL, screenshot with lightbox, debug context (collapsible), ClickUp link
- Only one row expanded at a time — clicking another row collapses the previous one (keeps the list scannable for triage)
- Keyboard: Enter/Space on focused row toggles expansion

**Component:** `FeedbackExpandedRow` — new file at `features/admin-feedback/ui/feedback-expanded-row.tsx`. Extracts the display-only parts from the existing `FeedbackDetailView` (info card, description block, screenshot, debug context, ClickUp link). Does NOT include the status change card (that's now inline in the table row).

### Inline Status Dropdown

Replace the static status badge in the table's Status column with a `Select` dropdown.

**Behavior:**
- `stopPropagation` on the Select to prevent toggling row expansion
- On value change → optimistic update (update local table state immediately)
- Call `updateFeedbackStatus(shortId, newStatus)` in background
- On error → revert to previous status, show toast
- No "Save" button — direct commit

### Bulk Status Change

Add a checkbox column using TanStack's row selection model.

**Behavior:**
- Header checkbox = select/deselect all on current page
- Individual row checkboxes in the first column
- When 1+ rows selected, a toolbar appears between the filter tabs and the table:
  - Left: `"{N} выбрано"` count
  - Center: status `Select` dropdown
  - Right: `"Применить"` button (disabled until a status is chosen)
  - Far right: `"Снять выделение"` text button
- On apply → call new `bulkUpdateFeedbackStatus(shortIds[], status)`
- After success → clear selection, refetch page data, show toast
- On error → show toast with error, keep selection

**New mutation:** `bulkUpdateFeedbackStatus` in `entities/admin/mutations.ts`:
```typescript
export async function bulkUpdateFeedbackStatus(
  shortIds: string[],
  status: string
): Promise<void> {
  const supabase = createClient();
  const { error } = await supabase
    .from("user_feedback")
    .update({ status, updated_at: new Date().toISOString() })
    .in("short_id", shortIds);
  if (error) throw new Error(error.message);
}
```

### Page Size Selector

**Behavior:**
- New URL param: `pageSize` (values: 25, 50, 100; default: 50)
- Selector rendered next to the pagination controls (small `Select` with options 25/50/100)
- Changing page size resets to page 1
- `fetchFeedbackList` accepts `pageSize` as a parameter instead of using the hardcoded constant

### Filter Tabs Enhancement

Keep existing status filter tabs. No changes to search or ClickUp link behavior.

## File Changes

| File | Change |
|------|--------|
| `entities/admin/queries.ts` | `fetchFeedbackList` accepts `pageSize` param, default 50 |
| `entities/admin/mutations.ts` | Add `bulkUpdateFeedbackStatus()` |
| `features/admin-feedback/ui/feedback-list.tsx` | Rewrite with TanStack Table: columns, expand, select, inline status |
| `features/admin-feedback/ui/feedback-expanded-row.tsx` | **New** — expanded row detail content |
| `features/admin-feedback/index.ts` | Re-export new component |
| `app/(app)/admin/feedback/page.tsx` | Read `pageSize` from searchParams, pass to fetch and component |

### Unchanged

| File | Reason |
|------|--------|
| `features/admin-feedback/ui/feedback-detail.tsx` | Detail page still uses it |
| `app/(app)/admin/feedback/[id]/page.tsx` | Deep link stays functional |
| `entities/admin/types.ts` | No type changes needed |
| `features/feedback/*` | Submission widget untouched |

## Dependencies

- **New:** `@tanstack/react-table` (npm install)
- **Existing:** shadcn `Sheet`, `Select`, `Checkbox`, `Table` components already present

## UX Complexity Check

| Metric | Value | Status |
|--------|-------|--------|
| Distinct user goals | 2 (triage tickets, bulk close) | OK |
| Interactive elements visible | ~8 (tabs, search, page size, checkboxes, status dropdowns, pagination) | OK |
| Primary CTAs | 1 (Apply bulk action — appears only on selection) | OK |
| Decision points | 2 (which status, which tickets) | OK |

## Testing

- Inline expand: click row → panel appears with correct data, click again → collapses
- Inline status: change status → updates immediately, verify in DB
- Bulk select: header checkbox selects all, individual checkboxes work, toolbar appears/disappears
- Bulk status: select 3 tickets → change to "closed" → all 3 update
- Page size: switch 25→50→100, verify correct item count and pagination
- Edge cases: bulk update with some already in target status, expand row then bulk-select it, change page size while rows are selected (clear selection)
