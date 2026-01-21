# OneStack Design Guidelines - Customer Detail Page

## Проблемы текущего UI

### 1. Вертикальный скролл

- Нужно прокручивать страницу, чтобы увидеть контакты
- Нет быстрого обзора всей информации
- Неудобно для работы

### 2. Отсутствие inline-редактирования

- Для редактирования нужно переходить на отдельную страницу `/edit`
- Долгий workflow: Просмотр → Редактировать → Сохранить → Назад
- Нет возможности быстро изменить одно поле

### 3. Не компактное расположение

- Много пустого пространства
- Информация разбросана вертикально
- Сложно увидеть картину целиком

## Решение: Табы + Inline-редактирование

### Структура табов

```
┌──────────────────────────────────────────────────────────┐
│  [Общая информация] [Адреса] [Контакты]                 │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  Содержимое выбранной вкладки                            │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

**Примечание:** Директор/руководство - это просто один из контактов с соответствующей должностью.

### Вкладка 1: "Общая информация"

**Содержимое:**

- Название компании (с иконкой редактирования)
- ИНН, КПП, ОГРН (в одну строку, компактно)
- Статус (Активен/Неактивен) - toggle switch
- Основные контактные данные (email, phone)

**Inline-редактирование:**

- Click на поле → превращается в input
- Кнопки "Сохранить" / "Отмена" появляются рядом с полем
- После сохранения - автоматически обратно в режим просмотра

### Вкладка 2: "Адреса"

**Содержимое:**

- Юридический адрес (с кнопкой редактирования)
- Фактический адрес (с кнопкой редактирования)
- Адреса складов (список с возможностью добавлять/удалять)

**Динамический список складов:**

```
📍 Адрес склада 1    [Редактировать] [Удалить]
📍 Адрес склада 2    [Редактировать] [Удалить]
[+ Добавить адрес склада]
```

### Вкладка 3: "Контакты"

**Содержимое:**
Таблица с колонками:

- ФИО
- Должность
- Email
- Телефон
- ✍️ Подписант (checkbox)
- ⭐ Основной (checkbox)
- Заметки
- Действия (Редактировать/Удалить)

**Inline-редактирование в таблице:**

- Click на строку → режим редактирования
- Или кнопка "✏️ Редактировать" в строке
- [+ Добавить контакт] - кнопка под таблицей

## Технические детали (FastHTML + HTMX)

### Табы

```python
# HTML структура
Div(
    # Tab navigation
    Div(
        Button("Общая информация", hx_get=f"/customers/{id}/tabs/general",
               hx_target="#tab-content", cls="tab-btn active"),
        Button("Адреса", hx_get=f"/customers/{id}/tabs/addresses",
               hx_target="#tab-content", cls="tab-btn"),
        Button("Контакты", hx_get=f"/customers/{id}/tabs/contacts",
               hx_target="#tab-content", cls="tab-btn"),
        cls="tabs-nav"
    ),
    # Tab content (динамически загружается через HTMX)
    Div(id="tab-content", cls="tab-content"),
    cls="tabs-container"
)
```

### Inline-редактирование

**Режим просмотра:**

```python
Div(
    Span("ООО Рога и Копыта", id="company-name-display"),
    Button("✏️", hx_get=f"/customers/{id}/edit/name",
           hx_target="#company-name-display",
           hx_swap="outerHTML",
           cls="edit-btn"),
    cls="editable-field"
)
```

**Режим редактирования (HTMX возвращает):**

```python
Form(
    Input(value="ООО Рога и Копыта", name="company_name",
          id="company-name-input"),
    Button("✓", type="submit", cls="save-btn"),
    Button("✕", hx_get=f"/customers/{id}/cancel-edit/name",
           hx_target="#company-name-input",
           hx_swap="outerHTML",
           cls="cancel-btn"),
    hx_post=f"/customers/{id}/update/name",
    hx_target="#company-name-input",
    hx_swap="outerHTML",
    cls="edit-form"
)
```

### CSS стили

```css
/* Табы */
.tabs-nav {
  display: flex;
  gap: 0;
  border-bottom: 2px solid #e5e7eb;
  margin-bottom: 2rem;
}

.tab-btn {
  padding: 0.75rem 1.5rem;
  background: none;
  border: none;
  border-bottom: 3px solid transparent;
  cursor: pointer;
  font-weight: 500;
  color: #6b7280;
  transition: all 0.2s;
}

.tab-btn:hover {
  color: #3b82f6;
  background: #f9fafb;
}

