"""
Contract-style Specification PDF Export Service

Generates Russian contract specification documents matching the
"Индутех Спецификация №1" format with:
- Header referencing contract
- Items table with 8 columns (№, IDN-SKU, Артикул, Название, Бренд, Кол-во, Цена, Сумма)
- Totals with amounts in words
- Editable delivery conditions
- Signature blocks for both parties
"""

from decimal import Decimal
from html import escape
from typing import Dict, Any, List, Tuple
from datetime import datetime

from services.database import get_supabase
from services.export_data_mapper import (
    format_date_russian,
    amount_in_words_russian,
    format_number_russian,
    get_currency_symbol,
    qty_in_words,
)


# Calculation field mappings (Excel column references from calculation engine)
# These map to specific calculation results in quote_calculation_results.phase_results
CALC_FIELDS = {
    "TOTAL_NO_VAT": "AK16",      # Total item price WITHOUT VAT
    "TOTAL_WITH_VAT": "AL16",    # Total item price WITH VAT (20%)
}


def fetch_contract_spec_data(spec_id: str, org_id: str) -> Dict[str, Any]:
    """
    Fetch all data needed for contract-style specification PDF.

    Returns dict with specification, quote, items, customer, seller_company,
    contract, signatory, and calculation totals.
    """
    supabase = get_supabase()

    # 1. Fetch specification with contract
    spec_result = supabase.table("specifications") \
        .select("*, customer_contracts(contract_number, contract_date)") \
        .eq("id", spec_id) \
        .eq("organization_id", org_id) \
        .execute()

    if not spec_result.data:
        raise ValueError(f"Specification not found: {spec_id}")

    spec = spec_result.data[0]
    contract = spec.get("customer_contracts") or {}
    quote_id = spec.get("quote_id")

    # 2. Fetch quote with related entities
    quote_result = supabase.table("quotes") \
        .select("*, customers(id, name, inn, address, postal_address), seller_companies(id, name, inn, general_director_last_name, general_director_first_name, general_director_patronymic, general_director_position, registration_address)") \
        .eq("id", quote_id) \
        .execute()

    quote = quote_result.data[0] if quote_result.data else {}
    customer = quote.get("customers") or {}
    seller_company = quote.get("seller_companies") or {}

    # 3. Fetch quote items with calculations
    items_result = supabase.table("quote_items") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .order("position") \
        .execute()

    items = items_result.data or []

    # 4. Fetch calculation results for all items in ONE batch query (N+1 fix)
    if items:
        item_ids = [item["id"] for item in items]
        calc_results = supabase.table("quote_calculation_results") \
            .select("quote_item_id, phase_results") \
            .in_("quote_item_id", item_ids) \
            .execute()

        # Create lookup dict for O(1) access
        calc_lookup = {r["quote_item_id"]: r.get("phase_results", {}) for r in (calc_results.data or [])}

        # Merge calculation results into items
        for item in items:
            item["calc"] = calc_lookup.get(item["id"], {})

    # 5. Fetch calculation summary
    summary_result = supabase.table("quote_calculation_summaries") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .execute()

    calculations = summary_result.data[0] if summary_result.data else {}

    # 6. Fetch signatory from customer_contacts
    signatory = {}
    if customer.get("id"):
        signatory_result = supabase.table("customer_contacts") \
            .select("name, position") \
            .eq("customer_id", customer.get("id")) \
            .eq("is_signatory", True) \
            .limit(1) \
            .execute()

        if signatory_result.data:
            signatory = signatory_result.data[0]

    # 7. Fetch organization for fallback
    org_result = supabase.table("organizations") \
        .select("*") \
        .eq("id", org_id) \
        .execute()

    organization = org_result.data[0] if org_result.data else {}

    return {
        "specification": spec,
        "quote": quote,
        "items": items,
        "customer": customer,
        "seller_company": seller_company,
        "contract": contract,
        "signatory": signatory,
        "calculations": calculations,
        "organization": organization,
    }


