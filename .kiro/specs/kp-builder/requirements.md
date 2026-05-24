# Requirements Document

## Introduction

KP Builder is a standalone PDF generator for heavy-machinery commercial proposals (КП на спецтехнику). Users open `/kp-builder` and see a split-screen workspace: a kvotaflow-styled fill-in form on the left, and a live A4 preview of the two-page proposal in the Master Bearing brand style on the right. A "Save PDF" button serializes the form state and posts it to a Python endpoint that renders the proposal via WeasyPrint and returns the binary PDF for download. Form state persists across page reloads via `localStorage`, with explicit "Clear" and "Example" reset actions.

This first iteration is intentionally standalone — no link to the existing quotes registry, no database persistence, no multi-tenant branding. Master Bearing branding is hardcoded but isolated in a single `branding-config` object so future iterations can swap logo, palette, illustrations, and footer per organization without rewriting the renderer.

The design source is a handoff bundle from Claude Design at `/tmp/kvota-pdf-design/extracted/untitled/project/`, with two key prototypes (`KpPage1.jsx`, `KpPage2.jsx`) defining the visual structure and `DEFAULT_DATA` in `App.jsx` defining the data shape.

## Requirements

### Requirement 1: Page Access and Sidebar Navigation
**Objective:** As a sales user, I want a dedicated entry point for the KP builder in the sidebar, so that I can open the generator from anywhere in the app without remembering a URL.

#### Acceptance Criteria
1. The KP Builder page SHALL be reachable at the URL path `/kp-builder` within the Next.js frontend.
2. The Sidebar widget SHALL display a navigation entry labelled "КП на технику" that links to `/kp-builder`.
3. The KP Builder page SHALL be available to any authenticated user whose Supabase session is valid; no role-based gating is required in this iteration.
4. IF an unauthenticated user navigates to `/kp-builder`, THEN the Sidebar widget SHALL redirect them to the login route consistent with other authenticated pages.
5. The KP Builder page SHALL render a split-screen layout where the left pane is the input form and the right pane is the live preview, occupying the full available viewport width.

### Requirement 2: Form State Lifecycle and Persistence
**Objective:** As a sales user, I want my in-progress KP to survive page reloads and tab closures, so that I do not lose work to accidental refreshes.

#### Acceptance Criteria
1. The KP Builder page SHALL initialize the form with `DEFAULT_DATA` (the example proposal) on first visit when no prior state exists in browser storage.
2. WHEN the user modifies any form field, the KP Builder page SHALL persist the entire form state to `localStorage` under the key `kvotaflow.kp.v1`.
3. WHEN the user reloads the page or returns in a new tab, the KP Builder page SHALL restore the last persisted form state and render it in both the form and the preview.
4. WHEN the user clicks the "Очистить" button and confirms in the resulting dialog, the KP Builder page SHALL reset all fields to empty values (empty strings, single empty row in dynamic lists, all checkboxes unchecked) and persist the cleared state.
5. WHEN the user clicks the "Пример" button and confirms in the resulting dialog, the KP Builder page SHALL reset all fields to `DEFAULT_DATA` and persist that state.
6. IF `localStorage` is unavailable or quota-exceeded, THEN the KP Builder page SHALL continue to function in-memory without throwing an error visible to the user.

### Requirement 3: Header and Meta Fields
**Objective:** As a sales user, I want to enter all proposal metadata (supplier identity, contact info, commercial terms, totals) in clearly grouped fields, so that the resulting КП conveys complete deal context.

#### Acceptance Criteria
1. The KP Builder form SHALL provide editable text inputs for each of: `subtitle`, `supplier`, `manager`, `phone`, `email`, `address`, `basis`, `payment`, `date`, `lead`, `amount`, `priceIncludes`.
2. WHEN the user updates any of these fields, the KP Builder page SHALL reflect the new value in the right-pane preview within one render cycle.
3. The KP Builder page SHALL display the `amount` field with a ruble suffix "₽" and group thousands using a non-breaking thin space in the preview (Russian locale formatting), regardless of how the user typed the value (with spaces, with commas as decimal, or as a plain integer).
4. IF the `amount` field contains a value that cannot be parsed as a number, THEN the KP renderer SHALL display the raw value as entered without crashing.
5. The KP Builder form SHALL group meta fields into a single section labelled "Информация о предложении" with section header iconography matching the kvotaflow design system.

