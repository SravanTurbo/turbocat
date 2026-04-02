import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel, ConfigDict, ValidationError

from orchestrator.settings import settings

# ---------------------------------------------------------------------------
# JWT — frontend / API clients
# ---------------------------------------------------------------------------

_bearer = HTTPBearer(auto_error=False)


class TokenPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sub: str
    account_id: uuid.UUID


def verify_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> TokenPayload:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    try:
        raw = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return TokenPayload.model_validate(raw)
    except (InvalidTokenError, ValidationError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


def get_account_id(token: Annotated[TokenPayload, Depends(verify_token)]) -> uuid.UUID:
    return token.account_id


# ---------------------------------------------------------------------------
# Shared API key — agent ↔ orchestrator machine-to-machine
# ---------------------------------------------------------------------------

_api_key_header = APIKeyHeader(name="X-Agent-Key", auto_error=False)


def verify_agent_key(
    key: Annotated[str | None, Security(_api_key_header)],
) -> None:
    if key is None or key != settings.agent_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing agent key")
