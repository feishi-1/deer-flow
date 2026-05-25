"""SSO configuration models for external identity provider integration.

Supports JWT-based SSO where an external system (e.g. Admin.NET) issues
a signed JWT token that DeerFlow validates to create a local session.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SSOClaimsMapping(BaseModel):
    """Mapping of external JWT claim names to DeerFlow user fields.

    Matches Admin.NET JWT structure by default.
    """

    user_id: str = Field(default="UserId", description="Claim for external user ID")
    account: str = Field(default="Account", description="Claim for username/account")
    real_name: str = Field(default="RealName", description="Claim for real name")
    nick_name: str = Field(default="NickName", description="Claim for nickname")
    account_type: str = Field(default="AccountType", description="Claim for account type")
    tenant_id: str = Field(default="TenantId", description="Claim for tenant ID")
    org_id: str = Field(default="OrgId", description="Claim for org ID")
    org_name: str = Field(default="OrgName", description="Claim for org name")
    org_type: str = Field(default="OrgType", description="Claim for org type")
    login_mode: str = Field(default="LoginMode", description="Claim for login mode")


class SSOProviderConfig(BaseModel):
    """Configuration for a single SSO identity provider."""

    name: str = Field(default="admin_net", description="Provider identifier")
    display_name: str = Field(default="Admin.NET 登录", description="Display name on login page")
    jwt_secret: str = Field(..., description="HMAC-SHA256 signing key (plain string)")
    algorithm: str = Field(default="HS256", description="JWT signing algorithm")
    claims_mapping: SSOClaimsMapping = Field(default_factory=SSOClaimsMapping)
    auto_create_user: bool = Field(default=True, description="Create DeerFlow user on first SSO login")
    default_role: str = Field(default="user", description="Role for auto-created users")
    token_max_age: int = Field(default=300, description="Max token age in seconds (anti-replay)")
    icon: str = Field(default="building", description="Icon name for login page button")
    login_url: str | None = Field(default=None, description="External login page URL (for redirect flow)")


class SSOConfig(BaseModel):
    """Top-level SSO configuration."""

    enabled: bool = Field(default=False, description="Enable SSO authentication")
    providers: list[SSOProviderConfig] = Field(default_factory=list)
