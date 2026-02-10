# Blueprint: Spec Control Page Redesign

**Task:** Redesign /dashboard?tab=spec-control (Контроль спецификаций)
**Priority:** UX improvement
**Estimated scope:** Medium (single page, backend data already exists)

---

## Current State (Problems)

**URL:** /dashboard?tab=spec-control

### What exists now:
1. **4 status cards** at top: Ожидают спецификации (4), На проверке (0), Утверждены (0), Подписаны (1)
2. **Итого summary line:** $35,704 | Профит: $2,081
3. **Dropdown filter** ("Фильтр:" with select: Все / Ожидают / Черновики / На проверке / Утверждены / Подписаны)
4. **3 separate tables:**
   - "КП ожидающие спецификации" — columns: № КП, КЛИЕНТ, ТИП СДЕЛКИ, СУММА, ДАТА, [Создать спецификацию]
   - "Спецификации на проверке" — columns: № СПЕЦИФИКАЦИИ, КЛИЕНТ, СТАТУС, ВАЛЮТА, СУММА, ПРОФИТ, ДАТА
   - "Подписанные спецификации" — same columns as "на проверке"

### Problems:
- **3 tables showing same data** — redundant vertical space, user scrolls a lot
- **Different column sets** — "Ожидающие КП" table lacks ВАЛЮТА/ПРОФИТ columns that spec tables have
- **Dropdown filter is disconnected** — sits in its own section above the tables, not inline
- **No search** — can't type to find a specific client or spec number
- **Empty sections take space** — "На проверке: 0" still renders a full table with header + empty message

---

## Proposed Design

### Layout

```
┌─────────────────────────────────────────────────────┐
│ Контроль спецификаций                               │
│                                                     │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐│
│ │ 4        │ │ 2        │ │ 0        │ │ 1        ││
│ │ Ожидают  │ │ Черновик  │ │ Проверка │ │ Подписаны││
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘│
│                                                     │
│ Итого: $35,704 | Профит: $2,081                    │
│                                                     │
│ ┌─────────────────────┐  [Ожидают] [Черновик]      │
│ │ 🔍 Поиск по №/клиенту│  [Проверка] [Подписаны]  │
│ └─────────────────────┘  [Все]                     │
│                                                     │
│ ┌───┬────────┬──────────┬────────┬─────┬───────┬───┐
│ │ # │ НОМЕР  │ КЛИЕНТ   │ СТАТУС │ VAL │ СУММА │...│
│ ├───┼────────┼──────────┼────────┼─────┼───────┼───┤
│ │   │        │          │        │     │       │   │
│ │ --- Ожидают спецификации ---                  │   │
│ │ 1 │Q-01-16 │ООО Тест 2│ Ожидает│ EUR │28,629 │...│
│ │ 2 │Q-01-14 │Test Co   │ Ожидает│ USD │27,365 │...│
│ │ 3 │Q-01-03 │Test Co   │ Ожидает│ RUB │17,557 │...│
│ │ 4 │Q-01-01 │Test Co   │ Ожидает│ RUB │84,692 │...│
│ │   │        │          │        │     │       │   │
│ │ --- Черновики ---                              │   │
│ │ 5 │S-02-XX │Client A  │Черновик│ USD │ 5,000 │...│
│ │   │        │          │        │     │       │   │
│ │ --- Подписаны ---                              │   │
│ │ 6 │Q-02-44 │Test Co   │Подписан│ USD │ 2,232 │...│
│ └───┴────────┴──────────┴────────┴─────┴───────┴───┘
│                                                     │
│ Записей: 6                                         │
└─────────────────────────────────────────────────────┘
```

### Key Changes

#### 1. Single unified table
- Merge all 3 tables into ONE
- Sorted by status priority: Ожидают → Черновики → На проверке → Утверждены → Подписаны
- Group headers (light gray row separators) between status groups
- Unified columns: №, НОМЕР (КП or Спецификации), КЛИЕНТ, СТАТУС, ВАЛЮТА, СУММА, ПРОФИТ, ДАТА, ДЕЙСТВИЕ

#### 2. Status chips as filter (replace dropdown)
- Clickable pill/chip buttons inline with search
- Each chip shows count: `Ожидают (4)` `Черновики (2)` `Подписаны (1)`
- Multi-select: click to toggle, active chips highlighted
- "Все" chip to reset
- Chips sit on the same line as search — no separate "Фильтр:" section

