# OneStack Design System

> Claude Code MUST read this file before any UI work.
> This is the single source of truth for all visual decisions.
> **Priority:** This file overrides plugin aesthetics (colors/fonts/spacing). Plugin creativity applies to layout/UX only.

## Stack

- **Framework:** Next.js 15 (App Router) — migrating from FastHTML
- **CSS:** Tailwind CSS v4
- **Components:** shadcn/ui
- **Icons:** Lucide React (no emoji as icons)
- **Font:** Plus Jakarta Sans (Google Fonts)

## Principles

1. **Visual hierarchy: size > weight > color** — one element per section gets all three
2. **Design in grayscale first** — color is supplementary, not structural
3. **Constrained scales only** — no arbitrary px/rem/hex values outside this document
4. **CSS variables** — use semantic tokens, never hardcoded hex in components
5. **One primary CTA per section** — secondary/tertiary actions visually subordinate
6. **Comfortable density by default** — compact mode opt-in for power users
7. **Warm, not cold** — backgrounds are cream-tinted, grays are warm stone, not blue-gray

---

## Color Palette: Slate & Copper

### Brand Identity

A warm, premium palette that combines **stone/slate neutrals** with **copper/burnt orange accents**. Inspired by natural materials — leather, stone, warm metal. Professional but human. Completely distinct from standard blue SaaS.

### Light Mode

| Token             | Hex       | OKLCH                  | Usage                                      |
| ----------------- | --------- | ---------------------- | ------------------------------------------ |
| `--primary`       | `#57534E` | `oklch(0.41 0.01 55)`  | Sidebar active, headings emphasis, logo    |
| `--primary-light` | `#78716C` | `oklch(0.52 0.01 55)`  | Hover states, secondary borders            |
| `--accent`        | `#C2410C` | `oklch(0.50 0.16 35)`  | Primary CTA buttons, links, focus rings    |
| `--accent-hover`  | `#9A3412` | `oklch(0.42 0.14 35)`  | CTA hover/pressed state                    |
| `--accent-subtle` | `#FFF7ED` | `oklch(0.98 0.01 70)`  | Accent backgrounds (selected rows, badges) |
| `--background`    | `#FAF9F7` | `oklch(0.98 0.005 80)` | Page background — warm off-white           |
| `--card`          | `#FFFFFF` | `oklch(1.0 0 0)`       | Cards, panels, table backgrounds           |
| `--sidebar`       | `#F0EDEA` | `oklch(0.94 0.008 60)` | Sidebar background — warm light gray       |
| `--text`          | `#1C1917` | `oklch(0.15 0.01 55)`  | Primary text — warm near-black             |
| `--text-muted`    | `#78716C` | `oklch(0.52 0.01 55)`  | Secondary text, labels, captions           |
| `--text-subtle`   | `#A8A29E` | `oklch(0.68 0.01 55)`  | Placeholder text, disabled                 |
| `--border`        | `#D6D3CE` | `oklch(0.85 0.008 60)` | Standard borders                           |
| `--border-light`  | `#E7E5E0` | `oklch(0.91 0.006 60)` | Subtle dividers, card borders              |
| `--ring`          | `#C2410C` | `oklch(0.50 0.16 35)`  | Focus ring (matches accent)                |

### Dark Mode

| Token            | Hex       | OKLCH                  | Usage                               |
| ---------------- | --------- | ---------------------- | ----------------------------------- |
| `--background`   | `#1C1917` | `oklch(0.15 0.01 55)`  | Page background                     |
| `--card`         | `#292524` | `oklch(0.21 0.01 40)`  | Cards, panels                       |
| `--sidebar`      | `#171412` | `oklch(0.12 0.01 40)`  | Sidebar                             |
| `--text`         | `#E7E5E4` | `oklch(0.92 0.005 55)` | Primary text                        |
| `--text-muted`   | `#A8A29E` | `oklch(0.68 0.01 55)`  | Secondary text                      |
| `--text-subtle`  | `#78716C` | `oklch(0.52 0.01 55)`  | Placeholder, disabled               |
| `--border`       | `#44403C` | `oklch(0.32 0.01 55)`  | Standard borders                    |
| `--border-light` | `#332F2C` | `oklch(0.25 0.01 50)`  | Subtle dividers                     |
| `--accent`       | `#EA580C` | `oklch(0.57 0.18 35)`  | CTA — slightly brighter for dark bg |
| `--accent-hover` | `#F97316` | `oklch(0.65 0.18 45)`  | CTA hover                           |

