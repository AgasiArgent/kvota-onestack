"""
Specification PDF Export Service

Generates Russian contract specification documents (Спецификация).
Uses HTML → weasyprint → PDF rendering.

Feature #70: Preview PDF specification with all 18 spec fields.
"""

from decimal import Decimal
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass

from services.export_data_mapper import ExportData, format_date_russian, amount_in_words_russian


@dataclass
class SpecificationData:
    """
    Data structure for specification PDF generation.
    Contains all data from the specifications table plus related entities.
    """
    specification: Dict[str, Any]  # From specifications table
    quote: Dict[str, Any]  # From quotes table
    items: List[Dict[str, Any]]  # From quote_items with calculations
    customer: Dict[str, Any]  # From customers table
    organization: Dict[str, Any]  # From organizations table
    calculations: Dict[str, Any]  # Totals from quote_calculation_summaries


def generate_specification_html(data: ExportData, contract_info: Dict[str, Any] = None) -> str:
    """
    Generate HTML for specification document.

    Args:
        data: ExportData from export_data_mapper
        contract_info: Optional contract details (number, date, etc.)

    Returns:
        HTML string ready for PDF rendering
    """
    contract_info = contract_info or {}

    quote = data.quote
    customer = data.customer
    organization = data.organization
    items = data.items
    calculations = data.calculations

    # Default values
    spec_number = contract_info.get("spec_number", quote.get("quote_number", "б/н"))
    contract_number = contract_info.get("contract_number", "")
    contract_date = contract_info.get("contract_date", format_date_russian())
    spec_date = format_date_russian()

    currency = quote.get("currency", "RUB")
    currency_symbol = {"RUB": "₽", "USD": "$", "EUR": "€", "CNY": "¥"}.get(currency, currency)

    # Calculate totals
    total_with_vat = calculations.get("total_with_vat", 0)
    total_no_vat = calculations.get("total_no_vat", 0)

    # Build product rows
    product_rows = ""
    for i, item in enumerate(items, 1):
        calc = item.get("calc", {})
        qty = item.get("quantity", 1)
        price_per_unit = calc.get("AJ16", 0)  # Sales price per unit (no VAT)
        total = calc.get("AL16", 0)  # Total with VAT

        product_rows += f"""
        <tr>
            <td style="text-align: center;">{i}</td>
            <td>{item.get('product_name', '')}</td>
            <td>{item.get('product_code', '-')}</td>
            <td style="text-align: center;">{qty}</td>
            <td style="text-align: center;">{item.get('unit', 'шт')}</td>
            <td style="text-align: right;">{currency_symbol}{price_per_unit:,.2f}</td>
            <td style="text-align: right;">{currency_symbol}{total:,.2f}</td>
        </tr>
        """

    # Amount in words
    amount_words = amount_in_words_russian(float(total_with_vat), currency)

    html = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: A4;
                margin: 2cm;
            }}
            body {{
                font-family: 'DejaVu Sans', Arial, sans-serif;
                font-size: 10pt;
                line-height: 1.4;
                color: #333;
            }}
            h1 {{
                text-align: center;
                font-size: 14pt;
                margin-bottom: 0.5cm;
            }}
            h2 {{
                font-size: 12pt;
                margin-top: 0.5cm;
            }}
            .header {{
                text-align: center;
                margin-bottom: 1cm;
            }}
            .parties {{
                margin-bottom: 1cm;
            }}
            .party {{
                margin-bottom: 0.5cm;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 0.5cm 0;
            }}
            th, td {{
                border: 1px solid #333;
                padding: 0.3cm;
                font-size: 9pt;
            }}
            th {{
                background: #f0f0f0;
                font-weight: bold;
            }}
            .total-row {{
                font-weight: bold;
                background: #f8f8f8;
            }}
            .amount-words {{
                margin: 0.5cm 0;
                font-style: italic;
            }}
            .signatures {{
                margin-top: 2cm;
                display: flex;
                justify-content: space-between;
            }}
            .signature-block {{
                width: 45%;
            }}
            .signature-line {{
                border-bottom: 1px solid #333;
                margin-top: 1.5cm;
                padding-bottom: 0.2cm;
            }}
            .delivery {{
                margin: 1cm 0;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>СПЕЦИФИКАЦИЯ № {spec_number}</h1>
            <p>к Договору № {contract_number} от {contract_date}</p>
            <p>от «{spec_date}»</p>
        </div>

        <div class="parties">
            <div class="party">
                <strong>Поставщик:</strong> {organization.get('name', 'Организация')},
                ИНН {organization.get('inn', '-')},
                {organization.get('legal_address', '')}
            </div>
            <div class="party">
                <strong>Покупатель:</strong> {customer.get('company_name', customer.get('name', 'Покупатель'))},
                ИНН {customer.get('inn', '-')},
                {customer.get('address', '')}
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th style="width: 5%;">№</th>
                    <th style="width: 35%;">Наименование</th>
                    <th style="width: 15%;">Артикул</th>
                    <th style="width: 8%;">Кол-во</th>
                    <th style="width: 7%;">Ед.</th>
                    <th style="width: 15%;">Цена</th>
                    <th style="width: 15%;">Сумма</th>
                </tr>
            </thead>
            <tbody>
                {product_rows}
            </tbody>
            <tfoot>
                <tr class="total-row">
                    <td colspan="6" style="text-align: right;">Итого без НДС:</td>
                    <td style="text-align: right;">{currency_symbol}{total_no_vat:,.2f}</td>
                </tr>
                <tr class="total-row">
                    <td colspan="6" style="text-align: right;">НДС (20%):</td>
                    <td style="text-align: right;">{currency_symbol}{total_with_vat - total_no_vat:,.2f}</td>
                </tr>
                <tr class="total-row">
                    <td colspan="6" style="text-align: right;"><strong>ИТОГО с НДС:</strong></td>
                    <td style="text-align: right;"><strong>{currency_symbol}{total_with_vat:,.2f}</strong></td>
                </tr>
            </tfoot>
        </table>

        <div class="amount-words">
            <strong>Сумма прописью:</strong> {amount_words}
        </div>

        <div class="delivery">
            <h2>Условия поставки:</h2>
            <p><strong>Условия:</strong> {data.variables.get('offer_incoterms', 'DDP')}</p>
            <p><strong>Срок поставки:</strong> {data.variables.get('delivery_time', 30)} дней</p>
            <p><strong>Адрес доставки:</strong> {customer.get('delivery_address', customer.get('address', 'По согласованию'))}</p>
        </div>

        <div class="signatures">
            <div class="signature-block">
                <strong>Поставщик:</strong>
                <div class="signature-line">
                    _________________ / {organization.get('director_name', '_________________')} /
                </div>
                <p>М.П.</p>
            </div>
            <div class="signature-block">
                <strong>Покупатель:</strong>
                <div class="signature-line">
                    _________________ / {customer.get('contact_person', '_________________')} /
                </div>
                <p>М.П.</p>
            </div>
        </div>
    </body>
    </html>
    """

    return html


def generate_specification_pdf(data: ExportData, contract_info: Dict[str, Any] = None) -> bytes:
    """
    Generate Specification PDF document.

    Args:
        data: ExportData from export_data_mapper
        contract_info: Optional contract details

    Returns:
        PDF file as bytes
    """
    try:
        from weasyprint import HTML

        html = generate_specification_html(data, contract_info)
        pdf_bytes = HTML(string=html).write_pdf()
        return pdf_bytes
    except ImportError:
        raise ImportError("weasyprint is required for PDF generation. Install with: pip install weasyprint")


# ============================================================================
# Feature #70: Enhanced specification PDF generation from specifications table
# ============================================================================

def fetch_specification_data(spec_id: str, org_id: str) -> SpecificationData:
    """
    Fetch all data needed for specification PDF from the specifications table.

    Args:
        spec_id: Specification UUID
        org_id: Organization UUID (for security)

    Returns:
        SpecificationData with all necessary information
    """
    from services.database import get_supabase

    supabase = get_supabase()

    # 1. Fetch specification
    spec_result = supabase.table("specifications") \
        .select("*") \
        .eq("id", spec_id) \
        .eq("organization_id", org_id) \
        .execute()

    if not spec_result.data:
        raise ValueError(f"Specification not found: {spec_id}")

    specification = spec_result.data[0]
    quote_id = specification.get("quote_id")

    # 2. Fetch quote
    quote_result = supabase.table("quotes") \
        .select("*") \
        .eq("id", quote_id) \
        .execute()

    quote = quote_result.data[0] if quote_result.data else {}

    # 3. Fetch customer
    customer_result = supabase.table("customers") \
        .select("*") \
        .eq("id", quote.get("customer_id")) \
        .execute()

    customer = customer_result.data[0] if customer_result.data else {}

    # 4. Fetch organization
    org_result = supabase.table("organizations") \
        .select("*") \
        .eq("id", org_id) \
        .execute()

    organization = org_result.data[0] if org_result.data else {}

    # 5. Fetch quote items
    items_result = supabase.table("quote_items") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .order("position") \
        .execute()

    items = items_result.data or []

    # 6. Fetch calculation results for each item
    for item in items:
        calc_result = supabase.table("quote_calculation_results") \
            .select("phase_results") \
            .eq("quote_item_id", item["id"]) \
            .execute()

        if calc_result.data:
            item["calc"] = calc_result.data[0].get("phase_results", {})
        else:
            item["calc"] = {}

    # 7. Fetch calculation summary
    summary_result = supabase.table("quote_calculation_summaries") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .execute()

    calculations = {}
    if summary_result.data:
        calculations = summary_result.data[0]
    else:
        # Calculate from items if no summary
        calculations = _calculate_totals_from_items(items, specification.get("specification_currency", quote.get("currency", "RUB")))

    return SpecificationData(
        specification=specification,
        quote=quote,
        items=items,
        customer=customer,
        organization=organization,
        calculations=calculations
    )


def _calculate_totals_from_items(items: List[Dict], currency: str) -> Dict[str, Any]:
    """Calculate totals from item calculation results"""
    totals = {
        "total_purchase": Decimal("0"),
        "total_logistics": Decimal("0"),
        "total_cogs": Decimal("0"),
        "total_profit": Decimal("0"),
        "total_no_vat": Decimal("0"),
        "total_with_vat": Decimal("0"),
        "total_vat": Decimal("0"),
        "currency": currency,
    }

    for item in items:
        calc = item.get("calc", {})
        totals["total_purchase"] += Decimal(str(calc.get("S16", 0)))
        totals["total_logistics"] += Decimal(str(calc.get("V16", 0)))
        totals["total_cogs"] += Decimal(str(calc.get("AB16", 0)))
        totals["total_profit"] += Decimal(str(calc.get("AF16", 0)))
        totals["total_no_vat"] += Decimal(str(calc.get("AK16", 0)))
        totals["total_with_vat"] += Decimal(str(calc.get("AL16", 0)))
        totals["total_vat"] += Decimal(str(calc.get("AP16", 0)))

    return {k: float(v) if isinstance(v, Decimal) else v for k, v in totals.items()}


def generate_spec_pdf_html(data: SpecificationData) -> str:
    """
    Generate HTML for specification document using data from specifications table.

    This uses all 18 fields from the specifications table for accurate document generation.

    Args:
        data: SpecificationData from fetch_specification_data

    Returns:
        HTML string ready for PDF rendering
    """
    spec = data.specification
    quote = data.quote
    customer = data.customer
    organization = data.organization
    items = data.items
    calculations = data.calculations

    # Specification fields (18 fields from the specifications table)
    spec_number = spec.get("specification_number") or "б/н"
    proposal_idn = spec.get("proposal_idn") or quote.get("idn_quote", "-")
    item_ind_sku = spec.get("item_ind_sku") or "-"
    sign_date = spec.get("sign_date")
    validity_period = spec.get("validity_period") or "90 дней"
    readiness_period = spec.get("readiness_period") or "30-45 дней"
    logistics_period = spec.get("logistics_period") or "14-21 дней"

    # Currency info
    spec_currency = spec.get("specification_currency") or quote.get("currency", "RUB")
    exchange_rate = spec.get("exchange_rate_to_ruble")

    # Payment terms
    payment_term_after_upd = spec.get("client_payment_term_after_upd")
    client_payment_terms = spec.get("client_payment_terms") or "100% предоплата"

    # Shipping info
    cargo_pickup_country = spec.get("cargo_pickup_country") or "Китай"
    goods_shipment_country = spec.get("goods_shipment_country") or "Китай"
    delivery_city = spec.get("delivery_city_russia") or customer.get("city", "Москва")
    cargo_type = spec.get("cargo_type") or "Генеральный"
    supplier_payment_country = spec.get("supplier_payment_country") or "Китай"

    # Legal entities
    our_legal_entity = spec.get("our_legal_entity") or organization.get("name", "Поставщик")
    client_legal_entity = spec.get("client_legal_entity") or customer.get("company_name") or customer.get("name", "Покупатель")

    # Format dates
    sign_date_str = format_date_russian(sign_date) if sign_date else format_date_russian()
    created_date_str = format_date_russian(spec.get("created_at"))

    # Currency symbol
    currency_symbol = {"RUB": "₽", "USD": "$", "EUR": "€", "CNY": "¥"}.get(spec_currency, spec_currency)

    # Calculate totals
    total_with_vat = calculations.get("total_with_vat", 0)
    total_no_vat = calculations.get("total_no_vat", 0)
    vat_amount = total_with_vat - total_no_vat

    # Build product rows
    product_rows = ""
    for i, item in enumerate(items, 1):
        calc = item.get("calc", {})
        qty = item.get("quantity", 1)
        unit = item.get("unit", "шт")
        price_per_unit = calc.get("AJ16", 0)  # Sales price per unit (no VAT)
        item_total = calc.get("AL16", 0)  # Total with VAT

        product_rows += f"""
        <tr>
            <td style="text-align: center;">{i}</td>
            <td>{item.get('product_name', '')}</td>
            <td>{item.get('product_code', '-')}</td>
            <td style="text-align: center;">{qty}</td>
            <td style="text-align: center;">{unit}</td>
            <td style="text-align: right;">{price_per_unit:,.2f}</td>
            <td style="text-align: right;">{item_total:,.2f}</td>
        </tr>
        """

    # Amount in words
    amount_words = amount_in_words_russian(float(total_with_vat), spec_currency)

    # Exchange rate info
    exchange_rate_info = ""
    if exchange_rate and spec_currency != "RUB":
        exchange_rate_info = f"<p><strong>Курс к рублю:</strong> {exchange_rate:,.4f}</p>"

    # Payment terms info
    payment_info = f"<p><strong>Условия оплаты:</strong> {client_payment_terms}</p>"
    if payment_term_after_upd is not None and payment_term_after_upd > 0:
        payment_info += f"<p><strong>Срок оплаты после УПД:</strong> {payment_term_after_upd} дней</p>"

    html = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: A4;
                margin: 1.5cm;
            }}
            body {{
                font-family: 'DejaVu Sans', Arial, sans-serif;
                font-size: 9pt;
                line-height: 1.4;
                color: #333;
            }}
            h1 {{
                text-align: center;
                font-size: 14pt;
                margin-bottom: 0.3cm;
                margin-top: 0;
            }}
            h2 {{
                font-size: 11pt;
                margin-top: 0.5cm;
                margin-bottom: 0.3cm;
            }}
            .header {{
                text-align: center;
                margin-bottom: 0.8cm;
            }}
            .header p {{
                margin: 0.1cm 0;
            }}
            .ref-info {{
                font-size: 8pt;
                color: #666;
                margin-bottom: 0.5cm;
            }}
            .parties {{
                margin-bottom: 0.8cm;
            }}
            .party {{
                margin-bottom: 0.4cm;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 0.3cm 0;
            }}
            th, td {{
                border: 1px solid #333;
                padding: 0.2cm;
                font-size: 8pt;
            }}
            th {{
                background: #f0f0f0;
                font-weight: bold;
            }}
            .total-row {{
                font-weight: bold;
                background: #f8f8f8;
            }}
            .amount-words {{
                margin: 0.3cm 0;
                font-style: italic;
            }}
            .terms-section {{
                margin: 0.5cm 0;
                padding: 0.3cm;
                background: #f9f9f9;
                border: 1px solid #ddd;
            }}
            .terms-section p {{
                margin: 0.15cm 0;
            }}
            .signatures {{
                margin-top: 1.5cm;
                display: flex;
                justify-content: space-between;
            }}
            .signature-block {{
                width: 45%;
            }}
            .signature-line {{
                border-bottom: 1px solid #333;
                margin-top: 1cm;
                padding-bottom: 0.15cm;
            }}
            .delivery-info {{
                margin: 0.5cm 0;
            }}
            .delivery-info p {{
                margin: 0.15cm 0;
            }}
            .footer-note {{
                margin-top: 0.5cm;
                font-size: 8pt;
                color: #666;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>СПЕЦИФИКАЦИЯ № {spec_number}</h1>
            <p>к Коммерческому предложению № {proposal_idn}</p>
            <p>от «{sign_date_str}»</p>
        </div>

        <div class="ref-info">
            IDN-SKU: {item_ind_sku} | Валюта: {spec_currency} {exchange_rate_info.replace('<p>', '| ').replace('</p>', '').replace('<strong>', '').replace('</strong>', '')}
        </div>

        <div class="parties">
            <div class="party">
                <strong>Поставщик:</strong> {our_legal_entity},
                ИНН {organization.get('inn', '-')},
                {organization.get('legal_address', '')}
            </div>
            <div class="party">
                <strong>Покупатель:</strong> {client_legal_entity},
                ИНН {customer.get('inn', '-')},
                {customer.get('address', '')}
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th style="width: 4%;">№</th>
                    <th style="width: 36%;">Наименование</th>
                    <th style="width: 12%;">Артикул</th>
                    <th style="width: 8%;">Кол-во</th>
                    <th style="width: 6%;">Ед.</th>
                    <th style="width: 14%;">Цена, {currency_symbol}</th>
                    <th style="width: 14%;">Сумма, {currency_symbol}</th>
                </tr>
            </thead>
            <tbody>
                {product_rows}
            </tbody>
            <tfoot>
                <tr class="total-row">
                    <td colspan="6" style="text-align: right;">Итого без НДС:</td>
                    <td style="text-align: right;">{total_no_vat:,.2f}</td>
                </tr>
                <tr class="total-row">
                    <td colspan="6" style="text-align: right;">НДС (20%):</td>
                    <td style="text-align: right;">{vat_amount:,.2f}</td>
                </tr>
                <tr class="total-row">
                    <td colspan="6" style="text-align: right;"><strong>ИТОГО с НДС:</strong></td>
                    <td style="text-align: right;"><strong>{total_with_vat:,.2f}</strong></td>
                </tr>
            </tfoot>
        </table>

        <div class="amount-words">
            <strong>Сумма прописью:</strong> {amount_words}
        </div>

        <div class="terms-section">
            <h2>Условия поставки и оплаты</h2>
            {payment_info}
            <p><strong>Срок готовности товара:</strong> {readiness_period}</p>
            <p><strong>Срок логистики:</strong> {logistics_period}</p>
            <p><strong>Срок действия спецификации:</strong> {validity_period}</p>
        </div>

        <div class="delivery-info">
            <h2>Информация о доставке</h2>
            <p><strong>Страна забора груза:</strong> {cargo_pickup_country}</p>
            <p><strong>Страна отгрузки:</strong> {goods_shipment_country}</p>
            <p><strong>Город доставки в РФ:</strong> {delivery_city}</p>
            <p><strong>Тип груза:</strong> {cargo_type}</p>
            <p><strong>Страна оплаты поставщику:</strong> {supplier_payment_country}</p>
        </div>

        <div class="signatures">
            <div class="signature-block">
                <strong>Поставщик:</strong><br>
                {our_legal_entity}
                <div class="signature-line">
                    _________________ / {organization.get('director_name', '_________________')} /
                </div>
                <p style="font-size: 8pt;">М.П.</p>
            </div>
            <div class="signature-block">
                <strong>Покупатель:</strong><br>
                {client_legal_entity}
                <div class="signature-line">
                    _________________ / {customer.get('contact_person', '_________________')} /
                </div>
                <p style="font-size: 8pt;">М.П.</p>
            </div>
        </div>

        <div class="footer-note">
            Документ сформирован в системе OneStack. IDN: {proposal_idn}
        </div>
    </body>
    </html>
    """

    return html


def generate_spec_pdf_from_spec_id(spec_id: str, org_id: str) -> bytes:
    """
    Generate Specification PDF from specification ID.

    This is the main function to call from routes.
    Uses data from the specifications table with all 18 fields.

    Args:
        spec_id: Specification UUID
        org_id: Organization UUID (for security)

    Returns:
        PDF file as bytes

    Example:
        pdf_bytes = generate_spec_pdf_from_spec_id(spec_id, user["org_id"])
    """
    try:
        from weasyprint import HTML

        # Fetch all data
        data = fetch_specification_data(spec_id, org_id)

        # Generate HTML
        html = generate_spec_pdf_html(data)

        # Generate PDF
        pdf_bytes = HTML(string=html).write_pdf()
        return pdf_bytes

    except ImportError:
        raise ImportError("weasyprint is required for PDF generation. Install with: pip install weasyprint")
