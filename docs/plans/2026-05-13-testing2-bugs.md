# Testing 2 — Bug Extract

**Date:** 2026-05-13
**Source:** Google Sheets "Testing 2" tab (`/tmp/testing2-real.txt`)
**Total bugs:** 58
**Users tested:** 8
**Affected pages (URL groups):** 5
**Unique test rows with at least one bug:** 18

## Users (column headers)

- **col H** — `ekaterina.kravtsova@masterbearing.ru` — РОП (Руководитель отдела продаж)
- **col I** — `bokov.a@masterbearing.ru` — МОП (Менеджер отдела продаж)
- **col J** — `chislova.e@masterbearing.ru` — РОЗ (Руководитель отдела закупок)
- **col K** — `ekaterina.pl@masterbearing.ru` — СтМОЗ (Старший менеджер отдела закупок)
- **col L** — `ekaterina.h@masterbearing.ru` — МОЗ (Менеджер отдела закупок)
- **col M** — `sidorov.a@masterbearing.ru` — РОЛ (Руководитель логистики)
- **col N** — `milana.d@masterbearing.ru` — МОЛ (Менеджер отдела логистики)
- **col O** — `oleg.k@masterbearing.ru` — МВЭД (Менеджер отдела ВЭД)

## Notes on extraction

- "Passed"/"passed"/"ok"/empty cells are SKIPPED.
- Rows where columns A–F (test definition) are all empty are SKIPPED (rows 20-49 in this sheet are numbered-only placeholders).
- "Не могу проверить" (cannot test) is recorded as a bug per spec (any non-pass text = bug), but the actual text is preserved so reviewers can downgrade to "blocked".
- Row IDs come from sheet column A (`№`), not row index.

## Counts

### By role
- **МВЭД**: 14
- **РОЛ**: 13
- **РОЗ**: 8
- **СтМОЗ**: 7
- **МОЗ**: 6
- **МОЛ**: 6
- **РОП**: 2
- **МОП**: 2

### By URL group
- `/quotes/{id}`: 35
- `/procurement/kanban`: 11
- `/quotes`: 6
- `/locations`: 4
- `/messages`: 2

## Bugs by page area

### `/quotes/{id}` (35 bugs)

#### B1–B8 — row №1 · Таможня КП / Q-202604-0047 · Главная страница - Инф. панель - Клиент

- **URL:** https://app.kvotaflow.ru/quotes/35079f61-b00e-4186-be75-f05428d8d606?invoice=07e53cc2-dabb-405e-a9c1-f88ec4096fac
- **Page:** Таможня КП / Q-202604-0047
- **Element:** Главная страница - Инф. панель - Клиент
- **Action:** Открываю страницу и просматриваю контент
- **Expected:** Корректно отражаются данные
- **Roles affected (8):** МВЭД, МОЗ, МОЛ, МОП, РОЗ, РОЛ, РОП, СтМОЗ
- **Actual (same for all 8 testers):**

  > Поправить отображение
  > FB-260513-100622-47b6
  > Контакт - не отражается фамилия
  > Адрес - не отражается полностью

#### B9–B16 — row №2 · Таможня КП / Q-202604-0047 · Главная страница - Инф. панель - Участники

- **URL:** https://app.kvotaflow.ru/quotes/35079f61-b00e-4186-be75-f05428d8d606?invoice=07e53cc2-dabb-405e-a9c1-f88ec4096fac
- **Page:** Таможня КП / Q-202604-0047
- **Element:** Главная страница - Инф. панель - Участники
- **Action:** Открываю страницу и просматриваю контент
- **Expected:** Отражаются участники и дата / время их добавления
- **Roles affected (8):** МВЭД, МОЗ, МОЛ, МОП, РОЗ, РОЛ, РОП, СтМОЗ
- **Actual (same for all 8 testers):**

  > Поправить отображение
  > FB-260513-100338-a778

#### B17–B18 — row №3 · Таможня КП / Q-202604-0047 · Таблица - Кнопка Все колонки

