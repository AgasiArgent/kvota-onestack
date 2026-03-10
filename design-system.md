# OneStack Design System

> Claude Code MUST read this file before any UI work.
> This is the single source of truth for all visual decisions.

## Stack

- **Framework:** FastHTML (Python) — server-rendered HTML
- **CSS Base:** PicoCSS v2
- **Utilities:** Tailwind CDN (play CDN, no config)
- **Components:** DaisyUI v4
- **Interactivity:** HTMX
- **Custom styles:** CSS variables in `APP_STYLES` (main.py, line ~149)

## Principles

1. **Visual hierarchy: size > weight > color** — one element per section gets all three
2. **Design in grayscale first** — color is supplementary, not structural
3. **Constrained scales only** — no arbitrary px/rem/hex values outside this document
4. **Variables over inline** — use `var(--token)` not hardcoded values
5. **No global transitions** — animate only specific properties on specific elements
6. **Compact by default** — this is a data-heavy CRM, not a marketing site

---

## Color Palette

### Primary: Blue

| Token | Hex | Usage |
|-------|-----|-------|
| `--blue-50` | `#eff6ff` | Tinted backgrounds, selected row |
| `--blue-100` | `#dbeafe` | Hover backgrounds, active tab bg |
| `--blue-200` | `#bfdbfe` | Borders on active elements |
| `--blue-300` | `#93c5fd` | Disabled primary elements |
| `--blue-400` | `#60a5fa` | Links on hover |
| `--blue-500` | `#3b82f6` | **Primary accent** — buttons, links, active states |
| `--blue-600` | `#2563eb` | Button hover, strong emphasis |
| `--blue-700` | `#1d4ed8` | Active/pressed states |
| `--blue-800` | `#1e40af` | Dark emphasis text |
| `--blue-900` | `#1e3a8a` | Headings on colored bg |

### Gray: Slate (blue-tinted)

Standardize on **slate** palette (not gray). The blue tint harmonizes with the blue primary.

| Token | Hex | CSS Variable | Usage |
|-------|-----|-------------|-------|
| `slate-50` | `#f8fafc` | `--bg-page` alt | Page bg, compact input bg |
| `slate-100` | `#f1f5f9` | — | Card hover, table header bg |
| `slate-200` | `#e2e8f0` | `--border-color` | Borders, dividers, input borders |
| `slate-300` | `#cbd5e1` | — | Disabled input borders |
| `slate-400` | `#94a3b8` | `--text-muted` | Placeholder text, icons |
| `slate-500` | `#64748b` | `--text-secondary` | Secondary labels, muted text |
| `slate-600` | `#475569` | — | Body text secondary |
| `slate-700` | `#334155` | — | Body text primary |
| `slate-800` | `#1e293b` | `--text-primary` | Headings, high-contrast text |
| `slate-900` | `#0f172a` | — | Near-black |

### Semantic Colors

| Role | Hex | Usage |
|------|-----|-------|
| Success | `#10b981` | Confirmations, approved states |
| Warning | `#f59e0b` | Alerts, pending states, draft |
| Error | `#ef4444` | Errors, rejected, destructive |
| Info | `#3b82f6` | Informational (same as primary) |

### Status Badge Colors

| Status | Background | Text |
|--------|-----------|------|
| Draft | `#fef3c7` | `#92400e` |
| Sent/In Progress | `#dbeafe` | `#1e40af` |
| Approved | `#d1fae5` | `#065f46` |
| Rejected | `#fee2e2` | `#991b1b` |
| Pending | `#fef3c7` | `#92400e` |
| Cancelled | `#f3f4f6` | `#4b5563` |

**Rule:** Use flat background + dark text for badges (not gradients). Easier to read, lighter visually.

---

## Typography

### Font

**Primary:** Inter — `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`

Load via Google Fonts:
```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">
```

### Type Scale (constrained)

Only these sizes are allowed. No 13px, 15px, 0.7rem, 0.85rem, or other arbitrary values.

