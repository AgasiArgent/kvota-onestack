"""APIRouter modules mounted under /api via api/app.py.

Each submodule owns a single `router` APIRouter instance grouping related
endpoints by business domain. Routers do NOT include the /api/ prefix in
their path decorators — the mount in main.py provides it.
"""

from api.routers import admin, deals, plan_fact, public, quotes  # re-export

__all__ = ["admin", "deals", "plan_fact", "public", "quotes"]
