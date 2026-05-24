# Implementation Plan

- [x] 1. Foundation — assets, fonts, dependencies
- [x] 1.1 Add `pdfminer.six` to `requirements.txt`
  - Pin a recent stable version (`pdfminer.six>=20240706`)
  - Verify the docker image still builds locally
  - _Requirements: 17.2_

- [x] 1.2 Bundle Inter (OFL) for the backend
  - Place four TTF weights (Regular 400, Medium 500, SemiBold 600, Bold 700) at `services/fonts/Inter/`
  - Include `OFL.txt` from the upstream font release alongside the TTF files
  - Use the Latin + Cyrillic subset; verify all weights load without error in Python via a one-off smoke script
  - _Requirements: 15.2_

- [x] 1.3 Mirror Inter into the Next.js public bundle
  - Copy the same four TTF files to `frontend/public/fonts/Inter/`
  - Add a single `@font-face` block in `frontend/src/widgets/kp-preview/ui/kp-preview.module.css` (created in task 7.1) loading them via `/fonts/Inter/...`
  - _Requirements: 11.4_

- [x] 1.4 Place hero illustrations and Master Bearing logo on the backend
  - Save `hero-machinery.png` (page-1 hero), `mountains.png` (page-2 contacts panel), `master-bearing-logo.svg` at `services/static/kp/`
  - Save four footer feature icon SVGs (`shield.svg`, `shield-check.svg`, `cog.svg`, `handshake.svg`) at `services/static/kp/icons/`
  - Use the cleaned assets from the design handoff at `/tmp/kvota-pdf-design/extracted/untitled/project/`
  - _Requirements: 15.3_

- [x] 1.5 Mirror PNG assets into the Next.js public bundle
  - Copy `hero-machinery.png` and `mountains.png` to `frontend/public/static/kp/` so the browser preview renders the same illustrations as the PDF
  - _Requirements: 11.3, 11.4_

- [x] 2. Backend — branding configuration
- [x] 2.1 Create `services/kp_branding.py` with `KpBranding` and `FooterFeature` frozen dataclasses
  - Define the dataclasses per the design.md interface (colors, default subtitle, footer features, asset paths, font dir)
  - Construct the `MASTER_BEARING` singleton by reading SVG files from `services/static/kp/icons/` at import time
  - Type-hint every field; use `Tuple[FooterFeature, FooterFeature, FooterFeature, FooterFeature]` for the four-tile footer
  - _Requirements: 16.1, 16.2_

- [x] 2.2 Add unit tests for `kp_branding`
  - `tests/services/test_kp_branding.py`: assert all asset paths resolve to existing files, all SVG strings parse, color values match brand spec
  - Mark as `@pytest.mark.unit`
  - _Requirements: 16.1, 16.2_

- [x] 3. (P) Backend — PDF renderer service
- [x] 3.1 Implement number formatting and proposal helpers in `services/kp_export.py`
  - Define the immutable dataclasses (`KpItem`, `KpPackagingItem`, `KpServices`, `KpProposal`) per design.md
  - Implement `_fmt_ru(value)` parsing rules: strip spaces, comma-as-decimal, return raw on parse failure
  - Implement `calc_row_total(item)` returning `qty * price` or `None`, and `calc_grand_total(items)` summing valid rows
  - _Requirements: 3.3, 3.4, 4.5, 4.6, 4.7_

- [x] 3.2 Port the KP CSS into the renderer
  - Add `_kp_styles(branding)` returning the full inlined CSS string with brand colors interpolated from the `KpBranding` instance
  - Reference Inter via `@font-face { src: url('file:///abs/path') }` using absolute paths from `branding.font_dir`
  - Confirm `clip-path: polygon(...)` declarations port from `kp.css` unchanged; pair each with an SVG polygon fallback per ADR-4
  - _Requirements: 11.4, 11.5, 15.2, 15.5, 15.6, 16.4_

- [x] 3.3 Build the page-1 HTML
  - `_page_1(proposal, branding)` emits: corner blue/red bars, hero illustration, "КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ" headline, info grid with 11 labelled fields, items table with grand total
  - Pad items table to at least 5 rows even when fewer items provided
  - Format `amount` field with `_fmt_ru` plus "₽" suffix; format per-row sum and grand total identically
  - Emit notes box and four footer feature tiles (shield, shield-check, cog, handshake)
  - _Requirements: 3.1, 3.2, 3.5, 4.1, 4.4, 4.5, 4.6, 5.1, 5.2, 5.3_

