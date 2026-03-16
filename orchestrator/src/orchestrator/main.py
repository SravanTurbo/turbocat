from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from orchestrator.scheduler import load_schedules, scheduler
from orchestrator.routes import agents, connections, jobs, pipelines


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    scheduler.start()
    load_schedules()
    yield
    scheduler.shutdown()


app = FastAPI(title="Orchestrator", lifespan=lifespan)

app.include_router(connections.router, prefix="/connections", tags=["connections"])
app.include_router(pipelines.router, prefix="/pipelines", tags=["pipelines"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(agents.router, prefix="/agents", tags=["agents"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
