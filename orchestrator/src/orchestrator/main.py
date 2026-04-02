from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from orchestrator.auth import verify_agent_key, verify_token
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
    app.state.session_factory = sessionmaker(
        bind=engine, autocommit=False, autoflush=False
    )

    scheduler.start()
    load_schedules(app.state.session_factory)
    yield
    scheduler.shutdown()
    engine.dispose()


app = FastAPI(
    title="Heartbeat Orchestrator",
    version="0.1.0",
    description=(
        "Control plane for the Heartbeat data pipeline system. "
        "Manages source connections, pipeline schedules, and job dispatch to client agents."
    ),
    lifespan=lifespan,
    # Disable the default Swagger UI — we serve Scalar instead
    docs_url=None,
    redoc_url=None,
)

_origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_jwt = [Depends(verify_token)]
_agent_key = [Depends(verify_agent_key)]
app.include_router(
    connections.router, prefix="/connections", tags=["connections"], dependencies=_jwt
)
app.include_router(
    pipelines.router, prefix="/pipelines", tags=["pipelines"], dependencies=_jwt
)
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"], dependencies=_agent_key)
app.include_router(
    agents.router, prefix="/agents", tags=["agents"], dependencies=_agent_key
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/docs", include_in_schema=False)
def scalar_docs() -> HTMLResponse:
    """Serve Scalar API reference — CDN-loaded, no extra dependency."""
    return HTMLResponse(content=f"""<!doctype html>
<html>
<head>
  <title>{app.title} — API Reference</title>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
</head>
<body>
  <script
    id="api-reference"
    data-url="/openapi.json"
    data-configuration='{{"theme":"purple"}}'
  ></script>
  <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
</body>
</html>""")
