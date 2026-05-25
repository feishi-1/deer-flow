"""SSO authentication endpoints.

Provides JWT-based single sign-on for external systems (e.g. Admin.NET).
External systems redirect users here with a signed JWT token; DeerFlow
validates the token, creates/links a local user, and establishes a session.
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from app.gateway.auth import create_access_token
from app.gateway.auth.config import get_auth_config
from app.gateway.auth.sso_provider import SSOProvider, SSOTokenError
from app.gateway.csrf_middleware import is_secure_request
from app.gateway.deps import get_user_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth/sso", tags=["sso"])


def _get_sso_config():
    """Get SSO config from auth config."""
    auth_config = get_auth_config()
    return getattr(auth_config, "sso", None)


def _validate_next_url(next_url: str) -> str:
    """Validate redirect URL to prevent open redirect attacks.

    Only allows relative paths starting with '/'.
    """
    if not next_url:
        return "/workspace"
    # Must start with / and not be protocol-relative (//evil.com)
    if not next_url.startswith("/") or next_url.startswith("//"):
        return "/workspace"
    # Strip any control characters
    if re.search(r"[\x00-\x1f]", next_url):
        return "/workspace"
    return next_url


def _set_session_cookie(response: Response, token: str, request: Request) -> None:
    """Set the access_token session cookie."""
    auth_config = get_auth_config()
    max_age = auth_config.token_expiry_days * 24 * 3600
    secure = is_secure_request(request)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=max_age,
        path="/",
    )


@router.get("/providers")
async def list_sso_providers():
    """Return list of enabled SSO providers for the login page.

    Response format:
    [{"name": "admin_net", "display_name": "Admin.NET 登录", "icon": "building", "login_url": "..."}]
    """
    sso_config = _get_sso_config()
    if not sso_config or not sso_config.enabled:
        return []
    return [
        {
            "name": p.name,
            "display_name": p.display_name,
            "icon": p.icon,
            "login_url": p.login_url,
        }
        for p in sso_config.providers
    ]


@router.get("")
async def sso_login_get(
    request: Request,
    token: str,
    next: str = "/workspace",
    provider: str = "admin_net",
):
    """SSO login via GET (URL token relay from external system).

    Usage from Admin.NET:
        GET /api/v1/auth/sso?token=<jwt>&next=/workspace/chats

    Flow:
    1. Validate external JWT (HMAC-SHA256)
    2. Extract user claims (UserId, Account, RealName, OrgName, etc.)
    3. Find or create DeerFlow user
    4. Issue DeerFlow session cookie
    5. 302 redirect to `next` URL
    """
    return await _handle_sso_login(request, token, next, provider)


@router.post("")
async def sso_login_post(
    request: Request,
    token: str,
    next: str = "/workspace",
    provider: str = "admin_net",
):
    """SSO login via POST (form submission from external system).

    Same logic as GET but accepts token in POST body for security.
    """
    return await _handle_sso_login(request, token, next, provider)


async def _handle_sso_login(request: Request, token: str, next_url: str, provider_name: str) -> Response:
    """Core SSO login handler shared by GET and POST endpoints."""
    # 1. Check SSO is enabled
    sso_config = _get_sso_config()
    if not sso_config or not sso_config.enabled:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="SSO is not enabled",
        )

    # 2. Find provider config
    provider_config = None
    for p in sso_config.providers:
        if p.name == provider_name:
            provider_config = p
            break
    if provider_config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown SSO provider: {provider_name}",
        )

    # 3. Verify external JWT
    user_repo = get_user_repository()
    sso_provider = SSOProvider(user_repo)

    try:
        claims = await sso_provider.verify_token(token, provider_config)
    except SSOTokenError as e:
        logger.warning("SSO token validation failed: %s (code=%s)", e.message, e.code)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
        )

    # 4. Get or create DeerFlow user
    try:
        user = await sso_provider.get_or_create_user(claims, provider_config)
    except SSOTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=e.message,
        )

    # 5. Issue DeerFlow session
    deerflow_token = create_access_token(str(user.id), token_version=user.token_version)

    # 6. Redirect to target page
    safe_next = _validate_next_url(next_url)
    response = RedirectResponse(url=safe_next, status_code=302)
    _set_session_cookie(response, deerflow_token, request)

    logger.info("SSO login successful: user=%s provider=%s", user.email, provider_name)
    return response
