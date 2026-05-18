"""API Key authentication middleware for /v1/* endpoints.

Validates Bearer token from the Authorization header, resolves
the tenant, and stamps request.state.tenant with a TenantContext.

This middleware only activates for paths starting with /v1/.
Other paths pass through untouched.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.gateway.api_auth.dependencies import TenantContext
from app.gateway.api_auth.key_manager import hash_api_key, validate_api_key_format

logger = logging.getLogger(__name__)

# Paths under /v1/ that don't require authentication (if any)
_V1_PUBLIC_PATHS: frozenset[str] = frozenset()


def _make_error_response(status_code: int, message: str, error_type: str) -> JSONResponse:
    """Create an OpenAI-compatible error response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "message": message,
                "type": error_type,
                "param": None,
                "code": error_type,
            }
        },
    )


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    """Authenticate /v1/* requests via Bearer API key.

    Flow:
    1. Extract Bearer token from Authorization header
    2. Validate key format (sk-xxx)
    3. Hash and look up in api_tenants table
    4. Check tenant status and expiry
    5. Stamp request.state.tenant with TenantContext
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only process /v1/* paths
        if not request.url.path.startswith("/v1/"):
            return await call_next(request)

        # Check if path is public
        if request.url.path in _V1_PUBLIC_PATHS:
            return await call_next(request)

        # Extract Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return _make_error_response(401, "Missing API key in Authorization header", "invalid_api_key")

        # Parse Bearer token
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return _make_error_response(401, "Invalid Authorization header format. Expected: Bearer sk-xxx", "invalid_api_key")

        api_key = parts[1]

        # Validate key format
        if not validate_api_key_format(api_key):
            return _make_error_response(401, "Invalid API key format", "invalid_api_key")

        # Hash and look up tenant
        key_hash = hash_api_key(api_key)

        # Get tenant repository from app state
        from app.gateway.deps import get_session_factory
        from deerflow.persistence.api_tenant import ApiTenantRepository

        session_factory = get_session_factory(request)
        tenant_repo = ApiTenantRepository(session_factory)

        tenant = await tenant_repo.get_by_api_key_hash(key_hash)
        if not tenant:
            logger.warning(f"API key not found: {api_key[:12]}...")
            return _make_error_response(401, "Invalid API key", "invalid_api_key")

        # Check tenant status
        if tenant["status"] != "active":
            logger.warning(f"Tenant {tenant['id']} is {tenant['status']}")
            return _make_error_response(403, f"API key is {tenant['status']}", "api_key_disabled")

        # Check expiry
        expires_at = tenant.get("expires_at")
        if expires_at:
            # Parse ISO string to datetime if needed
            if isinstance(expires_at, str):
                from datetime import datetime

                expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if datetime.now(UTC) > expires_at:
                logger.warning(f"Tenant {tenant['id']} API key expired")
                return _make_error_response(403, "API key has expired", "api_key_expired")

        # Stamp tenant context
        request.state.tenant = TenantContext.from_tenant_dict(tenant)

        # Set tenant_id in ContextVar for path resolution
        from deerflow.runtime.tenant_context import reset_current_tenant_id, set_current_tenant_id

        token = set_current_tenant_id(tenant["id"])
        try:
            return await call_next(request)
        finally:
            reset_current_tenant_id(token)
