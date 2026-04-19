"""
Composition Service — Phase 5c.

Adapter between the multi-supplier composition layer (the
``kvota.invoice_items`` + ``kvota.invoice_item_coverage`` tables introduced
in migrations 281/282) and the existing calculation pipeline
(build_calculation_inputs in main.py).

Replaces Phase 5b's ``invoice_item_prices`` junction with per-invoice
positions (``invoice_items``) and an M:N coverage table carrying a
``ratio`` coefficient. This enables local split (1 quote_item → N
invoice_items) and merge (N quote_items → 1 invoice_item) without
mutating the customer's quote_items.

Produces item dicts in the exact shape ``build_calculation_inputs()``
expects, so the locked calculation engine sees no difference.

Does NOT import from calculation_engine.py, calculation_models.py, or
calculation_mapper.py — those files are locked.

Public API (signature-preserved from Phase 5b):
    get_composed_items(quote_id, supabase) -> list[dict]
        Adapter — feeds ``build_calculation_inputs()`` at 3 call sites in
        main.py.
    get_composition_view(quote_id, supabase, user_id=None) -> dict
        For the GET /api/quotes/{id}/composition endpoint. Alternatives
        are grouped per invoice (not per invoice_item). Each alternative
        includes a ``coverage_summary`` field describing split/merge.
    apply_composition(quote_id, selection_map, supabase, user_id,
                      quote_updated_at)
        For the POST /api/quotes/{id}/composition endpoint. Validates
        coverage existence for every selection. Merge case: setting the
        same invoice for all covered quote_items in one atomic update.
    validate_composition(quote_id, selection_map, supabase) -> ValidationResult
        Pure validator — checks coverage rows exist for every pair.
    freeze_composition(quote_id, user_id, supabase) -> int
        Stamps frozen_at/frozen_by on invoice_items reached via active
        compositions. Walks quote_items → selected invoice →
        invoice_item_coverage → invoice_items.

Data model reference (see design.md §1.1):
    kvota.invoice_items(id, invoice_id, organization_id, position,
        product_name, supplier_sku, brand, quantity,
        purchase_price_original, purchase_currency, base_price_vat,
        price_includes_vat, vat_rate, weight_in_kg, customs_code,
        supplier_country, production_time_days, minimum_order_quantity,
        dimension_*_mm, license_*_cost, supplier_notes,
        version, frozen_at, frozen_by, created_at, updated_at, created_by)

    kvota.invoice_item_coverage(invoice_item_id, quote_item_id, ratio)
        PK (invoice_item_id, quote_item_id)
        ratio = invoice_item_units per quote_item_unit.

    kvota.quote_items.composition_selected_invoice_id UUID NULL
        FK -> kvota.invoices(id) ON DELETE SET NULL
        NULL = no composition chosen yet (legacy fallback path).
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


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
    that has no covering invoice_item.

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
        valid: True iff every selection has a covering invoice_item.
        errors: List of ``{"quote_item_id": ..., "invoice_id": ..., "reason": ...}``
            dicts. Empty when valid is True.
    """

    valid: bool
    errors: list[dict] = field(default_factory=list)


# ============================================================================
# Internal helpers
# ============================================================================

def _legacy_shape(qi: dict) -> dict:
    """Emit a calc-ready dict for a quote_item with no composition pointer.

    Used for pre-Phase-5c data and items left uncomposed. The engine tolerates
    None pricing fields — such items are skipped by build_calculation_inputs
    when purchase_price_original is falsy or is_unavailable is set.
    """
    return {
        # Identity (customer-side — no supplier invoice chosen yet)
        "product_name": qi.get("product_name"),
        "supplier_sku": qi.get("supplier_sku"),
        "brand": qi.get("brand"),
        "quantity": qi.get("quantity"),

        # Pricing — None because no invoice selected
        "purchase_price_original": None,
        "purchase_currency": None,
        "base_price_vat": None,
        "price_includes_vat": False,

        # Supplier-specific attrs — None for uncomposed items
        "weight_in_kg": None,
        "customs_code": None,
        "supplier_country": None,
        "license_ds_cost": None,
        "license_ss_cost": None,
        "license_sgr_cost": None,

        # Customer-side flags / markups (preserved verbatim)
        "is_unavailable": qi.get("is_unavailable", False),
        "import_banned": qi.get("import_banned", False),
        "markup": qi.get("markup"),
        "supplier_discount": qi.get("supplier_discount"),
        "vat_rate": qi.get("vat_rate"),
    }


