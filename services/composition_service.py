"""
Composition Service — Phase 5b.

Adapter between the multi-supplier composition layer (kvota.invoice_item_prices
junction) and the existing calculation pipeline (build_calculation_inputs in
main.py). Produces item dicts in the exact shape the current quote_items SELECT
returns, so build_calculation_inputs() sees no difference.

Does NOT import from calculation_engine.py, calculation_models.py, or
calculation_mapper.py — those files are locked.

Public API:
    get_composed_items(quote_id, supabase) -> list[dict]
        Adapter — replaces the 3 quote_items reads in main.py (Task 5).
    get_composition_view(quote_id, supabase, user_id=None) -> dict
        For the GET /api/quotes/{id}/composition endpoint (Task 6).
    apply_composition(quote_id, selection_map, supabase, user_id, quote_updated_at)
        For the POST /api/quotes/{id}/composition endpoint (Task 6).
    validate_composition(quote_id, selection_map, supabase) -> ValidationResult
        Pure validator used internally by apply_composition and exposed for
        pre-flight checks from the API layer.
    freeze_composition(quote_id, user_id, supabase) -> int
        Stamps frozen_at/frozen_by on all active iip rows (Task 8/13).

Data model reference (see design.md § "Data Model"):
    kvota.invoice_item_prices(id, invoice_id, quote_item_id, organization_id,
        purchase_price_original, purchase_currency, base_price_vat,
        price_includes_vat, production_time_days, minimum_order_quantity,
        supplier_notes, version, frozen_at, frozen_by, created_at, updated_at,
        created_by)
        UNIQUE (invoice_id, quote_item_id, version)

    kvota.quote_items.composition_selected_invoice_id UUID NULL
        FK -> kvota.invoices(id) ON DELETE SET NULL
        NULL = use legacy quote_items price fields (pre-Phase-5b path).
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Price fields overlaid from invoice_item_prices onto quote_items when a
# composition pointer is set. Every other field on quote_items passes through
# unchanged — the engine consumes them identically to today.
_OVERLAY_FIELDS: tuple[str, ...] = (
    "purchase_price_original",
    "purchase_currency",
    "base_price_vat",
    "price_includes_vat",
)


# ============================================================================
# Exceptions and result types
# ============================================================================

class ConcurrencyError(Exception):
    """Raised when the quote's updated_at changed since the client loaded it.

    Handled as HTTP 409 STALE_QUOTE at the API layer. The client must reload
    the quote and re-submit the composition.
    """

    pass


class ValidationError(Exception):
    """Raised when a composition selection references an (item, invoice) pair
    that has no matching invoice_item_prices row.

    Handled as HTTP 400 COMPOSITION_INVALID_SELECTION at the API layer. The
    error list is exposed via the ``errors`` attribute so the API can return
    per-item diagnostics.
    """

    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__(
            f"{len(errors)} invalid composition selection(s): "
            + ", ".join(
                f"{e['quote_item_id']}->{e['invoice_id']}" for e in errors
            )
        )


@dataclass
class ValidationResult:
    """Result of validate_composition — a value object for the API layer.

    Attributes:
        valid: True iff every selection has a matching iip row.
        errors: List of ``{"quote_item_id": ..., "invoice_id": ..., "reason": ...}``
            dicts. Empty when valid is True.
    """

    valid: bool
    errors: list[dict] = field(default_factory=list)


# ============================================================================
# Adapter — get_composed_items (replaces 3 quote_items reads in main.py)
# ============================================================================

def get_composed_items(quote_id: str, supabase) -> list[dict]:
    """Return quote_items with price fields overlaid from the active composition.

    This function is the adapter that replaces the three ``quote_items``
    reads in main.py (at lines ~13303, 14188, 14846 — verified at Task 5
    start via ``grep -n "build_calculation_inputs("``). It produces a
    ``list[dict]`` in the exact shape a plain
    ``supabase.table("quote_items").select("*").eq("quote_id", quote_id).execute().data``
    call would return, so ``build_calculation_inputs()`` sees no difference.

    For each quote_item:
      - If ``composition_selected_invoice_id`` IS NOT NULL and a matching
        invoice_item_prices row exists, the four price fields are overlaid
        from the iip row (the latest non-frozen version wins when multiple
        versions exist for the same (item, invoice) pair).
      - Otherwise, the quote_items row is returned unchanged — legacy path
        for pre-Phase-5b data and orphaned composition pointers.

    Non-price fields (``customs_code``, ``weight_in_kg``, ``quantity``,
    ``supplier_country``, ``is_unavailable``, ``import_banned``, license cost
    fields, etc.) are always preserved from quote_items.

    Query count: at most 2 SQL reads, regardless of item count. No N+1.
        1. SELECT * FROM quote_items WHERE quote_id = :quote_id
        2. SELECT * FROM invoice_item_prices
             WHERE quote_item_id IN (:items_with_pointer)
           (skipped when no item has a composition pointer)

    Args:
        quote_id: UUID of the quote to compose.
        supabase: Supabase client instance (schema-scoped to kvota).

    Returns:
        List of item dicts ready to feed into ``build_calculation_inputs()``.
    """
    items_resp = supabase.table("quote_items").select("*").eq(
        "quote_id", quote_id
    ).execute()
    items: list[dict] = items_resp.data or []

    # Collect quote_item_ids that have a composition pointer. If none, skip
    # the second query entirely — the legacy path is identical to today.
    pointed_item_ids = [
        item["id"]
        for item in items
        if item.get("composition_selected_invoice_id")
    ]
    if not pointed_item_ids:
        return items

    iip_resp = supabase.table("invoice_item_prices").select("*").in_(
        "quote_item_id", pointed_item_ids
    ).execute()
    iip_rows: list[dict] = iip_resp.data or []

    # Build lookup: (quote_item_id, invoice_id) -> iip row.
    # When multiple versions exist for the same pair, prefer the highest
    # version number (latest snapshot).
    iip_lookup: dict[tuple[str, str], dict] = {}
    for row in iip_rows:
        key = (row["quote_item_id"], row["invoice_id"])
        existing = iip_lookup.get(key)
        if existing is None or row.get("version", 1) > existing.get("version", 1):
            iip_lookup[key] = row

    # Overlay prices onto quote_items, preserving all non-price fields.
    composed: list[dict] = []
    for item in items:
        pointer = item.get("composition_selected_invoice_id")
        if pointer:
            iip = iip_lookup.get((item["id"], pointer))
            if iip is not None:
                overlaid = {**item}
                for field_name in _OVERLAY_FIELDS:
                    if field_name in iip:
                        overlaid[field_name] = iip[field_name]
                composed.append(overlaid)
                continue
            # Pointer set but no matching iip row — graceful fallback with
            # a warning. This can happen if an iip row was hard-deleted
            # without clearing the pointer.
            logger.warning(
                "Composition pointer references missing iip row: "
                "quote_item_id=%s invoice_id=%s — falling back to legacy values",
                item.get("id"),
                pointer,
            )
        composed.append(item)

    return composed


# ============================================================================
# GET composition view — for the picker UI
# ============================================================================

def get_composition_view(
    quote_id: str,
    supabase,
    user_id: Optional[str] = None,
) -> dict:
    """Return composition state with all supplier alternatives for the picker.

    Produces the shape the GET /api/quotes/{id}/composition endpoint returns.
    Groups every (iip row, invoice, supplier) triple as an alternative under
    its parent quote_item.

    Args:
        quote_id: Quote UUID.
        supabase: Supabase client instance.
        user_id: Acting user ID (reserved for future edit-permission checks;
            currently unused, access control happens at the API layer).

    Returns:
        dict with keys:
            quote_id: str
            items: list of {
                quote_item_id, brand, sku, name, quantity,
                selected_invoice_id, alternatives: [...]
            }
            composition_complete: bool — True iff every item has a non-null
                selected_invoice_id and the quote has at least one item.
    """
    items_resp = supabase.table("quote_items").select("*").eq(
        "quote_id", quote_id
    ).execute()
    items: list[dict] = items_resp.data or []
    if not items:
        return {
            "quote_id": quote_id,
            "items": [],
            "composition_complete": False,
        }

    item_ids = [item["id"] for item in items]
    iip_resp = supabase.table("invoice_item_prices").select("*").in_(
        "quote_item_id", item_ids
    ).execute()
    iip_rows: list[dict] = iip_resp.data or []

    # Fetch invoices referenced by those iip rows in one query.
    invoice_ids: list[str] = sorted({
        row["invoice_id"] for row in iip_rows if row.get("invoice_id")
    })
    invoices_by_id: dict[str, dict] = {}
    if invoice_ids:
        inv_resp = supabase.table("invoices").select("*").in_(
            "id", invoice_ids
        ).execute()
        for inv in inv_resp.data or []:
            invoices_by_id[inv["id"]] = inv

    # Fetch suppliers referenced by those invoices in one query. Collected
    # via explicit loop so Pyright can narrow the type away from Optional.
    supplier_id_set: set[str] = set()
    for inv_id in invoice_ids:
        sid = (invoices_by_id.get(inv_id) or {}).get("supplier_id")
        if sid:
            supplier_id_set.add(sid)
    supplier_ids: list[str] = sorted(supplier_id_set)
    suppliers_by_id: dict[str, dict] = {}
    if supplier_ids:
        sup_resp = supabase.table("suppliers").select("*").in_(
            "id", supplier_ids
        ).execute()
        for sup in sup_resp.data or []:
            suppliers_by_id[sup["id"]] = sup

    # Group alternatives by parent quote_item.
    alternatives_by_item: dict[str, list[dict]] = {}
    for row in iip_rows:
        qi_id = row["quote_item_id"]
        inv_id = row["invoice_id"]
        inv = invoices_by_id.get(inv_id) or {}
        sup = suppliers_by_id.get(inv.get("supplier_id") or "") or {}
        alternatives_by_item.setdefault(qi_id, []).append({
            "invoice_id": inv_id,
            "supplier_id": inv.get("supplier_id"),
            "supplier_name": sup.get("name"),
            "supplier_country": sup.get("country"),
            "purchase_price_original": row.get("purchase_price_original"),
            "purchase_currency": row.get("purchase_currency"),
            "base_price_vat": row.get("base_price_vat"),
            "price_includes_vat": row.get("price_includes_vat"),
            "production_time_days": row.get("production_time_days"),
            "version": row.get("version"),
            "frozen_at": row.get("frozen_at"),
        })

    # Assemble view items with selection state.
    view_items: list[dict] = []
    all_have_selection = True
    for item in items:
        selected = item.get("composition_selected_invoice_id")
        if selected is None:
            all_have_selection = False
        view_items.append({
            "quote_item_id": item["id"],
            "brand": item.get("brand"),
            "sku": item.get("idn_sku") or item.get("supplier_sku"),
            "name": item.get("name"),
            "quantity": item.get("quantity"),
            "selected_invoice_id": selected,
            "alternatives": alternatives_by_item.get(item["id"], []),
        })

    return {
        "quote_id": quote_id,
        "items": view_items,
        "composition_complete": all_have_selection and bool(view_items),
    }


# ============================================================================
# Validation
# ============================================================================

def validate_composition(
    quote_id: str,
    selection_map: dict[str, str],
    supabase,
) -> ValidationResult:
    """Verify every selected (quote_item_id, invoice_id) pair has an iip row.

    Pure function — does not mutate anything, does not check the quote's
    updated_at. Safe to call from preflight endpoints.

    Args:
        quote_id: Quote UUID (currently unused — kept in the signature for
            forward compatibility if per-quote validation is added).
        selection_map: ``{quote_item_id: invoice_id}`` mapping from the
            client. Empty map is trivially valid.
        supabase: Supabase client instance.

    Returns:
        ValidationResult with valid=True when every pair has a match,
        valid=False plus a list of errors otherwise.
    """
    if not selection_map:
        return ValidationResult(valid=True, errors=[])

    item_ids = list(selection_map.keys())
    iip_resp = supabase.table("invoice_item_prices").select(
        "quote_item_id,invoice_id"
    ).in_("quote_item_id", item_ids).execute()
    iip_rows: list[dict] = iip_resp.data or []

    existing_pairs: set[tuple[str, str]] = {
        (row["quote_item_id"], row["invoice_id"]) for row in iip_rows
    }

    errors: list[dict] = []
    for qi_id, inv_id in selection_map.items():
        if (qi_id, inv_id) not in existing_pairs:
            errors.append({
                "quote_item_id": qi_id,
                "invoice_id": inv_id,
                "reason": "no matching invoice_item_prices row",
            })

    return ValidationResult(valid=not errors, errors=errors)


# ============================================================================
# Apply — POST /api/quotes/{id}/composition
# ============================================================================

def apply_composition(
    quote_id: str,
    selection_map: dict[str, str],
    supabase,
    user_id: str,
    quote_updated_at: Optional[str] = None,
) -> None:
    """Persist the user's composition choice atomically.

    Sequence:
      1. Validate via validate_composition — raises ValidationError if any
         selection has no matching iip row. No writes on failure.
      2. (Optional) Optimistic concurrency check — if quote_updated_at is
         provided, compare against the current value in the DB and raise
         ConcurrencyError on mismatch. Skipped when None (e.g. for scripted
         backfills).
      3. UPDATE quote_items.composition_selected_invoice_id = :invoice_id
         for each entry in selection_map.
      4. Bump quotes.updated_at to force downstream cache invalidation.

    Note: steps 3 and 4 are NOT wrapped in a DB transaction here because the
    Supabase REST API does not expose transactions to the Python client. If
    strict atomicity is required in the future, move to a Postgres RPC or
    use supabase-py's ``rpc()`` wrapper. For MVP, the window between the
    first UPDATE and the updated_at bump is a few milliseconds.

    Args:
        quote_id: Quote UUID.
        selection_map: ``{quote_item_id: invoice_id}`` from the client.
        supabase: Supabase client instance.
        user_id: Acting user ID (for future audit logging; currently used
            only to disambiguate logs).
        quote_updated_at: Optional ISO timestamp captured by the client when
            it loaded the quote. Pass None to skip the concurrency check.

    Raises:
        ValidationError: selection references non-existent iip pair(s).
        ConcurrencyError: quote_updated_at does not match the current value.
    """
    # 1. Validate
    result = validate_composition(quote_id, selection_map, supabase)
    if not result.valid:
        raise ValidationError(result.errors)

    # 2. Optimistic concurrency check (opt-in)
    if quote_updated_at is not None:
        quote_resp = supabase.table("quotes").select("updated_at").eq(
            "id", quote_id
        ).execute()
        rows: list[dict] = quote_resp.data or []
        if not rows:
            raise ConcurrencyError(f"quote {quote_id} not found")
        current = rows[0].get("updated_at")
        if current != quote_updated_at:
            raise ConcurrencyError(
                f"quote {quote_id} was modified: "
                f"expected updated_at={quote_updated_at}, found={current}"
            )

    # 3. Update composition pointers
    for qi_id, inv_id in selection_map.items():
        supabase.table("quote_items").update(
            {"composition_selected_invoice_id": inv_id}
        ).eq("id", qi_id).execute()

    # 4. Bump quotes.updated_at
    now_iso = datetime.now(timezone.utc).isoformat()
    supabase.table("quotes").update({"updated_at": now_iso}).eq(
        "id", quote_id
    ).execute()

    logger.info(
        "Composition applied: quote_id=%s items=%d user_id=%s",
        quote_id,
        len(selection_map),
        user_id,
    )


# ============================================================================
# Freeze — KP send hook
# ============================================================================

def freeze_composition(
    quote_id: str,
    user_id: str,
    supabase,
) -> int:
    """Stamp frozen_at/frozen_by on all iip rows currently selected for this quote.

    Idempotent: already-frozen rows are skipped, so re-running is a no-op.
    Only rows that are (a) pointed to by ``quote_items.composition_selected_invoice_id``
    AND (b) currently unfrozen are touched.

    Called from the KP send flow (see Task 13) — when procurement sends a KP
    to the supplier, the composition at that moment becomes immutable history.

    Args:
        quote_id: Quote UUID.
        user_id: Acting user ID (stamped into frozen_by).
        supabase: Supabase client instance.

    Returns:
        Number of iip rows frozen by this call. 0 when there is nothing to
        freeze (no composition set, or every row is already frozen).
    """
    items_resp = supabase.table("quote_items").select(
        "id,composition_selected_invoice_id"
    ).eq("quote_id", quote_id).execute()
    items: list[dict] = items_resp.data or []

    active_pairs: list[tuple[str, str]] = [
        (item["id"], item["composition_selected_invoice_id"])
        for item in items
        if item.get("composition_selected_invoice_id")
    ]
    if not active_pairs:
        return 0

    item_ids = [pair[0] for pair in active_pairs]
    iip_resp = supabase.table("invoice_item_prices").select("*").in_(
        "quote_item_id", item_ids
    ).execute()
    iip_rows: list[dict] = iip_resp.data or []

    active_pairs_set: set[tuple[str, str]] = set(active_pairs)
    to_freeze = [
        row
        for row in iip_rows
        if (row["quote_item_id"], row["invoice_id"]) in active_pairs_set
        and row.get("frozen_at") is None
    ]

    now_iso = datetime.now(timezone.utc).isoformat()
    frozen_count = 0
    for row in to_freeze:
        supabase.table("invoice_item_prices").update({
            "frozen_at": now_iso,
            "frozen_by": user_id,
        }).eq("id", row["id"]).execute()
        frozen_count += 1

    if frozen_count:
        logger.info(
            "Composition frozen: quote_id=%s rows=%d user_id=%s",
            quote_id,
            frozen_count,
            user_id,
        )

    return frozen_count
