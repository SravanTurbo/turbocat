import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from orchestrator.db import get_db
from orchestrator.models import Connection, ConnectionStatus
from orchestrator.secrets import get_secret, put_secret

router = APIRouter()


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

    model_config = {"from_attributes": True}


def _get_source_client(source: str, credentials: dict[str, str]):  # type: ignore[no-untyped-def]
    """Instantiate a source client using the registry. Raises if source is unknown."""
    # TODO: replace with connector registry lookup once registry is built
    # from data_connectors.registry import get_source_client
    # return get_source_client(source, credentials)
    raise NotImplementedError(f"Connector registry not yet implemented: {source}")


@router.post("/test")
def test_connection(body: TestConnectionRequest) -> dict[str, object]:
    """Validate credentials against the source. Never persists anything."""
    try:
        client = _get_source_client(body.source, body.credentials)
        client.test_connection()
        return {"success": True}
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Connector registry not yet implemented")
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/", response_model=ConnectionResponse, status_code=201)
def create_connection(body: CreateConnectionRequest, db: Session = Depends(get_db)) -> Connection:
    """Save credentials to Secrets Manager and register the connection."""
    secret_ref = f"orchestrator/{body.account_id}/{body.source}"
    put_secret(secret_ref, body.credentials)

    connection = Connection(
        account_id=body.account_id,
        source=body.source,
        secret_ref=secret_ref,
        status=ConnectionStatus.ACTIVE,
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


class TableEntry(BaseModel):
    connector: str  # e.g. "razorpay_orders"
    table_name: str  # destination ClickHouse table e.g. "orders"


@router.get("/{connection_id}/schema", response_model=list[TableEntry])
def list_schema(connection_id: uuid.UUID, db: Session = Depends(get_db)) -> list[TableEntry]:
    """Return available connectors and their destination table names for a source."""
    connection = db.get(Connection, connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    credentials = get_secret(connection.secret_ref)
    try:
        client = _get_source_client(connection.source, credentials)
        # list_tables() returns [{"connector": "razorpay_orders", "table_name": "orders"}, ...]
        return [TableEntry(**entry) for entry in client.list_tables()]
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Connector registry not yet implemented")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch schema: {e}") from e
