"""SSO provider: validates external JWT tokens and maps to DeerFlow users.

Designed for Admin.NET integration using HMAC-SHA256 signed JWTs.
"""

from __future__ import annotations

import logging
import time

import jwt as pyjwt

from app.gateway.auth.models import User
from app.gateway.auth.repositories.base import UserRepository
from app.gateway.auth.sso_config import SSOProviderConfig

logger = logging.getLogger(__name__)


class SSOTokenError(Exception):
    """Raised when SSO token validation fails."""

    def __init__(self, message: str, code: str = "invalid_token"):
        self.message = message
        self.code = code
        super().__init__(message)


class SSOProvider:
    """Validates external JWT tokens and manages user lookup/creation."""

    def __init__(self, user_repo: UserRepository):
        self._repo = user_repo

    async def verify_token(self, token: str, config: SSOProviderConfig) -> dict:
        """Verify an external JWT token signature and validity.

        Args:
            token: Raw JWT string from external system
            config: Provider configuration with secret and algorithm

        Returns:
            Decoded claims dictionary

        Raises:
            SSOTokenError: If token is invalid, expired, or too old
        """
        try:
            payload = pyjwt.decode(
                token,
                config.jwt_secret,
                algorithms=[config.algorithm],
                options={"verify_exp": False, "verify_iat": False},
            )
        except pyjwt.ExpiredSignatureError:
            raise SSOTokenError("Token has expired", "token_expired")
        except pyjwt.InvalidSignatureError:
            raise SSOTokenError("Invalid token signature", "invalid_signature")
        except pyjwt.DecodeError as e:
            raise SSOTokenError(f"Failed to decode token: {e}", "decode_error")
        except Exception as e:
            raise SSOTokenError(f"Token validation failed: {e}", "invalid_token")

        # Anti-replay: check token age
        iat = payload.get("iat") or payload.get("nbf")
        if iat and isinstance(iat, (int, float)):
            age = time.time() - iat
            if age > config.token_max_age:
                raise SSOTokenError(
                    f"Token too old ({int(age)}s > {config.token_max_age}s)",
                    "token_too_old",
                )

        return payload

    async def get_or_create_user(self, claims: dict, config: SSOProviderConfig) -> User:
        """Look up or create a DeerFlow user from external JWT claims.

        Strategy:
        1. Find by oauth_provider + oauth_id (exact match)
        2. If not found and auto_create_user is True, create new user
        3. If found, update display_name/org_name if changed

        Args:
            claims: Decoded JWT claims dictionary
            config: Provider configuration

        Returns:
            DeerFlow User object

        Raises:
            SSOTokenError: If user not found and auto_create is disabled
        """
        mapping = config.claims_mapping
        external_id = str(claims.get(mapping.user_id, ""))
        account = str(claims.get(mapping.account, ""))
        real_name = str(claims.get(mapping.real_name, "") or "")
        nick_name = str(claims.get(mapping.nick_name, "") or "")
        org_name = str(claims.get(mapping.org_name, "") or "")
        tenant_id = str(claims.get(mapping.tenant_id, "") or "")

        if not external_id:
            raise SSOTokenError("Missing user ID in token claims", "missing_user_id")

        display_name = real_name or nick_name or account

        # 1. Look up by oauth identity
        user = await self._repo.get_user_by_oauth(config.name, external_id)

        if user is None:
            if not config.auto_create_user:
                raise SSOTokenError(
                    f"User {account} not registered in DeerFlow",
                    "user_not_registered",
                )
            # 2. Create new user (no password — SSO only)
            user = User(
                email=f"{account}@sso.deerflow.internal",
                password_hash=None,
                system_role=config.default_role,
                oauth_provider=config.name,
                oauth_id=external_id,
                display_name=display_name,
                org_name=org_name,
                external_tenant_id=tenant_id,
            )
            user = await self._repo.create_user(user)
            logger.info("SSO: created user %s (external_id=%s, provider=%s)", account, external_id, config.name)
        else:
            # 3. Update profile if changed
            updated = False
            if user.display_name != display_name:
                user.display_name = display_name
                updated = True
            if user.org_name != org_name:
                user.org_name = org_name
                updated = True
            if user.external_tenant_id != tenant_id:
                user.external_tenant_id = tenant_id
                updated = True
            if updated:
                await self._repo.update_user(user)
                logger.info("SSO: updated profile for user %s", account)

        return user
