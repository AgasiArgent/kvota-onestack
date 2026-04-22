# Access Control & Data Visibility

## Visibility Tiers

| Tier | Roles | Scope |
|------|-------|-------|
| **FULL_VIEW_EDIT** | `admin` | Everything |
| **FULL_VIEW_READONLY** | `top_manager` | Everything, no edit |
| **FULL_SCOPED_EDIT** | `quote_controller`, `spec_controller`, `finance`, `head_of_logistics` | All entities |
| **PROCUREMENT_ALL_STAGES** | `head_of_procurement` | All quotes |
| **PROCUREMENT_STAGE_ONLY** | `procurement_senior` | Pending procurement |
| **GROUP** | `head_of_sales` | Sales group |
| **OWN** | `sales` | Own data |
| **ASSIGNED_ITEMS** | `procurement`, `logistics`, `customs` | Assigned items |

---

## Entity-Level Rules

### Customers

| Tier | List | Detail |
|------|------|--------|
| FULL_VIEW_EDIT / FULL_VIEW_READONLY | All | All |
| FULL_SCOPED_EDIT | All | All |
| PROCUREMENT_* | **No access** | **No access** |
| GROUP (head_of_sales) | Group customers | Same |
| OWN (sales) | Own customers | Same |
| ASSIGNED_ITEMS (procurement/logistics/customs) | **No access** | **No access** |

### Quotes

| Tier | List | Detail |
|------|------|--------|
| FULL_VIEW_EDIT / FULL_VIEW_READONLY | All | All |
| FULL_SCOPED_EDIT | All | All |
| PROCUREMENT_ALL_STAGES (head_of_procurement) | All | All |
| PROCUREMENT_STAGE_ONLY (procurement_senior) | Pending procurement | Same |
| GROUP (head_of_sales) | Group quotes | Same |
| OWN (sales) | Own quotes | Same |
| ASSIGNED_ITEMS (procurement/logistics/customs) | Assigned items | Same |

### Specifications

Specifications follow the same rules as quotes.

### Suppliers

| Tier | List | Detail |
|------|------|--------|
| FULL_VIEW_EDIT (admin) | All | All |
| FULL_VIEW_READONLY (top_manager) | All | All |
| head_of_procurement | All | All |
| procurement_senior | Assigned suppliers | Same |
| procurement | Assigned suppliers | Same |
| All other roles | **No access** | **No access** |

---

## Edit Permissions

| Role | Can Edit |
|------|---------|
| `admin` | Everything |
| `top_manager` | **Nothing** — view-only |
| `head_of_sales` | Group customers, quotes |
| `sales` | Own quotes |
| `head_of_procurement` | Procurement fields |
| `procurement_senior` | Procurement stage |
| `procurement` | Assigned items |
| `logistics` | Assigned items |
| `customs` | Assigned items |
| `quote_controller` | Control fields |
| `spec_controller` | Spec control fields |
| `finance` | Payments |
| `head_of_logistics` | Logistics fields |