### Requirement 4: Equipment Items Table
**Objective:** As a sales user, I want to list each piece of machinery on a single row with name, model, quantity, and unit price, so that the КП itemizes the offer clearly with an automatic total.

#### Acceptance Criteria
1. The KP Builder form SHALL render the `items` array as a dynamic list where each row exposes editable fields for `name`, `model`, `qty`, and `price`.
2. The KP Builder form SHALL provide an "add row" control that appends a new empty `{ name: "", model: "", qty: "", price: "" }` entry to `items`.
3. The KP Builder form SHALL provide a "remove row" control on each row that removes that entry from `items`.
4. The KP renderer SHALL display at least five table rows in the preview, padding with empty rows if fewer items are entered, to preserve the visual rhythm of the proposal.
5. The KP renderer SHALL compute the row sum as `qty * price` and display it formatted in Russian locale.
6. The KP renderer SHALL compute the grand total as the sum of all `qty * price` products across non-empty rows and display it labelled "ИТОГО:" with the "₽" suffix.
7. IF `qty` or `price` cannot be parsed as a number, THEN that row SHALL contribute zero to the grand total and the per-row sum cell SHALL be blank.

### Requirement 5: Page-1 Notes Field
**Objective:** As a sales user, I want a free-text notes area on page 1, so that I can communicate caveats such as offer validity period without forcing a separate page.

#### Acceptance Criteria
1. The KP Builder form SHALL provide a multi-line text input bound to `notes`.
2. The KP renderer SHALL display `notes` inside a bordered box labelled "Примечания / Дополнительная информация:" beneath the items table on page 1.
3. IF `notes` is empty, THEN the KP renderer SHALL still display the bordered notes box with empty content (the placeholder structure is part of the brand layout).

### Requirement 6: Technical Specifications List (Page 2)
**Objective:** As a sales user, I want to list the headline technical characteristics that apply across the offered machinery, so that the buyer can scan key specs without reading model sheets.

#### Acceptance Criteria
1. The KP Builder form SHALL render the `specs` array as a dynamic list of text inputs with add and remove controls.
2. The KP renderer SHALL display each non-empty spec as a bulleted row inside the "ОСНОВНЫЕ ХАРАКТЕРИСТИКИ" card on page 2.
3. The KP renderer SHALL display at least eight bullet slots in the preview, padding with empty slots if fewer specs are entered, to preserve the layout balance with the packaging card.

### Requirement 7: Packaging Checklist (Page 2)
**Objective:** As a sales user, I want a checkbox-style packaging list, so that the buyer immediately sees which items are included versus available on request.

#### Acceptance Criteria
1. The KP Builder form SHALL render the `packaging` array as a dynamic list where each entry has a text input for the label and a checkbox for the included state.
2. The KP Builder form SHALL provide add and remove controls for packaging entries.
3. The KP renderer SHALL display each packaging entry as a row with a 45°-rotated square indicator inside the "КОМПЛЕКТАЦИЯ" card; the indicator SHALL appear filled when `checked` is true and empty when false.
4. The KP renderer SHALL display at least eight packaging slots in the preview, padding with empty entries if fewer are entered.

### Requirement 8: Conditions and Warranties List (Page 2)
**Objective:** As a sales user, I want to list warranty and service conditions as bullets, so that buyers see commitments clearly separated from technical specs.

#### Acceptance Criteria
1. The KP Builder form SHALL render the `conditions` array as a dynamic list of text inputs with add and remove controls.
2. The KP renderer SHALL display each non-empty condition as a bulleted row inside the "УСЛОВИЯ И ГАРАНТИИ" section on page 2.
3. The KP renderer SHALL display at least three condition slots in the preview, padding with empty slots if fewer are entered.

### Requirement 9: Additional Services Checkboxes (Page 2)
**Objective:** As a sales user, I want six fixed checkboxes for the standard add-on services we offer, so that the КП mirrors our service catalogue without typing.

