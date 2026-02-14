# Implementation Plan: User Feedback (12.02.2026+)

**Created:** 2026-02-14
**Source:** ТЗ.docx (1).pdf — items from 12.02.2026 onwards
**Estimated Sessions:** 5-6

---

## Codebase State (from exploration)

- **Tabs:** Centralized in `quote_detail_tabs()` at main.py:14760. Current order: Сводка, Продажи, Закупки, Логистика, Таможня, Контроль, Кост-анализ, Документы, Цепочка документов + finance tabs when deal exists.
- **Download buttons:** At main.py:9541-9546. Currently hidden only for `draft` status. Need granular per-status visibility.
- **Workflow tracking exists:** `assigned_procurement_users`, `assigned_logistics_user`, `assigned_customs_user`, `procurement_completed_at`, `logistics_completed_at`, `customs_completed_at`, `created_by`.
- **Workflow tracking MISSING:** `quote_controller_id`, `quote_control_completed_at`, `spec_controller_id`, `spec_control_completed_at` — needed for Сводка tab auto-fill.
- **Invoice bug:** `column quote_items.name does not exist` — Python code already fixed (uses `product_name`), may have been fixed by migration 134. Need to verify on production.
- **Workflow tracking for Сводка:** Only 4 new DB columns needed (2 UUIDs + 2 timestamps). User names come from existing user profiles table via JOIN.

---

## Session 1: Bugs + Quick Wins

**Goal:** Fix blocking bugs that affect daily user work.

### Task 1.1: Verify `quote_items.name` bug is fixed on production
- **Bug:** Error `column quote_items.name does not exist` when creating/editing procurement invoices
- **Status:** Python code already uses `product_name` correctly. Migration 134 likely fixed the DB function. Screenshot may be from before the fix.
- **Action:** Verify in browser that procurement invoice creation works. If still broken, check DB function on VPS.
- **Test:** Create a procurement invoice — confirm no error

### Task 1.2: Conditional download button visibility
- **Requirement:** (from ТЗ "Общие исправления — ВАЖНО")
  - Валидация Excel (МОП) → visible only during quote preparation stages (draft through pending_quote_control)
  - КП PDF → visible only AFTER Quote Control passed (pending_spec_control and later)
  - Счет PDF → visible only AFTER Spec Control passed (deal stage)
  - Спецификация DOC → visible only AFTER Spec Control passed (deal stage)
- **Current:** All buttons shown for any non-draft status (main.py:9541-9546)
- **Fix:** Replace `if workflow_status != "draft"` with per-button status checks:
  ```python
  # Status progression: draft → pending_procurement → pending_logistics → pending_customs →
  # pending_sales_review → pending_quote_control → pending_approval → approved →
  # sent_to_client → pending_spec_control → pending_signature → deal

  post_quote_control = workflow_status in ('pending_approval', 'approved', 'sent_to_client',
                                            'pending_spec_control', 'pending_signature', 'deal')
  post_spec_control = workflow_status in ('pending_signature', 'deal')

  # Excel validation - available during preparation
  Button("Валидация Excel") if workflow_status != "draft" else None,
  # КП PDF - only after quote control
  Button("КП PDF") if post_quote_control else None,
  # Счёт PDF - only after spec control
  Button("Счёт PDF") if post_spec_control else None,
  # Спецификация DOC - only after spec control
  Button("Спецификация DOC") if post_spec_control else None,
  ```
- **Files:** main.py (around line 9541)
- **Test:** Check different quotes at different statuses — buttons should appear/disappear correctly

### Task 1.3: Fix logistics not pulling through in Продажи tab
- **Bug:** Logistics cost shows "—" in the Итого block on Продажи tab
- **Investigation:** Check how logistics cost is queried/displayed in the sales overview section
- **Files:** main.py (Продажи tab rendering, likely around line 8000-9000)
- **Test:** View a quote with logistics data filled — should show logistics cost

**Session 1 estimated effort:** 2-3 hours

---

## Session 2: Tab Restructuring + DB Migrations for Workflow Tracking

**Goal:** Reorder tabs to match spec + prepare DB for Сводка tab data.

### Task 2.1: Reorder tabs in `quote_detail_tabs()`
- **New order per ТЗ:**
  1. Сводка (Summary) — visible to all
  2. Продажи (Sales) — visible to all
  3. Закупки (Procurement) — procurement, admin
  4. Таможня (Customs) — customs, admin
  5. Логистика (Logistics) — logistics, admin
  6. Контроль (Control) — quote_controller, admin
  7. Кост-анализ (Cost Analysis) — finance, top_manager, admin
  8. Документы (merge Documents + Document Chain) — visible to all
