"""Authentication configuration for DeerFlow."""

import logging
import os
import secrets

from pydantic import BaseModel, Field

from app.gateway.auth.sso_config import SSOConfig

logger = logging.getLogger(__name__)

_SECRET_FILE = ".jwt_secret"


class AuthConfig(BaseModel):
    """JWT and auth-related configuration. Parsed once at startup.

    Note: the ``users`` table now lives in the shared persistence
    database managed by ``deerflow.persistence.engine``. The old
    ``users_db_path`` config key has been removed — user storage is
    configured through ``config.database`` like every other table.
    """

    jwt_secret: str = Field(
        ...,
        description="Secret key for JWT signing. MUST be set via AUTH_JWT_SECRET.",
    )
    token_expiry_days: int = Field(default=7, ge=1, le=30)
    oauth_github_client_id: str | None = Field(default=None)
    oauth_github_client_secret: str | None = Field(default=None)
    sso: SSOConfig | None = Field(default=None, description="SSO configuration for external IdP integration")


_auth_config: AuthConfig | None = None


def _load_sso_config_from_env() -> SSOConfig | None:
    """Load SSO configuration from environment variables.

    Environment variables:
        SSO_ENABLED=true
        SSO_PROVIDER_NAME=admin_net
        SSO_PROVIDER_DISPLAY_NAME=Admin.NET 登录
        SSO_PROVIDER_JWT_SECRET=<secret>
        SSO_PROVIDER_ALGORITHM=HS256
        SSO_PROVIDER_AUTO_CREATE_USER=true
        SSO_PROVIDER_DEFAULT_ROLE=user
        SSO_PROVIDER_TOKEN_MAX_AGE=300
        SSO_PROVIDER_ICON=building
        SSO_PROVIDER_LOGIN_URL=https://admin.example.com/#/login
    """
    from app.gateway.auth.sso_config import SSOConfig, SSOProviderConfig

    sso_enabled = os.environ.get("SSO_ENABLED", "").lower() in ("true", "1", "yes")
    sso_secret = os.environ.get("SSO_PROVIDER_JWT_SECRET", "")

    if not sso_enabled or not sso_secret:
        return None

    provider = SSOProviderConfig(
        name=os.environ.get("SSO_PROVIDER_NAME", "admin_net"),
        display_name=os.environ.get("SSO_PROVIDER_DISPLAY_NAME", "Admin.NET 登录"),
        jwt_secret=sso_secret,
        algorithm=os.environ.get("SSO_PROVIDER_ALGORITHM", "HS256"),
        auto_create_user=os.environ.get("SSO_PROVIDER_AUTO_CREATE_USER", "true").lower() in ("true", "1", "yes"),
        default_role=os.environ.get("SSO_PROVIDER_DEFAULT_ROLE", "user"),
        token_max_age=int(os.environ.get("SSO_PROVIDER_TOKEN_MAX_AGE", "300")),
        icon=os.environ.get("SSO_PROVIDER_ICON", "building"),
        login_url=os.environ.get("SSO_PROVIDER_LOGIN_URL") or None,
    )

    logger.info("SSO enabled: provider=%s display_name=%s", provider.name, provider.display_name)
    return SSOConfig(enabled=True, providers=[provider])


def _load_or_create_secret() -> str:
    """Load persisted JWT secret from ``{base_dir}/.jwt_secret``, or generate and persist a new one."""
    from deerflow.config.paths import get_paths

    paths = get_paths()
    secret_file = paths.base_dir / _SECRET_FILE

    try:
        if secret_file.exists():
            secret = secret_file.read_text(encoding="utf-8").strip()
            if secret:
                return secret
    except OSError as exc:
        raise RuntimeError(f"Failed to read JWT secret from {secret_file}. Set AUTH_JWT_SECRET explicitly or fix DEER_FLOW_HOME/base directory permissions so DeerFlow can read its persisted auth secret.") from exc

    secret = secrets.token_urlsafe(32)
    try:
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(secret_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(secret)
    except OSError as exc:
        raise RuntimeError(f"Failed to persist JWT secret to {secret_file}. Set AUTH_JWT_SECRET explicitly or fix DEER_FLOW_HOME/base directory permissions so DeerFlow can store a stable auth secret.") from exc
    return secret


def get_auth_config() -> AuthConfig:
    """Get the global AuthConfig instance. Parses from env on first call."""
    global _auth_config
    if _auth_config is None:
        from dotenv import load_dotenv

        load_dotenv()
        jwt_secret = os.environ.get("AUTH_JWT_SECRET")
        if not jwt_secret:
            jwt_secret = _load_or_create_secret()
            os.environ["AUTH_JWT_SECRET"] = jwt_secret
            logger.warning(
                "⚠ AUTH_JWT_SECRET is not set — using an auto-generated secret "
                "persisted to .jwt_secret. Sessions will survive restarts. "
                "For production, add AUTH_JWT_SECRET to your .env file: "
                'python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )

        # Load SSO config from environment
        sso = _load_sso_config_from_env()

        _auth_config = AuthConfig(jwt_secret=jwt_secret, sso=sso)
    return _auth_config


def set_auth_config(config: AuthConfig) -> None:
    """Set the global AuthConfig instance (for testing)."""
    global _auth_config
    _auth_config = config
