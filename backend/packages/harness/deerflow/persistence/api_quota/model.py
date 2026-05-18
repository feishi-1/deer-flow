"""ORM model for the api_quota_periods table.

Tracks cumulative usage per tenant per billing period (monthly).
Used for quota enforcement — each period row accumulates tokens
and request counts, checked before allowing new API calls.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from deerflow.persistence.base import Base


class ApiQuotaPeriodRow(Base):
    __tablename__ = "api_quota_periods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Period boundaries (monthly granularity)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Cumulative usage within this period
    tokens_used: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    requests_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    __table_args__ = (Index("ix_api_quota_tenant_period", "tenant_id", "period_start", unique=True),)
