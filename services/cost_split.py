"""Pure proportional cost-split helper for shared customs certificates.

Phase B (customs-shared-certificates) — REQ-3.

Distributes a certificate's cost (`cert_cost`, RUB) across attached
quote-positions in proportion to each position's RUB cost basis.
The RUB cost basis is supplied by the caller (already computed via
``services.calculation_helpers._customs_value_in_rub`` — re-exported
here for symmetric API per LD-15 of the design doc).

Sister TypeScript implementation lives in
``frontend/src/shared/lib/cost-split.ts``. Both modules consume the
same JSON fixtures (``tests/fixtures/cost_split_fixtures.json``) and
must produce kopek-identical output.

This module is intentionally free of any I/O, HTTP, ORM or DB
concerns. It contains only ``Decimal`` arithmetic.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import List, Sequence

# Re-export the calc-engine source-of-truth helper for callers that need
# to derive the RUB cost basis on the backend (LD-15). The helper itself
# lives in services/calculation_helpers.py and is NOT modified by Phase B.
from services.calculation_helpers import (  # noqa: F401  (re-export)
    _customs_value_in_rub as customs_value_rub_for_item,
)

_QUANT = Decimal("0.01")


def split_cost(
    item_value: Decimal,
    total_items_value: Decimal,
    cert_cost: Decimal,
) -> Decimal:
    """Proportional share for a single item, quantized to kopeks.

    Args:
        item_value:        RUB cost basis of THIS item (already in RUB).
        total_items_value: sum of RUB cost basis of ALL attached items.
        cert_cost:         total cost of the certificate (RUB).

    Returns:
        Decimal share for this item, quantized to 0.01 with ROUND_HALF_UP.

    Edge cases:
        - ``total_items_value == 0`` returns Decimal("0.00") because a
          per-item formula has no meaning when the basis sums to zero.
          Callers needing the equal-split fallback must use
          :func:`split_cost_batch` (REQ-3 AC#5 — fallback is a batch
          property, not a single-share property).
        - ``cert_cost == 0`` returns Decimal("0.00").
    """
    if total_items_value == 0:
        return Decimal("0.00")
    share = (item_value / total_items_value) * cert_cost
    return share.quantize(_QUANT, rounding=ROUND_HALF_UP)


def split_cost_batch(
    item_values: Sequence[Decimal],
    cert_cost: Decimal,
) -> List[Decimal]:
    """Compute kopek-exact shares for all items.

    Args:
        item_values: ordered (typically by ``created_at`` ASC) RUB cost
            basis per item.
        cert_cost:   total cert cost (RUB).

    Returns:
        list[Decimal] of length ``len(item_values)``, each quantized to
        0.01; ``sum(result) == cert_cost`` exactly (REQ-3 AC#7 —
        last item absorbs the rounding residual).

    Edge cases (REQ-3 AC#5/AC#6):
        - empty list                   → ``[]``
        - single item                  → ``[cert_cost]`` (no rounding)
        - all-zero basis (sum == 0)    → equal split ``cert_cost / N``;
                                         last item absorbs residual.
        - normal proportional          → first ``N-1`` shares computed
                                         via ``split_cost``; last share
                                         = ``cert_cost - sum(others)``
                                         to ensure exact sum.
    """
    n = len(item_values)
    if n == 0:
        return []
    if n == 1:
        return [cert_cost]

    total = sum(item_values, Decimal("0"))

    if total == 0:
        # Equal-split fallback — divide cert_cost by N, last absorbs residual.
        equal = (cert_cost / Decimal(n)).quantize(_QUANT, rounding=ROUND_HALF_UP)
        shares = [equal] * (n - 1)
        last = cert_cost - sum(shares, Decimal("0"))
        shares.append(last)
        return shares

    # Normal proportional path.
    shares = [
        split_cost(item_values[i], total, cert_cost) for i in range(n - 1)
    ]
    last = cert_cost - sum(shares, Decimal("0"))
    shares.append(last)
    return shares


__all__ = [
    "split_cost",
    "split_cost_batch",
    "customs_value_rub_for_item",
]
