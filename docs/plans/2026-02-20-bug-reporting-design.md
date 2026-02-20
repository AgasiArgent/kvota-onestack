# Bug Reporting System Improvement — Design Doc

**Date:** 2026-02-20
**Status:** Approved
**Context:** Beta test with 19 MasterBearing users (medium tech skill)

---

## Problem

Current bug widget (grey icon, bottom-right) sends text-only feedback to Telegram. No screenshots, no annotation, no admin UI, no task tracking. For beta testing, need richer reports with maximum auto-collected context.

## Solution

Enhance existing widget with: auto-screenshot (html2canvas), canvas-based annotation editor (3 tools), admin UI, ClickUp integration, Telegram with photo.

---

## 1. User Flow

1. Click bug icon → modal opens (category, text, "Добавить скриншот" button)
2. "Добавить скриншот" → modal hides, html2canvas captures page, fullscreen editor opens
3. Annotation editor (fullscreen overlay):
   - Toolbar: Кисть (red free-draw), Стрелка (click+drag arrow), Текст (click to place + type)
   - Undo button, Готово (save), ✕ (cancel)
4. Back to modal with screenshot thumbnail, user submits
5. Auto-context collected: URL, user agent, screen size, roles, console errors, timestamp

## 2. Data Architecture

New columns in `kvota.user_feedback`:
- `screenshot_data` TEXT — base64 PNG
- `context_json` JSONB — auto-collected debug context
- `clickup_task_id` TEXT — nullable, filled after ClickUp task created
- `status` TEXT DEFAULT 'new' — new/in_progress/resolved/closed

## 3. Backend

- **POST `/api/feedback`** (extend): accept screenshot + context, save, create ClickUp task, send Telegram photo
- **GET `/admin/feedback`** (new): table of all feedback with status management, screenshot display, context viewer

## 4. Integrations

- **Telegram**: photo attachment via `sendPhoto` API (decode base64), caption with category + user + description + ClickUp link
- **ClickUp**: auto-create task in "Bug Reports" list, title `[Category] description...`, body with context + admin link

## 5. Annotation Editor

HTML5 Canvas, ~150-200 lines vanilla JS:
- Brush: mousemove → ctx.lineTo(), red 3px stroke
- Arrow: mousedown→mouseup → line + arrowhead with rotation math
- Text: click → positioned input → on blur → ctx.fillText()
- Undo: array of canvas state snapshots, pop last
- Export: canvas.toDataURL('image/png')
