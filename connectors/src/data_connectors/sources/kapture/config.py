from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class KaptureSourceConfig(BaseSettings):
    """
    Configuration for the Kapture source connector.

    Fields are loaded from environment variables with the KAPTURE_ prefix.

    Environment variables:
        KAPTURE_SUBDOMAIN   — your Kapture subdomain (e.g. "acme" for acme.kapturecrm.com)
        KAPTURE_TOKEN       — auth token; sent as "Authorization: Basic <token>"
        KAPTURE_CM_ID       — your Kapture account ID (required by customers/orders APIs)
        KAPTURE_BASE_URL    — optional full base URL override
    """

    model_config = SettingsConfigDict(
        env_prefix="KAPTURE_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    subdomain: str
    token: SecretStr
    cm_id: int | None = None  # required by customers/orders, not tickets
    tickets_template_id: int = 117
    timeout: int = 30
    max_retries: int = 3

    @property
    def base_url(self) -> str:
        return f"https://{self.subdomain}.kapturecrm.com"