#### 3. Search input
- Text input with search icon, left-aligned
- Searches across: spec number, КП number, client name
- Instant filter (on keyup, debounced 300ms)
- Placeholder: "Поиск по номеру или клиенту..."

#### 4. Status column with colored badges
- Ожидает → orange badge
- Черновик → gray badge
- На проверке → blue badge
- Утверждена → green badge
- Подписана → green filled badge

#### 5. Action column (unified)
- "Ожидает" rows → "Создать спецификацию" link (green text)
- "Черновик/На проверке" rows → "Редактировать" link
- "Подписана" rows → "Просмотр" link

#### 6. Keep status cards at top
- Keep the 4 colored count cards — they provide quick overview
- Cards are also clickable as filter shortcuts (click "Подписаны" card → filters to signed only)

---

## Data Model (no changes needed)

Current backend already provides all data. The page currently fetches:
- Quotes pending specification (from quotes table where status = pending_spec)
- Specifications in various statuses (from specifications table)

Just need to merge them into a single list in the route handler.

---

## Implementation Plan

### Step 1: Modify route handler
- File: `main.py` (spec-control route)
- Merge all queries into single combined list
- Add `type` field: "quote" (pending) vs "spec" (existing)
- Sort by status priority, then by date desc

### Step 2: Replace template
- Remove 3 separate table renders
- Replace dropdown filter with chip buttons
- Add search input with HTMX `hx-get` on keyup (debounced)
- Single table with group separators
- Status badges with colors

### Step 3: HTMX filtering
- `hx-get="/dashboard?tab=spec-control&status=pending&q=..."`
- Filter params: `status` (comma-separated), `q` (search text)
- Return only the table body for swap
- Target: `#spec-table-body`

### Step 4: Clickable cards
- Each status card gets `hx-get` with status filter
- Clicking card highlights it and filters table

---

## Columns Spec

| Column | Source (Quote) | Source (Spec) | Notes |
|--------|---------------|---------------|-------|
| № | row number | row number | sequential |
| НОМЕР | quote.idn | spec.idn | Q-YYYYMM-NNNN format |
| КЛИЕНТ | quote.customer.name | spec.customer.name | |
| СТАТУС | "Ожидает" (fixed) | spec.status | colored badge |
| ВАЛЮТА | quote.currency | spec.currency | |
| СУММА | quote items sum | spec items sum | |
| ПРОФИТ | — (dash) | spec profit | quotes don't have profit yet |
| ДАТА | quote.created_at | spec.created_at | |
| ДЕЙСТВИЕ | "Создать спецификацию" | "Просмотр"/"Редактировать" | link |

---

## Filter Chips HTML (reference)

```html
<div class="flex items-center gap-2 mb-4">
  <input type="text" placeholder="Поиск по номеру или клиенту..."
         class="border rounded px-3 py-1.5 w-64"
         hx-get="/spec-control/filter" hx-trigger="keyup changed delay:300ms"
         hx-target="#spec-table-body" name="q">

  <button class="px-3 py-1 rounded-full text-sm bg-blue-100 text-blue-700"
          hx-get="/spec-control/filter?status=all" hx-target="#spec-table-body">
    Все (7)
  </button>
  <button class="px-3 py-1 rounded-full text-sm bg-orange-100 text-orange-700">
    Ожидают (4)
  </button>
  <button class="px-3 py-1 rounded-full text-sm bg-gray-100 text-gray-700">
    Черновики (2)
  </button>
  <button class="px-3 py-1 rounded-full text-sm bg-blue-100 text-blue-700">
    Проверка (0)
  </button>
  <button class="px-3 py-1 rounded-full text-sm bg-green-100 text-green-700">
    Подписаны (1)
  </button>
</div>
```

---

## Testing Criteria

After implementation, verify:
- [ ] Single table shows all specs and pending quotes
- [ ] Status chips filter correctly (multi-select)
- [ ] Search by number and client name works
- [ ] Group separators between status groups
- [ ] Status badges colored correctly
- [ ] "Создать спецификацию" link works for pending quotes
- [ ] "Просмотр" link works for signed specs
- [ ] Итого summary updates when filtered
- [ ] Status cards at top are clickable as filter shortcuts
- [ ] Empty state when no results match filter
- [ ] No console errors
