"""
Contract-style Specification PDF Export Service

Generates Russian contract specification documents matching the
"Индутех Спецификация №1" format with:
- Header referencing contract
- Items table with 8 columns (№, IDN-SKU, Артикул, Название, Бренд, Кол-во, Цена, Сумма)
- Totals with amounts in words
- Fixed delivery conditions template with variable substitution
- Signature blocks for both parties

IMPORTANT: Delivery conditions use FIXED template text - only variable values change.
This matches standard Russian contract language that shouldn't be edited by users.
"""

from decimal import Decimal
from html import escape
from typing import Dict, Any, List, Tuple, Optional
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
CALC_FIELDS = {
    "TOTAL_NO_VAT": "AK16",      # Total item price WITHOUT VAT
    "TOTAL_WITH_VAT": "AL16",    # Total item price WITH VAT (20%)
}


# ============================================================================
# FIXED DELIVERY CONDITIONS TEMPLATES
# These are standard Russian contract language - NOT user-editable
# ============================================================================

DELIVERY_CONDITIONS_TEMPLATE = {
    "quality": "Требования к качеству: международные стандарты качества, стандарты, установленные заводом-изготовителем.",

    "transport": "Цены по настоящей Спецификации указаны с учетом транспортных расходов.",

    "payment": "Форма оплаты и расчетов по настоящей Спецификации: перечисление денежных средств на расчетный счет Поставщика в соответствии с условиями пункта 3.6 Договора поставки № {contract_number} от {contract_date} аванс в размере {payment_percent}% в течении {payment_days} дней с момента подписания Спецификации.",

    "partial": "Поставка Продукции может производиться партиями. Объем каждой партии может определяться Сторонами дополнительно.",

    "responsibility": "Поставка Продукции осуществляется силами и за счет Поставщика. Ответственный за организацию перевозки или наём перевозчика - Поставщик.",

    "warehouse": "Продукция поставляется на склад Покупателя, расположенный по адресу: {warehouse_address}.",

    "delivery_time": "Срок поставки Продукции {delivery_days} рабочих дней с даты комплектации на складе поставщика.",

    "consignee": """Грузополучатель – {client_name}:
- адрес регистрации: {registration_address}
- адрес поставки (адрес склада Покупателя) – {delivery_address}""",

    "incoterms": "Иные согласованные условия поставки: {incoterms}.",
}


def format_signatory_name(full_name: Optional[str]) -> str:
    """
    Format 'Surname Name Patronymic' as 'Surname N.P.'

    Examples:
        'Иванов Петр Сергеевич' -> 'Иванов П.С.'
        'Иванов Петр' -> 'Иванов П.'
        'Иванов' -> 'Иванов'
        None -> '_________________'

    Args:
        full_name: Full name in Russian format (Surname Name Patronymic)

    Returns:
        Formatted name like 'Surname N.P.' or placeholder if empty
    """
    if not full_name or not full_name.strip():
        return "_________________"

    parts = full_name.strip().split()
    if len(parts) >= 3:
        # Surname Name Patronymic -> Surname N.P.
        return f"{parts[0]} {parts[1][0]}.{parts[2][0]}."
    elif len(parts) == 2:
        # Surname Name -> Surname N.
        return f"{parts[0]} {parts[1][0]}."
    else:
        # Just surname
        return full_name.strip()