- **Changes:**
  - Swap Логистика/Таможня order (currently Логистика before Таможня, spec wants Таможня first)
  - Merge "Документы" and "Цепочка документов" into single "Документы" tab
- **Files:** main.py:14760-14900 (tab config), plus any route handling for merged documents tab
- **Test:** All tabs visible in correct order, no broken links

### Task 2.2: Merge Документы + Цепочка документов tabs
- **Current state:** Two separate tabs with separate routes (`/quotes/{id}/documents` and `/quotes/{id}/document-chain`)
- **Target:** Single "Документы" tab that contains both sections
- **Approach:** Keep both content sections but render under one tab, with sub-sections or accordion
- **Files:** main.py (document tab route + document chain route → combine)

### Task 2.3: DB migration — Workflow tracking fields (only 4 new columns needed)

**What already exists in DB:**
| Сводка field | DB column | Status |
|---|---|---|
| Создатель (ФИО) | `quotes.created_by` → JOIN users | EXISTS |
| Таможенный менеджер (ФИО) | `quotes.assigned_customs_user` → JOIN users | EXISTS |
| Логистический менеджер (ФИО) | `quotes.assigned_logistics_user` → JOIN users | EXISTS |
| Дата создания | `quotes.created_at` | EXISTS |
| Дата таможни | `quotes.customs_completed_at` | EXISTS |
| Дата логистики | `quotes.logistics_completed_at` | EXISTS |

**New columns (only 4):**
```sql
ALTER TABLE kvota.quotes
ADD COLUMN IF NOT EXISTS quote_controller_id UUID REFERENCES auth.users(id),
ADD COLUMN IF NOT EXISTS quote_control_completed_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS spec_controller_id UUID REFERENCES auth.users(id),
ADD COLUMN IF NOT EXISTS spec_control_completed_at TIMESTAMPTZ;
```

- **Auto-populate logic:** When workflow transitions happen:
  - Quote control approved → set `quote_controller_id = current_user, quote_control_completed_at = now()`
  - Spec control approved → set `spec_controller_id = current_user, spec_control_completed_at = now()`
  - Names displayed via JOIN to user profiles (ФИО already stored there)

- **Files:** migrations/XXX_add_workflow_tracking.sql, main.py (approval handlers)

**Session 2 estimated effort:** 3-4 hours

---

## Session 3: Сводка Tab Redesign

**Goal:** Build the comprehensive Сводка (Summary) tab per the detailed spec.

### Task 3.1: Сводка tab — LEFT side blocks

**Block I: ОСНОВНАЯ ИНФОРМАЦИЯ (2 columns)**
| Col 1 | Col 2 |
|-------|-------|
| Клиент (fix display) | ИНН Клиента |
| Продавец | ИНН Продавца |
| Контактное лицо | Номер продавца + mobile |

**Block II: ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ (2 columns)**
| Col 1 (People) | Col 2 (Dates) |
|-------|-------|
| Создатель — ФИО | Дата создания |
| Контролер КП — ФИО (auto) | Дата проверки КП (auto) |
| Контролер СП — ФИО (auto) | Дата проверки СП (auto) |
| Таможенный менеджер — ФИО (auto) | Дата таможни (auto) |
| Логистический менеджер — ФИО (auto) | Дата логистики (auto) |

**Block III: ИНФОРМАЦИЯ ДЛЯ ПЕЧАТИ (2 columns)**
| Col 1 | Col 2 |
|-------|-------|
| Дата выставления КП | Срок подготовки КП (calculated: created→issued) |
| Срок действия КП | Срок действия (дней) |
| Дата выставления СП | Дней от подписания СП |

- **Data sources:** quotes table, specifications table, auth.users for FIOs, customer + seller company tables
- **Auto-populated fields:** Controller IDs/dates from DB (set in Session 2 migration)
- **Files:** main.py — rewrite Сводка tab content function

### Task 3.2: Сводка tab — RIGHT side blocks

**Block I: ПОРЯДОК РАСЧЕТОВ (2 columns)**
| Col 1 | Col 2 |
|-------|-------|
| Курс USD/RUB на дату КП | Частичная предоплата |
| Курс USD/RUB на дату СП | Размер аванса |
| Курс USD/RUB на дату УПД | Условия расчетов |

