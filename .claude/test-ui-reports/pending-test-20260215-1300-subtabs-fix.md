BROWSER TEST
timestamp: 2026-02-15T13:00:00Z
session: 2026-02-14 #4 (sub-tabs fix)
base_url: https://kvotaflow.ru

TASK: [86afdkuyb-v2] Продажи sub-tabs — layout fix + unified action card
URL: /quotes/74aa8aba-09ec-4e78-8f89-216e633d6210 (Q-202601-0013, has data)
STEPS:
1. Login as admin (admin@test.kvota.ru / Test123!)
2. Navigate to /quotes/74aa8aba-09ec-4e78-8f89-216e633d6210
3. Click "Продажи" tab

**Обзор sub-tab (default):**
4. Verify "Обзор" pill is active (blue), "Позиции" is inactive (gray)
5. Check ОСНОВНАЯ ИНФОРМАЦИЯ block (full-width, 2-column grid)
6. Check 2-column layout below: ДОСТАВКА (left) + ИТОГО (right) side-by-side
   - Both cards should be roughly equal width
   - ДОСТАВКА: country, city, address, method, terms fields
   - ИТОГО: Общая сумма, Общий профит, Количество позиций, Маржа (2x2 grid)
7. Verify NO action buttons, NO Handsontable on this sub-tab
8. Edit a delivery field (e.g. change city) — verify inline save works (no page reload)

**Позиции sub-tab:**
9. Click "Позиции" pill
10. Verify unified action card at top with buttons:
    - "Рассчитать" (or "Пересчитать" if already calculated) — click it, verify it navigates to /quotes/.../calculate
    - Go back, click "Позиции" again
    - "История версий" — click, verify navigates to /quotes/.../versions, go back
    - "Валидация Excel" — check if visible (depends on workflow status)
    - "КП PDF" — check if visible (depends on workflow status)
    - "Счёт PDF" — check if visible (depends on workflow status)
    - "Удалить КП" (red/danger) — click it, verify delete modal appears, click cancel
11. Verify Handsontable items grid below action card (3 items visible)
12. Verify "Добавить" and "Загрузить" buttons on items grid header
13. Verify "История переходов" collapsible section below grid
14. Verify NO info cards (ОСНОВНАЯ ИНФОРМАЦИЯ, ДОСТАВКА, ИТОГО) on this sub-tab

**Sub-tab switching:**
15. Click "Обзор" — verify cards appear, items disappear
16. Click "Позиции" — verify items appear, cards disappear
17. Check URL params: ?tab=overview&subtab=info vs ?tab=overview&subtab=products

**Назад button:**
18. On Обзор sub-tab: verify "Назад" link at bottom navigates to /quotes
19. Go back, on Позиции sub-tab: verify "Назад" link also present

20. Check console for errors

EXPECT:
- 2-column layout: ДОСТАВКА left, ИТОГО right (NOT stacked)
- ONE unified action card on Позиции (NOT two separate cards)
- All action buttons functional (navigate correctly)
- Delete modal shows on "Удалить КП" click
- Inline editing works on Обзор fields
- Clean sub-tab switching
- No console errors

REPORT_TO: .claude/test-ui-reports/report-20260215-1300-subtabs-fix.md