.tab-btn.active {
  color: #3b82f6;
  border-bottom-color: #3b82f6;
}

.tab-content {
  min-height: 300px;
  padding: 1rem 0;
}

/* Inline-редактирование */
.editable-field {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.edit-btn {
  opacity: 0;
  padding: 0.25rem 0.5rem;
  background: #f3f4f6;
  border: 1px solid #d1d5db;
  border-radius: 0.25rem;
  cursor: pointer;
  font-size: 0.875rem;
  transition: opacity 0.2s;
}

.editable-field:hover .edit-btn {
  opacity: 1;
}

.edit-form {
  display: inline-flex;
  gap: 0.5rem;
  align-items: center;
}

.edit-form input {
  padding: 0.5rem;
  border: 2px solid #3b82f6;
  border-radius: 0.375rem;
  font-size: 1rem;
}

.save-btn {
  padding: 0.5rem 0.75rem;
  background: #10b981;
  color: white;
  border: none;
  border-radius: 0.375rem;
  cursor: pointer;
}

.cancel-btn {
  padding: 0.5rem 0.75rem;
  background: #ef4444;
  color: white;
  border: none;
  border-radius: 0.375rem;
  cursor: pointer;
}
```

## Преимущества нового дизайна

### 1. Меньше скролла

- Все данные в табах на одном уровне
- Быстрый переключатель между разделами
- Можно увидеть всю информацию без прокрутки

### 2. Быстрое редактирование

- Inline-редактирование прямо на странице просмотра
- Не нужно переходить на `/edit`
- Изменения сохраняются через HTMX без перезагрузки страницы

### 3. Компактность

- Информация сгруппирована логически
- Эффективное использование пространства
- Чистый и современный интерфейс

### 4. Масштабируемость

- Паттерн можно применить к другим страницам:
  - Детали котировок (Quotes)
  - Детали поставщиков (Suppliers)
  - Детали спецификаций
- Единообразный UX по всему приложению

## Следующие шаги

1. ✅ Создать базовую HTML/CSS структуру табов
2. ⏳ Реализовать переключение табов через HTMX
3. ⏳ Добавить inline-редактирование для простых полей (текст, числа)
4. ⏳ Реализовать динамический список складов (добавить/удалить)
5. ⏳ Реализовать inline-редактирование контактов в таблице
6. ⏳ Применить паттерн к другим страницам (Quotes, Suppliers)

---

## UI Modernization Roadmap

### Phase 1: PicoCSS Foundation ✅ COMPLETED (2026-01-20)

**Goal:** Add modern CSS framework for instant visual improvement

**Changes:**

- ✅ Added PicoCSS 2.0 CDN to page_layout
- ✅ Streamlined APP_STYLES to complement PicoCSS (removed redundant base styles)
- ✅ Kept custom styles: nav bar, status badges, stats grid, alerts
- ✅ Now using PicoCSS variables (--primary, --card-background-color, etc.)

**Benefits:**

- Modern, clean UI out of the box
- Beautiful forms, buttons, tables automatically
- Responsive design with no extra work
- ~10KB only, fast loading

**Files Changed:**

- `main.py:101-136` - Updated APP_STYLES
- `main.py:213` - Added PicoCSS link in page_layout

---

### Phase 2: DaisyUI Components ⏳ IN PROGRESS (Started 2026-01-20)

**Goal:** Add component library for tabs, modals, badges, and advanced UI elements

**Progress:**

**✅ Completed Items:**

1. **TailwindCSS + DaisyUI CDN Added**
   - Location: `main.py:216-217` in `page_layout` function
   - TailwindCSS for utility classes
   - DaisyUI 4.0 for component styling

2. **Component Helpers Created** (main.py:230-326)
   - `tab_nav()` - Tab navigation with HTMX integration
   - `badge()` - Colored badges (neutral, primary, success, warning, error, info)
   - `stat_card()` - Dashboard statistics cards with icons
   - `modal_dialog()` - Modal dialogs for confirmations

3. **Status Badges Migration Started**
   - Updated `status_badge()` function to use DaisyUI badges (main.py:432-439)
   - Replaced supplier list badges (main.py:~14091)
   - Replaced buyer company list badges (main.py:~14785)
   - Old CSS classes kept for backward compatibility

**⏳ TODO Items:**

4. **Tab Navigation Implementation**
   - Convert Customer Detail page to use `tab_nav()` helper
   - Apply to Quotes Detail page
   - Apply to Suppliers Detail page

**Original Plan (for reference):**

1. **TailwindCSS + DaisyUI CDN** ✅ DONE

   ```python
   # Add to page_layout Head:
   Script(src="https://cdn.tailwindcss.com"),
   Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/daisyui@4/dist/full.min.css")
   ```

2. **Implement Tab Navigation** ⏳ TODO
   - Use DaisyUI tabs: `<div class="tabs tabs-lifted">`
   - Convert Customer Detail page to use DaisyUI tabs
   - Apply to Quotes, Suppliers pages

3. **Add Component Helpers** ✅ DONE (in main.py)

   ```python
   def tab_nav(*tabs):
       """DaisyUI tab navigation"""
       return Div(*[
           A(tab["label"],
             href="#",
             cls=f"tab tab-lifted {'tab-active' if tab.get('active') else ''}",
             hx_get=tab["url"],
             hx_target="#tab-content")
           for tab in tabs
       ], cls="tabs tabs-lifted")

   def badge(text, type="default"):
       """DaisyUI badge component"""
       colors = {
           "default": "badge-neutral",
           "success": "badge-success",
           "warning": "badge-warning",
           "error": "badge-error"
       }
       return Span(text, cls=f"badge {colors.get(type, 'badge-neutral')}")

   def stat_card(label, value, description=""):
       """DaisyUI stat card"""
       return Div(
           Div(label, cls="stat-title"),
           Div(value, cls="stat-value"),
           Div(description, cls="stat-desc") if description else None,
           cls="stat"
       )
   ```

4. **Replace Custom Badges**
   - Convert `.status-badge` to DaisyUI badges
   - Use semantic colors: `badge-primary`, `badge-success`, etc.

**Estimated Effort:** 2-3 hours
**Impact:** Professional, modern UI with tabs and interactive components

**Files to Modify:**

- `main.py` - Add DaisyUI link, create helper functions
- Customer detail page - Convert to tabbed layout
- Quotes page - Add tab navigation
- Suppliers page - Add tab navigation

---

### Phase 3: Icons & Polish ⏳ TODO

**Goal:** Replace emoji icons with professional SVG icons and add subtle animations

**What to Add:**

1. **Heroicons Integration**

   ```python
   # Create icon helper function
   def icon(name, size="w-5 h-5"):
       """
       Heroicons SVG icon helper
       Common icons: pencil, trash, check, x-mark, plus, chevron-down
       """
       icons = {
           "pencil": '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10"/></svg>',
           "trash": '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"/></svg>',
           "check": '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5"/></svg>',
           "x-mark": '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>',
           "plus": '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15"/></svg>'
       }
       svg = icons.get(name, icons["check"])
       return NotStr(f'<svg class="{size}" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">{svg}</svg>')
   ```

2. **Replace Emoji Icons**
   - ✏️ → `icon("pencil")`
   - ✓ → `icon("check")`
   - ✕ → `icon("x-mark")`
   - 🗑️ → `icon("trash")`
   - ➕ → `icon("plus")`

3. **Add Subtle Animations**

   ```css
   /* Add to APP_STYLES */
   /* Smooth transitions */
   button,
   a,
   .badge,
   .tab {
     transition: all 0.2s ease;
   }

   /* Hover effects */
   button:hover {
     transform: translateY(-1px);
     box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
   }
   .card:hover {
     box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
   }

   /* Loading states */
   .htmx-request {
     opacity: 0.6;
     cursor: wait;
   }

   /* Fade-in animations */
   @keyframes fadeIn {
     from {
       opacity: 0;
       transform: translateY(10px);
     }
     to {
       opacity: 1;
       transform: translateY(0);
     }
   }
   .animate-in {
     animation: fadeIn 0.3s ease;
   }
   ```

4. **Enhanced Inline Editing** (from current design guide)
   - Add icon buttons with hover states
   - Smooth transitions when switching edit/view mode
   - Loading indicators during HTMX requests

**Estimated Effort:** 1-2 hours
**Impact:** Polished, professional feel with smooth interactions

**Files to Modify:**

- `main.py` - Add icon helper function, enhanced CSS
- All forms - Replace emoji with icon() helper
- Inline editing components - Add transitions and hover effects

---

## Summary

**Phase 1 (✅ DONE):** PicoCSS foundation - instant visual upgrade
**Phase 2 (⏳ TODO):** DaisyUI components - tabs, badges, advanced UI
**Phase 3 (⏳ TODO):** Icons & animations - polish and professional feel

**Total Effort:** ~4-6 hours for all phases
**Result:** Modern, professional, production-ready UI
