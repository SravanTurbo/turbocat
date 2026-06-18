import os
from pathlib import Path

import boto3
from pydantic_settings import BaseSettings, SettingsConfigDict

_APP_ENV = os.getenv("APP_ENV", "local")
_ENV_FILE = Path(__file__).parent / f".env.{_APP_ENV}"

# Mirrors IAMx's CONFIG_PROVIDER pattern.
# local (default): reads from .env.{APP_ENV} file
# aws:             fetches from SSM Parameter Store + Secrets Manager at startup
_CONFIG_PROVIDER = os.getenv("CONFIG_PROVIDER", "local")


def _load_from_aws(region: str, prefix: str) -> None:
    """
    Fetch orchestrator config from SSM / Secrets Manager and inject into
    os.environ so that Settings() picks them up via its normal env-var path.

    SSM params  → turbocat[-dev].{key}
    Secrets     → turbocat[-dev].{key}
    """
    ssm = boto3.client("ssm", region_name=region)
    sm = boto3.client("secretsmanager", region_name=region)

    def get_param(key: str) -> str:
        return str(ssm.get_parameter(Name=f"{prefix}.{key}", WithDecryption=True)["Parameter"]["Value"])

    def get_secret(key: str) -> str:
        return str(sm.get_secret_value(SecretId=f"{prefix}.{key}")["SecretString"])

    db_host = get_param("database.host")
    db_port = get_param("database.port")
    db_user = get_param("database.user")
    db_name = get_param("database.name")
    db_pass = get_secret("database.password")

    os.environ["DATABASE_URL"] = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    os.environ["AWS_REGION"] = region
    os.environ["JOB_POLL_INTERVAL_SECONDS"] = get_param("scheduler.poll_interval_seconds")
    os.environ["JWT_SECRET"] = get_secret("auth.jwt_secret")
    os.environ["JWT_ALGORITHM"] = get_param("auth.jwt_algorithm")
    os.environ["AGENT_API_KEY"] = get_secret("auth.agent_api_key")
    os.environ["CORS_ORIGINS"] = get_param("auth.cors_origins")


if _CONFIG_PROVIDER == "aws":
    _region = os.getenv("AWS_REGION", "ap-south-1")
    # Dev prefix: turbocat-dev, Prod prefix: turbocat
    # Mirrors the IAMx convention used in setup scripts
    _prefix = os.getenv("AWS_PARAM_PREFIX", "turbocat")
    _load_from_aws(_region, _prefix)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    # Shared RDS — orchestrator-db logical database
    database_url: str  # e.g. postgresql://user:pass@rds-host:5432/turbocat_db

    # AWS
    aws_region: str = "ap-south-1"

    # Scheduler
    job_poll_interval_seconds: int = 30

    # Auth — JWT for frontend/API clients
    jwt_secret: str
    jwt_algorithm: str = "HS256"

    # Auth — shared key for agent ↔ orchestrator machine-to-machine calls
    agent_api_key: str

    # CORS — comma-separated origins, e.g. "https://app.example.com,https://admin.example.com"
    cors_origins: str = "*"


settings = Settings()
