import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from orchestrator.db import get_db
from orchestrator.models import Connection, Pipeline
from orchestrator.scheduler import deregister_pipeline, register_pipeline

router = APIRouter()


class PipelineTableConfig(BaseModel):
    connector: str  # specific connector class e.g. "razorpay_orders"
    table_name: str  # display label, matches connector schema
    schedule: str
    params: dict[str, Any] = {}


class BulkCreateRequest(BaseModel):
    account_id: uuid.UUID
    agent_id: uuid.UUID
    connection_id: uuid.UUID
    tables: list[PipelineTableConfig]


class PipelineResponse(BaseModel):
    pipeline_id: uuid.UUID
    account_id: uuid.UUID
    agent_id: uuid.UUID
    connection_id: uuid.UUID
    connector: str
    table_name: str
    schedule: str
    params: dict[str, Any]
    is_active: bool

    model_config = {"from_attributes": True}


@router.post("/bulk", response_model=list[PipelineResponse], status_code=201)
def bulk_create_pipelines(body: BulkCreateRequest, db: Session = Depends(get_db)) -> list[Pipeline]:
    connection = db.get(Connection, body.connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    pipelines = []
    for table in body.tables:
        pipeline = Pipeline(
            account_id=body.account_id,
            agent_id=body.agent_id,
            connection_id=body.connection_id,
            connector=table.connector,
            table_name=table.table_name,
            schedule=table.schedule,
            params=table.params,
        )
        db.add(pipeline)
        pipelines.append(pipeline)

    db.commit()
    for p in pipelines:
        db.refresh(p)
        register_pipeline(p)

    return pipelines


@router.get("/{pipeline_id}", response_model=PipelineResponse)
def get_pipeline(pipeline_id: uuid.UUID, db: Session = Depends(get_db)) -> Pipeline:
    pipeline = db.get(Pipeline, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


@router.get("/", response_model=list[PipelineResponse])
def list_pipelines(account_id: uuid.UUID | None = None, db: Session = Depends(get_db)) -> list[Pipeline]:
    q = db.query(Pipeline)
    if account_id:
        q = q.filter(Pipeline.account_id == account_id)
    return q.all()


@router.patch("/{pipeline_id}/deactivate", response_model=PipelineResponse)
def deactivate_pipeline(pipeline_id: uuid.UUID, db: Session = Depends(get_db)) -> Pipeline:
    pipeline = db.get(Pipeline, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    pipeline.is_active = False
    db.commit()
    deregister_pipeline(pipeline_id)
    return pipeline
