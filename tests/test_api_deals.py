"""
Tests for POST /api/deals — Deal Creation API endpoint.

Tests cover:
- Happy path: full deal creation with logistics and invoices
- Validation: missing spec_id, user_id, org_id
- Not found: spec doesn't exist
- No signed scan: spec exists but signed_scan_url is null
- Wrong org: spec belongs to different organization
- Invoice skip reasons: no buyer companies, no seller company, no items
"""

import json

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4


def make_uuid() -> str:
    return str(uuid4())


# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def org_id():
    return make_uuid()


@pytest.fixture
def user_id():
    return make_uuid()


@pytest.fixture
def spec_id():
    return make_uuid()


@pytest.fixture
def quote_id():
    return make_uuid()


@pytest.fixture
def deal_id():
    return make_uuid()


@pytest.fixture
def mock_request():
    """Create a mock Starlette request with JSON body."""
    def _make(body: dict):
        request = MagicMock()
        request.json = AsyncMock(return_value=body)
        request.state = MagicMock()
        request.state.api_user = None  # No JWT in migration mode
        return request
    return _make


def _chain_mock():
    """Create a chainable mock that returns itself on method calls."""
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.gte.return_value = mock
    mock.single.return_value = mock
    mock.insert.return_value = mock
    mock.update.return_value = mock
    mock.limit.return_value = mock
    return mock


# ============================================================================
# HAPPY PATH
# ============================================================================


@pytest.mark.asyncio
async def test_create_deal_happy_path(mock_request, org_id, user_id, spec_id, quote_id, deal_id):
    """Full deal creation: spec validated, deal created, logistics initialized, invoices generated."""
    request = mock_request({
        "spec_id": spec_id,
        "user_id": user_id,
        "org_id": org_id,
    })

    mock_sb = MagicMock()

    # specifications.select().eq().execute()
    spec_chain = _chain_mock()
    spec_chain.execute.return_value = MagicMock(data=[{
        "id": spec_id,
        "quote_id": quote_id,
        "organization_id": org_id,
        "sign_date": "2026-04-01",
        "signed_scan_url": "https://storage.test/scan.pdf",
        "status": "draft",
    }])

    # quotes.select().eq().single().execute()
    quote_chain = _chain_mock()
    quote_chain.execute.return_value = MagicMock(data={
        "id": quote_id,
        "total_amount": 100000,
        "currency": "USD",
        "idn_quote": "Q202604-0001",
        "seller_company_id": make_uuid(),
        "seller_companies": {"id": make_uuid(), "name": "Test Seller Co"},
    })

    # deals.select().eq().gte().execute() — count for deal number
    count_chain = _chain_mock()
    count_chain.execute.return_value = MagicMock(count=3, data=[])

    # specifications.update().eq().execute()
    spec_update_chain = _chain_mock()
    spec_update_chain.execute.return_value = MagicMock(data=[{}])

    # deals.insert().execute()
    deal_insert_chain = _chain_mock()
    deal_insert_chain.execute.return_value = MagicMock(data=[{"id": deal_id}])

    # quotes.update().eq().execute()
    quote_update_chain = _chain_mock()
    quote_update_chain.execute.return_value = MagicMock(data=[{}])

    table_calls = {
        "specifications": [spec_chain, spec_update_chain],
        "quotes": [quote_chain, quote_update_chain],
        "deals": [count_chain, deal_insert_chain],
    }
    table_counters = {k: 0 for k in table_calls}

    def mock_table(name):
        if name in table_calls:
            idx = table_counters[name]
            table_counters[name] = idx + 1
            if idx < len(table_calls[name]):
                return table_calls[name][idx]
        return _chain_mock()

    mock_sb.table = mock_table

    mock_stages = [MagicMock() for _ in range(7)]

    with patch("api.deals.get_supabase", return_value=mock_sb), \
         patch("api.deals.initialize_logistics_stages", return_value=mock_stages) as mock_logistics, \
         patch("api.deals.fetch_items_with_buyer_companies", return_value=(
             [{"id": make_uuid(), "buyer_company_id": "bc1", "purchase_price_original": 100, "quantity": 10}],
             {"bc1": {"id": "bc1", "name": "Buyer Co", "region": "EU"}},
         )), \
         patch("api.deals.generate_currency_invoices", return_value=[
             {"segment": "EURTR", "total_amount": 1000},
             {"segment": "TRRU", "total_amount": 2000},
         ]) as mock_gen_inv, \
         patch("api.deals.save_currency_invoices") as mock_save_inv, \
         patch("api.deals.fetch_enrichment_data", return_value=([], [])):

        from api.deals import create_deal
        response = await create_deal(request)

    assert response.status_code == 201
    body = json.loads(response.body)
    assert body["success"] is True
    assert body["data"]["deal_id"] == deal_id
    assert body["data"]["deal_number"].startswith("DEAL-")
    assert body["data"]["logistics_stages"] == 7
    assert body["data"]["invoices_created"] == 2
    assert body["data"]["invoices_skipped_reason"] is None

    mock_logistics.assert_called_once_with(deal_id, user_id)
    mock_gen_inv.assert_called_once()
    mock_save_inv.assert_called_once()


