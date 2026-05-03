# МОП/РОП Test Triage — 2026-05-03

**Source:** `Project kvotaflow - МОП Тест.csv` + `Project kvotaflow - РОП Тест.csv`
**Testers:** bokov.a@masterbearing.ru (МОП = sales) + ekaterina.kravtsova@masterbearing.ru (РОП = head_of_sales)
**Verification mode:** browser session as both users + source code grep for root causes

---

## Already Resolved (no work needed)

| ID | Item | Verification | Why already fixed |
|----|------|--------------|-------------------|
| **C16/C17** | МОП create customer with/without ИНН → error page | Created Газпром (с ИНН) and "Новый клиент 20260503-1412" (без ИНН) under bokov.a — both succeeded, redirected to customer profile | PR #76 (`fix(customers): crash on note save + invisible МОП-created customers`) |
| **RC16/RC17** | РОП same crash | Same browser flow under kravtsova.e creates customers cleanly | Same PR #76 |
| **RC1** | РОП customer list пуст / "не отражаются" | kravtsova.e sees `Всего: 161` including own customers (АО "Р-ФАРМ") + subordinates (Александр Боков, Екатерина Макарова) | `getAssignedCustomerIds()` already unions `customer_assignees` + `manager_id`, scoped via `resolveScopedUserIds` for `head_of_sales` group. Working as designed. |
| **M14** | РОП "Все" tab in /messages не показывает чаты подчинённых | kravtsova.e "Все" tab shows 4 chats incl. bokov.a's Q-202604-0075. Clicking shows full thread. | Group-scoped subordinate visibility wired correctly |
| **M4** | "Должность не отражается возле имени" | Visible in both /messages and quote chat: "Александр Боков / Продажи / 29 апр. 14:55" | Already shows role |

---

## Confirmed Tracks (work needed)

### Track A — `searchCustomers` ownership leak (Q10/Q19/RQ10/RQ19) **P5**

**File:** `frontend/src/entities/quote/mutations.ts:123-144`

**Current behavior** (verified in browser as bokov.a — 13 customers in his list):
Typed "ООО" in "Новый КП" → Клиент field → dropdown shows ООО "Астра", ООО "АЭМЗ", ООО "АВАНГАРД" etc. — system-wide companies, not bokov.a's 13.

**Root cause:** `searchCustomers` query at `mutations.ts:129-135`:
```ts
.from("customers")
.select("id, name, inn")
.eq("organization_id", orgId)        // ← only org filter
.or(`name.ilike.%${q}%,inn.ilike.%${q}%`)
```
No `assigned_user_id` / `manager_id` filter. Compare with `fetchCustomersList` (entities/customer/queries.ts:55-63) which gates on `isSalesOnly` + `getAssignedCustomerIds()`.

**Secondary bug:** Typed " 7707083893" (leading space, INN of СБЕРБАНК which exists) → picker shows "Создать: ПАО СБЕРБАНК" suggestion = duplicate creation for an existing customer because the search wasn't trimmed.

**Fix:**
1. Make `searchCustomers` accept `user: { id, roles, salesGroupId, orgId }` and apply the same `isSalesOnly + getAssignedCustomerIds` filter as `fetchCustomersList`
2. Trim `query` before `.ilike` and before passing to DaData lookup
3. `searchCustomers` callers (`create-quote-dialog.tsx`) must thread current user + group context

**Closes:** Q10 (МОП), Q19 (МОП ownership bypass — downstream of Q10), RQ10 (РОП), RQ19 (РОП)

---

### Track B — Sidebar "Новый КП" missing for head_of_sales (S5) **P4**

**File:** `frontend/src/widgets/sidebar/sidebar-menu.ts:72`

**Current:**
```ts
if (hasRole("sales", "sales_manager")) {
  mainItems.push({ icon: PlusCircle, label: "Новый КП", href: "/quotes?create=true" });
}
```

**Verified:** РОП kravtsova.e sidebar links: Обучение / Сообщения / Обновления / Обзор / Клиенты / Коммерческие предложения. **No "Новый КП"**. МОП bokov.a has it.

**Fix:** add `"head_of_sales"` to the gate. РОП has same quote-creation permission (and per Q10 the dialog itself works for them).

**Closes:** S5

---

### Track C — Chat date/time formatting (M5/M6/QP8/QP9) **P3**

Affects both /messages chat list AND in-thread message timestamps for ALL users (not RU-specific).

**Symptoms verified:**
- Chat list left sidebar: `3 дн / 4 дн` (relative) — bug expects absolute "DD.MM"
- Live freshly-sent message: shows "только что / час назад" until refresh, then snaps to "29 апр. 14:55"
- After page refresh, in-thread is fine (`29 апр. 14:55`)

**Likely files** (need code-explore in implementation phase):
- `frontend/src/features/chat/**` or `frontend/src/widgets/messages/**` — date formatter
- Live message format on optimistic insert (likely `formatDistanceToNow`) — should mount with absolute format from the start

