"""SQLAlchemy-backed API quota period repository.

Manages monthly quota periods and cumulative usage tracking.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from deerflow.persistence.api_quota.model import ApiQuotaPeriodRow


class ApiQuotaPeriodRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    @staticmethod
    def _row_to_dict(row: ApiQuotaPeriodRow) -> dict[str, Any]:
        """Convert ORM row to dict with datetime serialization."""
        d = row.to_dict()
        for key in ("period_start", "period_end", "created_at", "updated_at"):
            val = d.get(key)
            if isinstance(val, datetime):
                d[key] = val.isoformat()
        return d

    async def get_or_create_period(self, tenant_id: str, period_start: datetime, period_end: datetime) -> dict[str, Any]:
        """Get existing period or create a new one."""
        async with self._sf() as session:
            # Try to get existing period
            stmt = select(ApiQuotaPeriodRow).where(ApiQuotaPeriodRow.tenant_id == tenant_id, ApiQuotaPeriodRow.period_start == period_start)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            if row:
                return self._row_to_dict(row)

            # Create new period
            row = ApiQuotaPeriodRow(tenant_id=tenant_id, period_start=period_start, period_end=period_end, tokens_used=0, requests_used=0)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._row_to_dict(row)

    async def increment_usage(self, tenant_id: str, period_start: datetime, *, tokens: int = 0, requests: int = 1) -> None:
        """Atomically increment usage counters for a period."""
        async with self._sf() as session:
            stmt = (
                update(ApiQuotaPeriodRow)
                .where(ApiQuotaPeriodRow.tenant_id == tenant_id, ApiQuotaPeriodRow.period_start == period_start)
                .values(
                    tokens_used=ApiQuotaPeriodRow.tokens_used + tokens,
                    requests_used=ApiQuotaPeriodRow.requests_used + requests,
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def get_current_usage(self, tenant_id: str, period_start: datetime) -> dict[str, int]:
        """Get current usage for a period. Returns zeros if period doesn't exist."""
        async with self._sf() as session:
            stmt = select(ApiQuotaPeriodRow).where(ApiQuotaPeriodRow.tenant_id == tenant_id, ApiQuotaPeriodRow.period_start == period_start)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                return {"tokens_used": row.tokens_used, "requests_used": row.requests_used}
            return {"tokens_used": 0, "requests_used": 0}

    async def get_tenant_periods(self, tenant_id: str, *, limit: int = 12) -> list[dict[str, Any]]:
        """Get recent quota periods for a tenant (for usage history)."""
        async with self._sf() as session:
            stmt = select(ApiQuotaPeriodRow).where(ApiQuotaPeriodRow.tenant_id == tenant_id).order_by(ApiQuotaPeriodRow.period_start.desc()).limit(limit)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._row_to_dict(row) for row in rows]
