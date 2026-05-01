# Implementation Tasks: Inline merge UX

> Estimates: 1-3 hours per sub-task. `(P)` marks tasks safely runnable in parallel; default is sequential.

## 1. Build mergeable eligibility state in invoice-card

- [ ] 1.1 Add `mergeableByItemId` state and populate it inside the existing `load()` function alongside `splitableByItemId`. Gate: a row is mergeable IFF it is a 1:1 candidate AND the invoice has ≥ 2 such candidates total. Reset on `rows.length === 0`. _Requirements: 1.1, 1.2, 5.4_
- [ ] 1.2 Add `mergeInlineState` dialog-state and a `handleMergeClick(invoiceItemId)` callback that resolves the row's defaults from `invoiceItems` and the source qi metadata from `mergeableByItemId`. _Requirements: 1.3, 1.4_

## 2. New `MergeInlineDialog` component

- [ ] 2.1 Create `frontend/src/features/quotes/ui/procurement-step/merge-inline-dialog.tsx` with `MergeInlineDialogProps` and `MergeFormState` typed exactly as the design contract. Pure helpers `isValidMergeForm` and `isPartnerSelected` exported for unit tests. _Requirements: 3.1, 3.2, 3.5_
- [ ] 2.2 Render the dialog body: header (initiator product name + qty, currency badge), checkbox list of partners with brand/sku/name/qty, form fields (product_name + brand* + supplier_sku* + цена закупки* with currency suffix). Empty-candidate state handled gracefully. _Requirements: 2.1, 2.2, 2.5, 3.3, 3.4, 6.3_
- [ ] 2.3 Wire submit + cancel: gate submit on `isValidMergeForm`, call `mergeInvoiceItems` with `[initiator.source_qi, ...selected.source_qi]` and the form payload (currency from prop), success → `toast.success` + `onClose()`, failure → keep dialog open and surface `extractErrorMessage`. Both buttons disabled while in flight. _Requirements: 4.1, 4.2, 4.3, 6.4, 6.5_

## 3. Wire per-row trigger in `procurement-handsontable.tsx`

- [ ] 3.1 Extend `ProcurementHandsontableProps` with `mergeableByItemId` + `onMergeRow`. Sync via the same `useRef` pattern that protects split eligibility, and trigger `hotInstance.render()` in the existing eligibility-effect when the new map flips. _Requirements: 1.1, 1.2, 6.1_
- [ ] 3.2 In `rowActionsRenderer`, add the `⋃` icon branch BETWEEN `↧` and `↪`. Style identical to the existing icons; `onclick` calls `onMergeRowRef.current(rowId)`. Bump actions-column width from 80 to 96 to fit four icons (↧/⋃/↪/✕) without clipping. _Requirements: 1.1, 6.1_

## 4. Pass-through in `procurement-items-editor.tsx`

- [ ] 4.1 Add `mergeableByItemId?` and `onMergeRow?` to `ProcurementItemsEditorProps` and forward them to `<ProcurementHandsontable>`. Mirror the optionality and JSDoc of the existing `splitableByItemId` props. _Requirements: 1.1, 1.3_

## 5. Mount `<MergeInlineDialog>` in invoice-card

- [ ] 5.1 Mount the dialog beside `<SplitInlineDialog>`. Build the `candidates` array from `mergeableByItemId` minus the initiator. Wire `onClose` to clear `mergeInlineState` AND bump `refreshKey` (same pattern as split). _Requirements: 1.5, 4.4_

## 6. Remove the legacy top-level merge surface

- [ ] 6.1 Remove the «Объединить» button from the КП card header (`oneToOneCandidates.length >= 2` branch in invoice-card.tsx). _Requirements: 5.1_
- [ ] 6.2 Remove `mergeOpen` state, `setMergeOpen` calls, and the `<MergeModal>` mount from invoice-card.tsx. Drop the now-unused `Merge` lucide import if grep confirms no remaining use. _Requirements: 5.1, 5.2_
- [ ] 6.3 Run `rg "from.*['\"].*merge-modal['\"]"` to confirm no production callers. Delete `merge-modal.tsx` AND `__tests__/merge-modal.test.tsx`. If the audit finds a stray caller, address it before deleting. _Requirements: 5.3_

## 7. Tests

- [ ] 7.1 Create `__tests__/merge-inline-dialog.test.tsx`: unit tests for `isValidMergeForm` (each required field + ratio of selected partners ≥ 1) and `isPartnerSelected`; SSR sanity for module export + closed-state render without throwing (Portal omitted in SSR). _Requirements: 2.4, 3.5, 6.4_
- [ ] 7.2*(P) Update or add tests in `invoice-card.test.tsx` for two cases: (a) merge eligibility map is empty when there are < 2 1:1 candidates, (b) the legacy `<MergeModal>` is no longer rendered. _Requirements: 1.2, 5.1, 5.2_
- [ ] 7.3 Run `npx tsc --noEmit` and `npx vitest run` from `frontend/` and confirm zero TS errors and zero failing tests. _Requirements: 5.4_

## 8. Browser verification

- [ ] 8.1 On `localhost:3000` open a КП with at least 3 1:1 positions. Verify per-row icons: ⋃ visible on every 1:1 row, NOT on already-split rows. Click ⋃ on row A → dialog opens with B, C in candidate list (no A). _Requirements: 1.1, 1.3, 2.1, 2.2_
- [ ] 8.2 Submit a merge with 2 partners checked → confirm rows collapse to one merged row in the table, «← X, Y объединены» label appears above, ⋃ icon disappears from the merged row. _Requirements: 4.1, 4.2, 4.4, 4.5_
- [ ] 8.3 Try invalid forms: empty brand/sku/price → confirm submit disabled; uncheck all partners → confirm submit disabled. Try short viewport → dialog scrolls cleanly with sticky header/footer. _Requirements: 2.4, 3.5, 6.2, 6.5_