- **Exchange rates:** Auto-fetch from CBR API (https://www.cbr-xml-daily.ru/) based on date
- **Implementation:** New utility function `get_cbr_rate(date, currency)` that caches rates
- **Files:** services/cbr_rates.py (new), main.py (display)

**Block II: ДОСТАВКА (2 columns)**
| Col 1 | Col 2 |
|-------|-------|
| Тип доставки | Страна поставки |
| Базис поставки | Город поставки |
| | Адрес поставки (optional) |

**Block III: ИТОГО (2 columns)**
| Col 1 | Col 2 |
|-------|-------|
| Общая сумма | Количество позиций |
| Общий профит | Маржа % |

### Task 3.3: Embed Product Details + Cost Breakdown (read-only)
- **From /calculate page:** Take the Product Details table and Cost Breakdown and render read-only versions on Сводка
- **Data source:** Same calculation results used by `/quotes/{id}/calculate`
- **Approach:** Extract calculation display logic into reusable function, call from both calculate page and Сводка tab
- **Files:** main.py (refactor calculate display into shared function)

**Session 3 estimated effort:** 4-5 hours (largest session)

---

## Session 4: Продажи Tab Redesign

**Goal:** Restructure the Sales (Продажи) tab layout per spec.

### Task 4.1: Block ОСНОВНАЯ ИНФОРМАЦИЯ
- 2-column layout:
  - Col 1: Продавец, Клиент (searchable), Контактное лицо, Срок действия КП
  - Col 2: Создатель, Дата создания, Дополнительная информация (NEW text field), Действительно до
- **New field:** `additional_info` on quotes table (TEXT, nullable)
- **Migration:** Add column + update POST handler

### Task 4.2: Block ДОСТАВКА
- Align all fields in clean grid:
  - Страна, Город, Адрес поставки (select from customer profile addresses), Способ, Условия
  - Skip "Транзит через Турцию" (marked "надо узнать" — deferred)
- **Customer address selection:** Add dropdown populated from customer's addresses

### Task 4.3: Block ИТОГО
- Add more data, verify data pulling works
- Show: Общая сумма, Общий профит, Количество позиций, Маржа %

### Task 4.4: Buttons reorganization
- Move action buttons ABOVE items table (currently below)
- Layout: "Рассчитать" (left) | "Отправить на контроль" (right)

**Session 4 estimated effort:** 3-4 hours

---

## Session 5: Invoice Display + CBR Integration + Polish

### Task 5.1: Fix invoice display in Закупки tab
- **Current:** Invoice cards are stacked vertically
- **Target:** Display as horizontal blocks in a line (like a card grid)
- **Approach:** CSS flexbox/grid layout for invoice cards, `flex-wrap: wrap` for responsive
- **Files:** main.py (procurement page invoice rendering, around line 15700)

### Task 5.2: CBR API integration for exchange rates
- **Service:** `services/cbr_rates.py`
- **API:** `https://www.cbr-xml-daily.ru/archive/YYYY/MM/DD/daily_json.js`
- **Caching:** Cache rates per date in a simple DB table or in-memory dict
- **Usage:** Called from Сводка tab to display rates at КП/СП/УПД dates
- **Fallback:** If API unavailable, show "—" with tooltip

### Task 5.3: Final UI polish
- Verify all tabs render correctly
- Check responsive behavior
- Verify all data pulls correctly on Сводка

**Session 5 estimated effort:** 3-4 hours

---

## Summary: Priority Order

| # | Session | What | Impact |
|---|---------|------|--------|
| 1 | Bugs + Quick Wins | Fix invoice bug, download buttons, logistics display | Unblocks daily user work |
| 2 | Tab Restructure + DB | Reorder tabs, merge docs, add tracking fields | Foundation for everything else |
| 3 | Сводка Tab | Build full Summary tab with all 6 blocks + calc data | Most requested new feature |
| 4 | Продажи Redesign | Restructure sales tab layout + new fields | Better UX for sales team |
| 5 | Invoice Display + CBR + Polish | Horizontal invoices, exchange rates, final polish | Completeness |

---

## Items Explicitly Deferred

1. **"Транзит через Турцию или напрямую"** — marked "надо узнать" in ТЗ, skipped until clarified
2. **"Выгрузить данные" button on ERPS** — ТЗ says "потом сделаем функционал выгрузки за период" (will do export later)
3. **Dashboard overview blocks** (Мои запросы, Мои СП, Мои КП with filters) — from 11.02 section, assumed resolved or separate effort
4. **Page 9 forms/modals** — Additional error screenshots that were hard to parse from PDF; the main one (quote_items.name) is covered in Session 1

---

## Risk / Dependencies

- **Session 3 depends on Session 2** (need DB fields for auto-populated managers/dates)
- **CBR API may have rate limits** — need to implement caching
- **main.py monolith risk** — Sessions 3 and 4 heavily modify the same file, should run sequentially
- **"Размер аванса" and "Условия расчетов"** — reported as "не отобразилось" (not displayed). Need to verify if data exists in DB but isn't rendered, or if fields are empty
