# Design: Inline merge UX for procurement КП positions

## Overview

Симметричный двойник недавно отгруженного inline-split: per-row trigger в `procurement-handsontable` + slim Dialog с чек-листом кандидатов и формой сводной строки. Серверная семантика и mutation `mergeInvoiceItems` (entities/quote/mutations.ts) не меняются — это чисто UI-перенос «куда нажать» с шапки КП на строку.

## Architecture pattern & boundary map

| Слой | Что делает | Файлы |
|---|---|---|
| **UI primitive** | Render row-actions cell с тремя возможными иконками (↧ split, ⋃ merge, ↪ undo) + ✕ unassign. Reading rows-eligibility maps via refs (stale-closure-safe). | `procurement-handsontable.tsx` |
| **Container** | Builds eligibility maps from coverage data, holds dialog state, dispatches mutations, bumps `refreshKey` on completion. | `invoice-card.tsx` |
| **Form** | Slim Dialog с checkbox-листом партнёров + 4-полевой формой merged-row. Validation pure-function (тестируема в isolation). | `merge-inline-dialog.tsx` (новый) |
| **Editor pass-through** | Прокидывает `mergeableByItemId` + `onMergeRow` props сверху вниз. | `procurement-items-editor.tsx` |
| **Mutation** | Existing `mergeInvoiceItems` — не трогаем. | `entities/quote/mutations.ts` |

Единственный новый файл — `merge-inline-dialog.tsx`. Всё остальное — точечные правки уже существующих файлов вокруг существующего паттерна (split inline).

## Technology stack & alignment

- React 19 + Next.js 15 App Router (как остальной frontend/).
- shadcn/ui `Dialog`, `Input`, `Label`, `Button`, `Checkbox` (или `<input type="checkbox" className="...">` если Checkbox-компонента нет в репо).
- `sonner` `toast` для feedback.
- Vitest + react-dom/server для тестов (unit-уровень, без DOM).
- Никаких новых dependencies. Никаких schema-changes.

## Components & interface contracts

### `MergeInlineDialog` (new)

```ts
interface MergeInlineDialogProps {
  open: boolean;
  onClose: () => void;
  invoiceId: string;
  initiatorInvoiceItemId: string;
  initiatorSourceQuoteItemId: string;
  candidates: Array<{
    invoice_item_id: string;
    source_quote_item_id: string;
    brand: string;
    supplier_sku: string;
    product_name: string;
    quantity: number;
  }>;
  currency: string;
  defaults: {
    product_name: string;
    brand: string;
    supplier_sku: string;
    purchase_price_original: number | null;
  };
}
```

Internal state:

```ts
type MergeFormState = {
  product_name: string;
  brand: string;
  supplier_sku: string;
  purchase_price_original: string;
  selectedPartnerIds: Set<string>; // invoice_item_ids
};
```

Pure helpers (exported для unit-тестов):

```ts
export function isValidMergeForm(state: MergeFormState): boolean;
export function isPartnerSelected(state: MergeFormState, id: string): boolean;
```

Submit path:

```
isValidMergeForm(state) === true  →  mergeInvoiceItems(invoiceId, sourceIds[], merged) →
  success → toast.success("Позиции объединены") → onClose() → parent bumps refreshKey
  failure → toast.error(extractErrorMessage(err) ?? "Не удалось объединить") → keep open
```

`sourceIds[]` = `[initiatorSourceQuoteItemId, ...selected partners' source_quote_item_ids]`.

`merged` = the form values + `currency` (inherited).

### `procurement-handsontable.tsx` extensions

New props (additive, all optional):

```ts
mergeableByItemId?: Record<string, true>; // presence = "show ⋃"
onMergeRow?: (invoiceItemId: string) => void;
```

The existing rowActionsRenderer — already ref-driven after Bug A fix — gains a new branch:

```
1. ↧  if rowId in splitableRef.current
2. ⋃  if rowId in mergeableRef.current   ← NEW
3. ↪  if rowId in splitChildRef.current
4. ✕  always
```

Refs synced on every render; `useEffect([mergeableByItemId])` triggers `hotInstance.render()` to repaint cells when the map flips.

Actions column width: bump from 80 → 96 to fit up to 3 icons + ✕ comfortably without clipping in stretchH=all distribution.

### `invoice-card.tsx` integration points

Adds two pieces of derived state alongside existing `splitableByItemId` / `splitChildByItemId`:

```ts
// 1:1 candidates indexed by their invoice_item_id, with source qi metadata
// embedded so the dialog can resolve partners without re-querying.
const [mergeableByItemId, setMergeableByItemId] = useState<
  Record<string, {
    sourceQuoteItemId: string;
    sourceProductName: string;
    sourceQuantity: number;
  }>
>({});

// Active dialog state (null = closed).
const [mergeInlineState, setMergeInlineState] = useState<{
  initiatorInvoiceItemId: string;
  initiatorSourceQuoteItemId: string;
  defaults: { product_name: string; brand: string; supplier_sku: string; purchase_price_original: number | null };
} | null>(null);
```

Build path inside the existing `load()` function: rows that ARE 1:1 (the same condition that populates `splitableByItemId`) get an entry in `mergeableByItemId` IF AND ONLY IF the invoice has ≥ 2 such rows total. With <2, the icon is hidden everywhere — symmetric to the old `oneToOneCandidates.length >= 2` gate.

Dialog mount alongside `<SplitInlineDialog>`:

```tsx
<MergeInlineDialog
  open={mergeInlineState !== null}
  onClose={() => {
    setMergeInlineState(null);
    setRefreshKey((k) => k + 1);
  }}
  invoiceId={invoice.id}
  initiatorInvoiceItemId={mergeInlineState?.initiatorInvoiceItemId ?? ""}
  initiatorSourceQuoteItemId={mergeInlineState?.initiatorSourceQuoteItemId ?? ""}
  candidates={Object.entries(mergeableByItemId)
    .filter(([id]) => id !== mergeInlineState?.initiatorInvoiceItemId)
    .map(([id, meta]) => {
      const ii = invoiceItems.find((r) => r.id === id);
      return {
        invoice_item_id: id,
        source_quote_item_id: meta.sourceQuoteItemId,
        brand: ii?.brand ?? "",
        supplier_sku: ii?.supplier_sku ?? "",
        product_name: meta.sourceProductName,
        quantity: meta.sourceQuantity,
      };
    })}
  currency={currency}
  defaults={mergeInlineState?.defaults ?? blankDefaults}
/>
```

### Removed surface (R5 cleanup)

| Symbol | Where | Action |
|---|---|---|
| `mergeOpen`, `setMergeOpen` | invoice-card.tsx | delete |
| Header-bar «Объединить» button | invoice-card.tsx (~line 647) | delete |
| `<MergeModal>` mount | invoice-card.tsx (~line 904) | delete |
| `Merge` icon import (lucide) | invoice-card.tsx | delete if unused |
| `merge-modal.tsx` | features/quotes/ui/procurement-step/ | delete if grep finds zero non-test imports |
| `__tests__/merge-modal.test.tsx` | features/quotes/ui/procurement-step/__tests__/ | delete (covers deleted module) |

## Data flow (sequence)

```
[user clicks ⋃ on row Ri]
        ↓
procurement-handsontable.rowActionsRenderer.onclick
        ↓
onMergeRowRef.current(Ri)
        ↓
invoice-card.handleMergeClick(Ri)
        ↓
setMergeInlineState({ initiator..., defaults: from invoiceItems[Ri] })
        ↓
<MergeInlineDialog open={true} ...>
        ↓
[user checks partners P1, P2; edits merged-row form; clicks "Объединить"]
        ↓
MergeInlineDialog.handleSubmit()
        ↓
mergeInvoiceItems(invoiceId, [Ri.source_qi, P1.source_qi, P2.source_qi], { product_name, brand, supplier_sku, price, currency })
        ↓
Supabase  →  N invoice_items deleted  →  1 merged invoice_item inserted  →  N coverage rows inserted (ratio=1)
        ↓
toast.success → onClose() → invoice-card bumps refreshKey
        ↓
load() re-runs → coverage refetched → mergeableByItemId / splitableByItemId rebuilt → cells repainted
        ↓
Merged row visible in handsontable + "← X, Y объединены" label above
```

## Validation

| Rule | Where | Failure mode |
|---|---|---|
| Initiator must be a 1:1 candidate | `mergeableByItemId` gate at icon level | Icon never rendered → click impossible |
| ≥1 partner selected | `isValidMergeForm` | Submit button disabled |
| Brand non-empty | `isValidMergeForm` | Submit button disabled |
| Supplier SKU non-empty | `isValidMergeForm` | Submit button disabled |
| Price > 0 | `isValidMergeForm` | Submit button disabled |
| Currency provided | inherited from invoice — invariant | n/a |
| Concurrent re-fetch during open dialog | `refreshKey` not bumped while dialog open | n/a — load() guarded by useEffect cancellation |

