# Navigation Architecture - OneStack

**Последнее обновление:** 2026-01-22
**Модель:** Hub-and-Spoke Navigation

---

## Основные принципы

### 1. Hub-and-Spoke (Звезда)

```
                    /tasks (HUB)
                        │
        ┌───────────────┼───────────────┐
        │               │               │
   /quotes/{id}    /deals/{id}    /specs/{id}
        │
   ┌────┴────┬────────┬────────┐
   │         │        │        │
overview  procurement logistics customs
```

**HUB (`/tasks`)** - единая точка входа для всех задач пользователя
**SPOKES** - детальные страницы объектов с role-based табами

### 2. Object-Oriented URLs (по сущностям)

| Сущность | Список | Детали | Создание |
|----------|--------|--------|----------|
| Quotes | `/quotes` | `/quotes/{id}` | `/quotes/new` |
| Customers | `/customers` | `/customers/{id}` | `/customers/new` |
| Suppliers | `/suppliers` | `/suppliers/{id}` | `/suppliers/new` |
| Deals | `/deals` | `/deals/{id}` | — |
| Specs | `/specs` | `/specs/{id}` | `/specs/create/{quote_id}` |

**Правило:** URL строится от сущности (noun), а не от действия (verb).

### 3. Role-Based Tabs (а не отдельные страницы)

**БЫЛО (плохо):**
```
/procurement/{quote_id}  ← отдельная страница
/logistics/{quote_id}    ← отдельная страница
/customs/{quote_id}      ← отдельная страница
```

**СТАЛО (хорошо):**
```
/quotes/{id}                    ← единая страница с табами
  └── tabs: [Обзор, Закупки, Логистика, Таможня, Контроль]
            (видимость по ролям)
```

**Исключение:** Legacy routes `/procurement/{id}`, `/logistics/{id}` и т.д. сохранены для совместимости, но используют те же табы.

---

## Структура Sidebar

```
ГЛАВНОЕ
├── Мои задачи      → /tasks (PRIMARY ENTRY POINT)
├── Новый КП        → /quotes/new (sales/admin)
└── Обзор           → /dashboard?tab=overview (admin/top_manager)

РЕЕСТРЫ
├── Клиенты         → /customers
├── Поставщики      → /suppliers
├── Юрлица-продажи  → /admin?tab=seller-companies
└── Юрлица-закупки  → /admin?tab=buyer-companies

ФИНАНСЫ (finance/top_manager/admin)
├── Сделки          → /deals
├── ERPS            → /finance?tab=erps
└── Календарь       → /payments/calendar

АДМИНИСТРИРОВАНИЕ (admin)
├── Пользователи    → /admin?tab=users
└── Настройки       → /settings
```

**Принцип видимости:**
- Секция показывается только если у пользователя есть хотя бы одна роль для её элементов
- Элемент показывается только при наличии соответствующей роли

---

## Правила для новых страниц

### DO (правильно):

1. **Новая сущность** → создай CRUD routes:
   ```
   /entities          - список
   /entities/{id}     - детали
   /entities/new      - создание (если нужно)
   /entities/{id}/edit - редактирование (если нужно)
   ```

2. **Новый workspace для существующей сущности** → добавь таб:
   ```python
   # В quote_detail_tabs() добавить:
   {
       "id": "new_workspace",
       "label": "Новый раздел",
       "href": f"/quotes/{quote_id}?tab=new_workspace",
       "roles": ["new_role", "admin"],
   }
   ```

3. **Новый отчёт/инструмент** → добавь в существующий раздел через таб:
   ```
   /finance?tab=new_report
   /admin?tab=new_tool
   ```

### DON'T (неправильно):

1. **Не создавай отдельные workspace routes:**
   ```
   ❌ /new-department/{quote_id}  - плохо, дублирует структуру
   ✅ /quotes/{id}?tab=new-dept   - хорошо, расширяет существующую
   ```

2. **Не создавай глубокую вложенность:**
   ```
   ❌ /quotes/{id}/items/{item_id}/procurement/edit
   ✅ /quote-items/{item_id}/edit
   ```

3. **Не дублируй данные в разных местах:**
   ```
   ❌ /dashboard показывает то же, что /procurement
   ✅ /dashboard агрегирует задачи, /procurement - детали
   ```

---

## Role-Based Access Matrix

| Route | Roles |
|-------|-------|
| `/tasks` | all authenticated |
| `/quotes/*` | all authenticated |
| `/customers/*` | sales, sales_manager, admin |
| `/suppliers/*` | procurement, admin |
| `/deals/*` | finance, top_manager, admin |
| `/payments/*` | finance, top_manager, admin |
| `/admin/*` | admin |
| `/settings` | admin |

### Quote Detail Tabs:

| Tab | Roles |
|-----|-------|
| Обзор | all with quote access |
| Закупки | procurement, admin |
| Логистика | logistics, head_of_logistics, admin |
| Таможня | customs, head_of_customs, admin |
| Контроль | quote_controller, admin |

---

## Принцип единственной точки входа

**Для обычного сотрудника:**
```
Login → /tasks → Click task → /quotes/{id}?tab=my_workspace
                                    ↓
                              Work on task
                                    ↓
                              ← К задачам (back to /tasks)
```

**Для админа/руководителя:**
```
Login → /tasks → See all departments' tasks
            │
            ├── /dashboard?tab=overview (общая статистика)
            ├── /deals (финансовый контроль)
            └── /quotes/{id} (все табы видны)
```

---

## Миграция старых URL

При добавлении новой структуры сохраняй старые URL через редиректы:

```python
@rt("/old-route/{id}")
def get(id: str):
    return RedirectResponse(f"/new-route/{id}", status_code=301)
```

Или через совместимый роутинг (как сделано с `/procurement/{id}` → показывает те же табы).

---

## Checklist для новой страницы

- [ ] URL следует object-oriented паттерну?
- [ ] Это действительно новая сущность или можно добавить таб?
- [ ] Role-based доступ настроен?
- [ ] Добавлена в sidebar (если нужно)?
- [ ] Back link ведёт на /tasks?
- [ ] Старые URL сохранены/редиректятся?

---

## См. также

- `main.py:quote_detail_tabs()` - реализация role-based табов
- `main.py:1400-1650` - sidebar structure
- `main.py:3670-3760` - /tasks route (hub)
