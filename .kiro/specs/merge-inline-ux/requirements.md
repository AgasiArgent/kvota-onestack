# Requirements: Inline merge UX for procurement КП positions

## Introduction

Менеджер отдела закупок объединяет позиции в КП поставщику, когда поставщик отвечает «эти три товара по сути один артикул, выставляйте одной строкой». Сегодня действие живёт в шапочной кнопке «Объединить», которая открывает отдельный модал и заставляет пользователя выбирать обе исходные позиции из выпадашек. После переноса split-действия на per-row trigger merge остался единственным «не-инлайновым» структурным действием — это создаёт асимметрию и дополнительный ментальный shift.

Эта фича добавляет per-row trigger для merge, симметричный недавно отгруженному inline-split. Кнопка «Объединить» в шапке КП убирается. Серверная семантика (mutation `mergeInvoiceItems`) не меняется.

---

## Requirements

### Requirement 1: Per-row trigger для merge

**Objective:** As a procurement manager, I want a merge icon directly on the source row, so that I don't have to scan the table for multi-select-then-action and the flow matches the inline split I already use.

#### Acceptance Criteria

1. The procurement handsontable shall render a merge icon (⋃) in the row-actions cell of every invoice_item that is currently a 1:1 candidate (single coverage row, ratio=1, source quote_item not part of any split or merge in this invoice).
2. The procurement handsontable shall NOT render the merge icon for rows that are already part of a split or merge.
3. When the procurement manager clicks the merge icon, the InvoiceCard shall open the MergeInlineDialog anchored conceptually to the clicked row, with that row pre-selected as the merge initiator.
4. The InvoiceCard shall pass the clicked row's defaults (наименование, бренд, supplier_sku, цена закупки) to the dialog as initial values for the merged-row form.
5. While the merge dialog is open, the InvoiceCard shall NOT trigger refetches that could invalidate the open form.

### Requirement 2: Selection of merge partners

**Objective:** As a procurement manager, I want to see candidate rows I can merge with the initiator and pick one or more, so that I'm not limited to the strict pairwise merges of the old multi-select modal.

#### Acceptance Criteria

1. The MergeInlineDialog shall display the list of all OTHER 1:1 candidates in this invoice (excluding the initiator) as a checkbox list.
2. Each candidate row in the list shall show: бренд, артикул поставщика, наименование, количество — enough information to disambiguate similar items.
3. The MergeInlineDialog shall start with all candidate checkboxes unchecked, requiring explicit selection by the user.
4. The MergeInlineDialog shall enable the «Объединить» submit button only when at least one candidate is checked.
5. If there are zero other 1:1 candidates in the invoice, the MergeInlineDialog shall display a non-blocking message «Нет позиций, с которыми можно объединить» and disable the submit button. (This case is also prevented by hiding the merge icon at row-level, but the dialog must handle it gracefully if reached.)

### Requirement 3: Merged-row form

**Objective:** As a procurement manager, I want to type the consolidated row's name, brand, sku, and price once, so that the resulting merged row has clean canonical data instead of arbitrary picks from the sources.

#### Acceptance Criteria

1. The MergeInlineDialog shall expose form fields for the merged row: наименование, бренд (required), артикул поставщика (required), цена закупки (required).
2. The MergeInlineDialog shall NOT expose: валюта, вес, объём, код ТНВЭД, MOQ, габариты, поля производителя, срок поставки. These are filled inline in the handsontable after the merge succeeds.
3. The MergeInlineDialog shall pre-fill наименование, бренд, supplier_sku, цена from the initiator row's defaults; the user can override any field.
4. The InvoiceCard shall inherit currency from the parent invoice when calling the merge mutation; the user shall NOT see a currency picker.
5. The MergeInlineDialog shall reject submit when бренд, артикул поставщика, or цена is empty / non-positive, with field-level inline error markers.

### Requirement 4: Submit and state refresh

**Objective:** As a procurement manager, I want the merge to persist and the table to reflect the new state immediately, so that I can keep working without a manual refresh.

#### Acceptance Criteria

1. When the procurement manager submits a valid form, the InvoiceCard shall call the existing `mergeInvoiceItems` mutation with the initiator + selected partners as sources and the form values as the merged-row payload.
2. When `mergeInvoiceItems` resolves successfully, the InvoiceCard shall close the dialog, surface a success toast «Позиции объединены», and bump its local refresh trigger so coverage / merge eligibility maps re-fetch.
3. When `mergeInvoiceItems` rejects, the InvoiceCard shall keep the dialog open, surface a toast with the extracted error message (or a fallback «Не удалось объединить позиции»), and re-enable the submit button.
4. The procurement handsontable shall, after refresh, reflect: the source rows replaced by a single merged row, the merge label («← X, Y объединены») visible above the table for the merged row, and an undo-merge icon (if implemented in scope) on the merged row.
5. The procurement handsontable shall NOT render the merge icon for the resulting merged row (it's no longer 1:1).

### Requirement 5: Removal of the top-level «Объединить» button

**Objective:** As a procurement manager, I want only one place that initiates merge, so that the UI doesn't offer two ways to do the same thing.

#### Acceptance Criteria

1. The InvoiceCard shall remove the existing «Объединить» button from the КП card header.
2. The InvoiceCard shall remove the legacy `MergeModal` mount and its `mergeOpen` state.
3. The legacy `merge-modal.tsx` file and its tests shall be deleted from the repo if no other module imports them; otherwise the import-graph audit shall identify and address the remaining callers.
4. The InvoiceCard shall NOT change the contract or behaviour of the existing `mergeInvoiceItems` mutation.

### Requirement 6: Symmetry, accessibility, and error handling

**Objective:** As a procurement manager, I want the merge UX to feel like a mirror of the split UX I already learned, so that I don't have to remember a second mental model.

#### Acceptance Criteria

1. The merge icon (⋃), its hover treatment, its placement next to the unassign (✕) and split (↧) icons, and the actions-column width shall follow the same visual conventions as the split icon shipped in this session.
2. The MergeInlineDialog shall use the project's standard `Dialog` primitive (now scroll-aware) so that on short viewports the form remains fully reachable.
3. The MergeInlineDialog shall use the project's `Input`, `Label`, `Button`, `Checkbox` (or `<input type="checkbox">` if Checkbox is unavailable) components for visual consistency.
4. If the user closes the dialog with unsaved changes, the InvoiceCard shall discard form state without confirmation (consistent with split).
5. While the merge mutation is in flight, the MergeInlineDialog shall disable both submit and cancel buttons to prevent double-submit and avoid losing state during a slow network.
