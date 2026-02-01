"""
Export Data Mapper Service

Unified data fetcher for all export formats (Specification PDF, Invoice PDF, Validation Excel).
Fetches quote, items, calculation results, customer, and organization data.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Any, List, Optional
from datetime import datetime

from services.database import get_supabase


@dataclass
class ExportData:
    """Unified export data structure"""
    quote: Dict[str, Any]
    items: List[Dict[str, Any]]  # with calculation results merged
    customer: Dict[str, Any]
    organization: Dict[str, Any]
    variables: Dict[str, Any]
    calculations: Dict[str, Any]  # totals and summaries
    seller_company: Optional[Dict[str, Any]] = None  # Our legal entity for invoices
    bank_accounts: List[Dict[str, Any]] = None  # Bank accounts for seller_company
    selected_bank_account: Optional[Dict[str, Any]] = None  # Selected bank account for invoice


def fetch_export_data(quote_id: str, org_id: str) -> ExportData:
    """
    Fetch all data needed for exports.

    Args:
        quote_id: Quote UUID
        org_id: Organization UUID (for security - ensures RLS)

    Returns:
        ExportData with all necessary information
    """
    supabase = get_supabase()

    # 1. Fetch quote
    quote_result = supabase.table("quotes") \
        .select("*") \
        .eq("id", quote_id) \
        .eq("organization_id", org_id) \
        .execute()

    if not quote_result.data:
        raise ValueError(f"Quote not found: {quote_id}")

    quote = quote_result.data[0]

    # 2. Fetch customer
    customer_result = supabase.table("customers") \
        .select("*") \
        .eq("id", quote["customer_id"]) \
        .execute()

    customer = customer_result.data[0] if customer_result.data else {}

    # 3. Fetch organization
    org_result = supabase.table("organizations") \
        .select("*") \
        .eq("id", org_id) \
        .execute()

    organization = org_result.data[0] if org_result.data else {}

    # 4. Fetch quote items
    items_result = supabase.table("quote_items") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .order("position") \
        .execute()

    items = items_result.data or []

    # 5. Fetch calculation results for each item
    for item in items:
        calc_result = supabase.table("quote_calculation_results") \
            .select("phase_results") \
            .eq("quote_item_id", item["id"]) \
            .execute()

        if calc_result.data:
            item["calc"] = calc_result.data[0].get("phase_results", {})
        else:
            item["calc"] = {}

    # 6. Fetch calculation variables
    vars_result = supabase.table("quote_calculation_variables") \
        .select("variables") \
        .eq("quote_id", quote_id) \
        .execute()

    variables = {}
    if vars_result.data:
        variables = vars_result.data[0].get("variables", {})

    # 7. Fetch calculation summary
    summary_result = supabase.table("quote_calculation_summaries") \
        .select("*") \
        .eq("quote_id", quote_id) \
        .execute()

    calculations = {}
    if summary_result.data:
        calculations = summary_result.data[0]

    # Calculate totals from items if not in summary
    if not calculations:
        calculations = calculate_totals_from_items(items, quote.get("currency", "USD"))

    # 8. Fetch seller company (our legal entity) if quote has seller_company_id
    seller_company = None
    bank_accounts = []
    if quote.get("seller_company_id"):
        seller_result = supabase.table("seller_companies") \
            .select("*") \
            .eq("id", quote["seller_company_id"]) \
            .execute()
        if seller_result.data:
            seller_company = seller_result.data[0]

            # 9. Fetch bank accounts for seller company
            bank_result = supabase.table("bank_accounts") \
                .select("*") \
                .eq("entity_type", "seller_company") \
                .eq("entity_id", quote["seller_company_id"]) \
                .eq("is_active", True) \
                .order("is_default", desc=True) \
                .execute()
            bank_accounts = bank_result.data or []

    return ExportData(
        quote=quote,
        items=items,
        customer=customer,
        organization=organization,
        variables=variables,
        calculations=calculations,
        seller_company=seller_company,
        bank_accounts=bank_accounts,
        selected_bank_account=bank_accounts[0] if bank_accounts else None  # Default to first (is_default=true comes first)
    )


def fetch_export_data_with_bank(quote_id: str, org_id: str, bank_account_id: str = None) -> ExportData:
    """
    Fetch export data with specific bank account selected.

    Args:
        quote_id: Quote UUID
        org_id: Organization UUID
        bank_account_id: Optional bank account UUID to use (defaults to is_default=true)

    Returns:
        ExportData with selected_bank_account set
    """
    data = fetch_export_data(quote_id, org_id)

    # If specific bank account requested, find and set it
    if bank_account_id and data.bank_accounts:
        for bank in data.bank_accounts:
            if bank["id"] == bank_account_id:
                data.selected_bank_account = bank
                break

    return data


def get_bank_accounts_for_seller(seller_company_id: str) -> List[Dict[str, Any]]:
    """
    Get all active bank accounts for a seller company.

    Args:
        seller_company_id: Seller company UUID

    Returns:
        List of bank account dicts
    """
    supabase = get_supabase()

    result = supabase.table("bank_accounts") \
        .select("*") \
        .eq("entity_type", "seller_company") \
        .eq("entity_id", seller_company_id) \
        .eq("is_active", True) \
        .order("is_default", desc=True) \
        .order("currency") \
        .execute()

    return result.data or []


def calculate_totals_from_items(items: List[Dict], currency: str) -> Dict[str, Any]:
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

    # Convert to float for JSON serialization
    return {k: float(v) if isinstance(v, Decimal) else v for k, v in totals.items()}


def format_date_russian(dt: Optional[datetime] = None) -> str:
    """Format date in Russian style: DD.MM.YYYY"""
    if dt is None:
        dt = datetime.now()
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    return dt.strftime("%d.%m.%Y")


def amount_in_words_russian(amount: float, currency: str = "RUB") -> str:
    """
    Convert amount to Russian words (прописью).

    Example: 12345.67 -> "Двенадцать тысяч триста сорок пять рублей 67 копеек"
    """
    try:
        from num2words import num2words

        # Split integer and decimal parts
        rubles = int(amount)
        kopecks = int(round((amount - rubles) * 100))

        # Currency-specific suffixes
        currency_words = {
            "RUB": ("рубль", "рубля", "рублей", "копейка", "копейки", "копеек"),
            "USD": ("доллар", "доллара", "долларов", "цент", "цента", "центов"),
            "EUR": ("евро", "евро", "евро", "цент", "цента", "центов"),
        }

        words = currency_words.get(currency, currency_words["RUB"])

        # Convert rubles to words
        rubles_word = num2words(rubles, lang='ru')

        # Determine correct form for rubles
        last_digit = rubles % 10
        last_two = rubles % 100

        if last_two in (11, 12, 13, 14):
            ruble_form = words[2]  # рублей
        elif last_digit == 1:
            ruble_form = words[0]  # рубль
        elif last_digit in (2, 3, 4):
            ruble_form = words[1]  # рубля
        else:
            ruble_form = words[2]  # рублей

        # Determine correct form for kopecks
        last_digit = kopecks % 10
        last_two = kopecks % 100

        if last_two in (11, 12, 13, 14):
            kopeck_form = words[5]  # копеек
        elif last_digit == 1:
            kopeck_form = words[3]  # копейка
        elif last_digit in (2, 3, 4):
            kopeck_form = words[4]  # копейки
        else:
            kopeck_form = words[5]  # копеек

        # Capitalize first letter
        rubles_word = rubles_word.capitalize()

        return f"{rubles_word} {ruble_form} {kopecks:02d} {kopeck_form}"

    except ImportError:
        return f"{amount:,.2f} {currency}"


def format_number_russian(value: float) -> str:
    """
    Format number with Russian decimal separator: 1 234,56

    Uses space as thousands separator and comma as decimal separator.

    Args:
        value: Number to format (handles None)

    Returns:
        Formatted string like "1 234,56"
    """
    if value is None:
        return "0,00"
    formatted = f"{value:,.2f}"
    # Replace comma with space (thousands) and period with comma (decimals)
    formatted = formatted.replace(",", " ").replace(".", ",")
    return formatted


def get_currency_symbol(currency: str) -> str:
    """
    Get currency symbol for display.

    Args:
        currency: ISO currency code (RUB, USD, EUR, CNY, TRY)

    Returns:
        Currency symbol or the code itself if not in mapping
    """
    return {
        "RUB": "₽",
        "USD": "$",
        "EUR": "€",
        "CNY": "¥",
        "TRY": "₺",
    }.get(currency, currency)


def qty_in_words(qty: int) -> str:
    """
    Convert quantity to Russian words.

    Args:
        qty: Integer quantity

    Returns:
        Number in Russian words (e.g., "пятнадцать")
    """
    try:
        from num2words import num2words
        return num2words(qty, lang='ru')
    except ImportError:
        return str(qty)
