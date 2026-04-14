# Design — Kanban Inline Distribution

## Component Structure

```
features/procurement-kanban/ui/
├── kanban-card.tsx           (edit: conditional action slot)
├── kanban-board.tsx          (edit: drag guard)
├── assign-popover.tsx        (new: popover body, ~120 lines)
└── ...

shared/ui/procurement/
└── user-search-select.tsx    (moved from procurement-distribution/ui/)
```

## Popover Structure (Base UI)

```tsx
<Popover open={open} onOpenChange={setOpen}>
  <PopoverTrigger asChild>
    <button>Распределить</button>
  </PopoverTrigger>
  <PopoverContent align="start" side="bottom" className="w-[320px]">
    <div className="p-3 space-y-3">
      {notice && <p className="text-xs text-warning">{notice}</p>}
      <UserSearchSelect users={users} value={userId} onValueChange={setUserId} />
      {brand && (
        <label>
          <Checkbox checked={pinBrand} onChange={setPinBrand} />
          Закрепить бренд {brand} за этим МОЗ
        </label>
      )}
      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onCancel}>Отмена</Button>
        <Button onClick={handleAssign} disabled={!userId || loading}>
          {loading ? <Loader2 /> : null} Назначить
        </Button>
      </div>
    </div>
  </PopoverContent>
</Popover>
```

`notice` is used for the drag-guard case: "Не все позиции назначены."

## Kanban Card: Conditional Action

```tsx
// kanban-card.tsx (simplified)
const isDistributing = card.procurement_substatus === "distributing";

return (
  <div className="kanban-card">
    ...existing content (IDN, МОП, МОЗ, days, etc.)...

    {isDistributing && (
      <AssignPopover
        open={assignOpen}
        onOpenChange={setAssignOpen}
        card={card}
        users={procUsers}
        notice={forcedByGuard ? "Не все позиции назначены. Назначьте оставшиеся." : undefined}
        onAssigned={() => {
          setAssignOpen(false);
          // parent Board will refetch or optimistically advance
          onCardAssigned?.(card);
        }}
      />
    )}
  </div>
);
```

## Drag Guard in Board

```tsx
// kanban-board.tsx
async function handleDrop(dragEvent) {
  const from = dragEvent.activeColumn;
  const to = dragEvent.overColumn;

  if (from === "distributing" && to === "searching_supplier") {
    const unassigned = await countUnassigned(card.quote_id, card.brand);
    if (unassigned > 0) {
      // Rollback optimistic move
      setCards(prev => moveCard(prev, to, from, card));
      toast.error("Не все позиции назначены");
      setForcedAssignCardKey(brandCardKey(card));  // opens popover on that card
      return;
    }
  }

  // Normal path
  await transitionSubstatus(card.quote_id, card.brand, to);
  ...
}

async function countUnassigned(quoteId: string, brand: string): Promise<number> {
  const supabase = createClient();
  const { count } = await supabase
    .from("quote_items")
    .select("id", { count: "exact", head: true })
    .eq("quote_id", quoteId)
    .eq("brand", brand)  // handle brand === null case separately
    .is("assigned_procurement_user", null)
    .neq("is_unavailable", true);
  return count ?? 0;
}
```

Note on brand === null: `UserSearchSelect` already handles that case today. Guard query needs parallel handling — use `.is("brand", null)` instead of `.eq` when brand is null.

## State Machine for Card's Assign Popover

One card can be in these states:
- **idle** — no popover
- **open (user-initiated)** — user clicked "Распределить"
- **open (guard-forced)** — user tried drag forward, guard blocked, popover auto-opened with notice
- **submitting** — API call in flight
- **error** — failed, popover stays with toast

Transitions:
```
idle → open (user-initiated)    on click Распределить
idle → open (guard-forced)      on drag-drop failed guard
open → submitting               on Assign click
submitting → idle               on success
submitting → error              on failure
error → submitting              on retry
open → idle                     on cancel/outside/escape
```

Only one popover at a time (two simultaneous popovers would be awkward on the board). Track `openCardKey: string | null` at Board level — only the matching card renders its popover as `open`.

## FSD Cross-Slice Fix

Current:
```
features/procurement-distribution/ui/user-search-select.tsx
    ↑ imports from procurement-distribution/model
```

After:
```
shared/ui/procurement/user-search-select.tsx
    ↑ imports from shared/types/procurement-user.ts (new, simple type)
```

Move:
1. Copy file to `shared/ui/procurement/user-search-select.tsx`.
2. Extract `ProcurementUserWorkload` type to `shared/types/procurement-user.ts` (or accept `users: Array<{ user_id, full_name, active_quotes }>` as a generic prop).
3. Update distribution-page import.
4. Delete original file.

Update public API indexes as needed.

## Mutation Wiring

Existing `assignBrandGroup(itemIds, userId, pinBrand, orgId, brand)` in `procurement-distribution/api/mutations.ts` already wraps the backend call. Move this to `entities/quote/mutations.ts` or keep and have kanban import via shared — whichever respects FSD.

**Recommendation:** expose `assignBrandGroup` from `entities/quote/mutations.ts` (entity-level mutation, both features consume). This is the cleaner place given how FSD treats entity mutations.

## Testing Plan

1. **Frontend component test** (`kanban-card.test.ts` or new `assign-popover.test.ts`):
   - Distributing card renders "Распределить" button.
   - Other-column cards do NOT render it.
   - Popover opens on click, closes on cancel.

2. **Drag guard test** (`kanban-board.test.ts` extend):
   - Mock supabase count = 0 → transition proceeds.
   - Mock supabase count > 0 → optimistic rollback + popover opens + toast shown.

3. **Prod browser-test** (mandatory):
   - Login as procurement dispatcher (head_of_procurement: chislova.e@masterbearing.ru).
   - Navigate to /procurement/kanban.
   - Click "Распределить" on a distributing card → popover opens.
   - Select user, click Assign → card moves to Поиск поставщика (auto-advance if all items now assigned) OR stays with updated МОЗ.
   - Try to drag an undistributed card to Поиск поставщика → popover auto-opens with notice, card stays in distributing.

## Edge Cases

- **Card becomes empty-column mid-drag**: if slice auto-advances between drag-start and drop, the drop goes to wrong column. Base case: we refetch state on any successful transition, so race is short-lived. Accept.
- **Two popovers on the same card**: impossible — one openCardKey state.
- **Pin brand when brand is null**: disable the Pin checkbox; show disabled state with tooltip "Нельзя закрепить без бренда."
- **User has no procurement users configured**: popover shows "Нет доступных МОЗ" in the select. Assign button stays disabled.

## Non-Functional

- Popover must be keyboard-accessible (tab, escape, enter on select).
- Drop guard query budget: <150ms p95 (simple COUNT, no joins).
- Card action area must not interfere with drag (stopPropagation on popover trigger pointerDown, same pattern as IDN link in current kanban-card.tsx).
