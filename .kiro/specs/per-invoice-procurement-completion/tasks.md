# Implementation Tasks: Per-invoice procurement completion

## 1. DB migration

- [ ] 1.1 Add migration `NNN_per_invoice_procurement_completion.sql` adding `procurement_completed_at TIMESTAMPTZ` and `procurement_completed_by UUID` to `kvota.invoices`. Partial index on `procurement_completed_at IS NOT NULL`. Comments. _Requirements: 1.1, 1.2, 1.3, 1.4_

## 2. New mutations

- [ ] 2.1 Add `completeInvoiceProcurement(invoiceId)` and `reopenInvoiceProcurement(invoiceId)` to `entities/quote/mutations.ts`. _Requirements: 9.1, 9.2_
- [ ] 2.2 Unit tests for both mutations: happy + error path. New file `__tests__/procurement-completion.test.ts`. _Requirements: 9.3_

## 3. InvoiceCard lock + button + badge

- [ ] 3.1 Switch `procurementCompleted` source to read from `invoice.procurement_completed_at` instead of `quote.procurement_completed_at`. _Requirements: 3.1, 3.2, 3.3, 3.4_
- [ ] 3.2 Add «Завершить закупку по КП» button in the КП header bar; gate on `!procurementCompleted && invoiceItems.length > 0`. Wire to `completeInvoiceProcurement`. _Requirements: 2.1, 2.2, 2.3, 2.4_
- [ ] 3.3 Add lifecycle badge (4 states: in-work / procurement-done / logistics / customs) with completion date next to it. _Requirements: 4.1, 4.2, 4.3_
- [ ] 3.4 Update `ProcurementUnlockButton` to use the new `reopenInvoiceProcurement` mutation. _Requirements: 8.1, 8.3_

## 4. Procurement-step header cleanup

- [ ] 4.1 Remove the top-level «Завершить закупку» button from `procurement-step.tsx` (or wherever it lives). Remove the now-orphan quote-level mutation if any. _Requirements: 2.5_

## 5. Customs query refactor

- [ ] 5.1 Audit customs workspace queries — list every place that filters by `quote.procurement_completed_at`. _Requirements: 5.1, 5.3_
- [ ] 5.2 Switch each filter to `invoice.procurement_completed_at IS NOT NULL`. Update item grouping to be per-invoice when 1:1 coverage. _Requirements: 5.1, 5.2, 5.4_

## 6. Logistics query verification

- [ ] 6.1 Audit logistics queries — confirm/correct filter to use per-invoice flag. Patch any quote-level reads. _Requirements: 6.1, 6.2, 6.3_

## 7. Quote progress badge

- [ ] 7.1 Add a `getProcurementProgress(invoices)` helper. Replace existing «закупка завершена» indicator in quote list/dashboards with the derived progress badge. _Requirements: 7.1, 7.2_
- [ ] 7.2 Audit reads of `quote.procurement_completed_at` across the codebase. Replace each with the per-invoice computation OR remove if downstream is already invoice-aware. _Requirements: 7.3_

## 8. Verification

- [ ] 8.1 `npx tsc --noEmit` and full `npx vitest run` green. _Requirements: 9.4, 9.5_
- [ ] 8.2 Localhost browser-test: create quote → 2 КП → complete one → verify per-КП lock + badge + completion date → second stays editable → re-open works → customs/logistics see partial state correctly. _Requirements: 4.3, 5.4, 8.3_
