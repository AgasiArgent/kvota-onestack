# API-First Architecture

## Principle

Every business operation must be accessible through a documented API endpoint. The system serves two equally important consumers: **humans** (via Next.js UI) and **AI agents** (via REST/MCP).

## The Rule

```
Business logic → Python API endpoint (single source of truth)
Next.js Server Action → thin wrapper: auth + call API + revalidate cache
AI agent → calls the same API endpoint directly
```

**Never put business logic in Server Actions.** Server Actions are UI glue — they validate the session, call the Python API, revalidate Next.js cache, and return. If an operation can't be performed by an AI agent without a browser, the architecture is wrong.

## What Goes Where

### Python API (`/api/*`) — Business Logic

Operations that involve business rules, multi-step orchestration, or side effects:

- **Workflow transitions** — quote status changes, deal creation, approvals
- **Document generation** — currency invoices, PDFs, exports
- **Calculations** — pricing, markups, totals
- **Side effects** — creating child entities (deal → logistics stages → currency invoices)
- **Integrations** — DaData, Telegram notifications, HERE geocoding

Pattern:
```python
@app.post("/api/deals")
async def create_deal(request):
    # 1. Validate input
    # 2. Execute business logic (via services)
    # 3. Return structured JSON response
    return {"success": True, "data": {"deal_id": ..., "invoices_created": ...}}
```

### Next.js Server Actions — UI Orchestration Only

Server Actions handle:
- Session validation (`getSessionUser()`)
- Calling Python API via `apiServerClient` (JWT forwarded automatically)
- Revalidating Next.js cache (`revalidatePath`, `revalidateTag`)
- Formatting response for UI consumption

Pattern:
```typescript
"use server";
import { apiServerClient } from "@/shared/lib/api-server";

export async function createDeal(specId: string) {
  const user = await getSessionUser();
  if (!user) throw new Error("Unauthorized");

  const res = await apiServerClient("/deals", {
    method: "POST",
    body: JSON.stringify({
      spec_id: specId,
      user_id: user.id,
      org_id: user.orgId,
    }),
  });
  if (!res.success) throw new Error(res.error?.message || "Failed");

  revalidatePath(`/quotes`);
  return res;
}
```

`apiServerClient` (in `shared/lib/api-server.ts`) handles JWT forwarding via `PYTHON_API_URL` env var, so Server Actions don't need to construct URLs or auth headers manually.

### Supabase Direct — Simple CRUD Only

Read queries and simple single-table updates that have no business rules or side effects:
- Fetching lists with filters and FK joins (quotes, customers, invoices)
- Updating a single data field (display name, description, boolean flag)
- Real-time subscriptions

**NOT Supabase direct:** Status transitions (e.g. `workflow_status`), anything that should trigger notifications, create child records, or update related entities.

**Test:** If the operation **writes to 2+ tables**, triggers side effects, or has conditional business logic — it goes through the Python API, not Supabase direct. Multi-table **reads** (FK joins) are fine via Supabase, unless they require authorization logic beyond what RLS provides — those reads go through Python API too.

## API Endpoint Standards

### Authentication

All `/api/*` endpoints use `Authorization: Bearer <jwt>` — Supabase JWT forwarded from Next.js or sent directly by AI agents.

The `ApiAuthMiddleware` validates the JWT and sets `request.state.api_user`. During migration, if no JWT is present, the middleware passes through (handlers can fall back to FastHTML session auth). After migration, all endpoints will require JWT.

See `strangler-fig-auth.md` for the dual-auth pattern during migration.

### Response Format

Success — include `data`, omit `error`:
```json
{
  "success": true,
  "data": { ... }
}
```

Error — include `error`, omit `data`:
```json
{
  "success": false,
  "error": { "code": "VALIDATION_ERROR", "message": "spec_id is required" }
}
```

For paginated list endpoints, include pagination inside `data` (overrides `api-design.md` which places it in `meta` — this keeps the response flatter):
```json
{
  "success": true,
  "data": { "items": [...], "pagination": { "cursor": "...", "has_more": true } }
}
```

Validation errors may include an additional `fields` key with per-field details:
```json
{
  "success": false,
  "error": { "code": "VALIDATION_ERROR", "message": "Missing required fields", "fields": {"spec_id": "required"} }
}
```

### Naming

- **Resource CRUD:** REST nouns — `POST /api/deals` (create), `GET /api/deals/{id}`, `PATCH /api/deals/{id}`
- **Business actions:** verb sub-resources — `POST /api/quotes/{id}/calculate`, `POST /api/specs/{id}/confirm-signature`. This extends common REST conventions: some operations don't map cleanly to CRUD, so actions use verb sub-resources on the parent entity.
- **List endpoints:** follow common pagination rules (see `api-design.md`). Cursor-based for feeds, offset/limit for admin tables. Every list endpoint requires a `limit` parameter.
- Group by business domain, not technical layer

### Versioning