def _build_calc_item(qi: dict, ii: dict, ratio) -> dict:
    """Merge quote_item (customer-side) + invoice_item (supplier-side) into calc dict.

    Supplier-side fields come from the invoice_item (identity, pricing,
    supplier-specific attrs). Customer-side fields come from the quote_item
    (markup/discount/flags/vat_rate). The ``ratio`` is carried on the
    coverage row but does NOT scale invoice_item.quantity at the calc
    layer — invoice_item.quantity is already the supplier's final per-line
    quantity (validated by the application layer against
    quote_item.quantity * ratio).
    """
    return {
        # Identity & pricing — from invoice_item (supplier-side)
        "product_name": ii.get("product_name"),
        "supplier_sku": ii.get("supplier_sku"),
        "brand": ii.get("brand") or qi.get("brand"),
        "quantity": ii.get("quantity"),
        "purchase_price_original": ii.get("purchase_price_original"),
        "purchase_currency": ii.get("purchase_currency"),
        "base_price_vat": ii.get("base_price_vat"),
        "price_includes_vat": ii.get("price_includes_vat", False),

        # Supplier-specific attrs — from invoice_item
        "weight_in_kg": ii.get("weight_in_kg"),
        "customs_code": ii.get("customs_code"),
        "supplier_country": ii.get("supplier_country"),
        "production_time_days": ii.get("production_time_days"),
        "minimum_order_quantity": ii.get("minimum_order_quantity"),
        "license_ds_cost": ii.get("license_ds_cost"),
        "license_ss_cost": ii.get("license_ss_cost"),
        "license_sgr_cost": ii.get("license_sgr_cost"),

        # Customer-side flags + sales markups — from quote_item
        "is_unavailable": qi.get("is_unavailable", False),
        "import_banned": qi.get("import_banned", False),
        "markup": qi.get("markup"),
        "supplier_discount": qi.get("supplier_discount"),
        "vat_rate": qi.get("vat_rate"),

        # Traceability — useful for UI highlighting and audit
        "quote_item_id": qi.get("id"),
        "invoice_item_id": ii.get("id"),
        "invoice_id": ii.get("invoice_id"),
        "coverage_ratio": ratio,
    }


def _load_coverage_with_items(
    item_ids: list[str], supabase
) -> list[dict]:
    """Fetch coverage rows plus their invoice_items in one query.

    Returns the raw coverage rows, each with an ``invoice_items`` nested dict
    from the PostgREST embedded join. Filters to only rows whose
    ``quote_item_id`` is in the given list.
    """
    if not item_ids:
        return []
    resp = (
        supabase.table("invoice_item_coverage")
        .select("invoice_item_id, quote_item_id, ratio, invoice_items!inner(*)")
        .in_("quote_item_id", item_ids)
        .execute()
    )
    return resp.data or []


# ============================================================================
# Adapter — get_composed_items (feeds build_calculation_inputs)
# ============================================================================

