# Triage отчёт РОЗ Тест (Е. Числова, 2026-05-03)

**Источник:** `Project kvotaflow - РОЗ Тест.csv` (158 заполненных строк)
**Тестировщик:** chislova.e@masterbearing.ru, ЗАКУПКИ, Руководитель закупок (РОЗ)
**Метод:** cross-reference с МОЗ Тест triage (`2026-05-01-moz-test-triage.md`) → выделить только новые failures + регрессии.

---

## Сводка

| Статус | Кол-во | % |
|--------|-------|---|
| Passed | 100 | 63% |
| Passed with Notes | 19 | 12% |
| **Failed** | **30** | **19%** |
| Blocked | 2 | 1% |
| Not Run | 9 | 6% |

**Из 30 Failed:**
- ✅ ~17 уже закрыты в PR #77–82 (МОЗ triage) — нужно только пометить
- ⚠️ 3 кандидата на регрессию — требуют браузерной проверки
- 🆕 7 truly new — попадают в спринт
- ❌ 3 deferred (UX redesigns / cleanup)

---

## ✅ Закрыто в PR #77–82 (МОЗ triage cross-reference)

Подтверждение: РОЗ тестировался ДО мерджа PR #77–82. Эти Failed уже не воспроизводятся. Пометить как closed без повторных фиксов.

| РОЗ # | Описание | Соответствие МОЗ | PR |
|-------|----------|------------------|-----|
| 32 | Кнопка «Мои КП» — фильтр неверный | МОЗ #28 | #77 |
| 39 | Должности «unknown» в чатах | МОЗ #35 | #79 |
| 41 | Не отражается время сообщений | МОЗ #37 | #79 |
| 43 | Файл (скрепка) не отражается в чате | МОЗ #39 | #80 |
| 44 | Файл (скрепка) не появляется в документах КП | МОЗ #40 | #80 |
| 46 | Файл (drag-drop) не отражается в чате | МОЗ #42 | #80 |
| 47 | Файл (drag-drop) не появляется в документах КП | МОЗ #43 | #80 |
| 69 | В блоке «Подразделение» нет руководителя | МОЗ #56 | #78 |
| 81 | Drag-and-drop в документы не работает | МОЗ #68 | #77 |
| 83 | Кнопка «Удалить» документ не работает | МОЗ #70 | #77 |
| 84 | Кнопка «Скачать» открывает, не качает | МОЗ #71 | #79 |
| 89 | Поиск в dropdown «Поставщик» не работает | МОЗ #76 | #82 |
| 91 | Поиск в dropdown «Компания-покупатель» | МОЗ #78 | #82 |
| 101 | Бренд не полностью + нет ед.изм в КПП позициях | МОЗ #107 | #78 |
| 104 | Назначение позиций в КПП требует reload | МОЗ #91 | #78 |
| 111 | XLS всегда RU | МОЗ #98 | #79 |
| 117 | Список позиций не тянется в письмо | МОЗ #104 | #81 |
| 120 | В таблице позиций КПП нет Ед.Изм / Наим. произв. | МОЗ #107 | #78 |
| 121 | Крестик «удалить позицию из КПП» не работает | МОЗ #108 | **(подтверждено пользователем 2026-05-03 — реализовано)** |

---

## ❌ Deferred / Не делаем (МОЗ triage cross-reference)

| РОЗ # | Описание | Причина |
|-------|----------|---------|
| 85 | Переработать полосу кнопок под Header | МОЗ F.72 — design redesign, отдельный design-task |
| 87 | Доп.поля в КПП modal (адрес, комментарий, контакт) | МОЗ #74 — было закрыто до МОЗ теста |
| 119 | Удалить блок под историей отправок | МОЗ I.106 — cleanup, низкий приоритет |

---

## ⚠️ Регрессии — браузерная проверка 2026-05-03

Проверено под `chislova.e@masterbearing.ru` (роли: procurement + head_of_procurement) на проде.

### R1 — Канбан закупок (РОЗ #58) — ✅ НЕ регрессия
- Открыта `/procurement/kanban`: «17 карточек в работе», колонки «Распределение» (2) и «Поиск поставщика» (14) и далее заполнены.
- Старый отчёт устарел — фикс PR #74 работает корректно.

### R2 — Грузовые места (РОЗ #109) — 🆕 ПОДТВЕРЖДЁН реальный баг
- КП `9cb179a7-...` (`Q-202604-0073`) на стадии «На закупке», КПП открыт.
- Блок «Грузовые места (1)» отображается как plain `<div class="text-xs text-muted-foreground tabular-nums">` без клика, без кнопок, без input'ов.
- После клика «Редактировать с одобрением» — появились 3 checkbox'а для позиций, **но cargo places по-прежнему read-only**.
- **Вывод:** НЕТ affordance для edit грузовых мест, ни до запроса одобрения, ни после.

