"""Configuration models for roundtripper.

Adapted from confluence-markdown-exporter by Sebastian Penhouet.
https://github.com/Spenhouet/confluence-markdown-exporter
"""

from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, Field, SecretStr, field_serializer


class ConnectionConfig(BaseModel):
    """Configuration for the connection like retry options."""

    backoff_and_retry: bool = Field(
        default=True,
        title="Enable Retry",
        description=(
            "Enable or disable automatic retry with exponential backoff on network errors."
        ),
    )
    backoff_factor: int = Field(
        default=2,
        title="Backoff Factor",
        description=(
            "Multiplier for exponential backoff between retries. "
            "For example, 2 means each retry waits twice as long as the previous."
        ),
    )
    max_backoff_seconds: int = Field(
        default=60,
        title="Max Backoff Seconds",
        description="Maximum number of seconds to wait between retries.",
    )
    max_backoff_retries: int = Field(
        default=5,
        title="Max Retries",
        description="Maximum number of retry attempts before giving up.",
    )
    retry_status_codes: list[int] = Field(
        default_factory=lambda: [413, 429, 502, 503, 504],
        title="Retry Status Codes",
        description="HTTP status codes that should trigger a retry.",
    )
    verify_ssl: bool = Field(
        default=True,
        title="Verify SSL",
        description=(
            "Whether to verify SSL certificates for HTTPS requests. "
            "Set to False only if you are sure about the security of your connection."
        ),
    )


class ApiDetails(BaseModel):
    """API authentication details."""

    url: AnyHttpUrl | Literal[""] = Field(
        default="",
        title="Instance URL",
        description="Base URL of the Confluence instance.",
    )
    username: SecretStr = Field(
        default=SecretStr(""),
        title="Username (email)",
        description="Username or email for API authentication.",
    )
    api_token: SecretStr = Field(
        default=SecretStr(""),
        title="API Token",
        description=(
            "API token for authentication (if required). "
            "Create an Atlassian API token at "
            "https://id.atlassian.com/manage-profile/security/api-tokens. "
            "See Atlassian documentation for details."
        ),
    )
    pat: SecretStr = Field(
        default=SecretStr(""),
        title="Personal Access Token (PAT)",
        description=(
            "Personal Access Token for authentication. "
            "Set this if you use a PAT instead of username+API token. "
            "See your Atlassian instance documentation for how to create a PAT."
        ),
    )

    @field_serializer("username", "api_token", "pat", when_used="json")
    def dump_secret(self, v: SecretStr) -> str:
        """Serialize SecretStr fields as plain strings for JSON output."""
        return v.get_secret_value()


class AuthConfig(BaseModel):
    """Authentication configuration for Confluence."""

    confluence: ApiDetails = Field(
        default_factory=ApiDetails,
        title="Confluence Account",
        description="Authentication for Confluence.",
    )


class ConfigModel(BaseModel):
    """Top-level application configuration model."""

    connection_config: ConnectionConfig = Field(
        default_factory=ConnectionConfig, title="Connection Configuration"
    )
    auth: AuthConfig = Field(default_factory=AuthConfig, title="Authentication")