- [x] 3.4 Build the page-2 HTML
  - `_page_2(proposal, branding)` emits: header strip with "2/2" page indicator, two-column specs+packaging cards (min 8 slots each), conditions list (min 3 slots), 6 service checkboxes, notes-2 box, contacts block with mountains illustration, footer with phone/site/email
  - 45°-rotated check indicators rendered as `<div class="c checked">` with the styling defined in 3.2
  - Service labels emitted in the fixed Russian order from REQ-9.3
  - _Requirements: 6.1, 6.2, 6.3, 7.1, 7.3, 7.4, 8.1, 8.2, 8.3, 9.1, 9.2, 9.3, 10.1, 10.2, 10.3, 10.4_

- [x] 3.5 Wire `render_proposal_html` and `render_proposal_pdf` entry points
  - `render_proposal_html(proposal, branding=MASTER_BEARING) -> str` composes `_kp_styles`, `_page_1`, `_page_2` inside a single HTML document with `<meta charset>` and `@page { size: A4; margin: 0 }`
  - `render_proposal_pdf(proposal, branding=MASTER_BEARING) -> bytes` calls `weasyprint.HTML(string=html).write_pdf()` and returns bytes
  - Expose both from `services/__init__.py` alongside the existing exports
  - _Requirements: 15.1, 15.2_

- [x] 4. (P) Backend — PDF renderer tests
- [x] 4.1 Unit tests for renderer helpers
  - `tests/services/test_kp_export_units.py`: `_fmt_ru` cases, `calc_row_total`, `calc_grand_total`, items-table padding count
  - Mark `@pytest.mark.unit`; complete in milliseconds
  - _Requirements: 3.3, 4.4, 4.5, 4.6, 4.7_

- [x] 4.2 HTML-output assertions
  - `tests/services/test_kp_export_html.py`: assert rendered HTML contains brand colors, `file://` font URLs for all 4 weights, ≥5 items table rows, ≥8 spec slots, ≥8 packaging slots, ≥3 condition slots, 6 service rows, all 4 footer feature titles
  - Drive with a `MINIMAL_PROPOSAL` fixture (one item, two specs) to exercise the padding logic
  - _Requirements: 4.4, 6.3, 7.4, 8.3, 9.2, 15.2_

- [x] 4.3 PDF integration test
  - `tests/services/test_kp_export_render.py`: `render_proposal_pdf(DEFAULT_PROPOSAL_FIXTURE)` returns bytes starting with `%PDF-`
  - Open output with `pikepdf.Pdf.open(io.BytesIO(pdf))`; assert `len(pdf.pages) == 2`
  - Assert PDF contains embedded font names matching "Inter" via `pikepdf.Pdf.docinfo` font enumeration
  - Mark `@pytest.mark.integration`
  - _Requirements: 15.1, 15.2_

- [x] 4.4 Visual regression baseline and compare
  - `tests/services/test_kp_export_visual.py`: render `DEFAULT_PROPOSAL_FIXTURE` PDF, extract structural map (text + bounding boxes per page) via `pdfminer.six`, normalize coordinates, compare against committed baseline JSON at `tests/services/__fixtures__/kp_baseline.json`
  - Add `--update-baseline` pytest CLI flag that overwrites the baseline JSON when intentional
  - Failure message must say "baseline drift; review changes and re-run with --update-baseline if intentional"
  - Mark `@pytest.mark.integration`
  - _Requirements: 17.1, 17.2, 17.3_

- [x] 5. Backend — API endpoint
- [x] 5.1 Implement `api/kp.py:render_pdf` handler
  - Validate the JWT-derived `request.state.api_user`; raise 401 via `error_response("UNAUTHORIZED", ...)` when missing
  - Parse JSON body; return 400 with `VALIDATION_ERROR` on `ValueError`
  - `_build_proposal(body)` defensively coerces missing/null fields to empty strings or empty tuples, builds nested `KpItem`/`KpPackagingItem`/`KpServices` instances
  - Call `render_proposal_pdf(proposal)`; on exception, log with `request_id`+`user_id`+`org_id` and return 500 with `RENDER_ERROR` plus `request_id`
  - On success, return `Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="kp-{date.today().isoformat()}.pdf"'})`
  - Log structured success line with `request_id`, `user_id`, `org_id`, `bytes`, `duration_ms`
  - Add the docstring per `.kiro/steering/api-first.md`
  - _Requirements: 13.3, 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8, 18.1, 18.2, 18.3, 18.4, 19.4_

- [x] 5.2 Create the thin router and wire it into the FastAPI sub-app
  - `api/routers/kp.py`: declare `APIRouter(tags=["kp"])` and a single `POST /render-pdf` delegate to `api.kp.render_pdf`
  - Edit `api/app.py`: import the router, include it with `prefix="/kp"` next to the existing `notes`/`workspace` blocks (one alphabetical insertion)
  - _Requirements: 14.1_