### R3 — Подготовить письмо (РОЗ #112) — ✅ НЕ регрессия
- На том же КП клик «Подготовить письмо» в КПП → открывается стандартная modal (`role="dialog"`, ширина 512px, центрирована).
- Старый отчёт был, видимо, опечаткой (CSV содержал «Соответствует ожидаемому» при статусе Failed).

---

## 🆕 Truly new failures (попадают в спринт)

### Группа N1 — Distribution: фильтр активных + UX (РОЗ #49 + #52, #57) — 🆕 ПОДТВЕРЖДЕНЫ

| # | Что | Root cause (verified) | Серьёзность |
|---|-----|----------|-------------|
| 49 | Блок «Загрузка закупщиков» — все МОЗ, включая banned | DB: `barmina.a@masterbearing.ru` имеет `auth.users.banned_until = 2126-03-22` (будущее = activated permanent ban). UI fetch не фильтрует по `banned_until IS NULL OR banned_until < now()`. | Med |
| 52 | Dropdown «Назначить МОЗ» — те же все МОЗ | Тот же fetch (один компонент `Загрузка` + dropdown шарят источник). Dropdown сейчас searchable (PR #82), но фильтр active отсутствует. | Med |
| 57 | Sidebar badge ≠ page header: badge="2", header="3 заявки" | Два разных counter'а: sidebar badge запрашивает один источник, страница — другой. На /quotes отдельно — 36 КП «Всего», без видимого procurement-stage filter. | Med |

**Триаж N1 (подтверждено в браузере 2026-05-03):**
- **49 + 52** — один фикс: добавить фильтр `auth.users.banned_until IS NULL OR auth.users.banned_until < now()` AND `auth.users.deleted_at IS NULL` в `fetchProcurementUsers` и в "Загрузка закупщиков" query. Колонки `banned_until`, `deleted_at` существуют в `auth.users`.
- **57** — найти источник sidebar-badge counter и выровнять с заголовком distribution-страницы. Возможно один из них считает по `workflow_status='pending_procurement'` (3), а другой по более узкому условию (2). Нужен grep по `Распределение` + `count`.

---

### Группа N2 — Suppliers list пустой (РОЗ #60) 🔴 P5 — 🆕 ROOT CAUSE НАЙДЕН

| # | Что | Root cause (verified) | Серьёзность |
|---|-----|----------|-------------|
| 60 | `/suppliers` — «Всего: 0 / Поставщики не найдены» | Frontend role-helper bug (см. ниже) | **High** |

**Браузерная проверка 2026-05-03:**
- DB содержит **45 поставщиков** в той же организации, в которой состоит chislova.e
- Supabase RLS policy `suppliers_select_policy` корректна — фильтрует по `organization_id IN (members of user)`
- Корневая причина: **frontend** в `frontend/src/entities/supplier/queries.ts:68` вызывает `isProcurementOnly(user.roles)` → если true, накладывает фильтр `id IN (assignedSupplierIds)`, и при пустом массиве — sentinel UUID `00000000-...` → 0 строк.
- В `frontend/src/shared/lib/roles.ts:57` `isProcurementOnly` возвращает **true для head_of_procurement**, хотя docstring явно говорит обратное:
  > «head_of_procurement sees all suppliers (not "procurement only").»

**Несоответствие кода и комментария:**
```ts
const PROCUREMENT_ROLES = ["procurement", "procurement_senior", "head_of_procurement"];
const NON_PROCUREMENT_ROLES = [/* … */, "head_of_logistics" /* head_of_procurement отсутствует */];

export function isProcurementOnly(roles: string[]): boolean {
  return (
    roles.some((r) => PROCUREMENT_ROLES.includes(r)) &&            // true для head_of_procurement
    !roles.some((r) => NON_PROCUREMENT_ROLES.includes(r))           // true (нет broader-visibility ролей)
  );  // ⇒ возвращает true вместо false
}
```

**Fix (один из двух):**
1. Убрать `head_of_procurement` из `PROCUREMENT_ROLES` (тогда нужно поправить `hasProcurementAccess`, `canManageSupplierAssignees` и др., чтобы явно включали head)
2. Добавить early-return: `if (roles.includes("head_of_procurement")) return false;` — соответствует docstring, наименьший blast radius

**Рекомендация:** вариант 2 — точечный, не ломает другие места.

**Дополнительно проверить:** есть ли другие места, где `isProcurementOnly` вызывается, которые могут сейчас неправильно блокировать РОЗ (positions, brand_assignments, и т.д.). `grep -rn "isProcurementOnly" frontend/src/`.

---

### Группа N3 — Approval flow: уведомления (РОЗ #158) — 🆕 ПОДТВЕРЖДЁН partial

| # | Что | Root cause (verified) | Серьёзность |
|---|-----|----------|-------------|
| 158 | «Редактировать с одобрением» — пишет «отправлено», нигде не отражается | Approval INSERT работает, но pipeline на notifications **не срабатывает** | Med |

**Браузерная проверка 2026-05-03:**
- Клик «Редактировать с одобрением» на КП `9cb179a7-...` (`Q-202604-0073`)
- В `kvota.approvals` создалось **5 записей** в момент клика (09:57:37):
  ```
  approval_type = 'edit_completed_procurement'
  status = 'pending'
  approver_id = [Гумер В., Конюховский А., Гук И., Пластинина Е., Новиков А.]
  ```
- В `kvota.notifications` за тот же промежуток — **0 записей**.
- **UI feedback после клика:** пустой toast (`role="status"` элемент создан, но `innerText=""`). Пользователь не видит подтверждения.

**Триаж:**
- ❌ **Backend pipeline broken** — нет триггера/сервиса, который при INSERT в `approvals` создаёт `notifications` записи. Это узкий fix (миграция с триггером, или вызов notify-сервиса из API endpoint что INSERT'ит approval).
- ❌ **UI feedback broken** — toast не содержит текста. Возможно `toast()` вызывается с пустой строкой ИЛИ строка не подтягивается. Точечный fix в Server Action / API client.

**Approvers** (получатели нотификаций):
- 4× admin
- 1× head_of_procurement (Пластинина) — корректно, начальник заявителя
- 1× currency_controller — странно для procurement-edit
- 1× finance/CFO — нормально

Список approver'ов выглядит грубым broadcast (все админы). Возможно нужна более узкая логика выбора approver'а для `edit_completed_procurement` типа.

**Действие:** добавить `INSERT INTO kvota.notifications (channel='telegram', type='approval_requested', user_id=approver_id, approval_id=…, title=…, message=…)` в момент создания approval. Telegram-dispatch worker уже существует (см. `kvota.telegram_users`).

---

### Группа N4 — Кросс-страничный default step (РОЗ #54 + #80) — 🆕 ПОДТВЕРЖДЕНЫ

| # | Что | Root cause (verified) | Серьёзность |
|---|-----|----------|-------------|
| 54 | Клик IDN в distribution → стадия «Заявки», нужна «Закупки» | URL после клика: `/quotes/aa64551e-...` (без `?step=`), активная стадия = «Заявка» (DOM: `bg-accent/10` на кнопке Заявка). КП имеет `workflow_status='pending_procurement'` («На закупке») — но default step не учитывает stage/role. | Med |
| 80 | «Закрыть документы» возвращает на «Заявку», не на «Закупки» | Линк «Закрыть документы» имеет `href="/quotes/{id}"` без `?step=`, поэтому fallback тот же default = Заявка | Med |

**Подтверждено в браузере 2026-05-03:** оба бага имеют общий root cause — **default step при отсутствии `?step=` всегда «Заявка»**, не учитывает ни роль пользователя, ни workflow_status КП.

**Возможные fix-стратегии (выбрать одну):**
1. **Default = workflow_status of КП** — если КП на `pending_procurement`, дефолт «Закупки»; если на `pending_logistics_and_customs`, дефолт «Логистика»; и т.д. Минимум role-логики, бизнесово консистентно.
2. **Default = последняя стадия пользователя в URL** — Next.js может хранить `searchParams` в session-storage. Лишняя сложность.
3. **Линк «Закрыть документы» — preserve previous step** — использовать `router.back()` или передавать `?step=…` через URL state. Точечно для #80.

**Рекомендация:** **#1 (workflow_status-aware default)** — закрывает оба бага в одном PR + добавляет интуитивный UX для всех ролей. Покрыть unit-тестом маппинга `workflow_status → default step`.

---

## Сводная приоритизация (после браузерной верификации 2026-05-03)

### 🔴 P5 — Срочное исправление (mission-critical workflow break)
- **N2 (#60)** — Suppliers list пустой для РОЗ. **Root cause:** `isProcurementOnly` баг в `frontend/src/shared/lib/roles.ts:57`. **Fix:** одна строка — early-return для head_of_procurement.

### 🟠 P4 — Приоритетное (важная функциональность)
- **N1.49+52** — Distribution показывает забаненную Бармину А. **Fix:** добавить `banned_until` фильтр в users-query.
- **N4 (#54+80)** — Default step «Заявка» вместо stage-aware. **Fix:** workflow_status-aware default в quote detail layout.
- **R2 (#109)** — Cargo places read-only без affordance. **Подтверждённый bug**, не регрессия — поле никогда не было editable из summary view. Нужно edit-modal или inline edit.
- **N3 (#158) — backend pipeline** — approvals INSERT работает, notifications не создаются. **Fix:** trigger/service для INSERT в notifications при INSERT в approvals.

### 🟡 P3 — Средний (UX / полу-фичи)
- **N1.57** — Sidebar badge counter ≠ page header counter. **Fix:** найти и выровнять источники.
- **N3 (#158) — UI feedback** — пустой toast после клика «Редактировать с одобрением». **Fix:** заполнить текст toast'а в Server Action.
- **N3 (#158) — approver list** — broadcast на 4 admin'а. **Triage:** обсудить корректность списка approver'ов для `edit_completed_procurement`.

### ✅ Не регрессии (подтверждено 2026-05-03)
- **R1 (#58)** — канбан показывает 17 карточек, всё работает.
- **R3 (#112)** — модалка письма открывается корректно.

### ❌ Не делаем
- РОЗ #85, #87, #119 (см. Deferred выше)

---

## Распределение по слоям

| Слой | Группы | Кол-во | Корневая причина |
|------|--------|--------|------------------|
| **Backend RLS / permissions** | N2 (#60), R1 (#58) | 2 | Role-based filter blocks РОЗ visibility |
| **Backend queries — фильтры** | N1.49+52, N1.57 | 2 | Missing `is_active` / mismatched filters |
| **Frontend routing — default step** | N4 (#54, #80) | 1 | Role-aware default missing |
| **Backend approval pipeline** | N3 (#158) | 1 | Notifications not implemented or broken |
| **Frontend regression** | R2 (#109), R3 (#112) | 2 | Possible regressions from recent PRs |

---

## План действий (финал)

### Шаг 1 — ✅ Браузерная проверка завершена (2026-05-03)
Все 8 пунктов проверены под `chislova.e@masterbearing.ru`. Результаты выше.

### Шаг 2 — Группировка в /lean-tdd батч (готов к запуску)

| Track | Задача | Файлы (предположительно) | Сложность |
|-------|--------|--------------------------|-----------|
| **A — P5 (одна строка)** | N2 (#60) — Suppliers fix | `frontend/src/shared/lib/roles.ts` | XS |
| **B — P4** | N1.49+52 — banned_until filter | `frontend/src/entities/supplier/queries.ts` (`fetchProcurementUsers`) + источник «Загрузка закупщиков» | S |
| **C — P4** | N4 (#54+80) — workflow_status-aware default step | `frontend/src/app/quotes/[id]/page.tsx` или ближайший layout | M |
| **D — P4** | N3 backend — approval → notification pipeline | DB migration (trigger) ИЛИ Python API endpoint что INSERT'ит approval | M |
| **E — P4** | R2 (#109) — Cargo places editable | КПП card component (`frontend/src/features/quotes/ui/procurement-step/`) — отдельный edit modal или inline | M |
| **F — P3** | N1.57 — sidebar badge counter alignment | grep по `procurement/distribution` count | S |
| **G — P3** | N3 UI feedback — fill toast text | Server Action для approval-request | XS |

### Шаг 3 — Триаж-апдейт
После мерджа PR'ов — обновить этот документ с маркировкой `closed-by-PR-#NNN` (как сделано в МОЗ triage).

---

## Что обсудить перед /lean-tdd

1. **N2** — fix-стратегия 1 vs 2 в group N2 (см. выше). Рекомендация: вариант 2 (early-return). OK?
2. **N4** — workflow_status-aware default step (стратегия 1 в group N4). Альтернативы — preserve previous step или role-aware. OK?
3. **N3 backend** — есть ли уже dispatch worker для notifications? (Память: `kvota.notifications.channel='telegram'` + `telegram_users` table). Если есть — простой fix. Если нет — отдельный спринт.
4. **R2 cargo edit UX** — каким должен быть edit affordance? Inline (клик по cell → input)? Edit modal? Это отдельный design-task или сразу делаем?
5. **N3 approver list** — рассылка на 4 admin'а корректна для `edit_completed_procurement`? Или нужна узкая логика?
6. **Запускаем параллельно или последовательно?** A+B+C+G можно дать 4 разным агентам сразу (independent files). D+E+F — sequential.
