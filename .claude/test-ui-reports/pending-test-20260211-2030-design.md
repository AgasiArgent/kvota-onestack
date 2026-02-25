BROWSER TEST
timestamp: 2026-02-11T20:30:00
session: 2026-02-11 #2
base_url: https://kvotaflow.ru

LOGIN: Use admin account (Test123!) or existing session

TASK: [D1] Quotes list page redesign
URL: https://kvotaflow.ru/quotes
STEPS:
1. Navigate to /quotes
2. Check for 9 summary stage cards at top (Черновик, Закупки, Логистика, Таможня, Контроль, Проверка, Клиент, Сделка, Закрыт)
3. Each card should show count + sum
4. Check table columns: Дата, IDN, Клиент, Статус, Версии, Сумма, Профит, Кнопки
5. Click on IDN link — should navigate to quote detail page
6. Click on client name — should navigate to customer detail page
7. Verify rows are compact (narrow height)
8. Check console for errors
EXPECT: Stage cards with accurate counts, clean compact table, clickable links work

TASK: [D2/D3] Quote detail card layout + IDN header
URL: https://kvotaflow.ru/quotes/{pick_any_quote_id}
STEPS:
1. Navigate to any quote detail page
2. Verify persistent header at top: IDN number + status badge + client name
3. Check Продажи tab has 4 info cards: Основная информация, Доставка, Дополнительная информация, Информация для печати
4. Cards should have white background, rounded corners, clean layout
5. Click through ALL tabs: Закупки, Логистика, Таможня, Контроль, Кост-анализ, Документы, Цепочка
6. On EACH tab — verify the IDN+Client header is visible
7. Check action buttons are split into 2 groups (primary left, export right)
8. Try inline editing on Продажи tab (click a dropdown like customer) — verify it still works
9. Check console for errors
EXPECT: Header persistent on all tabs, 4 clean info cards on Продажи, inline editing works

TASK: [D7] ERPS -> Контроль платежей
URL: https://kvotaflow.ru/finance?tab=erps
STEPS:
1. Navigate to /finance?tab=erps (or look for "Контроль платежей" tab name)
2. Verify tab is renamed from "ERPS" to "Контроль платежей"
3. Check sidebar also says "Контроль платежей" instead of "ERPS"
4. Click on any row — should redirect to deal detail page (plan-fact tab)
5. Look for "+" add payment button on rows that have a deal
6. Click "+" button — modal should open with payment form
7. Check modal has fields: amount, currency, date, category, description
8. Close modal without submitting
9. Check if "days until next payment" column shows values
10. Check console for errors
EXPECT: Tab renamed, rows clickable to deal detail, payment modal works, days counter displays

TASK: [D9] Dashboard overview blocks (sales manager)
URL: https://kvotaflow.ru/dashboard?tab=overview
STEPS:
1. Login as a sales user (or admin who also has sales role)
2. Navigate to /dashboard?tab=overview
3. Look for "Мои показатели" section with 3 blocks:
   - Мои запросы (в работе) — count + sum
   - Мои СП — count + sum
   - Мои КП — count + sum
4. Check date range filter (from/to) is present
5. Change date range — blocks should update via HTMX
6. Click "Посмотреть все" on each block — should navigate to filtered pages
7. Check console for errors
EXPECT: 3 summary blocks visible for sales users, date filter works, links navigate correctly

REPORT_TO: .claude/test-ui-reports/report-20260211-2030-design.md
