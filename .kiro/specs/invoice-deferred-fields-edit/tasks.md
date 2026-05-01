# Implementation Tasks: Editable deferred-fill fields

## 1. New cargo-place mutations

- [ ] 1.1 Add `addCargoPlace`, `updateCargoPlace`, `deleteCargoPlace` exports to `entities/quote/mutations.ts`. Compute next position in `addCargoPlace` via `MAX(position) + 1` query. Use `Partial<EditableCargoPlace>` for `updateCargoPlace`. _Requirements: 3.1, 3.2, 3.3, 3.4_
- [ ] 1.2 Unit tests for the three mutations using the existing fake-supabase pattern in `entities/quote/__tests__/mutations.test.ts`. Cover happy path + error propagation. _Requirements: 6.1_

## 2. Invoice-level field editor in card

- [ ] 2.1 Add local state for `pickupCountryCodeLocal`, `pickupCity`, `incotermsLocal`, `currencyLocal`, `vatRateLocal` (synced from `invoice.*` props). _Requirements: 1.1, 1.5_
- [ ] 2.2 Add `handleSaveInvoiceField` helper that calls `updateInvoice` with a no-op guard, success toast, error toast preserving input. _Requirements: 1.2, 1.3, 5.3, 5.4, 5.5_
- [ ] 2.3 Render the 5-input row (CountryCombobox + city + incoterms select + currency select + vat input) inside the existing weight-segment container, gated on `!isLocked`. Save text/number on `onBlur`, selects on `onChange`. _Requirements: 1.1, 1.4, 1.6, 1.7, 4.1, 4.2, 4.3, 5.1, 5.2_

## 3. Cargo-place editor

- [ ] 3.1 Replace the read-only cargo-places list with editable rows: 4 numeric inputs + ✕ button per place. Save each field on `onBlur` via `updateCargoPlace`. _Requirements: 2.1, 2.3_
- [ ] 3.2 Add the «+ Добавить место» button below the list; on click call `addCargoPlace(invoiceId, blank)` and refetch via existing `fetchCargoPlaces`. _Requirements: 2.2_
- [ ] 3.3 Wire the ✕ button to `deleteCargoPlace(placeId)` + refetch. _Requirements: 2.4_
- [ ] 3.4 Hide all add/edit/delete affordances when `isLocked`; fall back to read-only display. _Requirements: 2.5, 2.6_

## 4. Read-only fallback for locked state

- [ ] 4.1 When `isLocked`, render a single read-only summary block listing country/city/incoterms/currency/vat/places — same data, no inputs. Reuse the existing `hasInvoiceWeight` block as the entry point. _Requirements: 1.4, 2.5_

## 5. Verification

- [ ] 5.1 `npx tsc --noEmit` clean. `npx vitest run` from `frontend/` — full suite green (existing 474 + new mutation tests). _Requirements: 6.3_
- [ ] 5.2 Localhost browser-test: create empty КП → expand card → edit each invoice-level field → reload → verify; add 2 cargo places → edit one → delete one → reload → verify. _Requirements: 6.4_
