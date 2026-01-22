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

### Phase 2: DaisyUI Components ✅ COMPLETE (Started 2026-01-20, Completed 2026-01-21)

**Goal:** Add component library for tabs, modals, badges, and advanced UI elements

**Status:** ✅ Deployed to production | 🟢 Live at https://kvotaflow.ru

**What's Live:**

- Modern badge components with proper colors
- Component library infrastructure (tab_nav, badge, stat_card, modal_dialog)
- Supplier and buyer company pages with DaisyUI badges
- Customer detail page with DaisyUI tab navigation ✨ NEW

---

**✅ Completed & Deployed:**

1. **TailwindCSS + DaisyUI CDN Added**
   - Location: `main.py:216-217` in `page_layout` function
   - TailwindCSS for utility classes
   - DaisyUI 4.0 for component styling
   - Deployed: Commit 48e2a39

2. **Component Helpers Created** (main.py:230-326)
   - `tab_nav()` - Tab navigation with HTMX integration
   - `badge()` - Colored badges (neutral, primary, success, warning, error, info, accent, secondary)
   - `stat_card()` - Dashboard statistics cards with icons
   - `modal_dialog()` - Modal dialogs for confirmations
   - All helpers ready for use

3. **Status Badges Migrated**
   - Updated `status_badge()` function to use DaisyUI badges (main.py:432-439)
   - Replaced supplier list badges (main.py:~14091) - ✅ Verified live
   - Replaced buyer company list badges (main.py:~14785) - ✅ Verified live
   - Old CSS classes kept for backward compatibility
   - **Visual Result:** Green "Активен" badges look much cleaner and more modern

4. **Tab Navigation Implementation** ✅
   - **Customer Detail Page** - Converted to DaisyUI tabs (Commit 50bed60, 2026-01-21)
     - Removed 40+ lines of custom CSS (.tabs-nav, .tab-btn styles)
     - Now using `tab_nav()` helper with DaisyUI tabs-lifted component
     - 7 tabs: Общая информация, Адреса, Контакты, Договоры, КП, Спецификации, Запрашиваемые позиции
     - Tab switching works correctly, content loads properly
     - **Verified live:** https://kvotaflow.ru/customers/[customer_id]

   - **Implementation Details:**
     - Changed from custom `Div(cls="tabs-nav")` to `tab_nav()` helper
     - Added `id="tab-content"` wrapper div for HTMX targeting
     - Cleaned up 50+ lines of redundant code
     - More maintainable and consistent with DaisyUI design system

**Final Verification (2026-01-21 09:30 UTC):**

- ✅ CI/CD passed (commit 50bed60)
- ✅ Deploy succeeded
- ✅ Customer detail tabs working live
- ✅ Tab switching functional
- ✅ Content rendering correctly in each tab
- ✅ DaisyUI tab-lifted styling applied

---

**📊 Phase 2 Results:**

**Code Reduction:**

- Removed ~50 lines of custom CSS
- Replaced with 4 reusable component helpers
- Customer detail page: -51 lines of code

**Benefits Delivered:**

- Consistent design system across the app
- Modern, professional UI components
- Easier to maintain (DaisyUI handles updates)
- HTMX-ready for dynamic loading
- Reduced technical debt

**Time Invested:** ~3 hours total

- Initial setup + badges: ~1.5 hours
- Tab implementation: ~1.5 hours

---

**⏳ Optional Future Enhancements:**

These can be done in future sessions if needed:

- Apply `tab_nav()` to Quotes Detail page (similar structure)
- Apply `tab_nav()` to Suppliers Detail page (if tabs are added)
- Convert more status badges throughout the app
- Add `modal_dialog()` for delete confirmations

**Phase 2 is COMPLETE.** All core goals achieved and deployed to production.

---

### 🐛 Phase 2 Bug Fixes (2026-01-21)

**Two critical issues were discovered after Phase 2 deployment:**

#### Bug #1: Tab Navigation Duplication ✅ FIXED

