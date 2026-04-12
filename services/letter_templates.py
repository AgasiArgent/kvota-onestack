"""
Letter Templates Service

Pre-built letter templates for sending invoices to suppliers.
Supports Russian (primary) and English (placeholder for Phase 4b).

Uses str.format_map() with a defaultdict for graceful handling of missing
placeholders — missing keys render as empty strings instead of raising.
"""

from collections import defaultdict


# ============================================================================
# Subject Templates
# ============================================================================

SUBJECT_TEMPLATE_RU: str = "Запрос коммерческого предложения: {skus}"

SUBJECT_TEMPLATE_EN: str = "Request for quotation: {skus}"


# ============================================================================
# Letter Body Templates
# ============================================================================

LETTER_TEMPLATE_RU: str = """\
Уважаемый {greeting},

Прошу рассмотреть возможность поставки следующих позиций:

{items_list}

Условия поставки: {incoterms}
Страна назначения: {delivery_country}
Валюта: {currency}

Подробная спецификация во вложении.
Пожалуйста, предоставьте ваши цены и сроки поставки.

С уважением,
{sender_name}
{sender_email}
{sender_phone}"""

LETTER_TEMPLATE_EN: str = """\
Dear {greeting},

We would like to request pricing for the following items:

{items_list}

Delivery terms: {incoterms}
Destination country: {delivery_country}
Currency: {currency}

Detailed specification is attached.
Please provide your prices and lead times.

Best regards,
{sender_name}
{sender_email}
{sender_phone}"""


# ============================================================================
# Template Registry
# ============================================================================

_TEMPLATES = {
    "ru": (SUBJECT_TEMPLATE_RU, LETTER_TEMPLATE_RU),
    "en": (SUBJECT_TEMPLATE_EN, LETTER_TEMPLATE_EN),
}


# ============================================================================
# Public API
# ============================================================================

def render_letter(template_lang: str, context: dict) -> tuple[str, str]:
    """Render a letter template with the given context.

    Args:
        template_lang: Language code ('ru' or 'en'). Falls back to 'ru' for unknown.
        context: Dict with placeholder values. Keys: greeting, items_list,
                 delivery_country, incoterms, currency, sender_name,
                 sender_email, sender_phone, skus.

    Returns:
        Tuple of (subject, body_text) with all placeholders substituted.
        Missing keys render as empty strings (no KeyError).
    """
    subject_template, body_template = _TEMPLATES.get(template_lang, _TEMPLATES["ru"])

    # defaultdict returns "" for any missing key — graceful degradation
    safe_context = defaultdict(str, context)

    subject = subject_template.format_map(safe_context)
    body = body_template.format_map(safe_context)

    return subject, body