def _calculate_totals(items: List[Dict], currency: str) -> Dict[str, float]:
    """Calculate totals from item calculation results."""
    totals = {
        "total_qty": 0,
        "total_no_vat": Decimal("0"),
        "total_with_vat": Decimal("0"),
        "vat_amount": Decimal("0"),
    }

    for item in items:
        calc = item.get("calc", {})
        qty = max(item.get("quantity") or 1, 1)  # Ensure qty is at least 1
        totals["total_qty"] += qty
        totals["total_no_vat"] += Decimal(str(calc.get(CALC_FIELDS["TOTAL_NO_VAT"], 0)))
        totals["total_with_vat"] += Decimal(str(calc.get(CALC_FIELDS["TOTAL_WITH_VAT"], 0)))

    totals["vat_amount"] = totals["total_with_vat"] - totals["total_no_vat"]

    return {
        "total_qty": totals["total_qty"],
        "total_no_vat": float(totals["total_no_vat"]),
        "total_with_vat": float(totals["total_with_vat"]),
        "vat_amount": float(totals["vat_amount"]),
    }


# Note: format_number_russian, qty_in_words moved to export_data_mapper.py
# Import via: from services.export_data_mapper import format_number_russian, qty_in_words


def generate_contract_spec_html(data: Dict[str, Any], delivery_conditions: Dict[str, str]) -> str:
    """
    Generate HTML for contract-style specification document.

    Args:
        data: Dict from fetch_contract_spec_data
        delivery_conditions: Dict with 11 user-edited delivery condition strings

    Returns:
        HTML string ready for PDF rendering
    """
    spec = data["specification"]
    quote = data["quote"]
    items = data["items"]
    customer = data["customer"]
    seller_company = data["seller_company"]
    contract = data["contract"]
    signatory = data["signatory"]
    calculations = data["calculations"]
    organization = data["organization"]

    # Specification fields
    spec_number = spec.get("specification_number") or "б/н"
    spec_date = format_date_russian(spec.get("specification_date") or spec.get("sign_date"))

    # Contract fields
    contract_number = contract.get("contract_number", "б/н")
    contract_date = format_date_russian(contract.get("contract_date"))

    # Company names
    seller_name = seller_company.get("name") or spec.get("our_legal_entity") or organization.get("name", "Поставщик")
    customer_name = customer.get("company_name") or customer.get("name") or spec.get("client_legal_entity", "Покупатель")

    # Director/signatory names - construct from separate name parts
    seller_director_parts = [
        seller_company.get("general_director_last_name", ""),
        seller_company.get("general_director_first_name", ""),
        seller_company.get("general_director_patronymic", "")
    ]
    seller_director = " ".join(p for p in seller_director_parts if p) or "_________________"
    customer_signatory = signatory.get("name") or customer.get("contact_person", "_________________")
    signatory_position = signatory.get("position", "Генеральный директор")

    # Currency
    spec_currency = spec.get("specification_currency") or quote.get("currency", "RUB")
    currency_symbol = get_currency_symbol(spec_currency)

    # Calculate totals
    if calculations:
        totals = {
            "total_qty": sum(item.get("quantity", 1) for item in items),
            "total_no_vat": calculations.get("total_no_vat", 0),
            "total_with_vat": calculations.get("total_with_vat", 0),
            "vat_amount": calculations.get("total_with_vat", 0) - calculations.get("total_no_vat", 0),
        }
    else:
        totals = _calculate_totals(items, spec_currency)

    # Build product rows (8 columns)
    product_rows = ""
    for i, item in enumerate(items, 1):
        calc = item.get("calc", {})
        qty = max(item.get("quantity") or 1, 1)  # Ensure qty is at least 1 (division by zero fix)

        # Price with VAT per unit = TOTAL_WITH_VAT / quantity
        item_total_vat = float(calc.get(CALC_FIELDS["TOTAL_WITH_VAT"], 0))
        price_per_unit_vat = item_total_vat / qty  # Safe: qty is always >= 1

        product_rows += f"""
        <tr>
            <td style="text-align: center;">{i}</td>
            <td>{item.get('item_ind_sku', '-')}</td>
            <td>{item.get('product_code', '-')}</td>
            <td>{item.get('product_name', '')}</td>
            <td>{item.get('brand', '-')}</td>
            <td style="text-align: center;">{qty}</td>
            <td style="text-align: right;">{format_number_russian(price_per_unit_vat)} {currency_symbol}</td>
            <td style="text-align: right;">{format_number_russian(item_total_vat)} {currency_symbol}</td>
        </tr>
        """

    # Amount in words
    total_with_vat = totals["total_with_vat"]
    vat_amount = totals["vat_amount"]
    total_qty = totals["total_qty"]

    amount_words = amount_in_words_russian(float(total_with_vat), spec_currency)
    qty_words = qty_in_words(total_qty)

    # Unit form for quantity
    last_digit = total_qty % 10
    last_two = total_qty % 100
    if last_two in (11, 12, 13, 14):
        unit_form = "штук (единиц)"
    elif last_digit == 1:
        unit_form = "штука (единица)"
    elif last_digit in (2, 3, 4):
        unit_form = "штуки (единицы)"
    else:
        unit_form = "штук (единиц)"

    # Build delivery conditions section from user-edited fields (with HTML escaping for XSS protection)
    conditions_html = ""
    if delivery_conditions.get("quality"):
        conditions_html += f"<p>{escape(delivery_conditions['quality'])}</p>"
    if delivery_conditions.get("transport"):
        conditions_html += f"<p>{escape(delivery_conditions['transport'])}</p>"
    if delivery_conditions.get("currency_note"):
        conditions_html += f"<p>{escape(delivery_conditions['currency_note'])}</p>"
    if delivery_conditions.get("payment_terms_text"):
        conditions_html += f"<p>{escape(delivery_conditions['payment_terms_text'])}</p>"
    if delivery_conditions.get("partial_delivery"):
        conditions_html += f"<p>{escape(delivery_conditions['partial_delivery'])}</p>"
    if delivery_conditions.get("delivery_responsibility"):
        conditions_html += f"<p>{escape(delivery_conditions['delivery_responsibility'])}</p>"
    if delivery_conditions.get("warehouse_address"):
        conditions_html += f"<p>{escape(delivery_conditions['warehouse_address'])}</p>"
    if delivery_conditions.get("delivery_time"):
        conditions_html += f"<p>{escape(delivery_conditions['delivery_time'])}</p>"

    # Consignee section (with HTML escaping)
    consignee_html = ""
    if delivery_conditions.get("consignee_legal") or delivery_conditions.get("consignee_delivery"):
        consignee_html = f"""
        <p><strong>Грузополучатель – {escape(customer_name)}:</strong></p>
        <p>- {escape(delivery_conditions.get('consignee_legal', ''))}</p>
        <p>- {escape(delivery_conditions.get('consignee_delivery', ''))}</p>
        """

    if delivery_conditions.get("incoterms"):
        conditions_html += f"<p>{escape(delivery_conditions['incoterms'])}</p>"

    html = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: A4;
                margin: 2cm 1.5cm;
            }}
            body {{
                font-family: 'DejaVu Sans', Arial, sans-serif;
                font-size: 10pt;
                line-height: 1.5;
                color: #000;
            }}
            h1 {{
                text-align: center;
                font-size: 14pt;
                margin: 0.5cm 0;
                text-transform: uppercase;
            }}
            .header {{
                text-align: center;
                margin-bottom: 1cm;
            }}
            .header p {{
                margin: 0.1cm 0;
            }}
            .date-row {{
                display: flex;
                justify-content: space-between;
                margin: 0.5cm 0 1cm 0;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 0.5cm 0;
            }}
            th, td {{
                border: 1px solid #000;
                padding: 0.2cm 0.3cm;
                font-size: 9pt;
            }}
            th {{
                background: #f0f0f0;
                font-weight: bold;
                text-align: center;
            }}
            .summary {{
                margin: 0.5cm 0;
            }}
            .summary p {{
                margin: 0.2cm 0;
            }}
            .conditions {{
                margin: 0.8cm 0;
            }}
            .conditions h3 {{
                font-size: 11pt;
                margin-bottom: 0.3cm;
            }}
            .conditions p {{
                margin: 0.15cm 0;
                text-align: justify;
            }}
            .signatures {{
                margin-top: 1.5cm;
                display: flex;
                justify-content: space-between;
            }}
            .signature-block {{
                width: 45%;
            }}
            .signature-block p {{
                margin: 0.1cm 0;
            }}
            .signature-line {{
                margin-top: 1cm;
                border-bottom: 1px solid #000;
                padding-bottom: 0.1cm;
            }}
            .mp {{
                font-size: 8pt;
                margin-top: 0.5cm;
            }}
            .footer {{
                margin-top: 1cm;
                text-align: center;
                font-size: 9pt;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <p>Приложение № {spec_number}</p>
            <p>к договору поставки № {contract_number}</p>
            <p>от «{contract_date}» г.</p>
        </div>

        <h1>СПЕЦИФИКАЦИЯ №{spec_number}</h1>

        <div class="header">
            <p>к договору поставки № {contract_number} от «{contract_date}» г.</p>
            <p>между {seller_name} и {customer_name}</p>
        </div>

        <div class="date-row">
            <span>г. Москва</span>
            <span>«{spec_date}» г.</span>
        </div>

        <table>
            <thead>
                <tr>
                    <th style="width: 4%;">№</th>
                    <th style="width: 12%;">IDN-SKU</th>
                    <th style="width: 12%;">Артикул</th>
                    <th style="width: 24%;">Наименование продукции</th>
                    <th style="width: 10%;">Бренд</th>
                    <th style="width: 6%;">Кол-во</th>
                    <th style="width: 14%;">Цена в т.ч. НДС (20%)</th>
                    <th style="width: 14%;">Общая стоимость в т.ч. НДС (20%)</th>
                </tr>
            </thead>
            <tbody>
                {product_rows}
            </tbody>
        </table>

        <div class="summary">
            <p><strong>Итог:</strong></p>
            <p>- общее количество поставляемой Продукции по настоящей Спецификации составляет {total_qty} ({qty_words}) {unit_form} Продукции.</p>
            <p>- общая сумма поставки Продукции по настоящей Спецификации:</p>
            <p style="margin-left: 1cm;"><strong>{format_number_russian(total_with_vat)} ({amount_words}),</strong></p>
            <p style="margin-left: 1cm;">в т.ч. НДС 20% - {format_number_russian(vat_amount)}.</p>
        </div>

        <div class="conditions">
            <h3>Условия поставки:</h3>
            {conditions_html}
            {consignee_html}
        </div>

        <p class="footer">Настоящая Спецификация согласована и подписана Сторонами в 2 (двух) подлинных экземплярах.</p>

        <div class="signatures">
            <div class="signature-block">
                <p><strong>Поставщик</strong></p>
                <p>{seller_name}</p>
                <p>Генеральный директор</p>
                <div class="signature-line">
                    ______________/ {seller_director} /
                </div>
                <p class="mp">м.п.</p>
            </div>
            <div class="signature-block">
                <p><strong>Покупатель</strong></p>
                <p>{customer_name}</p>
                <p>{signatory_position}</p>
                <div class="signature-line">
                    ______________/ {customer_signatory} /
                </div>
                <p class="mp">м.п.</p>
            </div>
        </div>
    </body>
    </html>
    """

    return html


def generate_contract_spec_pdf(spec_id: str, org_id: str, delivery_conditions: Dict[str, str]) -> Tuple[bytes, str]:
    """
    Generate contract-style specification PDF.

    Args:
        spec_id: Specification UUID
        org_id: Organization UUID
        delivery_conditions: Dict with 11 user-edited delivery condition strings

    Returns:
        Tuple of (PDF file as bytes, specification_number for filename)
    """
    try:
        from weasyprint import HTML

        # Fetch all data
        data = fetch_contract_spec_data(spec_id, org_id)

        # Generate HTML
        html = generate_contract_spec_html(data, delivery_conditions)

        # Generate PDF
        pdf_bytes = HTML(string=html).write_pdf()

        # Return spec_number along with PDF bytes to avoid redundant DB fetch in route
        spec_number = data["specification"].get("specification_number") or data["specification"].get("proposal_idn") or "spec"

        return pdf_bytes, spec_number

    except ImportError:
        raise ImportError("weasyprint is required for PDF generation. Install with: pip install weasyprint")
