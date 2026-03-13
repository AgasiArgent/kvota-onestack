"""JWT validation middleware for /api/* endpoints called by the Next.js frontend.

All /api/* routes (except /api/health) require a valid Supabase JWT.
This is enforced as Starlette middleware, not a per-handler decorator,
so new API endpoints are protected by default.
"""

import asyncio
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from supabase_auth import SyncGoTrueClient

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

# Paths under /api/ that don't require auth
# Paths that handle their own auth (dual-auth: JWT or session)
DUAL_AUTH_PATHS = {"/api/feedback"}
PUBLIC_API_PATHS = {"/api/health"}

# Module-level singleton — reused across requests
_gotrue_client: SyncGoTrueClient | None = None


def _get_gotrue_client() -> SyncGoTrueClient:
    global _gotrue_client
    if _gotrue_client is None:
        _gotrue_client = SyncGoTrueClient(
            url=f"{SUPABASE_URL}/auth/v1",
            headers={"apikey": SUPABASE_ANON_KEY},
        )
    return _gotrue_client


def get_user_from_token(auth_header: str):
    """Extract and validate Supabase JWT from Authorization header value."""
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]
    try:
        client = _get_gotrue_client()
        user = client.get_user(token)
        return user.user if user else None
    except Exception:
        return None


class ApiAuthMiddleware(BaseHTTPMiddleware):
    """Reject unauthenticated requests to /api/* (except public paths)."""

    async def dispatch(self, request, call_next):
        path = request.url.path

        # Only apply to /api/* routes
        if not path.startswith("/api/"):
            return await call_next(request)

        # Skip public endpoints
        if path in PUBLIC_API_PATHS:
            return await call_next(request)

        # Validate JWT (run sync GoTrue call in thread pool to avoid blocking event loop)
        auth_header = request.headers.get("authorization", "")
        user = await asyncio.get_event_loop().run_in_executor(
            None, get_user_from_token, auth_header
        )

        # Dual-auth paths: attach JWT user if present, but allow through for session auth
        if path in DUAL_AUTH_PATHS:
            request.state.api_user = user  # None if no JWT — handler checks session
            return await call_next(request)

        if not user:
            return JSONResponse(
                {"success": False, "error": {"code": "UNAUTHORIZED", "message": "Invalid or missing token"}},
                status_code=401,
            )

        # Attach user to request state for downstream handlers
        request.state.api_user = user
        return await call_next(request)