def fetch_contract_spec_data(spec_id: str, org_id: str) -> Dict[str, Any]:
    """
    Fetch all data needed for contract-style specification PDF.

    Returns dict with specification, quote, items, customer, seller_company,
    contract, signatory, calculation totals, and calculation variables.
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

    # 8. Fetch calculation variables (for payment terms, incoterms, delivery time)
    calc_vars_result = supabase.table("quote_calculation_variables") \
        .select("variables") \
        .eq("quote_id", quote_id) \
        .execute()

    calc_variables = {}
    if calc_vars_result.data:
        calc_variables = calc_vars_result.data[0].get("variables", {})

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
        "calc_variables": calc_variables,
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
        qty = max(item.get("quantity") or 1, 1)
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


def _build_delivery_conditions(data: Dict[str, Any]) -> str:
    """
    Build delivery conditions HTML from fixed template + variable values.

    Uses DELIVERY_CONDITIONS_TEMPLATE with variable substitution from:
    - contract: contract_number, contract_date
    - calc_variables: advance_from_client, time_to_advance, delivery_time
    - customer: name, address, postal_address
    - quote: delivery_terms (+ " 2020" for incoterms)
    - spec: logistics_period (fallback for delivery days)

    Returns HTML string with all delivery conditions.
    """
    spec = data["specification"]
    quote = data["quote"]
    customer = data["customer"]
    contract = data["contract"]
    calc_vars = data.get("calc_variables", {})

    # Extract variable values
    contract_number = contract.get("contract_number", "б/н")
    contract_date = format_date_russian(contract.get("contract_date"))

    # Payment terms from calculation variables
    # advance_from_client is stored as decimal (e.g., 1.0 = 100%, 0.5 = 50%)
    advance_from_client = calc_vars.get("advance_from_client", 1.0)
    payment_percent = int(float(advance_from_client) * 100)  # Convert to percentage
    payment_days = int(calc_vars.get("time_to_advance", 5))  # Days for advance payment

    # Delivery time from calculation variables (already calculated: max(production) + max(logistics))
    # Fallback to logistics_period from spec if not available
    delivery_days_val = calc_vars.get("delivery_time")
    if delivery_days_val:
        delivery_days = int(delivery_days_val)
    else:
        # Parse from logistics_period string (e.g., "30-45 рабочих дней" -> "30-45")
        logistics_period = spec.get("logistics_period", "30-45")
        # Extract numeric part
        import re
        match = re.search(r'(\d+(?:-\d+)?)', str(logistics_period))
        delivery_days = match.group(1) if match else "30-45"

    # Customer addresses
    client_name = customer.get("company_name") or customer.get("name", "Покупатель")
    registration_address = customer.get("address", "не указан")
    # Postal address for delivery, fallback to registration address
    delivery_address = customer.get("postal_address") or registration_address
    warehouse_address = delivery_address

    # Incoterms from quote.delivery_terms + " 2020"
    delivery_terms = quote.get("delivery_terms", "DDP")
    incoterms = f"{delivery_terms} 2020" if delivery_terms else "DDP 2020"

    # Build conditions HTML using fixed templates
    conditions_parts = []

    # 1. Quality
    conditions_parts.append(f"<p>{escape(DELIVERY_CONDITIONS_TEMPLATE['quality'])}</p>")

    # 2. Transport
    conditions_parts.append(f"<p>{escape(DELIVERY_CONDITIONS_TEMPLATE['transport'])}</p>")

    # 3. Payment terms (with variable substitution)
    payment_text = DELIVERY_CONDITIONS_TEMPLATE["payment"].format(
        contract_number=contract_number,
        contract_date=contract_date,
        payment_percent=payment_percent,
        payment_days=payment_days
    )
    conditions_parts.append(f"<p>{escape(payment_text)}</p>")

    # 4. Partial delivery
    conditions_parts.append(f"<p>{escape(DELIVERY_CONDITIONS_TEMPLATE['partial'])}</p>")

    # 5. Responsibility
    conditions_parts.append(f"<p>{escape(DELIVERY_CONDITIONS_TEMPLATE['responsibility'])}</p>")

    # 6. Warehouse address
    warehouse_text = DELIVERY_CONDITIONS_TEMPLATE["warehouse"].format(
        warehouse_address=warehouse_address
    )
    conditions_parts.append(f"<p>{escape(warehouse_text)}</p>")

    # 7. Delivery time
    delivery_time_text = DELIVERY_CONDITIONS_TEMPLATE["delivery_time"].format(
        delivery_days=delivery_days
    )
    conditions_parts.append(f"<p>{escape(delivery_time_text)}</p>")

    # 8. Consignee (multiline)
    consignee_text = DELIVERY_CONDITIONS_TEMPLATE["consignee"].format(
        client_name=client_name,
        registration_address=registration_address,
        delivery_address=delivery_address
    )
    # Convert newlines to <br> for HTML
    consignee_html = escape(consignee_text).replace('\n', '<br>')
    conditions_parts.append(f"<p>{consignee_html}</p>")

    # 9. Incoterms
    incoterms_text = DELIVERY_CONDITIONS_TEMPLATE["incoterms"].format(
        incoterms=incoterms
    )
    conditions_parts.append(f"<p>{escape(incoterms_text)}</p>")

    return "\n".join(conditions_parts)


def generate_contract_spec_html(data: Dict[str, Any]) -> str:
    """
    Generate HTML for contract-style specification document.

    Uses FIXED template for delivery conditions - no user-editable text fields.
    Variable values are pulled from the database:
    - Payment terms from calc_variables (advance_from_client, time_to_advance)
    - Incoterms from quote.delivery_terms + " 2020"
    - Addresses from customer (address, postal_address)
    - Contract info from customer_contracts (contract_number, contract_date)

    Args:
        data: Dict from fetch_contract_spec_data

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

    # Director/signatory names - construct from separate name parts and format as "Surname N.P."
    seller_director_parts = [
        seller_company.get("general_director_last_name", ""),
        seller_company.get("general_director_first_name", ""),
        seller_company.get("general_director_patronymic", "")
    ]
    seller_director_full = " ".join(p for p in seller_director_parts if p)
    seller_director = format_signatory_name(seller_director_full)

    # Customer signatory - format as "Surname N.P."
    # Signatory comes from customer_contacts table (fetched in step 6)
    customer_signatory_full = signatory.get("name", "")
    customer_signatory = format_signatory_name(customer_signatory_full)
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
        qty = max(item.get("quantity") or 1, 1)

        # Price with VAT per unit = TOTAL_WITH_VAT / quantity
        item_total_vat = float(calc.get(CALC_FIELDS["TOTAL_WITH_VAT"], 0))
        price_per_unit_vat = item_total_vat / qty

        product_rows += f"""
        <tr>
            <td style="text-align: center;">{i}</td>
            <td>{escape(str(item.get('idn_sku') or '-'))}</td>
            <td>{escape(str(item.get('product_code', '-')))}</td>
            <td>{escape(str(item.get('product_name', '')))}</td>
            <td>{escape(str(item.get('brand', '-')))}</td>
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

    # Build delivery conditions from fixed template
    conditions_html = _build_delivery_conditions(data)

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
            <p>Приложение № {escape(str(spec_number))}</p>
            <p>к договору поставки № {escape(str(contract_number))}</p>
            <p>от «{contract_date}» г.</p>
        </div>

        <h1>СПЕЦИФИКАЦИЯ №{escape(str(spec_number))}</h1>

        <div class="header">
            <p>к договору поставки № {escape(str(contract_number))} от «{contract_date}» г.</p>
            <p>между {escape(seller_name)} и {escape(customer_name)}</p>
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
        </div>

        <p class="footer">Настоящая Спецификация согласована и подписана Сторонами в 2 (двух) подлинных экземплярах.</p>

        <div class="signatures">
            <div class="signature-block">
                <p><strong>Поставщик</strong></p>
                <p>{escape(seller_name)}</p>
                <p>Генеральный директор</p>
                <div class="signature-line">
                    ______________/ {seller_director} /
                </div>
                <p class="mp">м.п.</p>
            </div>
            <div class="signature-block">
                <p><strong>Покупатель</strong></p>
                <p>{escape(customer_name)}</p>
                <p>{escape(signatory_position)}</p>
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


def generate_contract_spec_pdf(spec_id: str, org_id: str) -> Tuple[bytes, str]:
    """
    Generate contract-style specification PDF.

    Uses fixed template for delivery conditions - no user input needed.
    All variable values are pulled from the database.

    Args:
        spec_id: Specification UUID
        org_id: Organization UUID

    Returns:
        Tuple of (PDF file as bytes, specification_number for filename)
    """
    try:
        from weasyprint import HTML

        # Fetch all data
        data = fetch_contract_spec_data(spec_id, org_id)

        # Generate HTML (no delivery_conditions parameter - uses fixed template)
        html = generate_contract_spec_html(data)

        # Generate PDF
        pdf_bytes = HTML(string=html).write_pdf()

        # Return spec_number along with PDF bytes
        spec_number = data["specification"].get("specification_number") or data["specification"].get("proposal_idn") or "spec"

        return pdf_bytes, spec_number

    except ImportError:
        raise ImportError("weasyprint is required for PDF generation. Install with: pip install weasyprint")
