# Design: Editable deferred-fill fields on the КП card

## Overview

Расширяем текущий блок «Вес и габариты» в `invoice-card.tsx` до полноценного «Параметры отгрузки» editor: добавляем 5 invoice-level инпутов (страна, город, инкотермс, валюта, ставка НДС) и CRUD для cargo places. Серверная семантика — повторное использование `updateInvoice` плюс три новые тонкие mutations для `invoice_cargo_places`.

## Architecture pattern

```
invoice-card.tsx
├─ existing weight/volume inputs               (kept, reused)
├─ NEW: invoice-level field row                 (5 inputs, onBlur/onChange save)
└─ existing cargo places list
   └─ NEW: each row becomes editable + add/remove buttons
```

Никаких новых компонентов — UI inline в карточке. Никаких новых ролевых проверок — RLS на `invoices` / `invoice_cargo_places` уже разрешают procurement писать.

## Mutation contracts (new)

```ts
// entities/quote/mutations.ts (additions)
export async function addCargoPlace(
  invoiceId: string,
  place: CargoPlaceInput
): Promise<{ id: string; position: number }>;

export async function updateCargoPlace(
  placeId: string,
  updates: Partial<CargoPlaceInput>
): Promise<void>;

export async function deleteCargoPlace(placeId: string): Promise<void>;
```

`CargoPlaceInput` уже экспортируется из того же файла (используется `createInvoice`). Для `addCargoPlace` входной объект может содержать null-поля (новое место создаётся пустым), поэтому `CargoPlaceInput`-тип ослабляем до `{ weight_kg: number | null; length_mm: number | null; ... }` или используем отдельный `Partial<CargoPlaceInput>` для add. Чтобы не ломать существующих callers (createInvoice), вводим новый narrow тип `EditableCargoPlace = { weight_kg: number | null; length_mm: number | null; width_mm: number | null; height_mm: number | null }` и используем его для всех 3-х новых mutations.

`addCargoPlace` сам вычисляет следующий `position` — берёт `MAX(position)` для invoice + 1.

`updateCargoPlace` принимает `Partial`, чтобы UI мог сохранять одно поле за раз без лишних read-modify-write циклов.

`deleteCargoPlace` тривиален — `DELETE FROM invoice_cargo_places WHERE id = $1`.

## State shape inside invoice-card

```ts
// Existing
const [weightKg, setWeightKg] = useState(invoice.total_weight_kg?.toString() ?? "");
const [volumeM3, setVolumeM3] = useState(invoice.total_volume_m3?.toString() ?? "");

// NEW (invoice-level)
const [pickupCity, setPickupCity] = useState(invoice.pickup_city ?? "");
const [pickupCountryCodeLocal, setPickupCountryCodeLocal] = useState<string | null>(
  invoice.pickup_country_code ?? null
);
const [incotermsLocal, setIncotermsLocal] = useState(invoice.supplier_incoterms ?? "");
const [currencyLocal, setCurrencyLocal] = useState(invoice.currency ?? "USD");
const [vatRateLocal, setVatRateLocal] = useState(
  invoice.vat_rate != null ? String(invoice.vat_rate) : ""
);

// Cargo places — new editable buffer
type EditableCargoRow = {
  id: string;
  weight_kg: string;
  length_mm: string;
  width_mm: string;
  height_mm: string;
};
const [cargoEdits, setCargoEdits] = useState<EditableCargoRow[]>([]);
```

`cargoEdits` синхронизируется с `cargoPlaces` (server state) через `useEffect`. Inputs читают из `cargoEdits`, save идёт через mutations, после успеха — `setRefreshKey((k) => k + 1)` и cargoPlaces refetch.

## Save flow

| Field | Trigger | Save fn |
|---|---|---|
| pickup_country_code | onChange (CountryCombobox) | `updateInvoice(id, { pickup_country_code: code, pickup_country: ruName })` |
| pickup_city | onBlur | `updateInvoice(id, { pickup_city: trimmed \|\| null })` |
| supplier_incoterms | onChange | `updateInvoice(id, { supplier_incoterms: value \|\| null })` |
| currency | onChange | `updateInvoice(id, { currency: value })` |
| vat_rate | onBlur | `updateInvoice(id, { vat_rate: parsed \|\| null })` |
| cargo place field | onBlur | `updateCargoPlace(placeId, { [field]: parsed })` |
| add cargo place | button click | `addCargoPlace(invoiceId, blank)` → refresh |
| delete cargo place | button click | `deleteCargoPlace(placeId)` → refresh |

