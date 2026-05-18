"""SQLAlchemy-backed API tenant repository.

Provides CRUD operations for API tenants with API key management.
Each method acquires its own short-lived session.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from deerflow.persistence.api_tenant.model import ApiTenantRow


class ApiTenantRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    @staticmethod
    def _row_to_dict(row: ApiTenantRow) -> dict[str, Any]:
        """Convert ORM row to dict with datetime serialization."""
        d = row.to_dict()
        # Convert datetime to ISO string
        for key in ("created_at", "updated_at", "expires_at"):
            val = d.get(key)
            if isinstance(val, datetime):
                d[key] = val.isoformat()
        return d

    async def create(
        self,
        tenant_id: str,
        name: str,
        api_key_hash: str,
        api_key_prefix: str,
        *,
        description: str | None = None,
        rate_limit_rpm: int = 60,
        rate_limit_tpm: int = 100000,
        quota_monthly_tokens: int | None = None,
        quota_monthly_requests: int | None = None,
        max_concurrent_runs: int = 5,
        allowed_models: dict | None = None,
        sandbox_config: dict | None = None,
        metadata_json: dict | None = None,
        expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Create a new API tenant."""
        async with self._sf() as session:
            row = ApiTenantRow(
                id=tenant_id,
                name=name,
                description=description,
                api_key_hash=api_key_hash,
                api_key_prefix=api_key_prefix,
                rate_limit_rpm=rate_limit_rpm,
                rate_limit_tpm=rate_limit_tpm,
                quota_monthly_tokens=quota_monthly_tokens,
                quota_monthly_requests=quota_monthly_requests,
                max_concurrent_runs=max_concurrent_runs,
                allowed_models=allowed_models,
                sandbox_config=sandbox_config,
                metadata_json=metadata_json or {},
                expires_at=expires_at,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._row_to_dict(row)

    async def get_by_id(self, tenant_id: str) -> dict[str, Any] | None:
        """Get tenant by ID."""
        async with self._sf() as session:
            result = await session.execute(select(ApiTenantRow).where(ApiTenantRow.id == tenant_id))
            row = result.scalar_one_or_none()
            return self._row_to_dict(row) if row else None

    async def get_by_api_key_hash(self, api_key_hash: str) -> dict[str, Any] | None:
        """Get tenant by API key hash."""
        async with self._sf() as session:
            result = await session.execute(select(ApiTenantRow).where(ApiTenantRow.api_key_hash == api_key_hash))
            row = result.scalar_one_or_none()
            return self._row_to_dict(row) if row else None

    async def list_tenants(self, *, status: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """List tenants with optional status filter."""
        async with self._sf() as session:
            stmt = select(ApiTenantRow)
            if status:
                stmt = stmt.where(ApiTenantRow.status == status)
            stmt = stmt.order_by(ApiTenantRow.created_at.desc()).limit(limit).offset(offset)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._row_to_dict(row) for row in rows]

    async def update_status(self, tenant_id: str, status: str) -> bool:
        """Update tenant status."""
        async with self._sf() as session:
            stmt = update(ApiTenantRow).where(ApiTenantRow.id == tenant_id).values(status=status)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0

    async def update_api_key(self, tenant_id: str, api_key_hash: str, api_key_prefix: str) -> bool:
        """Rotate API key for a tenant."""
        async with self._sf() as session:
            stmt = update(ApiTenantRow).where(ApiTenantRow.id == tenant_id).values(api_key_hash=api_key_hash, api_key_prefix=api_key_prefix)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0

    async def update_limits(
        self,
        tenant_id: str,
        *,
        rate_limit_rpm: int | None = None,
        rate_limit_tpm: int | None = None,
        quota_monthly_tokens: int | None = None,
        quota_monthly_requests: int | None = None,
        max_concurrent_runs: int | None = None,
    ) -> bool:
        """Update tenant rate limits and quotas."""
        async with self._sf() as session:
            values = {}
            if rate_limit_rpm is not None:
                values["rate_limit_rpm"] = rate_limit_rpm
            if rate_limit_tpm is not None:
                values["rate_limit_tpm"] = rate_limit_tpm
            if quota_monthly_tokens is not None:
                values["quota_monthly_tokens"] = quota_monthly_tokens
            if quota_monthly_requests is not None:
                values["quota_monthly_requests"] = quota_monthly_requests
            if max_concurrent_runs is not None:
                values["max_concurrent_runs"] = max_concurrent_runs

            if not values:
                return False

            stmt = update(ApiTenantRow).where(ApiTenantRow.id == tenant_id).values(**values)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0

    async def delete(self, tenant_id: str) -> bool:
        """Delete a tenant."""
        async with self._sf() as session:
            result = await session.execute(select(ApiTenantRow).where(ApiTenantRow.id == tenant_id))
            row = result.scalar_one_or_none()
            if row:
                await session.delete(row)
                await session.commit()
                return True
            return False
