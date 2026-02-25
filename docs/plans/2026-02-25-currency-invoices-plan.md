# Currency Invoices — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Auto-generate internal currency invoices between group companies when a deal is signed, with editing, registry, and DOCX/PDF export.

**Architecture:** New service `currency_invoice_service.py` handles generation logic + regeneration. Routes added to `main.py` for UI (deal tab, detail page, registry). Export via `currency_invoice_export.py` using python-docx. Triggered automatically in the existing deal-creation flow at `/spec-control/{spec_id}/confirm-signature`.

**Tech Stack:** FastHTML/HTMX (existing), PostgreSQL (kvota schema), openpyxl (existing), python-docx (new dependency), pytest (existing)

**Design doc:** `docs/plans/2026-02-25-currency-invoices-design.md`

---

## Dependency Graph

```
Task 1 (migrations) ──┬──→ Task 2 (generation service) ──→ Task 3 (hook into deal creation)
                      │                                            ↓
                      ├──→ Task 7 (DOCX export service) ──→ Task 8 (PDF export)
                      │                                            ↓
                      └──→ Task 4 (deal tab) → Task 5 (detail page) → Task 6 (registry)
                                                     ↓
                                              Task 9 (tasks integration)
                                                     ↓
                                              Task 10 (regeneration)
```

**Parallelizable:** Task 2 + Task 7 (different service files). All main.py tasks (3-6, 9-10) are sequential.

---

## Task 1: Database Schema + Role

**Files:**
- Create: `migrations/185_create_currency_invoices.sql`
- Create: `migrations/186_create_currency_invoice_items.sql`
- Create: `migrations/187_add_currency_controller_role.sql`

**Step 1: Write migration 185 — currency_invoices table**

```sql
-- migrations/185_create_currency_invoices.sql
CREATE TABLE IF NOT EXISTS kvota.currency_invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id UUID NOT NULL REFERENCES kvota.deals(id) ON DELETE CASCADE,
    segment TEXT NOT NULL CHECK (segment IN ('EURTR', 'TRRU')),
    invoice_number TEXT UNIQUE NOT NULL,
    seller_entity_type TEXT NOT NULL CHECK (seller_entity_type IN ('buyer_company', 'seller_company')),
    seller_entity_id UUID,
    buyer_entity_type TEXT NOT NULL CHECK (buyer_entity_type IN ('buyer_company', 'seller_company')),
    buyer_entity_id UUID,
    markup_percent DECIMAL(5,2) NOT NULL DEFAULT 2.0,
    total_amount DECIMAL(15,2),
    currency VARCHAR(3) NOT NULL DEFAULT 'EUR',
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'verified', 'exported')),
    source_invoice_ids UUID[],
    generated_at TIMESTAMPTZ DEFAULT now(),
    verified_by UUID REFERENCES auth.users(id),
    verified_at TIMESTAMPTZ,
    organization_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_currency_invoices_deal ON kvota.currency_invoices(deal_id);
CREATE INDEX IF NOT EXISTS idx_currency_invoices_status ON kvota.currency_invoices(status);
CREATE INDEX IF NOT EXISTS idx_currency_invoices_org ON kvota.currency_invoices(organization_id);

-- RLS
ALTER TABLE kvota.currency_invoices ENABLE ROW LEVEL SECURITY;

CREATE POLICY currency_invoices_org_isolation ON kvota.currency_invoices
    USING (organization_id = current_setting('app.current_organization_id')::uuid);

INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (185, '185_create_currency_invoices.sql', now())
ON CONFLICT (id) DO NOTHING;
```

**Step 2: Write migration 186 — currency_invoice_items table**

```sql
-- migrations/186_create_currency_invoice_items.sql
CREATE TABLE IF NOT EXISTS kvota.currency_invoice_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    currency_invoice_id UUID NOT NULL REFERENCES kvota.currency_invoices(id) ON DELETE CASCADE,
    source_item_id UUID REFERENCES kvota.quote_items(id),
    product_name TEXT NOT NULL,
    sku TEXT,
    idn_sku TEXT,
    manufacturer TEXT,
    quantity DECIMAL(12,3) NOT NULL DEFAULT 0,
    unit TEXT DEFAULT 'pcs',
    hs_code TEXT,
    base_price DECIMAL(15,4) NOT NULL DEFAULT 0,
    price DECIMAL(15,4) NOT NULL DEFAULT 0,
    total DECIMAL(15,2) NOT NULL DEFAULT 0,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_currency_invoice_items_invoice ON kvota.currency_invoice_items(currency_invoice_id);
CREATE INDEX IF NOT EXISTS idx_currency_invoice_items_source ON kvota.currency_invoice_items(source_item_id);

-- RLS via parent join
ALTER TABLE kvota.currency_invoice_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY currency_invoice_items_via_parent ON kvota.currency_invoice_items
    USING (currency_invoice_id IN (
        SELECT id FROM kvota.currency_invoices
        WHERE organization_id = current_setting('app.current_organization_id')::uuid
    ));

INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (186, '186_create_currency_invoice_items.sql', now())
ON CONFLICT (id) DO NOTHING;
```

