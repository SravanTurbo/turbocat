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

    model_config = {
        "json_schema_extra": {
            "example": {
                "source": "razorpay",
                "credentials": {"api_key": "rzp_live_xxx", "api_secret": "your_secret"},
            }
        }
    }


class CreateConnectionRequest(BaseModel):
    account_id: uuid.UUID
    name: str
    source: str
    credentials: dict[str, str]

    model_config = {
        "json_schema_extra": {
            "example": {
                "account_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "name": "Razorpay Production",
                "source": "razorpay",
                "credentials": {"api_key": "rzp_live_xxx", "api_secret": "your_secret"},
            }
        }
    }


class ConnectionResponse(BaseModel):
    connection_id: uuid.UUID
    account_id: uuid.UUID
    name: str
    source: str
    status: str
    last_tested_at: datetime | None

    model_config = {"from_attributes": True}


class TableEntry(BaseModel):
    connector: str
    table_name: str


class TestConnectionResponse(BaseModel):
    success: bool
    error: str | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_test(source: str, credentials: dict[str, str]) -> tuple[ConnectionStatus, str | None]:
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


@router.post(
    "/test",
    response_model=TestConnectionResponse,
    summary="Test credentials",
    response_description="Whether the credentials were accepted by the source API",
    operation_id="testConnection",
)
def test_connection(body: TestConnectionRequest) -> TestConnectionResponse:
    """
    Validate credentials against the source API without saving anything.

    An account with zero records still returns `success: true` — we verify
    that the auth was accepted (no 401/403), not that data exists.

    **Supported sources:** `razorpay`, `kapture`
    """
    status, error = _run_test(body.source, body.credentials)
    return TestConnectionResponse(success=(status == ConnectionStatus.ACTIVE), error=error)


@router.post(
    "/",
    response_model=ConnectionResponse,
    status_code=201,
    summary="Save a connection",
    response_description="The created connection record",
    operation_id="createConnection",
)
def create_connection(body: CreateConnectionRequest, db: Session = Depends(get_db)) -> Connection:
    """
    Save credentials to Secrets Manager and register the connection.

    Always persists regardless of whether the credential test passes —
    `status` reflects the test result (`active` or `failed`).

    Call `POST /{connection_id}/test` to re-test at any time.
    """
    secret_ref = f"orchestrator/{body.account_id}/{body.source}"
    put_secret(secret_ref, body.credentials)

    status, _ = _run_test(body.source, body.credentials)

    connection = Connection(
        account_id=body.account_id,
        name=body.name,
        source=body.source,
        secret_ref=secret_ref,
        status=status,
        last_tested_at=datetime.now(timezone.utc),
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


@router.get(
    "/",
    response_model=list[ConnectionResponse],
    summary="List connections",
    response_description="All connections for the account, newest first",
    operation_id="listConnections",
)
def list_connections(account_id: uuid.UUID | None = None, db: Session = Depends(get_db)) -> list[Connection]:
    """
    List all saved connections, optionally filtered by `account_id`.

    `status` values:
    - `untested` — saved but never tested
    - `active` — last test passed
    - `failed` — last test failed; credentials may be invalid or the source is unreachable
    """
    query = db.query(Connection)
    if account_id is not None:
        query = query.filter(Connection.account_id == account_id)
    return query.order_by(Connection.created_at.desc()).all()


@router.post(
    "/{connection_id}/test",
    response_model=TestConnectionResponse,
    summary="Re-test a saved connection",
    response_description="Whether the stored credentials are still valid",
    operation_id="retestConnection",
)
def test_saved_connection(connection_id: uuid.UUID, db: Session = Depends(get_db)) -> TestConnectionResponse:
    """
    Re-test an existing connection using its stored credentials.

    Updates `status` and `last_tested_at` in place. Use this to verify
    credentials are still valid after a key rotation or source outage.
    """
    connection = db.get(Connection, connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    credentials = get_secret(connection.secret_ref)
    status, error = _run_test(connection.source, credentials)

    connection.status = status
    connection.last_tested_at = datetime.now(timezone.utc)
    db.commit()

    return TestConnectionResponse(success=(status == ConnectionStatus.ACTIVE), error=error)


@router.get(
    "/{connection_id}/schema",
    response_model=list[TableEntry],
    summary="List available entities",
    response_description="Connectors and their destination table names for this source",
    operation_id="listConnectionSchema",
)
def list_schema(connection_id: uuid.UUID, db: Session = Depends(get_db)) -> list[TableEntry]:
    """
    Return all available data entities for a connection.

    For SaaS sources (Razorpay, Kapture) this lists the registered connectors
    and their destination table names — no live API call is made.

    Example response for a Razorpay connection:
    ```json
    [
      {"connector": "razorpay_orders",    "table_name": "razorpay_orders"},
      {"connector": "razorpay_customers", "table_name": "razorpay_customers"}
    ]
    ```
    """
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
        raise HTTPException(status_code=502, detail=f"Failed to fetch schema: {exc}") from exc
