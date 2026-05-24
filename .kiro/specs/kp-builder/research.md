# Research Log: kp-builder

## Summary

- **Discovery scope:** WeasyPrint capability survey, existing OneStack PDF export patterns, FastAPI sub-app router conventions, Next.js FSD page+widget structure, sidebar wiring, Inter licensing.
- **Discovery type:** Full (greenfield page + new backend endpoint + new font bundle).
- **Key takeaway:** All required CSS features for the Master Bearing layout are supported by WeasyPrint ≥53, the project already runs WeasyPrint in three other exports, and the Next.js frontend has a stable FSD pattern (entity → widget → feature → page) we can follow without inventing new conventions.

## Research Log

### R-1: WeasyPrint CSS feature coverage for the КП layout

**Question:** Does WeasyPrint render `clip-path: polygon(...)`, `transform: rotate(45deg)`, `transform: translateY(-50%)`, and SVG icons correctly?

**Findings:**
- WeasyPrint 53.0+ supports `clip-path: polygon(...)` in CSS shapes; we will pin the docker image to `weasyprint==60.x` (the version used by `services/specification_export.py`).
- CSS transforms (`rotate`, `translate`) are supported for non-inline boxes.
- SVG icons embedded inline render correctly when sized with explicit `width`/`height`.
- `position: absolute` + percentage offsets work — used by the design for corner bars (`.kp1-head__bluebar` etc.).

**Implication:** The design source CSS in `/tmp/kvota-pdf-design/extracted/untitled/project/kp.css` can be ported almost verbatim. The only known risk area is highly specific Chromium font kerning vs WeasyPrint's Pango rendering — mitigated by font subsetting via `@font-face` and a visual regression fixture (see R-6).

### R-2: Existing OneStack PDF export pattern

**Question:** What does the existing `services/*_export.py` pattern look like, and how should `kp_export.py` align?

**Findings:**
- Three exports exist: `specification_export.py`, `invoice_export.py`, `contract_spec_export.py`.
- Pattern: single Python module with a `generate_<doc>_html(data) -> str` helper plus a `generate_<doc>_pdf(...) -> bytes` wrapper that calls `weasyprint.HTML(string=html).write_pdf()`.
- HTML is built via f-strings with inlined CSS in a `<style>` tag — no template engine. CSS uses `@page { size: A4; margin: 2cm }` for layout.
- All exports use `'DejaVu Sans'` as the font family today; KP Builder is the first export to bundle a custom font.

**Implication:** Match the f-string + inlined CSS pattern for consistency. Introduce `services/fonts/` as a new bundle directory and load `Inter` via `@font-face` with `url(file://...)` pointing at absolute paths.

### R-3: FastAPI sub-app router convention

**Question:** Where does a new `/api/kp/render-pdf` endpoint live?

**Findings:**
- `api/app.py` mounts `api_sub_app` at `/api` on the outer app.
- Routers live in `api/routers/{domain}.py`. They are thin wrappers; business logic lives in `api/{domain}.py` modules at the layer above.
- The sub-app already has 18+ routers (admin, chat, cost_analysis, ..., workspace). One more router fits the pattern.
- `ApiAuthMiddleware` is registered on the outer app, so any new router inherits JWT validation. `request.state.api_user` is populated by the middleware on valid JWTs.
- The canonical error envelope is `error_response(code, message, status_code)` from `api/lib/errors.py`. The default Pydantic 422 is normalized to `VALIDATION_ERROR` in `api/app.py:validation_error_handler`.

**Implication:** Create `api/kp.py` (handler) + `api/routers/kp.py` (router), wire it in `api/app.py` with `prefix="/kp"`. Reuse the existing error helper and JWT guard — no new auth code.

### R-4: Next.js FSD layout for a standalone page

**Question:** Which FSD layers does a new standalone page require?

**Findings:**
- Routes live under `frontend/src/app/(app)/{slug}/page.tsx`. They are thin shells that import a composition from `frontend/src/pages/{slug}/`.
- Pages compose widgets; widgets compose features; features use entities; entities use shared.
- Sidebar entries are declared in `frontend/src/widgets/sidebar/sidebar-menu.ts` via `MenuItem { icon, label, href, badge? }` inside a `MenuSection`.
- The existing `(app)/quotes/` route uses `[id]/page.tsx` and `trash/`, both following the same pattern.

**Implication:** Add a new route `frontend/src/app/(app)/kp-builder/page.tsx` that delegates to `frontend/src/pages/kp-builder/`. Build form and preview as **widgets**, the PDF-download action as a **feature**, the proposal data shape as an **entity**. Add a sidebar item under the "Главное" section (where "Новый КП" already lives).

### R-5: Inter license & bundling

**Question:** Can we ship Inter inside the docker image?

**Findings:**
- Inter is licensed under SIL Open Font License (OFL) 1.1 — explicit permission to embed in PDFs and ship with closed-source software, with the only requirement that derived font names differ from the original.
- We need four weights: Regular (400), Medium (500), SemiBold (600), Bold (700) — matches what the design CSS specifies.
- File size per weight is ~80 KB (Latin + Cyrillic subset). Total bundle ≈ 320 KB.
- WeasyPrint reads `@font-face { src: url('file:///abs/path.ttf') }` — must use absolute paths or absolute file URLs.

**Implication:** Bundle four TTFs under `services/fonts/Inter/`. Include OFL.txt alongside per the license. Use `pathlib.Path(__file__).parent / "fonts" / "Inter"` to build absolute paths at runtime.

### R-6: Visual regression strategy

