BROWSER TEST
timestamp: 2026-02-11T01:00:00+03:00
session: 2026-02-10 #1
base_url: https://kvotaflow.ru

TASK: [BUG-2 RETEST] Delivery city saves correctly
URL: /quotes/ba4a486f-d2cb-4356-8832-db9db3c54246

TEST 1: City autocomplete works without TypeError
STEPS:
1. Navigate to Q-202602-0073
2. Find the city combobox in ДОСТАВКА section
3. Type "Моск" — verify autocomplete suggestions appear WITHOUT console TypeError
4. Select "Москва" from suggestions (or type full name)
5. Click outside (blur)
6. Reload the page
7. Verify "Москва" persisted in the city field
8. Check console — should be 0 errors (no more "Cannot read properties of undefined")
EXPECT:
- No TypeError on typing
- Autocomplete suggestions work
- City value persists after reload
- 0 console errors

---

TASK: [BUG-5 RETEST] Supplier invoices tab in finance
URL: /finance

TEST 2: Инвойсы tab shows supplier invoices
STEPS:
1. Navigate to /finance
2. Look for tabs — should now have 4: Рабочая зона, ERPS, Платежи, **Инвойсы**
3. Click "Инвойсы" tab
4. Verify table with columns: №, Номер инвойса, Поставщик, Дата, Срок оплаты, Сумма, Статус
5. If invoices exist, verify supplier names show (not just IDs)
6. Check summary footer with totals
7. Check console for errors
EXPECT:
- "Инвойсы" tab exists in finance
- Table displays supplier invoices from all quotes
- Supplier names resolved (not UUIDs)
- 0 console errors

---

TASK: [P2.8 RETEST] Expense form submission works
URL: /finance/ad66b5c0-93b7-44e7-8a83-18ad6ea33742

TEST 3: Add expense to logistics stage
STEPS:
1. Navigate to DEAL-2026-0002
2. Find ЛОГИСТИКА section
3. On "Первая миля" stage, click "+ Добавить расход"
4. Fill: Описание = "Транспорт", Amount = 5000, Currency = RUB
5. Click "Добавить"
6. Verify expense appears in the stage's expense list
7. Verify form closes or resets after successful add
8. Reload page — verify expense persisted
9. Check console for errors
EXPECT:
- Expense saves successfully
- Appears in stage expense list
- Persists after reload
- 0 console errors

REPORT_TO: .claude/test-ui-reports/report-20260211-0100-fixes.md
