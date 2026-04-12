# Technical Design — Procurement Phase 4

## Architecture Overview

Phase 4 adds three capability groups to the invoice lifecycle, the admin panel, and the procurement workflow. Each group ships as an independent chunk.

```
Phase 4a: Invoice Send Flow + VAT Auto-Detect + Edit-After-Send Approval
Phase 4b: Bilingual Document Output (English XLS + Letter Templates)
Phase 4c: Procurement Sub-Status State Machine + Kanban Page
```

All business logic lives in Python API endpoints (per `api-first.md`). The Next.js frontend calls them via `apiServerClient`. New admin pages follow FSD structure under `app/admin/`.

### Data Flow — Phase 4a Send Flow

```
User picks country → frontend calls GET /api/geo/vat-rate
                   → auto-fills VAT rate in modal (unless manually overridden)

User clicks "Download XLS" → POST /api/invoices/{id}/download-xls
                           → Python generates XLS via openpyxl
                           → Writes invoice_letter_drafts row (method=xls_download, sent_at=NOW)
                           → Updates invoices.sent_at (denormalized)
                           → Returns file bytes

User clicks "Prepare Letter" → Opens letter-draft-composer.tsx
                             → Pre-fills from template + invoice/supplier/user data
                             → User edits, saves draft (POST /api/invoices/{id}/letter-draft)
                             → User marks as sent (POST /api/invoices/{id}/letter-draft/send)
                             → Writes invoice_letter_drafts row (method=letter_draft, sent_at=NOW)
                             → Updates invoices.sent_at

User tries to edit sent invoice → API returns 403 EDIT_REQUIRES_APPROVAL
                                → User requests approval via POST /api/invoices/{id}/edit-request-approval
                                → head_of_procurement approves → invoice unlocked → user edits → re-sends
```

### Data Flow — Phase 4c Sub-Status Transitions

```
Kanban drag → POST /api/quotes/{id}/substatus { to_substatus, reason }
           → workflow_service.transition_substatus() validates (forward/backward)
           → Writes status_history row
           → Updates quotes.procurement_substatus
           → Returns updated quote

Kanban read → GET /api/quotes/kanban?status=pending_procurement
           → Groups quotes by procurement_substatus
           → Computes days_in_state from status_history
           → Returns grouped data
```

---

## Data Model

### Migration 269: VAT Rates Table (REQ 1)

```sql
CREATE TABLE kvota.vat_rates_by_country (
  country_code CHAR(2) PRIMARY KEY,
  rate NUMERIC(5,2) NOT NULL DEFAULT 20.00,
  notes TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_by UUID REFERENCES auth.users(id)
);

-- Seed EAEU countries at 0% (VAT collected via tax declaration, not customs)
INSERT INTO kvota.vat_rates_by_country (country_code, rate, notes) VALUES
  ('RU', 0, 'Россия — внутренний рынок'),
  ('KZ', 0, 'ЕАЭС — косвенный НДС через декларацию'),
  ('BY', 0, 'ЕАЭС — косвенный НДС через декларацию'),
  ('AM', 0, 'ЕАЭС — косвенный НДС через декларацию'),
  ('KG', 0, 'ЕАЭС — косвенный НДС через декларацию');

-- Major import origin countries at standard 20% (pre-seeded for admin visibility)
INSERT INTO kvota.vat_rates_by_country (country_code, rate, notes) VALUES
  ('CN', 20, 'Китай — стандартная ставка'),
  ('TR', 20, 'Турция — стандартная ставка'),
  ('DE', 20, 'Германия — стандартная ставка'),
  ('IT', 20, 'Италия — стандартная ставка'),
  ('AE', 20, 'ОАЭ — стандартная ставка'),
  ('JP', 20, 'Япония — стандартная ставка'),
  ('KR', 20, 'Южная Корея — стандартная ставка'),
  ('IN', 20, 'Индия — стандартная ставка'),
  ('US', 20, 'США — стандартная ставка'),
  ('GB', 20, 'Великобритания — стандартная ставка');
```

### Migration 270: Invoice Send Infrastructure (REQ 4, 5, 6)