# ============================================================================
# VALIDATION ERRORS
# ============================================================================


@pytest.mark.asyncio
async def test_create_deal_missing_spec_id(mock_request, user_id, org_id):
    """Missing spec_id returns 400."""
    request = mock_request({"user_id": user_id, "org_id": org_id})

    from api.deals import create_deal
    response = await create_deal(request)

    assert response.status_code == 400
    body = json.loads(response.body)
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "spec_id" in body["error"]["message"]


@pytest.mark.asyncio
async def test_create_deal_missing_user_id(mock_request, spec_id, org_id):
    """Missing user_id returns 400."""
    request = mock_request({"spec_id": spec_id, "org_id": org_id})

    from api.deals import create_deal
    response = await create_deal(request)

    assert response.status_code == 400
    body = json.loads(response.body)
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_create_deal_missing_org_id(mock_request, spec_id, user_id):
    """Missing org_id returns 400."""
    request = mock_request({"spec_id": spec_id, "user_id": user_id})

    from api.deals import create_deal
    response = await create_deal(request)

    assert response.status_code == 400
    body = json.loads(response.body)
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_create_deal_invalid_json(mock_request):
    """Invalid JSON body returns 400."""
    request = MagicMock()
    request.json = AsyncMock(side_effect=ValueError("Invalid JSON"))
    request.state = MagicMock()
    request.state.api_user = None

    from api.deals import create_deal
    response = await create_deal(request)

    assert response.status_code == 400
    body = json.loads(response.body)
    assert body["error"]["code"] == "BAD_REQUEST"


# ============================================================================
# NOT FOUND / AUTHORIZATION
# ============================================================================