| Size | Name | Usage | Weight |
|------|------|-------|--------|
| 11px | `--text-2xs` | Uppercase labels, timestamps | 600 |
| 12px | `--text-xs` | Badges, captions, compact table cells | 400-500 |
| 14px | `--text-sm` | **Base body**, form inputs, table cells, nav links | 400 |
| 16px | `--text-base` | Emphasized body, standalone paragraphs | 400 |
| 18px | `--text-lg` | Card titles, section headings | 600 |
| 20px | `--text-xl` | Page section titles | 600 |
| 24px | `--text-2xl` | Page titles | 700 |

**Rules:**
- Body text base = **14px** (this is a data-dense CRM)
- Headings use `font-weight: 600-700`, body uses `400`
- Line height: `1.25` for headings, `1.5` for body
- Max prose width: `65ch`
- **Letter spacing:** `-0.01em` for headings 20px+, `0.05em` for uppercase labels

### Mapping from current values

| Current (remove) | Map to |
|-------------------|--------|
| 13px | 12px or 14px |
| 15px | 14px or 16px |
| 0.7rem (11.2px) | 11px |
| 0.75rem (12px) | 12px |
| 0.8rem (12.8px) | 12px |
| 0.8125rem (13px) | 14px |
| 0.85rem (13.6px) | 14px |
| 0.875rem (14px) | 14px |
| 0.9rem (14.4px) | 14px |
| 0.9375rem (15px) | 14px or 16px |
| 1rem (16px) | 16px |
| 1.125rem (18px) | 18px |
| 1.25rem (20px) | 20px |
| 1.5rem (24px) | 24px |
| 1.75rem (28px) | 24px |
| 2rem (32px) | 24px |

---

## Spacing Scale

| Value | Name | Usage |
|-------|------|-------|
| 2px | — | Borders, outlines only |
| 4px | `xs` | Icon gaps, tight inline elements |
| 6px | `sm` | Compact badge padding, chip gaps |
| 8px | `md` | List items, compact card padding, form field vertical gap |
| 12px | `lg` | Standard card padding, form group gap |
| 16px | `xl` | Comfortable card padding, between components |
| 20px | `2xl` | Section gap within a card |
| 24px | `3xl` | Between cards, section spacing |
| 32px | `4xl` | Between page sections |
| 48px | `5xl` | Large page margins |

**Rules:**
- **No arbitrary spacing.** If a value doesn't appear in this table, don't use it.
- Prefer `8px` and `12px` for most internal padding (compact CRM feel).
- Use `16px` or `24px` for card padding (depending on content density).
- Gap between form label and input: `4px`
- Gap between form fields: `12px`
- Gap between form sections: `24px`

---

## Component Patterns

### Buttons (BEM system — `.btn`)

The project uses a BEM button system defined in APP_STYLES. **Always use `.btn` classes, never raw `<button>` without a class.**

| Variant | Class | Look | Usage |
|---------|-------|------|-------|
| Primary | `.btn.btn--primary` | **Blue fill** (`#3b82f6`), white text | Main actions (Сохранить, Передать) |
| Secondary | `.btn.btn--secondary` | White + slate border | Secondary actions (Отмена, Назад) |
| Success | `.btn.btn--success` | White + green border, green fill on hover | Confirmations (Одобрить, Подтвердить) |
| Danger | `.btn.btn--danger` | White + red border, red fill on hover | Destructive (Удалить, Отклонить) |
| Ghost | `.btn.btn--ghost` | Transparent, hover bg | Toolbar/inline (Добавить, Загрузить) |

| Modifier | Class | Usage |
|----------|-------|-------|
| Small | `.btn--sm` | Inline, table actions |
| Large | `.btn--lg` | Full-page primary CTA |
| Full width | `.btn--full` | Form submit on mobile |
| Icon only | `.btn--icon-only` | Toolbar icon buttons |

**Button rules:**
- Max 1 primary button per card/section
- Destructive buttons always on the right
- Group buttons with `gap: 8px`
- No hover transforms on buttons (remove `translateY`)

### Cards

