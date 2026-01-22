# Kvota OneStack Design System

**Референс:** [Livento CRM Dashboard](https://www.behance.net/gallery/239045803/CRM-Dashboard-UI-UX-Branding-Case-Study)
**Последнее обновление:** 2026-01-22

---

## Типографика

### Шрифт: Manrope
Google Fonts: https://fonts.google.com/specimen/Manrope

| Элемент | Размер | Вес | Line Height |
|---------|--------|-----|-------------|
| H1 (заголовок страницы) | 32px | 700 (Bold) | 1.2 |
| H2 (заголовок секции) | 24px | 600 (SemiBold) | 1.3 |
| H3 (заголовок карточки) | 18px | 600 (SemiBold) | 1.4 |
| Body (основной текст) | 14px | 400 (Regular) | 1.5 |
| Small (подписи) | 12px | 500 (Medium) | 1.4 |
| Stat Value (большие числа) | 32px | 700 (Bold) | 1.1 |

---

## Цветовая палитра

### Светлая тема (по умолчанию)

```css
/* Backgrounds */
--bg-page: #F5F7FA;          /* Фон страницы */
--bg-page-alt: #EEF1F5;      /* Альтернативный фон */
--bg-card: #FFFFFF;          /* Карточки */
--bg-sidebar: #FFFFFF;       /* Сайдбар */

/* Text */
--text-primary: #1F2937;     /* Основной текст */
--text-secondary: #6B7280;   /* Вторичный текст */
--text-muted: #9CA3AF;       /* Приглушённый текст */

/* Accent */
--accent: #3B82F6;           /* Основной акцент (синий) */
--accent-hover: #2563EB;     /* Hover состояние */
--accent-light: #EFF6FF;     /* Светлый акцент для backgrounds */

/* Borders & Shadows */
--border-color: #E5E7EB;     /* Границы */
--border-light: #F3F4F6;     /* Лёгкие границы */
--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
--shadow-md: 0 4px 12px rgba(0, 0, 0, 0.08);
--shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.12);
```

### Status Colors (для обеих тем)

```css
/* Success - зелёный */
--status-success: #10B981;
--status-success-bg: #D1FAE5;
--status-success-text: #065F46;

/* Info - синий */
--status-info: #3B82F6;
--status-info-bg: #DBEAFE;
--status-info-text: #1E40AF;

/* Warning - жёлтый/оранжевый */
--status-warning: #F59E0B;
--status-warning-bg: #FEF3C7;
--status-warning-text: #92400E;

/* Error/Danger - красный */
--status-error: #EF4444;
--status-error-bg: #FEE2E2;
--status-error-text: #991B1B;

/* Neutral - серый */
--status-neutral: #6B7280;
--status-neutral-bg: #F3F4F6;
--status-neutral-text: #374151;

/* Purple (scheduled, special) */
--status-purple: #8B5CF6;
--status-purple-bg: #EDE9FE;
--status-purple-text: #5B21B6;
```

---

## Spacing System (8px base)

```css
--space-1: 4px;    /* 0.25rem */
--space-2: 8px;    /* 0.5rem */
--space-3: 12px;   /* 0.75rem */
--space-4: 16px;   /* 1rem */
--space-5: 20px;   /* 1.25rem */
--space-6: 24px;   /* 1.5rem */
--space-8: 32px;   /* 2rem */
--space-10: 40px;  /* 2.5rem */
--space-12: 48px;  /* 3rem */
```

### Применение:
- **Padding карточек:** 24px (--space-6)
- **Gap между элементами:** 16px (--space-4)
- **Gap между секциями:** 32px (--space-8)
- **Padding кнопок:** 12px 20px

---

## Border Radius

```css
--radius-sm: 6px;    /* Мелкие элементы (badges, inputs) */
--radius-md: 8px;    /* Средние элементы (buttons) */
--radius-lg: 12px;   /* Карточки */
--radius-xl: 16px;   /* Большие карточки, модальные окна */
--radius-full: 9999px; /* Pills, avatars */
```

---

## Компоненты

### Stat Card
```
┌─────────────────────────────┐
│  [icon]                     │
│                             │
│  120                        │  ← Большое число (32px, bold, accent)
│  +12% ↗                     │  ← Badge с изменением (зелёный/красный)
│                             │
│  Active Leads               │  ← Label (14px, text-secondary)
└─────────────────────────────┘

- Background: белый
- Padding: 24px
- Border-radius: 12px
- Shadow: shadow-md
- Иконка: 24x24, accent color
```

### Button Styles

**Primary Button:**
```css
background: var(--accent);
color: white;
padding: 12px 20px;
border-radius: 8px;
font-weight: 500;
box-shadow: 0 1px 2px rgba(59, 130, 246, 0.2);
```

**Secondary Button:**
```css
background: white;
color: var(--text-primary);
border: 1px solid var(--border-color);
padding: 12px 20px;
border-radius: 8px;
```

**Ghost Button:**
```css
background: transparent;
color: var(--accent);
padding: 12px 20px;
border-radius: 8px;
```

### Status Badges
```css
padding: 4px 12px;
border-radius: 9999px;
font-size: 12px;
font-weight: 500;
/* Цвет фона и текста из status colors */
```

### Tabs
```css
/* Inactive tab */
color: var(--text-secondary);
padding: 8px 16px;
border-radius: 8px;

/* Active tab */
background: var(--accent);
color: white;
padding: 8px 16px;
border-radius: 8px;
```

---

## Иконки

### Рекомендуемые библиотеки:
1. **Lucide Icons** - https://lucide.dev (рекомендуется)
2. **Heroicons** - https://heroicons.com
3. **Feather Icons** - https://feathericons.com

### Стиль:
- Outline (не filled)
- Stroke width: 1.5-2px
- Размеры: 16px (small), 20px (default), 24px (large)

### Основные иконки:
| Функция | Иконка | Lucide name |
|---------|--------|-------------|
| Dashboard | 📊 → | `layout-dashboard` |
| Quotes | 📋 → | `file-text` |
| New Quote | 📝 → | `plus-circle` |
| Customers | 👥 → | `users` |
| Procurement | 🛒 → | `shopping-cart` |
| Suppliers | 🏭 → | `building-2` |
| Logistics | 🚚 → | `truck` |
| Customs | 🛃 → | `shield-check` |
| Finance | 💰 → | `wallet` |
| Settings | ⚙️ → | `settings` |
| Admin | 🔧 → | `wrench` |
| Logout | → | `log-out` |

---

## Примеры улучшений

### До (текущее):
- Emoji иконки (📊, 📋)
- Фиолетовые градиенты
- Плотный spacing
- Inconsistent border-radius

### После (по гайдлайну):
- SVG иконки (Lucide)
- Чистый синий акцент (#3B82F6)
- Просторный spacing (24px padding)
- Единообразный border-radius (12px)

---

## Чеклист внедрения

- [ ] Подключить Google Font Manrope
- [ ] Обновить CSS переменные
- [ ] Заменить emoji на SVG иконки
- [ ] Обновить stat-cards
- [ ] Обновить кнопки
- [ ] Обновить status badges
- [ ] Обновить tabs
- [ ] Обновить spacing
- [ ] Протестировать light/dark тему
