"""Request-scoped tenant context for multi-tenant isolation.

Similar to user_context.py, this module provides a ContextVar for
tenant_id that is set by the ApiKeyAuthMiddleware for /v1/* requests.

For non-API-key requests (cookie-based auth), tenant_id is None and
the system falls back to user-only isolation.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Final

_current_tenant_id: Final[ContextVar[str | None]] = ContextVar("deerflow_current_tenant_id", default=None)


def set_current_tenant_id(tenant_id: str) -> Token[str | None]:
    """Set the current tenant ID for this async task.

    Returns a reset token for cleanup in a finally block.
    """
    return _current_tenant_id.set(tenant_id)


def reset_current_tenant_id(token: Token[str | None]) -> None:
    """Restore the tenant context to the state captured by token."""
    _current_tenant_id.reset(token)


def get_current_tenant_id() -> str | None:
    """Return the current tenant ID, or None if unset.

    Returns None for cookie-based authenticated requests (non-API-key).
    """
    return _current_tenant_id.get()


def get_effective_tenant_id() -> str | None:
    """Return the current tenant ID for path resolution.

    Unlike user_id which has a DEFAULT_USER_ID fallback, tenant_id
    returns None when unset, indicating non-tenant (cookie-based) access.
    """
    return _current_tenant_id.get()
