# PHMB Workspace (`/phmb/[id]`) — UX Audit

**Date:** 2026-03-15
**Auditor:** Pre-migration UX analysis
**Source:** Live FastHTML at kvotaflow.ru, quote Q-202603-0013

## Current State Summary

The PHMB tab lives inside the master quote detail page as one of 10 tabs (Сводка, Продажи, **PHMB**, Закупки, Таможня, Логистика, Контроль, Кост-анализ, Документы, Чат). It appears only on quotes where PHMB mode is enabled via user profile toggle.

### What exists today (PHMB tab)

1. **Settings bar** (top): Аванс %, Наценка %, Маржа %, Срок оплаты (к.д.), Курс CNY/USD (read-only from CB). Full-width "Сохранить" button below.
2. **Search bar**: "Поиск по артикулу или названию..." — searches `phmb_price_list` (76,868 items).
3. **Manual add**: "Добавить позицию вручную" accordion.
4. **Items table** (HTML table, not Handsontable): Артикул, Наименование, Бренд, Кол-во (editable spinner), Цена RMB, Скидка, Итого USD, delete button.
5. **Footer**: Итого без НДС + Итого с НДС (left), "Рассчитать PHMB" button (right).

### Pain points in current UI

- **Settings bar wastes vertical space.** 5 inputs + save button take a full horizontal row at the top, always visible, pushing the table down. Settings are changed rarely (once per quote), items are edited constantly.
- **"Рассчитать" button is manual.** User must remember to click after every change. Easy to forget, leading to stale totals.
- **No status indicator for items without price.** The third row (TEST-001) shows "---" for Скидка and Итого, but there is no visual distinction (color, icon, badge) marking it as "waiting for procurement."
- **HTML table, not spreadsheet.** No copy-paste, no cell navigation, no multi-row select. Only the Кол-во field is editable inline. Everything else requires the search/add workflow.
- **No versioning UI.** No way to create/switch versions from the PHMB tab.
- **No PDF export button.** Must navigate to a different tab.
- **No partial quote indicator.** User cannot see "3 of 5 items priced" at a glance.
- **Tab context is confusing.** PHMB tab coexists with Продажи, Закупки, etc. that belong to the master flow. Users may not know which tabs are relevant for PHMB quotes.

---

## Proposed Layout for `/phmb/[id]`

### A. Page Layout (top to bottom)

```
+------------------------------------------------------------------+
| HEADER: Q-202603-0013 | Test Client | Черновик | v1 [v2] [+]     |
|        3/5 items priced | Итого: $6,588                    [PDF] |
+------------------------------------------------------------------+
| SEARCH BAR: [Search by article/name...]        [+ Add manually]  |
+------------------------------------------------------------------+
|                                                                   |
|  HANDSONTABLE (full width, ~60-70% of viewport height)            |
|  Columns: #, Article, Name, Brand, Qty, Price RMB, Discount,     |
|           EXW USD, COGS, Fin.cost, Sale Price, Total w/VAT,       |
|           Status                                                  |
|                                                                   |
+------------------------------------------------------------------+
| FOOTER BAR: Итого без НДС: $X | Итого с НДС: $Y | Профит: $Z    |
+------------------------------------------------------------------+
| PAYMENT TERMS (collapsible panel, collapsed by default):          |
| Аванс % | Наценка % | Маржа % | Срок оплаты | Курс CNY/USD      |
+------------------------------------------------------------------+
```

**Key decisions:**
- **Header** holds quote identity + version switcher + PDF button. Always visible.
- **Search bar** directly above the table. Results appear as a dropdown overlay (like VS Code command palette). Click adds row to table.
- **Handsontable** takes maximum vertical space. This is where users spend 90% of their time.
- **Payment terms** collapse into a panel below the table. Users set these once, not per-item. Expanding them triggers recalculation of all items automatically (no save button needed).
- **No sidebar.** Full width for the spreadsheet. Sidebar wastes horizontal space that Handsontable needs.

### B. Handsontable Columns

| # | Column | Source | Editable | Notes |
|---|--------|--------|----------|-------|
| 1 | Row # | Auto | No | Sequential |
| 2 | Артикул | price_list / manual | No | From search or manual entry |
| 3 | Наименование | price_list / manual | No | Truncated, full on hover |
| 4 | Бренд | price_list / manual | No | |
| 5 | Кол-во | User | Yes | Spinner or direct input |
| 6 | Цена (RMB) | price_list or procurement | No* | Green = from DB, orange = from procurement, red placeholder = waiting |
| 7 | Скидка % | brand_type_discounts | No | Auto-applied from settings |
| 8 | Итого USD | Calculated | No | (Price - Discount) / CNY rate |
| 9 | Цена продажи | Calculated | No | After overhead + markup |
| 10 | Итого с НДС | Calculated | No | Sale price * qty * 1.2 |
| 11 | Статус | System | No | Icon: checkmark (priced) / clock (waiting) |

*Procurement-filled price becomes editable only by procurement role.

### C. Interaction Patterns

**Search and add:**
- User types in search bar -> debounced query (300ms) against `phmb_price_list`
- Results dropdown shows: Article | Name | Brand | Price RMB | Discount %
- Click result -> row added to Handsontable with qty=1, auto-calculated if price exists
- If no price in DB -> row added with status "waiting", item goes to procurement queue
- Search stays focused after adding (for rapid multi-item entry)

**Waiting for procurement:**
- Rows without price: light orange background, clock icon in Status column
- Header shows "3/5 items priced" counter with progress bar
- When procurement sets price (via `/phmb/procurement`), row auto-updates on next page load (or via polling/realtime subscription)

**Versioning:**
- Header shows version pills: `v1` `v2` `[+]`
- Click `[+]` -> dialog: "Create version with current items and new terms?" -> copies current state
- Click version pill -> switches view to that version's calculated prices
- Active version highlighted with accent color

**PDF export:**
- Button in header, always visible
- If partial quote: "Export 3 priced items" vs "Export all (2 items waiting)" choice in dropdown
- Generates via Python API endpoint

**Payment terms panel:**
- Collapsed by default (chevron toggle, like an accordion)
- When expanded: inline editable fields (Аванс %, Наценка %, Маржа %, Срок оплаты)
- Changes trigger immediate recalculation of all table rows (debounced 500ms)
- No save button — auto-persisted on change (optimistic UI)
- Курс CNY/USD shown as read-only (from Central Bank API)

### D. What Makes This 10x Better

1. **Auto-calc eliminates "Рассчитать" button.** Prices update instantly when terms change or items are added. No stale data.
2. **Handsontable replaces HTML table.** Copy-paste from Excel, keyboard navigation, multi-select delete. Users explicitly requested this.
3. **Standalone page removes tab confusion.** No more 10-tab bar mixing PHMB with master flow concepts (Таможня, Логистика) that don't apply.
4. **Visual status for waiting items.** Orange rows + progress counter replace invisible "---" dashes.
5. **Collapsed payment terms free vertical space.** Settings bar currently takes ~120px of prime screen real estate for rarely-changed values.
6. **Version pills in header** make version management discoverable vs. nonexistent today.
7. **PDF button always visible** in header vs. hidden on another tab.
