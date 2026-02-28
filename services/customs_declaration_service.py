"""
Customs Declaration (GTD) XML Import Service.
Parses AltaGTD XML files and extracts declaration header, items, and payment data.

Feature: [86aftzmne] Загрузка таможенных деклараций (ДТ) из XML + учёт пошлин в план-факте
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import List, Optional, Dict, Any
import logging
import os
import uuid
import xml.etree.ElementTree as ET

from supabase import create_client, ClientOptions

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class GTDItem:
    """A single goods item (TOVG) from a customs declaration."""
    sku: Optional[str] = None
    description: Optional[str] = None
    manufacturer: Optional[str] = None
    brand: Optional[str] = None
    quantity: int = 0
    unit: Optional[str] = None
    gross_weight: Decimal = Decimal("0")
    net_weight: Decimal = Decimal("0")
    invoice_cost: Decimal = Decimal("0")
    hs_code: Optional[str] = None
    customs_value_rub: Decimal = Decimal("0")
    fee_rub: Decimal = Decimal("0")
    duty_rub: Decimal = Decimal("0")
    vat_rub: Decimal = Decimal("0")


@dataclass
class GTDParseResult:
    """Result of parsing an AltaGTD XML file."""
    regnum: Optional[str] = None
    declaration_date: Optional[str] = None
    currency: Optional[str] = None
    exchange_rate: Decimal = Decimal("0")
    sender_name: Optional[str] = None
    sender_country: Optional[str] = None
    receiver_name: Optional[str] = None
    receiver_inn: Optional[str] = None
    internal_ref: Optional[str] = None
    total_customs_value_rub: Decimal = Decimal("0")
    total_fee_rub: Decimal = Decimal("0")
    total_duty_rub: Decimal = Decimal("0")
    total_vat_rub: Decimal = Decimal("0")
    items: List[GTDItem] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# =============================================================================
# Helper: safe text extraction
# =============================================================================

def _text(element, tag: str, default: str = "") -> str:
    """Safely get text content of a child element."""
    child = element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return default


def _decimal(element, tag: str, default: str = "0") -> Decimal:
    """Safely get a Decimal value from a child element."""
    text = _text(element, tag, default)
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return Decimal(default)


# =============================================================================
# Parse B_1, B_2, B_3 total payment elements
# =============================================================================

def _parse_b_total(element, tag: str) -> Decimal:
    """
    Parse B_1/B_2/B_3 element text.
    Format: "{type_code}-{amount}-{currency_numeric}-{inn}"
    Example: "1010-30000.00-643-0242013464"
    Returns the amount as Decimal.
    """
    text = _text(element, tag)
    if not text:
        return Decimal("0")
    parts = text.split("-")
    if len(parts) >= 2:
        try:
            return Decimal(parts[1])
        except (InvalidOperation, ValueError):
            return Decimal("0")
    return Decimal("0")


# =============================================================================
# Parse G_47 flat payment elements from a BLOCK
# =============================================================================

def _parse_block_payments(block) -> dict:
    """
    Parse G_47 flat payment elements from a BLOCK.
    Pattern: G_47_{row}_{field} where field 1=type code, 4=amount.
    Returns dict: {type_code: amount_decimal}
    """
    payments = {}
    for i in range(1, 20):
        type_tag = f"G_47_{i}_1"
        amount_tag = f"G_47_{i}_4"
        type_elem = block.find(type_tag)
        if type_elem is None:
            break  # No more payment rows
        type_code = type_elem.text.strip() if type_elem.text else ""
        amount_elem = block.find(amount_tag)
        if amount_elem is not None and amount_elem.text:
            try:
                amount = Decimal(amount_elem.text.strip())
            except (InvalidOperation, ValueError):
                amount = Decimal("0")
        else:
            amount = Decimal("0")
        if type_code:
            payments[type_code] = amount
    return payments


# =============================================================================
# Distribute payments proportionally by INVOICCOST
# =============================================================================

def _distribute_payments(
    tovg_costs: List[Decimal],
    block_payments: dict,
    customs_value_rub: Decimal = Decimal("0"),
) -> List[dict]:
    """
    Distribute block-level payments and customs_value_rub across TOVGs
    proportionally by INVOICCOST.

    Returns list of dicts: [{fee_rub, duty_rub, vat_rub, customs_value_rub}, ...]
    """
    n = len(tovg_costs)
    if n == 0:
        return []

    total_cost = sum(tovg_costs)
    result = []

    fee_total = block_payments.get("1010", Decimal("0"))
    duty_total = block_payments.get("2010", Decimal("0"))
    vat_total = block_payments.get("5010", Decimal("0"))
    cv_total = customs_value_rub

    if total_cost == 0:
        # Equal distribution if all costs are zero; last item gets remainder
        fee_distributed = Decimal("0")
        duty_distributed = Decimal("0")
        vat_distributed = Decimal("0")
        cv_distributed = Decimal("0")
        for i in range(n):
            if i == n - 1:
                # Last item gets remainder to avoid rounding loss
                result.append({
                    "fee_rub": fee_total - fee_distributed,
                    "duty_rub": duty_total - duty_distributed,
                    "vat_rub": vat_total - vat_distributed,
                    "customs_value_rub": cv_total - cv_distributed,
                })
            else:
                fee_share = (fee_total / n).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                duty_share = (duty_total / n).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                vat_share = (vat_total / n).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                cv_share = (cv_total / n).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                fee_distributed += fee_share
                duty_distributed += duty_share
                vat_distributed += vat_share
                cv_distributed += cv_share
                result.append({
                    "fee_rub": fee_share,
                    "duty_rub": duty_share,
                    "vat_rub": vat_share,
                    "customs_value_rub": cv_share,
                })
        return result

    # Proportional distribution with remainder handling
    fee_distributed = Decimal("0")
    duty_distributed = Decimal("0")
    vat_distributed = Decimal("0")
    cv_distributed = Decimal("0")

    for i, cost in enumerate(tovg_costs):
        proportion = cost / total_cost

        if i == n - 1:
            # Last item gets remainder to avoid rounding errors
            fee_share = fee_total - fee_distributed
            duty_share = duty_total - duty_distributed
            vat_share = vat_total - vat_distributed
            cv_share = cv_total - cv_distributed
        else:
            fee_share = (fee_total * proportion).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            duty_share = (duty_total * proportion).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            vat_share = (vat_total * proportion).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            cv_share = (cv_total * proportion).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            fee_distributed += fee_share
            duty_distributed += duty_share
            vat_distributed += vat_share
            cv_distributed += cv_share

        result.append({
            "fee_rub": fee_share,
            "duty_rub": duty_share,
            "vat_rub": vat_share,
            "customs_value_rub": cv_share,
        })

    return result


# =============================================================================
# Main Parser
# =============================================================================

def parse_gtd_xml(file_path: str) -> GTDParseResult:
    """
    Parse an AltaGTD XML file and extract declaration data.

    Args:
        file_path: Path to the XML file (windows-1251 or utf-8 encoded).

    Returns:
        GTDParseResult with parsed data or errors.
    """
    result = GTDParseResult()

    # Read and parse XML
    try:
        raw_bytes = _read_file(file_path)
    except FileNotFoundError:
        result.errors.append(f"File not found: {file_path}")
        return result
    except Exception as e:
        result.errors.append(f"Error reading file: {str(e)}")
        return result

    try:
        root = _parse_xml_bytes(raw_bytes)
    except ET.ParseError as e:
        result.errors.append(f"Invalid XML: {str(e)}")
        return result
    except Exception as e:
        result.errors.append(f"Error parsing XML: {str(e)}")
        return result

    # Validate root element
    if root.tag != "AltaGTD":
        result.errors.append(f"Not an AltaGTD XML file (root element: {root.tag})")
        return result

    # Parse header fields
    _parse_header(root, result)

    # Parse BLOCK elements
    _parse_blocks(root, result)

    # Parse B_1/B_2/B_3 totals
    result.total_fee_rub = _parse_b_total(root, "B_1")
    result.total_duty_rub = _parse_b_total(root, "B_2")
    result.total_vat_rub = _parse_b_total(root, "B_3")

    return result


def _read_file(file_path: str) -> bytes:
    """Read file as raw bytes."""
    with open(file_path, "rb") as f:
        return f.read()


def _parse_xml_bytes(raw_bytes: bytes):
    """
    Parse XML from raw bytes, handling windows-1251 encoding.
    xml.etree.ElementTree handles the encoding declaration in the XML prolog.
    """
    # ET.fromstring expects a string or bytes. When bytes contain an encoding
    # declaration (<?xml ... encoding="windows-1251"?>), ET handles it natively.
    try:
        root = ET.fromstring(raw_bytes)
        return root
    except ET.ParseError:
        # Fallback: try decoding as windows-1251 then re-encoding as utf-8
        try:
            text = raw_bytes.decode("windows-1251")
            # Replace encoding declaration
            text = text.replace('encoding="windows-1251"', 'encoding="utf-8"')
            root = ET.fromstring(text.encode("utf-8"))
            return root
        except Exception:
            raise


def _parse_header(root, result: GTDParseResult):
    """Extract header-level fields from the AltaGTD root element."""
    # Registration number
    result.regnum = _text(root, "REGNUM")

    # Declaration date
    result.declaration_date = _text(root, "REG_DATE")

    # Currency code
    result.currency = _text(root, "G_22_3")

    # Exchange rate
    result.exchange_rate = _decimal(root, "G_23_1")

    # Sender info
    result.sender_name = _text(root, "G_2_NAM")
    result.sender_country = _text(root, "G_2_7")

    # Receiver info
    result.receiver_name = _text(root, "G_8_NAM")
    result.receiver_inn = _text(root, "G_8_6")

    # Internal reference from Comment attribute
    result.internal_ref = root.attrib.get("Comment", "")

    # Total customs value in RUB
    result.total_customs_value_rub = _decimal(root, "G_12_0")


def _parse_blocks(root, result: GTDParseResult):
    """Parse all BLOCK elements and their TOVG children."""
    for block in root.findall("BLOCK"):
        # Block-level data
        hs_code = _text(block, "G_33_1")
        customs_value_rub = _decimal(block, "G_45_0")

        # Parse G_47 payments for this block
        block_payments = _parse_block_payments(block)

        # Find all TOVG elements in this block
        tovgs = block.findall("TOVG")
        if not tovgs:
            # No items in this block, skip
            continue

        # Collect invoice costs for proportional distribution
        tovg_costs = []
        for tovg in tovgs:
            cost = _decimal(tovg, "INVOICCOST")
            tovg_costs.append(cost)

        # Distribute payments and customs_value_rub proportionally
        distributed = _distribute_payments(tovg_costs, block_payments, customs_value_rub)

        # Parse each TOVG
        for idx, tovg in enumerate(tovgs):
            item = GTDItem()
            item.sku = _text(tovg, "G31_15") or None
            item.description = _text(tovg, "G31_1") or None
            item.manufacturer = _text(tovg, "G31_11") or None
            item.brand = _text(tovg, "G31_14") or None

            # Quantity
            kolvo_text = _text(tovg, "KOLVO", "0")
            try:
                item.quantity = int(Decimal(kolvo_text))
            except (InvalidOperation, ValueError):
                item.quantity = 0

            item.unit = _text(tovg, "NAME_EDI") or None
            item.gross_weight = _decimal(tovg, "G31_35")
            item.net_weight = _decimal(tovg, "G31_38")
            item.invoice_cost = _decimal(tovg, "INVOICCOST")

            # Block-level data shared by all TOVGs
            item.hs_code = hs_code

            # Distributed payments and customs_value_rub
            if idx < len(distributed):
                item.fee_rub = distributed[idx]["fee_rub"]
                item.duty_rub = distributed[idx]["duty_rub"]
                item.vat_rub = distributed[idx]["vat_rub"]
                item.customs_value_rub = distributed[idx]["customs_value_rub"]

            result.items.append(item)


# =============================================================================
# Database Client
# =============================================================================

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")


def _get_supabase():
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(
        SUPABASE_URL,
        SUPABASE_SERVICE_KEY,
        options=ClientOptions(schema="kvota")
    )


# =============================================================================
# CRUD: Save Declaration
# =============================================================================

def save_declaration(result: GTDParseResult, org_id: str, raw_xml: str, created_by: str) -> str:
    """
    Persist a parsed GTD declaration and its items to the database.

    Args:
        result: Parsed GTD data from parse_gtd_xml().
        org_id: Organization UUID.
        raw_xml: Full XML text for audit/reprocessing.
        created_by: User UUID who uploaded the file.

    Returns:
        The UUID of the newly created customs_declarations row.

    Raises:
        Exception on duplicate regnum or database error.
    """
    client = _get_supabase()

    # Insert declaration header
    decl_data = {
        "regnum": result.regnum,
        "declaration_date": result.declaration_date,
        "currency": result.currency,
        "exchange_rate": str(result.exchange_rate),
        "sender_name": result.sender_name,
        "sender_country": result.sender_country,
        "receiver_name": result.receiver_name,
        "receiver_inn": result.receiver_inn,
        "total_customs_value_rub": str(result.total_customs_value_rub),
        "total_fee_rub": str(result.total_fee_rub),
        "total_duty_rub": str(result.total_duty_rub),
        "total_vat_rub": str(result.total_vat_rub),
        "internal_ref": result.internal_ref,
        "raw_xml": raw_xml,
        "created_by": created_by,
        "organization_id": org_id,
    }

    try:
        resp = client.table("customs_declarations").insert(decl_data).execute()
        declaration_id = resp.data[0]["id"]
    except Exception as e:
        logger.error(f"Failed to insert customs_declarations: {e}")
        raise

    # Insert items
    if result.items:
        items_data = []
        for idx, item in enumerate(result.items, start=1):
            items_data.append({
                "declaration_id": declaration_id,
                "block_number": 1,  # Simplified: block tracking is per-item in real data
                "item_number": idx,
                "hs_code": item.hs_code,
                "description": item.description,
                "manufacturer": item.manufacturer,
                "brand": item.brand,
                "sku": item.sku,
                "quantity": str(item.quantity),
                "unit": item.unit,
                "gross_weight_kg": str(item.gross_weight),
                "net_weight_kg": str(item.net_weight),
                "invoice_cost": str(item.invoice_cost),
                "invoice_currency": result.currency,
                "customs_value_rub": str(item.customs_value_rub),
                "fee_amount_rub": str(item.fee_rub),
                "duty_amount_rub": str(item.duty_rub),
                "vat_amount_rub": str(item.vat_rub),
                "organization_id": org_id,
            })

        try:
            client.table("customs_declaration_items").insert(items_data).execute()
        except Exception as e:
            logger.error(f"Failed to insert customs_declaration_items: {e}")
            raise

    return declaration_id


# =============================================================================
# CRUD: List Declarations
# =============================================================================

def list_declarations(org_id: str) -> List[Dict[str, Any]]:
    """
    List all customs declarations for an organization, ordered by date descending.
    Includes item_count and matched_count aggregated from nested items.

    Args:
        org_id: Organization UUID.

    Returns:
        List of declaration dicts with item_count and matched_count.
    """
    try:
        client = _get_supabase()
        resp = client.table("customs_declarations").select(
            "*, customs_declaration_items(id, deal_id)"
        ).eq("organization_id", org_id).order("declaration_date", desc=True).execute()

        result = []
        for d in (resp.data or []):
            items = d.pop("customs_declaration_items", []) or []
            d["item_count"] = len(items)
            d["matched_count"] = sum(1 for i in items if i.get("deal_id"))
            result.append(d)
        return result
    except Exception as e:
        logger.error(f"Failed to list customs declarations: {e}")
        return []


# =============================================================================
# CRUD: Get Declaration Items
# =============================================================================

def get_declaration_items(declaration_id: str, org_id: str) -> List[Dict[str, Any]]:
    """
    Get all items for a specific declaration.

    Args:
        declaration_id: Declaration UUID.
        org_id: Organization UUID (for access check via parent declaration).

    Returns:
        List of item dicts.
    """
    try:
        client = _get_supabase()
        # Verify declaration belongs to org
        decl_resp = client.table("customs_declarations").select("id").eq(
            "id", declaration_id
        ).eq("organization_id", org_id).execute()

        if not decl_resp.data:
            return []

        resp = client.table("customs_declaration_items").select("*").eq(
            "declaration_id", declaration_id
        ).order("item_number").execute()

        return resp.data or []
    except Exception as e:
        logger.error(f"Failed to get declaration items: {e}")
        return []


# =============================================================================
# Deal Matching (best-effort)
# =============================================================================

def match_items_to_deals(declaration_id: str, org_id: str) -> int:
    """
    Attempt to match declaration items to existing deals by SKU.
    Updates matched items with deal_id and matched_at timestamp.

    This is a best-effort operation: failures are logged but do not raise.

    Args:
        declaration_id: Declaration UUID.
        org_id: Organization UUID.

    Returns:
        Number of items successfully matched.
    """
    matched = 0
    try:
        client = _get_supabase()
        items = get_declaration_items(declaration_id, org_id)

        for item in items:
            sku = item.get("sku")
            if not sku:
                continue

            try:
                # Search for matching SKU in quote_items, filtered by org_id
                # through quotes table to prevent cross-org data leak
                qi_resp = client.table("quote_items").select(
                    "id, quote_id, quotes!inner(id, organization_id)"
                ).ilike("sku", sku).eq(
                    "quotes.organization_id", org_id
                ).execute()

                if not qi_resp.data:
                    continue

                # Try to find a deal through: quote -> specification -> deal
                for qi in qi_resp.data:
                    quote_id = qi.get("quote_id")
                    if not quote_id:
                        continue

                    spec_resp = client.table("specifications").select(
                        "id"
                    ).eq("quote_id", quote_id).execute()

                    if not spec_resp.data:
                        continue

                    spec_id = spec_resp.data[0]["id"]

                    deal_resp = client.table("deals").select(
                        "id"
                    ).eq("specification_id", spec_id).execute()

                    if not deal_resp.data:
                        continue

                    deal_id = deal_resp.data[0]["id"]

                    # Update the declaration item with deal match
                    client.table("customs_declaration_items").update({
                        "deal_id": deal_id,
                        "matched_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("id", item["id"]).execute()

                    matched += 1
                    break  # First match wins for this item

            except Exception as e:
                logger.warning(f"Match failed for item {item.get('id')}: {e}")
                continue

    except Exception as e:
        logger.error(f"Deal matching failed: {e}")

    return matched
