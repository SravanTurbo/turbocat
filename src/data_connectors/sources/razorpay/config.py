from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class RazorpaySourceConfig(BaseSettings):
    """
    Configuration for the Razorpay source connector.

    Fields are loaded from environment variables with the RAZORPAY_ prefix.
    Sensitive values use SecretStr so they are never accidentally logged or
    included in repr() output.

    Environment variables:
        RAZORPAY_API_KEY      — public key (e.g. rzp_live_xxx / rzp_test_xxx)
        RAZORPAY_API_SECRET   — private secret
        RAZORPAY_BASE_URL     — optional override, defaults to production URL
    """

    model_config = SettingsConfigDict(
        env_prefix="RAZORPAY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: str
    api_secret: SecretStr
    base_url: str = "https://api.razorpay.com/v1"
