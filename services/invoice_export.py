"""
Invoice PDF Export Service

Generates Russian commercial invoice (Счет на оплату).
Format matches the reference invoice template from Master Bearing.
Uses HTML + WeasyPrint for PDF generation.
"""

from decimal import Decimal
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from services.export_data_mapper import (
    ExportData,
    format_date_russian,
    amount_in_words_russian,
    format_number_russian,
    get_currency_symbol,
)


# Note: get_currency_symbol and format_number_russian are now consolidated
# in export_data_mapper.py to avoid code duplication


def generate_invoice_html(data: ExportData, invoice_info: Dict[str, Any] = None) -> str:
    """
    Generate HTML for Russian commercial invoice (Счет).

    Template matches reference invoice:
    - Header with logo and contacts
    - Bank payment details section (Образец платежного поручения)
    - Invoice number and validity date
    - Seller/Buyer info blocks
    - Items table with currency
    - Totals with VAT
    - Amount in words
    - Terms (payment, delivery, includes)
    - Director signature

    Args:
        data: ExportData from export_data_mapper
        invoice_info: Optional invoice details (number, date, etc.)

    Returns:
        HTML string ready for PDF rendering
    """
    invoice_info = invoice_info or {}

    quote = data.quote
    customer = data.customer
    seller = data.seller_company or {}
    calculations = data.calculations
    variables = data.variables
    items = data.items

    # Invoice identification
    invoice_number = invoice_info.get("invoice_number", quote.get("idn_quote", "б/н"))

    # Invoice date
    invoice_date_raw = invoice_info.get("invoice_date") or quote.get("created_at")
    if isinstance(invoice_date_raw, str):
        try:
            invoice_date_obj = datetime.fromisoformat(invoice_date_raw.replace("Z", "+00:00"))
        except:
            invoice_date_obj = datetime.now()
    elif isinstance(invoice_date_raw, datetime):
        invoice_date_obj = invoice_date_raw
    else:
        invoice_date_obj = datetime.now()
    invoice_date = invoice_date_obj.strftime("%d.%m.%Y")

    # Validity date (30 days from invoice date by default)
    validity_days = seller.get("invoice_validity_days", 30) or 30
    valid_until_obj = invoice_date_obj + timedelta(days=validity_days)
    valid_until = valid_until_obj.strftime("%d.%m.%Y")

    # Currency
    currency = quote.get("currency", "RUB")
    currency_symbol = get_currency_symbol(currency)

    # Seller info (from seller_company or fallback)
    seller_name = seller.get("name", "Организация")
    seller_inn = seller.get("inn", "")
    seller_kpp = seller.get("kpp", "")
    seller_address = seller.get("registration_address", "")
    seller_phone = seller.get("phone", "")
    seller_website = seller.get("website", "")

    # Bank details - prefer selected_bank_account, fallback to seller_company fields
    bank = data.selected_bank_account or {}
    bank_name = bank.get("bank_name") or seller.get("bank_name", "")
    bank_bik = bank.get("bik") or seller.get("bik", "")
    bank_corr = bank.get("correspondent_account") or seller.get("correspondent_account", "")
    bank_account = bank.get("account_number") or seller.get("payment_account", "")

    # Director info
    director_name = ""
    if seller.get("general_director_last_name"):
        director_name = seller.get("general_director_last_name", "")
        if seller.get("general_director_first_name"):
            # Initials format: Фамилия И.О.
            first_initial = seller.get("general_director_first_name", "")[0] if seller.get("general_director_first_name") else ""
            patronymic_initial = seller.get("general_director_patronymic", "")[0] if seller.get("general_director_patronymic") else ""
            if first_initial:
                director_name += f" {first_initial}."
            if patronymic_initial:
                director_name += f"{patronymic_initial}."
    director_position = seller.get("general_director_position", "Генеральный директор")

    # Customer info
    customer_name = customer.get("name") or quote.get("customer_name") or "Покупатель"
    customer_inn = customer.get("inn") or ""
    customer_address = customer.get("address") or ""
    customer_phone = customer.get("phone") or ""

    # Calculate totals from items
    total_no_vat = Decimal("0")
    total_with_vat = Decimal("0")

    for item in items:
        calc = item.get("calc", {})
        total_no_vat += Decimal(str(calc.get("AK16", 0)))  # sales_price_total_no_vat
        total_with_vat += Decimal(str(calc.get("AL16", 0)))  # sales_price_total_with_vat

    # If no calculation results, use quote totals
    if total_with_vat == 0:
        total_no_vat = Decimal(str(calculations.get("total_no_vat", 0)))
        total_with_vat = Decimal(str(calculations.get("total_with_vat", 0)))

    vat_amount = total_with_vat - total_no_vat

    # VAT rate (22% for Russia 2025+)
    vat_rate = 22

    # Build product rows
    product_rows = ""
    for i, item in enumerate(items, 1):
        calc = item.get("calc", {})
        qty = item.get("quantity", 1)
        unit = item.get("unit", "шт.")

        # Prices from calculation results
        price_no_vat = float(calc.get("AJ16", 0))  # sales_price_per_unit_no_vat
        item_total_no_vat = float(calc.get("AK16", 0))  # sales_price_total_no_vat

        product_rows += f"""
        <tr>
            <td class="col-num">{i}</td>
            <td class="col-name">{item.get('product_name', '')}</td>
            <td class="col-qty">{qty}</td>
            <td class="col-unit">{unit}</td>
            <td class="col-price">{format_number_russian(price_no_vat)}</td>
            <td class="col-total">{format_number_russian(item_total_no_vat)}</td>
        </tr>
        """

    # Amount in words
    amount_words = amount_in_words_russian(float(total_with_vat), currency)

    # Payment terms from calculation variables
    # Use advance_from_client (not advance_percent which doesn't exist)
    advance_from_client = float(variables.get("advance_from_client", 0))
    time_to_advance_raw = int(variables.get("time_to_advance", 0))
    time_to_receiving_raw = int(variables.get("time_to_advance_on_receiving", 0))

    # Apply minimum values: at least 5 days for advance, 3 days for final payment
    time_to_advance = max(time_to_advance_raw, 5)
    time_to_receiving = max(time_to_receiving_raw, 3)

    # Build payment terms text based on advance percentage
    if advance_from_client >= 100:
        payment_terms = f"100% предоплата в течение {time_to_advance} дней"
    elif advance_from_client > 0:
        remainder = int(100 - advance_from_client)
        advance_int = int(advance_from_client)
        payment_terms = f"Аванс {advance_int}% в течение {time_to_advance} дней, остаток {remainder}% в течение {time_to_receiving} дней после отгрузки"
    else:
        payment_terms = f"Оплата 100% в течение {time_to_receiving} дней после отгрузки"

    delivery_time = variables.get("delivery_time", 60)
    price_includes = variables.get("price_includes", "НДС, страховку, таможенную очистку и доставку товара до склада")

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <style>
        @page {{
            size: A4;
            margin: 1.5cm 1.5cm 2cm 1.5cm;
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            font-family: 'DejaVu Sans', Arial, sans-serif;
            font-size: 9pt;
            line-height: 1.3;
            color: #333;
            margin: 0;
            padding: 0;
        }}

        /* Header with logo and contacts */
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #0066cc;
        }}

        .logo {{
            max-height: 50px;
        }}

        .contacts {{
            text-align: right;
            font-size: 9pt;
        }}

        .contacts .phone {{
            font-weight: bold;
            font-size: 11pt;
        }}

        /* Bank details section */
        .bank-section {{
            margin-bottom: 20px;
        }}

        .bank-section h3 {{
            font-size: 9pt;
            margin: 0 0 8px 0;
            font-weight: bold;
        }}

        .bank-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 8pt;
        }}

        .bank-table td {{
            border: 1px solid #333;
            padding: 4px 6px;
            vertical-align: top;
        }}

        .bank-label {{
            background: #f5f5f5;
            font-size: 7pt;
            color: #666;
        }}

        .bank-value {{
            font-weight: normal;
        }}

        .bank-right {{
            width: 30%;
        }}

        /* Invoice title */
        .invoice-title {{
            text-align: center;
            margin: 25px 0 15px 0;
        }}

        .invoice-title h1 {{
            font-size: 16pt;
            margin: 0;
            color: #000;
        }}

        .invoice-title .validity {{
            font-size: 9pt;
            color: #666;
            margin-top: 5px;
        }}

        /* Seller/Buyer info */
        .party-section {{
            margin-bottom: 15px;
        }}

        .party-section p {{
            margin: 3px 0;
            font-size: 9pt;
        }}

        .party-label {{
            font-weight: bold;
            color: #0066cc;
        }}

        .party-name {{
            font-weight: bold;
        }}

        /* Currency indicator */
        .currency-line {{
            text-align: right;
            margin-bottom: 8px;
            font-size: 9pt;
        }}

        /* Items table */
        .items-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 10px;
            font-size: 8pt;
        }}

        .items-table th {{
            background: #0066cc;
            color: white;
            padding: 6px 4px;
            text-align: center;
            font-weight: bold;
            font-size: 8pt;
            border: 1px solid #0066cc;
        }}

        .items-table td {{
            border: 1px solid #ccc;
            padding: 5px 4px;
            vertical-align: top;
        }}

        .col-num {{ width: 5%; text-align: center; }}
        .col-name {{ width: 40%; }}
        .col-qty {{ width: 8%; text-align: center; }}
        .col-unit {{ width: 7%; text-align: center; }}
        .col-price {{ width: 18%; text-align: right; white-space: nowrap; }}
        .col-total {{ width: 22%; text-align: right; white-space: nowrap; }}

        /* Totals section */
        .totals-section {{
            display: flex;
            justify-content: flex-end;
            margin-bottom: 15px;
        }}

        .totals-table {{
            width: 40%;
            font-size: 9pt;
        }}

        .totals-table tr td {{
            padding: 3px 8px;
        }}

        .totals-table .label {{
            text-align: right;
        }}

        .totals-table .value {{
            text-align: right;
            font-weight: normal;
            width: 45%;
            white-space: nowrap;
        }}

        .totals-table .total-row td {{
            font-weight: bold;
            font-size: 11pt;
            padding-top: 8px;
            border-top: 2px solid #333;
        }}

        /* Amount in words */
        .amount-words {{
            margin: 15px 0;
            padding: 8px 0;
            border-top: 1px solid #ccc;
            border-bottom: 1px solid #ccc;
        }}

        .amount-words .count {{
            font-weight: normal;
        }}

        .amount-words .words {{
            font-weight: bold;
        }}

        /* Terms section */
        .terms-section {{
            margin: 15px 0;
            padding: 10px;
            background: #f8f8f8;
            border-left: 3px solid #0066cc;
            font-size: 8pt;
        }}

        .terms-section p {{
            margin: 4px 0;
        }}

        .terms-label {{
            font-weight: bold;
        }}

        /* Signature */
        .signature-section {{
            margin-top: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .signature-position {{
            font-weight: bold;
        }}

        .signature-line {{
            width: 150px;
            border-bottom: 1px solid #333;
            margin: 0 15px;
        }}

        .signature-name {{
            font-weight: normal;
        }}
    </style>
</head>
<body>
    <!-- Header with contacts -->
    <div class="header">
        <div class="logo-area">
            <!-- Logo placeholder - would be embedded as base64 in production -->
        </div>
        <div class="contacts">
            <div class="phone">{seller_phone}</div>
            <div class="website">{seller_website}</div>
        </div>
    </div>

    <!-- Bank details section -->
    <div class="bank-section">
        <h3>Образец заполнения платежного поручения:</h3>
        <table class="bank-table">
            <tr>
                <td rowspan="2" style="width: 25%;">
                    <div class="bank-label">Банк получателя</div>
                    <div class="bank-value"><strong>{bank_name}</strong></div>
                </td>
                <td class="bank-right">
                    <div class="bank-label">БИК</div>
                    <div class="bank-value">{bank_bik}</div>
                </td>
            </tr>
            <tr>
                <td class="bank-right">
                    <div class="bank-label">Сч. №</div>
                    <div class="bank-value">{bank_corr}</div>
                </td>
            </tr>
            <tr>
                <td>
                    <div class="bank-label">Получатель</div>
                    <div class="bank-label">ИНН {seller_inn}    КПП {seller_kpp}</div>
                    <div class="bank-value"><strong>{seller_name}</strong></div>
                </td>
                <td class="bank-right">
                    <div class="bank-label">Сч. №</div>
                    <div class="bank-value">{bank_account}</div>
                </td>
            </tr>
        </table>
    </div>

    <!-- Invoice title -->
    <div class="invoice-title">
        <h1>Счет № {invoice_number} от {invoice_date}</h1>
        <div class="validity">Действителен до: {valid_until}</div>
    </div>

    <!-- Seller info -->
    <div class="party-section">
        <p><span class="party-label">Поставщик:</span></p>
        <p><span class="party-name">"{seller_name}"</span>, ИНН {seller_inn}, КПП {seller_kpp}, {seller_address}</p>
    </div>

    <!-- Buyer info -->
    <div class="party-section">
        <p><span class="party-label">Покупатель:</span></p>
        <p><span class="party-name">"{customer_name}"</span>{f", ИНН {customer_inn}" if customer_inn else ""}{f", {customer_address}" if customer_address else ""}{f", тел.: {customer_phone}" if customer_phone else ""}</p>
    </div>

    <!-- Currency indicator -->
    <div class="currency-line">
        Валюта: <strong>{currency}</strong>
    </div>

    <!-- Items table -->
    <table class="items-table">
        <thead>
            <tr>
                <th class="col-num">№</th>
                <th class="col-name">Наименование товара</th>
                <th class="col-qty">Кол-во</th>
                <th class="col-unit">Ед.изм</th>
                <th class="col-price">Цена, {currency_symbol}</th>
                <th class="col-total">Сумма, {currency_symbol}</th>
            </tr>
        </thead>
        <tbody>
            {product_rows}
        </tbody>
    </table>

    <!-- Totals -->
    <div class="totals-section">
        <table class="totals-table">
            <tr>
                <td class="label">Итого:</td>
                <td class="value">{format_number_russian(float(total_no_vat))}</td>
            </tr>
            <tr>
                <td class="label">НДС ({vat_rate}%):</td>
                <td class="value">{format_number_russian(float(vat_amount))}</td>
            </tr>
            <tr class="total-row">
                <td class="label">Итого с НДС:</td>
                <td class="value">{format_number_russian(float(total_with_vat))}</td>
            </tr>
        </table>
    </div>

    <!-- Amount in words -->
    <div class="amount-words">
        <span class="count">Всего наименований {len(items)}, на сумму:</span>
        <span class="words">{amount_words}</span>
    </div>

    <!-- Terms -->
    <div class="terms-section">
        <p><span class="terms-label">Условия оплаты:</span> {payment_terms}</p>
        <p><span class="terms-label">Срок поставки:</span> {delivery_time} календарных дней с даты зачисления аванса</p>
        <p><span class="terms-label">Цена включает:</span> {price_includes}</p>
    </div>

    <!-- Signature -->
    <div class="signature-section">
        <span class="signature-position">{director_position}</span>
        <span class="signature-line"></span>
        <span class="signature-name">{director_name}</span>
    </div>
</body>
</html>"""

    return html


def generate_invoice_pdf(data: ExportData, invoice_info: Dict[str, Any] = None) -> bytes:
    """
    Generate Invoice PDF document (Счет на оплату).

    Args:
        data: ExportData from export_data_mapper
        invoice_info: Optional invoice details

    Returns:
        PDF file as bytes
    """
    try:
        from weasyprint import HTML

        html = generate_invoice_html(data, invoice_info)
        pdf_bytes = HTML(string=html).write_pdf()
        return pdf_bytes
    except ImportError:
        raise ImportError("weasyprint is required for PDF generation. Install with: pip install weasyprint")
