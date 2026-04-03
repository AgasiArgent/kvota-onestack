# Context Panel Redesign — Remove Duplication, Restyle, Open by Default

**Date:** 2026-04-03
**Fixes:** FB-260403-100442-defe (верхнее меню съедает поля)
**Status:** Approved

---

## Problem

The quote detail page shows the same information in two places:

1. **ContextPanel** (toggled via ℹ button) — client, terms, financials, sales checklist, participants
2. **SalesContextCard** (always visible on procurement step) — transfer date/actor, request badges, equipment description, МОП

Duplicated fields: request type badges (4x), equipment description, sales manager (МОП). Users see the same data twice when the ContextPanel is open on the procurement step.

Additionally, the ContextPanel is hidden by default — procurement users must click ℹ to see any context about the quote they're working on.

## Solution

### 1. Delete SalesContextCard

Remove `sales-context-card.tsx` and its usage in `procurement-step.tsx`. All data it showed is already in the ContextPanel (transfer info is in the Participants block).

**Files to delete:**
- `frontend/src/features/quotes/ui/procurement-step/sales-context-card.tsx`

**Files to modify:**
- `frontend/src/features/quotes/ui/procurement-step/procurement-step.tsx` — remove SalesContextCard import and rendering

### 2. ContextPanel Open by Default + localStorage Persistence

Change `isContextOpen` initial state from `false` to `true`, with localStorage override.

**Behavior:**
- Panel starts **open** on all steps (sales, procurement, calculation, etc.)
- When user clicks ℹ to close → save quote ID to localStorage key `context-panel-closed`
- When user clicks ℹ to open → remove quote ID from localStorage
- On next visit to same quote → check localStorage, respect user's choice
- localStorage stores a JSON array of quote IDs, max 100 entries (FIFO eviction when full)

**Implementation in `quote-sticky-header.tsx`:**
```typescript
const STORAGE_KEY = "context-panel-closed";
const MAX_ENTRIES = 100;

function isQuotePanelClosed(quoteId: string): boolean {
  try {
    const ids: string[] = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    return ids.includes(quoteId);
  } catch { return false; }
}

function toggleQuotePanelClosed(quoteId: string, closed: boolean): void {
  try {
    let ids: string[] = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    ids = ids.filter((id) => id !== quoteId);
    if (closed) {
      ids.push(quoteId);
      if (ids.length > MAX_ENTRIES) ids = ids.slice(-MAX_ENTRIES);
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  } catch { /* localStorage unavailable */ }
}
```

Change initial state:
```typescript
const [isContextOpen, setIsContextOpen] = useState(
  () => !isQuotePanelClosed(quote.id)
);
```

Update toggle handler to persist:
```typescript
function handleToggleContext() {
  setIsContextOpen((prev) => {
    const next = !prev;
    toggleQuotePanelClosed(quote.id, !next);
    return next;
  });
}
```

### 3. Restyle ContextPanel to Match SalesContextCard

Replace the current plain `border-t border-border bg-card` style with SalesContextCard's slicker card design.

**Current style (context-panel.tsx):**
```
border-t border-border bg-card px-6 py-4
```

**New style:**
```
mx-6 mt-3 mb-1 rounded-lg border border-border bg-muted/30 p-4
```

**Section headers — add icons** (matching SalesContextCard pattern with icon + uppercase label):

| Section | Icon | Label |
|---------|------|-------|
| Клиент | `User` (lucide) | КЛИЕНТ |
| Условия | `Package` (lucide) | УСЛОВИЯ |
| Финансы | `TrendingUp` (lucide) | ФИНАНСЫ |
| Контекст продаж | `ClipboardList` (lucide) | КОНТЕКСТ ПРОДАЖ |
| Участники | `Users` (lucide) | УЧАСТНИКИ |

**Section header markup:**
```tsx
<div className="flex items-center gap-2 mb-2">
  <Icon size={14} className="text-muted-foreground" />
  <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
    {label}
  </h4>
</div>
```

This matches the existing SalesContextCard header pattern (lines 116-119 and 138-141 in `sales-context-card.tsx`).

### 4. Compact Delivery Line

Combine delivery method + incoterms + delivery priority into a single row to reduce vertical space:

**Current:** 3 separate InfoRow items
**New:** Single row: `Авто · DDP · Быстрее`

```tsx
<InfoRow label="Доставка">
  <span className="text-sm font-medium">
    {deliveryMethod}
    {incoterms && <> · <Badge variant="outline" className="text-xs font-semibold px-2 py-0">{incoterms}</Badge></>}
    {deliveryPriority && <> · {priorityLabel}</>}
  </span>
</InfoRow>
```

---

## Scope

| Change | File | Impact |
|--------|------|--------|
| Delete SalesContextCard | `sales-context-card.tsx` | Remove file |
| Remove from procurement step | `procurement-step.tsx` | Remove import + JSX |
| Default open + localStorage | `quote-sticky-header.tsx` | ~20 lines added |
| Restyle wrapper | `context-panel.tsx` | CSS class change |
| Add section icons | `context-panel.tsx` | Import icons, add header markup |
| Compact delivery line | `context-panel.tsx` | Combine 3 rows → 1 |

**Not in scope:**
- No data model changes
- No API changes
- No new components
- ContextPanel data fetching stays the same
