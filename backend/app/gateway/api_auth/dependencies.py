"""Dependencies and context for API key authentication.

Provides the TenantContext dataclass and helper functions for
extracting tenant information from authenticated requests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TenantContext:
    """Authenticated tenant context attached to request.state."""

    tenant_id: str
    name: str
    status: str
    rate_limit_rpm: int
    rate_limit_tpm: int
    quota_monthly_tokens: int | None
    quota_monthly_requests: int | None
    max_concurrent_runs: int
    allowed_models: list[str] | None
    sandbox_config: dict[str, Any] | None

    @classmethod
    def from_tenant_dict(cls, tenant: dict[str, Any]) -> TenantContext:
        """Create TenantContext from a tenant repository dict."""
        allowed = tenant.get("allowed_models")
        if isinstance(allowed, dict):
            allowed = allowed.get("models")
        return cls(
            tenant_id=tenant["id"],
            name=tenant["name"],
            status=tenant["status"],
            rate_limit_rpm=tenant["rate_limit_rpm"],
            rate_limit_tpm=tenant["rate_limit_tpm"],
            quota_monthly_tokens=tenant.get("quota_monthly_tokens"),
            quota_monthly_requests=tenant.get("quota_monthly_requests"),
            max_concurrent_runs=tenant["max_concurrent_runs"],
            allowed_models=allowed,
            sandbox_config=tenant.get("sandbox_config"),
        )