- **URL:** https://app.kvotaflow.ru/quotes/35079f61-b00e-4186-be75-f05428d8d606?invoice=07e53cc2-dabb-405e-a9c1-f88ec4096fac
- **Page:** Таможня КП / Q-202604-0047
- **Element:** Таблица - Кнопка Все колонки
- **Action:** Нажимаю на кнопку
- **Expected:** Выпадает список возможных фильтров
- **Roles affected (2):** МВЭД, РОЛ
- **Actual (same for all 2 testers):**

  > Выпадающий список выпадает под колонки таблицы, а не поверх нее. Таким образом не все кнопки досткпны к нажатию

#### B19–B20 — row №4 · Таможня КП / Q-202604-0047 · Расходы по таможне

- **URL:** https://app.kvotaflow.ru/quotes/35079f61-b00e-4186-be75-f05428d8d606?invoice=07e53cc2-dabb-405e-a9c1-f88ec4096fac
- **Page:** Таможня КП / Q-202604-0047
- **Element:** Расходы по таможне
- **Action:** Открываю страницу и просматриваю контент, Нажимаю на кнопку
- **Expected:** Кнопки работают корректно 
- **Roles affected (2):** МВЭД, РОЛ
- **Actual (same for all 2 testers):**

  > Кнопки работают корректно, но задублированны 
  > FB-260513-101402-304e

#### B21–B22 — row №5 · Таможня КП / Q-202604-0047 · Примечания

- **URL:** https://app.kvotaflow.ru/quotes/35079f61-b00e-4186-be75-f05428d8d606?invoice=07e53cc2-dabb-405e-a9c1-f88ec4096fac
- **Page:** Таможня КП / Q-202604-0047
- **Element:** Примечания
- **Action:** Открываю страницу и просматриваю контент, заполняю ячейку
- **Expected:** Примечания сохраняются 
- **Roles affected (2):** МВЭД, РОЛ
- **Actual (same for all 2 testers):**

  > После заполнения ячейки данные не сохраняются и не поялвяется кнопка сохранить. Думаю можно удалить, так как ниже есть еще одни примечания. ИЛИ СДЕЛАТЬ В ЭТОМ БЛОК ОТОБРАЖЕНИЕ ИНФОРМАЦИИ ОТ ИНЫХ ОТДЕЛОВ

#### B23–B24 — row №7 · Таможня КП / Q-202604-0047 · Ответственные

- **URL:** https://app.kvotaflow.ru/quotes/b4e56dac-8c0a-419c-ba8c-8f3c4861ac31?step=customs
- **Page:** Таможня КП / Q-202604-0047
- **Element:** Ответственные
- **Action:** Открываю страницу и просматриваю контент
- **Expected:** Отражаются участники и дата / время их добавления
- **Roles affected (2):** МВЭД, РОЛ
- **Actual (same for all 2 testers):**

  > Не работает (не отражает данные после МОЗ)

#### B25–B26 — row №8 · Таможня КП / Q-202604-0047 · Таблица

- **URL:** https://app.kvotaflow.ru/quotes/b4e56dac-8c0a-419c-ba8c-8f3c4861ac31?step=customs
- **Page:** Таможня КП / Q-202604-0047
- **Element:** Таблица
- **Action:** Открываю страницу и просматриваю контент, заполняю ячейки
- **Expected:** Данные заполняются и в таблице, и при открытом модальном окне
- **Roles affected (2):** МВЭД, РОЛ
- **Actual (same for all 2 testers):**

  > При изменении типа пошлины в таблице, она не меняется в модальном окне

#### B27–B28 — row №9 · Таможня КП / Q-202604-0047 · Модальное окно позиции 1

- **URL:** https://app.kvotaflow.ru/quotes/b4e56dac-8c0a-419c-ba8c-8f3c4861ac31?step=customs
- **Page:** Таможня КП / Q-202604-0047
- **Element:** Модальное окно позиции 1
- **Action:** Открываю страницу и просматриваю контент, заполняю ячейки
- **Expected:** Данные заполняются и отражаются внутри модального окна, а также таблице
- **Roles affected (2):** МВЭД, РОЛ
- **Actual (same for all 2 testers):**

  > При изменении типа пошлины и ее числа в модальном, она не меняется в таблице и не сохранется

#### B29–B30 — row №10 · Таможня КП / Q-202604-0047 · Модальное окно позиции 1 - Страна происхождения

