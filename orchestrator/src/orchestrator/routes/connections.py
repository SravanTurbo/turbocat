import uuid
from datetime import datetime, timezone

from data_connectors.registry import build_from_credentials, get_schemas_for_source
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from orchestrator.db import get_db
from orchestrator.models import Connection, ConnectionStatus
from orchestrator.secrets import get_secret, put_secret

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class TestConnectionRequest(BaseModel):
    source: str
    credentials: dict[str, str]


class CreateConnectionRequest(BaseModel):
    account_id: uuid.UUID
    source: str
    credentials: dict[str, str]


class ConnectionResponse(BaseModel):
    connection_id: uuid.UUID
    account_id: uuid.UUID
    source: str
    status: str
    last_tested_at: datetime | None

    model_config = {"from_attributes": True}


class TableEntry(BaseModel):
    connector: str
    table_name: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_test(
    source: str, credentials: dict[str, str]
) -> tuple[ConnectionStatus, str | None]:
    """
    Attempt a live connection test for the given source and credentials.

    An HTTP 200 with empty results is a pass — we only care that the server
    accepted our auth (no 401/403), matching how Fivetran tests REST sources.

    Returns (ConnectionStatus.ACTIVE, None) on success or
            (ConnectionStatus.FAILED, error_message) on failure.
    Raises HTTPException(400) if the source name is unknown.
    """
    try:
        connector = build_from_credentials(source, credentials)
        connector.test_connection()
        return ConnectionStatus.ACTIVE, None
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        return ConnectionStatus.FAILED, str(exc)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/test")
def test_connection(body: TestConnectionRequest) -> dict[str, object]:
    """
    Validate credentials against the source API. Never persists anything.

    An empty account (no records yet) still returns success — we verify
    that auth was accepted, not that data exists.
    """
    status, error = _run_test(body.source, body.credentials)
    if status == ConnectionStatus.ACTIVE:
        return {"success": True}
    return {"success": False, "error": error}


@router.post("/", response_model=ConnectionResponse, status_code=201)
def create_connection(
    body: CreateConnectionRequest, db: Session = Depends(get_db)
) -> Connection:
    """
    Save credentials to Secrets Manager and register the connection.

    Always persists regardless of whether the credential test passes.
    status is set to 'active' or 'failed' based on the test result.
    """
    secret_ref = f"orchestrator/{body.account_id}/{body.source}"
    put_secret(secret_ref, body.credentials)

    status, _ = _run_test(body.source, body.credentials)

    connection = Connection(
        account_id=body.account_id,
        source=body.source,
        secret_ref=secret_ref,
        status=status,
        last_tested_at=datetime.now(timezone.utc),
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


@router.get("/", response_model=list[ConnectionResponse])
def list_connections(
    account_id: uuid.UUID | None = None, db: Session = Depends(get_db)
) -> list[Connection]:
    """
    List all connections, optionally filtered by account_id.

    Each record includes status (untested | active | failed) and last_tested_at.
    """
    query = db.query(Connection)
    if account_id is not None:
        query = query.filter(Connection.account_id == account_id)
    return query.order_by(Connection.created_at.desc()).all()


@router.post("/{connection_id}/test")
def test_saved_connection(
    connection_id: uuid.UUID, db: Session = Depends(get_db)
) -> dict[str, object]:
    """
    Re-test an existing connection using its stored credentials.

    Updates status and last_tested_at in place.
    """
    connection = db.get(Connection, connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    credentials = get_secret(connection.secret_ref)
    status, error = _run_test(connection.source, credentials)

    connection.status = status
    connection.last_tested_at = datetime.now(timezone.utc)
    db.commit()

    if status == ConnectionStatus.ACTIVE:
        return {"success": True}
    return {"success": False, "error": error}


@router.get("/{connection_id}/schema", response_model=list[TableEntry])
def list_schema(
    connection_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[TableEntry]:
    """Return available connectors and their destination table names for a source."""
    connection = db.get(Connection, connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    credentials = get_secret(connection.secret_ref)
    try:
        entries = get_schemas_for_source(connection.source, credentials)
        return [TableEntry(**entry) for entry in entries]
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Failed to fetch schema: {exc}"
        ) from exc