### Semantic Colors

| Token          | Light     | Dark                     | Usage                            |
| -------------- | --------- | ------------------------ | -------------------------------- |
| `--success`    | `#059669` | `#10B981`                | Won deals, positive metrics      |
| `--success-bg` | `#DCFCE7` | `rgba(22, 101, 52, 0.3)` | Success badge background         |
| `--warning`    | `#D97706` | `#F59E0B`                | Pending, awaiting action         |
| `--warning-bg` | `#FEF3C7` | `rgba(146, 64, 14, 0.3)` | Warning badge background         |
| `--error`      | `#DC2626` | `#EF4444`                | Errors, overdue, rejected        |
| `--error-bg`   | `#FEE2E2` | `rgba(220, 38, 38, 0.3)` | Error badge background           |
| `--info`       | `#9A3412` | `#C2410C`                | In progress (uses copper family) |
| `--info-bg`    | `#FFF7ED` | `rgba(154, 52, 18, 0.3)` | Info badge background            |

---

## Typography

### Font: Plus Jakarta Sans

```css
@import url("https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap");
```

**Why:** Modern alternative to Inter. Geometric but friendly. Professional but approachable. Single font, multiple weights — no pairing complexity.

### Type Scale (1.25 ratio)

| Token         | Size | Weight  | Line Height | Usage                               |
| ------------- | ---- | ------- | ----------- | ----------------------------------- |
| `--text-xs`   | 12px | 400-500 | 1.5         | Badges, timestamps, captions        |
| `--text-sm`   | 14px | 400-500 | 1.5         | Labels, table cells, secondary text |
| `--text-base` | 16px | 400     | 1.625       | Body text, form inputs              |
| `--text-lg`   | 18px | 600     | 1.4         | Card titles, section headings       |
| `--text-xl`   | 20px | 600     | 1.3         | Page section titles                 |
| `--text-2xl`  | 24px | 700     | 1.25        | Page titles                         |
| `--text-3xl`  | 30px | 700     | 1.2         | Dashboard hero numbers              |

### Rules

- **Headings:** `font-semibold` (600) — never `font-bold` (700) except page titles
- **Body:** `font-normal` (400)
- **Labels:** `text-sm font-medium text-muted uppercase tracking-wide`
- **Numbers:** `font-variant-numeric: tabular-nums` for aligned columns
- **Max prose width:** 65ch (`max-w-prose`)

---

## Spacing Scale (4px base)

| Token | Value | Usage                                  |
| ----- | ----- | -------------------------------------- |
| `1`   | 4px   | Icon gaps, tight inline                |
| `2`   | 8px   | Between related items, compact padding |
| `3`   | 12px  | Form field gaps, small card padding    |
| `4`   | 16px  | Card padding, section element gaps     |
| `6`   | 24px  | Between form groups, card sections     |
| `8`   | 32px  | Between major content blocks           |
| `12`  | 48px  | Between page sections                  |
| `16`  | 64px  | Top/bottom page margins                |

### Rules

- **Card padding:** `p-5` (20px) standard, `p-4` (16px) compact
- **Section gaps:** `gap-6` (24px)
- **Page padding:** `px-8` (32px) desktop, `px-4` (16px) mobile
- **Form field gaps:** `gap-3` to `gap-4`
- **Table cell padding:** `px-5 py-3.5` (20px/14px)
- **Button padding:** `px-4 py-2.5` standard, `px-3 py-2` small

---

## Border Radius

| Token         | Value | Usage                  |
| ------------- | ----- | ---------------------- |
| `--radius-sm` | 6px   | Badges, small inputs   |
| `--radius-md` | 8px   | Buttons, inputs, pills |
| `--radius-lg` | 12px  | Cards, panels, modals  |

One system. Never mix 4px, 10px, 16px randomly.

---

## Shadows

| Token         | Value                                                               | Usage                     |
| ------------- | ------------------------------------------------------------------- | ------------------------- |
| `--shadow-sm` | `0 1px 2px rgba(28, 25, 23, 0.05)`                                  | Cards resting state       |
| `--shadow`    | `0 1px 3px rgba(28, 25, 23, 0.1), 0 1px 2px rgba(28, 25, 23, 0.06)` | Elevated cards, dropdowns |
| `--shadow-md` | `0 4px 6px rgba(28, 25, 23, 0.1)`                                   | Modals, floating panels   |

**Rules:**