Internal API is unversioned during strangler fig migration (overrides common `api-design.md` versioning rule). When versioning is introduced post-migration, existing unversioned `/api/*` paths will continue to work as v1 (no breaking change). New versions will use `/api/v2/...`.

## Checklist: Adding a New Business Operation

1. Does this operation have business logic, side effects, or **write** to multiple tables?
   - **Yes** → Python API endpoint + Server Action wrapper
   - **No** (simple read or single-table write) → Supabase direct is fine

2. Write the Python API endpoint first:
   - Input validation
   - Business logic (call existing services or create new one)
   - Structured JSON response
   - Auth (JWT Bearer via `ApiAuthMiddleware`)

3. Write the Server Action as a thin wrapper:
   - `getSessionUser()` for auth
   - `apiServerClient()` to call Python API (handles JWT + base URL)
   - `revalidatePath()` / `revalidateTag()`
   - Return typed result

4. Document the endpoint with a structured docstring (see below)

## Endpoint Documentation Standard

Every `/api/*` handler must have a structured docstring in this format:

```python
async def create_deal(request):
    """Create a deal from a confirmed specification.

    Path: POST /api/deals

    Params:
        spec_id: str (required) — Specification to convert to deal
        user_id: str (required) — Acting user
        org_id: str (required) — Organization

    Returns:
        deal_id: str — Created deal ID
        invoices_created: int — Number of currency invoices generated

    Side Effects:
        - Creates deal record linked to specification
        - Creates logistics stages for the deal
        - Generates currency invoices based on deal items

    Roles: sales, admin
    """
```

**Why this matters:** This format is machine-parseable. It feeds:
1. **Now:** AI coding agents understand what endpoints do and how to call them
2. **Soon:** Auto-generated OpenAPI spec when migrating to FastAPI (docstring → Pydantic models)
3. **Later:** MCP tool definitions generated from OpenAPI (name, description, input schema, output schema)

**Rules:**
- `Path:` — HTTP method + URL pattern, one line
- `Params:` — one line per param: `name: type (required|optional) — description`
- `Returns:` — one line per field in the `data` response object
- `Side Effects:` — bullet list of what gets created/updated/deleted/notified beyond the primary resource
- `Roles:` — comma-separated list of roles that can call this endpoint
- Omit sections that don't apply (e.g., GET endpoints with no side effects)

## AI Agent Readiness (Roadmap)

The documentation standard above is step 1 of a three-step path to full AI agent support:

1. **Now:** Structured docstrings on all `/api/*` handlers (machine-readable documentation)
2. **Post-migration:** FastAPI with Pydantic models replaces docstrings (auto-generated OpenAPI spec)
3. **When API is stable:** MCP server generated from OpenAPI + `llms.txt` at site root + AI agents authenticate via JWT

## Migration Status

**New code must follow the API-first pattern.** Existing code has migration debt — some workflow transitions still go direct to Supabase.

Already migrated to Python API:
- `completeProcurement`, `completeCustoms`, `skipCustoms`, `cancelQuote`, `submitToProcurement`

Still going direct to Supabase (migration debt):
- Simple status writes (`entities/quote/mutations.ts`): `completeLogistics`, `sendToClient`, `acceptQuote`, `rejectQuote`, `requestChanges`, `approveQuote`
- Multi-table writes that should be migrated first:
  - `returnQuoteForRevision`, `escalateQuote` (`entities/quote/mutations.ts`) — write to `quotes` + `quote_comments` non-atomically
  - `createInvoice` (`entities/quote/mutations.ts`) — writes to `invoices` + `invoice_cargo_places`
  - `confirmSignatureAndCreateDeal` (`features/quotes/ui/specification-step/mutations.ts`) — writes to `specifications` + `deals` + `quotes` (3 tables)
  - `assignBrandGroup` (`features/procurement-distribution/api/mutations.ts`) — writes to `quote_items` + `brand_assignments`

**Priority:** Migrate multi-table writes first (they need transactions), then simple status writes as side effects are added.

## Edge Cases

- **File uploads:** Upload to Supabase Storage directly (signed URLs). If the upload triggers business logic (e.g. document processing), call a Python API endpoint after upload with the storage path.
- **Batch operations:** Single Python API endpoint (`POST /api/items/batch`), not N individual calls from a Server Action loop.
- **Webhooks/callbacks:** External services calling back are another API consumer — they hit the same `/api/*` endpoints with auth (API key or JWT).
- **Long-running operations:** If a Python API call may exceed 30s (e.g. PDF generation with many pages), consider background processing with a status-polling pattern. Out of scope during migration.

## Anti-Patterns

- **Business logic in Server Actions** — untestable, inaccessible to agents, no API contract
- **Direct DB writes for multi-step operations** — skips side effects, breaks consistency
- **Duplicating Python logic in TypeScript** — one source of truth per operation
- **FastHTML HTML handlers as API** — return JSON from `/api/*`, not HTML from route handlers

---
_The measure of good architecture: an AI agent and a human can accomplish the same tasks._
