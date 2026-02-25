BROWSER TEST
timestamp: 2026-02-12T02:30:00
session: 2026-02-11 #2
base_url: https://kvotaflow.ru

LOGIN: Use admin account (Test123!)

TASK: [svodka-default] Сводка tab is default and renders cards
URL: https://kvotaflow.ru/quotes/1f3440d7-33e0-41bd-aadb-2c17edd42008
STEPS:
1. Login as admin
2. Navigate to /quotes/1f3440d7-33e0-41bd-aadb-2c17edd42008 (Q-202601-0004, has deal)
3. Verify "Сводка" is the FIRST tab and active by default
4. Verify 6 white cards visible:
   - "ОСНОВНАЯ ИНФОРМАЦИЯ" — client name (clickable link), ИНН, seller company, ИНН продавца, контактное лицо
   - "ДОСТАВКА" — тип сделки, базис поставки, страна, город, адрес
   - "ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ" — тендер, источник, создатель, дата создания, примечания
   - "ПОРЯДОК РАСЧЕТОВ" — условия, предоплата, аванс %, валюта, курс
   - "ИТОГО" — общая сумма + общий профит (both in quote currency, NOT USD), кол-во позиций
   - "ИНФОРМАЦИЯ ДЛЯ ПЕЧАТИ" — дата выставления, срок действия
5. Verify cards use white background with subtle borders (like customer detail page)
6. Verify action buttons present: "Отправить на проверку", "Скачать"
7. Click "Скачать" — should navigate to export/specification (no 404)
8. Check console for errors
EXPECT: 6 cards with auto-filled data, clean white design, no errors

TASK: [svodka-tab-switch] Can switch between Сводка and Продажи
URL: https://kvotaflow.ru/quotes/1f3440d7-33e0-41bd-aadb-2c17edd42008
STEPS:
1. On same quote, verify "Сводка" tab is active
2. Click "Продажи" tab
3. Verify Продажи content loads (items table, Handsontable)
4. Click "Сводка" tab again
5. Verify Сводка cards reload correctly
6. Click a finance tab (e.g. "Сделка") — verify it works too
7. Check console for errors
EXPECT: Tab switching works smoothly between all tabs

TASK: [svodka-draft] Сводка on draft quote (minimal data)
URL: https://kvotaflow.ru/quotes
STEPS:
1. Find a ЧЕРНОВИК (draft) quote and open it
2. Verify Сводка is default tab
3. Verify cards render with "—" for missing fields (no crashes)
4. Verify no finance tabs in second row (draft = no deal)
5. Check console for errors
EXPECT: Graceful handling of empty/null fields, shows "—" where data is missing

REPORT_TO: .claude/test-ui-reports/report-20260212-0230-svodka.md
