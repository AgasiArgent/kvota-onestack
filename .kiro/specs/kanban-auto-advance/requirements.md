# Requirements: Kanban auto-advance

## Introduction

На канбане закупок единица движения — **brand-slice** (квота × бренд). Сейчас все 3 forward-перехода между колонками работают только через ручное drag-and-drop. Функция auto-advance существует в Python (`maybe_advance_after_distribution`) но никогда не вызывается из реальных пользовательских действий — фронт пишет в Supabase напрямую. В итоге карточки застревают в «Распределении» даже когда МОЗ давно назначен, КП отправлен, или закупка завершена.

Эта фича добавляет 3 точки авто-продвижения, привязанные к существующим действиям пользователя: назначение МОЗ, отправка КП, завершение закупки по КП. Реализация — на frontend-уровне (Server Actions / mutations), без нового Python endpoint'а.

---

## Requirements

### Requirement 1: Auto-advance distributing → searching_supplier

**Objective:** As a procurement-team head, I want the kanban card to leave «Распределение» as soon as all items of the brand are routed (МОЗ-assigned or unavailable), so that I don't have to drag every card manually.

#### Acceptance Criteria

1. The `assignBrandGroup` Server Action shall, after a successful items update, evaluate every (quote_id, brand) pair affected by the update.
2. For each affected (quote_id, brand) where the current `quote_brand_substates.substatus = 'distributing'`, the Server Action shall query whether ALL `quote_items` matching that (quote_id, brand) have `assigned_procurement_user IS NOT NULL OR is_unavailable IS TRUE`.
3. If the condition holds, the Server Action shall update `quote_brand_substates.substatus = 'searching_supplier'` and append a row to `status_history` with `from_substatus='distributing'`, `to_substatus='searching_supplier'`, `transitioned_by=auth.uid()`, `reason='auto: all items routed'`.
4. The Server Action shall NOT advance brand-slices that are not in `distributing` (e.g. already in `searching_supplier`).
5. The Server Action shall remain idempotent — repeated calls with the same input shall not produce duplicate `status_history` rows for an already-advanced slice.
6. When the condition does not hold (some items unrouted), the Server Action shall leave the slice in `distributing` silently.

### Requirement 2: Auto-advance searching_supplier → waiting_prices on send

**Objective:** As a procurement manager, I want the brand-slices represented in a КП to advance to «Ожидание цен» when I send the КП to the supplier, so that the kanban reflects what I just did without an extra click.

#### Acceptance Criteria

1. The mutation that sets `invoices.sent_at` shall, after the successful update, identify the set of brands present in the invoice's `invoice_items`.
2. For each (invoice.quote_id, brand) pair where `quote_brand_substates.substatus = 'searching_supplier'`, the mutation shall update it to `waiting_prices` and append a `status_history` row.
3. The mutation shall NOT advance brand-slices in any other substatus (idempotent — won't move from `prices_ready` back).
4. The mutation shall handle the multi-supplier case: an invoice covering 2 brands advances both brand-slices.
5. Re-sending an already-sent invoice (`sent_at` already set) shall NOT trigger advance again.

### Requirement 3: Auto-advance waiting_prices → prices_ready on procurement completion

**Objective:** As a procurement manager, I want a brand-slice to land in «Цены готовы» when I've completed all the КП covering that brand's items, so that downstream stages see ready slices automatically.

#### Acceptance Criteria

1. The `completeInvoiceProcurement` mutation shall, after stamping `procurement_completed_at`, evaluate every brand present in the completed invoice's `invoice_items`.
2. For each (quote_id, brand) where `quote_brand_substates.substatus = 'waiting_prices'`, the mutation shall check coverage: every `quote_item` of that (quote_id, brand) where `is_unavailable IS NOT TRUE` shall be covered by at least one `invoice_item` belonging to an invoice with `procurement_completed_at IS NOT NULL`.
3. If the coverage condition holds, the mutation shall update the brand-slice to `prices_ready` and append a `status_history` row with `from_substatus='waiting_prices'`, `to_substatus='prices_ready'`, `transitioned_by=auth.uid()`, `reason='auto: all КП for this brand completed'`.
4. The mutation shall NOT advance brand-slices that are not in `waiting_prices`.
5. Items marked `is_unavailable=true` shall be excluded from the coverage requirement.
6. Re-opening an invoice via `reopenInvoiceProcurement` shall NOT auto-rollback advanced brand-slices (one-way auto-advance; manual drag is the recovery path).

### Requirement 4: Manual drag-and-drop unchanged

**Objective:** As a procurement manager, I want manual kanban drag-and-drop to keep working exactly as before, so that I can override auto-advance when reality differs from the heuristic.

#### Acceptance Criteria

1. The existing `transition_substatus` Python flow shall continue to handle drag-and-drop without modification.
2. Auto-advance shall ONLY move forward (distributing → searching_supplier → waiting_prices → prices_ready). Backward transitions stay manual.
3. A manually-set substatus shall NOT be overridden by auto-advance on a subsequent action (e.g. dragging back from waiting_prices to searching_supplier, then assigning a new МОЗ, shall NOT auto-advance to searching_supplier — the rule already encodes "only if currently in `distributing`").

### Requirement 5: Auth, idempotency, error handling

**Objective:** As a developer, I want auto-advance to be safe under concurrent edits and not break the originating action when it fails.

#### Acceptance Criteria

1. Auto-advance shall use the `createAdminClient()` to bypass RLS, since the originating Server Action already validated user permissions.
2. Auto-advance failures (DB error, network) shall log and continue — they shall NOT roll back the originating action (e.g. the МОЗ assignment must persist even if substatus update fails).
3. Auto-advance shall be idempotent: a second invocation against the same state shall be a no-op.
4. The `transitioned_by` field on auto-advance `status_history` rows shall be the calling user's `auth.uid()`, not a system user.

### Requirement 6: Tests

**Objective:** As a developer, I want regression coverage so future refactors don't silently break the auto-advance behaviour.

#### Acceptance Criteria

1. Unit tests for the new helper(s) shall cover: full advance, partial state (no advance), already-advanced (no-op), edge case `is_unavailable=true`, mixed-brand quote (only target brand advances).
2. Existing tests for `assignBrandGroup`, `completeInvoiceProcurement`, and the «send» mutation shall continue to pass.
3. `npx tsc --noEmit` clean. `npx vitest run` from `frontend/` — full suite green.
