"""Legacy FastHTML /api/cities/search — archived 2026-04-20 during Phase 6C-1.

This HTMX endpoint is broken post-migration-284 (Phase 5d exempt list).
Preserved for historical reference; NOT imported by main.py or api/app.py.
The equivalent live endpoint is `GET /api/geo/cities/search` on the FastAPI
sub-app (see api/geo.py and api/routers/geo.py).

To restore this route temporarily, copy the handler back to main.py and
re-apply the @rt decorator. Not recommended — use /api/geo/cities/search.
"""
# flake8: noqa
# type: ignore

from fasthtml.common import Group, Option


# @rt("/api/cities/search")  — decorator removed, file is archived and not mounted
def get(session, q: str = "", pickup_city: str = "", limit: int = 5):
    """City autocomplete using HERE Geocode API.
    Returns datalist options with city names and country codes."""
    from services.here_service import search_cities
    search_term = q or pickup_city
    if not search_term or len(search_term) < 2:
        return ""
    cities = search_cities(search_term, count=limit)
    if not cities:
        return Option("Ничего не найдено", value="", disabled=True)
    options = []
    for c in cities:
        # value = display text, data attributes for JS to extract
        options.append(Option(
            c["display"],
            value=c["display"],
            **{"data-city": c["city"], "data-country-code": c["country_code"]}
        ))
    return Group(*options)
