# API-First Architecture

Every business operation must be accessible through a Python API endpoint. The system serves two equal consumers: humans (Next.js UI) and AI agents (REST/MCP).

## Where Logic Lives

| Operation type | Where | Example |
|----------------|-------|---------|
| Business logic, workflows, side effects | Python API (`/api/*`) | Deal creation, currency invoice generation, workflow transitions |
| Simple CRUD, reads, single-field writes (no multi-table writes, no notifications, no child records) | Supabase direct | Fetch quotes list, update a display name, toggle a boolean flag |
| UI orchestration | Next.js Server Action (thin wrapper) | Auth check → call Python API → revalidate cache |

## The Test

Before writing a Server Action, ask: **"Can an AI agent do this without a browser?"**
- **No** → wrong architecture. Extract to Python API endpoint first.
- **Yes** → proceed.

## Server Action Pattern (Thin Wrapper)

```typescript
"use server";
import { apiServerClient } from "@/shared/lib/api-server";

export async function createDeal(specId: string) {
  const user = await getSessionUser();                    // 1. Auth
  const res = await apiServerClient("/deals", {           // 2. Call Python API
    method: "POST",
    body: JSON.stringify({ spec_id: specId, user_id: user.id }),
  });
  if (!res.success) throw new Error(res.error?.message || "Failed");
  revalidatePath("/quotes");                              // 3. Cache
  return res;                                             // 4. Return
}
```

`apiServerClient` (in `shared/lib/api-server.ts`) handles JWT forwarding, absolute URL (`PYTHON_API_URL`), and typed responses.

**Never put business logic in Server Actions.** No multi-table writes, no side effects, no conditional orchestration.

## Python API Endpoint Pattern

```python
@app.post("/api/deals")
async def create_deal(request):
    # Validate → execute business logic (via services) → return JSON
    return {"success": True, "data": {"deal_id": ..., "invoices_created": ...}}
```

Auth: `Authorization: Bearer <jwt>` — Supabase JWT forwarded from Next.js or sent directly by AI agents. Session fallback for legacy FastHTML routes (see `strangler-fig-auth.md`).

> **Note:** Internal API is unversioned during strangler fig migration (overrides common `api-design.md` versioning rule). Versioning will be added when the API stabilizes post-migration.

## Endpoint Documentation (for future OpenAPI/MCP)

Every `/api/*` handler must have a structured docstring:

```python
async def create_deal(request):
    """Create a deal from a confirmed specification.

    Path: POST /api/deals
    Params:
        spec_id: str (required) — Specification to convert
        user_id: str (required) — Acting user
    Returns:
        deal_id: str — Created deal ID
        invoices_created: int — Number generated
    Side Effects:
        - Creates logistics stages
        - Generates currency invoices
    Roles: sales, admin
    """
```

This format feeds future OpenAPI spec and MCP tool generation. See steering doc for full details.

## Anti-Patterns

- Business logic in Server Actions (inaccessible to agents, untestable via API)
- Duplicating Python logic in TypeScript (two sources of truth)
- Multi-table writes from Next.js without Python API (skips side effects)
- FastHTML HTML handlers as API (return JSON from `/api/*`, not HTML)

Full architecture details: `.kiro/steering/api-first.md`
