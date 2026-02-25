BROWSER TEST
timestamp: 2026-02-15T10:30:00Z
session: 2026-02-14 #3
base_url: https://kvotaflow.ru

TASK: [86afdkux7] Сводка tab 6-block layout redesign
URL: /quotes/74aa8aba-09ec-4e78-8f89-216e633d6210 (Q-202601-0013, has data)
STEPS:
1. Login as admin (admin@test.kvota.ru / Test123!)
2. Navigate to /quotes/74aa8aba-09ec-4e78-8f89-216e633d6210
3. Verify "Сводка" tab is active by default
4. Check 6-block layout — 3 rows of 2 cards each:
   - Row 1 LEFT: "ОСНОВНАЯ ИНФОРМАЦИЯ" (customer name, INN, seller, seller INN, contact, phone)
   - Row 1 RIGHT: "ПОРЯДОК РАСЧЕТОВ" (payment terms, advance, currency, 3 exchange rate "—" placeholders)
   - Row 2 LEFT: "ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ" (Создатель, Контролер КП, Контролер СП, Таможенный менеджер, Логистический менеджер + dates)
   - Row 2 RIGHT: "ДОСТАВКА" (delivery method, country, city, terms)
   - Row 3 LEFT: "ИНФОРМАЦИЯ ДЛЯ ПЕЧАТИ" (KP issue date, validity)
   - Row 3 RIGHT: "ИТОГО" (total amount, profit, item count, margin %)
5. Verify NO "Тендер ФЗ" or "Дополнительно" text in the ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ block
6. Verify "Маржа %" field exists in the ИТОГО block with a percentage value
7. Verify 3 exchange rate placeholders show "—": "Курс USD/RUB на дату КП", "Курс USD/RUB на дату СП", "Курс USD/RUB на дату УПД"
8. Check console for errors
EXPECT:
- 6 cards visible in 3 rows x 2 columns layout
- Block headers: ОСНОВНАЯ ИНФОРМАЦИЯ, ПОРЯДОК РАСЧЕТОВ, ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ, ДОСТАВКА, ИНФОРМАЦИЯ ДЛЯ ПЕЧАТИ, ИТОГО
- Workflow actors listed in Block II with "—" for empty FIOs
- Exchange rate placeholders show "—"
- Margin % visible in ИТОГО block
- No console errors

REPORT_TO: .claude/test-ui-reports/report-20260215-1030-session3.md
