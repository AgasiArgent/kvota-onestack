"""
Specification PDF Export Service

Generates Russian contract specification documents (Спецификация).
Uses HTML → weasyprint → PDF rendering.
"""

from decimal import Decimal
from typing import Dict, Any
from datetime import datetime

from services.export_data_mapper import ExportData, format_date_russian, amount_in_words_russian


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
