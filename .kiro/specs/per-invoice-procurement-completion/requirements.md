# Requirements: Per-invoice procurement completion

## Introduction

Сейчас «Завершить закупку» — флаг на квоте: один клик блокирует ВСЕ КП поставщиков в квоте и отправляет всю закупку дальше. На реальном multi-supplier флоу это плохо: один КП готов через неделю, второй — через месяц, третий ещё в переписке. Кнопка превращается в «всё или ничего» и заставляет пользователя ждать самого медленного поставщика.

Эта фича переносит completion с квоты на инвойс: каждый КП завершается отдельно своей кнопкой, блокируется только он, и его позиции уходят дальше по флоу (логистика → таможня) независимо от остальных КП. Quote-level статус становится derived («3/5 КП завершено»).

---

## Requirements

### Requirement 1: Per-invoice completion timestamp

**Objective:** As a procurement manager, I want each КП to have its own «закупка завершена» state, so that I can finalize them at different times as supplier replies arrive.

#### Acceptance Criteria

1. The DB schema shall add `procurement_completed_at TIMESTAMPTZ NULL` and `procurement_completed_by UUID REFERENCES auth.users(id) NULL` to `kvota.invoices`.
2. The migration shall be sequential (next free number) and reversible.
3. Existing rows shall start with `procurement_completed_at = NULL` (no implicit completion of historical data).
4. The DB shall NOT enforce a CHECK linking the two columns — application code maintains the «set together / clear together» invariant.

### Requirement 2: Per-КП completion button

**Objective:** As a procurement manager, I want a «Завершить закупку по КП» button on each КП card, so that I finalize a single invoice without affecting siblings.

#### Acceptance Criteria

1. The InvoiceCard shall render a «Завершить закупку по КП» button when the invoice has at least one assigned `invoice_item` AND `invoice.procurement_completed_at IS NULL`.
2. When the procurement manager clicks the button, the InvoiceCard shall call a new mutation `completeInvoiceProcurement(invoiceId)` that sets `procurement_completed_at = now()` and `procurement_completed_by = auth.uid()`.
3. The InvoiceCard shall NOT render the button when the invoice has zero assigned items (must add positions first).
4. The InvoiceCard shall toast «Закупка по КП завершена» on success and `extractErrorMessage` on failure.
5. The quote-level «Завершить закупку» button shall be removed from the procurement-step header.

### Requirement 3: Per-invoice lock state

**Objective:** As a procurement manager, I want only the completed КП to become read-only, so that other КП stay editable.

#### Acceptance Criteria

1. The InvoiceCard shall compute `isLocked = invoice.procurement_completed_at != null` instead of reading the quote-level flag.
2. When `isLocked` is true, the InvoiceCard shall hide all editable surfaces of THIS КП card: the «Параметры отгрузки» editor, the cargo-places editor, the procurement handsontable cell editing, the assign-positions button, the split/merge/undo icons.
3. When `isLocked` is true, the InvoiceCard shall continue to render the read-only fallback (existing pattern for `procurementCompleted`).
4. Sibling КП on the same quote shall NOT be locked when one of them is completed.
5. The existing `ProcurementUnlockButton` shall continue to operate, scoped to ONE invoice (clears `invoice.procurement_completed_at` and `procurement_completed_by`).

### Requirement 4: Lifecycle status badge per КП

**Objective:** As a sales / quote_controller / head, I want to glance at a КП card and see where it is in the flow, so that I don't need to open it and trace through.

#### Acceptance Criteria

1. The InvoiceCard header shall render a status badge with one of:
   - «В работе» — `procurement_completed_at IS NULL` and at least one invoice_item assigned
   - «Закупка завершена» — `procurement_completed_at IS NOT NULL` (no further downstream signal)
   - «В логистике» — completed AND at least one logistics_route exists for items in this invoice
   - «На таможне» — completed AND at least one customs row exists for items in this invoice
2. The InvoiceCard shall display the completion date next to the badge when `procurement_completed_at IS NOT NULL`, formatted as «dd.MM».
3. The badge shall update immediately after the user clicks «Завершить закупку по КП» (after the local state refresh).

### Requirement 5: Customs query — group by invoice

**Objective:** As a customs specialist, I want to see customs work scoped to a single completed КП at a time, so that I don't process items that procurement is still negotiating.

#### Acceptance Criteria

1. Customs workspace queries shall filter visible items by `invoice.procurement_completed_at IS NOT NULL` (not by `quote.procurement_completed_at`).
2. Customs lists shall group items per КП when an item belongs to a single completed invoice (the 1:1 case). Merge / split coverage cases continue to follow the existing display rules.
3. When NO invoices for a quote are completed yet, that quote's items shall NOT appear in customs workspace.
4. When SOME invoices are completed, customs workspace shall show ONLY the completed-invoice items, with the quote in a partial state.

### Requirement 6: Logistics query — already per-invoice

**Objective:** As a logistics specialist, I want the existing per-invoice grouping to keep working with the new completion model.

#### Acceptance Criteria

1. Logistics workspace queries that filter by `quote.procurement_completed_at` shall be updated to filter by `invoice.procurement_completed_at` (semantics-preserving change).
2. Existing logistics_route assignment per invoice shall continue to be created/updated as today; only the visibility filter changes.
3. Logistics workspace shall surface invoices independently — each completed КП appears regardless of sibling state.

### Requirement 7: Quote-level derived status

**Objective:** As a sales manager browsing the quotes list, I want to see how far procurement has progressed across all КП for a quote, so that I can prioritize follow-ups.

#### Acceptance Criteria

1. The quote list / dashboards shall replace the boolean «закупка завершена» indicator with a derived progress ratio: `completedInvoices / totalNonEmptyInvoices`.
2. The progress shall render as a badge: «N/M КП завершено» when 1 ≤ N < M, «Закупка завершена» when N == M, hidden when M == 0.
3. The legacy `quotes.procurement_completed_at` column shall be deprecated (kept in DB for backwards-compat with existing exports/calc), and at the application level shall be IGNORED in favour of the per-invoice flag. NO new code shall write to it; existing reads shall be migrated to the per-invoice computation.

### Requirement 8: Re-open per invoice

**Objective:** As a procurement senior / admin, I want to re-open a completed КП for fixes, so that typos don't require an admin SQL session.

#### Acceptance Criteria

1. The existing `ProcurementUnlockButton` shall be invoked per-invoice (not per-quote): clears only `invoice.procurement_completed_at` and `procurement_completed_by` for the target invoice.
2. The role/permission check on the unlock button shall remain unchanged from current behaviour.
3. After re-open, the КП card returns to editable state; sibling КП state unaffected.
4. Items already pulled into logistics/customs for this invoice — what happens to them is OUT OF SCOPE here; current behaviour (items remain visible downstream) is preserved.

### Requirement 9: Mutations and tests

**Objective:** As a developer, I want clean mutations and regression coverage so this change doesn't quietly break the flow.

#### Acceptance Criteria

1. New mutation `completeInvoiceProcurement(invoiceId: string): Promise<void>` shall set `procurement_completed_at = now()`, `procurement_completed_by = auth.uid()`, and propagate Supabase errors.
2. New mutation `reopenInvoiceProcurement(invoiceId: string): Promise<void>` shall clear both fields.
3. Unit tests for both mutations: happy path + error propagation, mirror the cargo-places.test.ts pattern.
4. `npx tsc --noEmit` clean. `npx vitest run` from `frontend/` — full suite green after the change.
5. SSR sanity tests for `invoice-card.tsx` shall continue to pass; the new completion button + badge shall not break the closed-state render.