```
background: var(--bg-card);
border: 1px solid var(--border-color);
border-radius: 8px;
padding: 16px;           /* compact */
padding: 20px 24px;      /* standard */
box-shadow: var(--shadow-subtle);  /* 0 1px 4px rgba(0,0,0,0.06) */
```

**Card rules:**
- **No hover lift effect** — remove `transform: translateY(-4px)` from cards
- No hover border color change
- Cards are static containers, not interactive targets
- Use `cursor: pointer` + subtle `background` change only if the entire card is clickable

### Tables

```
Header:  background: #f8fafc; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b;
Cells:   font-size: 14px; padding: 8px 12px; color: #1e293b;
Rows:    border-bottom: 1px solid #e2e8f0;
Hover:   background: #f8fafc; (subtle, no transform)
```

**Table rules:**
- Headers always uppercase, smaller than body
- No zebra stripes (use hover instead)
- Compact padding: `8px 12px`
- Date columns: first or second column
- Status columns: use badge, not plain text
- Action columns: right-aligned, ghost buttons

### Forms

```
Label:   font-size: 12px; font-weight: 500; color: #64748b; margin-bottom: 4px;
Input:   height: 36px; padding: 8px 12px; font-size: 14px; border: 1px solid #e2e8f0; border-radius: 6px;
Focus:   border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59,130,246,0.1);
Group:   gap between fields: 12px; gap between sections: 24px;
```

### Badges

```
padding: 2px 8px;
font-size: 12px;
font-weight: 500;
border-radius: 4px;
background: {semantic flat color};
color: {semantic dark text};
```

**No gradients on badges.** Use flat bg from Status Badge Colors table above.

### Sidebar

Keep the current sidebar structure. Key tokens:
- Width: `260px` expanded, `60px` collapsed
- Background: `#ffffff` (light) / dark theme variant
- Active item: `background: rgba(59, 130, 246, 0.1); color: #3b82f6;`
- Font size: `14px`

---

## Animations & Transitions

### Removed (performance)

```css
/* REMOVED — was causing performance issues */
/* * { transition: all 0.2s ease-in-out; } */
```

### Allowed transitions (opt-in only)

```css
/* Only these properties may be animated */
.transition-colors { transition: color 0.15s ease, background-color 0.15s ease, border-color 0.15s ease; }
.transition-opacity { transition: opacity 0.15s ease; }
.transition-shadow { transition: box-shadow 0.15s ease; }
```

**Rules:**
- No `transform: translateY()` on hover — cards don't lift, buttons don't bounce
- No `transition: all` — always specify the exact property
- Max transition duration: `0.2s`
- Allowed animations: loading spinners, toast slide-in, modal fade

---

## Layout

### Page structure

```
[Sidebar 260px] | [Main Content max-width: 1200px, padding: 24px]
```

### Responsive breakpoints

| Name | Width | Behavior |
|------|-------|----------|
| `sm` | ≤640px | Stack columns, full-width cards |
| `md` | ≤1024px | Collapse sidebar, 2-col grid |
| `lg` | >1024px | Full layout, sidebar visible |

### Content width

- Main content: `max-width: 1200px`
- Forms: `max-width: 600px` (single column)
- Tables: full width of content area
- Prose text: `max-width: 65ch`

---

## Icons

Use Lucide icons (already available via HTML SVG). Consistent sizing:
- Inline with text: `16px` (width/height)
- Section headers: `20px`
- Page headers: `24px`
- Standalone/decorative: `32px` or `48px`

---

## Do NOT

1. ❌ Use hex colors not in this palette
2. ❌ Use font sizes not in the type scale
3. ❌ Use spacing values not in the spacing scale
4. ❌ Add `transition: all` anywhere
5. ❌ Add `transform: translateY()` on hover
6. ❌ Use `!important` (fix specificity instead)
7. ❌ Add gradient backgrounds to badges
8. ❌ Use inline `style=` for colors/fonts/spacing (use CSS classes or variables)
9. ❌ Mix `rem` and `px` for the same property type (use `px` for this project)
10. ❌ Use Manrope font (migrated to Inter)
