# Implementation Tasks: Kanban auto-advance

## Phase A — Distribution → Searching supplier

- [ ] A.1 Create `frontend/src/entities/quote/kanban-auto-advance.ts` with the `maybeAdvanceBrandSlices` helper. Trigger types: `distribution`, `send`, `procurement_complete`. _Requirements: 1.1-1.6, 4.1-4.3, 5.1-5.4_
- [ ] A.2 Implement gate logic for `distribution` trigger (all items routed → advance). _Requirements: 1.2_
- [ ] A.3 Wire helper into `assignBrandGroup` Server Action: derive (quote, brand) from updated items, call helper after successful update. _Requirements: 1.1, 5.2_
- [ ] A.4 Unit tests for distribution trigger: full route, partial, idempotent, is_unavailable. _Requirements: 6.1_
- [ ] A.5 `npx tsc --noEmit` + `npx vitest run` green. _Requirements: 6.3_
- [ ] A.6 Browser verify: assign МОЗ to last item of a brand → kanban card moves from «Распределение» to «Поиск поставщика».

## Phase B — Send КП → Waiting prices

- [ ] B.1 Locate the existing «отправить КП» mutation that sets `invoices.sent_at`. Likely `prepareLetter` / `sendInvoiceLetter` somewhere in `entities/invoice/` or `procurement-step/letter-draft-composer.tsx`.
- [ ] B.2 Implement gate logic for `send` trigger (no extra check; just current substatus = searching_supplier). _Requirements: 2.2-2.5_
- [ ] B.3 Wire helper into the send mutation: derive distinct brands from invoice_items, call helper. _Requirements: 2.1, 2.4_
- [ ] B.4 Unit tests for send trigger: searching → advance, waiting → no-op, distributing → no-op. _Requirements: 6.1_
- [ ] B.5 Browser verify: send a КП to supplier → kanban cards for those brands move to «Ожидание цен».

## Phase C — Procurement complete → Prices ready

- [ ] C.1 Implement gate logic for `procurement_complete` trigger (all non-unavailable items of brand covered by completed invoices). _Requirements: 3.2, 3.5_
- [ ] C.2 Wire helper into `completeInvoiceProcurement` mutation. _Requirements: 3.1, 3.6_
- [ ] C.3 Unit tests for procurement_complete: all covered, one uncovered, is_unavailable excluded, already prices_ready. _Requirements: 6.1_
- [ ] C.4 Browser verify: complete the last КП covering a brand → kanban card moves to «Цены готовы».

## Cross-phase checks

- [ ] D.1 Existing tests for `assignBrandGroup`, `completeInvoiceProcurement`, send mutation pass after each phase. _Requirements: 6.2_
- [ ] D.2 Manual drag-and-drop still works for backward transitions and overrides. Spot-check on localhost. _Requirements: 4.1, 4.3_