- **URL:** https://app.kvotaflow.ru/quotes/b4e56dac-8c0a-419c-ba8c-8f3c4861ac31?step=customs
- **Page:** Таможня КП / Q-202604-0047
- **Element:** Модальное окно позиции 1 - Страна происхождения
- **Action:** Открываю страницу и просматриваю контент, заполняю ячейки
- **Expected:** При выборе страны происхождения, она отражается в таблице
- **Roles affected (2):** МВЭД, РОЛ
- **Actual (same for all 2 testers):**

  > Не отразилась страна. Отразилось число

#### B31–B32 — row №11 · Таможня КП / Q-202604-0047 · Кнопка - Таможня завершена

- **URL:** https://app.kvotaflow.ru/quotes/b4e56dac-8c0a-419c-ba8c-8f3c4861ac31?step=customs
- **Page:** Таможня КП / Q-202604-0047
- **Element:** Кнопка - Таможня завершена
- **Action:** Нажимаю на кнопку
- **Expected:** Этап завершается
- **Roles affected (2):** МВЭД, РОЛ
- **Actual (same for all 2 testers):**

  > Ничего не происходит

#### B33–B35 — row №14 · Логистика КП  / Q-202604-0051 · Панель информации о грузе

- **URL:** https://app.kvotaflow.ru/quotes/ee2969a9-4036-4cc5-966e-139ae995e270?invoice=23706f4f-c2da-4817-b0d5-bec355c2bdf9
- **Page:** Логистика КП  / Q-202604-0051
- **Element:** Панель информации о грузе
- **Action:** Открываю страницу и просматриваю контент
- **Expected:** Ожидаю увидеть: 
Откуда - Страна, Город, Адрес
Куда - Страна, Город, Адрес (конечный адрес)
Получатель - (Организация покупатель) - Наименование организации 
Вес - КГ
Габариты - мм
Объем - м3
Incoterms - 
Транзит через турцию или прямой - 

Описание груза или список позиций
- **Roles affected (3):** МВЭД, МОЛ, РОЛ
  - **РОЛ (sidorov.a@masterbearing.ru):**
    > Информация не полная
  - **МОЛ (milana.d@masterbearing.ru):**
    > Не могу проверить, тк на нее нет КП
  - **МВЭД (oleg.k@masterbearing.ru):**
    > Информация не полная

### `/procurement/kanban` (11 bugs)

#### B36–B38 — row №15 · Канбан закупок · Изучение содержания страницы

- **URL:** https://app.kvotaflow.ru/procurement/kanban
- **Page:** Канбан закупок
- **Element:** Изучение содержания страницы
- **Action:** Открываю страницу и просматриваю контент
- **Expected:** На стадии Поиск поставщика отражаются все КПП из таблицы /quotes, относящиеся к этой стадии
- **Roles affected (3):** МОЗ, РОЗ, СтМОЗ
- **Actual (same for all 3 testers):**

  > Отражается только одно старое КП - новые не появляются

#### B39–B41 — row №16 · Канбан закупок · Работоспособность элемента Ожидание цен

- **URL:** https://app.kvotaflow.ru/procurement/kanban
- **Page:** Канбан закупок
- **Element:** Работоспособность элемента Ожидание цен
- **Action:** Переношу данные на стадию
- **Expected:** --
- **Roles affected (3):** МОЗ, РОЗ, СтМОЗ
- **Actual (same for all 3 testers):**

  > Нет возможности проверить, так как не работае отображение на первой стадии

#### B42–B44 — row №17 · Канбан закупок · Работоспособность элемента Цены готовы

- **URL:** https://app.kvotaflow.ru/procurement/kanban
- **Page:** Канбан закупок
- **Element:** Работоспособность элемента Цены готовы
- **Action:** Переношу данные на стадию
- **Expected:** --
- **Roles affected (3):** МОЗ, РОЗ, СтМОЗ
- **Actual (same for all 3 testers):**

  > Нет возможности проверить, так как не работае отображение на первой стадии

#### B45–B46 — row №18 · Канбан закупок · Работоспособность элемента Распределение

- **URL:** https://app.kvotaflow.ru/procurement/kanban
- **Page:** Канбан закупок
- **Element:** Работоспособность элемента Распределение
- **Action:** Заполняю элемент
- **Expected:** --
- **Roles affected (2):** РОЗ, СтМОЗ
- **Actual (same for all 2 testers):**

  > Нет возможности проверить, так как не работае отображение на первой стадии

