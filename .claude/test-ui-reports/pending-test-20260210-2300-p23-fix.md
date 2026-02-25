BROWSER TEST
timestamp: 2026-02-10T23:30:00+03:00
session: 2026-02-10 #1
base_url: https://kvotaflow.ru

TASK: [P2.3] Cost Analysis fix — verify 500 error is resolved
URL: /quotes/{any_calculated_quote}

TEST 1: Calculated quote — tab loads without 500
STEPS:
1. Navigate to /quotes and find Q-202602-0073 (calculated, has price data)
2. Click the "Кост-анализ" tab
3. Verify page loads WITHOUT 500 error
4. Verify P&L waterfall table is visible with rows:
   - Выручка (без НДС) — should show non-zero number
   - Сумма закупки
   - Логистика (итого) with W2-W10 sub-rows
   - Пошлина
   - Акциз
   - Валовая прибыль
   - Financial expenses (DM fee, Forex, Fin agent, Financing)
   - Чистая прибыль
   - Наценка %
5. Verify top metric cards show: Выручка, Наценка %, Продажа/Закупка
6. Check console for errors

TEST 2: Uncalculated quote — "not calculated" message
STEPS:
1. Navigate to a draft quote (e.g., Q-202602-0075 or any new/draft quote)
2. Click the "Кост-анализ" tab
3. Verify it shows "Расчёт ещё не выполнен" message (NOT a 500 error)
4. Check console for errors

EXPECT:
- No 500 error on either quote type
- Calculated quote shows full P&L waterfall with real numbers
- Uncalculated quote shows friendly "not calculated" message
- No console errors
- No regression on other quote tabs

REPORT_TO: .claude/test-ui-reports/report-20260210-2300-p23-fix.md
