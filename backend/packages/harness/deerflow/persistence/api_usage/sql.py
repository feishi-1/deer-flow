"""SQLAlchemy-backed API usage repository.

Records individual API request usage for analytics and billing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from deerflow.persistence.api_usage.model import ApiUsageRow


class ApiUsageRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    @staticmethod
    def _row_to_dict(row: ApiUsageRow) -> dict[str, Any]:
        """Convert ORM row to dict with datetime serialization."""
        d = row.to_dict()
        if isinstance(d.get("created_at"), datetime):
            d["created_at"] = d["created_at"].isoformat()
        return d

    async def record(
        self,
        tenant_id: str,
        *,
        user_id: str | None = None,
        thread_id: str | None = None,
        run_id: str | None = None,
        model_name: str | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        request_duration_ms: int | None = None,
        endpoint: str | None = None,
        status_code: int | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        """Record a single API usage event."""
        async with self._sf() as session:
            row = ApiUsageRow(
                tenant_id=tenant_id,
                user_id=user_id,
                thread_id=thread_id,
                run_id=run_id,
                model_name=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                request_duration_ms=request_duration_ms,
                endpoint=endpoint,
                status_code=status_code,
                error_message=error_message,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._row_to_dict(row)

    async def get_tenant_usage(
        self,
        tenant_id: str,
        *,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Get usage records for a tenant within a time range."""
        async with self._sf() as session:
            stmt = select(ApiUsageRow).where(ApiUsageRow.tenant_id == tenant_id)
            if start_time:
                stmt = stmt.where(ApiUsageRow.created_at >= start_time)
            if end_time:
                stmt = stmt.where(ApiUsageRow.created_at <= end_time)
            stmt = stmt.order_by(ApiUsageRow.created_at.desc()).limit(limit)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._row_to_dict(row) for row in rows]

    async def get_tenant_stats(self, tenant_id: str, *, start_time: datetime | None = None, end_time: datetime | None = None) -> dict[str, Any]:
        """Get aggregated usage statistics for a tenant."""
        async with self._sf() as session:
            stmt = select(
                func.count(ApiUsageRow.id).label("total_requests"),
                func.sum(ApiUsageRow.total_tokens).label("total_tokens"),
                func.sum(ApiUsageRow.prompt_tokens).label("total_prompt_tokens"),
                func.sum(ApiUsageRow.completion_tokens).label("total_completion_tokens"),
            ).where(ApiUsageRow.tenant_id == tenant_id)

            if start_time:
                stmt = stmt.where(ApiUsageRow.created_at >= start_time)
            if end_time:
                stmt = stmt.where(ApiUsageRow.created_at <= end_time)

            result = await session.execute(stmt)
            row = result.one()
            return {
                "total_requests": row.total_requests or 0,
                "total_tokens": row.total_tokens or 0,
                "total_prompt_tokens": row.total_prompt_tokens or 0,
                "total_completion_tokens": row.total_completion_tokens or 0,
            }
