"""
UI Components for Price Offers (JSONB Version)

FastHTML/HTMX components - identical UI to separate table version.
Only difference: routes pass quote_item_id to all operations.
"""

from fasthtml.common import *
from decimal import Decimal
from typing import List

# from services.price_offer_service import PriceOffer


def _render_offers_list(
    item_id: str,
    offers: List,  # List[PriceOffer]
    suppliers: List,  # List[Supplier]
) -> Div:
    """
    Render price offers list for a quote item.
    JSONB version - all routes include item_id.

    Args:
        item_id: Quote item UUID
        offers: List of PriceOffer objects
        suppliers: Available suppliers for dropdown
    """

    def format_price(offer) -> str:
        return f"{offer.currency} {offer.price:,.2f}"

    # Offers table rows
    offer_rows = []
    for offer in offers:
        is_selected = offer.is_selected

        offer_rows.append(
            Tr(
                # Radio for selection
                Td(
                    Input(
                        type="radio",
                        name=f"selected_offer_{item_id}",
                        checked=is_selected,
                        # JSONB version: include item_id in route
                        hx_post=f"/quote-items/{item_id}/offers/{offer.id}/select",
                        hx_target=f"#offers-container-{item_id}",
                        hx_swap="outerHTML",
                        cls="form-radio"
                    ),
                    cls="text-center"
                ),
                # Supplier (from denormalized field)
                Td(
                    offer.supplier_name,
                    cls="font-medium" if is_selected else ""
                ),
                # Price
                Td(
                    format_price(offer),
                    cls="text-right font-mono " + (
                        "font-bold text-green-600" if is_selected else ""
                    )
                ),
                # Production days
                Td(
                    f"{offer.production_days} дн." if offer.production_days else "—",
                    cls="text-center"
                ),
                # Delete button
                Td(
                    Button(
                        "✕",
                        # JSONB version: include item_id in route
                        hx_delete=f"/quote-items/{item_id}/offers/{offer.id}",
                        hx_target=f"#offers-container-{item_id}",
                        hx_swap="outerHTML",
                        hx_confirm="Удалить это предложение?",
                        cls="btn btn-xs btn-ghost text-red-500"
                    ),
                    cls="text-center"
                ),
                cls="hover:bg-gray-50" + (" bg-green-50" if is_selected else "")
            )
        )

    # Empty state
    if not offers:
        offer_rows.append(
            Tr(
                Td(
                    "Нет предложений",
                    colspan=5,
                    cls="text-center text-gray-500 py-4"
                )
            )
        )

    # Offers table
    offers_table = Table(
        Thead(
            Tr(
                Th("", cls="w-10"),
                Th("Поставщик"),
                Th("Цена", cls="text-right"),
                Th("Срок", cls="text-center"),
                Th("", cls="w-10"),
            ),
            cls="bg-gray-100"
        ),
        Tbody(*offer_rows),
        cls="table table-compact w-full"
    )

    # Add form
    add_form = Form(
        Div(
            Select(
                Option("Выберите поставщика...", value="", disabled=True, selected=True),
                *[Option(s.name, value=str(s.id), data_name=s.name) for s in suppliers],
                name="supplier_id",
                required=True,
                cls="select select-bordered select-sm flex-1",
                # Store supplier name for denormalization
                onchange="this.form.supplier_name.value = this.selectedOptions[0].dataset.name"
            ),
            # Hidden field for supplier name (denormalized in JSONB)
            Input(type="hidden", name="supplier_name", value=""),
            Input(
                type="number",
                name="price",
                step="0.01",
                min="0",
                required=True,
                placeholder="Цена",
                cls="input input-bordered input-sm w-24"
            ),
            Select(
                Option("USD", value="USD"),
                Option("EUR", value="EUR"),
                Option("RUB", value="RUB"),
                Option("CNY", value="CNY"),
                name="currency",
                cls="select select-bordered select-sm w-20"
            ),
            Input(
                type="number",
                name="production_days",
                min="0",
                placeholder="Дни",
                cls="input input-bordered input-sm w-16"
            ),
            Button(
                "+",
                type="submit",
                cls="btn btn-primary btn-sm"
            ),
            cls="flex gap-2 items-center"
        ),
        hx_post=f"/quote-items/{item_id}/offers",
        hx_target=f"#offers-container-{item_id}",
        hx_swap="outerHTML",
        cls="mt-2 pt-2 border-t border-dashed"
    )

    # Header with status
    selected = next((o for o in offers if o.is_selected), None)

    header = Div(
        Span(f"Предложения ({len(offers)}/5)", cls="font-medium text-sm"),
        Span(
            f"✓ {selected.supplier_name}: {format_price(selected)}" if selected else "⚠ Не выбрано",
            cls="text-xs " + ("text-green-600" if selected else "text-orange-500")
        ),
        cls="flex justify-between items-center mb-2"
    )

    return Div(
        header,
        offers_table,
        add_form if len(offers) < 5 else Div("Максимум 5 предложений", cls="text-xs text-gray-400 mt-2"),
        id=f"offers-container-{item_id}",
        cls="border rounded-lg p-3 bg-white"
    )
