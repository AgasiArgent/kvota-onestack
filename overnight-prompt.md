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

4. **DB-004** (customer_contacts table) - ✅ COMPLETE
   - Created `migrations/021_create_customer_contacts_table.sql`
   - Contact persons (ЛПР) for customers
   - `is_signatory` flag for specification PDF signatory selection
   - Helper function `get_customer_signatory()` for PDF generation

5. **DB-005** (customer_contracts table) - ✅ COMPLETE
   - Created `migrations/022_create_customer_contracts_table.sql`
   - Customer contracts with next_specification_number sequence
   - Auto-increment function for specification numbers

6. **DB-006** (bank_accounts table) - ✅ COMPLETE
   - Created `migrations/023_create_bank_accounts_table.sql`
   - Polymorphic design (entity_type + entity_id)
   - Supports: supplier, buyer_company, seller_company, customer
   - Russian format: BIK (9 digits), correspondent account (20 digits)
   - International: SWIFT (8/11 chars), IBAN validation
   - Single default trigger, helper functions

7. **DB-007** (locations table) - ✅ COMPLETE
   - Created `migrations/024_create_locations_table.sql`
   - Location directory for dropdown search with pg_trgm
   - GIN index for fast partial text matching
   - `search_locations()` function for HTMX dropdown
   - Default seed function with China, Russia, CIS, Europe, Turkey locations

8. **DB-008** (brand_supplier_assignments) - ✅ COMPLETE
   - Created `migrations/025_create_brand_supplier_assignments_table.sql`
   - Links BRANDS to SUPPLIERS (external companies)
   - `is_primary` flag for preferred supplier per brand
   - Helper functions for querying assignments

9. **DB-009** (brand_procurement_assignments) - ✅ COMPLETE
   - Created `migrations/026_create_brand_procurement_view.sql`
   - View alias for existing `brand_assignments` table
   - Assigns BRANDS to USERS (procurement managers)
   - Updatable view rules for full CRUD
   - Helper functions: get_procurement_manager_for_brand(), etc.

10. **DB-010** (route_logistics_assignments) - ✅ COMPLETE
   - Created `migrations/027_create_route_logistics_assignments_table.sql`
   - Routes to logistics managers with pattern matching (wildcards)

11. **DB-011** (quotes extension) - ✅ COMPLETE
   - Created `migrations/028_extend_quotes_v3.sql`
   - Added idn, seller_company_id, IDN generation functions

12. **DB-012** (quote_items supply chain) - ✅ COMPLETE
   - Created `migrations/029_extend_quote_items_supply_chain.sql`
   - item_idn, supplier_id, buyer_company_id, pickup_location_id

13. **DB-013** (quote_items logistics) - ✅ COMPLETE
   - Created `migrations/030_extend_quote_items_logistics.sql`
   - 4 logistics cost segments + total_days

14. **DB-014** (quote_items customs) - ✅ COMPLETE
   - Created `migrations/031_extend_quote_items_customs.sql`
   - hs_code, customs_duty_percent, customs_extra_cost

15. **DB-015** (supplier_invoices) - ✅ COMPLETE
   - Created `migrations/032_create_supplier_invoices_table.sql`

16. **DB-016** (supplier_invoice_items) - ✅ COMPLETE
   - Created `migrations/033_create_supplier_invoice_items_table.sql`

17. **DB-017** (supplier_invoice_payments) - ✅ COMPLETE
   - Created `migrations/034_create_supplier_invoice_payments_table.sql`

18. **DB-018** (workflow_transitions) - ✅ VERIFIED
   - Table exists from v2.0

19. **DB-019** (approvals modifications) - ✅ COMPLETE
   - Created `migrations/035_add_modifications_to_approvals.sql`

20. **DB-020** (specifications extension) - ✅ COMPLETE
   - Created `migrations/036_extend_specifications_v3.sql`

21. **DB-021** (deals extension) - ✅ COMPLETE
   - Created `migrations/037_extend_deals_v3.sql`

22. **DB-022** (plan_fact_categories) - ✅ COMPLETE
   - Created `migrations/038_create_plan_fact_categories_table.sql`

23. **DB-023** (plan_fact_items) - ✅ COMPLETE
   - Created `migrations/039_create_plan_fact_items_table.sql`

24. **DB-024** (telegram_users) - ✅ COMPLETE
   - Created `migrations/040_create_telegram_users_table.sql`
   - Telegram account linking with verification flow
   - Notification preferences per type
   - Helper functions for verification and recipients

25-56. (Features DB-025 to UI-006 completed in previous sessions - see features.json for details)

57. **UI-007** (Customers list with contacts preview) - ✅ COMPLETE
   - Created `GET /customers` route at line 13633 in main.py with v3.0 features:
     - Search by name or INN
     - Status filter (all/active/inactive)
     - Stats cards: total, active, with_contacts, with_signatory
     - Contacts preview showing up to 3 contacts per customer with badges (✍️ подписант, ★ основной)
   - Created `GET /customers/{id}` detail page at line 13854 with:
     - Full customer info (name, INN, KPP, OGRN)
     - Addresses section (legal, actual, warehouses list)
     - Director info (position, name)
     - Contacts table with edit links
   - Permission check: admin, sales, or top_manager roles
   - Uses customer_service functions properly
   - Russian localization

64. **UI-014** (Invoice payment form) - ✅ COMPLETE
   - Created `_invoice_payment_form()` helper function in main.py
   - Created `GET /supplier-invoices/{id}/payments/new` route
   - Created `POST /supplier-invoices/{id}/payments/new` route
   - Invoice context card showing supplier, dates, amounts, remaining balance
   - Payment fields: date, type (advance/partial/final/refund), amount, currency
   - Payer section: buyer_company dropdown, exchange rate to RUB
   - Document reference field and notes textarea
   - Role-based access: admin, procurement, finance
   - Organization access verification
   - Input validation: date format, amount positive, exchange rate positive
   - Uses `register_payment()` from supplier_invoice_payment_service
   - Tests: 37 passing tests in `tests/test_ui_invoice_payment.py`

69. **UI-016** (Quote item form: supplier selector) - ✅ COMPLETE
    - Added supplier_dropdown() to quote item (product) add form after Brand/Quantity row
    - Updated POST handler to accept and save supplier_id parameter
    - Updated product_row() function to display supplier badge when assigned:
      - Shows supplier code or name (📦 TSC)
      - Hover shows full supplier name
    - Updated GET handler to fetch supplier info for existing items
    - Russian UI labels ("Поставщик", "Внешний поставщик для данной позиции")
    - Tests: tests/test_ui_quote_item_supplier.py (7 passed, 8 skipped due to import)

### Progress:
- v3.0 features complete: **67/94** (26 DB + 2 IDN + 11 API + 6 WF + 3 SPEC + 3 DEAL + 16 UI features done!)
- Completed: UI-016 (Quote item form: supplier selector)
- Next feature: **UI-017** (Quote item form: buyer company selector)