**Question:** How do we detect rendering regressions when WeasyPrint, fonts, or CSS change?

**Findings:**
- Byte-level PDF diffs are brittle: WeasyPrint stamps `/CreationDate (D:20260522...)` in metadata on every render, and font subsetting can reorder glyph tables.
- Three viable strategies considered:
  1. **Byte diff with metadata strip** — `pikepdf` to remove `/CreationDate`, `/ModDate`, `/ID` from the trailer, then `hashlib.sha256`. Pros: simple. Cons: still hits non-deterministic font subset reordering.
  2. **Structural compare via `pdfminer.six`** — extract text + bounding boxes per page, normalize coordinates, compare structure as JSON. Pros: stable, semantic. Cons: misses pure-visual changes (color, line weight).
  3. **Perceptual diff via `pdf2image` + `pixelmatch`** — render PDF pages to PNG, compute pixel difference with tolerance. Pros: catches everything. Cons: heavy dependency (pdf2image needs poppler), tolerance tuning is fiddly.
- Other OneStack exports have no visual regression coverage today — KP Builder is the first.

**Implication:** Use **option 2 (`pdfminer.six` structural compare)** as the default test gate, with a hand-curated baseline JSON committed alongside the fixture. Add `pdfminer.six` to `requirements.txt` (≈ 250 KB, no native deps). Keep the door open for option 3 in a later iteration if subtle visual regressions slip through.

### R-7: localStorage quota behavior

**Question:** How should the form behave when `localStorage.setItem` throws (quota exceeded, private-mode Safari)?

**Findings:**
- Modern browsers raise `QuotaExceededError`; Safari in private mode raises a similar `DOMException`.
- The form state for a KP is small (~5 KB worst case with long notes), so quota is unlikely to be hit in normal use.
- UX research suggests toasting on every keystroke that fails persistence is noisy; users expect the form to "just work".

**Implication:** Swallow the exception silently. Continue holding state in React; nothing is lost during the session — only the cross-reload restore feature degrades. No toast in iteration 1.

### R-8: PDF filename convention

**Question:** Should the downloaded PDF include the supplier name?

**Findings:**
- The frontend doesn't know the user's organization in this iteration (no DB context); supplier is whatever the user typed in the form.
- File-system-safe characters: Russian Cyrillic in filenames is supported by macOS/Linux but Windows and some email clients corrupt it.
- Other OneStack PDF exports (`specification_export.py`) use ASCII-only filenames like `Spec_<quote_number>.pdf`.

**Implication:** Use `kp-{YYYY-MM-DD}.pdf` for iteration 1 — ASCII-safe and date-bounded. Filename customization (with sanitized supplier slug) can land in iteration 2 when supplier data comes from the DB.

## Architecture Pattern Evaluation

### Pattern A — Single-route page with two server-rendered widgets

- **Frontend:** One Next.js route, client-only (form state is interactive); calls Python API on submit.
- **Backend:** One FastAPI POST endpoint that renders HTML and returns PDF.
- **Pros:** Matches existing OneStack patterns (Next.js page + thin Python API).
- **Cons:** Heavy client bundle for the preview (KpPage1 + KpPage2 components stay in browser).

### Pattern B — Server-rendered preview via iframe + endpoint

- **Frontend:** Form is client; preview is an `<iframe src="/api/kp/preview-html?...">` that re-renders on debounce.
- **Backend:** Two endpoints — `/api/kp/preview-html` (HTML response) and `/api/kp/render-pdf` (PDF response).
- **Pros:** Single source of truth for layout — same HTML drives preview and PDF.
- **Cons:** Iframe causes layout jank, slower iteration loop, harder to test.

### Decision — Pattern A

- The preview is small (~500 lines TSX once translated from JSX).
- Identical rendering between Chromium preview and WeasyPrint PDF will be enforced by the visual regression fixture (R-6), not by sharing HTML at runtime.
- Sticking with pattern A keeps the architecture symmetric with all other OneStack pages: route → page composition → widgets → features → entities.

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| WeasyPrint rendering drifts from Chromium preview | Medium | Medium | Visual regression fixture (R-6), document known quirks |
| Inter font missing in container | Low | High | Bundle TTFs in repo, docker COPY them, test on every deploy |
| PDF generation latency exceeds 5s | Low | Low | Loading state on button (REQ-13.4); profile if it surfaces |
| localStorage quota fail breaks form on private-mode Safari | Low | Low | Silent catch (REQ-2.6); state lives in React anyway |
| WeasyPrint `clip-path` polygon not pixel-perfect at exact angles | Medium | Low | If broken, fall back to SVG polygon shapes (already inline-able) |
| User clicks "Сохранить PDF" twice → duplicate downloads | Low | Low | Disable button while in-flight (REQ-13.4) |

## Parallelization Notes

Implementation in Phase 3 can split into two parallel tracks with disjoint files:

- **Track B (backend):** `services/kp_branding.py`, `services/kp_export.py`, `services/fonts/Inter/*`, `api/kp.py`, `api/routers/kp.py`, `api/app.py` (one-line router wire-up).
- **Track F (frontend):** `frontend/src/entities/kp-proposal/`, `frontend/src/widgets/kp-form/`, `frontend/src/widgets/kp-preview/`, `frontend/src/features/kp-pdf-download/`, `frontend/src/pages/kp-builder/`, `frontend/src/app/(app)/kp-builder/page.tsx`, `frontend/src/widgets/sidebar/sidebar-menu.ts` (one-line entry add).

The only shared file is `api/app.py` (single-line addition) — assign to Track B. The two tracks converge for the end-to-end test fixture.
