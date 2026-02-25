BROWSER TEST
timestamp: 2026-02-15T11:30:00Z
session: 2026-02-14 #4
base_url: https://kvotaflow.ru

TASK: [86afdkuyb] Продажи tab redesign
URL: /quotes/74aa8aba-09ec-4e78-8f89-216e633d6210 (Q-202601-0013, has data)
STEPS:
1. Login as admin (admin@test.kvota.ru / Test123!)
2. Navigate to /quotes/74aa8aba-09ec-4e78-8f89-216e633d6210
3. Click "Продажи" tab (should be the 2nd tab)
4. Check 3-block layout:
   - Block I: "ОСНОВНАЯ ИНФОРМАЦИЯ" with 2-column grid
     - LEFT column: Создал, Клиент (dropdown), Компания-продавец (dropdown), Контактное лицо (dropdown)
     - RIGHT column: Дата создания, Доп. информация (textarea), Срок действия (дней), Дата КП
   - Block II: "ДОСТАВКА" with delivery fields (country, city, method, delivery address, terms)
   - Block III: "ИТОГО" with 4 metrics: Сумма, Профит, Позиций, Маржа %
5. Verify action buttons appear ABOVE the items spreadsheet:
   - "Рассчитать" button (left side)
   - "Отправить на контроль" button (right side, only if status is pending_sales_review)
6. Verify items spreadsheet (Handsontable) appears BELOW the action buttons
7. Check that there are NO separate "Доп. информация" or "Для печати" cards — they should be merged into Block I
8. Verify "Доп. информация" textarea is editable (type something, check it saves inline via HTMX)
9. Check console for errors
EXPECT:
- 3 blocks visible: ОСНОВНАЯ ИНФОРМАЦИЯ, ДОСТАВКА, ИТОГО
- Block I has 2-column layout with creator/date on the right
- ИТОГО block shows total amount, profit, item count, margin %
- Action buttons (Рассчитать) above items table
- No separate cards for "Для печати" or "Доп. информация"
- Textarea for additional_info works (inline save)
- No console errors

REPORT_TO: .claude/test-ui-reports/report-20260215-1130-session4.md
