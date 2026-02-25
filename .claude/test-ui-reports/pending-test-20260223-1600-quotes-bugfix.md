BROWSER TEST
timestamp: 2026-02-23T16:00:00+03:00
session: 2026-02-23 #1
base_url: https://kvotaflow.ru

TASK: [86afmrkh9] Ретест багов из report-20260223-1530-quotes-filters.md

--- RETEST 1: Dropdown синхронизация с URL ---
URL: /quotes?status=draft
LOGIN: admin
STEPS:
1. Перейти напрямую на /quotes?status=draft
2. Проверить: dropdown "Статус" показывает "Черновик" (НЕ "Все статусы")
3. Перейти на /quotes?status=pending_procurement
4. Проверить: dropdown показывает "Закупки"
5. Перейти на /quotes (без параметров)
6. Проверить: dropdown показывает "Все статусы"
EXPECT:
- Dropdown всегда отражает текущий URL-параметр
- "Все статусы" выбран только когда status пуст

--- RETEST 2: Sales — менеджер-dropdown скрыт (имперсонация) ---
URL: /quotes
LOGIN: admin → имперсонация как "Продажи"
STEPS:
1. Имперсонироваться как "Продажи"
2. Перейти на /quotes
3. Проверить: видны ТОЛЬКО 2 dropdown-а — "Статус" и "Клиент"
4. Проверить: dropdown "Менеджер" ОТСУТСТВУЕТ
5. Проверить: в списке только КП текущего пользователя
6. Вручную добавить ?manager_id=00000000-0000-0000-0000-000000000000 в URL
7. Проверить: параметр игнорируется, показываются те же КП что и без него
EXPECT:
- Dropdown "Менеджер" не виден для sales
- manager_id в URL не влияет на результат
- Показаны только свои КП

--- RETEST 3: Procurement — всё работает ---
URL: /quotes
LOGIN: admin → имперсонация как "Закупки"
STEPS:
1. Имперсонироваться как "Закупки"
2. Перейти на /quotes
3. Проверить: все 3 dropdown-а видны (Статус, Клиент, Менеджер)
4. Выбрать фильтр "Статус" → "Черновик"
5. Проверить: таблица отфильтрована, dropdown показывает "Черновик"
6. Нажать "Сбросить"
7. Проверить console на ошибки
EXPECT:
- 3 dropdown-а для procurement
- Фильтры работают
- Dropdown синхронизирован с URL после выбора
- Нет JS ошибок

REPORT_TO: .claude/test-ui-reports/report-20260223-1600-quotes-bugfix.md