**Step 3: Write migration 187 — currency_controller role**

```sql
-- migrations/187_add_currency_controller_role.sql
INSERT INTO kvota.roles (organization_id, slug, name, description, is_system_role)
SELECT o.id, 'currency_controller', 'Контролёр валютных документов',
       'Проверка и экспорт валютных инвойсов между компаниями группы', false
FROM kvota.organizations o
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.roles
    WHERE slug = 'currency_controller' AND organization_id = o.id
);

INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (187, '187_add_currency_controller_role.sql', now())
ON CONFLICT (id) DO NOTHING;
```

**Step 4: Apply migrations**

```bash
bash scripts/apply-migrations.sh
```

**Step 5: Commit**

```bash
git add migrations/185_create_currency_invoices.sql migrations/186_create_currency_invoice_items.sql migrations/187_add_currency_controller_role.sql
git commit -m "feat: add currency_invoices schema and currency_controller role (migrations 185-187)"
```

---

## Task 2: Currency Invoice Generation Service

**Files:**
- Create: `services/currency_invoice_service.py`
- Create: `tests/test_currency_invoice_service.py`
- Reference: `services/database.py` (Supabase client pattern)
- Reference: `conftest.py` (fixtures: make_quote, make_quote_item)

**Context:** This service contains the core generation logic. It takes deal data + procurement invoice items, groups them, determines segments, calculates prices with markup, and creates currency_invoices + currency_invoice_items records.

**Step 1: Write failing tests for generation logic**

Test file: `tests/test_currency_invoice_service.py`

Test scenarios:
1. **EU buyer → generates 2 invoices (EURTR + TRRU)** — buyer_company has country="EU", should create 2 currency invoices
2. **TR buyer → generates 1 invoice (TRRU only)** — buyer_company has country="TR", should create 1 currency invoice
3. **Multiple procurement invoices with same buyer_company → merged into 1 currency invoice per segment** — 2 invoices from different EU suppliers with same buyer_company produce 1 EURTR + 1 TRRU (not 2+2)
4. **Price calculation: EURTR segment** — base_price * 1.02 (default markup)
5. **Price calculation: TRRU segment from EU chain** — base_price * 1.02 * 1.02 (two markups cumulative)
6. **Price calculation: TRRU segment from TR chain** — base_price * 1.02 (one markup only)
7. **Custom markup percent** — if markup changed from 2% to 3%, prices recalculate
8. **Invoice numbering** — format `CI-{quote_idn}-{currency}-{segment}-{seq}`
9. **Items snapshot** — currency_invoice_items contain correct product_name, sku, idn_sku, manufacturer, quantity, unit, hs_code from source quote_items
10. **TRRU invoice contains ALL items** — items from both EU and TR procurement invoices merge into TRRU

