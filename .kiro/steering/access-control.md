# Access Control & Data Visibility

**Status:** Authoritative — every new page, API, and query must follow these rules.
**Applies to:** All frontend (Next.js) and backend (FastHTML/main.py) code that reads or mutates user data.

---

## Visibility Tiers

Every role maps to one visibility tier. The tier determines how broad a user's view is across the system.

| Tier | Roles | Scope |
|------|-------|-------|
| **FULL_VIEW_EDIT** | `admin` | Everything in org, full edit |
| **FULL_VIEW_READONLY** | `top_manager` | Everything in org, no edit |
| **FULL_SCOPED_EDIT** | `quote_controller`, `spec_controller`, `finance`, `head_of_logistics` | All entities, edit only their domain fields |
| **PROCUREMENT_ALL_STAGES** | `head_of_procurement` | All quotes across all stages, edit only procurement fields |
| **PROCUREMENT_STAGE_ONLY** | `procurement_senior` | Only quotes currently in procurement stage, edit procurement fields |
| **GROUP** | `head_of_sales` | Their sales group's data, full view + edit |
| **OWN** | `sales` | Own data + customers where they are assigned |
| **ASSIGNED_ITEMS** | `procurement`, `logistics`, `customs` | Only quote/spec items personally assigned to them |

**Implementation helper (frontend):** `isSalesOnly()` / `isHeadOfSales()` in `shared/lib/roles.ts`. Add more helpers as needed — never inline role checks in query functions.

---

## Customer Access Model — Many-to-Many

**Schema:** Customers have multiple "assigned managers" via a junction table. All assignees are equal — there is no "primary" concept.

```
customers             — customer record (no manager_id for access logic)
customer_assignees    — (customer_id, user_id) pairs, many-to-many
```

**Migration plan:**
1. Create `customer_assignees` table
2. Backfill: `INSERT INTO customer_assignees SELECT id, manager_id FROM customers WHERE manager_id IS NOT NULL`
3. Update all access queries to use the junction table
4. Keep `customers.manager_id` as display-only "lead manager" (for UI convenience, not access)
5. Eventually deprecate `manager_id` once all code paths migrate

**Why many-to-many:** Two sales managers often work with the same client on different company divisions. Both need to see the customer, see their own quotes for the customer, AND see each other's quotes for that customer (shared client context).

---

## Entity-Level Rules

### Customers

| Tier | List | Detail |
|------|------|--------|
| FULL_VIEW_EDIT / FULL_VIEW_READONLY | All | All |
| FULL_SCOPED_EDIT | All | All |
| PROCUREMENT_* | **No access** | **No access** |
| GROUP (head_of_sales) | Customers where any group member is in `customer_assignees` | Same filter |
| OWN (sales) | Customers where user is in `customer_assignees` | Same filter |
| ASSIGNED_ITEMS (procurement/logistics/customs) | **No access** | **No access** |

### Quotes

| Tier | List | Detail |
|------|------|--------|
| FULL_VIEW_EDIT / FULL_VIEW_READONLY | All | All |
| FULL_SCOPED_EDIT | All | All |
| PROCUREMENT_ALL_STAGES (head_of_procurement) | All | All (edit only procurement fields) |
| PROCUREMENT_STAGE_ONLY (procurement_senior) | Quotes where `workflow_status = 'procurement'` | Same |
| GROUP (head_of_sales) | Quotes where `created_by` is in group OR customer has a group member assignee | Same |
| OWN (sales) | Quotes where `created_by = user.id` OR customer has user as assignee | Same |
| ASSIGNED_ITEMS (procurement/logistics/customs) | Quotes that contain items assigned to user | Same |

**Key rule for shared clients:** Two sales managers sharing a customer BOTH see all quotes for that customer (even if created by the other). Visibility is OR'd: created-by OR customer-assignee.

### Specifications

Specifications are the "spec stage" of a quote (1:1 via `quotes.specification_id`). **Follow the same rules as quotes** — a user who can see a quote can see its spec.

### Deals

Deals are 1:1 with specifications (`deals.specification_id`). **Follow the same rules as specs/quotes.**

### Payments & Financials

**Follow deal visibility.** A user who can see a deal can see its payments. Exceptions:
- `finance` role sees all payments
- `sales` sees payments only for deals derived from quotes they can access

### Suppliers

| Tier | List | Detail |
|------|------|--------|
| FULL_VIEW_EDIT (admin) | All | All |
| FULL_VIEW_READONLY (top_manager) | All | All |
| head_of_procurement | All | All (edit all) |
| procurement_senior | Only suppliers where user is in `supplier_assignees` | Same filter |
| procurement | Only suppliers where user is in `supplier_assignees` | Same filter |
| All other roles | **No access** | **No access** |

**Schema:** Suppliers have multiple "assigned managers" via `supplier_assignees` junction table (mirrors `customer_assignees`).

