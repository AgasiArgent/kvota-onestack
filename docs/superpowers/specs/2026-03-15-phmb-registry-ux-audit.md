# PHMB Registry `/phmb` -- UX Audit

**Date:** 2026-03-15
**Target URL:** `/phmb` (new page, does not exist yet in FastHTML)
**Screenshots:** `audit-phmb-01-quotes-registry.png`, `audit-phmb-02-quote-creation-form.png`, `audit-phmb-03-procurement-queue.png`, `audit-phmb-04-phmb-tab.png`

---

## Existing Patterns Observed

### Quotes Registry (`/quotes`)
- **Header:** Title + count badge + primary CTA "Novoe KP"
- **Status summary bar:** Horizontal pill cards showing count + total per status (Chernovik 7, Zakupki 15, etc.)
- **Filters:** 3 dropdowns in a row (status, customer, manager)
- **Table columns:** Data | IDN | Client | Manager | Status | Versions | Summa | Profit
- **Footer:** "Vsego: 39 KP"
- **No pagination** -- all records shown (39 total)

### Quote Creation Form (`/quotes/new`)
- **Full page** with 2 card sections: "Client i kontakt" and "Dostavka"
- **Client field:** Typeahead combobox (required) + "Create new client" button
- **Our entity:** Dropdown (optional)
- **Delivery:** Country, City, Delivery method
- **CTA:** "Sozdat KP" (disabled until client selected) + "Otmena" link

### PHMB Tab (on quote detail)
- **Settings bar:** Avans %, Nacenka %, Marzha %, Payment days, CNY/USD rate + Save button
- **Search:** Text input for article/name search
- **Add manually:** Accordion expand
- **Items table:** Artikul | Name | Brand | Qty | Price RMB | Discount | Total USD | Delete
- **Footer:** Subtotals (bez NDS / s NDS) + "Rasschitat PHMB" button

### PHMB Procurement Queue (`/phmb/procurement`)
- **Header:** Title + count badge
- **Filters:** Status buttons (Vse | Novye | Zaprosheno | S cenoj)
- **Table columns:** KP | Brand | Artikul | Name | Qty | Status | Actions
- Only 1 item visible -- very sparse page

---

## UX Proposal: `/phmb` Registry

### What the user does here
1. **See all PHMB quotes** they manage (primary: 90% of visits)
2. **Check status** of pending quotes (how many items priced, how many waiting)
3. **Create new PHMB quote** (secondary action)
4. **Navigate to a quote** to work on it

### Registry Layout

**Header row:**
- Title: "PHMB -- Коммерческие предложения" + count badge
- Primary CTA: "Создать КП" button (opens dialog, not full page)

**No status summary bar.** Unlike /quotes with 9 lifecycle statuses, PHMB quotes only have 3 meaningful states: draft (items being added), partially priced (waiting for procurement), ready (all priced). A summary bar would add visual noise for low informational value. Instead, show status as a badge in each row.

**Filters (single row):**
- Text search (IDN or client name) -- most important, leftmost
- Status dropdown: Все | Черновик | Ожидает цен | Готов к расчёту
- Date range (optional, collapsed by default)

**Table columns (6):**

| Column | Source | Notes |
|--------|--------|-------|
| Дата | `quotes.created_at` | DD.MM.YYYY |
| IDN | `quotes.idn` | Link to `/phmb/[id]` |
| Клиент | `quotes.customer_id` -> name | Link to customer |
| Позиции | count of `phmb_quote_items` | e.g. "7 / 10" (priced / total) |
| Сумма | `quotes.total_amount` or calculated | Show currency symbol |
| Статус | derived from items | Badge: Черновик / Ожидает цен / Готов |

**Footer:** "Всего: N КП"

**Rationale for fewer columns than /quotes:**
- No "Manager" -- PHMB quotes are personal, manager = current user (filtered by default)
- No "Versions" -- version management happens inside the quote workspace
- No "Profit" -- profit margin is set per-quote in settings, not a list-level metric
- Added "Позиции (7/10)" -- unique to PHMB, shows procurement progress at a glance

### Create Dialog (not full page)

PHMB quote creation is simpler than standard quotes (no delivery info needed). A dialog is sufficient.

**Dialog: "Новый PHMB КП"**

Fields (3):
1. **Клиент** (required) -- Typeahead combobox, same component as /quotes/new
2. **Валюта КП** -- Dropdown: USD (default) | EUR | RUB
3. **Наше юрлицо** -- Dropdown (optional, same list as /quotes/new)

Defaults pre-filled from `phmb_settings`: markup %, advance %, payment days.

**CTA:** "Создать" (primary) + "Отмена" (ghost)
**On success:** Redirect to `/phmb/[new-id]`

**Why dialog, not full page:**
- Only 2-3 fields needed (vs 5+ on standard quote form)
- No delivery section (PHMB items ship from China, logistics handled separately)
- Faster workflow: click -> fill client -> create -> start adding items

### Sidebar Navigation

Current sidebar has "Очередь PHMB" under Реестры. Proposal:

Replace with:
- **PHMB** -> `/phmb` (registry -- new)
- Keep "Очередь PHMB" as a sub-item or move to `/phmb/procurement`

For sales role: show "PHMB" link.
For procurement role: show "Очередь PHMB" link (direct to procurement queue).
For admin: show both.

### Empty State

When no PHMB quotes exist:
- Centered illustration-free layout (per design system: no decorative images in task flows)
- Text: "Нет коммерческих предложений PHMB"
- Subtext: "Создайте первое КП для работы с прайс-листами"
- CTA: "Создать КП" button (same as header CTA, opens dialog)

### Row Interaction
- Entire row clickable -> navigates to `/phmb/[id]`
- Row hover: subtle warm tint (`hover:bg-[rgba(87,83,78,0.04)]` per design system)
- No inline actions column needed (all work happens inside the quote workspace)

---

## UX Issues Found in Current FastHTML

1. **Procurement queue shows "---" for KP link** -- the IDN cell shows a dash instead of the quote IDN
2. **No registry page** -- users must navigate from /quotes and filter mentally for PHMB quotes
3. **PHMB tab buried** -- 10 tabs on quote detail, PHMB is 3rd; in standalone flow it becomes the primary workspace
4. **"Rasschitat PHMB" manual button** -- should be auto-calc (per plan spec)
5. **Status column in procurement queue shows price, not status** -- confusing semantics
