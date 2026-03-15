# Settings Page — Screen Audit

**Date:** 2026-03-15
**Current URLs:** `/settings`, `/settings/phmb`
**Access:** Admin-only

---

## Screenshots

- Desktop 1440px: `settings-desktop-1440.png`
- PHMB full page: `settings-phmb-desktop-top.png`
- Mobile 375px: `settings-mobile-375.png`

---

## PRIMARY_ACTIONS

### /settings (main)
1. **Edit calculation rates** (forex risk %, commission %, loan rate) — core action, ~80% of visits
2. **Save settings** — confirm changes
3. **Navigate to PHMB settings** — link to subpage
4. **Navigate to Telegram settings** — link to subpage

### /settings/phmb
1. **Edit overhead costs** (logistics, customs, insurance) — primary
2. **Edit default values** (markup %, advance %, payment/delivery days) — frequent
3. **View brand discount table** — reference lookup (read-only)
4. **Manage brand groups** — rare, setup-time action
5. **Save PHMB settings** — confirm changes

---

## PAIN_POINTS

### P1. Two-page split is unnecessary
`/settings` has only 3 inputs + 2 navigation links. The entire page content fits in a single card. Users who need PHMB settings must click through, losing context. These should be tabs on one page.
**Severity:** Medium

### P2. Organization name field is misleading
Displayed as an editable textbox, but the hint says "contact admin to change." The field should be read-only text or disabled. Current state invites confusion.
**Severity:** Low

### P3. Save button scope is ambiguous
The full-width blue "Save settings" button on `/settings` visually covers all cards (org info, calc rates, Telegram, PHMB). But it only saves the 3 calculation rate fields. No feedback about what was saved.
**Severity:** Medium

### P4. Telegram and PHMB cards are just links
The Telegram and PHMB cards each contain a description + a navigation button. They look like settings sections but are just glorified links. They add vertical scroll for zero functionality.
**Severity:** Low

### P5. PHMB discount table is read-only but looks editable
The brand discount table (23 rows) takes up ~60% of the PHMB page height. It is display-only — no edit/delete actions on rows. Users cannot tell if they can or should modify these values from this page.
**Severity:** Medium

### P6. Brand groups section is empty and confusing
"No brand groups. Add the first group." with an inline form always visible. The "catch-all" checkbox is an advanced concept presented without context. This section feels unfinished.
**Severity:** Low

### P7. Mobile layout is broken
At 375px: sidebar remains open and pushes content off-screen. The "Loan rate" label wraps awkwardly, partially hidden by the feedback button. Two-column input layout breaks — first field ("Forex risk %") becomes invisible, only second field shows. Save button is cramped.
**Severity:** High

### P8. No visual grouping between related overhead inputs
PHMB has 8 inputs in flat pairs. There is no semantic grouping — logistics-related (pallet cost, logistics per pallet) vs. financial (insurance %, transit %) vs. customs (clearance, customs insurance). Users must read every label to find what they need.
**Severity:** Low

### P9. "Back to settings" button at bottom of PHMB
Navigation back is only available at the very bottom of a ~1500px tall page. No breadcrumb, no back link in the header.
**Severity:** Low

---

## USER_FLOWS

### Flow 1: Change forex risk rate
| Step | Current | Ideal |
|------|---------|-------|
| 1 | Navigate to /settings (sidebar: Администрирование > Настройки) | Same |
| 2 | Locate "Риск курса валют" field | Same |
| 3 | Edit value | Same |
| 4 | Click "Сохранить настройки" | Same |
| **Total** | **4 steps** | **4 steps** (acceptable) |

### Flow 2: Change PHMB markup default
| Step | Current | Ideal |
|------|---------|-------|
| 1 | Navigate to /settings | Navigate to /settings (PHMB tab) |
| 2 | Scroll down, click "Настройки PHMB" link | Edit field directly |
| 3 | Page loads, scroll to "Значения по умолчанию" section | Click save |
| 4 | Edit markup value | — |
| 5 | Click save | — |
| **Total** | **5 steps** | **3 steps** |

### Flow 3: Check brand discount
| Step | Current | Ideal |
|------|---------|-------|
| 1 | Navigate to /settings | Navigate to /settings (PHMB tab) |
| 2 | Click "Настройки PHMB" link | Scroll to discounts or search |
| 3 | Scroll past overhead + defaults sections | — |
| 4 | Find brand in unsorted-by-discount table | — |
| **Total** | **4 steps + scanning** | **2 steps + search** |