**Problem:** When clicking tabs like "Адреса" on customer detail page, the full page HTML (including navigation bar, header, tabs) was loading inside the tab-content div, causing duplicate navigation and tabs.

**Root Cause:** HTMX was using regular href links that loaded full page HTML instead of just content fragments.

**Solution (Commit: TBD):**

- Added `request` parameter to route handler (main.py:16444)
- Check for `HX-Request` header to detect HTMX requests
- Return only `tab_content` for HTMX requests
- Return full `page_layout()` only for initial page loads
- Removed duplicate `id="tab-content"` from all 7 individual tab content Divs

**Verification:** ✅ Tested live at https://kvotaflow.ru/customers/[customer_id] - tabs switch correctly without duplication

---

#### Bug #2: Inconsistent Stat Card Styling ✅ FIXED

**Problem:** Stat cards had inconsistent appearance:

- Different emoji sizes (📊💰📄💎)
- Random value colors (blue, green, purple, orange, cyan, red)
- Inconsistent padding and borders
- No unified design system

**Solution (Commit: TBD):**

- Replaced all custom stat card Divs with `stat_card()` DaisyUI helper
- Applied DaisyUI's `stats` component with consistent styling
- Used `stats-vertical lg:stats-horizontal` for responsive layout
- Customer detail page (main.py:16912-16934): 4 stat cards
- User profile page (main.py:17931-17961): 6 stat cards

**Code Reduction:**

- Removed 83 lines of custom stat card code
- Replaced with 47 lines using DaisyUI helpers
- Net reduction: -36 lines

**Verification:** ✅ Tested live at https://kvotaflow.ru/customers/[customer_id] - all stat cards now have uniform appearance with consistent DaisyUI styling

---

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

### Phase 4: Searchable Dropdowns - Datalist Pattern ✅ COMPLETED (2026-01-21)

**Goal:** Simplify searchable dropdown UX by using native HTML5 datalist instead of dual-element pattern

**Problem Identified:**

User feedback: "зачем отдельное окошко для поиска?" (why separate search box?)

Old pattern had TWO separate elements:

1. Search textbox "Поиск компании..." for typing query
2. Separate combobox dropdown "Выберите компанию..." for selecting result

This created confusion - users didn't immediately understand they needed to type in one field to populate another.

**Solution Implemented:**

Refactored all searchable dropdowns to use HTML5 datalist pattern:

```python
# Single input with native browser autocomplete
Input(
    type="text",
    list="datalist-id",
    placeholder="Начните печатать название...",
    hx_get="/api/companies/search",
    hx_trigger="input changed delay:300ms",
    hx_target="#datalist-id"
)
Datalist(id="datalist-id")
Input(type="hidden", name="company_id")  # Stores UUID

# Minimal JS to sync visible name with hidden UUID (5-10 lines)
Script("""
    input.addEventListener('input', () => {
        const option = datalist.options.find(opt => opt.value === input.value);
        if (option) hidden.value = option.getAttribute('data-id');
    });
""")
```

**Benefits:**

- **Simpler UX:** User types where they select (single mental model)
- **Native behavior:** Browser handles autocomplete natively
- **Zero dependencies:** No JavaScript libraries required
- **Minimal JS:** Only 5-10 lines for UUID sync
- **Accessible:** Works with keyboard navigation out of the box

**Design Guideline:**

> **Searchable Dropdowns Rule:**
>
> Always use single HTML5 datalist element for searchable dropdowns.
> Never create separate search textbox + results combobox.
> Single field is more intuitive - user types where they select.

**Implementation:**

- Refactored 4 dropdown functions: `buyer_company_dropdown`, `seller_company_dropdown`, `supplier_dropdown`, `location_dropdown`
- Updated 4 API endpoints to return `<option data-id="uuid">` format for datalist
- Commit: 31b706e
- Deployed to production

**Files Modified:**

- `main.py` - All dropdown functions and search API endpoints

---

---

## Phase 5: Unified Table Design System (2026-01-22) ✅ IN PROGRESS