- [x] 5.3 Endpoint integration tests
  - `tests/api/test_kp_endpoint.py`: spin up the FastAPI sub-app via the existing test client harness
  - Cases: missing JWT → 401 `UNAUTHORIZED`, malformed JSON → 400 `VALIDATION_ERROR`, valid body → 200 with `Content-Type: application/pdf` and `Content-Disposition` containing `kp-` and today's ISO date, simulated render exception (monkeypatch `render_proposal_pdf` to raise) → 500 `RENDER_ERROR` with a `request_id` field
  - Mark `@pytest.mark.integration`
  - _Requirements: 14.5, 14.6, 14.7, 19.1, 19.2, 19.3_

- [x] 6. (P) Frontend — entity layer for proposal data
- [x] 6.1 Declare proposal types and Zod schema in `entities/kp-proposal`
  - `model/types.ts`: TypeScript interfaces mirroring the Python dataclasses field-for-field (camelCase `priceIncludes` matched to Python `price_includes` via JSON serialization adapter)
  - `model/schema.ts`: Zod schema with all fields optional, used at the submit boundary to fail fast on type drift
  - _Requirements: 14.2, 20.1_

- [x] 6.2 Static defaults and branding constants
  - `model/default-data.ts`: `DEFAULT_PROPOSAL` populated with the full example from the design's `DEFAULT_DATA`
  - `model/empty-data.ts`: `EMPTY_PROPOSAL` with empty strings, single-empty-row dynamic lists, all checkboxes false
  - `model/branding.ts`: `BRANDING` constant with primary blue, primary red, accent cream, default subtitle, footer phone/site/email — mirroring `MASTER_BEARING` on the Python side
  - _Requirements: 2.1, 2.4, 2.5, 16.3_

- [x] 6.3 Helper utilities mirroring the Python renderer
  - `lib/fmt-ru.ts`: function matching `_fmt_ru` behavior (strip spaces, comma-as-decimal, fallback to raw)
  - `lib/calc-total.ts`: `calcRowTotal(item): number | null` and `calcGrandTotal(items): number`
  - Vitest unit coverage for both, including the "non-numeric input passes through" case
  - _Requirements: 3.3, 4.5, 4.6, 4.7_

- [x] 6.4 `useKpState` hook with localStorage persistence
  - `lib/use-kp-state.ts`: state shape `{ data, setData, clear, loadExample, zoom, setZoom }`, backed by `localStorage.kvotaflow.kp.v1` and `kvotaflow.kp.v1.zoom`
  - On mount: hydrate from storage, fall back to `DEFAULT_PROPOSAL` if missing
  - On every update: persist; swallow `QuotaExceededError` silently
  - `clear()` writes `EMPTY_PROPOSAL`, `loadExample()` writes `DEFAULT_PROPOSAL` (both behind `window.confirm` in the form, not here)
  - vitest with `*.dom.test.ts` for hydrate, persist, restore, quota-fail paths
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 12.3, 12.4_

- [x] 6.5 Public API barrel
  - `entities/kp-proposal/index.ts` re-exports the public surface: types, schemas, defaults, branding, hook, helpers
  - _Requirements: 20.1_

- [x] 7. (P) Frontend — KP preview widget
- [x] 7.1 Scoped CSS module porting `kp.css`
  - `widgets/kp-preview/ui/kp-preview.module.css`: port the design's `kp.css` under a single root class `.kpPage`
  - Replace hardcoded brand colors with CSS custom properties consumed from a `style={{ '--kp-primary-blue': branding.primaryBlue, ... }}` on the root element
  - Include the `@font-face` declarations for the four Inter weights pointing at `/fonts/Inter/...`
  - _Requirements: 11.4, 11.5, 16.4_

- [x] 7.2 KP-local visual assets as React components
  - `widgets/kp-preview/ui/icons.tsx`: port the SVG icon set (`UserBadge`, `Doc`, `UserTie`, `Cal`, `Phone`, `Clock`, `Mail`, `Ruble`, `Pin`, `Pkg`, `Truck`, `Shield`, `ShieldCheck`, `Cog`, `Handshake`, `Settings`, `Gear`, `Tools`, `Wrench`, `Globe`, `Mtn`) as named exports
  - `widgets/kp-preview/ui/master-bearing-mark.tsx`: ports `BearingLogo.jsx`
  - `widgets/kp-preview/ui/illustrations.tsx`: `HeavyMachineryIllu` and `MountainIllu` referencing `/static/kp/hero-machinery.png` and `/static/kp/mountains.png`
  - _Requirements: 11.3_

