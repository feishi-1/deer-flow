"""Sliding window rate limiter (in-memory, single-instance).

Uses a deque of timestamps per tenant to implement a sliding window
counter. Thread-safe via threading.Lock.

Two dimensions are tracked independently:
- RPM (requests per minute)
- TPM (tokens per minute) — updated after request completion
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    limit: int
    remaining: int
    reset_at: float  # Unix timestamp when the window resets
    retry_after: float | None = None  # Seconds until retry is allowed


class SlidingWindowLimiter:
    """In-memory sliding window rate limiter.

    Each tenant gets independent counters for RPM and TPM.
    State is lost on process restart (acceptable for single-instance).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # tenant_id -> deque of request timestamps
        self._rpm_windows: dict[str, deque[float]] = {}
        # tenant_id -> deque of (timestamp, token_count) tuples
        self._tpm_windows: dict[str, deque[tuple[float, int]]] = {}

    def check_rpm(self, tenant_id: str, limit: int) -> RateLimitResult:
        """Check if a request is allowed under the RPM limit.

        Args:
            tenant_id: The tenant identifier
            limit: Maximum requests per minute

        Returns:
            RateLimitResult indicating whether the request is allowed
        """
        now = time.time()
        window_start = now - 60.0

        with self._lock:
            window = self._rpm_windows.setdefault(tenant_id, deque())

            # Evict expired entries
            while window and window[0] < window_start:
                window.popleft()

            current_count = len(window)

            if current_count >= limit:
                # Rate limited
                oldest = window[0] if window else now
                retry_after = oldest + 60.0 - now
                return RateLimitResult(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    reset_at=oldest + 60.0,
                    retry_after=max(0.1, retry_after),
                )

            # Allow and record
            window.append(now)
            return RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=limit - current_count - 1,
                reset_at=now + 60.0,
            )

    def check_tpm(self, tenant_id: str, limit: int) -> RateLimitResult:
        """Check if tokens are available under the TPM limit.

        This is a pre-check based on current window usage.
        Actual token consumption is recorded after the request completes.
        """
        now = time.time()
        window_start = now - 60.0

        with self._lock:
            window = self._tpm_windows.setdefault(tenant_id, deque())

            # Evict expired entries
            while window and window[0][0] < window_start:
                window.popleft()

            current_tokens = sum(tokens for _, tokens in window)

            if current_tokens >= limit:
                oldest = window[0][0] if window else now
                retry_after = oldest + 60.0 - now
                return RateLimitResult(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    reset_at=oldest + 60.0,
                    retry_after=max(0.1, retry_after),
                )

            return RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=limit - current_tokens,
                reset_at=now + 60.0,
            )

    def record_tokens(self, tenant_id: str, token_count: int) -> None:
        """Record token consumption after a request completes.

        Called by the usage tracking middleware after the response is sent.
        """
        now = time.time()
        with self._lock:
            window = self._tpm_windows.setdefault(tenant_id, deque())
            window.append((now, token_count))

    def cleanup_tenant(self, tenant_id: str) -> None:
        """Remove all state for a tenant (e.g., on key revocation)."""
        with self._lock:
            self._rpm_windows.pop(tenant_id, None)
            self._tpm_windows.pop(tenant_id, None)


# Module-level singleton
_limiter: SlidingWindowLimiter | None = None


def get_rate_limiter() -> SlidingWindowLimiter:
    """Get the global rate limiter singleton."""
    global _limiter
    if _limiter is None:
        _limiter = SlidingWindowLimiter()
    return _limiter
