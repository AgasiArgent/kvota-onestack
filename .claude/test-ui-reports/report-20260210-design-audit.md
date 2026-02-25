# Design Consistency Audit Report

**Timestamp:** 2026-02-10T22:30:00+03:00 (updated 2026-02-11T01:40:00+03:00)
**Session:** 2026-02-10 #1
**Base URL:** https://kvotaflow.ru
**Reference:** DESIGN_GUIDELINES.md
**Pages audited:** 30 pages/views (comprehensive)

---

## Summary

| Category | Issues Found |
|----------|-------------|
| CRITICAL (breaks design system / bugs) | 7 |
| MEDIUM (inconsistency) | 13 |
| LOW (minor polish) | 7 |
| **Total** | **27** |

---

## CRITICAL Issues

### C1. English text on quote detail page (Totals/Actions section)
**Pages:** `/quotes/{id}` (all quotes)
**Guideline violated:** Consistency (all UI should be in Russian)

The bottom section of the quote detail page is entirely in English:
- "Totals" heading (should be "Итого")
- "Products Subtotal:" (should be "Товары (подитог):")
- "Logistics:" (should be "Логистика:")
- "Total:" (should be "Итого:")
- "Actions" heading (should be "Действия")
- "Calculate" button (should be "Рассчитать")
- "Version History" button (should be "История версий")
- "Export" heading (should be "Экспорт")
- "Specification PDF", "Invoice PDF", "Validation Excel" (should be Russian)

This is a significant user-facing issue. All other pages are consistently in Russian.

### C2. Emoji usage instead of Lucide icons
**Pages:** `/customers/{id}` (customer detail), `/logistics/{id}` (logistics workspace)
**Guideline violated:** Don't #1 — "Don't use emoji, always use Lucide icons"

- Contact card: pencil emoji for "Подписант" badge instead of Lucide `pen-line` or `file-signature` icon
- Logistics page: 🚛 emoji for delivery method "Авто" instead of Lucide `truck` icon
- The rest of these pages correctly uses Lucide icons

### C3. Payments tab — table is not `table-enhanced`
**Pages:** `/finance?tab=payments`
**Guideline violated:** Don't #6 — "Don't use plain `<table>`, wrap with table-enhanced classes"

The payments table lacks the `table-enhanced` styling:
- No gradient header row
- No zebra-striped rows
- No hover effects
- Plain white background
- Compare with the deals table and dashboard tables which correctly use styled headers

### C4. Summary footer on payments tab — not a card
**Pages:** `/finance?tab=payments`
**Guideline violated:** Cards should use `card-elevated`

The summary footer ("Poступления (план): 1,000..., Баланс: 1,000") is rendered as plain text in a row. Should be wrapped in a `card-elevated` with structured layout, similar to how summary cards appear on deals page and spec control.

### C5. Approvals page — no page header card
**Pages:** `/approvals`
**Guideline violated:** Page headers should use gradient header card pattern

The page title "Согласования" lacks the standard page header card pattern (gradient background, icon, subtitle) that is correctly used on:
- /finance ("Финансы" + "Сделки, ERPS и календарь платежей")
- /deals ("Сделки" + "Активные сделки и план-факт анализ")
- /suppliers ("Поставщики" with header card)
- /customers ("Клиенты" with header card)

The approvals page just has a bare H1 + subtitle paragraph without the card wrapper.

### C6. Dashboard procurement tab — 500 Internal Server Error
**Pages:** `/dashboard?tab=procurement`
**Issue:** Page returns HTTP 500 Internal Server Error — completely broken. All other dashboard tabs (overview, sales, logistics, customs, quote-control, spec-control, finance) work correctly.

This is a **BUG**, not just a design issue.

### C7. Admin page — ФИО column shows truncated UUIDs instead of user names
**Pages:** `/admin`
**Issue:** The "ФИО" (full name) column displays truncated UUIDs like "138311f7...", "e13fc18d..." instead of actual user names. This makes the admin page unusable for user management.

This is a **data rendering bug**, not just a design issue.

---

## MEDIUM Issues

### M1. Customers list — stats cards show "0" for all metrics
**Pages:** `/customers`
**Issue:** Stats cards show "0 Всего, 0 Активных, 0 С контактами, 0 С подписантом" but there are clearly 11 customers visible. This appears to be a data bug, not a design issue per se, but it makes the stats cards look broken/untrustworthy.

### M2. Suppliers — filter section is too spacious
**Pages:** `/suppliers`
**Guideline violated:** Don't #4 — "Don't create spacious layouts, keep things compact"

The search, country filter, and status filter are stacked vertically with each taking a full row. Should be a compact horizontal filter bar (like the payments tab filters or the customers search bar).

### M3. Deals — inconsistent currency display in summary cards vs table
**Pages:** `/deals`
**Issue:** Summary cards show "824,372 P" (rubles) but table shows "581,839.50 USD", "28,629.02 USD" etc. The summary is converting to RUB while the table shows native currency. Should either all be in one currency or clearly labeled.

