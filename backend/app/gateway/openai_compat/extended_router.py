"""Extended API router for DeerFlow-specific capabilities.

Provides /v1/memory, /v1/skills, /v1/sandbox, and /v1/usage endpoints
for third-party API consumers.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.gateway.api_auth.dependencies import TenantContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["openai-compat-extended"])


def _get_tenant(request: Request) -> TenantContext:
    """Get authenticated tenant from request state."""
    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        raise ValueError("Tenant context not found")
    return tenant


def _make_error(status_code: int, message: str, error_type: str) -> JSONResponse:
    """Create an OpenAI-compatible error response."""
    return JSONResponse(
        status_code=status_code,
        content={"error": {"message": message, "type": error_type, "param": None, "code": error_type}},
    )


# ---------------------------------------------------------------------------
# Memory endpoints
# ---------------------------------------------------------------------------


@router.get("/memory")
async def get_memory(request: Request, user_id: str | None = None):
    """Get memory data for a user within the tenant's scope."""
    try:
        tenant = _get_tenant(request)
    except ValueError:
        return _make_error(401, "Authentication required", "invalid_api_key")

    # Use tenant-scoped user_id (defaults to "default" if not provided)
    effective_user_id = user_id or "default"

    from deerflow.agents.memory.storage import get_memory_storage
    from deerflow.runtime.tenant_context import reset_current_tenant_id, set_current_tenant_id

    # Set tenant context for memory path resolution
    token = set_current_tenant_id(tenant.tenant_id)
    try:
        storage = get_memory_storage()
        memory_data = storage.load(user_id=effective_user_id)
        return JSONResponse(content={"memory": memory_data})
    finally:
        reset_current_tenant_id(token)


# ---------------------------------------------------------------------------
# Skills endpoints
# ---------------------------------------------------------------------------


@router.get("/skills")
async def list_skills(request: Request):
    """List available skills."""
    try:
        _get_tenant(request)  # Verify authentication
    except ValueError:
        return _make_error(401, "Authentication required", "invalid_api_key")

    from app.gateway.deps import get_config
    from deerflow.skills.loader import get_or_new_skill_storage

    config = get_config(request)
    skills_list = []

    try:
        storage = get_or_new_skill_storage(app_config=config)
        skills = storage.load_skills(enabled_only=False)
        for skill in skills:
            skills_list.append(
                {
                    "name": getattr(skill, "name", "unknown"),
                    "description": getattr(skill, "description", "") or "",
                    "enabled": getattr(skill, "enabled", True),
                }
            )
    except Exception:
        # Skills may not be configured; return empty list
        pass

    return JSONResponse(content={"skills": skills_list})


# ---------------------------------------------------------------------------
# Usage endpoints
# ---------------------------------------------------------------------------


@router.get("/usage")
async def get_usage(request: Request, start_date: str | None = None, end_date: str | None = None):
    """Get usage statistics for the authenticated tenant."""
    try:
        tenant = _get_tenant(request)
    except ValueError:
        return _make_error(401, "Authentication required", "invalid_api_key")

    from datetime import datetime

    from app.gateway.deps import get_session_factory
    from deerflow.persistence.api_usage import ApiUsageRepository

    try:
        sf = get_session_factory(request)
        usage_repo = ApiUsageRepository(sf)

        # Parse date range
        start_time = datetime.fromisoformat(start_date) if start_date else None
        end_time = datetime.fromisoformat(end_date) if end_date else None

        # Get aggregated stats
        stats = await usage_repo.get_tenant_stats(tenant.tenant_id, start_time=start_time, end_time=end_time)

        return JSONResponse(content={"usage": stats})
    except Exception as e:
        logger.error(f"Failed to fetch usage: {e}")
        return _make_error(500, "Failed to fetch usage statistics", "internal_error")
