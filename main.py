"""OneStack — FastHTML shell retired in Phase 6C-3 (2026-04-21).

The application now runs as a pure FastAPI service:

    Docker CMD: ``uvicorn api.app:api_app --host 0.0.0.0 --port 5001``

This stub re-exports the app for backward compatibility with tests and
tooling that still do ``from main import app``. New code should import
directly from ``api.app``.

Shared helpers previously living in this file have moved:
- ``build_calculation_inputs`` + country/VAT helpers → ``services/calculation_helpers.py``
- ``btn`` + ``icon`` (legacy FastHTML HTMX response fragments) → ``api/ui_helpers.py``

Archived routes live in ``legacy-fasthtml/`` and are never imported at runtime.
"""

from api.app import api_app as app

__all__ = ["app"]