```python
# tests/test_currency_invoice_service.py
import pytest
from decimal import Decimal
from services.currency_invoice_service import (
    generate_currency_invoices,
    calculate_segment_price,
    build_invoice_number,
    group_items_by_buyer_company,
)


# --- Price calculation tests ---

def test_calculate_segment_price_eurtr():
    """EURTR segment: base_price * (1 + markup/100)"""
    result = calculate_segment_price(
        base_price=Decimal("100.00"),
        segment="EURTR",
        markup_percent=Decimal("2.0"),
        prior_markup_percent=None,
    )
    assert result == Decimal("102.00")


def test_calculate_segment_price_trru_from_eu():
    """TRRU from EU chain: base_price * (1 + eurtr_markup/100) * (1 + trru_markup/100)"""
    result = calculate_segment_price(
        base_price=Decimal("100.00"),
        segment="TRRU",
        markup_percent=Decimal("2.0"),
        prior_markup_percent=Decimal("2.0"),  # EURTR markup applied first
    )
    assert result == Decimal("104.04")


def test_calculate_segment_price_trru_from_tr():
    """TRRU from TR chain: base_price * (1 + markup/100), no prior segment"""
    result = calculate_segment_price(
        base_price=Decimal("100.00"),
        segment="TRRU",
        markup_percent=Decimal("2.0"),
        prior_markup_percent=None,
    )
    assert result == Decimal("102.00")


def test_calculate_segment_price_custom_markup():
    """Custom 3% markup instead of default 2%"""
    result = calculate_segment_price(
        base_price=Decimal("100.00"),
        segment="EURTR",
        markup_percent=Decimal("3.0"),
        prior_markup_percent=None,
    )
    assert result == Decimal("103.00")


# --- Invoice numbering tests ---

def test_build_invoice_number():
    result = build_invoice_number(
        quote_idn="Q202601-0004",
        currency="EUR",
        segment="EURTR",
        sequence=1,
    )
    assert result == "CI-Q202601-0004-EUR-EURTR-1"


def test_build_invoice_number_usd_trru():
    result = build_invoice_number(
        quote_idn="Q202601-0004",
        currency="USD",
        segment="TRRU",
        sequence=1,
    )
    assert result == "CI-Q202601-0004-USD-TRRU-1"


# --- Grouping tests ---

def test_group_items_by_buyer_company_merges_same_company():
    """Multiple procurement invoices with same buyer_company merge into one group"""
    items = [
        {"id": "item-1", "buyer_company_id": "bc-1", "product_name": "Item A"},
        {"id": "item-2", "buyer_company_id": "bc-1", "product_name": "Item B"},
        {"id": "item-3", "buyer_company_id": "bc-2", "product_name": "Item C"},
    ]
    groups = group_items_by_buyer_company(items)
    assert len(groups) == 2
    assert len(groups["bc-1"]) == 2
    assert len(groups["bc-2"]) == 1


# --- Generation integration tests ---

def test_generate_eu_buyer_creates_two_invoices():
    """EU buyer_company -> 2 currency invoices (EURTR + TRRU)"""
    buyer_companies = {
        "bc-eu": {"id": "bc-eu", "name": "EuroInvest", "country": "EU"},
    }
    seller_company = {"id": "sc-ru", "name": "MB Rus", "entity_type": "seller_company"}
    items = [
        {
            "id": "item-1", "buyer_company_id": "bc-eu",
            "product_name": "Bearing", "sku": "BRG-001", "idn_sku": "IDN-001",
            "brand": "SKF", "quantity": Decimal("100"), "unit": "pcs",
            "hs_code": "8482.10", "purchase_price_original": Decimal("50.00"),
            "purchase_currency": "EUR",
        },
    ]
    result = generate_currency_invoices(
        deal_id="deal-1",
        quote_idn="Q202601-0004",
        items=items,
        buyer_companies=buyer_companies,
        seller_company=seller_company,
        organization_id="org-1",
    )
    assert len(result) == 2
    segments = {inv["segment"] for inv in result}
    assert segments == {"EURTR", "TRRU"}


def test_generate_tr_buyer_creates_one_invoice():
    """TR buyer_company -> 1 currency invoice (TRRU only)"""
    buyer_companies = {
        "bc-tr": {"id": "bc-tr", "name": "MB TR", "country": "TR"},
    }
    seller_company = {"id": "sc-ru", "name": "MB Rus", "entity_type": "seller_company"}
    items = [
        {
            "id": "item-1", "buyer_company_id": "bc-tr",
            "product_name": "Seal", "sku": "SL-001", "idn_sku": "IDN-002",
            "brand": "NOK", "quantity": Decimal("200"), "unit": "pcs",
            "hs_code": "4016.93", "purchase_price_original": Decimal("10.00"),
            "purchase_currency": "USD",
        },
    ]
    result = generate_currency_invoices(
        deal_id="deal-1",
        quote_idn="Q202601-0004",
        items=items,
        buyer_companies=buyer_companies,
        seller_company=seller_company,
        organization_id="org-1",
    )
    assert len(result) == 1
    assert result[0]["segment"] == "TRRU"


def test_generate_trru_contains_all_items():
    """TRRU invoice should contain ALL items (from both EU and TR chains)"""
    buyer_companies = {
        "bc-eu": {"id": "bc-eu", "name": "EuroInvest", "country": "EU"},
        "bc-tr": {"id": "bc-tr", "name": "MB TR", "country": "TR"},
    }
    seller_company = {"id": "sc-ru", "name": "MB Rus", "entity_type": "seller_company"}
    items = [
        {
            "id": "item-1", "buyer_company_id": "bc-eu",
            "product_name": "EU Item", "sku": "EU-001", "idn_sku": "IDN-001",
            "brand": "SKF", "quantity": Decimal("10"), "unit": "pcs",
            "hs_code": "8482.10", "purchase_price_original": Decimal("100.00"),
            "purchase_currency": "EUR",
        },
        {
            "id": "item-2", "buyer_company_id": "bc-tr",
            "product_name": "TR Item", "sku": "TR-001", "idn_sku": "IDN-002",
            "brand": "NOK", "quantity": Decimal("20"), "unit": "pcs",
            "hs_code": "4016.93", "purchase_price_original": Decimal("50.00"),
            "purchase_currency": "USD",
        },
    ]
    result = generate_currency_invoices(
        deal_id="deal-1",
        quote_idn="Q202601-0004",
        items=items,
        buyer_companies=buyer_companies,
        seller_company=seller_company,
        organization_id="org-1",
    )
    trru = [inv for inv in result if inv["segment"] == "TRRU"][0]
    assert len(trru["items"]) == 2  # both EU and TR items


def test_generate_items_snapshot_fields():
    """Currency invoice items contain all required snapshot fields"""
    buyer_companies = {
        "bc-tr": {"id": "bc-tr", "name": "MB TR", "country": "TR"},
    }
    seller_company = {"id": "sc-ru", "name": "MB Rus", "entity_type": "seller_company"}
    items = [
        {
            "id": "item-1", "buyer_company_id": "bc-tr",
            "product_name": "Bearing XYZ", "sku": "BRG-XYZ", "idn_sku": "IDN-42",
            "brand": "Timken", "quantity": Decimal("500"), "unit": "kg",
            "hs_code": "8482.10.90", "purchase_price_original": Decimal("25.50"),
            "purchase_currency": "USD",
        },
    ]
    result = generate_currency_invoices(
        deal_id="deal-1",
        quote_idn="Q202601-0004",
        items=items,
        buyer_companies=buyer_companies,
        seller_company=seller_company,
        organization_id="org-1",
    )
    item = result[0]["items"][0]
    assert item["product_name"] == "Bearing XYZ"
    assert item["sku"] == "BRG-XYZ"
    assert item["idn_sku"] == "IDN-42"
    assert item["manufacturer"] == "Timken"
    assert item["quantity"] == Decimal("500")
    assert item["unit"] == "kg"
    assert item["hs_code"] == "8482.10.90"
    assert item["base_price"] == Decimal("25.50")
    assert item["price"] == Decimal("26.01")  # 25.50 * 1.02
    assert item["total"] == Decimal("13005.00")  # 500 * 26.01
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_currency_invoice_service.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'services.currency_invoice_service'`

