"""Quota enforcement middleware for /v1/* endpoints.

Checks monthly quota (tokens + requests) before allowing requests.
Runs after ApiKeyAuthMiddleware and RateLimitMiddleware.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.gateway.quota.tracker import check_quota

logger = logging.getLogger(__name__)


class QuotaMiddleware(BaseHTTPMiddleware):
    """Enforce monthly quota limits on /v1/* endpoints.

    Checks if the tenant has remaining quota before processing.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only process /v1/* paths
        if not request.url.path.startswith("/v1/"):
            return await call_next(request)

        # Get tenant context
        tenant = getattr(request.state, "tenant", None)
        if tenant is None:
            return await call_next(request)

        # Skip quota check if both quotas are unlimited
        if tenant.quota_monthly_tokens is None and tenant.quota_monthly_requests is None:
            return await call_next(request)

        # Get quota repository
        from app.gateway.deps import get_session_factory
        from deerflow.persistence.api_quota import ApiQuotaPeriodRepository

        try:
            sf = get_session_factory(request)
            quota_repo = ApiQuotaPeriodRepository(sf)
        except Exception:
            # If DB is unavailable, allow the request (fail-open for quota)
            logger.warning("Quota check skipped: database unavailable")
            return await call_next(request)

        # Check quota
        allowed, error_msg = await check_quota(
            tenant.tenant_id,
            quota_repo,
            quota_monthly_tokens=tenant.quota_monthly_tokens,
            quota_monthly_requests=tenant.quota_monthly_requests,
        )

        if not allowed:
            logger.warning(f"Quota exceeded for tenant {tenant.tenant_id}: {error_msg}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "message": error_msg,
                        "type": "quota_exceeded",
                        "param": None,
                        "code": "quota_exceeded",
                    }
                },
            )

        return await call_next(request)