**Reference:** [Livento CRM Dashboard](https://www.behance.net/gallery/239045803/CRM-Dashboard-UI-UX-Branding-Case-Study)

**Status:** 🟡 In Progress | First table migrated: `/quotes`

**Problem:** Tables throughout the application have inconsistent styling:
- Different border styles
- Inconsistent header backgrounds
- Mixed status badge colors
- Various padding/spacing
- No unified hover states

### Design Principles

1. **Clean & Minimal** - White backgrounds, subtle borders
2. **Consistent Spacing** - Same padding across all tables
3. **Clear Hierarchy** - Headers distinct from data rows
4. **Status Badges** - Unified color palette for statuses
5. **Action Alignment** - Actions always on the right
6. **Responsive** - Tables scroll horizontally on mobile

### Unified Table CSS

```css
/* ========== Unified Table Styles ========== */

/* Table Container - adds shadow and rounded corners */
.table-container {
    background: var(--bg-card);
    border-radius: 12px;
    border: 1px solid var(--border-color);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    margin: 1.5rem;      /* Fixed spacing from edges */
    margin-top: 1rem;    /* Less space from top */
}

/* Base Table Styles */
.unified-table {
    width: 100%;
    min-width: 800px;    /* Minimum width for readability - enables horizontal scroll */
    border-collapse: collapse;
    font-size: 0.875rem;
}

/* Table Header Bar - search, filters, actions */
.table-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.25rem;
    border-bottom: 1px solid var(--border-color);
    background: var(--bg-card);
    gap: 1rem;
    flex-wrap: wrap;
}

.table-header-left {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.table-header-right {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

/* Search Input in Table Header */
.table-search {
    min-width: 250px;
    padding: 0.5rem 1rem;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    font-size: 0.875rem;
    background: var(--bg-primary);
}

.table-search:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

/* Base Table Styles */
.unified-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
}

/* Table Header */
.unified-table thead {
    background: #f8fafc;
    border-bottom: 1px solid var(--border-color);
}

.unified-table th {
    padding: 0.875rem 1rem;
    text-align: left;
    font-weight: 600;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-secondary);
    white-space: nowrap;
}

/* Right-align numeric columns */
.unified-table th.col-number,
.unified-table td.col-number,
.unified-table th.col-money,
.unified-table td.col-money {
    text-align: right;
}

/* Center-align action columns */
.unified-table th.col-actions,
.unified-table td.col-actions {
    text-align: center;
    width: 100px;
}

/* Table Body */
.unified-table tbody tr {
    border-bottom: 1px solid var(--border-color);
    transition: background-color 0.15s;
}

.unified-table tbody tr:last-child {
    border-bottom: none;
}

.unified-table tbody tr:hover {
    background: #f8fafc;
}

.unified-table td {
    padding: 0.875rem 1rem;
    color: var(--text-primary);
    vertical-align: middle;
}

/* Clickable row */
.unified-table tbody tr.clickable-row {
    cursor: pointer;
}

.unified-table tbody tr.clickable-row:hover {
    background: rgba(59, 130, 246, 0.05);
}

/* Status Badges - Unified Color Palette */
.status-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.25rem 0.625rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 500;
    white-space: nowrap;
}

/* Success - green */
.status-success {
    background: #dcfce7;
    color: #166534;
}

/* Warning - yellow/orange */
.status-warning {
    background: #fef3c7;
    color: #92400e;
}

/* Error/Danger - red */
.status-error {
    background: #fee2e2;
    color: #991b1b;
}

/* Info - blue */
.status-info {
    background: #dbeafe;
    color: #1e40af;
}

/* Neutral - gray */
.status-neutral {
    background: #f3f4f6;
    color: #4b5563;
}

/* New/Primary - blue accent */
.status-new {
    background: #eff6ff;
    color: #2563eb;
}

/* In Progress - purple */
.status-progress {
    background: #f3e8ff;
    color: #7c3aed;
}

/* Table Footer - pagination */
.table-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.875rem 1.25rem;
    border-top: 1px solid var(--border-color);
    background: #f8fafc;
    font-size: 0.875rem;
}

.table-pagination {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.table-pagination button {
    padding: 0.375rem 0.75rem;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--bg-card);
    cursor: pointer;
    font-size: 0.875rem;
}

.table-pagination button:hover:not(:disabled) {
    background: #f3f4f6;
}

.table-pagination button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.table-pagination .current-page {
    padding: 0.375rem 0.75rem;
    background: var(--accent);
    color: white;
    border-radius: 6px;
    font-weight: 500;
}

/* Empty State */
.table-empty {
    padding: 3rem 1rem;
    text-align: center;
    color: var(--text-muted);
}

.table-empty-icon {
    font-size: 2.5rem;
    margin-bottom: 0.75rem;
    opacity: 0.5;
}

.table-empty-text {
    font-size: 0.9375rem;
}

/* Action Buttons */
.table-action-btn {
    padding: 0.375rem;
    border: none;
    background: transparent;
    border-radius: 6px;
    cursor: pointer;
    color: var(--text-secondary);
    transition: all 0.15s;
}

.table-action-btn:hover {
    background: #f3f4f6;
    color: var(--text-primary);
}

.table-action-btn.danger:hover {
    background: #fee2e2;
    color: #dc2626;
}

/* Responsive Table Wrapper */
.table-responsive {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
}

@media (max-width: 768px) {
    .table-header {
        flex-direction: column;
        align-items: stretch;
    }

    .table-search {
        min-width: 100%;
    }

    .unified-table th,
    .unified-table td {
        padding: 0.625rem 0.75rem;
    }
}
```

### Python Helper Functions

```python
def unified_table(headers, rows, id=None, cls="", empty_message="Нет данных"):
    """
    Creates a unified table with consistent styling.

    Args:
        headers: List of tuples (label, class) e.g. [("Название", ""), ("Сумма", "col-money")]
        rows: List of Tr elements
        id: Optional table ID
        cls: Additional CSS classes
        empty_message: Message when no rows

    Example:
        unified_table(
            headers=[
                ("IDN", ""),
                ("Клиент", ""),
                ("Сумма", "col-money"),
                ("Статус", ""),
                ("", "col-actions")
            ],
            rows=[
                Tr(
                    Td("Q-001"),
                    Td("ООО Рога и Копыта"),
                    Td("$50,000", cls="col-money"),
                    Td(status_badge("Активен", "success")),
                    Td(A(icon("eye"), href="/view"), cls="col-actions")
                )
            ]
        )
    """
    if not rows:
        return Div(
            Div("📋", cls="table-empty-icon"),
            Div(empty_message, cls="table-empty-text"),
            cls="table-empty"
        )

    return Table(
        Thead(Tr(*[Th(label, cls=col_cls) for label, col_cls in headers])),
        Tbody(*rows),
        id=id,
        cls=f"unified-table {cls}"
    )

def table_container(*children, header_left=None, header_right=None, footer=None):
    """
    Wraps table in styled container with optional header and footer.

    Example:
        table_container(
            header_left=Input(placeholder="Поиск...", cls="table-search"),
            header_right=A("+ Добавить", cls="btn btn-primary", href="/new"),
            unified_table(...),
            footer=table_pagination(current=1, total=5)
        )
    """
    parts = []

    if header_left or header_right:
        parts.append(Div(
            Div(header_left or "", cls="table-header-left"),
            Div(header_right or "", cls="table-header-right"),
            cls="table-header"
        ))

    parts.append(Div(*[c for c in children if c], cls="table-responsive"))

    if footer:
        parts.append(Div(footer, cls="table-footer"))

    return Div(*parts, cls="table-container")

def status_badge(text, status="neutral"):
    """
    Creates a status badge with unified colors.

    status: success, warning, error, info, neutral, new, progress
    """
    return Span(text, cls=f"status-badge status-{status}")
```

### Status Badge Color Guide

| Status | CSS Class | Use Case | Color |
|--------|-----------|----------|-------|
| Success | `status-success` | Активен, Оплачено, Завершено | Green |
| Warning | `status-warning` | Ожидает, На проверке | Yellow |
| Error | `status-error` | Отменено, Просрочено | Red |
| Info | `status-info` | В работе, Информация | Blue |
| Neutral | `status-neutral` | Черновик, Неактивен | Gray |
| New | `status-new` | Новый, Новая заявка | Light Blue |
| Progress | `status-progress` | В процессе, Согласование | Purple |

### Example Implementation

```python
# Quotes List with Unified Table Style
table_container(
    header_left=Div(
        Input(type="text", placeholder="Поиск по номеру или клиенту...",
              cls="table-search", hx_get="/quotes/search", hx_trigger="keyup changed delay:300ms"),
        Select(
            Option("Все статусы", value=""),
            Option("Активные", value="active"),
            Option("Черновики", value="draft"),
            cls="table-filter"
        ),
        cls="table-header-left"
    ),
    header_right=A(
        icon("plus"), " Новый КП",
        href="/quotes/new", cls="btn btn-primary"
    ),
    unified_table(
        headers=[
            ("IDN", ""),
            ("Клиент", ""),
            ("Дата", ""),
            ("Сумма", "col-money"),
            ("Профит", "col-money"),
            ("Статус", ""),
            ("", "col-actions")
        ],
        rows=[
            Tr(
                Td(A("Q-202601-0014", href=f"/quotes/{q.id}")),
                Td(q.customer_name),
                Td(q.created_at.strftime("%d.%m.%Y")),
                Td(f"${q.total:,.0f}", cls="col-money"),
                Td(f"${q.profit:,.0f}", cls="col-money"),
                Td(status_badge(q.status_label, q.status_type)),
                Td(
                    A(icon("eye"), href=f"/quotes/{q.id}", cls="table-action-btn"),
                    A(icon("pencil"), href=f"/quotes/{q.id}/edit", cls="table-action-btn"),
                    cls="col-actions"
                ),
                cls="clickable-row",
                onclick=f"window.location='/quotes/{q.id}'"
            )
            for q in quotes
        ],
        empty_message="Нет котировок"
    ),
    footer=Div(
        Span(f"Показано {len(quotes)} из {total_count}"),
        table_pagination(current_page, total_pages)
    )
)
```

### Tables to Migrate

**Priority 1 (High Traffic):**
- [x] `/quotes` - Quotes list ✅ DONE (2026-01-22)
- [ ] `/customers` - Customers list
- [ ] `/finance?tab=erps` - ERPS registry (already has custom styling)
- [ ] `/deals` - Deals list

**Priority 2 (Medium):**
- [ ] `/suppliers` - Suppliers list
- [ ] `/admin?tab=users` - Users management
- [ ] Customer detail tabs (КП, Спецификации, Контакты)

**Priority 3 (Low):**
- [ ] Quote detail - Items table
- [ ] Procurement workspace tables
- [ ] Report tables

### Migration Strategy

1. Add unified table CSS to APP_STYLES
2. Create helper functions (`unified_table`, `table_container`, `status_badge`)
3. Migrate one table at a time, starting with `/quotes`
4. Test each migration before proceeding
5. Remove old table-specific CSS as tables are migrated

**Estimated Effort:** 4-6 hours for all tables
**Result:** Consistent, professional table UI across entire application

---

## Summary

**Phase 1 (✅ DONE):** PicoCSS foundation - instant visual upgrade
**Phase 2 (✅ DONE):** DaisyUI components - tabs, badges, advanced UI
**Phase 3 (⏳ TODO):** Icons & animations - polish and professional feel
**Phase 4 (✅ DONE):** Searchable dropdowns - datalist pattern
**Phase 5 (🟡 IN PROGRESS):** Unified table design - consistent table styling (quotes done)

**Total Effort:** ~10-12 hours for all phases
**Result:** Modern, professional, production-ready UI