def get_composed_items(quote_id: str, supabase) -> list[dict]:
    """Return calc-ready items derived from the active composition.

    Walks quote_items → composition_selected_invoice_id → coverage →
    invoice_items and emits one calc dict per applicable invoice_item.

    For each quote_item:
      - ``composition_selected_invoice_id`` NULL → emit a legacy-shape dict
        with None pricing fields. The engine skips such items when no price
        is present.
      - Pointer set → emit one calc dict per covering invoice_item in the
        selected invoice:
          * 1:1 (1 coverage row, ratio=1) → one result
          * Split (N coverage rows for this qi in the selected invoice) →
            N results (one per invoice_item)
          * Merge (1 invoice_item covers N quote_items) → the invoice_item
            is emitted ONCE across all N quote_items; subsequent iterations
            see it in the ``emitted_ii`` dedup set and skip it.
      - Pointer set but no coverage row in that invoice → qi is skipped
        (uncovered — this supplier doesn't provide this quote_item).

    Query count: at most 2 SQL reads (a third lookup is only added for
    view metadata in get_composition_view, not here).
        1. SELECT * FROM quote_items WHERE quote_id = :quote_id
        2. SELECT coverage + invoice_items!inner(*) WHERE quote_item_id IN (...)

    Args:
        quote_id: UUID of the quote to compose.
        supabase: Supabase client instance (schema-scoped to kvota).

    Returns:
        List of item dicts ready to feed into ``build_calculation_inputs()``.
    """
    items_resp = (
        supabase.table("quote_items")
        .select("*")
        .eq("quote_id", quote_id)
        .execute()
    )
    qi_rows: list[dict] = items_resp.data or []

    selected_invoice_ids = {
        qi.get("composition_selected_invoice_id")
        for qi in qi_rows
        if qi.get("composition_selected_invoice_id")
    }
    if not selected_invoice_ids:
        # Legacy fallback: no composition selected anywhere → emit each qi
        # with None pricing. Single query total.
        return [_legacy_shape(qi) for qi in qi_rows]

    coverage_rows = _load_coverage_with_items(
        [qi["id"] for qi in qi_rows], supabase
    )

    # Group coverage by quote_item_id, filtered to rows whose invoice_item
    # belongs to the invoice THIS quote_item has selected.
    by_qi: dict[str, list[dict]] = defaultdict(list)
    for cov in coverage_rows:
        ii = cov.get("invoice_items") or {}
        if not ii:
            continue
        by_qi[cov["quote_item_id"]].append(cov)

    # Emit results: for each quote_item, one result per covering
    # invoice_item in its selected invoice. Merge dedup via emitted_ii set.
    emitted_ii: set[str] = set()
    results: list[dict] = []
    for qi in qi_rows:
        selected = qi.get("composition_selected_invoice_id")
        if not selected:
            results.append(_legacy_shape(qi))
            continue
        coverings = [
            cov for cov in by_qi.get(qi["id"], [])
            if (cov.get("invoice_items") or {}).get("invoice_id") == selected
        ]
        if not coverings:
            # Pointer set but no coverage row in that invoice — this supplier
            # doesn't actually cover this quote_item. Skip (do not emit).
            logger.warning(
                "Composition pointer references invoice %s with no coverage "
                "for quote_item %s — skipping",
                selected,
                qi.get("id"),
            )
            continue
        for cov in coverings:
            ii = cov["invoice_items"]
            if ii["id"] in emitted_ii:
                # Merge case: invoice_item already emitted for an earlier qi
                continue
            emitted_ii.add(ii["id"])
            results.append(_build_calc_item(qi, ii, cov.get("ratio", 1)))

    return results


# ============================================================================
# Procurement readiness check — canonical helper for workflow gates
# ============================================================================

def is_procurement_complete(quote_id: str, supabase) -> bool:
    """Return True iff every non-N/A quote_item is covered + priced.

    The canonical readiness check that replaces per-surface
    ``quote_items.purchase_price_original`` scans. Consumers:
    ``workflow_service.check_all_procurement_complete``, procurement-step's
    "can we complete?" button guard.

    A quote is procurement-complete iff **every** non-N/A quote_item row
    (``is_unavailable=False``) has at least one covering ``invoice_items``
    row in the quote_item's currently-selected invoice
    (``composition_selected_invoice_id``) where that invoice_item has
    ``purchase_price_original IS NOT NULL``.

    Returns False for an empty quote (no items at all, or every item is N/A):
    there is nothing to be complete about.

    Query count: 2 reads (quote_items + invoice_item_coverage) regardless of
    item count.

    Args:
        quote_id: UUID of the quote to check.
        supabase: Supabase client instance (schema-scoped to kvota).

    Returns:
        True when every required quote_item is covered and priced, else False.
    """
    qi_rows: list[dict] = (
        supabase.table("quote_items")
        .select("id, is_unavailable, composition_selected_invoice_id")
        .eq("quote_id", quote_id)
        .execute()
        .data
        or []
    )

    required_qi = [qi for qi in qi_rows if not qi.get("is_unavailable")]
    if not required_qi:
        # Empty quote (or everything N/A) can't be "complete"
        return False

    qi_ids = [qi["id"] for qi in required_qi]
    coverage_rows: list[dict] = (
        supabase.table("invoice_item_coverage")
        .select(
            "quote_item_id, "
            "invoice_items!inner(invoice_id, purchase_price_original)"
        )
        .in_("quote_item_id", qi_ids)
        .execute()
        .data
        or []
    )

    selected_inv_by_qi = {
        qi["id"]: qi.get("composition_selected_invoice_id") for qi in required_qi
    }

    priced_qi_ids: set[str] = set()
    for cov in coverage_rows:
        ii = cov.get("invoice_items") or {}
        qi_id = cov.get("quote_item_id")
        selected = selected_inv_by_qi.get(qi_id)
        if selected is None:
            continue
        if ii.get("invoice_id") != selected:
            continue
        if ii.get("purchase_price_original") is None:
            continue
        priced_qi_ids.add(qi_id)

    return len(priced_qi_ids) == len(required_qi)


