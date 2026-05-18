"""Admin usage analytics API.

Provides aggregated usage statistics and detailed logs for all tenants.
Requires admin role.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/usage", tags=["admin-usage"])


async def _require_admin(request: Request) -> None:
    """Verify the request is from an admin user."""
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if getattr(user, "system_role", None) != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/tenants/{tenant_id}")
async def get_tenant_usage(
    tenant_id: str,
    request: Request,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 1000,
):
    """Get detailed usage records for a specific tenant."""
    await _require_admin(request)

    from app.gateway.deps import get_session_factory
    from deerflow.persistence.api_usage import ApiUsageRepository

    sf = get_session_factory(request)
    usage_repo = ApiUsageRepository(sf)

    # Parse dates
    start_time = datetime.fromisoformat(start_date) if start_date else None
    end_time = datetime.fromisoformat(end_date) if end_date else None

    # Get usage records
    records = await usage_repo.get_tenant_usage(
        tenant_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )

    # Get aggregated stats
    stats = await usage_repo.get_tenant_stats(
        tenant_id,
        start_time=start_time,
        end_time=end_time,
    )

    return JSONResponse(
        content={
            "tenant_id": tenant_id,
            "stats": stats,
            "records": records,
            "count": len(records),
        }
    )


@router.get("/quota/{tenant_id}")
async def get_tenant_quota_history(tenant_id: str, request: Request, limit: int = 12):
    """Get quota period history for a tenant (last N months)."""
    await _require_admin(request)

    from app.gateway.deps import get_session_factory
    from deerflow.persistence.api_quota import ApiQuotaPeriodRepository

    sf = get_session_factory(request)
    quota_repo = ApiQuotaPeriodRepository(sf)

    periods = await quota_repo.get_tenant_periods(tenant_id, limit=limit)

    return JSONResponse(
        content={
            "tenant_id": tenant_id,
            "periods": periods,
        }
    )


@router.get("/summary")
async def get_usage_summary(
    request: Request,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Get aggregated usage summary across all tenants."""
    await _require_admin(request)

    from app.gateway.deps import get_session_factory
    from deerflow.persistence.api_tenant import ApiTenantRepository

    sf = get_session_factory(request)
    tenant_repo = ApiTenantRepository(sf)

    # Get all tenants
    tenants = await tenant_repo.list_tenants(limit=1000)

    # Aggregate usage per tenant
    from deerflow.persistence.api_usage import ApiUsageRepository

    usage_repo = ApiUsageRepository(sf)
    start_time = datetime.fromisoformat(start_date) if start_date else None
    end_time = datetime.fromisoformat(end_date) if end_date else None

    summary = []
    for tenant in tenants:
        stats = await usage_repo.get_tenant_stats(
            tenant["id"],
            start_time=start_time,
            end_time=end_time,
        )
        summary.append(
            {
                "tenant_id": tenant["id"],
                "tenant_name": tenant["name"],
                "status": tenant["status"],
                "stats": stats,
            }
        )

    return JSONResponse(content={"summary": summary})
