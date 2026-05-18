"""ORM model for the api_tenants table.

Stores third-party API tenant information including API key hashes,
rate limits, quotas, and sandbox configuration. Each tenant maps to
exactly one API key (sk-xxx format).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, BigInteger, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from deerflow.persistence.base import Base


class ApiTenantRow(Base):
    __tablename__ = "api_tenants"

    # UUIDs stored as 36-char strings for cross-backend portability.
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # API key: only the SHA-256 hash is stored; prefix for display.
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    api_key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)

    # Tenant status: "active" | "suspended" | "revoked"
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")

    # Rate limits (per-minute sliding window)
    rate_limit_rpm: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    rate_limit_tpm: Mapped[int] = mapped_column(Integer, nullable=False, default=100000)

    # Monthly quotas (null = unlimited)
    quota_monthly_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    quota_monthly_requests: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Concurrency control
    max_concurrent_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    # Model access control (null = all models allowed)
    allowed_models: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Sandbox configuration overrides for this tenant
    sandbox_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Extensible metadata
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_api_tenants_status", "status"),)
