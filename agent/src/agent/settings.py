import uuid

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """
    Agent configuration — all values loaded from environment variables.

    Environment variables:
        AGENT_ID                  — UUID pre-provisioned in orchestrator DB
        AGENT_ORCHESTRATOR_URL    — base URL of the orchestrator, no trailing slash
        AGENT_API_KEY             — shared secret sent as X-Agent-Key header
        AGENT_MAX_WORKERS         — max concurrent connector jobs (default: 4)
        AGENT_POLL_INTERVAL       — seconds between job polls (default: 30)
        AGENT_HEARTBEAT_INTERVAL  — seconds between heartbeats (default: 60)
    """

    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    id: uuid.UUID
    orchestrator_url: str  # e.g. "https://orchestrator.example.com"
    api_key: str
    max_workers: int = 4
    poll_interval: int = 30
    heartbeat_interval: int = 60
