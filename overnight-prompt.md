# Overnight Session - Kvota OneStack v3.0

## Your Reference Files

1. **Specification**: `.claude/autonomous/app_spec.xml` — contains DB schema, API endpoints, UI layout, success criteria (v3.0)
2. **Features**: `.claude/autonomous/features.json` — 97 features to implement with pass/fail tracking (v3.0)
3. **Protocol**: `.claude/autonomous/SESSION_PROTOCOL.md` — mandatory checklist for each session

## Project Overview

**Kvota OneStack** - система управления коммерческими предложениями с многоролевым workflow.

**Цепочка поставок (НОВОЕ в v3.0):**
```
SUPPLIER → BUYER_COMPANY → SELLER_COMPANY → CUSTOMER
(Внешний)   (Наше юрлицо    (Наше юрлицо     (Внешний)
            для закупок)    для продаж)
```

**Уровни привязки:**
- Supplier, Buyer Company → на уровне ПОЗИЦИИ (quote_item)
- Seller Company, Customer → на уровне КП (quote)

## Key Features to Implement (v3.0)

### Database (26 features: DB-001 to DB-026)
- **NEW:** suppliers table (external suppliers)
- **NEW:** buyer_companies table (our purchasing legal entities)
- **VERIFY:** seller_companies table (already exists)
- **NEW:** customer_contacts table with is_signatory for specification signatory
- **NEW:** customer_contracts with next_specification_number
- **NEW:** bank_accounts (polymorphic for all entity types)
- **NEW:** locations directory for dropdown search
- **NEW:** brand_supplier_assignments, brand_procurement_assignments
- **NEW:** route_logistics_assignments
- **EXTEND:** quotes table with idn, seller_company_id, workflow_status
- **EXTEND:** quote_items with supplier_id, buyer_company_id, pickup_location_id, logistics fields, customs fields
- **NEW:** supplier_invoices registry with items and payments
- workflow_transitions, approvals, specifications, deals, plan_fact

### IDN System (2 features: IDN-001 to IDN-002)
- Quote IDN: SELLER-INN-YEAR-SEQ (e.g., CMT-1234567890-2025-1)
- Item IDN: QUOTE_IDN-POSITION (e.g., CMT-1234567890-2025-1-001)

### Backend APIs (13 features: API-001 to API-011)
- CRUD for suppliers, buyer_companies, seller_companies
- CRUD for customers with contacts
- CRUD for locations with search endpoint for HTMX dropdown
- Brand and route assignments APIs
- Supplier invoices CRUD with payments

### Workflow (6 features: WF-001 to WF-006)
- Status transition service
- Auto-transitions (procurement complete, logistics+customs complete)
- Approval with modifications
- Quote versioning

### Specifications & Deals (6 features: SPEC/DEAL)
- Specification creation from quote version
- PDF generation (uses customer_contacts.is_signatory for signatory name)
- Signed scan upload
- Deal creation from specification

### Frontend (35 features: UI-001 to UI-035)
- Entity management pages (suppliers, buyer/seller companies, customers with contacts)
- **Location dropdown component with HTMX search** (not free text!)
- Supplier invoices registry
- Role-specific workspace views (procurement, logistics, customs)
- Workflow components (status badge, progress bar, history)
- Quote form with supply chain selectors (seller_company at quote level, supplier/buyer_company at item level)

### Telegram (4 features: TG-001 to TG-004)
- Already implemented in v2.0

### Testing (4 features: TEST-001 to TEST-004)
- Migration tests, API tests, workflow tests, permission tests

## Important Business Rules

1. **Customer contacts → Specifications**: The `is_signatory=true` contact from customer_contacts provides the signatory name for specification PDF generation.

2. **Locations dropdown**: Must be a searchable dropdown component using HTMX, not free text input.

3. **Finance role**: Does NOT approve KP! Only tracks plan-fact payments after deal is created.

4. **Top manager**: CAN modify quote values during approval (stored in approvals.modifications).

5. **Supply chain levels**:
   - seller_company_id → at QUOTE level (one for entire quote)
   - supplier_id, buyer_company_id → at QUOTE ITEM level (can vary per item)

## Instructions

1. Read and follow SESSION_PROTOCOL.md at the START of each session
2. Reference app_spec.xml when implementing — it has all technical details
3. Work through features.json one by one until all have `passes: true`
4. Update claude-progress.txt with notes after each feature
5. **Commit every 2 features** (checkpoint-interval: 2)

## Stop Conditions

- All 97 features have `passes: true`
- Stuck after 5 attempts on same issue (document blocker first)
- Max 100 iterations reached
- Max 8 hours (28800 seconds) reached
- Max $999 cost reached

## Testing Commands

```bash
# Start server
cd /Users/andreynovikov/workspace/tech/projects/kvota/onestack
python main.py

# Check feature progress
python3 -c "import json; d=json.load(open('.claude/autonomous/features.json')); done=len([f for f in d['features'] if f.get('passes')]); print(f'{done}/{len(d[\"features\"])} complete')"

# View progress log
tail -100 .claude/autonomous/claude-progress.txt
```

## Previous Completion Note

v2.0 (88 features) was completed successfully on 2026-01-15.
v3.0 adds 9 new features for supply chain entities and modifies existing features.
Start with DB-001 (suppliers table) and work through sequentially.


## Previous Context

### Completed in this session:
1. **DB-001** (suppliers table) - ✅ COMPLETE
   - Created `migrations/018_create_suppliers_table.sql`
   - External supplier companies with supplier_code, inn, kpp, contacts

2. **DB-002** (buyer_companies table) - ✅ COMPLETE
   - Created `migrations/019_create_buyer_companies_table.sql`
   - Our legal entities for purchasing with company_code, inn, kpp, ogrn
   - Director info for document signing

3. **DB-003** (seller_companies table) - ✅ COMPLETE
   - Created `migrations/020_create_seller_companies_table.sql`
   - Our legal entities for selling (quote level)
   - supplier_code, inn, kpp, ogrn, director info
   - Examples: MBR, RAR, CMT, GES, TEX

### Progress:
- v3.0 features complete: **3/94**
- Next feature: **DB-004** (customer_contacts table with is_signatory)