- [x] 7.3 Page-1 preview component
  - `widgets/kp-preview/ui/kp-page-1.tsx`: header bars + logo + hero + headline + info grid + items table (auto-total, ≥5 rows padding) + notes box + page-1 footer features
  - Use `KpField` sub-component for the info-grid rows (icon + label + value with optional `₽` suffix)
  - Format numbers via `fmtRu` from `entities/kp-proposal`
  - _Requirements: 3.1, 3.2, 3.5, 4.1, 4.4, 4.5, 4.6, 5.1, 5.2, 5.3_

- [x] 7.4 Page-2 preview component
  - `widgets/kp-preview/ui/kp-page-2.tsx`: header strip with `2/2`, two-column specs+packaging cards (min 8 slots each), conditions section (min 3 slots), six service items, notes-2, contacts panel with mountains illustration, page-2 footer
  - 45°-rotated check indicators implemented as `<div className="c">` styled in the CSS module
  - Service labels rendered in the fixed Russian order from REQ-9.3
  - _Requirements: 6.1, 6.2, 6.3, 7.1, 7.3, 7.4, 8.1, 8.2, 8.3, 9.1, 9.2, 9.3, 10.1, 10.2, 10.3, 10.4_

- [x] 7.5 Preview toolbar with zoom controls
  - `widgets/kp-preview/ui/preview-toolbar.tsx`: "Предпросмотр · A4 · 2 страницы" title, decrement/value/increment/reset zoom controls (range 30%–120%, reset to 70%), and a slot prop for the download button
  - _Requirements: 12.1, 12.2, 12.3, 12.4_

- [x] 7.6 Preview root composition
  - `widgets/kp-preview/ui/kp-preview.tsx`: scales `<KpPage1>` and `<KpPage2>` via `transform: scale(zoom)`; sets explicit width 794px and scaled height 1123*zoom px to keep the surrounding layout from reflowing
  - Threads `data`, `zoom`, `setZoom`, and a `downloadSlot` prop from the page
  - `widgets/kp-preview/index.ts` exports `KpPreview`
  - _Requirements: 11.1, 11.2_

- [x] 8. (P) Frontend — KP form widget
- [x] 8.1 Form shell and reusable dynamic-list helper
  - `widgets/kp-form/ui/kp-form.tsx`: root container, threads `data` and `setData` (and `clear`/`loadExample` for the header)
  - `widgets/kp-form/ui/form-header.tsx`: wordmark "kvotaflow", crumb "КП · Поставка спецтехники · Master Bearing", "Очистить" and "Пример" outline buttons (both behind `window.confirm`)
  - `widgets/kp-form/lib/use-dynamic-list.ts`: hook returning `{ add, remove }` for list-typed proposal fields, immutable updates via spread
  - `widgets/kp-form/ui/kp-form.module.css`: cream background, Inter→Inter toggle for the form area, BEM-style class names; **must not import shadcn or kvotaflow design tokens directly** to avoid cross-contamination with the preview module
  - _Requirements: 1.5, 2.4, 2.5_

- [x] 8.2 Offer info, items, and notes sections (page-1 inputs)
  - `section-offer.tsx`: inputs for `subtitle`, `supplier`, `manager`, `phone`, `email`, `address`, `basis`, `payment`, `date`, `lead`, `amount`, `priceIncludes`; grouped under "Информация о предложении" with section icon
  - `section-items.tsx`: dynamic items table with per-row inputs for `name`, `model`, `qty`, `price`; add and remove controls; live row sum display
  - `section-notes.tsx`: multi-line textarea bound to `notes`
  - _Requirements: 3.1, 3.2, 3.5, 4.1, 4.2, 4.3, 5.1_

- [x] 8.3 Specs, packaging, conditions, services sections (page-2 inputs)
  - `section-specs.tsx`: dynamic list of text inputs for `specs`, with add/remove
  - `section-packaging.tsx`: dynamic list with text input + checkbox per row for `packaging`
  - `section-conditions.tsx`: dynamic list of text inputs for `conditions`
  - `section-services.tsx`: 6 fixed checkboxes bound to `services.delivery`/`training`/`supervision`/`warranty`/`commissioning`/`service`
  - _Requirements: 6.1, 7.1, 7.2, 8.1, 9.1_

