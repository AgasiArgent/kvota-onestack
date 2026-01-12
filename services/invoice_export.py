"""
Invoice PDF Export Service

Generates Russian commercial invoice (Счет на оплату).
Uses HTML → weasyprint → PDF rendering.
"""

from decimal import Decimal
from typing import Dict, Any
from datetime import datetime

from services.export_data_mapper import ExportData, format_date_russian, amount_in_words_russian


def generate_invoice_html(data: ExportData, invoice_info: Dict[str, Any] = None) -> str:
    """
    Generate HTML for Russian commercial invoice (Счет).

    Args:
        data: ExportData from export_data_mapper
        invoice_info: Optional invoice details (number, date, etc.)

    Returns:
        HTML string ready for PDF rendering
    """
    invoice_info = invoice_info or {}

    quote = data.quote
    customer = data.customer
    organization = data.organization
    items = data.items
    calculations = data.calculations

    # Default values
    invoice_number = invoice_info.get("invoice_number", quote.get("quote_number", "б/н"))
    invoice_date = invoice_info.get("invoice_date", format_date_russian())

    currency = quote.get("currency", "RUB")
    currency_symbol = {"RUB": "₽", "USD": "$", "EUR": "€", "CNY": "¥"}.get(currency, currency)

    # Calculate totals
    total_with_vat = calculations.get("total_with_vat", 0)
    total_no_vat = calculations.get("total_no_vat", 0)
    vat_amount = total_with_vat - total_no_vat

    # Build product rows
    product_rows = ""
    for i, item in enumerate(items, 1):
        calc = item.get("calc", {})
        qty = item.get("quantity", 1)
        price_per_unit = calc.get("AJ16", 0)  # Sales price per unit (no VAT)
        item_total_no_vat = calc.get("AK16", 0)  # Total no VAT
        item_total_with_vat = calc.get("AL16", 0)  # Total with VAT

        product_rows += f"""
        <tr>
            <td style="text-align: center;">{i}</td>
            <td>{item.get('product_name', '')}</td>
            <td style="text-align: center;">{item.get('unit', 'шт')}</td>
            <td style="text-align: center;">{qty}</td>
            <td style="text-align: right;">{currency_symbol}{price_per_unit:,.2f}</td>
            <td style="text-align: right;">{currency_symbol}{item_total_no_vat:,.2f}</td>
        </tr>
        """

    # Amount in words
    amount_words = amount_in_words_russian(float(total_with_vat), currency)

    # Bank details
    bank_name = organization.get('bank_name', 'Наименование банка')
    bank_bik = organization.get('bik', '-')
    bank_account = organization.get('payment_account', '-')
    bank_corr = organization.get('correspondent_account', '-')

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
                line-height: 1.3;
                color: #333;
            }}
            .bank-section {{
                border: 1px solid #333;
                margin-bottom: 0.5cm;
            }}
            .bank-row {{
                display: flex;
                border-bottom: 1px solid #333;
            }}
            .bank-row:last-child {{
                border-bottom: none;
            }}
            .bank-label {{
                width: 3cm;
                padding: 0.2cm;
                border-right: 1px solid #333;
                font-size: 8pt;
            }}
            .bank-value {{
                padding: 0.2cm;
                flex: 1;
            }}
            .bank-right {{
                width: 4cm;
                border-left: 1px solid #333;
            }}
            h1 {{
                text-align: center;
                font-size: 14pt;
                margin: 0.5cm 0;
            }}
            .seller-buyer {{
                margin: 0.5cm 0;
            }}
            .seller-buyer p {{
                margin: 0.2cm 0;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 0.5cm 0;
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
            .total-section {{
                text-align: right;
                margin: 0.5cm 0;
            }}
            .total-section p {{
                margin: 0.1cm 0;
            }}
            .amount-words {{
                margin: 0.5cm 0;
                font-weight: bold;
            }}
            .footer-note {{
                margin-top: 0.5cm;
                font-size: 8pt;
            }}
            .signatures {{
                margin-top: 1cm;
                display: flex;
                gap: 2cm;
            }}
            .signature-block {{
                flex: 1;
            }}
            .signature-line {{
                border-bottom: 1px solid #333;
                margin-top: 0.8cm;
                padding-bottom: 0.1cm;
            }}
        </style>
    </head>
    <body>
        <!-- Bank details header -->
        <div class="bank-section">
            <div class="bank-row">
                <div class="bank-label">Банк получателя</div>
                <div class="bank-value">{bank_name}</div>
                <div class="bank-right">
                    <div style="border-bottom: 1px solid #333; padding: 0.2cm;">БИК {bank_bik}</div>
                    <div style="padding: 0.2cm;">К/с {bank_corr}</div>
                </div>
            </div>
            <div class="bank-row">
                <div class="bank-label">ИНН {organization.get('inn', '-')}</div>
                <div class="bank-value" style="border-right: 1px solid #333;">КПП {organization.get('kpp', '-')}</div>
                <div class="bank-value">Сч. № {bank_account}</div>
            </div>
            <div class="bank-row">
                <div class="bank-label">Получатель</div>
                <div class="bank-value" colspan="2">{organization.get('name', 'Организация')}</div>
            </div>
        </div>

        <!-- Invoice title -->
        <h1>Счёт на оплату № {invoice_number} от {invoice_date}</h1>

        <!-- Seller and Buyer -->
        <div class="seller-buyer">
            <p><strong>Поставщик:</strong> {organization.get('name', 'Организация')},
               ИНН {organization.get('inn', '-')}, КПП {organization.get('kpp', '-')},
               {organization.get('legal_address', '')}</p>
            <p><strong>Покупатель:</strong> {customer.get('company_name', customer.get('name', 'Покупатель'))},
               ИНН {customer.get('inn', '-')},
               {customer.get('address', '')}</p>
        </div>

        <!-- Products table -->
        <table>
            <thead>
                <tr>
                    <th style="width: 5%;">№</th>
                    <th style="width: 45%;">Товар (работы, услуги)</th>
                    <th style="width: 10%;">Ед.</th>
                    <th style="width: 10%;">Кол-во</th>
                    <th style="width: 15%;">Цена</th>
                    <th style="width: 15%;">Сумма</th>
                </tr>
            </thead>
            <tbody>
                {product_rows}
            </tbody>
        </table>

        <!-- Totals -->
        <div class="total-section">
            <p>Итого: {currency_symbol}{total_no_vat:,.2f}</p>
            <p>В том числе НДС (20%): {currency_symbol}{vat_amount:,.2f}</p>
            <p><strong>Всего к оплате: {currency_symbol}{total_with_vat:,.2f}</strong></p>
        </div>

        <div class="amount-words">
            Всего наименований {len(items)}, на сумму {amount_words}
        </div>

        <div class="footer-note">
            <p>Счёт действителен в течение {invoice_info.get('valid_days', 5)} банковских дней.</p>
            <p>Оплата данного счёта означает согласие с условиями поставки товара.</p>
        </div>

        <!-- Signatures -->
        <div class="signatures">
            <div class="signature-block">
                <strong>Руководитель</strong>
                <div class="signature-line">
                    _________________ / {organization.get('director_name', '_____________')} /
                </div>
            </div>
            <div class="signature-block">
                <strong>Гл. бухгалтер</strong>
                <div class="signature-line">
                    _________________ / {organization.get('accountant_name', '_____________')} /
                </div>
            </div>
        </div>
    </body>
    </html>
    """

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
