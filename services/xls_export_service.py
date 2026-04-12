"""
Invoice XLS Export Service

Generates XLSX file from an invoice and its assigned quote items using openpyxl.
Language parameter controls column headers and item name field.

Called by POST /api/invoices/{id}/download-xls.
"""

import logging
from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from services.database import get_supabase

logger = logging.getLogger(__name__)


# --- Column definitions ---

COLUMNS_RU: list[tuple[str, str]] = [
    ("Бренд", "brand"),
    ("Арт. запрошенный", "idn_sku"),
    ("Арт. производителя", "supplier_sku"),
    ("Наименование производителя", "manufacturer_product_name"),
    ("Наименование", "_item_name"),
    ("Кол-во", "quantity"),
    ("Мин. заказ", "min_order_quantity"),
    ("Цена", "purchase_price_original"),
    ("Срок (к.д.)", "production_time_days"),
    ("Вес (кг)", "weight_kg"),
    ("Размеры (В×Ш×Д мм)", "_dimensions"),
    ("Примечание", "procurement_notes"),
]

COLUMNS_EN: list[tuple[str, str]] = [
    ("Brand", "brand"),
    ("Requested SKU", "idn_sku"),
    ("Manufacturer SKU", "supplier_sku"),
    ("Manufacturer Name", "manufacturer_product_name"),
    ("Item Name", "_item_name"),
    ("Quantity", "quantity"),
    ("MOQ", "min_order_quantity"),
    ("Price", "purchase_price_original"),
    ("Lead Time (days)", "production_time_days"),
    ("Weight (kg)", "weight_kg"),
    ("Dimensions (HxWxL mm)", "_dimensions"),
    ("Notes", "procurement_notes"),
]

HEADER_FONT = Font(bold=True)
HEADER_FILL = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")


def _get_columns(language: str) -> list[tuple[str, str]]:
    """Return column definitions for the given language."""
    if language == "en":
        return COLUMNS_EN
    return COLUMNS_RU


def _format_dimensions(item: dict[str, Any]) -> str | None:
    """Format dimensions as HxWxL string, or None if all dimensions are missing."""
    h = item.get("dimension_height_mm")
    w = item.get("dimension_width_mm")
    l = item.get("dimension_length_mm")
    if h is None and w is None and l is None:
        return None
    return f"{h or 0}×{w or 0}×{l or 0}"


def _get_item_name(item: dict[str, Any], language: str) -> str | None:
    """Get item name based on language. EN uses name_en with fallback to product_name."""
    if language == "en":
        name_en = item.get("name_en")
        if name_en:
            return name_en
    return item.get("product_name")


def _get_cell_value(item: dict[str, Any], field_key: str, language: str) -> Any:
    """Extract cell value from an item for the given field key."""
    if field_key == "_item_name":
        return _get_item_name(item, language)
    if field_key == "_dimensions":
        return _format_dimensions(item)
    return item.get(field_key)


def _fetch_invoice(invoice_id: str) -> dict[str, Any]:
    """Fetch invoice with supplier name."""
    supabase = get_supabase()
    result = supabase.table("invoices").select(
        "*, suppliers!supplier_id(id, name)"
    ).eq("id", invoice_id).execute()
    data = result.data or []
    if not data:
        raise ValueError(f"Invoice not found: {invoice_id}")
    return data[0]


def _fetch_invoice_items(invoice_id: str) -> list[dict[str, Any]]:
    """Fetch quote items assigned to this invoice."""
    supabase = get_supabase()
    result = supabase.table("quote_items").select("*").eq(
        "invoice_id", invoice_id
    ).order("position").execute()
    return result.data or []


def generate_invoice_xls(invoice_id: str, language: str = "ru") -> bytes:
    """Generate XLS from invoice + assigned items.

    Path: called by POST /api/invoices/{id}/download-xls
    Params:
        invoice_id: UUID of the invoice
        language: 'ru' or 'en' -- controls column headers and item name field
    Returns:
        bytes -- the XLSX file content
    """
    invoice = _fetch_invoice(invoice_id)
    items = _fetch_invoice_items(invoice_id)
    columns = _get_columns(language)

    wb = Workbook()
    ws = wb.active
    ws.title = "Invoice Items"

    # Write header row
    for col_idx, (header, _) in enumerate(columns, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL

    # Write item rows
    for row_idx, item in enumerate(items, 2):
        for col_idx, (_, field_key) in enumerate(columns, 1):
            value = _get_cell_value(item, field_key, language)
            ws.cell(row=row_idx, column=col_idx, value=value)

    # Auto-size columns
    for col_idx, (header, _) in enumerate(columns, 1):
        max_len = len(str(header))
        for row_idx in range(2, len(items) + 2):
            cell_value = ws.cell(row=row_idx, column=col_idx).value
            if cell_value is not None:
                max_len = max(max_len, len(str(cell_value)))
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 3, 50)

    # Save to bytes
    output = BytesIO()
    wb.save(output)
    return output.getvalue()
