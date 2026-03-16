import json

import boto3
from botocore.exceptions import ClientError

from orchestrator.settings import settings

_client = boto3.client(
    "secretsmanager",
    region_name=settings.aws_region,
    aws_access_key_id=settings.aws_access_key_id or None,
    aws_secret_access_key=settings.aws_secret_access_key or None,
)


def put_secret(secret_ref: str, credentials: dict[str, str]) -> None:
    """Save credentials to Secrets Manager. Called once at connection creation."""
    try:
        # Try update first, create if it doesn't exist
        try:
            _client.put_secret_value(SecretId=secret_ref, SecretString=json.dumps(credentials))
        except _client.exceptions.ResourceNotFoundException:
            _client.create_secret(Name=secret_ref, SecretString=json.dumps(credentials))
    except ClientError as e:
        raise RuntimeError(f"Failed to save secret '{secret_ref}': {e}") from e


def get_secret(secret_ref: str) -> dict[str, str]:
    """Fetch and return credentials for a pipeline. Always in-memory, never logged."""
    try:
        response = _client.get_secret_value(SecretId=secret_ref)
    except ClientError as e:
        raise RuntimeError(f"Failed to fetch secret '{secret_ref}': {e}") from e

    secret_string = response.get("SecretString")
    if not secret_string:
        raise RuntimeError(f"Secret '{secret_ref}' has no SecretString value")

    return json.loads(secret_string)  # type: ignore[no-any-return]