### M4. Quote detail — "Спецификация" status badge uses different style
**Pages:** `/quotes/{id}`
**Issue:** The status badge next to "КП Q-202602-0073" shows "Спецификация" in a blue-bordered pill that doesn't match the `status-badge-v2` pattern. Compare with deals page "В работе" badges which correctly use the status-badge-v2 green variant.

### M5. Dashboard overview — section tables not using `table-enhanced`
**Pages:** `/dashboard?tab=overview`
**Guideline violated:** Don't #6

Multiple tables on the dashboard overview use plain styling:
- "Ожидают согласования" table
- "Логистика: ожидают данных" table
- "Финансы: активные сделки" table
- "Продажи: ожидают вашего решения" table
- "Последние КП" table

None use the `table-enhanced` class with gradient headers. The "Последние КП" table does have styled blue headers but the other tables have plain gray headers — inconsistent within the same page.

### M6. Spec control — "---" separator rows in table
**Pages:** `/dashboard?tab=spec-control`
**Issue:** The spec control table uses raw text "--- Ожидают спецификации ---", "--- Черновики ---", "--- Подписаны ---" as group separator rows. These look like raw/unformatted data rather than styled group headers. Should use background-colored rows or proper group header styling.

### M7. Customer detail — "Контакты" card shows duplicated name
**Pages:** `/customers/{id}`
**Issue:** Contact displays as "Мамут Рахал Мамут Иванович Иванович" — the name appears duplicated/garbled. This is a data rendering bug visible in the UI.

### M8. Document chain — page header missing `card-elevated` wrapper
**Pages:** `/quotes/{id}/document-chain`
**Issue:** The page title "Цепочка документов КП Q-202602-0074" and subtitle are rendered without the standard page header card (gradient background, shadow). Other quote sub-pages use the tab bar above + header card pattern.

### M9. Payments calendar — table not `table-enhanced`, redundant heading
**Pages:** `/payments/calendar`
**Guideline violated:** Don't #6

- Table uses plain headers (no gradient, no zebra stripes)
- "Календарь платежей" heading appears both in page header card AND inside the content card (redundant)
- Dark scrollbar-like element visible at bottom of table area

### M10. Settings page — missing standard page header card
**Pages:** `/settings`
**Guideline violated:** Page headers should use gradient header card pattern

"Настройки организации" heading is rendered as plain H1 text without the standard page header card (icon + gradient background + subtitle) used on /finance, /deals, /suppliers, /customers, etc.

### M11. Dashboard sales tab — tables not `table-enhanced`
**Pages:** `/dashboard?tab=sales`
**Guideline violated:** Don't #6

"Активные спецификации" and "Активные КП" tables use blue text headers instead of the `table-enhanced` gradient header pattern. Inconsistent with the logistics/customs dashboard tabs which use proper styled headers.

### M12. Tasks page — section tables not `table-enhanced`
**Pages:** `/tasks`
**Guideline violated:** Don't #6

All 5 section tables (Согласования, Логистика, Спецификации, Финансы, Продажи) use plain gray headers. Same issue as dashboard overview (M5). Should use consistent `table-enhanced` styling.

### M13. Customs Handsontable — raw country codes
**Pages:** `/customs/{id}`
**Guideline violated:** Don't #5 — "Don't show raw database values"

"Страна закупки" column shows raw codes "CN" instead of "Китай". Same pattern as suppliers issue (L4/L5).

---

## LOW Issues

### L1. Quotes list — ПРОФИТ column shows red "P0"
**Pages:** `/quotes`
**Issue:** The profit column shows "P0" in red text for drafts with zero profit. Red color implies error/loss. Zero profit drafts should show "—" or gray "0" instead.

### L2. Customer detail — tab styling differs from quote detail tabs
**Pages:** `/customers/{id}` vs `/quotes/{id}`
**Issue:** Customer tabs use a flat underline style, while quote detail uses a colored button-style active tab. Both work but are visually inconsistent across the app.

### L3. Deals page — "Финансовый менеджер" section heading
**Pages:** `/deals`, `/finance?tab=workspace`
**Issue:** The heading "Финансовый менеджер" above the stats cards seems out of place. This heading implies it's the current user's role, but it doesn't add useful context. Other pages (spec control, customers) don't have a role heading above their stats.

### L4. Suppliers — "Все страны" dropdown shows raw country codes
**Pages:** `/suppliers`
**Guideline violated:** Don't #5 — "Don't show raw database values"

Country filter shows raw codes: "CN", "DE", "IT", "TR" plus one mixed "Germany". Should be "Китай", "Германия", "Италия", "Турция" (or consistent full English names).

### L5. Suppliers table — location shows "Germany, —" pattern
**Pages:** `/suppliers`
**Issue:** Location cells show "Germany, —", "DE, —", "CN, —" — mixing raw country codes with dashes. Should show proper country names and hide the dash when city is empty.

