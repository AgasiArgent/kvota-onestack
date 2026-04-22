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

### Suppliers

| Tier | List | Detail |
|------|------|--------|
| FULL_VIEW_EDIT (admin) | All | All |
| FULL_VIEW_READONLY (top_manager) | All | All |
| head_of_procurement | All | All |
| procurement_senior | Assigned suppliers | Same |
| procurement | Assigned suppliers | Same |
| All other roles | **No access** | **No access** |
