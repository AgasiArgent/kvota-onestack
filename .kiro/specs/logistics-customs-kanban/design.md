# Logistics & Customs Kanban — Design

Implements `requirements.md` (REQ-1..REQ-11). Replaces the table-based logistics
& customs workspace pages with kanban boards modeled on the procurement kanban.

## Architecture decision

One shared `workspace-kanban` feature slice with a `domain: "logistics" | "customs"`
discriminator — mirrors the existing shared table, avoids duplicate board/card code.

## File plan

| # | File | Action | Notes |
|---|------|--------|-------|
| 1 | `frontend/src/features/workspace-kanban/model/types.ts` | CREATE | `WorkspaceKanbanCard`, `WorkspaceKanbanColumns`, `cardKey()` |
| 2 | `frontend/src/features/workspace-kanban/api/queries.ts` | CREATE | `fetchKanbanBoard(domain,userId,orgId,isHead)` → `{unassigned,in_progress,completed}` |
| 3 | `frontend/src/features/workspace-kanban/server-actions.ts` | CREATE | `selfPullInvoice(invoiceId,domain)` member-only self-assign; re-export `reassignInvoice` |
| 4 | `frontend/src/features/workspace-kanban/ui/kanban-card.tsx` | CREATE | Draggable card, REQ-10 fields |
| 5 | `frontend/src/features/workspace-kanban/ui/kanban-board.tsx` | CREATE | `DndContext` + 3 columns; member vs head drag |
| 6 | `frontend/src/features/workspace-kanban/ui/assignee-picker-popover.tsx` | CREATE | Adapted from `procurement-kanban/ui/assign-popover.tsx` |
| 7 | `frontend/src/features/workspace-kanban/ui/kanban-page.tsx` | CREATE | Client shell, `dynamic(ssr:false)` |
| 8 | `frontend/src/features/workspace-kanban/index.ts` | CREATE | Public barrel |
| 9 | `frontend/src/entities/workspace-invoice/queries.ts` | MODIFY | Add `fetchKanbanInvoices`; SELECT `procurement_completed_at` + `invoice_cargo_places(weight_kg,length_mm,width_mm,height_mm)`; fix `domainFields()` fallback `created_at`→`procurement_completed_at` (REQ-4) |
| 10 | `frontend/src/entities/workspace-invoice/index.ts` | MODIFY | Export new query |
| 11 | `frontend/src/app/(app)/workspace/logistics/page.tsx` | REPLACE | Drop tabs/table/inbox; keep `WorkspaceStatsStrip`; render `<KanbanPage domain="logistics">` |
| 12 | `frontend/src/app/(app)/workspace/customs/page.tsx` | REPLACE | Same, `domain="customs"` |
| 13 | `frontend/src/app/(app)/workspace/logistics/workspace-logistics-client.tsx` | DELETE | — |
| 14 | `frontend/src/features/workspace-logistics/ui/workspace-invoices-table.tsx` | DELETE | — |
| 15 | `frontend/src/features/workspace-logistics/ui/unassigned-inbox.tsx` | DELETE | — |
| 16 | `frontend/src/features/workspace-logistics/ui/workspace-tab-bar.tsx` | DELETE | — |
| 17 | `frontend/src/features/workspace-logistics/index.ts` | MODIFY | Remove deleted exports; keep `WorkspaceStatsStrip` + `reassignInvoice` |
| 18 | `services/workflow_service.py` | MODIFY | Remove auto-distribution (see Backend) |

## Column predicates (REQ-2)

| Column | Predicate | Visibility |
|--------|-----------|------------|
| Нераспределено | `procurement_completed_at IS NOT NULL AND assigned_{domain}_user IS NULL AND {domain}_completed_at IS NULL` | all domain users |
| В работе | `assigned_{domain}_user IS NOT NULL AND {domain}_completed_at IS NULL` | member: own only; head: all |
| Завершено | `{domain}_completed_at IS NOT NULL` | all; limit last ~100 / 90 days |

Single query returns all three column keys pre-populated.

## Card payload (REQ-10)

