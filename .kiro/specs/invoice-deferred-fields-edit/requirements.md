# Requirements: Editable deferred-fill fields on the КП card

## Introduction

Когда мы сделали поля КП-создания необязательными (фаза «Создание КП поставщику»), мы оставили их пустыми, но не дали способ заполнить позже без миграции данных. Сейчас в карточке КП виден только инпут «Вес / Объём» (агрегатные значения по invoice). Менеджер закупок не может из карточки добавить страну/город отгрузки, выбрать инкотермс, поменять валюту, ставку НДС или отредактировать грузовые места — всё это становится доступным только в момент создания.

Эта фича добавляет редактирование всех тех же полей после создания КП — прямо в карточке, на месте текущего блока «Вес и габариты». Серверная семантика стандартная: invoice-level поля идут через `updateInvoice`, грузовые места получают новые CRUD mutations.

---

## Requirements

### Requirement 1: Editable invoice-level fields

**Objective:** As a procurement manager, I want to fill in the country / city / incoterms / currency / VAT rate after the КП is created, so that I'm not forced to enter them when creating an empty КП.

#### Acceptance Criteria

1. The InvoiceCard shall expose editable inputs for: `pickup_country` + `pickup_country_code`, `pickup_city`, `supplier_incoterms`, `currency`, `vat_rate`.
2. When the procurement manager edits any of those fields and the field loses focus, the InvoiceCard shall persist the change via the existing `updateInvoice` mutation.
3. The InvoiceCard shall show a brief success toast on each successful save and a non-blocking error toast on failure (preserving current input).
4. The InvoiceCard shall hide the editable inputs and fall back to read-only display when `procurement_completed_at` is set on the parent quote (the locked state).
5. The country picker shall use the existing `CountryCombobox` component from `@/shared/ui/geo` for parity with the create modal.
6. The incoterms picker shall use the existing `INCOTERMS_2020` list and same `<select>` styling as the create modal.
7. The currency picker shall use `SUPPORTED_CURRENCIES` and same `<select>` styling.

### Requirement 2: Editable cargo places

**Objective:** As a procurement manager, I want to add, edit, and delete cargo places after creation, so that I can fill them in once the supplier sends back the actual packing details.

#### Acceptance Criteria

1. The InvoiceCard shall display every cargo place in `invoice_cargo_places` for the current invoice as an editable row with four numeric inputs (вес, длина, ширина, высота) plus a delete button.
2. The InvoiceCard shall expose a «+ Добавить место» button that creates a new cargo place row via a new `addCargoPlace` mutation; the new row appends at the next position and starts empty.
3. The InvoiceCard shall persist edits via a new `updateCargoPlace` mutation on field blur; partial values (any field empty) are persisted as-is — DB CHECK constraints govern validity at write time.
4. The InvoiceCard shall delete a cargo place via a new `deleteCargoPlace` mutation; deletion is immediate (no undo) but confirmed implicitly via toast.
5. The InvoiceCard shall hide all add/edit/delete affordances when the parent quote is locked (`procurement_completed_at` is set), falling back to read-only display.
6. The cargo-places editor shall live inside the same expanded section as the invoice-level fields, not as a separate panel.

### Requirement 3: Mutation contracts

**Objective:** As a developer, I want clean, testable mutations for cargo places that mirror the existing patterns in `entities/quote/mutations.ts`, so that future UIs (e.g. logistics) can reuse them.

#### Acceptance Criteria

1. `addCargoPlace(invoiceId: string, place: CargoPlaceInput): Promise<{ id: string; position: number }>` shall insert one row, computing `position = MAX(position) + 1` for that invoice. Returns the new row id + position.
2. `updateCargoPlace(placeId: string, updates: Partial<CargoPlaceInput>): Promise<void>` shall update only the supplied fields. Empty/undefined fields are left untouched.
3. `deleteCargoPlace(placeId: string): Promise<void>` shall delete the single row by id.
4. None of the above shall touch invoice-level `total_weight_kg` / `total_volume_m3` — those remain explicit invoice-level fields managed by Requirement 1.

### Requirement 4: UI consistency and layout

**Objective:** As a procurement manager, I want the new editing surface to feel like a natural extension of the current «Вес и габариты» bar, so that there's no second panel to learn.

#### Acceptance Criteria

1. The InvoiceCard shall render the deferred-fields editor inside the same `bg-muted/30 border-b` container as the current weight/volume inputs.
2. The editor shall use a compact 2-row layout: row 1 contains country / city / incoterms / currency / VAT side-by-side; row 2 contains cargo places (existing `<Package>` segment, now editable).
3. The editor shall reuse the project's standard `Input`, `Label`, `Button`, and `CountryCombobox` components — no custom field primitives.
4. The editor shall NOT introduce additional modals or dialogs — every field is inline.
5. The editor shall visually align with the design system's spacing (gap-2, gap-3) and typography conventions already established in the КП card.

### Requirement 5: Save UX and error handling

**Objective:** As a procurement manager, I want clear feedback on saves and errors, so that I trust changes are persisted without verifying via a refresh.

#### Acceptance Criteria

1. The InvoiceCard shall save text/number invoice-level fields on `onBlur` (not on every keystroke).
2. The InvoiceCard shall save select fields (country, incoterms, currency) on `onChange`.
3. The InvoiceCard shall NOT issue a save when the new value equals the current value (no-op).
4. The InvoiceCard shall toast `«Сохранено»` on success and `extractErrorMessage(err)` on failure, with `«Не удалось сохранить»` as fallback.
5. The InvoiceCard shall keep the user's input visible after a failed save (do not revert).

### Requirement 6: Tests and verification

**Objective:** As a developer, I want regression coverage for the new mutations and a clean way to verify the UI on localhost, so that future changes don't quietly break the deferred-fill flow.

#### Acceptance Criteria

1. New unit tests in `entities/quote/__tests__/` shall cover `addCargoPlace`, `updateCargoPlace`, `deleteCargoPlace` happy paths + propagation of Supabase errors.
2. Existing tests for `invoice-card.tsx` shall continue to pass; the new editor section shall not break SSR sanity checks.
3. `npx tsc --noEmit` and `npx vitest run` from `frontend/` shall both report zero errors after the change.
4. Localhost browser-test plan: create an empty КП → open card → edit each invoice-level field → reload → verify persistence; add 2 cargo places → edit one → delete one → reload → verify state.
