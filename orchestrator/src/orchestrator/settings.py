from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    # Shared RDS — orchestrator-db logical database
    database_url: str  # e.g. postgresql://user:pass@rds-host:5432/orchestrator-db

    # AWS
    aws_region: str = "ap-south-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # Scheduler
    job_poll_interval_seconds: int = 30  # how often agents poll


settings = Settings()