#### Acceptance Criteria
1. The KP Builder form SHALL provide six boolean checkboxes bound to `services.delivery`, `services.training`, `services.supervision`, `services.warranty`, `services.commissioning`, and `services.service`.
2. The KP renderer SHALL display all six service options on page 2 with each checkbox indicator (45°-rotated square) shown filled when the corresponding service flag is true and empty when false.
3. The KP renderer SHALL display the labels "Доставка", "Обучение операторов", "Шеф-монтаж", "Расширенная гарантия", "Пусконаладочные работы", "Сервисное обслуживание" alongside each indicator, in this fixed order.

### Requirement 10: Page-2 Notes, Contacts, and Footer
**Objective:** As a sales user, I want a free-form notes area, structured contact details, and a branded footer on page 2, so that the buyer has everything needed to act on the offer.

#### Acceptance Criteria
1. The KP Builder form SHALL provide a multi-line input bound to `notes2` and render it inside the "ДЛЯ ЗАМЕТОК" box on page 2.
2. The KP Builder form SHALL provide text inputs bound to `contact_phone`, `contact_email`, `contact_site`, `contact_address` and render each as a row inside the "КОНТАКТЫ" block on page 2.
3. The KP Builder form SHALL provide text inputs bound to `foot_phone`, `foot_site`, `foot_email` and render each inside the page-2 footer.
4. WHEN a contact or footer field is empty, the KP renderer SHALL display the row label but leave the value blank, preserving the layout structure.

### Requirement 11: Live Preview Rendering
**Objective:** As a sales user, I want the right-pane preview to update as I type, so that I can iterate on the wording and layout before exporting.

#### Acceptance Criteria
1. The KP Builder page SHALL render the right-pane preview as two A4-proportioned pages (794 × 1123 CSS pixels each) stacked vertically.
2. WHEN any form field changes, the KP Builder page SHALL update the corresponding region of the preview without a full reload.
3. The KP Builder page SHALL render the preview using the Master Bearing brand styles (blue and red bars, "КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ" headline, hero machinery illustration on page 1, mountains illustration on page 2).
4. The KP Builder page SHALL render the preview with the Inter font loaded from the same source as the PDF font bundle, so the browser preview visually matches the PDF output.
5. The KP Builder page SHALL isolate KP preview styles from the global kvotaflow design system, scoping them under a `.kp-page` (or equivalent) namespace so they do not bleed into the surrounding form UI.

### Requirement 12: Preview Zoom Controls
**Objective:** As a sales user, I want to zoom the preview in and out, so that I can verify both layout and detail without printing.

#### Acceptance Criteria
1. The KP Builder page SHALL provide zoom controls (decrement, increment, reset) that adjust the preview scale between 30% and 120%.
2. The KP Builder page SHALL display the current zoom percentage between the decrement and increment controls.
3. The KP Builder page SHALL persist the chosen zoom level to `localStorage` under the key `kvotaflow.kp.v1.zoom` and restore it on subsequent visits.
4. WHEN the user clicks the reset zoom control, the KP Builder page SHALL set the zoom back to 70%.

### Requirement 13: PDF Download Trigger
**Objective:** As a sales user, I want a single button to download the proposal as a PDF, so that I can attach it to an email or print it.