```
suppliers               — supplier record
supplier_assignees      — (supplier_id, user_id) pairs, many-to-many
```

**Auto-assign on create:** When a procurement user creates a supplier, they are automatically added to `supplier_assignees`.

**Assignee management:** Only `admin` and `head_of_procurement` can add/remove assignees. Regular procurement users see the assignees tab read-only.

**Implementation helpers:**
- `isProcurementOnly()` / `hasProcurementAccess()` / `canManageSupplierAssignees()` in `shared/lib/roles.ts`
- `getAssignedSupplierIds()` in `shared/lib/access.ts`
- `canAccessSupplier()` in `entities/supplier/queries.ts`

### Supplier Contacts & Brands

**Follow supplier visibility.** If you can see the supplier, you see its contacts and brand assignments.

### Customer Contacts & LPR

**Follow customer visibility.** If you can see the customer, you see its contacts. If not, you see nothing — contacts are sensitive.

### Calls

**Follow customer visibility.** Sales user can see calls for any customer they have access to, regardless of who logged the call.

---

## Edit Permissions

Edit is a separate concern from view. A user may see an entity but not be allowed to edit it.

| Role | Can Edit |
|------|---------|
| `admin` | Everything |
| `top_manager` | **Nothing** — view-only across the system |
| `head_of_sales` | Group's customers, quotes, contacts, calls |
| `sales` | Customers they are assigned to, own quotes, own calls |
| `head_of_procurement` | Only procurement fields on any quote |
| `procurement_senior` | Procurement fields on quotes in procurement stage |
| `procurement` | Procurement fields on their assigned items only |
| `logistics`, `customs` | Logistics/customs fields on their assigned items |
| `quote_controller` | Control/approval fields on quotes |
| `spec_controller` | Control/approval fields on specs |
| `finance` | Payment and financial fields |
| `head_of_logistics` | Logistics fields across all shipments |

**Rule:** When implementing edit, check tier → then check per-field scope → then check record ownership.

---

## Implementation Pattern

Every page/API that reads entity data must:

1. **Fetch session user** with roles
2. **Determine tier** via role helpers
3. **Apply visibility filter** to the query — never rely on RLS alone for this logic (too complex for policy SQL)
4. **For detail pages**, add an explicit `canAccess{Entity}()` guard that returns `notFound()` on deny — never leak existence via 403

**Example: Query function signature**
```typescript
async function fetchXList(
  params: Params,
  user: { id: string; roles: string[]; salesGroupId?: string | null; orgId: string }
): Promise<Result>
```

**Example: Detail page guard**
```typescript
const [entity, hasAccess] = await Promise.all([
  fetchEntityDetail(id, user.orgId),
  canAccessEntity(id, { id: user.id, roles: user.roles, orgId: user.orgId }),
]);
if (!entity || !hasAccess) notFound();
```

**Parallel, not sequential** — never sacrifice happy-path performance for a rare denial check.

---

## Helper Functions (canonical location)

All role/access helpers live in:
- `frontend/src/shared/lib/roles.ts` — role tier predicates (`isSalesOnly`, `isHeadOfSales`, `canEditProcurement`, etc.)
- `frontend/src/entities/{entity}/queries.ts` — entity-specific `canAccess{Entity}()` functions

**Do not duplicate logic.** Every role check must be in `roles.ts`. Every entity access check must be in the entity's `queries.ts`.

---

## Non-Functional Rules

- **Fail closed:** If role is unknown or ambiguous, deny access by default
- **No bypass via direct URL:** Every detail page must guard via `canAccess*` — URL-guessing is a common attack vector
- **No over-fetching:** Server components should fetch the minimum set of fields needed
- **404 on denial:** Return `notFound()` — never `403 Forbidden` for cross-user denial (leaks existence)
- **Org scope always:** Every query must filter by `organization_id` before any other filter — this is the hard outer boundary

---

## Checklist for New Pages/APIs

Before merging any feature that reads or writes user data:

- [ ] Identified the role tier(s) for this feature
- [ ] Query filters by `organization_id`
- [ ] Query applies visibility filter based on tier
- [ ] Detail page has `canAccess*` guard
- [ ] Edit actions check both visibility AND edit permission
- [ ] No role checks inlined — all go through `roles.ts` helpers
- [ ] Manually tested with at least: `sales`, `head_of_sales`, `admin` roles
- [ ] Related entities (contacts, calls, payments) inherit visibility correctly

---

## Known Limitations / TODO

- **procurement_senior** role currently has no users — Plastinina needs her role changed from `head_of_procurement` to `procurement_senior`
- **Head of X roles**: `head_of_procurement` and `head_of_logistics` are org-wide (no group), but `head_of_sales` is group-scoped — this asymmetry is intentional but may surprise future devs
- **Supplier assignees backfill**: Existing suppliers have no assignees after migration 253 — admin/head_of_procurement must assign manually