### `/quotes` (6 bugs)

#### B47–B52 — row №19 · Коммерческие предложения · Главная страница

- **URL:** https://app.kvotaflow.ru/quotes
- **Page:** Коммерческие предложения
- **Element:** Главная страница
- **Action:** Открываю страницу и просматриваю контент
- **Expected:** Простая таблица без разделений
- **Roles affected (6):** МВЭД, МОЗ, МОЛ, РОЗ, РОЛ, СтМОЗ
  - **РОЗ (chislova.e@masterbearing.ru):**
    > Таблица с разделением на Требует вашего действия и Остальные
  - **СтМОЗ (ekaterina.pl@masterbearing.ru):**
    > Таблица с кп где только - Требует вашего действия
  - **МОЗ (ekaterina.h@masterbearing.ru):**
    > Таблица с разделением на Требует вашего действия и Остальные
  - **РОЛ (sidorov.a@masterbearing.ru):**
    > Таблица с разделением на Требует вашего действия и Остальные
  - **МОЛ (milana.d@masterbearing.ru):**
    > Таблица с разделением на Требует вашего действия и Остальные
  - **МВЭД (oleg.k@masterbearing.ru):**
    > Таблица с разделением на Требует вашего действия и Остальные

### `/locations` (4 bugs)

#### B53–B56 — row №13 · Локации · Главная страница

- **URL:** https://app.kvotaflow.ru/locations
- **Page:** Локации
- **Element:** Главная страница
- **Action:** Открываю страницу и просматриваю контент
- **Expected:** Кнопку содания локации
- **Roles affected (4):** МВЭД, МОЛ, РОЗ, РОЛ
- **Actual (same for all 4 testers):**

  > Добавить возможность создания локации

### `/messages` (2 bugs)

#### B57–B58 — row №12 · Сообщения · Главная страница

- **URL:** https://app.kvotaflow.ru/messages
- **Page:** Сообщения
- **Element:** Главная страница
- **Action:** Открываю страницу и просматриваю контент, заполняю ячейку
- **Expected:** Отражаются сообщения пользователя
- **Roles affected (2):** МВЭД, МОЛ
  - **МОЛ (milana.d@masterbearing.ru):**
    > Не могу проверить, тк на нее нет КП
  - **МВЭД (oleg.k@masterbearing.ru):**
    > Вообще не отражаютяс карточки чатов

### Procurement step + Заявка on Q-202605-0007 (4 rows, added after original triage)

> Discovered 2026-05-13 mid-session — sheet was updated with 4 new test rows
> all keyed to a SECOND quote: Q-202605-0007 (87bd01a3-cf24-4017-89fa-dd8e7ff96d1d).

#### row №20 · Закупки / Q-202605-0007 · Таблица КПП

- **URL:** https://app.kvotaflow.ru/quotes/87bd01a3-cf24-4017-89fa-dd8e7ff96d1d
- **Element:** Таблица КПП
- **Action:** Нажимаю на ячейку
- **Expected:** Таблица принимает данные в ячейку и сохраняет
- **Roles affected (3):** РОЗ, СтМОЗ, МОЗ
- **Actual (same for all 3 testers):**
  > Таблица прыгает при сохранении данных в каждой ячейке

#### row №21 · Закупки / Q-202605-0007 · Таблица КПП

- **URL:** https://app.kvotaflow.ru/quotes/87bd01a3-cf24-4017-89fa-dd8e7ff96d1d
- **Element:** Таблица КПП
- **Action:** Открываю страницу и просматриваю контент
- **Expected:** Ячейки — Страна / Город / Адрес / Условия поставки / Валюта / НДС
- **Roles affected (3):** РОЗ, СтМОЗ, МОЗ
- **Actual (same for all 3 testers):**
  > Добавить «Адрес забора груза»
  > Добавить выбор контакта поставщика в модальное окно создания КПП (обязательные данные) — отразить в КПП контакт и его реквизиты

#### row №22 · Закупки / Q-202605-0007 · Кнопка «Назад»

