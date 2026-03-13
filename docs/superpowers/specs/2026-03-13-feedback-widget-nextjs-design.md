# Feedback Widget — Next.js Migration Design

**Date:** 2026-03-13
**Status:** Draft
**Depends on:** Phase 1 Foundation (scaffold, auth, layout, API middleware)

---

## Problem

Feedback widget ("жучок") lives in FastHTML monolith. Three bugs were fixed (short_id race condition, screenshot overflow, false success toast), but the architecture has inherent fragility: base64 screenshots in DB column, inline JS in Python strings, no type safety. As part of the strangler fig migration, this widget becomes the first real React component on the Next.js foundation.

## Scope

Migrate the feedback widget to a React component in Next.js. The widget:
- Appears on all Next.js pages (global layout component)
- Captures screenshot + annotation
- Submits via existing Python API `/api/feedback` (with JWT auth)
- Uploads screenshots to Supabase Storage (replaces base64-in-DB)

FastHTML widget remains on FastHTML pages until those pages are migrated.

---

## Architecture

### Data Flow

```
User clicks bug icon
  → React modal opens
  → html2canvas captures screenshot
  → Annotation editor (canvas)
  → On submit:
      1. Upload screenshot to Supabase Storage (feedback-screenshots bucket)
      2. POST /api/feedback with { description, type, screenshot_url, debug_context }
      3. Python API: insert DB + ClickUp + Telegram (existing logic)
  → Success: close modal, show toast
  → Error: show message + retry button
```

### FSD Placement

```
src/
├── features/
│   └── feedback/
│       ├── ui/
│       │   ├── FeedbackButton.tsx      # Floating bug icon
│       │   ├── FeedbackModal.tsx        # Modal with form
│       │   ├── ScreenshotCapture.tsx    # html2canvas + annotation
│       │   └── AnnotationEditor.tsx     # Canvas drawing tools
│       ├── api/
│       │   └── submitFeedback.ts        # Upload screenshot + POST /api/feedback
│       ├── lib/
│       │   └── debugContext.ts          # Collect URL, console errors, etc.
│       └── index.ts                     # Public API: export { FeedbackButton }
```

Layer 3 (features) — correct: it's a user action, not a business entity. Imports from `shared/` only (Supabase client, API client, UI primitives).

### Screenshot Storage

**Bucket:** `feedback-screenshots` in Supabase Storage
**Path:** `{org_id}/{short_id}.jpg`
**Access:** Authenticated upload (RLS: user must be authenticated), public read (for admin viewing)
**Compression:** Client-side resize to max 1280px + JPEG quality 0.7 (same as current fix)

### API Changes

**`/api/feedback` endpoint updates:**
1. Accept `screenshot_url` field (string, URL to Supabase Storage) in addition to existing `screenshot` (base64)
2. If `screenshot_url` is provided, store it in a new `screenshot_url` column
3. If `screenshot` (base64) is provided, continue existing behavior (backward compat for FastHTML widget)
4. Admin detail page: render from `screenshot_url` if present, fall back to `screenshot_data` base64

**New DB column:**
```sql
ALTER TABLE kvota.user_feedback ADD COLUMN screenshot_url TEXT;
```

### Components

**FeedbackButton** — Floating button, bottom-right, z-50. Uses Lucide `Bug` icon. Opens modal on click. Renders in root layout so it's on every page.

**FeedbackModal** — shadcn Dialog component. Form fields:
- Type selector (bug / ux_ui / suggestion / question) — shadcn Select
- Description textarea — required
- Screenshot section: capture button + thumbnail preview + annotation
- Hidden debug context (auto-collected)
- Submit button with loading state

**ScreenshotCapture** — Uses `html2canvas` to capture current page. Compresses to JPEG. Opens AnnotationEditor overlay.

**AnnotationEditor** — Canvas overlay for drawing on screenshot. Tools: brush (red), arrow, text. Undo stack. Save returns compressed JPEG data URL.

**submitFeedback** — Orchestrates submission:
1. If screenshot exists: upload to Supabase Storage, get public URL
2. POST to `/api/feedback` with form data + screenshot_url
3. Return success/error

### Auth

Widget uses Supabase session (JWT). The `/api/feedback` endpoint is protected by `ApiAuthMiddleware` (Phase 1). User identity comes from JWT — no session dependency.

### Error Handling

- Screenshot capture fails → allow submission without screenshot, show warning
- Storage upload fails → fall back to base64 via existing `screenshot` field
- API call fails → show error message + retry button in modal
- No silent failures — every error is visible to user

---

## What Changes in Python

1. **New column:** `screenshot_url TEXT` on `user_feedback`
2. **Endpoint update:** Accept `screenshot_url` in POST body, store in new column
3. **Admin page:** Prefer `screenshot_url` over `screenshot_data` for display
4. **Supabase Storage:** Create `feedback-screenshots` bucket via migration or manual setup

## What Stays the Same

- ClickUp integration (existing, called from Python)
- Telegram notification (existing, called from Python)
- `short_id` generation (already fixed)
- Base64 path for FastHTML widget (backward compat)
- Admin feedback list/detail pages (FastHTML, unchanged except screenshot display)

---

## Key Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| API approach | Existing `/api/feedback` | No logic duplication, integrations already work |
| Screenshot storage | Supabase Storage | No size limits, proper file storage, CDN-friendly |
| Annotation | Custom canvas editor | Matching existing functionality, no heavy dependency |
| FSD layer | `features/feedback/` | User action, not entity — correct FSD placement |
| Fallback | Base64 if Storage fails | Graceful degradation, never lose user's feedback |
