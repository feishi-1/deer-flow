"""Usage tracker for recording API usage and enforcing quotas.

Tracks token consumption and request counts per tenant per month.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


def get_current_period() -> tuple[datetime, datetime]:
    """Get the current monthly quota period boundaries.

    Returns:
        Tuple of (period_start, period_end) as timezone-aware datetimes
    """
    now = datetime.now(UTC)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Calculate next month's first day
    if period_start.month == 12:
        period_end = period_start.replace(year=period_start.year + 1, month=1)
    else:
        period_end = period_start.replace(month=period_start.month + 1)

    return period_start, period_end


async def check_quota(
    tenant_id: str,
    quota_repo,
    *,
    quota_monthly_tokens: int | None,
    quota_monthly_requests: int | None,
) -> tuple[bool, str | None]:
    """Check if a tenant has quota available for a new request.

    Args:
        tenant_id: The tenant identifier
        quota_repo: ApiQuotaPeriodRepository instance
        quota_monthly_tokens: Monthly token limit (None = unlimited)
        quota_monthly_requests: Monthly request limit (None = unlimited)

    Returns:
        Tuple of (allowed, error_message)
    """
    period_start, period_end = get_current_period()

    # Get or create current period
    period = await quota_repo.get_or_create_period(tenant_id, period_start, period_end)

    # Check request quota
    if quota_monthly_requests is not None:
        if period["requests_used"] >= quota_monthly_requests:
            return False, f"Monthly request quota exceeded: {quota_monthly_requests} requests/month"

    # Check token quota
    if quota_monthly_tokens is not None:
        if period["tokens_used"] >= quota_monthly_tokens:
            return False, f"Monthly token quota exceeded: {quota_monthly_tokens} tokens/month"

    return True, None


async def record_usage(
    tenant_id: str,
    usage_repo,
    quota_repo,
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
) -> None:
    """Record API usage after a request completes.

    Args:
        tenant_id: The tenant identifier
        usage_repo: ApiUsageRepository instance
        quota_repo: ApiQuotaPeriodRepository instance
        (other args): Usage details to record
    """
    try:
        # Record detailed usage
        await usage_repo.record(
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

        # Update quota period
        period_start, _ = get_current_period()
        await quota_repo.increment_usage(tenant_id, period_start, tokens=total_tokens, requests=1)

        logger.info(f"Recorded usage for tenant {tenant_id}: {total_tokens} tokens, 1 request")
    except Exception as e:
        logger.error(f"Failed to record usage for tenant {tenant_id}: {e}")
