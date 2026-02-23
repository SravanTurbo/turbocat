from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ClickHouseConfig(BaseSettings):
    """
    Configuration for the ClickHouse destination connector.

    Fields are loaded from environment variables with the CLICKHOUSE_ prefix.
    The password uses SecretStr so it is never accidentally logged or
    included in repr() output.

    Environment variables:
        CLICKHOUSE_HOST       — hostname or IP of the ClickHouse server
        CLICKHOUSE_PORT       — native protocol port (default: 9000)
        CLICKHOUSE_DATABASE   — target database (default: "default")
        CLICKHOUSE_USER       — username (default: "default")
        CLICKHOUSE_PASSWORD   — password (default: empty string)
        CLICKHOUSE_SECURE     — use TLS/SSL (default: false)
    """

    model_config = SettingsConfigDict(
        env_prefix="CLICKHOUSE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str
    port: int = 9000
    database: str = "default"
    user: str = "default"
    password: SecretStr = SecretStr("")
    secure: bool = False