```sql
-- Denormalized "last sent" timestamp for fast filtering
ALTER TABLE kvota.invoices
  ADD COLUMN IF NOT EXISTS sent_at TIMESTAMPTZ;

-- Letter drafts table: 1:N audit trail per invoice
CREATE TABLE kvota.invoice_letter_drafts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_id UUID NOT NULL REFERENCES kvota.invoices(id) ON DELETE CASCADE,
  created_by UUID NOT NULL REFERENCES auth.users(id),
  language CHAR(2) NOT NULL DEFAULT 'ru' CHECK (language IN ('ru', 'en')),
  method VARCHAR(20) NOT NULL CHECK (method IN ('xls_download', 'letter_draft')),
  recipient_email TEXT,
  subject TEXT,
  body_text TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  sent_at TIMESTAMPTZ NULL
);

-- At most one unsent draft per invoice
CREATE UNIQUE INDEX idx_invoice_letter_drafts_one_active
  ON kvota.invoice_letter_drafts(invoice_id) WHERE sent_at IS NULL;

-- Fast lookups by invoice
CREATE INDEX idx_invoice_letter_drafts_invoice
  ON kvota.invoice_letter_drafts(invoice_id);
```

### Migration 271: English Item Names (REQ 8)

```sql
ALTER TABLE kvota.quote_items
  ADD COLUMN IF NOT EXISTS name_en TEXT;
```

### Migration 272: Procurement Sub-Status + History (REQ 10, 11)

```sql
-- Sub-status column on quotes
ALTER TABLE kvota.quotes
  ADD COLUMN IF NOT EXISTS procurement_substatus VARCHAR(30);

-- Valid (workflow_status, substatus) pairs
ALTER TABLE kvota.quotes
  ADD CONSTRAINT chk_procurement_substatus CHECK (
    (procurement_substatus IS NULL) OR
    (workflow_status = 'pending_procurement' AND procurement_substatus IN (
      'distributing', 'searching_supplier', 'waiting_prices', 'prices_ready'
    ))
  );

-- Status history audit table
CREATE TABLE kvota.status_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  quote_id UUID NOT NULL REFERENCES kvota.quotes(id) ON DELETE CASCADE,
  from_status VARCHAR(50),
  from_substatus VARCHAR(30),
  to_status VARCHAR(50),
  to_substatus VARCHAR(30),
  transitioned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  transitioned_by UUID NOT NULL REFERENCES auth.users(id),
  reason TEXT NOT NULL DEFAULT ''
);

CREATE INDEX idx_status_history_quote ON kvota.status_history(quote_id);
CREATE INDEX idx_status_history_date ON kvota.status_history(transitioned_at DESC);

-- Backfill existing procurement quotes
UPDATE kvota.quotes
  SET procurement_substatus = 'distributing'
  WHERE workflow_status = 'pending_procurement'
    AND procurement_substatus IS NULL;
```

---

## API Contracts

### 1. GET /api/geo/vat-rate (REQ 1.3, 1.4, 1.5)

**Location:** `api/geo.py` (extend existing file that has cities search)

```python
async def get_vat_rate(request):
    """Get VAT rate for a country.

    Path: GET /api/geo/vat-rate
    Params:
        country_code: str (required) — ISO 3166-1 alpha-2
    Returns:
        country_code: str
        rate: float — VAT rate percentage (e.g., 20.00)
    Roles: any authenticated user
    """
```

- Missing/invalid `country_code` → 400
- Unknown country → return default 20.00 (not 404)
- Response: `{ "success": true, "data": { "country_code": "CN", "rate": 20.00 } }`

### 2. PUT /api/admin/vat-rates (REQ 2.3, 2.4)

**Location:** `api/admin.py` (new file for admin endpoints)

```python
async def update_vat_rate(request):
    """Update VAT rate for a country.

    Path: PUT /api/admin/vat-rates
    Params:
        country_code: str (required)
        rate: float (required) — 0.00 to 100.00
        notes: str (optional)
    Returns:
        country_code: str
        rate: float
        updated_at: str
    Roles: admin
    """
```

### 3. POST /api/invoices/{id}/download-xls (REQ 4.2, 4.4)

**Location:** `api/invoices.py` (new file)

```python
async def download_invoice_xls(request, id: str):
    """Generate and download invoice as XLS, committing it as sent.

    Path: POST /api/invoices/{id}/download-xls
    Params:
        language: str (optional, default 'ru') — 'ru' or 'en'
    Returns:
        Binary XLS file (Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet)
    Side Effects:
        - Writes invoice_letter_drafts row with method='xls_download', sent_at=NOW()
        - Updates invoices.sent_at
    Roles: procurement, admin, head_of_procurement
    """
```

### 4. Letter Draft CRUD (REQ 5, 6)

