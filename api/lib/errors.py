"""Canonical structured response envelopes.

Single source of truth for the API envelope shape mandated by
``.kiro/steering/api-first.md``. Replaces the per-file ``_err``/``_ok``
helpers that previously duplicated this logic across the API layer.
"""

from typing import Any

from fastapi.responses import JSONResponse


def error_response(
    code: str,
    message: str,
    status_code: int = 400,
) -> JSONResponse:
    """Canonical structured error envelope per .kiro/steering/api-first.md."""
    return JSONResponse(
        {"success": False, "error": {"code": code, "message": message}},
        status_code=status_code,
    )


def success_response(
    data: Any = None,
    meta: dict[str, Any] | None = None,
    status_code: int = 200,
) -> JSONResponse:
    """Canonical structured success envelope per .kiro/steering/api-first.md."""
    payload: dict[str, Any] = {"success": True}
    if data is not None:
        payload["data"] = data
    if meta is not None:
        payload["meta"] = meta
    return JSONResponse(payload, status_code=status_code)