**Step 3: Implement `services/currency_invoice_service.py`**

Core functions to implement:
- `calculate_segment_price(base_price, segment, markup_percent, prior_markup_percent)` → Decimal
- `build_invoice_number(quote_idn, currency, segment, sequence)` → str
- `group_items_by_buyer_company(items)` → dict[str, list]
- `generate_currency_invoices(deal_id, quote_idn, items, buyer_companies, seller_company, organization_id, markup_percent=2.0)` → list[dict]
- `save_currency_invoices(supabase, invoices)` → list[dict] (DB persistence)
- `regenerate_currency_invoices(supabase, deal_id, ...)` → list[dict] (delete old + re-generate)

The `generate_currency_invoices` function is pure logic (no DB), returns dicts ready for insertion.
The `save_currency_invoices` function handles Supabase inserts.

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_currency_invoice_service.py -v
```

Expected: all PASS

**Step 5: Commit**

```bash
git add services/currency_invoice_service.py tests/test_currency_invoice_service.py
git commit -m "feat: add currency invoice generation service with tests"
```

---

## Task 3: Hook Generation into Deal Creation

**Files:**
- Modify: `main.py` — route `/spec-control/{spec_id}/confirm-signature` (around line 26335)
- Reference: `services/currency_invoice_service.py`

**Context:** The deal is created at `/spec-control/{spec_id}/confirm-signature` POST handler. After the deal INSERT (line 26335) and logistics init (line 26350), we add currency invoice generation.

**Step 1: Write failing test**

Test file: `tests/test_currency_invoice_generation_hook.py`

Test scenario: After deal creation, currency_invoices table should have records. This is an integration test that mocks the Supabase calls.

```python
# tests/test_currency_invoice_generation_hook.py
import pytest
from unittest.mock import MagicMock, patch
from services.currency_invoice_service import generate_currency_invoices, save_currency_invoices