- Cards use `border` by default, NOT shadows (Stripe pattern)
- Shadows only for elevated/floating elements (dropdowns, modals, tooltips)
- Shadow color uses warm black (`28, 25, 23`), not pure black

---

## Components

### Buttons

```
Primary:    bg-accent text-white rounded-md px-4 py-2.5 font-semibold
Secondary:  bg-transparent border border-border text-text rounded-md px-4 py-2.5 font-semibold
Ghost:      bg-transparent text-text-muted rounded-md px-4 py-2.5 font-medium
Danger:     bg-transparent border border-error text-error rounded-md px-4 py-2.5 font-semibold
```

- **Max 1 primary button per section**
- Destructive actions: NEVER primary style — use outlined danger with confirmation
- Loading state: disable + show spinner

### Badges

```
Success:    bg-success-bg text-success-text rounded-sm px-2.5 py-1 text-xs font-semibold
Warning:    bg-warning-bg text-warning-text rounded-sm px-2.5 py-1 text-xs font-semibold
Error:      bg-error-bg text-error-text rounded-sm px-2.5 py-1 text-xs font-semibold
Copper:     bg-accent-subtle text-info rounded-sm px-2.5 py-1 text-xs font-semibold
Neutral:    bg-sidebar text-text-muted rounded-sm px-2.5 py-1 text-xs font-semibold
```

### Cards

```
Standard:   bg-card border border-border-light rounded-lg
Elevated:   bg-card border border-border-light rounded-lg shadow-sm
```

- No gradient backgrounds on cards
- No colored card headers — use type hierarchy instead

### Tables

```
Header:     text-xs font-semibold uppercase tracking-wide text-text-muted
Row:        hover:bg-[rgba(87,83,78,0.04)] transition-colors
Cell:       text-sm py-3.5 px-5
Border:     border-b border-border-light
```

- Row hover: subtle warm tint, not highlight
- Sort indicator on column headers
- Max 3 visible action icons per row, rest in overflow menu

### Forms

```
Input:      bg-transparent border border-border rounded-md px-3 py-2.5 text-base
            focus:ring-2 focus:ring-accent focus:border-accent
Label:      text-xs font-semibold uppercase tracking-wide text-text-muted mb-1.5
Helper:     text-xs text-text-subtle mt-1
Error:      text-xs text-error mt-1
```

- Labels ABOVE inputs (never beside)
- Max 5 fields visible without progressive disclosure
- Smart defaults: pre-fill from context

### Sidebar

```
Background: bg-sidebar border-r border-border-light
Logo:       text-lg font-bold text-primary
Section:    text-xs font-semibold uppercase tracking-wide text-text-muted
Item:       text-sm font-medium text-text-muted px-3 py-2 rounded-md
Active:     text-text font-semibold bg-[rgba(87,83,78,0.08)]
```

---

## Tailwind v4 CSS Variables

```css
@theme inline {
  /* Primary palette */
  --color-primary: oklch(0.41 0.01 55);
  --color-primary-light: oklch(0.52 0.01 55);
  --color-accent: oklch(0.5 0.16 35);
  --color-accent-hover: oklch(0.42 0.14 35);
  --color-accent-subtle: oklch(0.98 0.01 70);

  /* Backgrounds */
  --color-background: oklch(0.98 0.005 80);
  --color-card: oklch(1 0 0);
  --color-sidebar: oklch(0.94 0.008 60);

  /* Text */
  --color-text: oklch(0.15 0.01 55);
  --color-text-muted: oklch(0.52 0.01 55);
  --color-text-subtle: oklch(0.68 0.01 55);

  /* Borders */
  --color-border: oklch(0.85 0.008 60);
  --color-border-light: oklch(0.91 0.006 60);

  /* Semantic */
  --color-success: oklch(0.55 0.15 160);
  --color-warning: oklch(0.6 0.15 75);
  --color-error: oklch(0.5 0.2 25);

  /* Radius */
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
}
```

---

## Anti-Patterns (NEVER do these)

- No `transition: all` — animate specific properties only
- No `transform: translateY()` on hover for cards/buttons — use color/shadow changes
- No emoji as icons — use Lucide React SVGs
- No pure gray (`#6b7280`) — always warm-tinted (`#78716C`)
- No hardcoded hex in components — use semantic tokens
- No `text-[#hex]` or `bg-[#hex]` — use design system classes
- No decorative images in task flows (forms, dashboards)
- No more than 4 distinct colors carrying meaning per page
- No arbitrary spacing (`gap-[13px]`) — use scale values only
- No mixing border-radius values outside the 3-value system