**Location:** `api/invoices.py`

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/invoices/{id}/letter-draft` | GET | Fetch active (unsent) draft |
| `/api/invoices/{id}/letter-draft` | POST | Create/update active draft |
| `/api/invoices/{id}/letter-draft/send` | POST | Mark draft as sent (commit) |
| `/api/invoices/{id}/letter-draft/{draft_id}` | DELETE | Delete unsent draft |
| `/api/invoices/{id}/letter-drafts/history` | GET | Fetch all sent drafts (audit trail) |

### 5. POST /api/invoices/{id}/edit-request-approval (REQ 7.3)

**Location:** `api/invoices.py`

Delegates to `approval_service.create_approvals_for_role()` with:
- `quote_id` = parent quote (from invoice → quote join)
- `approval_type = 'edit_sent_invoice'`
- `reason` = includes `invoice_id` for traceability
- `role_codes = ['head_of_procurement', 'admin']`

### 6. Kanban + Sub-Status (REQ 10, 11)

**Location:** `api/quotes.py` (extend existing, or new `api/procurement.py`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/quotes/kanban` | GET | Quotes grouped by `procurement_substatus` with `days_in_state` |
| `/api/quotes/{id}/substatus` | POST | Transition sub-status with optional reason |
| `/api/quotes/{id}/status-history` | GET | Full transition audit log |

---

## Python Service Architecture

### services/vat_service.py (NEW — REQ 1, 3)

```python
def get_vat_rate(country_code: str) -> Decimal:
    """Lookup VAT rate. Returns 20.00 default for unknown countries."""

def list_all_rates() -> list[dict]:
    """Return all rows for admin display."""

def upsert_rate(country_code: str, rate: Decimal, notes: str | None, user_id: str) -> dict:
    """Insert or update a rate. Used by admin UI."""
```

### services/invoice_send_service.py (NEW — REQ 4, 5, 6, 7)

```python
def commit_invoice_send(
    invoice_id: str,
    user_id: str,
    method: Literal['xls_download', 'letter_draft'],
    language: str = 'ru',
    recipient_email: str | None = None,
    subject: str | None = None,
    body_text: str | None = None,
) -> dict:
    """Atomic commit: write letter_drafts row + update invoices.sent_at."""

def save_draft(invoice_id: str, user_id: str, data: dict) -> dict:
    """Create or update the active (unsent) draft for an invoice."""

def get_active_draft(invoice_id: str) -> dict | None:
    """Return the unsent draft or None."""

def get_send_history(invoice_id: str) -> list[dict]:
    """Return all sent drafts, ordered by sent_at DESC."""

def is_invoice_sent(invoice_id: str) -> bool:
    """Check if invoices.sent_at is not null (fast, uses denormalized column)."""

def check_edit_permission(invoice_id: str, user_roles: list[str]) -> bool:
    """Returns True if invoice is unsent OR user has approved edit permission."""
```

### services/xls_export_service.py (NEW — REQ 4, 8)

```python
def generate_invoice_xls(
    invoice_id: str,
    language: str = 'ru',
) -> bytes:
    """Generate XLS from invoice + assigned items. Uses openpyxl.
    Language controls column headers and item name field (name vs name_en)."""
```

### services/letter_templates.py (NEW — REQ 5, 9)

```python
LETTER_TEMPLATE_RU: str = """..."""   # Russian template with {{placeholders}}
LETTER_TEMPLATE_EN: str = """..."""   # English template with {{placeholders}}

def render_letter(
    template_lang: str,
    context: dict,  # greeting, items_list, delivery_country, incoterms, currency, sender_*
) -> tuple[str, str]:
    """Returns (subject, body_text) with all placeholders substituted.
    Uses str.format_map() with defaultdict for missing keys."""
```

### services/workflow_service.py (EXTEND — REQ 10)

Add alongside existing `StatusTransition`:

```python
@dataclass
class SubStateTransition:
    """Reusable sub-state transition definition.
    Same pattern as StatusTransition but for the sub-state axis."""
    parent_status: str
    from_substatus: str
    to_substatus: str
    allowed_roles: list[str]
    requires_reason: bool  # True for backward moves
    auto_transition: bool = False

PROCUREMENT_SUBSTATUS_TRANSITIONS: list[SubStateTransition] = [
    SubStateTransition('pending_procurement', 'distributing', 'searching_supplier', [...], False),
    SubStateTransition('pending_procurement', 'searching_supplier', 'waiting_prices', [...], False),
    SubStateTransition('pending_procurement', 'waiting_prices', 'prices_ready', [...], False),
    # Backward (require reason)
    SubStateTransition('pending_procurement', 'searching_supplier', 'distributing', [...], True),
    SubStateTransition('pending_procurement', 'waiting_prices', 'searching_supplier', [...], True),
    SubStateTransition('pending_procurement', 'prices_ready', 'waiting_prices', [...], True),
]

def transition_substatus(
    quote_id: str,
    to_substatus: str,
    user_id: str,
    user_roles: list[str],
    reason: str = '',
) -> TransitionResult:
    """Validate and execute sub-status transition. Writes status_history row."""
```

