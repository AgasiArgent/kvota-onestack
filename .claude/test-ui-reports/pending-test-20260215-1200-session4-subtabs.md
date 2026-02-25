BROWSER TEST
timestamp: 2026-02-15T12:00:00Z
session: 2026-02-14 #4 (sub-tabs iteration)
base_url: https://kvotaflow.ru

TASK: [86afdkuyb-v2] Продажи tab sub-tabs split (Обзор + Позиции)
URL: /quotes/74aa8aba-09ec-4e78-8f89-216e633d6210 (Q-202601-0013, has data)
STEPS:
1. Login as admin (admin@test.kvota.ru / Test123!)
2. Navigate to /quotes/74aa8aba-09ec-4e78-8f89-216e633d6210
3. Click "Продажи" tab (should be the 2nd tab after Сводка)
4. Verify sub-tab pills appear: "Обзор" (active, blue background) and "Позиции"
5. On "Обзор" sub-tab check:
   - Block I: "ОСНОВНАЯ ИНФОРМАЦИЯ" full-width, 2-column grid
     - LEFT: Создал, Клиент, Компания-продавец, Контактное лицо
     - RIGHT: Дата создания, Доп. информация, Срок действия, Дата КП
   - Block II + III in 2-column layout below:
     - LEFT: "ДОСТАВКА" with delivery fields
     - RIGHT: "ИТОГО" with Сумма, Профит, Позиций, Маржа %
   - NO items spreadsheet visible
   - NO action buttons (Рассчитать) visible
6. Click "Позиции" sub-tab pill
7. Verify URL changes to ?tab=overview&subtab=products
8. On "Позиции" sub-tab check:
   - Unified action card with buttons:
     - "Рассчитать" (calculate)
     - "История версий" (version history)
     - "Валидация Excel" (validation)
     - "КП PDF" (quote PDF)
     - "Счёт PDF" (invoice PDF)
     - "Отправить на контроль" (if status allows)
     - "Удалить КП" (delete, danger style)
   - Handsontable items spreadsheet below action card
   - Workflow history section at bottom
   - NO info cards (ОСНОВНАЯ ИНФОРМАЦИЯ, ДОСТАВКА, ИТОГО) visible
9. Click "Обзор" pill to go back — verify cards reappear, items disappear
10. Check console for errors
EXPECT:
- 2 pill-style sub-tabs visible under Продажи tab
- Active pill has blue background (#3b82f6), inactive has gray (#f3f4f6)
- "Обзор" shows info cards only (3 blocks, delivery+itogo in 2-col layout)
- "Позиции" shows action card + Handsontable + workflow history only
- Switching between sub-tabs works correctly
- No console errors
- Clean separation — no content overlap between sub-tabs

REPORT_TO: .claude/test-ui-reports/report-20260215-1200-session4-subtabs.md
