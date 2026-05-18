"""Admin tenant management API.

Provides CRUD operations for API tenants, including key generation,
rotation, suspension, and quota management. Requires admin role.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.gateway.api_auth.key_manager import generate_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/tenants", tags=["admin-tenants"])


# ---------------------------------------------------------------------------
# Request/Response schemas
# ---------------------------------------------------------------------------


class CreateTenantRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    rate_limit_rpm: int = Field(default=60, ge=1, le=10000)
    rate_limit_tpm: int = Field(default=100000, ge=1000, le=10000000)
    quota_monthly_tokens: int | None = None
    quota_monthly_requests: int | None = None
    max_concurrent_runs: int = Field(default=5, ge=1, le=100)
    allowed_models: list[str] | None = None
    expires_at: str | None = None


class UpdateTenantRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    rate_limit_rpm: int | None = None
    rate_limit_tpm: int | None = None
    quota_monthly_tokens: int | None = None
    quota_monthly_requests: int | None = None
    max_concurrent_runs: int | None = None
    allowed_models: list[str] | None = None


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


async def _require_admin(request: Request) -> None:
    """Verify the request is from an admin user (cookie-based auth)."""
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if getattr(user, "system_role", None) != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


def _get_repo(request: Request):
    """Get ApiTenantRepository from session factory."""
    from app.gateway.deps import get_session_factory
    from deerflow.persistence.api_tenant import ApiTenantRepository

    sf = get_session_factory(request)
    return ApiTenantRepository(sf)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_tenants(
    request: Request,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """List all tenants with optional status filter."""
    await _require_admin(request)
    repo = _get_repo(request)
    tenants = await repo.list_tenants(status=status, limit=limit, offset=offset)
    return JSONResponse(content={"tenants": tenants, "total": len(tenants)})


@router.post("")
async def create_tenant(body: CreateTenantRequest, request: Request):
    """Create a new tenant and generate an API key.

    The API key is returned only once in the response.
    """
    await _require_admin(request)
    repo = _get_repo(request)

    # Generate API key
    full_key, key_hash, key_prefix = generate_api_key()
    tenant_id = str(uuid.uuid4())

    # Parse expires_at if provided
    expires_at = None
    if body.expires_at:
        from datetime import datetime

        expires_at = datetime.fromisoformat(body.expires_at)

    # Build allowed_models dict
    allowed_models = {"models": body.allowed_models} if body.allowed_models else None

    tenant = await repo.create(
        tenant_id=tenant_id,
        name=body.name,
        api_key_hash=key_hash,
        api_key_prefix=key_prefix,
        description=body.description,
        rate_limit_rpm=body.rate_limit_rpm,
        rate_limit_tpm=body.rate_limit_tpm,
        quota_monthly_tokens=body.quota_monthly_tokens,
        quota_monthly_requests=body.quota_monthly_requests,
        max_concurrent_runs=body.max_concurrent_runs,
        allowed_models=allowed_models,
        expires_at=expires_at,
    )

    # Return tenant info WITH the plaintext key (only time it's shown)
    return JSONResponse(
        status_code=201,
        content={
            "tenant": tenant,
            "api_key": full_key,
            "warning": "Save this API key now. It will not be shown again.",
        },
    )


@router.get("/{tenant_id}")
async def get_tenant(tenant_id: str, request: Request):
    """Get tenant details by ID."""
    await _require_admin(request)
    repo = _get_repo(request)
    tenant = await repo.get_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return JSONResponse(content={"tenant": tenant})


@router.patch("/{tenant_id}")
async def update_tenant(tenant_id: str, body: UpdateTenantRequest, request: Request):
    """Update tenant configuration."""
    await _require_admin(request)
    repo = _get_repo(request)

    # Check tenant exists
    tenant = await repo.get_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Update limits if any provided
    updated = await repo.update_limits(
        tenant_id,
        rate_limit_rpm=body.rate_limit_rpm,
        rate_limit_tpm=body.rate_limit_tpm,
        quota_monthly_tokens=body.quota_monthly_tokens,
        quota_monthly_requests=body.quota_monthly_requests,
        max_concurrent_runs=body.max_concurrent_runs,
    )

    # Refresh tenant data
    tenant = await repo.get_by_id(tenant_id)
    return JSONResponse(content={"tenant": tenant, "updated": updated})


@router.delete("/{tenant_id}")
async def delete_tenant(tenant_id: str, request: Request):
    """Delete a tenant permanently."""
    await _require_admin(request)
    repo = _get_repo(request)
    deleted = await repo.delete(tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return JSONResponse(content={"deleted": True})


@router.post("/{tenant_id}/rotate")
async def rotate_key(tenant_id: str, request: Request):
    """Rotate the API key for a tenant. Old key is immediately invalidated."""
    await _require_admin(request)
    repo = _get_repo(request)

    tenant = await repo.get_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Generate new key
    full_key, key_hash, key_prefix = generate_api_key()
    await repo.update_api_key(tenant_id, key_hash, key_prefix)

    return JSONResponse(
        content={
            "api_key": full_key,
            "api_key_prefix": key_prefix,
            "warning": "Save this API key now. It will not be shown again.",
        }
    )


@router.post("/{tenant_id}/suspend")
async def suspend_tenant(tenant_id: str, request: Request):
    """Suspend a tenant (API key becomes inactive)."""
    await _require_admin(request)
    repo = _get_repo(request)
    updated = await repo.update_status(tenant_id, "suspended")
    if not updated:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return JSONResponse(content={"status": "suspended"})


@router.post("/{tenant_id}/resume")
async def resume_tenant(tenant_id: str, request: Request):
    """Resume a suspended tenant."""
    await _require_admin(request)
    repo = _get_repo(request)
    updated = await repo.update_status(tenant_id, "active")
    if not updated:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return JSONResponse(content={"status": "active"})
