"""JWT validation middleware for /api/* endpoints called by the Next.js frontend.

All /api/* routes (except /api/health) require a valid Supabase JWT.
This is enforced as Starlette middleware, not a per-handler decorator,
so new API endpoints are protected by default.
"""

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

# Paths under /api/ that don't require auth
PUBLIC_API_PATHS = {"/api/health"}


def get_user_from_token(auth_header: str):
    """Extract and validate Supabase JWT from Authorization header value."""
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]
    try:
        from gotrue import SyncGoTrueClient

        gotrue = SyncGoTrueClient(
            url=f"{SUPABASE_URL}/auth/v1",
            headers={"apikey": SUPABASE_ANON_KEY},
        )
        user = gotrue.get_user(token)
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

        # Validate JWT
        auth_header = request.headers.get("authorization", "")
        user = get_user_from_token(auth_header)
        if not user:
            return JSONResponse(
                {"success": False, "error": {"code": "UNAUTHORIZED", "message": "Invalid or missing token"}},
                status_code=401,
            )

        # Attach user to request state for downstream handlers
        request.state.api_user = user
        return await call_next(request)