def test_save_currency_invoices_inserts_records():
    """save_currency_invoices should insert into currency_invoices and currency_invoice_items"""
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [{"id": "ci-1"}]

    invoices = [
        {
            "deal_id": "deal-1",
            "segment": "EURTR",
            "invoice_number": "CI-Q202601-0004-EUR-EURTR-1",
            "seller_entity_type": "buyer_company",
            "seller_entity_id": "bc-eu",
            "buyer_entity_type": None,
            "buyer_entity_id": None,
            "markup_percent": 2.0,
            "total_amount": 102.00,
            "currency": "EUR",
            "status": "draft",
            "source_invoice_ids": [],
            "organization_id": "org-1",
            "items": [
                {
                    "source_item_id": "item-1",
                    "product_name": "Bearing",
                    "sku": "BRG-001",
                    "idn_sku": "IDN-001",
                    "manufacturer": "SKF",
                    "quantity": 100,
                    "unit": "pcs",
                    "hs_code": "8482.10",
                    "base_price": 100.00,
                    "price": 102.00,
                    "total": 10200.00,
                    "sort_order": 0,
                },
            ],
        },
    ]

    save_currency_invoices(mock_supabase, invoices)

    # Should insert into currency_invoices table
    mock_supabase.table.assert_any_call("currency_invoices")
    # Should insert into currency_invoice_items table
    mock_supabase.table.assert_any_call("currency_invoice_items")
```

**Step 2: Run test → verify FAIL**

```bash
pytest tests/test_currency_invoice_generation_hook.py -v
```

**Step 3: Implement save_currency_invoices in service + wire into main.py**

In `main.py`, after deal INSERT (around line 26350), add:

```python
# --- Generate currency invoices ---
try:
    from services.currency_invoice_service import generate_currency_invoices, save_currency_invoices

    # Fetch quote items with buyer_company info
    quote_items_resp = supabase.table("quote_items").select(
        "*, buyer_companies!buyer_company_id(id, name, country)"
    ).eq("quote_id", quote_id).execute()
    ci_items = quote_items_resp.data or []

    # Build buyer_companies lookup
    bc_lookup = {}
    for item in ci_items:
        bc = (item.get("buyer_companies") or {})
        if bc and bc.get("id"):
            bc_lookup[bc["id"]] = bc

    # Get seller_company from quote
    quote_resp = supabase.table("quotes").select(
        "idn, seller_companies!seller_company_id(id, name)"
    ).eq("id", quote_id).single().execute()
    quote_data = quote_resp.data
    sc = (quote_data.get("seller_companies") or {})
    seller_company = {"id": sc.get("id"), "name": sc.get("name"), "entity_type": "seller_company"}

    if bc_lookup and seller_company.get("id"):
        invoices = generate_currency_invoices(
            deal_id=str(deal_id),
            quote_idn=quote_data.get("idn", ""),
            items=ci_items,
            buyer_companies=bc_lookup,
            seller_company=seller_company,
            organization_id=org_id,
        )
        if invoices:
            save_currency_invoices(supabase, invoices)
except Exception as e:
    print(f"Warning: currency invoice generation failed: {e}")
    # Non-blocking — deal creation still succeeds
