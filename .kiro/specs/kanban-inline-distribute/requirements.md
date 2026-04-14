# Requirements — Kanban Inline Distribution + Drag Guard

**Created:** 2026-04-14
**Type:** FEATURE + BIG
**Priority:** Normal (UX improvement; builds on Phase 4 kanban)

## Problem

Procurement dispatchers using the kanban board (`/procurement/kanban`) can see brand-slices sitting in the `Распределение` column but cannot act on them there — they must navigate to `/procurement/distribution` to assign МОЗ. This forces a context switch for the most common single-slice action.

Additionally, manual drag of an undistributed slice from `Распределение` → `Поиск поставщика` is currently allowed structurally — nothing prevents a dispatcher from moving a brand-slice forward before all items have МОЗ assigned. This creates inconsistent state (slice in `searching_supplier`, items with no МОЗ).

## Goal

Make the kanban `Распределение` column actionable: dispatchers should be able to assign МОЗ directly on a card via a popover, without leaving the page. And drag-drop transitions from `distributing` → `searching_supplier` must guarantee all items are assigned (or marked unavailable) before completing.

The existing `/procurement/distribution` page stays — it remains the bulk-list view for dispatchers doing 10+ assignments in a row.

## Requirements

### REQ-1 — Inline assign popover on distributing cards
- Cards in the `Распределение` column MUST show a "Распределить" affordance (button or inline control).
- Clicking opens a popover anchored to the card containing:
  - **User select** — searchable dropdown of procurement users (reuse the component from the distribution page)
  - **Pin brand** — optional checkbox to set this brand as always-assigned to this user for future quotes
  - **Assign** submit button
  - **Cancel** / click-outside close
- Popover uses the existing Base UI `Popover` component (shared/ui/popover).
- Popover MUST NOT appear on cards in other substatus columns (`Поиск поставщика`, `Ждём цены`, `Цены готовы`).

### REQ-2 — Assign action wiring
- On confirm, call the existing backend mutation (`POST /api/procurement/items/bulk` or equivalent) with all item IDs of the brand-slice + selected user ID + pin flag.
- On success:
  - Optimistic: card's МОЗ field updates in place with assignee's name
  - Toast: `"{IDN}: N позиций назначены на {user name}"`
  - If the assignment completes the slice (all items have МОЗ or are marked unavailable), the server auto-advance will move it to `Поиск поставщика`. The frontend MUST refetch kanban state (or optimistically move the card) to reflect this.
- On failure: toast error, popover stays open for retry.

### REQ-3 — Drag-drop guard: distributing → searching_supplier
- When user drops a card from `Распределение` onto `Поиск поставщика`:
  1. Before calling the transition API, query: do all non-unavailable items of the brand-slice have `assigned_procurement_user` set?
  2. **All assigned** → proceed with normal transition API call.
  3. **NOT all assigned** → rollback the optimistic drop (card stays in `Распределение`), then open the inline assign popover on the card with a note: "Не все позиции назначены. Назначьте оставшиеся."
- After user completes assignment via the popover, server auto-advance kicks in and the slice moves forward.

### REQ-4 — Reverse (auto-advance) verified
- Existing `maybe_advance_after_distribution` already advances slices once fully assigned. This REQ exists only as a confirmation: the inline assign flow (REQ-2) MUST trigger the same auto-advance without special-casing — the backend is unchanged, the frontend just needs to re-sync kanban state to see the card move.

### REQ-5 — Shared UserSearchSelect
- The `UserSearchSelect` component currently lives in `features/procurement-distribution/ui/user-search-select.tsx`.
- Kanban (feature slice) MUST NOT import from distribution (feature slice) — FSD horizontal-import rule.
- Solution: move `UserSearchSelect` to `shared/ui/procurement/user-search-select.tsx` (or `shared/ui/user-search-select.tsx` if fully generic). Both distribution and kanban import from shared.

### REQ-6 — No backend changes
- All requirements are implementable with existing endpoints (`items/bulk`, `transitions/substatus`).
- Guard query in REQ-3 MAY use Supabase direct from the browser (read-only count of unassigned items) since it's a simple existence check with no privacy concerns.
- No new migrations.

### REQ-7 — Popover dismissal contract
- Clicking outside the popover or pressing Escape MUST close it without submitting.
- While assignment is in flight (API pending), the popover MUST show a loading state and block further submissions.

### REQ-8 — Test coverage
- Frontend test: kanban card in distributing column renders "Распределить" button; cards in other columns don't.
- Frontend test: drag-drop guard blocks partial assignment and opens popover with message.
- Integration test (Python or frontend): items/bulk endpoint still triggers auto-advance when slice becomes fully assigned — likely already covered in `test_workflow_substatus.py::TestMaybeAdvanceAfterDistribution`. Verify, don't duplicate.

## Non-Requirements

- Drag backward (`Поиск` → `Распределение`) — stays as-is, uses existing reason dialog.
- `/procurement/distribution` page — unchanged, kept for bulk flow.
- Bulk-assign multiple cards at once on kanban — out of scope (that's distribution page's job).
- Sidebar badge behavior — unchanged.

## Risks

| Risk | Mitigation |
|------|------------|
| FSD violation: kanban imports from distribution | Move UserSearchSelect to shared/ui (REQ-5) |
| Popover positioning breaks on card edges (right-most column) | Base UI Popover auto-flips; verify at 1440px |
| Drop-guard query latency adds perceivable lag on drop | Query is `select count, head=true` via Supabase — should be <100ms |
| Optimistic UI desyncs after auto-advance | Use router.refresh() after successful assignment to resync |
| Pin brand flag: UI mismatch between distribution + kanban if pinned differently | Both paths call same API; no drift |

## Rollout

1. Move UserSearchSelect to shared (no user-visible change)
2. Add popover to kanban card + wire assign mutation
3. Add drag guard
4. Browser-test on prod with dispatcher role
5. Update user memory about the new flow

Single atomic PR. No migration. Low rollback cost (revert commit).
