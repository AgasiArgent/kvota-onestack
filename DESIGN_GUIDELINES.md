# OneStack Design System

**Last Updated:** 2026-02-02
**Audit Status:** Complete (56 pages updated)

A practical guide for building consistent, polished UI in OneStack.

---

## Quick Reference

### CSS Classes

| Class | Purpose |
|-------|---------|
| `card-elevated` | Cards with gradient background + shadow |
| `table-enhanced` | Tables with styled headers, zebra rows, hover |
| `table-enhanced-container` | Wrapper for table-enhanced |
| `handsontable-container` | Wrapper for Handsontable spreadsheets |
| `status-badge-v2 status-badge-v2--{variant}` | Status badges |

### Python Helpers

| Function | Purpose |
|----------|---------|
| `icon(name, size)` | Lucide SVG icon |
| `btn(label, variant, icon_name)` | Standard button |
| `btn_link(label, href, variant)` | Link styled as button |
| `btn_icon(icon_name, variant)` | Icon-only button |
| `status_badge_v2(status)` | Status badge with Russian labels |

---

## Core Principles

### 1. Compact & Efficient
- Tight padding (12-16px), not spacious
- Dense but readable layouts
- Multi-column where appropriate
- No excessive whitespace

### 2. Consistent Typography
- **Labels:** 11px, uppercase, gray (#64748b), letter-spacing 0.05em
- **Values:** 14px, normal weight
- **Headers:** 14-16px, 600 weight

### 3. Subtle Visual Hierarchy
- Gradient backgrounds for depth (not flat colors)
- Light shadows (0 2px 8px rgba(0,0,0,0.04))
- Blue accent color (#3b82f6)

---

## Cards

### Elevated Card

```python
Div(
    H2("Section Title", style="font-size: 14px; font-weight: 600; margin: 0 0 12px 0;"),
    # Content here
    cls="card-elevated",
    style="padding: 16px;"  # Optional: adjust padding
)
```

**CSS Variables:**
```css
.card-elevated {
    background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
    border-radius: 12px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
```

### Card with Accent Border

```python
Div(
    # Content
    cls="card-elevated",
    style="border-left: 4px solid #3b82f6; padding: 16px;"
)
```

### Page Header Card

Used at the top of detail/form pages with gradient background, icon, and title.

```python
header_style = """
    background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
    border-radius: 12px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    padding: 20px 24px;
    margin-bottom: 20px;
"""

Div(
    # Back link
    A(icon("arrow-left", size=14), " К списку", href="/items",
      style="font-size: 13px; color: #64748b; text-decoration: none; display: inline-flex; align-items: center; gap: 4px; margin-bottom: 12px;"),
    # Title row with icon and badge
    Div(
        icon("briefcase", size=24, style="color: #3b82f6;"),
        Span("Название сущности", style="font-size: 20px; font-weight: 700; color: #1e293b;"),
        status_badge_v2("approved"),
        style="display: flex; align-items: center; gap: 12px;"
    ),
    style=header_style
)
```

**Theme colors for header icons:**
- Blue (#3b82f6): Default, finance, logistics
- Green (#10b981): Success states, locations
- Amber (#f59e0b): Warnings, edit forms
- Purple (#8b5cf6): Customs
- Red (#dc2626): Errors, unauthorized

**Accent colors by department:**
- Approvals: `#f59e0b` (orange)
- Procurement: `#fbbf24` (amber)
- Logistics: `#3b82f6` (blue)
- Customs: `#8b5cf6` (purple)
- Quote Control: `#ec4899` (pink)
- Specifications: `#6366f1` (indigo)
- Finance: `#10b981` (green)
- Sales: `#f97316` (orange)

---

## Tables

### Enhanced Table

```python
Div(
    Table(
        Thead(Tr(
            Th("КП #"),
            Th("Клиент"),
            Th("Сумма", cls="col-money"),
            Th("Действие")
        )),
        Tbody(
            Tr(
                Td("Q-202601-0001"),
                Td("Test Company"),
                Td("₽50,000", cls="col-money"),
                Td(A("Открыть", href="/quotes/123"))
            ),
            # More rows...
        ),
        cls="table-enhanced"
    ),
    cls="table-enhanced-container"
)
```

**Features:**
- Gradient header with 11px uppercase labels
- Zebra striping (subtle blue tint on even rows)
- Hover effect on rows
- Blue link styling

**Column classes:**
- `col-money` - Right-aligned for numbers/currency
- `col-actions` - Center-aligned for action buttons

---

## Status Badges

### Using status_badge_v2()

```python
from main import status_badge_v2

# Automatic label mapping
status_badge_v2("pending_procurement")  # → "Закупки" (amber)
status_badge_v2("pending_logistics")    # → "Логистика" (blue)
status_badge_v2("approved")             # → "Одобрено" (green)

# Custom label
status_badge_v2("pending_procurement", custom_label="На закупке")
```

### Status Mapping

| Database Value | Russian Label | Variant |
|----------------|---------------|---------|
| `draft` | Черновик | neutral |
| `pending_procurement` | Закупки | pending |
| `pending_logistics` | Логистика | info |
| `pending_customs` | Таможня | purple |
| `pending_quote_control` | Контроль КП | warning |
| `pending_spec_control` | Спецификации | info |
| `pending_sales_review` | Проверка | warning |
| `pending_approval` | Согласование | warning |
| `approved` | Одобрено | success |
| `rejected` | Отклонено | error |
| `deal` | Сделка | success |

### Badge Variants CSS

```css
.status-badge-v2--pending  { background: linear-gradient(135deg, #fef3c7, #fde68a); color: #92400e; }
.status-badge-v2--success  { background: linear-gradient(135deg, #d1fae5, #a7f3d0); color: #065f46; }
.status-badge-v2--info     { background: linear-gradient(135deg, #dbeafe, #bfdbfe); color: #1e40af; }
.status-badge-v2--warning  { background: linear-gradient(135deg, #fed7aa, #fdba74); color: #9a3412; }
.status-badge-v2--error    { background: linear-gradient(135deg, #fecaca, #fca5a5); color: #991b1b; }
.status-badge-v2--purple   { background: linear-gradient(135deg, #e9d5ff, #d8b4fe); color: #6b21a8; }
.status-badge-v2--neutral  { background: linear-gradient(135deg, #f1f5f9, #e2e8f0); color: #475569; }
```

---

## Buttons

### Standard Buttons

```python
btn("Сохранить", variant="primary", icon_name="save", type="submit")
btn("Одобрить", variant="success", icon_name="check")
btn("Удалить", variant="danger", icon_name="trash-2")
btn("Отмена", variant="secondary")
btn("Добавить", variant="ghost", icon_name="plus")
```

### Link Buttons

```python
btn_link("Новый КП", href="/quotes/new", icon_name="plus")
btn_link("Назад", href="/quotes", variant="secondary", icon_name="arrow-left")
```

### Icon-Only Buttons

```python
btn_icon("edit", title="Редактировать")
btn_icon("trash-2", variant="danger", title="Удалить")
```

### Variants

| Variant | Use Case |
|---------|----------|
| `primary` | Main action (Save, Submit) |
| `secondary` | Cancel, Back |
| `success` | Approve, Complete |
| `danger` | Delete, Reject |
| `ghost` | Toolbar actions |

---

## Icons (Lucide)

### Usage

```python
icon("save", size=16)           # In buttons
icon("inbox", size=24)          # In headers
icon("check-circle", size=40)   # Large decorative
```

### Common Icons

| Purpose | Icon Name |
|---------|-----------|
| Save | `save` |
| Edit | `edit` |
| Delete | `trash-2` |
| View | `eye` |
| Add | `plus` |
| Back | `arrow-left` |
| Check/Success | `check-circle` |
| Warning | `alert-triangle` |
| Info | `info` |
| User | `user` |
| Users | `users` |
| Package | `package` |
| Truck | `truck` |
| Wallet | `wallet` |
| File | `file-text` |
| Clock | `clock` |

Full catalog: https://lucide.dev/icons

---

## Handsontable Styling

### Wrapping Handsontable

```python
Div(
    Div(id="spreadsheet-container", style="width: 100%; height: 400px;"),
    cls="handsontable-container"
)
```

**Automatic styling applied:**
- Gradient header row
- Zebra striping
- Hover effects
- Read-only cells have gray background
- Rounded container with shadow

---

## Page Layouts

### Task Section (Dashboard/Tasks)

```python
Div(
    H2(icon("truck", size=20), f" Логистика: ожидают данных ({count})",
       style="font-size: 14px; font-weight: 600; color: #1e293b; margin: 0 0 12px 0; display: flex; align-items: center; gap: 8px;"),
    Div(
        Table(
            Thead(Tr(Th("КП #"), Th("Клиент"), Th("Создано"), Th("Действие"))),
            Tbody(*rows),
            cls="table-enhanced"
        ),
        cls="table-enhanced-container"
    ),
    A("Открыть раздел Логистика →", href="/logistics",
      style="display: inline-block; margin-top: 12px; font-size: 13px; color: #3b82f6; font-weight: 500;"),
    cls="card-elevated",
    style="border-left: 4px solid #3b82f6; padding: 16px;"
)
```

### Stat Cards Grid

```python
Div(
    Div(
        Div("4", style="font-size: 20px; font-weight: 700; color: #4338ca;"),
        Div("КП ДЛЯ СОЗДАНИЯ СПЕЦ.", style="font-size: 11px; text-transform: uppercase; color: #64748b; letter-spacing: 0.05em;"),
        style="background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%); padding: 12px; border-radius: 8px; text-align: center;"
    ),
    # More stat cards...
    style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;"
)
```

### Two-Column Layout

Used for detail pages with info on left, actions/form on right.

```python
# Responsive two-column grid
Div(
    # Left column - info cards
    Div(
        Div(..., cls="card-elevated", style="padding: 16px; margin-bottom: 16px;"),
        Div(..., cls="card-elevated", style="padding: 16px;"),
    ),
    # Right column - actions/form
    Div(
        Div(..., cls="card-elevated", style="padding: 16px;"),
    ),
    style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;"
)
```

### Four-Column Stats Grid

Used for summary statistics at top of pages.

```python
stats_card = """
    background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
    border-radius: 10px;
    border: 1px solid #e2e8f0;
    padding: 16px;
    text-align: center;
"""

Div(
    Div(
        Div("12", style="font-size: 24px; font-weight: 700; color: #3b82f6;"),
        Div("ВСЕГО", style="font-size: 11px; text-transform: uppercase; color: #64748b; letter-spacing: 0.05em; margin-top: 4px;"),
        style=stats_card
    ),
    Div(
        Div("₽1.2M", style="font-size: 24px; font-weight: 700; color: #10b981;"),
        Div("ДОХОД", style="font-size: 11px; text-transform: uppercase; color: #64748b; letter-spacing: 0.05em; margin-top: 4px;"),
        style=stats_card
    ),
    # More stats...
    style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px;"
)
```

### Compact Form Layout (Calculate Page Style)

```python
card_style = """
    background: linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%);
    border-radius: 12px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    padding: 16px;
    margin-bottom: 12px;
"""

input_row_style = "display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid #f1f5f9;"
field_label_style = "font-size: 13px; color: #64748b; width: 140px; font-weight: 500;"
field_input_style = "width: 90px; padding: 6px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; text-align: right;"

Div(
    Div(icon("building-2", size=16), " КОМПАНИЯ И УСЛОВИЯ",
        style="font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 0.05em; margin-bottom: 12px; display: flex; align-items: center; gap: 6px;"),
    Div(
        Span("Юрлицо продавца", style=field_label_style),
        Select(..., style="flex: 1; padding: 6px 10px; border: 1px solid #e2e8f0; border-radius: 6px;"),
        style=input_row_style
    ),
    # More rows...
    style=card_style
)
```

---

## Inline Styles Reference

### Labels
```python
style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; font-weight: 600;"
```

### Section Headers (with icon)

The standard pattern for section headers inside cards.

```python
Div(
    icon("package", size=14, style="color: #64748b;"),
    " ИНФОРМАЦИЯ О ТОВАРАХ",
    style="font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px; display: flex; align-items: center; gap: 6px;"
)
```

### Section Headers (card title)
```python
style="font-size: 14px; font-weight: 600; color: #1e293b; margin: 0 0 12px 0; display: flex; align-items: center; gap: 8px;"
```

### Form Row
```python
style="display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid #f1f5f9;"
```

### Compact Input
```python
style="width: 90px; padding: 6px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; text-align: right;"
```

### Link CTA
```python
style="display: inline-block; margin-top: 12px; font-size: 13px; color: #3b82f6; font-weight: 500;"
```

---

## Don'ts

1. **Don't use emoji** - Always use Lucide icons
2. **Don't use !important** - Fix specificity properly
3. **Don't use inline colors** - Use CSS variables or established patterns
4. **Don't create spacious layouts** - Keep things compact
5. **Don't show raw database values** - Use status_badge_v2() for mapping
6. **Don't use plain `<table>`** - Wrap with table-enhanced classes

---

## Color Palette

### Primary
- Blue accent: `#3b82f6`
- Blue hover: `#2563eb`

### Backgrounds
- Card gradient: `linear-gradient(135deg, #fafbfc 0%, #f4f5f7 100%)`
- Success gradient: `linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%)`

### Text
- Primary: `#1e293b`
- Secondary: `#64748b`
- Muted: `#94a3b8`

### Borders
- Default: `#e2e8f0`
- Light: `#f1f5f9`

### Status Colors
- Success: `#10b981` / `#059669`
- Warning: `#f59e0b` / `#d97706`
- Error: `#ef4444` / `#dc2626`
- Info: `#3b82f6` / `#2563eb`

---

## Dark Theme

All CSS uses variables that automatically switch in dark mode:
- `var(--bg-primary)`, `var(--bg-card)`
- `var(--text-primary)`, `var(--text-secondary)`
- `var(--border-color)`
- `var(--accent)`

Cards and tables have `[data-theme="dark"]` variants defined.

---

## Error Pages

### Centered Card (Unauthorized, Not Found)

```python
page_bg_style = """
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
    background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 50%, #f1f5f9 100%);
"""

card_style = """
    background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
    border-radius: 16px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 4px 24px rgba(0,0,0,0.08);
    padding: 48px 40px;
    max-width: 480px;
    text-align: center;
"""

icon_container_style = """
    width: 72px;
    height: 72px;
    background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
    border-radius: 20px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 24px;
    border: 1px solid #fecaca;
"""

Div(
    Div(
        Div(icon("shield-x", size=36, style="color: #dc2626;"), style=icon_container_style),
        H1("Доступ запрещён", style="font-size: 22px; font-weight: 700; color: #1e293b; margin: 0 0 12px 0;"),
        P("Описание ошибки.", style="font-size: 14px; color: #64748b; margin: 0 0 8px 0;"),
        A(icon("arrow-left", size=16), " Вернуться", href="/tasks",
          style="display: inline-flex; align-items: center; gap: 8px; padding: 12px 20px; ..."),
        style=card_style
    ),
    style=page_bg_style
)
```

---

## Gold Standard Pages

Reference these pages when implementing new designs:

| Page | URL | Why |
|------|-----|-----|
| Calculate Page | `/quotes/{id}/calculate` | Compact form layout, section cards |
| Logistics Workspace | `/logistics/{id}` | Workspace with multiple sections |
| Deal Detail | `/finance/{deal_id}` | Two-column layout, stats grid |
| Brand Assignments | `/admin/brands` | List with stats, modern table |
