"""APIRouter modules mounted under /api via api/app.py.

Each submodule owns a single `router` APIRouter instance grouping related
endpoints by business domain. Routers do NOT include the /api/ prefix in
their path decorators — the mount in main.py provides it.
"""

from api.routers import (  # re-export
    admin,
    chat,
    cost_analysis,
    cron,
    customs,
    deals,
    documents,
    feedback,
    geo,
    integrations,
    invoices,
    plan_fact,
    public,
    quotes,
)

__all__ = [
    "admin",
    "chat",
    "cost_analysis",
    "cron",
    "customs",
    "deals",
    "documents",
    "feedback",
    "geo",
    "integrations",
    "invoices",
    "plan_fact",
    "public",
    "quotes",
]