@pytest.mark.asyncio
async def test_create_deal_spec_not_found(mock_request, user_id, org_id, spec_id):
    """Non-existent spec returns 404."""
    request = mock_request({
        "spec_id": spec_id,
        "user_id": user_id,
        "org_id": org_id,
    })

    mock_sb = MagicMock()
    spec_chain = _chain_mock()
    spec_chain.execute.return_value = MagicMock(data=[])
    mock_sb.table.return_value = spec_chain

    with patch("api.deals.get_supabase", return_value=mock_sb):
        from api.deals import create_deal
        response = await create_deal(request)

    assert response.status_code == 404
    body = json.loads(response.body)
    assert body["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_create_deal_spec_wrong_org(mock_request, user_id, org_id, spec_id, quote_id):
    """Spec belonging to different org returns 404."""
    request = mock_request({
        "spec_id": spec_id,
        "user_id": user_id,
        "org_id": org_id,
    })

    mock_sb = MagicMock()
    spec_chain = _chain_mock()
    spec_chain.execute.return_value = MagicMock(data=[{
        "id": spec_id,
        "quote_id": quote_id,
        "organization_id": make_uuid(),  # Different org
        "sign_date": None,
        "signed_scan_url": "https://storage.test/scan.pdf",
        "status": "draft",
    }])
    mock_sb.table.return_value = spec_chain

    with patch("api.deals.get_supabase", return_value=mock_sb):
        from api.deals import create_deal
        response = await create_deal(request)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_deal_no_signed_scan(mock_request, user_id, org_id, spec_id, quote_id):
    """Spec without signed_scan_url returns 400."""
    request = mock_request({
        "spec_id": spec_id,
        "user_id": user_id,
        "org_id": org_id,
    })

    mock_sb = MagicMock()
    spec_chain = _chain_mock()
    spec_chain.execute.return_value = MagicMock(data=[{
        "id": spec_id,
        "quote_id": quote_id,
        "organization_id": org_id,
        "sign_date": None,
        "signed_scan_url": None,  # No scan
        "status": "draft",
    }])
    mock_sb.table.return_value = spec_chain

    with patch("api.deals.get_supabase", return_value=mock_sb):
        from api.deals import create_deal
        response = await create_deal(request)

    assert response.status_code == 400
    body = json.loads(response.body)
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "scan" in body["error"]["message"].lower()


# ============================================================================
# INVOICE SKIP REASONS
# ============================================================================


@pytest.mark.asyncio
async def test_create_deal_invoices_skip_no_items(
    mock_request, org_id, user_id, spec_id, quote_id, deal_id
):
    """When quote has no items, invoices_skipped_reason explains why."""
    request = mock_request({
        "spec_id": spec_id,
        "user_id": user_id,
        "org_id": org_id,
    })

    mock_sb = MagicMock()

    spec_chain = _chain_mock()
    spec_chain.execute.return_value = MagicMock(data=[{
        "id": spec_id,
        "quote_id": quote_id,
        "organization_id": org_id,
        "sign_date": "2026-04-01",
        "signed_scan_url": "https://storage.test/scan.pdf",
        "status": "draft",
    }])

    quote_chain = _chain_mock()
    quote_chain.execute.return_value = MagicMock(data={
        "id": quote_id,
        "total_amount": 100000,
        "currency": "USD",
        "idn_quote": "Q202604-0001",
        "seller_company_id": make_uuid(),
        "seller_companies": {"id": make_uuid(), "name": "Seller Co"},
    })

    count_chain = _chain_mock()
    count_chain.execute.return_value = MagicMock(count=0, data=[])

    spec_update_chain = _chain_mock()
    spec_update_chain.execute.return_value = MagicMock(data=[{}])

    deal_insert_chain = _chain_mock()
    deal_insert_chain.execute.return_value = MagicMock(data=[{"id": deal_id}])

    quote_update_chain = _chain_mock()
    quote_update_chain.execute.return_value = MagicMock(data=[{}])

    table_calls = {
        "specifications": [spec_chain, spec_update_chain],
        "quotes": [quote_chain, quote_update_chain],
        "deals": [count_chain, deal_insert_chain],
    }
    table_counters = {k: 0 for k in table_calls}

    def mock_table(name):
        if name in table_calls:
            idx = table_counters[name]
            table_counters[name] = idx + 1
            if idx < len(table_calls[name]):
                return table_calls[name][idx]
        return _chain_mock()

    mock_sb.table = mock_table

    with patch("api.deals.get_supabase", return_value=mock_sb), \
         patch("api.deals.initialize_logistics_stages", return_value=[MagicMock()] * 7), \
         patch("api.deals.fetch_items_with_buyer_companies", return_value=([], {})):

        from api.deals import create_deal
        response = await create_deal(request)

    assert response.status_code == 201
    body = json.loads(response.body)
    assert body["success"] is True
    assert body["data"]["invoices_created"] == 0
    assert body["data"]["invoices_skipped_reason"] == "No items in quote"


@pytest.mark.asyncio
async def test_create_deal_invoices_skip_no_buyer_companies(
    mock_request, org_id, user_id, spec_id, quote_id, deal_id
):
    """When no buyer companies assigned, invoices_skipped_reason explains why."""
    request = mock_request({
        "spec_id": spec_id,
        "user_id": user_id,
        "org_id": org_id,
    })

    mock_sb = MagicMock()

    spec_chain = _chain_mock()
    spec_chain.execute.return_value = MagicMock(data=[{
        "id": spec_id,
        "quote_id": quote_id,
        "organization_id": org_id,
        "sign_date": "2026-04-01",
        "signed_scan_url": "https://storage.test/scan.pdf",
        "status": "draft",
    }])

    quote_chain = _chain_mock()
    quote_chain.execute.return_value = MagicMock(data={
        "id": quote_id,
        "total_amount": 100000,
        "currency": "USD",
        "idn_quote": "Q202604-0001",
        "seller_company_id": make_uuid(),
        "seller_companies": {"id": make_uuid(), "name": "Seller Co"},
    })

    count_chain = _chain_mock()
    count_chain.execute.return_value = MagicMock(count=0, data=[])

    spec_update_chain = _chain_mock()
    spec_update_chain.execute.return_value = MagicMock(data=[{}])

    deal_insert_chain = _chain_mock()
    deal_insert_chain.execute.return_value = MagicMock(data=[{"id": deal_id}])

    quote_update_chain = _chain_mock()
    quote_update_chain.execute.return_value = MagicMock(data=[{}])

    table_calls = {
        "specifications": [spec_chain, spec_update_chain],
        "quotes": [quote_chain, quote_update_chain],
        "deals": [count_chain, deal_insert_chain],
    }
    table_counters = {k: 0 for k in table_calls}

    def mock_table(name):
        if name in table_calls:
            idx = table_counters[name]
            table_counters[name] = idx + 1
            if idx < len(table_calls[name]):
                return table_calls[name][idx]
        return _chain_mock()

    mock_sb.table = mock_table

    with patch("api.deals.get_supabase", return_value=mock_sb), \
         patch("api.deals.initialize_logistics_stages", return_value=[MagicMock()] * 7), \
         patch("api.deals.fetch_items_with_buyer_companies", return_value=(
             [{"id": make_uuid(), "quantity": 10}],  # Items exist
             {},  # No buyer companies
         )):

        from api.deals import create_deal
        response = await create_deal(request)

    assert response.status_code == 201
    body = json.loads(response.body)
    assert body["success"] is True
    assert body["data"]["invoices_created"] == 0
    assert body["data"]["invoices_skipped_reason"] == "No buyer companies assigned to quote items"


@pytest.mark.asyncio
async def test_create_deal_invoices_skip_no_seller_company(
    mock_request, org_id, user_id, spec_id, quote_id, deal_id
):
    """When no seller company on quote, invoices_skipped_reason explains why."""
    request = mock_request({
        "spec_id": spec_id,
        "user_id": user_id,
        "org_id": org_id,
    })

    mock_sb = MagicMock()

    spec_chain = _chain_mock()
    spec_chain.execute.return_value = MagicMock(data=[{
        "id": spec_id,
        "quote_id": quote_id,
        "organization_id": org_id,
        "sign_date": "2026-04-01",
        "signed_scan_url": "https://storage.test/scan.pdf",
        "status": "draft",
    }])

    quote_chain = _chain_mock()
    quote_chain.execute.return_value = MagicMock(data={
        "id": quote_id,
        "total_amount": 100000,
        "currency": "USD",
        "idn_quote": "Q202604-0001",
        "seller_company_id": None,
        "seller_companies": None,  # No seller company
    })

    count_chain = _chain_mock()
    count_chain.execute.return_value = MagicMock(count=0, data=[])

    spec_update_chain = _chain_mock()
    spec_update_chain.execute.return_value = MagicMock(data=[{}])

    deal_insert_chain = _chain_mock()
    deal_insert_chain.execute.return_value = MagicMock(data=[{"id": deal_id}])

    quote_update_chain = _chain_mock()
    quote_update_chain.execute.return_value = MagicMock(data=[{}])

    table_calls = {
        "specifications": [spec_chain, spec_update_chain],
        "quotes": [quote_chain, quote_update_chain],
        "deals": [count_chain, deal_insert_chain],
    }
    table_counters = {k: 0 for k in table_calls}

    def mock_table(name):
        if name in table_calls:
            idx = table_counters[name]
            table_counters[name] = idx + 1
            if idx < len(table_calls[name]):
                return table_calls[name][idx]
        return _chain_mock()

    mock_sb.table = mock_table

    with patch("api.deals.get_supabase", return_value=mock_sb), \
         patch("api.deals.initialize_logistics_stages", return_value=[MagicMock()] * 7), \
         patch("api.deals.fetch_items_with_buyer_companies", return_value=(
             [{"id": make_uuid(), "buyer_company_id": "bc1", "quantity": 10}],
             {"bc1": {"id": "bc1", "name": "Buyer Co", "region": "EU"}},
         )):

        from api.deals import create_deal
        response = await create_deal(request)

    assert response.status_code == 201
    body = json.loads(response.body)
    assert body["success"] is True
    assert body["data"]["invoices_created"] == 0
    assert body["data"]["invoices_skipped_reason"] == "No seller company on quote"


# ============================================================================
# ERROR PATH: DEAL INSERT FAILURE + ROLLBACK
# ============================================================================


@pytest.mark.asyncio
async def test_create_deal_insert_failure_rollbacks_spec(
    mock_request, user_id, org_id, spec_id, quote_id
):
    """Deal insert DB failure returns 500 and rolls back spec status."""
    request = mock_request({
        "spec_id": spec_id,
        "user_id": user_id,
        "org_id": org_id,
    })

    mock_sb = MagicMock()

    spec_chain = _chain_mock()
    spec_chain.execute.return_value = MagicMock(data=[{
        "id": spec_id,
        "quote_id": quote_id,
        "organization_id": org_id,
        "sign_date": "2026-04-01",
        "signed_scan_url": "https://storage.test/scan.pdf",
        "status": "approved",
    }])

    quote_chain = _chain_mock()
    quote_chain.execute.return_value = MagicMock(data={
        "id": quote_id,
        "total_amount": 100000,
        "currency": "USD",
        "idn_quote": "Q202604-0001",
        "seller_company_id": make_uuid(),
        "seller_companies": {"id": make_uuid(), "name": "Seller"},
    })

    count_chain = _chain_mock()
    count_chain.execute.return_value = MagicMock(count=0, data=[])

    spec_update_chain = _chain_mock()
    spec_update_chain.execute.return_value = MagicMock(data=[{}])

    # Deal insert FAILS
    deal_insert_chain = _chain_mock()
    deal_insert_chain.execute.side_effect = Exception("DB connection lost")

    # Rollback spec status
    spec_rollback_chain = _chain_mock()
    spec_rollback_chain.execute.return_value = MagicMock(data=[{}])

    table_calls = {
        "specifications": [spec_chain, spec_update_chain, spec_rollback_chain],
        "quotes": [quote_chain],
        "deals": [count_chain, deal_insert_chain],
    }
    table_counters = {k: 0 for k in table_calls}

    def mock_table(name):
        if name in table_calls:
            idx = table_counters[name]
            table_counters[name] = idx + 1
            if idx < len(table_calls[name]):
                return table_calls[name][idx]
        return _chain_mock()

    mock_sb.table = mock_table

    with patch("api.deals.get_supabase", return_value=mock_sb):
        from api.deals import create_deal
        response = await create_deal(request)

    assert response.status_code == 500
    body = json.loads(response.body)
    assert body["success"] is False
    assert body["error"]["code"] == "INTERNAL_ERROR"
    # Spec should have been accessed 3 times: read, update to signed, rollback
    assert table_counters["specifications"] == 3


@pytest.mark.asyncio
async def test_create_deal_insert_returns_empty_data(
    mock_request, user_id, org_id, spec_id, quote_id
):
    """Deal insert returning empty data returns 500."""
    request = mock_request({
        "spec_id": spec_id,
        "user_id": user_id,
        "org_id": org_id,
    })

    mock_sb = MagicMock()

    spec_chain = _chain_mock()
    spec_chain.execute.return_value = MagicMock(data=[{
        "id": spec_id,
        "quote_id": quote_id,
        "organization_id": org_id,
        "sign_date": "2026-04-01",
        "signed_scan_url": "https://storage.test/scan.pdf",
        "status": "draft",
    }])

    quote_chain = _chain_mock()
    quote_chain.execute.return_value = MagicMock(data={
        "id": quote_id,
        "total_amount": 100000,
        "currency": "USD",
        "idn_quote": "Q202604-0001",
        "seller_company_id": make_uuid(),
        "seller_companies": {"id": make_uuid(), "name": "Seller"},
    })

    count_chain = _chain_mock()
    count_chain.execute.return_value = MagicMock(count=0, data=[])

    spec_update_chain = _chain_mock()
    spec_update_chain.execute.return_value = MagicMock(data=[{}])

    # Deal insert returns empty
    deal_insert_chain = _chain_mock()
    deal_insert_chain.execute.return_value = MagicMock(data=[])

    table_calls = {
        "specifications": [spec_chain, spec_update_chain],
        "quotes": [quote_chain],
        "deals": [count_chain, deal_insert_chain],
    }
    table_counters = {k: 0 for k in table_calls}

    def mock_table(name):
        if name in table_calls:
            idx = table_counters[name]
            table_counters[name] = idx + 1
            if idx < len(table_calls[name]):
                return table_calls[name][idx]
        return _chain_mock()

    mock_sb.table = mock_table

    with patch("api.deals.get_supabase", return_value=mock_sb):
        from api.deals import create_deal
        response = await create_deal(request)

    assert response.status_code == 500
    body = json.loads(response.body)
    assert body["success"] is False
    assert body["error"]["code"] == "INTERNAL_ERROR"