```

**Step 4: Run tests → verify PASS**

```bash
pytest tests/test_currency_invoice_generation_hook.py tests/test_currency_invoice_service.py -v
```

**Step 5: Commit**

```bash
git add main.py services/currency_invoice_service.py tests/test_currency_invoice_generation_hook.py
git commit -m "feat: hook currency invoice generation into deal creation flow"
```

---

## Task 4: Currency Invoices Tab on Deal Detail Page

**Files:**
- Modify: `main.py` — deal detail route (find route for `/deals/{deal_id}`)
- Reference: existing tab patterns on deal page

**Context:** Add a "Валютные инвойсы" tab to the deal detail page. Shows a table of generated currency invoices with columns: number, segment, seller, buyer, amount, currency, status.

**Step 1: Find deal detail route in main.py**

Search for `@rt("/deals/` or `@rt("/finance/deals/` to find the existing deal page.

**Step 2: Add tab to deal detail page**

Add tab button "Валютные инвойсы" to existing tab bar. Only visible to roles: `admin`, `currency_controller`, `finance`.

Tab content: table listing currency_invoices for this deal.

```python
# Query currency invoices for this deal
ci_resp = supabase.table("currency_invoices").select("*").eq("deal_id", deal_id).order("segment").execute()
currency_invoices = ci_resp.data or []

# Resolve company names (polymorphic lookup)
for ci in currency_invoices:
    ci["seller_name"] = _resolve_company_name(supabase, ci.get("seller_entity_type"), ci.get("seller_entity_id"))
    ci["buyer_name"] = _resolve_company_name(supabase, ci.get("buyer_entity_type"), ci.get("buyer_entity_id"))
```

Table HTML:

```python
Table(
    Thead(Tr(
        Th("Номер"), Th("Сегмент"), Th("Продавец"), Th("Покупатель"),
        Th("Сумма"), Th("Валюта"), Th("Статус"), Th(""),
    )),
    Tbody(*[Tr(
        Td(A(ci["invoice_number"], href=f"/currency-invoices/{ci['id']}")),
        Td(ci["segment"]),
        Td(ci.get("seller_name", "Не выбрана")),
        Td(ci.get("buyer_name", "Не выбрана")),
        Td(f"{ci.get('total_amount', 0):,.2f}"),
        Td(ci.get("currency", "")),
        Td(_status_badge(ci["status"])),
        Td(A("Открыть", href=f"/currency-invoices/{ci['id']}", cls="btn btn-sm")),
    ) for ci in currency_invoices]),
    cls="table"
)
```

Helper `_resolve_company_name(supabase, entity_type, entity_id)`:

```python
def _resolve_company_name(supabase, entity_type, entity_id):
    if not entity_type or not entity_id:
        return "Не выбрана"
    table = "buyer_companies" if entity_type == "buyer_company" else "seller_companies"
    resp = supabase.table(table).select("name").eq("id", entity_id).single().execute()
    return (resp.data or {}).get("name", "Неизвестно")
```

**Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add currency invoices tab to deal detail page"
```

---

## Task 5: Currency Invoice Detail Page

**Files:**
- Modify: `main.py` — add routes GET/POST `/currency-invoices/{ci_id}`

**Context:** Detail page for viewing/editing a single currency invoice. Shows company dropdowns (filtered by country), editable markup, items table, action buttons.

**Step 1: Add GET route `/currency-invoices/{ci_id}`**

Page layout:
- Header: invoice number, date, segment badge, status badge
- Company section: seller dropdown + buyer dropdown (from buyer_companies/seller_companies, filtered by country)
  - EURTR seller: filter buyer_companies where country LIKE 'EU%' or similar
  - EURTR buyer: filter where country = 'TR'
  - TRRU seller: filter where country = 'TR'
  - TRRU buyer: filter seller_companies where country = 'RU'
- Markup field: number input, default 2.0
- Items table: #, Product Name, SKU, IDN-SKU, Manufacturer, Qty, Unit, HS Code, Base Price, Price, Total
- Total row at bottom
- Buttons: "Сохранить" (POST), "Подтвердить" (→ verified), "Пересоздать", "DOCX", "PDF"

**Step 2: Add POST route `/currency-invoices/{ci_id}`**

Saves changes:
- seller_entity_type, seller_entity_id
- buyer_entity_type, buyer_entity_id
- markup_percent → recalculates all item prices and totals
- status transitions (draft→verified, verified→exported)

**Step 3: Add POST route `/currency-invoices/{ci_id}/verify`**

Sets status = "verified", verified_by = current user, verified_at = now().

**Step 4: Commit**

```bash
git add main.py
git commit -m "feat: add currency invoice detail page with editing"
```

---

## Task 6: Currency Invoices Registry Page

**Files:**
- Modify: `main.py` — add GET `/currency-invoices`

**Context:** Registry of all currency invoices across all deals. Accessible to `admin` and `currency_controller`.

**Step 1: Add route GET `/currency-invoices`**

Query all currency_invoices with deal and quote info:

```python
ci_resp = supabase.table("currency_invoices").select(
    "*, deals!deal_id(deal_number, specification_id, specifications!specification_id(quote_id, quotes!quote_id(idn, customers!customer_id(name))))"
).order("created_at", desc=True).execute()
```

Table columns (matching existing CSV registry):
- Дата (generated_at)
- Номер инвойса (invoice_number)
- Сегмент (segment)
- Продавец (resolved company name)
- Покупатель (resolved company name)
- Клиент (customer name from quote)
- Номер КП (quote IDN)
- Сумма (total_amount)
- Валюта (currency)
- Статус (status badge)

**Step 2: Add menu item**

Add "Валютные инвойсы" to sidebar navigation for `admin` and `currency_controller` roles. Place under "Финансы" section.

**Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add currency invoices registry page"
```

---

## Task 7: DOCX Export Service

**Files:**
- Create: `services/currency_invoice_export.py`
- Create: `tests/test_currency_invoice_export.py`
- Modify: `requirements.txt` — add `python-docx`

**Context:** Generate DOCX file matching the format from the example invoice (Downloads/Инвойс 167...). Uses python-docx library.

**Step 1: Add python-docx dependency**

```bash
pip install python-docx
# Add to requirements.txt
```

**Step 2: Write failing test**

```python
# tests/test_currency_invoice_export.py
import pytest
from io import BytesIO
from services.currency_invoice_export import generate_currency_invoice_docx


def test_generate_docx_returns_bytes():
    """Should return valid DOCX bytes"""
    invoice = {
        "invoice_number": "CI-Q202601-0004-EUR-EURTR-1",
        "generated_at": "2026-02-25T12:00:00Z",
        "currency": "EUR",
        "total_amount": 10200.00,
        "segment": "EURTR",
    }
    seller = {"name": "EuroInvest Ltd", "address": "Sofia, Bulgaria", "tax_id": "BG12345"}
    buyer = {"name": "MB TR Ltd", "address": "Istanbul, Turkey", "tax_id": "TR67890"}
    items = [
        {
            "product_name": "Bearing XYZ",
            "sku": "BRG-001",
            "manufacturer": "SKF",
            "quantity": 100,
            "unit": "kg",
            "hs_code": "8482.10",
            "price": 102.00,
            "total": 10200.00,
        },
    ]

    result = generate_currency_invoice_docx(invoice, seller, buyer, items)

    assert isinstance(result, bytes)
    assert len(result) > 0
    # Verify it's a valid DOCX (ZIP magic bytes)
    assert result[:2] == b'PK'


def test_generate_docx_contains_invoice_number():
    """DOCX should contain the invoice number text"""
    from docx import Document
    invoice = {
        "invoice_number": "CI-Q202601-0004-EUR-EURTR-1",
        "generated_at": "2026-02-25T12:00:00Z",
        "currency": "EUR",
        "total_amount": 500.00,
        "segment": "EURTR",
    }
    seller = {"name": "Test Seller", "address": "Addr", "tax_id": "123"}
    buyer = {"name": "Test Buyer", "address": "Addr", "tax_id": "456"}
    items = [
        {"product_name": "Item", "sku": "S1", "manufacturer": "M1",
         "quantity": 10, "unit": "pcs", "hs_code": "1234", "price": 50.0, "total": 500.0},
    ]

    docx_bytes = generate_currency_invoice_docx(invoice, seller, buyer, items)
    doc = Document(BytesIO(docx_bytes))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "CI-Q202601-0004-EUR-EURTR-1" in full_text
```

**Step 3: Run tests → verify FAIL**

**Step 4: Implement `services/currency_invoice_export.py`**

Document structure (matching example):
1. Title: "INVOICE No. {invoice_number}"
2. Date: "Date: {generated_at formatted}"
3. Supplier block: name, address, tax ID
4. Buyer block: name, address, tax ID
5. Items table: #, Product Name, SKU, Manufacturer, Qty, Unit, HS Code, Unit Price {currency}, Total {currency}
6. Total row
7. (Optional) Payment terms section

**Step 5: Run tests → verify PASS**

**Step 6: Commit**

```bash
git add services/currency_invoice_export.py tests/test_currency_invoice_export.py requirements.txt
git commit -m "feat: add DOCX export for currency invoices"
```

---

## Task 8: PDF Export + Download Routes

**Files:**
- Modify: `services/currency_invoice_export.py` — add PDF conversion function
- Modify: `main.py` — add download routes
- Modify: `Dockerfile` — ensure libreoffice available (or use alternative)

**Context:** PDF generated by converting DOCX via libreoffice --headless (already available in Docker) or weasyprint (already in project).

**Step 1: Add PDF conversion function**

```python
def convert_docx_to_pdf(docx_bytes: bytes) -> bytes:
    """Convert DOCX bytes to PDF using libreoffice headless"""
    import subprocess, tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = os.path.join(tmpdir, "invoice.docx")
        with open(docx_path, "wb") as f:
            f.write(docx_bytes)
        subprocess.run([
            "libreoffice", "--headless", "--convert-to", "pdf",
            "--outdir", tmpdir, docx_path
        ], check=True, timeout=30)
        pdf_path = os.path.join(tmpdir, "invoice.pdf")
        with open(pdf_path, "rb") as f:
            return f.read()
```

**Step 2: Add download routes in main.py**

```python
@rt("/currency-invoices/{ci_id}/download-docx")
def get(session, ci_id: str): ...

@rt("/currency-invoices/{ci_id}/download-pdf")
def get(session, ci_id: str): ...
```

Both routes: fetch invoice + items + company data → generate DOCX → return Response with Content-Disposition header.

**Step 3: Commit**

```bash
git add services/currency_invoice_export.py main.py Dockerfile
git commit -m "feat: add PDF export and download routes for currency invoices"
```

---

## Task 9: Task System Integration

**Files:**
- Modify: `main.py` — function `_get_role_tasks_sections` (search for this function)

**Context:** When currency invoices are generated (Task 3), a workflow task should appear for `currency_controller` on the `/tasks` page.

**Step 1: Understand current task system**

The task system is built from `workflow_transitions` and quote statuses. We need to add a new task section for `currency_controller` that shows deals with draft currency invoices.

**Step 2: Add currency_controller section to `_get_role_tasks_sections`**

```python
# In _get_role_tasks_sections:
if "currency_controller" in roles or "admin" in roles:
    # Find deals with draft currency invoices
    draft_ci = supabase.table("currency_invoices").select(
        "id, deal_id, invoice_number, segment, status, deals!deal_id(deal_number)"
    ).eq("status", "draft").eq("organization_id", org_id).execute()

    if draft_ci.data:
        sections.append({
            "title": "Валютные инвойсы",
            "icon": "💱",
            "tasks": [{
                "title": f"Проверить {ci['invoice_number']}",
                "subtitle": f"Сделка {(ci.get('deals') or {}).get('deal_number', '')}",
                "url": f"/currency-invoices/{ci['id']}",
                "status": ci["status"],
            } for ci in draft_ci.data],
        })
```

**Step 3: Add sidebar menu item for currency_controller**

In menu building logic (around line 142-165), add "Валютные инвойсы" menu item visible to `currency_controller` and `admin`.

**Step 4: Commit**

```bash
git add main.py
git commit -m "feat: add currency_controller tasks to /tasks page and sidebar menu"
```

---

## Task 10: Regeneration from Source

**Files:**
- Modify: `services/currency_invoice_service.py` — add `regenerate_currency_invoices`
- Modify: `main.py` — add POST route `/currency-invoices/{ci_id}/regenerate`
- Create: `tests/test_currency_invoice_regeneration.py`

**Context:** "Пересоздать из источника" button. Deletes existing currency_invoice_items and re-generates from current quote_items data.

**Step 1: Write failing test**

```python
# tests/test_currency_invoice_regeneration.py
def test_regenerate_replaces_items():
    """Regeneration should delete old items and create new ones from source"""
    ...

def test_regenerate_resets_status_to_draft():
    """After regeneration, status should be reset to draft"""
    ...

def test_regenerate_recalculates_prices():
    """If source prices changed, regenerated items reflect new prices"""
    ...
```

**Step 2: Implement regenerate function**

```python
def regenerate_currency_invoices(supabase, deal_id, quote_idn, organization_id):
    """Delete all currency invoices for deal and re-generate from current data"""
    # 1. Delete existing currency_invoice_items (CASCADE from currency_invoices)
    supabase.table("currency_invoices").delete().eq("deal_id", deal_id).execute()
    # 2. Re-run full generation
    # ... (same logic as initial generation)
```

**Step 3: Add route**

```python
@rt("/currency-invoices/{ci_id}/regenerate")
def post(session, ci_id: str):
    # Confirm dialog handled by HTMX (hx-confirm)
    # Regenerate for the entire deal (all currency invoices)
    ...
```

**Step 4: Run tests → verify PASS**

**Step 5: Commit**

```bash
git add services/currency_invoice_service.py main.py tests/test_currency_invoice_regeneration.py
git commit -m "feat: add regeneration of currency invoices from source data"
```

---

## Summary

| Task | Description | Touches main.py | Estimated |
|------|-------------|:---:|-----------|
| 1 | DB schema + role | No | 15 min |
| 2 | Generation service + tests | No | 30 min |
| 3 | Hook into deal creation | Yes | 20 min |
| 4 | Deal tab UI | Yes | 20 min |
| 5 | Detail page + editing | Yes | 40 min |
| 6 | Registry page | Yes | 20 min |
| 7 | DOCX export + tests | No | 30 min |
| 8 | PDF export + routes | Yes | 20 min |
| 9 | Tasks integration | Yes | 15 min |
| 10 | Regeneration | Yes | 20 min |

**Parallel tracks:**
- Track A (services): Task 2 → Task 7 (can run in parallel, different files)
- Track B (main.py): Tasks 3 → 4 → 5 → 6 → 8 → 9 → 10 (sequential, same file)

**Total estimated: ~3.5 hours**