#### Acceptance Criteria
1. The KP Builder page SHALL display a "Сохранить PDF" button in the preview toolbar.
2. WHEN the user clicks "Сохранить PDF", the KP Builder page SHALL send the current form state as JSON to `POST /api/kp/render-pdf` with the user's Supabase JWT in the `Authorization: Bearer <token>` header.
3. WHEN the endpoint responds with a PDF binary, the KP Builder page SHALL trigger a browser download of the file with a filename of the form `kp-{YYYY-MM-DD}.pdf` (using the user's local date).
4. WHILE the PDF render request is in flight, the KP Builder page SHALL disable the "Сохранить PDF" button and display a loading indicator on the button.
5. IF the render request fails, THEN the KP Builder page SHALL display a non-blocking error toast with the failure reason and re-enable the button.

### Requirement 14: PDF Render Endpoint Contract
**Objective:** As an AI agent or future integration, I want a documented JSON-in/PDF-out endpoint, so that the KP can be generated without using the browser UI.

#### Acceptance Criteria
1. The KP PDF endpoint SHALL be implemented as `POST /api/kp/render-pdf` inside the FastAPI sub-app mounted under `/api`.
2. The KP PDF endpoint SHALL accept a JSON request body matching the form data shape (all fields listed in REQ-3 through REQ-10) with all fields optional and defaulting to empty strings or empty arrays.
3. The KP PDF endpoint SHALL respond with `Content-Type: application/pdf` and the rendered PDF bytes when the request succeeds.
4. The KP PDF endpoint SHALL respond with HTTP 200 and a `Content-Disposition: attachment; filename="kp-{YYYY-MM-DD}.pdf"` header on success.
5. The KP PDF endpoint SHALL require a valid Supabase JWT in the `Authorization` header and SHALL reject unauthenticated requests with HTTP 401 and a structured error response (`{"success": false, "error": {"code": "UNAUTHORIZED", "message": "..."}}`).
6. IF the JSON body is malformed, THEN the KP PDF endpoint SHALL respond with HTTP 400 and a `VALIDATION_ERROR` structured error.
7. IF the WeasyPrint render raises an exception, THEN the KP PDF endpoint SHALL log the exception with full context and respond with HTTP 500 and a `RENDER_ERROR` structured error; no partial PDF SHALL be returned.
8. The KP PDF endpoint SHALL include a structured docstring matching the documentation standard in `.kiro/steering/api-first.md` (Path, Params, Returns, Roles).

### Requirement 15: PDF Document Specification
**Objective:** As a sales user, I want the downloaded PDF to look exactly like the preview, so that the buyer receives the branded layout faithfully.

#### Acceptance Criteria
1. The KP renderer SHALL produce a PDF with exactly two A4 portrait pages (210 × 297 mm) regardless of how many items, specs, or conditions were entered.
2. The KP renderer SHALL embed the Inter font (Regular, Medium, SemiBold, Bold weights) directly in the PDF, with the font files loaded from `services/fonts/` and referenced via `@font-face` in the rendered HTML.
3. The KP renderer SHALL embed both hero illustrations (heavy machinery on page 1, mountains on page 2) as raster assets loaded from a static path inside the Python service.
4. The KP renderer SHALL produce a PDF whose visible layout matches the browser preview within acceptable WeasyPrint-vs-Chromium drift (positioning, colors, font weights — no missing sections, no font fallback to default sans).
5. The KP renderer SHALL render `clip-path: polygon(...)` shapes (corner bars and footer cuts) as solid filled polygons; if WeasyPrint cannot render a particular polygon, the renderer SHALL fall back to an equivalent SVG shape so the bar still appears.
6. The KP renderer SHALL render the 45°-rotated check indicators for packaging and services as solid filled squares whose visual orientation matches the preview.

### Requirement 16: Branding Configuration Isolation
**Objective:** As a future feature, I want one place to swap logo, colors, illustrations, and footer per organization, so that we can add Master Bearing's competitors without rewriting the renderer.

#### Acceptance Criteria
1. The KP renderer SHALL load all brand-specific values (palette colors, logo SVG, hero illustration paths, footer feature tiles, default footer phone/site/email, default subtitle) from a single `branding` configuration object.
2. The KP renderer SHALL hardcode this `branding` object to the Master Bearing values in this iteration; the value SHALL live in a single file (`services/exports/kp_branding.py`) so that future multi-brand work changes only that file's lookup logic.
3. The KP Builder page SHALL receive the same `branding` object (or its frontend equivalent) from a single source so that the browser preview matches the PDF brand at all times.
4. The KP renderer SHALL NOT reference any kvotaflow design tokens (Inter font, palette, spacing) inside the proposal layout — all proposal styling comes from the `branding` object and an isolated `kp.css` module.

### Requirement 17: Visual Fidelity Between Preview and PDF
**Objective:** As a sales user, I want what I see in the right pane to be what the buyer sees in the PDF, so that I can ship confidently without opening the file every time.

#### Acceptance Criteria
1. The KP Builder system SHALL render both the preview and the PDF from the same HTML/CSS source structure to minimize visual drift.
2. The KP Builder system SHALL include an automated visual regression test fixture that generates a PDF from a known fixture data set and compares output bytes against a stored baseline; baseline updates SHALL be intentional and reviewed.
3. WHEN a font, illustration, or branding-config change is made, the KP Builder system SHALL update the baseline as part of the same change so the regression test continues to pass.
4. The KP Builder system SHALL document any known acceptable drift between Chromium preview and WeasyPrint PDF in a "Known WeasyPrint quirks" section of the design document.

### Requirement 18: Authentication and Authorization
**Objective:** As the platform owner, I want only authenticated users to consume PDF generation, so that we do not expose CPU-bound rendering to anonymous traffic.

#### Acceptance Criteria
1. The KP Builder page SHALL be served only to authenticated Supabase users; unauthenticated visitors SHALL be redirected to the login route.
2. The KP PDF endpoint SHALL be protected by the existing `ApiAuthMiddleware` JWT validation; calls without a valid JWT SHALL receive HTTP 401.
3. The KP PDF endpoint SHALL log the calling user's ID and organization ID with each successful render so operators can correlate usage.
4. The KP PDF endpoint SHALL NOT enforce role-based access in this iteration; any authenticated user may generate a KP.

### Requirement 19: Error Surfaces and Logging
**Objective:** As a sales user, I want clear feedback when something goes wrong, so that I can retry or escalate without staring at a hung button.

#### Acceptance Criteria
1. IF the PDF endpoint returns HTTP 401, THEN the KP Builder page SHALL display a toast prompting the user to refresh their session and SHALL leave form state untouched.
2. IF the PDF endpoint returns HTTP 400 with a `VALIDATION_ERROR`, THEN the KP Builder page SHALL display the `message` from the structured error in a toast.
3. IF the PDF endpoint returns HTTP 500 with a `RENDER_ERROR`, THEN the KP Builder page SHALL display a generic "Не удалось сгенерировать PDF, попробуйте ещё раз" toast and SHALL surface the request ID (if returned) for support.
4. The KP PDF endpoint SHALL log every render attempt with: request ID, user ID, payload size, render duration, success/failure, error class on failure.

### Requirement 20: Out-of-Scope Boundaries (Iteration 1)
**Objective:** As the team, I want explicit non-goals captured, so that scope-creep doesn't dilute this iteration.

#### Acceptance Criteria
1. The KP Builder system SHALL NOT persist any KP data to the database in this iteration.
2. The KP Builder system SHALL NOT connect to the existing `quotes` or `specifications` registries; the form is filled manually.
3. The KP Builder system SHALL NOT add a sidebar entry under "Реестры" or "Финансы"; the entry lives under "Главное" (or equivalent top-level section) for now and migrates when registry integration arrives.
4. The KP Builder system SHALL NOT expose any multi-tenant or per-organization branding UI; the `branding` config is a developer-edited constant.
5. The KP Builder system SHALL NOT send the generated PDF via email or upload it to Supabase Storage; download to the user's machine is the only output channel.
6. The KP Builder system SHALL NOT version, history, or audit-log generated KPs; the only audit trail is the endpoint log entry from REQ-19.

---

## Open Questions

- **Q1:** Should the PDF filename include the supplier name (e.g. `kp-master-bearing-2026-05-22.pdf`) or stay date-only (`kp-2026-05-22.pdf`)? Current default is date-only per REQ-13. _Decision needed before Phase 2b._
- **Q2:** When `localStorage` quota fails (REQ-2.6), should we surface a one-time warning toast or stay silent? Current REQ says silent. _Decision needed before Phase 2b._
- **Q3:** REQ-17.2 calls for a visual regression test on PDF bytes. Byte-level diff is brittle (timestamps, IDs in PDF metadata). Should the baseline strip PDF metadata before comparing, or should we use a perceptual-diff library (e.g. `pdfminer` extract + structural compare)? _Decision needed before Phase 3 implementation tasks._