## Test strategy

`__tests__/merge-inline-dialog.test.tsx`:

- `isValidMergeForm` — accepts valid, rejects on each missing/empty/zero field, rejects on empty selectedPartnerIds.
- `isPartnerSelected` — set semantics.
- SSR sanity — module exports cleanly, closed-state renders without throw (Portal omitted in SSR, like split).

Existing `mergeInvoiceItems` tests in `entities/quote/__tests__/mutations.test.ts` already cover the mutation; we don't touch it. After the legacy modal is deleted, run full test suite to confirm no orphan imports.

Browser verification on localhost: open КП with 2+ 1:1 positions → click ⋃ on first row → dialog opens with second row in candidate list → check it → fill form → submit → confirm rows collapse to one merged row + label appears above.

## Trade-offs and risks

1. **Single-step "select partners + fill form" vs two-step wizard.** Single-step keeps it lighter; with 5+ candidates the dialog grows tall. Mitigation: Dialog is now scroll-aware (this session's primitive fix), so vertical growth is fine.
2. **Initiator pre-selection.** The initiator is the row clicked, NOT a checkbox in the list. List shows OTHER candidates only. Trade-off: the "initiator" concept is implicit (it's the row you clicked). Alternative would be a true symmetric multi-select with no implicit initiator, but that requires checkboxes inside the handsontable — out of scope.
3. **Where the merged row's defaults come from.** From the initiator. If the user clicked the wrong row, they re-edit fields. Trade-off: simpler than "merge defaults from N rows" heuristic.
4. **Coverage refresh after merge.** Same `refreshKey` mechanism as split — proven to work this session.

## Requirement traceability

| Req ID | Where addressed |
|---|---|
| 1.1 | `mergeableByItemId` map + ⋃ branch in `rowActionsRenderer` |
| 1.2 | Map builder gates on `siblings.length === 1 && covers.length === 1 && ratio === 1` |
| 1.3 | `onMergeRow` callback → `setMergeInlineState` |
| 1.4 | `defaults` prop sourced from `invoiceItems.find((i) => i.id === Ri)` |
| 1.5 | useEffect cancellation token in `load()`; refresh only on dialog `onClose` |
| 2.1 | `candidates` prop = `mergeableByItemId` minus initiator |
| 2.2 | Each candidate row renders brand/sku/name/qty |
| 2.3 | `selectedPartnerIds` initialized to empty `Set` |
| 2.4 | `isValidMergeForm` requires `selectedPartnerIds.size >= 1` |
| 2.5 | If `candidates.length === 0`, dialog renders empty-state message |
| 3.1 | Form fields: product_name + brand + supplier_sku + purchase_price_original |
| 3.2 | No fields beyond above; verified by `MergeFormState` type |
| 3.3 | Defaults pre-fill on dialog open via `useEffect([open, initiatorId])` |
| 3.4 | `currency` prop — read-only display only |
| 3.5 | `isValidMergeForm` returns false for empty/invalid inputs; submit disabled |
| 4.1 | `handleSubmit` calls `mergeInvoiceItems` with assembled args |
| 4.2 | onClose + toast on success; parent bumps `refreshKey` |
| 4.3 | catch block keeps `submitting=false` and dialog `open=true` |
| 4.4 | Refresh re-runs `load()` which rebuilds eligibility maps |
| 4.5 | Merged row not in `mergeableByItemId` (covers.length > 1) |
| 5.1 | Header «Объединить» button removed in invoice-card.tsx |
| 5.2 | `mergeOpen` state + `<MergeModal>` mount removed |
| 5.3 | `merge-modal.tsx` + test deleted (subject to grep audit) |
| 5.4 | Mutation untouched |
| 6.1 | ⋃ icon styled identically to ↧ |
| 6.2 | Standard `Dialog` primitive (now scroll-aware globally) |
| 6.3 | shadcn `Input`, `Label`, `Button`; `<input type="checkbox">` for partner list |
| 6.4 | onClose discards `useState` form values; no confirm prompt |
| 6.5 | Submit + Cancel buttons gated on `submitting` flag |