- [x] 8.4 Contacts and footer section
  - `section-contacts.tsx`: textarea for `notes2`; inputs for `contact_phone`, `contact_email`, `contact_site`, `contact_address`, `foot_phone`, `foot_site`, `foot_email`; grouped with section icon
  - `widgets/kp-form/index.ts` exports `KpForm`
  - _Requirements: 10.1, 10.2, 10.3_

- [x] 8.5 Items table dom-level vitest
  - `widgets/kp-form/ui/section-items.dom.test.tsx`: render with one item, assert "add row" appends an empty entry, "remove row" removes it, qty/price inputs update parent state via `setData`
  - _Requirements: 4.1, 4.2, 4.3_

- [x] 9. Frontend — PDF download feature
- [x] 9.1 Server Action calling the Python API
  - `features/kp-pdf-download/api/render-pdf-action.ts`: validates session via `getSessionUser()`, calls `apiServerClient("/kp/render-pdf", { method: "POST", body, returnRaw: true })`
  - Returns `{ ok: true, blob }` on success or `{ ok: false, code, message, requestId? }` on failure (parse the JSON error envelope when `Content-Type` is application/json, otherwise treat as raw render failure)
  - _Requirements: 13.2, 14.5_

- [x] 9.2 Error-to-toast mapping helper
  - `features/kp-pdf-download/api/parse-error.ts`: maps `UNAUTHORIZED` → "Сессия истекла, перезагрузите страницу", `VALIDATION_ERROR` → message verbatim, `RENDER_ERROR` → "Не удалось сгенерировать PDF, попробуйте ещё раз (ID: {request_id})"
  - _Requirements: 19.1, 19.2, 19.3_

- [x] 9.3 Download button component
  - `features/kp-pdf-download/ui/download-button.tsx`: shadcn primary button with download icon, click handler runs the Server Action, on success creates a `Blob` URL and triggers an `<a>` click with `download="kp-{ISO date}.pdf"`, then revokes the URL
  - While in-flight: button is disabled, shows a spinner; on error: re-enables and surfaces the mapped message via `sonner` toast
  - `features/kp-pdf-download/index.ts` exports `DownloadKpPdfButton`
  - _Requirements: 13.1, 13.3, 13.4, 13.5_

- [x] 10. Frontend — page composition, route, and sidebar
- [x] 10.1 Page composition
  - `pages/kp-builder/ui/kp-builder-page.tsx`: split-screen layout (left form pane, right preview pane), reads `useKpState()` once at the top, passes `data`/`setData`/`clear`/`loadExample` to `<KpForm>` and `data`/`zoom`/`setZoom` plus a `<DownloadKpPdfButton data={data} />` slot to `<KpPreview>`
  - On viewports < 1024px wide: stack the form above the preview (preview becomes read-only at narrow widths per browser-test plan)
  - `pages/kp-builder/index.ts` exports `KpBuilderPage`
  - _Requirements: 1.5, 11.1_

- [x] 10.2 Route shell
  - `app/(app)/kp-builder/page.tsx`: imports and renders `<KpBuilderPage />`; relies on `(app)` layout for auth gating
  - _Requirements: 1.1, 1.3, 1.4_

- [x] 10.3 Sidebar entry
  - Edit `frontend/src/widgets/sidebar/sidebar-menu.ts`: add a `MenuItem` `{ icon: FileText, label: "КП на технику", href: "/kp-builder" }` to the `mainItems` array, gated by the same sales-role check as "Новый КП"
  - _Requirements: 1.2_

- [x] 11. End-to-end fixture and quirks log
- [x] 11.1 Shared default-proposal fixture
  - Create `tests/services/__fixtures__/default_proposal.json` matching the design's `DEFAULT_DATA` byte-for-byte
  - Make both `test_kp_export_visual.py` and `test_kp_endpoint.py` load this fixture
  - _Requirements: 17.1_

- [x] 11.2 Verify the WeasyPrint quirks log
  - After tasks 3–5 land, re-run the rendered fixture and append any new quirks discovered to the "Known WeasyPrint Quirks" section of `design.md`
  - Confirm that the three quirks already documented (font kerning, color profile, letter-spacing on uppercase) still match observed behavior
  - _Requirements: 17.4_

- [x] 12. Static guards for the out-of-scope boundary
- [x] 12.1 Lint test that the KP renderer never touches the database
  - `tests/services/test_kp_no_db.py`: regex-scan `services/kp_export.py`, `services/kp_branding.py`, `api/kp.py`, `api/routers/kp.py` for any reference to `supabase`, `from services.database`, or SQL keywords (`INSERT`, `UPDATE`, `DELETE`, `SELECT`). Fail if any match
  - Mark `@pytest.mark.unit`
  - _Requirements: 20.1, 20.2, 20.5, 20.6_
