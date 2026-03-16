import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from orchestrator.db import get_db
from orchestrator.models import Agent

router = APIRouter()


@router.post("/{agent_id}/heartbeat")
def heartbeat(agent_id: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, str]:
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "ok"}