**Fix:**
1. Chat list timestamps: switch from `formatDistanceToNow` to absolute `dd MMM` (e.g., "29 апр")
2. New messages on send: optimistic insert should use the same formatter as historical messages so no "только что" → snap

**Closes:** M5, M6, QP8, QP9 (4 items dedup'd into one fix)

---

### Track D — Chat file upload broken in /messages (M9-M13, RPQ12-17) **P3 / P4**

**Symptoms (per CSV, not re-tested in browser — clear from report):**
- M9 (МОП): file via paperclip without message → file disappears, no chat entry
- M10: file with message → only text appears, file lost
- M12/M13: same via drag-and-drop
- RPQ11-17 (РОП on quote chat): "появилась ошибка" when attaching, file not delivered

**Note:** Quote-page chat (КП profile) for МОП passes M11-M17 (file upload works there). The break is specifically in `/messages` page chat (and RPQ in quote chat for РОП — possibly RLS on message_attachments).

**Code suspects** (need code-explore):
- `frontend/src/features/chat-attachment/**` (touched in PR #80 per recent log)
- `services/messages` API endpoints
- RLS on `messages` / `message_attachments` for `head_of_sales`

**Fix needs investigation** — start with code-explore to map current flow.

**Closes:** M9, M10, M12, M13 (МОП /messages); RPQ11-17 (РОП quote chat) — possibly two distinct bugs

---

### Track E — Quote profile UX papercuts (QP2/QP3/QP4/QP5) **P3**

5 separate UI bugs on quote detail documents tab:
- **QP2:** drag-drop dotted zone не активна (no event handler bound)
- **QP3:** Кнопка удалить файл не удаляет (likely DELETE endpoint missing or 403)
- **QP4:** Кнопка скачать открывает файл в новой вкладке вместо download (missing `download` attr or `Content-Disposition`)
- **QP5:** Закрытие документов возвращает на этап "Заявка" вместо последнего открытого этапа (state-not-preserved on toggle close)

**Code suspects:** `frontend/src/features/quote-documents/**` or quote profile page tabs.

**Fix:** small individual fixes — probably one PR with 4 commits or a single touched-file PR.

**Closes:** QP2, QP3, QP4, QP5

---

### Track F — Long ФИО truncation in chat list (M3) **P3**

Browser snapshot did not visibly truncate ("Александр Боков", "Екатерина Кравцова" full). Likely a CSS issue at narrower widths or specific to chat preview cards. Need quick browser inspection at smaller width.

**Fix:** likely add `text-overflow: ellipsis; max-width:` or `min-width: 0` on flex parent.

**Closes:** M3

---

### Track G — Quote table view persistence (Q3/RQ3) **P3**

When user saves a custom column view, then switches back to "Все" preset, the saved view's columns persist instead of full default set.

**Code suspect:** `frontend/src/features/quotes/ui/quotes-table-client.tsx` — view selection logic likely shares a single `selectedColumns` state regardless of view preset.

**Fix:** keep "Все" preset's columns hardcoded to full default; only custom presets persist.

**Closes:** Q3

---

### Track H (Optional) — Items table dropdown bug (QP22, RPQ22) **P3**

"Дропдаун ед. бажно открывается" — likely Handsontable dropdown editor positioning issue (re-fits poorly with 2-3 items already filled). Needs browser repro.

Defer unless trivial to investigate.

---

## Scope Recommendation

**Mandatory P5 (block release):**
- Track A — searchCustomers leak (Q10/Q19/RQ10/RQ19)

**Strong P4 (1-line / 1-file each, low cost):**
- Track B — sidebar gate (S5)

**P3 — quality batch (consolidates 8+ visible bugs into ~3 fixes):**
- Track C — chat date/time format (M5+M6+QP8+QP9 = 1 fix)
- Track E — quote docs UX (QP2-5 = 1 PR with 4 small fixes)
- Track F — ФИО truncation (M3 = CSS fix)

**P3 — needs investigation before scoping:**
- Track D — chat file upload (M9-M13, RPQ11-17). Spawn code-explore in spec phase to determine scope.
- Track G — table view persistence (Q3)

**Defer:**
- Track H — Handsontable dropdown UX (low impact, hard to fix without browser repro)

---

## Pre-flight Notes

- **Browser test creds:** Mb2026Beta! works for both bokov.a and kravtsova.e
- **Created junk customer during verification:** `c767f62e-a322-4bab-b709-d5672d483e29` ("Новый клиент 20260503-1412") and `0cdbbf86-3d87-4fef-a8b9-da22120280df` (ПАО ГАЗПРОМ) — owned by bokov.a. Optional cleanup before/after fix work.
- **Localhost browser test for Q10:** localhost:3000 + prod Supabase via `frontend/.env.local`. Auth: bokov.a creds work against prod Supabase from local Next.js.