---

## Frontend Component Architecture

### Phase 4a Components

```
frontend/src/
├── app/admin/vat-rates/
│   └── page.tsx                              # NEW: admin page shell (REQ 2)
├── features/admin/
│   └── ui/vat-rates-table.tsx                # NEW: CRUD table for rates (REQ 2)
├── features/quotes/ui/procurement-step/
│   ├── invoice-card.tsx                      # MODIFY: add "Send КП" button group (REQ 4, 5)
│   ├── invoice-create-modal.tsx              # MODIFY: wire VAT auto-fill (REQ 3)
│   ├── letter-draft-composer.tsx             # NEW: form with pre-fill + preview (REQ 5)
│   ├── send-history-panel.tsx                # NEW: list of sent rows (REQ 6)
│   └── edit-approval-button.tsx              # NEW: "Edit with approval" UX (REQ 7)
├── entities/invoice/
│   ├── queries.ts                            # NEW: useVatRate, useLetterDraft, useSendHistory
│   └── mutations.ts                          # NEW: saveLetterDraft, commitSend, requestEditApproval
├── shared/lib/
│   └── api-server.ts                         # EXISTING: used by new server actions
```

### Phase 4b Components

```
├── features/quotes/ui/procurement-step/
│   ├── invoice-card.tsx                      # MODIFY: add RU/EN language toggle (REQ 8)
│   └── letter-draft-composer.tsx             # MODIFY: language toggle + EN template (REQ 9)
├── features/quotes/ui/procurement-step/
│   └── procurement-handsontable.tsx          # MODIFY: add name_en column (REQ 8)
```

### Phase 4c Components

```
├── app/procurement/kanban/
│   └── page.tsx                              # NEW: kanban page shell (REQ 11)
├── features/procurement/
│   └── ui/
│       ├── kanban-board.tsx                  # NEW: board with 4 columns (REQ 11)
│       ├── kanban-card.tsx                   # NEW: card with quote info + days (REQ 11)
│       ├── substatus-reason-dialog.tsx       # NEW: reason prompt for backward moves (REQ 11)
│       └── status-history-panel.tsx          # NEW: audit log viewer (REQ 10)
├── entities/quote/
│   ├── queries.ts                            # MODIFY: add useKanbanQuotes, useStatusHistory
│   └── mutations.ts                          # MODIFY: add transitionSubstatus
├── shared/lib/
│   └── workflow-substates.ts                 # NEW: constants mirroring Python side
├── widgets/sidebar/
│   └── sidebar.tsx                           # MODIFY: add kanban link for procurement roles
```

### Role Gating (REQ 7, 11)

- `/admin/vat-rates`: `admin` only (middleware check in `app/admin/layout.tsx`)
- `/procurement/kanban`: `procurement`, `admin`, `head_of_procurement` (layout guard)
- "Send КП" buttons: check `hasProcurementAccess()` from `shared/lib/roles.ts`
- "Edit with approval": visible only when `invoices.sent_at IS NOT NULL`
- Kanban sub-status: invisible to `sales` — parent `workflow_status` shown instead

---

## Integration Points

### VAT Auto-Fill Integration (REQ 3 → invoice-create-modal.tsx)

The modal already has `countryCode` state + CountryCombobox (Phase 3). Add:
1. New state: `vatRate: string`, `vatManuallyOverridden: boolean`
2. `useEffect` on `countryCode` change → fetch `/api/geo/vat-rate` → set `vatRate` (skip if `vatManuallyOverridden`)
3. VAT field with badge showing "manual" + reset button when overridden
4. On submit: pass `vat_rate` to `createInvoice()` → writes to `quote_items.vat_rate` for assigned items

### Send Flow Integration (REQ 4, 5 → invoice-card.tsx)

The card currently shows invoice metadata + items editor. Add:
1. Button group: "Скачать XLS" + "Подготовить письмо" — visible when invoice has items
2. After send: show "Sent at {date}" badge + "Send History" expandable section
3. If `sent_at IS NOT NULL`: hide normal edit controls, show "Edit with approval" button

### Approval Integration (REQ 7 → approval_service.py)

