"""Rate limiting middleware for /v1/* endpoints.

Checks RPM (requests per minute) before allowing the request to proceed.
TPM (tokens per minute) is checked as a pre-flight estimate; actual
token recording happens after the response via usage tracking.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.gateway.rate_limit.sliding_window import get_rate_limiter

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce per-tenant rate limits on /v1/* endpoints.

    Only activates after ApiKeyAuthMiddleware has stamped
    request.state.tenant with a TenantContext.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only process /v1/* paths
        if not request.url.path.startswith("/v1/"):
            return await call_next(request)

        # Get tenant context (set by ApiKeyAuthMiddleware)
        tenant = getattr(request.state, "tenant", None)
        if tenant is None:
            # No tenant = auth middleware hasn't run or failed
            return await call_next(request)

        limiter = get_rate_limiter()

        # Check RPM
        rpm_result = limiter.check_rpm(tenant.tenant_id, tenant.rate_limit_rpm)
        if not rpm_result.allowed:
            logger.warning(f"Rate limit (RPM) exceeded for tenant {tenant.tenant_id}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "message": f"Rate limit exceeded: {tenant.rate_limit_rpm} requests per minute",
                        "type": "rate_limit_exceeded",
                        "param": None,
                        "code": "rate_limit_exceeded",
                    }
                },
                headers={
                    "Retry-After": str(int(rpm_result.retry_after or 1)),
                    "X-RateLimit-Limit-Requests": str(rpm_result.limit),
                    "X-RateLimit-Remaining-Requests": str(rpm_result.remaining),
                },
            )

        # Check TPM (pre-flight estimate)
        tpm_result = limiter.check_tpm(tenant.tenant_id, tenant.rate_limit_tpm)
        if not tpm_result.allowed:
            logger.warning(f"Rate limit (TPM) exceeded for tenant {tenant.tenant_id}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "message": f"Token rate limit exceeded: {tenant.rate_limit_tpm} tokens per minute",
                        "type": "rate_limit_exceeded",
                        "param": None,
                        "code": "tokens_rate_limit_exceeded",
                    }
                },
                headers={
                    "Retry-After": str(int(tpm_result.retry_after or 1)),
                    "X-RateLimit-Limit-Tokens": str(tpm_result.limit),
                    "X-RateLimit-Remaining-Tokens": str(tpm_result.remaining),
                },
            )

        # Add rate limit headers to successful responses
        response = await call_next(request)
        response.headers["X-RateLimit-Limit-Requests"] = str(rpm_result.limit)
        response.headers["X-RateLimit-Remaining-Requests"] = str(rpm_result.remaining)
        response.headers["X-RateLimit-Limit-Tokens"] = str(tpm_result.limit)
        response.headers["X-RateLimit-Remaining-Tokens"] = str(tpm_result.remaining)
        return response
