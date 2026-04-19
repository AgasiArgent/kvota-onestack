"""
Export Data Mapper Service

Unified data fetcher for all export formats (Specification PDF, Invoice PDF, Validation Excel).
Fetches quote, items, calculation results, customer, and organization data.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Any, List, Optional
from datetime import datetime

import logging

from services import composition_service
from services.database import get_supabase
from services.dadata_service import validate_inn, _call_dadata_api, normalize_dadata_result

logger = logging.getLogger(__name__)


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


def _lookup_legal_name(inn: str, cache: Dict[str, str]) -> Optional[str]:
    """
    Look up official legal name by INN via DaData (sync).

    Returns full_with_opf name or None on any failure.
    Results are cached by INN within the export session.
    """
    if not inn or not validate_inn(inn):
        return None

    inn = str(inn).strip()
    if inn in cache:
        return cache[inn]

    try:
        response_data = _call_dadata_api(inn)
        suggestions = response_data.get("suggestions", [])
        if not suggestions:
            cache[inn] = None
            return None
        result = normalize_dadata_result(suggestions[0])
        legal_name = result.get("full_name")
        cache[inn] = legal_name
        return legal_name
    except Exception:
        logger.warning("DaData lookup failed for INN %s", inn, exc_info=True)
        cache[inn] = None
        return None


def enrich_with_legal_names(
    *entities: Optional[Dict[str, Any]],
    inn_key: str = "inn",
) -> None:
    """
    Enrich company dicts with DaData legal name (in-place).

    For each entity that has an INN, looks up the official legal name
    and stores it as 'legal_name'. Uses a shared cache so the same INN
    is never looked up twice.

    Args:
        *entities: Company dicts to enrich (seller_company, customer, organization, etc.)
        inn_key: Key name for the INN field in the dict
    """
    cache: Dict[str, str] = {}
    for entity in entities:
        if entity is None:
            continue
        inn = entity.get(inn_key)
        if inn:
            legal_name = _lookup_legal_name(inn, cache)
            if legal_name:
                entity["legal_name"] = legal_name


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

    # 4. Fetch composed items (Phase 5d Pattern A).
    # Source supplier-side fields (weight_in_kg, base_price_vat,
    # purchase_price_original, purchase_currency, customs_code,
    # supplier_country, ...) from the selected invoice_items row via
    # composition_service.get_composed_items rather than reading the
    # legacy quote_items columns directly. See
    # .kiro/specs/phase-5d-legacy-refactor/design.md §2.1.7 and REQ-1.6.
    items = composition_service.get_composed_items(quote_id, supabase)

    # 4b. Enrich composed items with customer-facing display fields
    # (product_code, unit, description) that the composed shape does not
    # carry. Customer-facing exports (specification PDF, invoice PDF)
    # render these fields for the customer — they are NOT supplier-side
    # and therefore do not belong in the calc-ready composition shape.
    # One extra read keyed by quote_item_id; soft-deleted rows excluded.
    qi_ids = [item["quote_item_id"] for item in items if item.get("quote_item_id")]
    if qi_ids:
        qi_result = supabase.table("quote_items") \
            .select("id, product_code, unit, description, position") \
            .in_("id", qi_ids) \
            .execute()
        by_qi = {row["id"]: row for row in (qi_result.data or [])}
        for item in items:
            qi = by_qi.get(item.get("quote_item_id"))
            if qi:
                # Don't clobber composed fields — only add customer-side
                # fields that are absent from the composed shape.
                for key in ("product_code", "unit", "description", "position"):
                    item.setdefault(key, qi.get(key))

    # 5. Merge per-item calculation results, keyed by the composed item's
    #    quote_item_id traceability field.
    for item in items:
        qi_id = item.get("quote_item_id")
        if not qi_id:
            item["calc"] = {}
            continue
        calc_result = supabase.table("quote_calculation_results") \
            .select("phase_results") \
            .eq("quote_item_id", qi_id) \
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

    # 10. Enrich company names with DaData legal names
    enrich_with_legal_names(seller_company, customer, organization)

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


def format_date_russian_long(dt: Optional[datetime] = None) -> str:
    """
    Format date in long Russian style: «01» февраля 2026 г.

    Used for contract specification documents.
    """
    if dt is None:
        dt = datetime.now()
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            # Try parsing as date only
            from datetime import date
            dt = datetime.strptime(dt[:10], "%Y-%m-%d")

    # Russian month names in genitive case (родительный падеж)
    months_genitive = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля",
        5: "мая", 6: "июня", 7: "июля", 8: "августа",
        9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
    }

    day = dt.day
    month = months_genitive[dt.month]
    year = dt.year

    return f"«{day:02d}» {month} {year} г."


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

        # Currency-specific suffixes: (sing, few, plural, cent_sing, cent_few, cent_plural, feminine)
        currency_words = {
            "RUB": ("рубль", "рубля", "рублей", "копейка", "копейки", "копеек", False),
            "USD": ("доллар США", "доллара США", "долларов США", "цент", "цента", "центов", False),
            "EUR": ("евро", "евро", "евро", "евроцент", "евроцента", "евроцентов", False),
            "CNY": ("юань", "юаня", "юаней", "фэнь", "фэня", "фэней", False),
            "TRY": ("турецкая лира", "турецкие лиры", "турецких лир", "куруш", "куруша", "курушей", True),
        }

        words = currency_words.get(currency, currency_words["RUB"])
        is_feminine = words[6]

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

        # Convert to feminine form if needed (e.g., "один" → "одна" for лира)
        if is_feminine:
            rubles_word = rubles_word.replace("один ", "одна ").replace("два ", "две ")
            if rubles_word.endswith("один"):
                rubles_word = rubles_word[:-4] + "одна"
            elif rubles_word.endswith("два"):
                rubles_word = rubles_word[:-3] + "две"

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