`id, quoteId, invoiceNumber, idnQuote, customerName, pickupCountry/Code/City,
deliveryCountry/City, stageEnteredAt (=procurement_completed_at), assignedAt
(={domain}_assigned_at, nullable), deadlineAt, completedAt, assignedUserId/Name,
itemCount, dealSumTotal/Currency, cargoPlaces (count + grouped dims from
invoice_cargo_places), packageCount, totalWeightKg, totalVolumeM3`.

**REQ-4 timer fix:** `entities/workspace-invoice/queries.ts` `domainFields()` — the
`assignedAt` fallback `inv.created_at` becomes `inv.procurement_completed_at ??
inv.created_at` for both logistics and customs. `SlaTimerBadge` itself unchanged
EXCEPT: must accept a null `deadlineAt` and render elapsed-since-stage-entry for
unassigned cards (deadline is stamped only on assignment).

## Drag semantics (REQ-7/8/9)

| Actor | Drag | Action |
|-------|------|--------|
| Member | Нераспределено → В работе | `selfPullInvoice(invoiceId,domain)` — assigns self, stamps `assigned_at` |
| Member | В работе → elsewhere | blocked (toast) |
| Member/Head | → Завершено | blocked — not a `useDroppable` target (auto on stage completion) |
| Head | Нераспределено → В работе | opens `AssigneePickerPopover` → `reassignInvoice(invoiceId,domain,userId)` |
| Head | В работе → В работе | reassign → `reassignInvoice(...)` |

Optimistic move + rollback on failure (race: another member pulled it first),
same pattern as procurement kanban `commitTransition`.

`selfPullInvoice` is a NEW server action — role gate allows `logistics`/`customs`
members + heads. Do NOT relax `reassignInvoice`'s existing head-only gate.

## Backend change (REQ-3) — `services/workflow_service.py`

Remove auto-distribution. Confirmed call sites:
- Line ~3227 `assign_logistics_to_invoices(quote_id)` block in `complete_procurement` — remove.
- Line ~3255 `assign_customs_to_invoices(quote_id)` block — remove (+ any `result_error` text referencing them).
- `_assign_logistics_and_customs_to_invoices` helper (def ~3306, calls at 3317/3341) — becomes dead after removing its only caller at line ~3526; delete it.
- Line ~3526 `warnings = _assign_logistics_and_customs_to_invoices(quote_id)` — remove call + dependent `logistics_assigned`/`customs_assigned` result flags.
- `assign_logistics_to_invoices` (~2491) + `assign_customs_to_invoices` (~2672) + their `_*_result` builders (~2481/2663) — after the above, grep confirms zero callers → delete (no-dead-code rule). Verify no other caller before deleting.

After change: completing procurement advances workflow to logistics+customs stage
WITHOUT assigning anyone; invoices surface in the «Нераспределено» kanban column;
timers run from `procurement_completed_at`.

## Build sequence

1. **Backend** (independent, separate PR): remove auto-distribution + dead functions.
2. **Data layer**: extend `entities/workspace-invoice/queries.ts` (types + `fetchKanbanInvoices` + REQ-4 fallback fix). Bottleneck — must finish before UI.
3. **Feature slice UI**: types → server-actions → assignee-picker → card → board → page → barrel.
4. **Page wiring**: replace both `page.tsx`; delete table/tabs/inbox/client; trim `workspace-logistics/index.ts`.

Phases 2-4 ship as ONE frontend PR (partial merge would leave a broken page).

## Risks

1. `invoice_cargo_places` nested join — verify PostgREST FK alias resolves (pattern
   `cargo_places:invoice_cargo_places(...)`); test with a quote that has cargo boxes.
2. Unassigned cards have NULL `{domain}_deadline_at` — `SlaTimerBadge` must handle
   null deadline (render elapsed since stage entry, no overdue state).
3. Keep `reassignInvoice` head-only gate intact; `selfPullInvoice` is separate.
4. Завершено column unbounded — limit (last 100 / 90 days), like `fetchMyCompletedInvoices` (30).
5. Optimistic self-pull race — rollback + toast on failure.
6. Verify no frontend consumer reads the removed `logistics_assigned`/`customs_assigned`
   fields from the `complete-procurement` API response.