The existing `create_approval()` takes `quote_id`. For invoice edits:
- Pass the parent quote's `quote_id` (from `invoices.quote_id` FK)
- Include `invoice_id` in `reason` for traceability: `"Edit sent invoice {invoice_id}: {user_reason}"`
- Approval type: `'edit_sent_invoice'` (new, coexists with existing types)

### Workflow Integration (REQ 10 → workflow_service.py)

Extend the existing `ALLOWED_TRANSITIONS` pattern:
- `SubStateTransition` dataclass mirrors `StatusTransition`
- `PROCUREMENT_SUBSTATUS_TRANSITIONS` list follows the same pattern
- `_SUBSTATUS_TRANSITIONS_BY_STATUS` dict for O(1) lookup
- `transition_substatus()` function follows `perform_transition()` pattern
- `status_history` table writes happen inside the transition function

### Existing Consumer Protection (REQ 12)

| Consumer | Impact | Action |
|---|---|---|
| 331 `workflow_status` references | None | `procurement_substatus` is a separate column; existing code never reads it |
| `calculation_engine.py` | None | Frozen, not touched |
| `approval_service.py` | Extended with new `approval_type` | Backward compatible — existing types keep working |
| Phase 3 dual-write | None | VAT auto-fill reads `pickup_country_code`, does not write `pickup_country` |
| `quote_items.vat_rate` | Written by VAT auto-fill | Existing manual entry path unchanged — auto-fill only writes on country selection |

---

## Requirements Traceability

| REQ | Components | Migrations | API Endpoints | Phase |
|---|---|---|---|---|
| 1 | vat_service.py | 269 | GET /api/geo/vat-rate | 4a |
| 2 | vat-rates-table.tsx, admin page | 269 | PUT /api/admin/vat-rates | 4a |
| 3 | invoice-create-modal.tsx | — | GET /api/geo/vat-rate | 4a |
| 4 | invoice-card.tsx, xls_export_service.py | 270 | POST /api/invoices/{id}/download-xls | 4a |
| 5 | letter-draft-composer.tsx, invoice_send_service.py, letter_templates.py | 270 | GET/POST letter-draft, POST letter-draft/send | 4a |
| 6 | send-history-panel.tsx | 270 | GET letter-drafts/history | 4a |
| 7 | edit-approval-button.tsx | — | POST edit-request-approval | 4a |
| 8 | xls_export_service.py, procurement-handsontable.tsx | 271 | POST download-xls (language param) | 4b |
| 9 | letter_templates.py, letter-draft-composer.tsx | — | — | 4b |
| 10 | workflow_service.py, status-history-panel.tsx | 272 | POST substatus, GET status-history | 4c |
| 11 | kanban-board.tsx, kanban-card.tsx, substatus-reason-dialog.tsx | 272 | GET kanban, POST substatus | 4c |
| 12 | — (non-regression tests) | — | — | all |

---

## Technology Decisions

| Decision | Choice | Rationale |
|---|---|---|
| XLS generation | `openpyxl` (server-side Python) | Already in `requirements.txt`. API-first: generate on server, return file. |
| Template engine | `str.format_map()` with `defaultdict` | 8 substitutions — Jinja2 is overkill. No dependency. |
| Kanban DnD | `@dnd-kit/sortable` | Well-maintained, works with Next.js 15 RSC, lightweight. New frontend dep. |
| Admin table | Reuse existing DataTable pattern if available, or plain table with inline edit | Follow project's existing patterns in `/admin/` (check first admin page). |
| Feature flag | `NEXT_PUBLIC_SEND_FLOW_ENABLED` env var | UI buttons hidden until feature is stable on prod. Removed after validation. |
| Sub-state pattern | `SubStateTransition` dataclass + separate transitions list | Mirrors existing `StatusTransition` pattern exactly. Reusable for future departments. |

---

## Open Implementation Notes

1. **Migration numbering:** Check `ls migrations/ | tail -5` before generating. Phase 3 was 266-268. Phase 4a starts at 269 unless concurrent work shifted.
2. **XLS download atomicity:** Generate file first → on success, write drafts row + update `invoices.sent_at` in a single transaction → return file. If generation fails, no row written.
3. **Frontend type regeneration:** After each migration batch: `cd frontend && npm run db:types`.
4. **Kanban backfill:** Migration 272 backfills existing `pending_procurement` quotes to `distributing`. Run on prod Supabase. Idempotent (only updates NULL rows).
5. **Feature flag removal:** After 4a ships and passes prod smoke, remove `NEXT_PUBLIC_SEND_FLOW_ENABLED` guard and commit the removal.
