"""Shared JSON response envelope for /api/* endpoints.

Every OneStack API endpoint returns a uniform envelope per Req 16.4 (Customer
Journey Map spec) and `.kiro/steering/api-first.md`:

    Success: {"success": true, "data": ...}
    Error:   {"success": false, "error": {"code": "...", "message": "..."}}

This module centralises envelope construction so no router re-implements the
shape (or drifts from it). The legacy /api/* handlers (public, feedback, ...)
build the dict inline; new code should import from here.

Helpers intentionally return ``JSONResponse`` so Starlette/FastAPI status codes
can be set without wrapping Pydantic models on the way out.
"""

from __future__ import annotations

from typing import Any

from starlette.responses import JSONResponse

__all__ = [
    "success_response",
    "error_response",
    "success_envelope",
    "error_envelope",
]


def success_envelope(data: Any) -> dict[str, Any]:
    """Build the plain-dict success envelope.

    Path: n/a (pure function)
    Params:
        data: payload to wrap (any JSON-serialisable value)
    Returns:
        dict with ``success=True`` and ``data`` keys.
    Side Effects: none.
    Roles: n/a.
    """
    return {"success": True, "data": data}


def error_envelope(code: str, message: str) -> dict[str, Any]:
    """Build the plain-dict error envelope.

    Path: n/a (pure function)
    Params:
        code: UPPER_SNAKE_CASE machine-readable identifier (e.g. "STALE_VERSION")
        message: human-readable description (Russian UI copy lives in frontend;
                 message here is for logs / fallback display)
    Returns:
        dict with ``success=False`` and ``error={code, message}`` keys.
    Side Effects: none.
    Roles: n/a.
    """
    return {"success": False, "error": {"code": code, "message": message}}


def success_response(data: Any, *, status_code: int = 200) -> JSONResponse:
    """Wrap ``data`` in the success envelope and return a JSONResponse.

    Path: n/a (pure function)
    Params:
        data: payload (any JSON-serialisable value)
        status_code: HTTP status (default 200; use 201 for creates, 204 n/a
                     since 204 bodies are discarded)
    Returns:
        JSONResponse with ``{"success": true, "data": ...}`` body.
    Side Effects: none.
    Roles: n/a.
    """
    return JSONResponse(success_envelope(data), status_code=status_code)


def error_response(
    code: str,
    message: str,
    *,
    status_code: int = 400,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    """Wrap a failure in the error envelope and return a JSONResponse.

    Path: n/a (pure function)
    Params:
        code: UPPER_SNAKE_CASE identifier (``"VALIDATION_ERROR"``, ``"NOT_FOUND"``,
              ``"STALE_VERSION"``, ...)
        message: human-readable description.
        status_code: HTTP status (default 400).
        extra: optional extra top-level keys to merge into the envelope (e.g.
               the journey PATCH endpoint ships current server state under
               ``data`` alongside ``success=false``). Keys in ``extra``
               override envelope keys only if explicitly namespaced.
    Returns:
        JSONResponse with ``{"success": false, "error": {code, message}, ...extra}``.
    Side Effects: none.
    Roles: n/a.
    """
    payload = error_envelope(code, message)
    if extra:
        payload.update(extra)
    return JSONResponse(payload, status_code=status_code)
