# Requirements: POST /api/deals — API-First Deal Creation

## Context

When a quote transitions to Deal stage (specification signed), the system must create a deal record and trigger all associated side effects: logistics stages initialization and currency invoice generation. Currently this logic is split: FastHTML has the full orchestration, Next.js Server Action only does partial CRUD (missing logistics + invoices). This feature creates a proper Python API endpoint that both UI and future AI agents can call.

## Requirements

### REQ-001: API endpoint accepts specification ID and creates a deal
**EARS:** When the endpoint receives a valid spec_id with a signed scan uploaded, the system shall create a deal record linked to the specification and return the deal details.

**Acceptance:**
- `POST /api/deals` with `{spec_id, user_id, org_id}` body
- Validates spec exists, belongs to org, has `signed_scan_url` set
- Generates sequential deal number: `DEAL-{year}-{0001..9999}`
- Creates deal with status `active`, linked to specification
- Returns `{success: true, data: {deal_id, deal_number, logistics_stages, invoices_created, invoices_skipped_reason}}`

### REQ-002: Endpoint updates specification and quote statuses
**EARS:** When a deal is successfully created, the system shall update the specification status to `signed` and the quote workflow_status to `deal`.

**Acceptance:**
- Specification status updated to `signed` before deal creation
- Quote `workflow_status` updated to `deal` after deal creation
- If deal creation fails, spec status should not remain as `signed` (rollback or error)

### REQ-003: Endpoint initializes logistics stages for the deal
**EARS:** When a deal is created, the system shall initialize logistics tracking stages using the existing logistics service.

**Acceptance:**
- Calls `initialize_logistics_stages(deal_id, user_id)` from `services/logistics_service.py`
- Returns `logistics_stages` count in response
- DB failure here fails the whole request (logistics is essential for deal workflow)

### REQ-004: Endpoint generates currency invoices when data is available
**EARS:** When a deal is created and quote items have buyer companies with regions assigned, the system shall generate currency invoices. When prerequisite data is missing, the system shall skip generation and report why.

**Acceptance:**
- Fetches quote items with buyer company associations (via invoices FK)
- Fetches seller company from quote
- If buyer companies AND seller company exist:
  - Fetches enrichment data (contracts, bank accounts)
  - Calls `generate_currency_invoices()` + `save_currency_invoices()`
  - Returns `invoices_created` count in response
- If prerequisite data is missing:
  - Returns `invoices_created: 0` + `invoices_skipped_reason` explaining what's missing
  - This is NOT an error — deal creation succeeds
  - UI can display the reason to the user
- Possible skip reasons: "No buyer companies assigned to quote items", "No seller company on quote", "No items in quote"

### REQ-005: Endpoint authenticates via JWT or internal key
**EARS:** The endpoint shall accept authentication via Supabase JWT (for AI agents) or internal API key (for Next.js Server Actions), following the dual-auth pattern.

**Acceptance:**
- `Authorization: Bearer <jwt>` — validated by ApiAuthMiddleware
- During migration: unauthenticated requests pass through (middleware allows)
- Endpoint extracts user_id from request body (trusted internal call)

### REQ-006: Next.js Server Action becomes a thin wrapper
**EARS:** The existing `confirmSignatureAndCreateDeal` Server Action shall be refactored to call the Python API endpoint instead of performing direct database operations.

**Acceptance:**
- Uses `apiServerClient` to call `POST /api/deals`
- Handles file upload (signed scan) separately via Supabase Storage (unchanged)
- Calls `revalidatePath` after successful deal creation
- No direct Supabase writes for spec/deal/quote in the Server Action

### REQ-007: Endpoint has structured docstring for future OpenAPI/MCP
**EARS:** The endpoint handler shall include a structured docstring following the api-first.md documentation standard.

**Acceptance:**
- Docstring includes: Path, Params, Returns, Side Effects, Roles
- Machine-parseable format per `.kiro/steering/api-first.md`

### REQ-008: Error handling returns structured error responses
**EARS:** When validation fails or an error occurs, the endpoint shall return a structured error response.

**Acceptance:**
- Missing/invalid spec_id → `{success: false, error: {code: "NOT_FOUND", message: "..."}}`
- No signed scan → `{success: false, error: {code: "VALIDATION_ERROR", message: "Signed scan not uploaded"}}`
- Deal creation DB error → `{success: false, error: {code: "INTERNAL_ERROR", message: "..."}}`
- HTTP status codes: 400 (validation), 404 (not found), 500 (internal)
