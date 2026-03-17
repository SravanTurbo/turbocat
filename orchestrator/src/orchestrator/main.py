from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from orchestrator.scheduler import load_schedules, scheduler
from orchestrator.routes import agents, connections, jobs, pipelines
from orchestrator.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    app.state.engine = engine
    app.state.session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    scheduler.start()
    load_schedules(app.state.session_factory)
    yield
    scheduler.shutdown()
    engine.dispose()


app = FastAPI(title="Orchestrator", lifespan=lifespan)

app.include_router(connections.router, prefix="/connections", tags=["connections"])
app.include_router(pipelines.router, prefix="/pipelines", tags=["pipelines"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(agents.router, prefix="/agents", tags=["agents"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