No-op guard: each save fn compares the new value to the current `invoice.*` value (or `cargoPlaces[i].*`) and skips when equal.

## Layout

```
┌─ Параметры отгрузки ──────────────────────────────────────────────┐
│ Страна:  [CountryCombobox]    Город:  [Input]                       │
│ Инкотермс:  [select]    Валюта:  [select]    НДС, %:  [Input]       │
│                                                                     │
│ Грузовые места (N):                                  [+ Добавить]  │
│   Место 1:  [Вес кг]  [Дл мм]  [Ш мм]  [В мм]   ✕                  │
│   Место 2:  [Вес кг]  [Дл мм]  [Ш мм]  [В мм]   ✕                  │
│                                                                     │
│ Итого: Вес [_____] кг   Объём [_____] м³                            │
└─────────────────────────────────────────────────────────────────────┘
```

Рендерится только когда `!isLocked`. Когда `isLocked`, остаётся текущий read-only вариант.

## Lock-state read-only fallback

Существующая ветка `hasInvoiceWeight` уже рендерит read-only сводку. Расширяем её до полного read-only формата с теми же полями: страна / город / инкотермс / валюта / НДС / места. Один и тот же блок, разные внутренности.

## Trade-offs and risks

1. **Inline vs expandable.** Текущий weight-bar занимает мало места; новый блок будет высотой ~150-200px. Пробуем inline без collapse-toggle (всегда видно). Если по UX тесно — добавим toggle в follow-up. Acceptance criterion 4.4 запрещает модалки — оставляем inline.
2. **Save granularity.** Каждое поле сохраняется отдельно (5 invoice + 4×N cargo). При быстром заполнении это может быть много сетевых вызовов. Smoothing через onBlur (а не onChange) для текстовых/числовых полей решает это для ручного ввода. Bulk save можно добавить позже.
3. **Cargo places refresh.** После add/delete нужно перетащить актуальный список с сервера. Используем существующий `fetchCargoPlaces` + локальный refetch (не `router.refresh` — слишком тяжело для CRUD одной строки).
4. **NULL handling.** Cargo place's CHECK constraints (если есть) против NULL не должны нас удивлять — `updateCargoPlace` принимает `Partial`, мы пишем только то, что пользователь ввёл. Полностью пустое место → null во всех 4 полях, это валидно (миграция 235 разрешила NULL для total_weight; cargo places наследуют ту же логику). Если поставщик ответит с настоящими цифрами — пользователь подправит.
5. **Country code/name dual write.** Существующий `pickup_country` (text, RU-name) сосуществует с `pickup_country_code` (alpha-2). При сохранении из CountryCombobox пишем оба — code via `findCountryByCode(code)?.nameRu` для текстового поля. Тот же паттерн что в `createInvoice`.

## Test strategy

**Unit (Vitest, fake supabase client):**
- `addCargoPlace` — happy path (returns id + position), error propagation
- `updateCargoPlace` — happy path, partial update, error
- `deleteCargoPlace` — happy path, error

**SSR sanity:**
- `invoice-card.test.tsx` — existing tests must continue to pass; new editor renders without throwing in closed-state SSR

**Browser (manual on localhost):**
- Create empty КП → open card → fill each field → reload → verify
- Add 2 cargo places → edit → delete → reload → verify

## Requirement traceability

| Req | Where |
|---|---|
| 1.1 | inputs row 1 + row 2 |
| 1.2 | onBlur/onChange handlers call `updateInvoice` |
| 1.3 | `toast.success("Сохранено")` / `toast.error(...)` |
| 1.4 | render-gate on `!isLocked` |
| 1.5 | `<CountryCombobox>` reused |
| 1.6 | `INCOTERMS_2020` reused |
| 1.7 | `SUPPORTED_CURRENCIES` reused |
| 2.1 | per-row inputs in cargo section |
| 2.2 | `+ Добавить место` button + `addCargoPlace` |
| 2.3 | onBlur per-field + `updateCargoPlace` |
| 2.4 | ✕ button + `deleteCargoPlace` |
| 2.5 | render-gate on `!isLocked` |
| 2.6 | single section in card |
| 3.1-3.4 | new mutations |
| 4.1-4.5 | inline layout, no modal, reuse primitives |
| 5.1-5.5 | save handlers + no-op guard + toast |
| 6.1-6.4 | unit tests, SSR sanity, full-suite green, browser plan |