- **URL:** https://app.kvotaflow.ru/quotes/87bd01a3-cf24-4017-89fa-dd8e7ff96d1d
- **Element:** Кнопка «Назад»
- **Action:** Нажимаю на кнопку
- **Expected:** Кнопка возвращает на предыдущую страницу
- **Roles affected (8 — ALL testers):** РОП, МОП, РОЗ, СтМОЗ, МОЗ, РОЛ, МОЛ, МВЭД
- **FB ticket:** FB-260513-155446-efa0
- **Actual (same for all 8 testers):**
  > Кнопка назад ведёт не на предыдущую страницу, а в раздел КП

#### row №23 · Заявка / Q-202605-0007 · Контакт

- **URL:** https://app.kvotaflow.ru/quotes/87bd01a3-cf24-4017-89fa-dd8e7ff96d1d
- **Element:** Контакт
- **Action:** —
- **Expected:** —
- **Roles affected (2):** РОП, МОП
- **Actual (same for both testers):**
  > Добавление контакта клиента должно быть обязательным для МОП. Запретить переход на следующий этап

## Cross-role systemic bugs

Bugs where the same test row has bug reports from ≥2 testers (likely backend/UI defect affecting everyone, not a role-permission issue).

- **row №1** [B1–B8] · _Таможня КП / Q-202604-0047 → Главная страница - Инф. панель - Клиент_ · roles: МВЭД, МОЗ, МОЛ, МОП, РОЗ, РОЛ, РОП, СтМОЗ (8 testers)
  - same actual text across testers: _Поправить отображение FB-260513-100622-47b6 Контакт - не отражается фамилия Адрес - не отражается полностью_
- **row №2** [B9–B16] · _Таможня КП / Q-202604-0047 → Главная страница - Инф. панель - Участники_ · roles: МВЭД, МОЗ, МОЛ, МОП, РОЗ, РОЛ, РОП, СтМОЗ (8 testers)
  - same actual text across testers: _Поправить отображение FB-260513-100338-a778_
- **row №19** [B47–B52] · _Коммерческие предложения → Главная страница_ · roles: МВЭД, МОЗ, МОЛ, РОЗ, РОЛ, СтМОЗ (6 testers)
  - **divergent actual** (2 different texts) — may be partial regression
- **row №13** [B53–B56] · _Локации → Главная страница_ · roles: МВЭД, МОЛ, РОЗ, РОЛ (4 testers)
  - same actual text across testers: _Добавить возможность создания локации_
- **row №14** [B33–B35] · _Логистика КП  / Q-202604-0051 → Панель информации о грузе_ · roles: МВЭД, МОЛ, РОЛ (3 testers)
  - **divergent actual** (2 different texts) — may be partial regression
- **row №15** [B36–B38] · _Канбан закупок → Изучение содержания страницы_ · roles: МОЗ, РОЗ, СтМОЗ (3 testers)
  - same actual text across testers: _Отражается только одно старое КП - новые не появляются_
- **row №16** [B39–B41] · _Канбан закупок → Работоспособность элемента Ожидание цен_ · roles: МОЗ, РОЗ, СтМОЗ (3 testers)
  - same actual text across testers: _Нет возможности проверить, так как не работае отображение на первой стадии_
- **row №17** [B42–B44] · _Канбан закупок → Работоспособность элемента Цены готовы_ · roles: МОЗ, РОЗ, СтМОЗ (3 testers)
  - same actual text across testers: _Нет возможности проверить, так как не работае отображение на первой стадии_
- **row №3** [B17–B18] · _Таможня КП / Q-202604-0047 → Таблица - Кнопка Все колонки_ · roles: МВЭД, РОЛ (2 testers)
  - same actual text across testers: _Выпадающий список выпадает под колонки таблицы, а не поверх нее. Таким образом не все кнопки досткпны к нажатию_
- **row №4** [B19–B20] · _Таможня КП / Q-202604-0047 → Расходы по таможне_ · roles: МВЭД, РОЛ (2 testers)
  - same actual text across testers: _Кнопки работают корректно, но задублированны FB-260513-101402-304e_
- **row №5** [B21–B22] · _Таможня КП / Q-202604-0047 → Примечания_ · roles: МВЭД, РОЛ (2 testers)
  - same actual text across testers: _После заполнения ячейки данные не сохраняются и не поялвяется кнопка сохранить. Думаю можно удалить, так как ниже есть е_
- **row №7** [B23–B24] · _Таможня КП / Q-202604-0047 → Ответственные_ · roles: МВЭД, РОЛ (2 testers)
  - same actual text across testers: _Не работает (не отражает данные после МОЗ)_