### L6. Date format inconsistency — ISO vs DD.MM.YYYY
**Pages:** `/finance?tab=payments`, `/finance?tab=workspace`, `/finance/{deal_id}`, `/dashboard?tab=logistics`, `/dashboard?tab=customs`, `/admin`
**Issue:** Many pages show dates in ISO "2026-02-10" format while some pages (e.g., customer detail) use DD.MM.YYYY format ("10.02.2026"). Should be consistent across the app — the Russian locale format DD.MM.YYYY is used on some pages but not others.

### L7. Admin page — dates in ISO format
**Pages:** `/admin`
**Issue:** "Дата создания" column shows "2025-10-17" in ISO format. Should use DD.MM.YYYY consistent with Russian locale.

---

## Pages With Good Design Compliance

These pages follow the design guidelines well:

| Page | Compliance | Notes |
|------|-----------|-------|
| `/deals` | Good | Page header card, stats cards, `table-enhanced`, status badges |
| `/customers` | Good | Header card, stats cards, search bar, table styling |
| `/customers/{id}` | Good | Tab layout, 3-column grid, card-elevated sections, inline editing |
| `/dashboard?tab=spec-control` | Good | Stats cards, search, filter pills, table with columns |
| `/quotes/{id}/document-chain` | Good | Clean card-based document sections, proper Lucide icons per type |
| `/finance?tab=erps` | Good | Complex Handsontable with view toggles, proper styling |
| `/companies` | Good | Header card, tabs, info banner, table with action icons |
| `/companies?tab=buyer_companies` | Good | Consistent with seller tab |
| `/procurement/{id}` | Good | Progress stepper, invoice cards, Handsontable |
| `/customs/{id}` | Good | Progress stepper, stats cards, Handsontable, expense sections |
| `/quote-control/{id}` | Good | Summary card, checklist, calculation table, invoice verification |
| `/dashboard?tab=logistics` | Good | Header, stats cards, filter, styled tables |
| `/dashboard?tab=customs` | Good | Same pattern as logistics — consistent |
| `/dashboard?tab=quote-control` | Good | Stats cards, filter, table styling |
| `/finance/{deal_id}` | Good | Two-column layout, plan-fact summary, payment tables |
| `/tasks` | Good | Header with role badges, organized sections (tables need styling though) |

---

## Priority Fix Recommendations

### Urgent (bugs, broken pages)
1. **C6** — Fix 500 error on `/dashboard?tab=procurement`
2. **C7** — Fix admin ФИО column showing UUIDs instead of names
3. **M1** — Fix customer stats cards showing 0
4. **M7** — Fix duplicated contact name rendering

### High Priority (user-facing, breaks UX)
5. **C1** — Translate English text on quote detail page to Russian
6. **C3** — Apply `table-enhanced` to payments table
7. **C2** — Replace emoji with Lucide icons (customer contact + logistics delivery method)

### Medium Priority (design consistency)
8. **C5** — Add page header card to approvals page
9. **M10** — Add page header card to settings page
10. **M5/M11/M12** — Apply `table-enhanced` to dashboard overview, sales, and tasks tables
11. **M6** — Style spec control group separator rows
12. **M9** — Fix payments calendar table + remove redundant heading
13. **L4/L5/M13** — Show proper country names everywhere (suppliers, customs)

### Low Priority (polish)
14. **C4** — Wrap payments summary footer in card-elevated
15. **M2** — Make suppliers filter bar horizontal/compact
16. **M8** — Add header card to document chain page
17. **L1** — Show "—" instead of red "P0" for zero-profit drafts
18. **L6/L7** — Standardize date format to DD.MM.YYYY across all pages
19. **M3** — Clarify currency in deals summary cards vs table
20. **L3** — Remove "Финансовый менеджер" role heading

---

## Console Errors
- `/dashboard?tab=procurement` — HTTP 500 (Internal Server Error)
- All other 29 pages — 0 JS errors, only tailwindcss CDN warnings (non-critical)

---

## Methodology
- **Pass 1 (14 pages):** /finance?tab=payments (flat + grouped), /quotes, /quotes/{id}/document-chain, /quotes/{id} detail, /dashboard?tab=spec-control, /customers, /customers/{id}, /deals, /suppliers, /approvals, /dashboard?tab=overview, /quotes/new
- **Pass 2 (16 pages):** /admin, /companies (both tabs), /finance?tab=workspace, /finance/{deal_id}, /payments/calendar, /tasks, /settings, /procurement/{id}, /logistics/{id}, /customs/{id}, /quote-control/{id}, /dashboard?tab=sales, /dashboard?tab=procurement, /dashboard?tab=logistics, /dashboard?tab=customs, /dashboard?tab=quote-control, /dashboard?tab=finance
- Compared each against DESIGN_GUIDELINES.md rules
- Checked: card styling, table classes, typography, icons vs emoji, color palette, layout density, Russian language consistency, status badge usage, raw DB values
- Screenshots saved as audit-01 through audit-29