# ============================================================================
# GET composition view — for the picker UI
# ============================================================================

def get_composition_view(
    quote_id: str,
    supabase,
    user_id: Optional[str] = None,
) -> dict:
    """Return composition state with supplier alternatives for the picker.

    Produces the shape the GET /api/quotes/{id}/composition endpoint returns.
    Alternatives are grouped per invoice (not per invoice_item) — each
    alternative represents one supplier offering one concrete structure
    (1:1, split, or merge) for this quote_item.

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

        Each alternative in ``alternatives`` has:
            invoice_id, supplier_id, supplier_name, supplier_country,
            purchase_price_original, purchase_currency, base_price_vat,
            price_includes_vat, production_time_days,
            version, frozen_at,
            coverage_summary: str ("" for 1:1, "→ ..." for split,
                "← ... объединены" for merge)
            divergent_markups: bool — True when this is a merged alternative
                whose covered quote_items have different ``markup`` values
                (UI warning: ``get_composed_items`` will use the first qi's
                markup — see design.md §7.1).
    """
    items_resp = (
        supabase.table("quote_items")
        .select("*")
        .eq("quote_id", quote_id)
        .execute()
    )
    items: list[dict] = items_resp.data or []
    if not items:
        return {
            "quote_id": quote_id,
            "items": [],
            "composition_complete": False,
        }

    item_ids = [item["id"] for item in items]
    qi_by_id = {qi["id"]: qi for qi in items}

    # Query 2: coverage + invoice_items for any qi of this quote
    coverage_rows = _load_coverage_with_items(item_ids, supabase)

    # Resolve invoices and suppliers for display metadata
    invoice_ids: list[str] = sorted({
        (cov.get("invoice_items") or {}).get("invoice_id")
        for cov in coverage_rows
        if (cov.get("invoice_items") or {}).get("invoice_id")
    })
    invoices_by_id: dict[str, dict] = {}
    if invoice_ids:
        inv_resp = (
            supabase.table("invoices")
            .select("*")
            .in_("id", invoice_ids)
            .execute()
        )
        for inv in inv_resp.data or []:
            invoices_by_id[inv["id"]] = inv

    supplier_id_set: set[str] = set()
    for inv_id in invoice_ids:
        sid = (invoices_by_id.get(inv_id) or {}).get("supplier_id")
        if sid:
            supplier_id_set.add(sid)
    supplier_ids: list[str] = sorted(supplier_id_set)
    suppliers_by_id: dict[str, dict] = {}
    if supplier_ids:
        sup_resp = (
            supabase.table("suppliers")
            .select("*")
            .in_("id", supplier_ids)
            .execute()
        )
        for sup in sup_resp.data or []:
            suppliers_by_id[sup["id"]] = sup

    # For merge summary: count distinct quote_items each invoice_item covers
    # (globally within this quote — restricted by the quote-scoped qi set).
    qi_count_by_ii: dict[str, set[str]] = defaultdict(set)
    for cov in coverage_rows:
        ii = cov.get("invoice_items") or {}
        if ii.get("id"):
            qi_count_by_ii[ii["id"]].add(cov["quote_item_id"])

    # Lookup: for a given invoice_item, list of covered quote_item names
    # (used to render the merge label like "← bolt, nut, washer объединены")
    covered_qi_names_by_ii: dict[str, list[str]] = {}
    for ii_id, qi_ids in qi_count_by_ii.items():
        names = []
        for qid in qi_ids:
            qrow = qi_by_id.get(qid) or {}
            nm = qrow.get("product_name")
            if nm:
                names.append(nm)
        covered_qi_names_by_ii[ii_id] = names

    # Group per (quote_item_id, invoice_id) — each group is one alternative
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for cov in coverage_rows:
        ii = cov.get("invoice_items") or {}
        inv_id = ii.get("invoice_id")
        if not inv_id:
            continue
        groups[(cov["quote_item_id"], inv_id)].append(cov)

    # Build alternatives per quote_item
    alternatives_by_item: dict[str, list[dict]] = defaultdict(list)
    for (qi_id, inv_id), cov_list in groups.items():
        inv = invoices_by_id.get(inv_id) or {}
        sup = suppliers_by_id.get(inv.get("supplier_id") or "") or {}

        # Aggregate per-invoice display numbers by summing across the
        # invoice_items covering this qi (split case sums the price across
        # split parts; 1:1 just forwards the single price).
        unique_ii: dict[str, dict] = {}
        for cov in cov_list:
            ii = cov.get("invoice_items") or {}
            if ii.get("id"):
                unique_ii[ii["id"]] = ii

        # Representative invoice_item for singular display fields
        # (currency, frozen_at, version). Split alternatives keep these
        # from the first invoice_item — the UI expands details on click.
        first_ii = next(iter(unique_ii.values()), {})

        # Coverage summary string
        # Merge case: this invoice_item covers >1 distinct quote_items
        coverage_summary = ""
        divergent_markups = False
        first_ii_id = first_ii.get("id")
        if first_ii_id:
            covered_qi_ids = qi_count_by_ii.get(first_ii_id, set())
            n_qi_for_this_ii = len(covered_qi_ids)
            if n_qi_for_this_ii > 1:
                # Merge — list all covered quote_item names
                other_names = [
                    nm for nm in covered_qi_names_by_ii.get(first_ii_id, [])
                    if nm and nm != (qi_by_id.get(qi_id) or {}).get("product_name")
                ]
                # Include self first, then siblings, for a readable label
                self_name = (qi_by_id.get(qi_id) or {}).get("product_name")
                display_names = [n for n in [self_name, *other_names] if n]
                if display_names:
                    coverage_summary = "← " + ", ".join(display_names) + " объединены"
                else:
                    coverage_summary = "← объединены"
                # Divergent markups: the covered quote_items have different
                # `markup` values. Matters because get_composed_items picks
                # the first qi's markup (option a, design.md §7.1) — UI
                # warns so the user can decide.
                covered_markups = {
                    (qi_by_id.get(qid) or {}).get("markup")
                    for qid in covered_qi_ids
                    if (qi_by_id.get(qid) or {}).get("markup") is not None
                }
                divergent_markups = len(covered_markups) > 1
            elif len(unique_ii) > 1:
                # Split — multiple invoice_items cover this single qi
                parts = []
                for cov in cov_list:
                    ii = cov.get("invoice_items") or {}
                    nm = ii.get("product_name") or "?"
                    ratio = cov.get("ratio", 1)
                    parts.append(f"{nm} ×{ratio}")
                coverage_summary = "→ " + " + ".join(parts)
            # else: 1:1 → empty string

        alt = {
            "invoice_id": inv_id,
            "supplier_id": inv.get("supplier_id"),
            "supplier_name": sup.get("name"),
            "supplier_country": sup.get("country"),
            "purchase_price_original": first_ii.get("purchase_price_original"),
            "purchase_currency": first_ii.get("purchase_currency"),
            "base_price_vat": first_ii.get("base_price_vat"),
            "price_includes_vat": first_ii.get("price_includes_vat"),
            "production_time_days": first_ii.get("production_time_days"),
            "version": first_ii.get("version"),
            "frozen_at": first_ii.get("frozen_at"),
            "coverage_summary": coverage_summary,
            "divergent_markups": divergent_markups,
        }
        alternatives_by_item[qi_id].append(alt)

    # Assemble view items with selection state
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
            "name": item.get("product_name") or item.get("name"),
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
    """Verify every selected (quote_item_id, invoice_id) has a covering invoice_item.

    Pure function — does not mutate anything, does not check the quote's
    updated_at. Safe to call from preflight endpoints.

    A selection is valid when at least one invoice_item in the target invoice
    has a coverage row linking it to the quote_item.

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
    coverage_rows = _load_coverage_with_items(item_ids, supabase)

    # Build (quote_item_id, invoice_id) set of covered pairs
    covered_pairs: set[tuple[str, str]] = set()
    for cov in coverage_rows:
        ii = cov.get("invoice_items") or {}
        inv_id = ii.get("invoice_id")
        if inv_id:
            covered_pairs.add((cov["quote_item_id"], inv_id))

    errors: list[dict] = []
    for qi_id, inv_id in selection_map.items():
        if (qi_id, inv_id) not in covered_pairs:
            errors.append({
                "quote_item_id": qi_id,
                "invoice_id": inv_id,
                "reason": "no matching invoice_item_coverage row",
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
         selection has no covering invoice_item. No writes on failure.
      2. (Optional) Optimistic concurrency check — if quote_updated_at is
         provided, compare against the current value in the DB and raise
         ConcurrencyError on mismatch. Skipped when None (e.g. for scripted
         backfills).
      3. UPDATE quote_items.composition_selected_invoice_id = :invoice_id
         for each entry in selection_map. Merge case is handled naturally:
         UI submits N entries with the same invoice_id when that invoice's
         one invoice_item covers N quote_items; each qi row gets updated.
      4. Bump quotes.updated_at to force downstream cache invalidation.

    Note: steps 3 and 4 are NOT wrapped in a DB transaction here because the
    Supabase REST API does not expose transactions to the Python client. If
    strict atomicity is required in the future, move to a Postgres RPC or
    use supabase-py's ``rpc()`` wrapper.

    Args:
        quote_id: Quote UUID.
        selection_map: ``{quote_item_id: invoice_id}`` from the client.
        supabase: Supabase client instance.
        user_id: Acting user ID (for future audit logging; currently used
            only to disambiguate logs).
        quote_updated_at: Optional ISO timestamp captured by the client when
            it loaded the quote. Pass None to skip the concurrency check.

    Raises:
        ValidationError: selection references non-existent coverage pair(s).
        ConcurrencyError: quote_updated_at does not match the current value.
    """
    # 1. Validate
    result = validate_composition(quote_id, selection_map, supabase)
    if not result.valid:
        raise ValidationError(result.errors)

    # 2. Optimistic concurrency check (opt-in)
    if quote_updated_at is not None:
        quote_resp = (
            supabase.table("quotes")
            .select("updated_at")
            .eq("id", quote_id)
            .is_("deleted_at", None)
            .execute()
        )
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
    """Stamp frozen_at/frozen_by on all invoice_items currently in active compositions.

    Idempotent: already-frozen rows are skipped, so re-running is a no-op.
    An invoice_item is "active" for this quote iff there is some quote_item
    whose composition_selected_invoice_id matches the invoice_item's
    invoice_id AND a coverage row links them.

    Called from the KP send flow — when procurement sends a KP to the
    supplier, the composition at that moment becomes immutable history.

    Args:
        quote_id: Quote UUID.
        user_id: Acting user ID (stamped into frozen_by).
        supabase: Supabase client instance.

    Returns:
        Number of invoice_items rows frozen by this call. 0 when there is
        nothing to freeze (no composition set, or every row is already frozen).
    """
    items_resp = (
        supabase.table("quote_items")
        .select("id,composition_selected_invoice_id")
        .eq("quote_id", quote_id)
        .execute()
    )
    items: list[dict] = items_resp.data or []

    active_pairs: list[tuple[str, str]] = [
        (item["id"], item["composition_selected_invoice_id"])
        for item in items
        if item.get("composition_selected_invoice_id")
    ]
    if not active_pairs:
        return 0

    item_ids = [pair[0] for pair in active_pairs]
    coverage_rows = _load_coverage_with_items(item_ids, supabase)

    active_pairs_set: set[tuple[str, str]] = set(active_pairs)

    # Determine which invoice_items to freeze:
    #   - its invoice_id == the qi's selected invoice (via active_pairs)
    #   - currently unfrozen
    to_freeze: dict[str, dict] = {}
    for cov in coverage_rows:
        ii = cov.get("invoice_items") or {}
        ii_id = ii.get("id")
        inv_id = ii.get("invoice_id")
        if not ii_id or not inv_id:
            continue
        if (cov["quote_item_id"], inv_id) not in active_pairs_set:
            continue
        if ii.get("frozen_at") is not None:
            continue
        # Dedup: one invoice_item may be reached via multiple qi (merge) —
        # freeze it only once.
        to_freeze.setdefault(ii_id, ii)

    if not to_freeze:
        return 0

    now_iso = datetime.now(timezone.utc).isoformat()
    frozen_count = 0
    for ii_id in to_freeze:
        supabase.table("invoice_items").update({
            "frozen_at": now_iso,
            "frozen_by": user_id,
        }).eq("id", ii_id).execute()
        frozen_count += 1

    if frozen_count:
        logger.info(
            "Composition frozen: quote_id=%s rows=%d user_id=%s",
            quote_id,
            frozen_count,
            user_id,
        )

    return frozen_count