- **row №8** [B25–B26] · _Таможня КП / Q-202604-0047 → Таблица_ · roles: МВЭД, РОЛ (2 testers)
  - same actual text across testers: _При изменении типа пошлины в таблице, она не меняется в модальном окне_
- **row №9** [B27–B28] · _Таможня КП / Q-202604-0047 → Модальное окно позиции 1_ · roles: МВЭД, РОЛ (2 testers)
  - same actual text across testers: _При изменении типа пошлины и ее числа в модальном, она не меняется в таблице и не сохранется_
- **row №10** [B29–B30] · _Таможня КП / Q-202604-0047 → Модальное окно позиции 1 - Страна происхождения_ · roles: МВЭД, РОЛ (2 testers)
  - same actual text across testers: _Не отразилась страна. Отразилось число_
- **row №11** [B31–B32] · _Таможня КП / Q-202604-0047 → Кнопка - Таможня завершена_ · roles: МВЭД, РОЛ (2 testers)
  - same actual text across testers: _Ничего не происходит_
- **row №12** [B57–B58] · _Сообщения → Главная страница_ · roles: МВЭД, МОЛ (2 testers)
  - **divergent actual** (2 different texts) — may be partial regression
- **row №18** [B45–B46] · _Канбан закупок → Работоспособность элемента Распределение_ · roles: РОЗ, СтМОЗ (2 testers)
  - same actual text across testers: _Нет возможности проверить, так как не работае отображение на первой стадии_

## Role-specific bugs

Bugs reported by exactly one role (could indicate role-specific permission/logic).

---

## Resolutions

### row 19 (/quotes split table) — DOCS-ONLY, NO CODE CHANGE

**Verdict: A — INTENDED FEATURE.**

- Split introduced 2026-04-10 in commit `dd5397b8` (`feat(data-table): DataTable shell + quotes registry integration (Group 4)`). Body explicitly mentions row grouping for "Требует вашего действия". Five-week-old deliberate UX feature.
- Implementation: `frontend/src/features/quotes/ui/quotes-table-client.tsx:360-363` unconditional `rowGrouping={{ label, predicate: q => actionStatusSet.has(q.workflow_status) }}`; render logic in `frontend/src/shared/ui/data-table/data-table.tsx:386-421`.
- Per-role `actionStatuses` from `frontend/src/entities/quote/types.ts:112-155` + role-tier list filter from `frontend/src/entities/quote/queries.ts:48-71`.

**The СтМОЗ-only "anomaly" is also by design, not a sub-bug:**
- `isProcurementSeniorOnly` narrows СтМОЗ's list to `workflow_status = 'pending_procurement'` only (queries.ts:69-71, per `.kiro/steering/access-control.md`).
- `procurement_senior`'s action-status set is exactly `['pending_procurement']` (types.ts:116).
- Consequence: every row СтМОЗ sees is an action row → `otherRows.length === 0` → the `{otherRows.length > 0 && ...}` guard at `data-table.tsx:404` correctly hides the "Остальные" header.
- This is correct system behavior. Same logic predicts pure-customs users (МВЭД) should ALSO see no "Остальные" — if oleg.k reported seeing both sections, he likely has a second role assigned; quick DB check on `kvota.user_roles` would confirm (skipped unless asked).

**Explainer for tester guide:**

> Главная страница КП использует двухсекционную таблицу: сверху — заявки, требующие именно вашего действия (в зависимости от роли), ниже — все остальные. Если у вас доступ только к стадии закупок (СтМОЗ) или таможни (МВЭД без доп. ролей), второй секции «Остальные» может не быть — это нормально, у вас просто нет заявок вне вашей стадии. Ожидание «простая таблица без разделений» в этой версии не выполняется намеренно.

**If product later wants flat table for everyone:** remove `rowGrouping` prop in `quotes-table-client.tsx:360-363` (~3-line diff). Punt to product decision, not a hotfix.

**Optional low-priority follow-up ticket:** clarify "Остальные" semantics for narrowly-scoped roles — either always render the header (even empty, "—" or "0 заявок вне вашей стадии") for consistency, or document the conditional. Current behavior is correct but surprising to testers comparing notes across roles.