### 80/80 rule
80% of admin visits to settings change one of: forex risk %, commission %, or PHMB markup %. These three fields should be the most prominent and quickest to reach.

---

## PROPOSALS

### 1. MERGE: Combine /settings and /settings/phmb into tabbed page
Merge into single `/settings` with tabs: "Расчёты" (calc rates + PHMB overhead/defaults), "Скидки" (brand discounts), "Интеграции" (Telegram).
- **Impact:** High | **Effort:** Low
- Eliminates navigation between pages, reduces mental model from 2 pages to 1

### 2. RESTRUCTURE: Make organization name read-only
Replace the editable textbox with plain text display. Remove "contact admin" hint (the user IS the admin).
- **Impact:** Medium | **Effort:** Low
- Removes confusion about what is editable

### 3. SIMPLIFY: Merge all calculation inputs into one section
Group the 3 main calc rates and 8 PHMB overhead inputs into logical subsections within a single "Расчёты" tab:
- **Financial rates:** forex risk, commission, loan rate
- **Logistics:** pallet price, logistics per pallet
- **Insurance & customs:** currency insurance, financial transit, customs clearance, customs insurance
- **Defaults:** markup, advance, payment days, delivery days
One save button for all.
- **Impact:** High | **Effort:** Medium

### 4. ENHANCE: Add search/filter to brand discount table
23 rows is manageable but will grow. Add a simple text filter on brand name. Also add edit/delete actions inline if discounts are meant to be admin-managed.
- **Impact:** Medium | **Effort:** Low

### 5. REMOVE: Eliminate Telegram card from settings
Telegram config is a per-user preference, not an org setting. It already lives at `/telegram` (accessible from sidebar: Уведомления). Remove the link card from settings — it adds no value.
- **Impact:** Medium | **Effort:** Low
- Keeps settings focused on org-level configuration

### 6. SIMPLIFY: Collapse brand groups into expandable section
Brand groups form should be hidden behind an "Add group" button, not always-visible. Show existing groups as a simple list with delete. The checkbox "catch-all" needs a tooltip.
- **Impact:** Low | **Effort:** Low

### 7. FIX: Mobile layout
Sidebar must collapse on mobile. Form inputs must stack to single column. Save button must be full-width.
- **Impact:** High | **Effort:** Low (handled by Next.js responsive layout)

---

## DESIGN_SYSTEM_COMPLIANCE

| Aspect | Current (FastHTML) | Design System Target |
|--------|-------------------|---------------------|
| Font | System default / Inter | Plus Jakarta Sans |
| Colors | Blue primary (#3B82F6), blue CTA button | Copper accent (#C2410C), warm neutrals |
| Backgrounds | White cards on white bg | Warm off-white (#FAF9F7), white cards |
| Borders | Light gray | Warm border-light (#E7E5E0) |
| Labels | Mixed case, varying sizes | Uppercase, text-xs, font-semibold, tracking-wide |
| Save button | Full-width blue | Should be standard-width accent CTA, right-aligned |
| Section headers | Icon + uppercase text, decent | Matches DS pattern — keep |
| Spacing | Generally OK, some inconsistency | Needs 4px-base scale alignment |
| Border radius | Mixed (some rounded-lg, some rounded-md) | 3-value system: 6/8/12px |
| Shadows | None on cards | Cards use border, not shadow (correct per DS) |

---

## RECOMMENDED_CHANGES (final list for spec phase)

1. **Merge into tabbed single page** `/settings` with tabs: Расчёты | Скидки | Интеграции
2. **Organization name** becomes read-only header text, not a form field
3. **Group calculation inputs** into logical subsections with subheadings (financial, logistics, customs, defaults)
4. **Single save button** per tab, standard width, right-aligned
5. **Remove Telegram link card** from settings (it is a user-level feature, not org settings)
6. **Add text filter** to brand discount table
7. **Make discount rows editable inline** with add/delete capability
8. **Hide brand groups form** behind "Add group" button; show existing as list
9. **Add breadcrumb** or page-level "back" in header (not bottom of page)
10. **Apply design system**: Plus Jakarta Sans, copper accent, warm palette, proper label styles
11. **Fix mobile layout**: collapsible sidebar, single-column stacking, responsive form
12. **Markup/margin calculator** (currently not visible in UI) — if still needed, add as a utility section in Расчёты tab
