BROWSER TEST
timestamp: 2026-02-11T00:30:00+03:00
session: 2026-02-10 #1
base_url: https://kvotaflow.ru

TASK: [C1+C2+C3] Plan-fact payments table improvements
URL: /finance/{deal_id} (e.g., DEAL-2026-0002)

TEST 1: Empty state + Date + Currency columns on payments table
STEPS:
1. Navigate to /finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742 (DEAL-2026-0002)
2. Find the ПЛАН-ФАКТ ПЛАТЕЖЕЙ section
3. If no payment rows: verify empty state message like "Нет записей" or "Пока нет платежей" (not just an empty table)
4. If payment rows exist: verify table has "Дата" column header
5. Verify table has "Валюта" column header
6. Verify Russian labels (not English) in section headers like "Итого", "Действия"
7. Check that icons use Lucide (SVG icons) not emoji characters
8. Check console for errors
EXPECT:
- Empty state message when no payments
- "Дата" and "Валюта" columns present
- Russian labels throughout
- No emoji characters, Lucide icons instead

---

TASK: [C6] Procurement dashboard error handling
URL: /dashboard (logged in as any user)

TEST 2: Procurement dashboard doesn't crash
STEPS:
1. Navigate to /dashboard
2. If procurement section visible, verify it shows content or a friendly error message (not a 500/crash)
3. Check console for errors
EXPECT:
- No crash even if procurement data fails to load
- Friendly error card if data unavailable

---

TASK: [C7] Admin users table shows FIO
URL: /admin

TEST 3: Users table shows names not UUIDs
STEPS:
1. Navigate to /admin
2. Look at the users table (Пользователи tab)
3. Check the ФИО column — should show full names (e.g., "Иван Петров"), not truncated UUIDs (e.g., "a1b2c3d4...")
4. Check console for errors
EXPECT:
- Full names displayed in ФИО column
- UUID shown only as fallback if no profile exists

---

TASK: [M3/M5/M9/M11/M12] Table-enhanced styling
URL: multiple pages

TEST 4: Tables have consistent enhanced styling
STEPS:
1. Navigate to /dashboard — check "Последние КП" table has styled header (gradient or colored)
2. Navigate to /finance → Платежи → Календарь tab — check calendar table has styled header
3. Navigate to /dashboard as sales role — check quotes and specs tables have styled headers
4. On each table, verify:
   - Table wrapped in container div
   - Header row has gradient/colored background (not plain white)
   - Consistent look across all tables
5. Check console for errors
EXPECT:
- All list tables have table-enhanced styling
- Gradient/colored headers
- Consistent visual style

---

TASK: [M6] Country names instead of ISO codes
URL: /suppliers, /customs/{quote_id}

TEST 5: Country names in Russian
STEPS:
1. Navigate to /suppliers
2. Check the filter dropdown — should show "Китай", "Турция", "Германия" not "CN", "TR", "DE"
3. Check the suppliers table location column — should show country names
4. Navigate to /customs/ba4a486f-d2cb-4356-8832-db9db3c54246 (Q-202602-0073)
5. Check the "Страна закупки" column — should show country names not ISO codes
6. Check console for errors
EXPECT:
- Country names in Russian everywhere
- No raw ISO codes like "CN", "RU", "TR" in user-facing UI

---

TASK: [M7] Customer contact name deduplication
URL: /customers/{id}

TEST 6: Contact names not duplicated
STEPS:
1. Navigate to /customers and open any customer with contacts
2. Check contact names — should NOT show duplicated parts like "Мамут Мамут Рахал Иванович Иванович"
3. Names should appear clean: "Мамут Рахал Иванович"
4. Check console for errors
EXPECT:
- Clean contact names without word duplication

---

TASK: [MISC] Date format + profit colors + status badges
URL: multiple pages

TEST 7: Dates in DD.MM.YYYY format
STEPS:
1. Navigate to /quotes — check date column uses DD.MM.YYYY (e.g., "10.02.2026" not "2026-02-10")
2. Navigate to /finance → ERPS — check dates in DD.MM.YYYY
3. Navigate to /customers/{id} — check creation dates in DD.MM.YYYY
4. Check console for errors
EXPECT:
- All dates in Russian format DD.MM.YYYY
- No ISO format YYYY-MM-DD in user-facing tables

TEST 8: Profit shows color coding
STEPS:
1. Navigate to /finance → ERPS tab
2. Check profit column — positive profits should be green, zero/negative should be gray/red
3. Zero amounts should show "---" not "$0.00"
4. Check console for errors
EXPECT:
- Green for positive profit
- Gray/red for zero/negative
- Dash for zero amounts

REPORT_TO: .claude/test-ui-reports/report-20260211-0030-design.md
