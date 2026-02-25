# Browser Test Report

**Timestamp:** 2026-02-20T12:08:00+03:00
**Session:** 2026-02-20 #1 (re-test after fixes)
**Base URL:** https://kvotaflow.ru
**Overall:** 1/3 PASS, 1 PARTIAL, 1 FAIL

---

## Task: Screenshot capture + annotation (re-test)
**URL:** /tasks
**Status:** FAIL (not fixed)

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Login as admin | PASS | Already logged in |
| 2 | Click bug icon | PASS | Modal opens correctly |
| 3 | Type description | PASS | "Тест скриншот после фикса" entered |
| 4 | Click "Добавить скриншот" | FAIL | **Same alert: "Failed to capture screenshot. Please try again."** |
| 5 | Annotation editor opens | SKIP | Blocked — screenshot capture still fails |
| 6-9 | Annotation tools | SKIP | Blocked |
| 10 | Screenshot thumbnail | SKIP | Blocked |
| 11 | Click "Отправить" | FAIL | **NEW: 502 Bad Gateway from /api/feedback** — modal stayed open |
| 12 | Success toast | FAIL | No toast — submission failed with 502 |
| 13 | Console errors | FAIL | oklch error + 502 error |

**Console Errors:**
```
[ERROR] html2canvas error: Error: Attempting to parse an unsupported color function "oklch"
    at ue (https://html2canvas.hertzen.com/dist/html2canvas.min.js:20:74711)
[ERROR] Failed to load resource: the server responded with a status of 502 () @ /api/feedback
[ERROR] Response Status Error Code 502 from /api/feedback
```

**Root Cause — Screenshot:** html2canvas `onclone` callback fix did NOT resolve the oklch parsing error. html2canvas fails during CSS parsing before the clone callback fires. The library from `html2canvas.hertzen.com` CDN does not support oklch().

**Root Cause — 502:** The `/api/feedback` POST endpoint is now returning 502 Bad Gateway. This is a **regression** — previously (before fixes) text-only submissions returned 200 and modal closed. Now submissions fail entirely.

**Note:** Tailwind CDN still `cdn.tailwindcss.com` (fix claimed cdnjs.cloudflare.com — not deployed?)

**Screenshots:** retest-task1-502-error.png

---

## Task: Admin feedback page (re-test)
**URL:** /admin/feedback
**Status:** PASS

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Navigate via sidebar "Обращения" | PASS | Link exists under Администрирование |
| 2 | Page loads (no 500) | PASS | **Fixed! Page loads correctly** |
| 3 | Feedback list shows entries | PASS | 7 entries visible (from earlier tests) |
| 4 | Click on submission detail | PASS | Detail page loads for FB-260220115536 |
| 5 | Screenshot on detail | N/A | Entry had no screenshot (text-only) |
| 6 | Debug context info | PASS | Shows Browser: Chrome, Screen: 1584x812, URL |
| 7 | Change status to "В работе" | PASS | Dropdown works, selected "В работе" |
| 8 | Save status | PASS | Confirmation: "Сохранено: В работе" |
| 9 | Status visible in list | PASS | FB-260220115536 shows "В работе" in list |
| 10 | Status filter works | PASS | "В работе" filter shows only 1 entry correctly |
| 11 | Console errors | PASS | No errors on admin pages |

**Console Errors:** None
**Screenshots:** retest-task2-admin-feedback-list.png, retest-task2-detail-page.png

---

## Task: Text-only feedback + success toast (re-test)
**URL:** /tasks
**Status:** PARTIAL PASS

| # | Check | Result | Details |
|---|-------|--------|---------|
| 1 | Click bug icon | PASS | Modal opens |
| 2 | Select "Предложение" category | PASS | Category changed correctly |
| 3 | Type description | PASS | "Тест без скриншота" entered |
| 4 | Click "Отправить" | PASS | Submission succeeds, no errors |
| 5 | Success toast appears | PASS | **Fixed! "Спасибо! Обращение отправлено." appears** |
| 6 | Verify in /admin/feedback | PASS | New entry FB-260220120731 visible, type "Предложение" |

**Note:** Text-only submission works (this test), but submission AFTER clicking "Добавить скриншот" (and getting the oklch error) returns 502 — the failed screenshot attempt may corrupt the form state, causing subsequent submission to fail.

**Console Errors:** None during this task
**Screenshots:** retest-task3-success-toast.png

---

## Console Errors (all tasks)

1. `html2canvas error: Attempting to parse an unsupported color function "oklch"` — **NOT FIXED** — still blocks screenshot capture
2. `502 Bad Gateway from /api/feedback` — **NEW REGRESSION** — submission fails after screenshot capture attempt
3. `cdn.tailwindcss.com should not be used in production` (WARNING) — CDN change not deployed?

---

## Summary for Terminal 1

**PASS:** Task 2 (Admin feedback page) — fully working now
**PARTIAL PASS:** Task 3 (Text-only feedback) — works when no screenshot attempted, toast appears
**FAIL:** Task 1 (Screenshot + annotation) — two issues remain

**What's fixed:**
1. `/admin/feedback` page loads (was 500, now works)
2. Success toast "Спасибо! Обращение отправлено." shows after submission
3. Admin detail page, status management, filters — all work perfectly

**What's still broken:**
1. **CRITICAL: html2canvas oklch() error** — `onclone` callback fix ineffective. html2canvas parses CSS colors BEFORE cloning, so the callback never fires. Need a different approach:
   - Option A: Replace html2canvas with `html-to-image` (uses native browser serialization, supports oklch)
   - Option B: Use native Canvas API `drawImage()` on a DOM screenshot
   - Option C: Patch Tailwind config to emit rgb/hsl fallbacks instead of oklch
2. **REGRESSION: /api/feedback returns 502** after screenshot attempt fails. The failed html2canvas call may leave the form in a bad state. Check server logs: `ssh beget-kvota "docker logs kvota-onestack --tail 100 | grep -i feedback"`
3. **CDN not updated**: Still loading from `cdn.tailwindcss.com` (fix claimed `cdnjs.cloudflare.com`)

**ACTION:**
1. Fix html2canvas oklch — recommend replacing with `html-to-image` library
2. Investigate 502 regression on /api/feedback POST
3. Deploy CDN change (cdnjs.cloudflare.com for html2canvas)
