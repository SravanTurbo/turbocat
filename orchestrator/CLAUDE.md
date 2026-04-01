# orchestrator

FastAPI control plane. Manages pipeline config, job dispatch, connection credentials, and APScheduler cron jobs.

## Source layout

```
src/orchestrator/
├── main.py          # FastAPI app + lifespan (engine, session_factory, scheduler)
├── settings.py      # Settings(BaseSettings) — reads .env.{APP_ENV} or AWS SSM
├── db.py            # get_db(request) dependency — pulls session_factory from app.state
├── auth.py          # JWT verification: verify_token, get_account_id dependencies
├── scheduler.py     # APScheduler instance + load_schedules, register_pipeline, deregister_pipeline
├── secrets.py       # get_secret / put_secret via AWS Secrets Manager
├── models/          # SQLAlchemy ORM: Agent, Connection, Pipeline, JobRun (schema=pipeline_schema)
└── routes/
    ├── connections.py  # CRUD for source connections
    ├── pipelines.py    # CRUD for pipelines + APScheduler registration
    ├── jobs.py         # GET /pending (claim with FOR UPDATE SKIP LOCKED), POST /{id}/status
    └── agents.py       # POST /{id}/heartbeat
```

## Key patterns

**DB access:** `db: Session = Depends(get_db)` — session_factory lives in `app.state`.

**Auth:** all routes except `/health` and `/docs` require a Bearer JWT. Use `Depends(verify_token)` at the router level in `main.py`. Use `account_id: uuid.UUID = Depends(get_account_id)` inside any route that needs to scope data to the caller.

**account_id scoping:** `account_id` comes from the JWT, never from request body or query params. Always filter DB queries by `account_id` from the token. Always verify ownership (`resource.account_id != account_id → 403`) before returning or mutating a record.

**Secrets:** credentials are stored in AWS Secrets Manager under `orchestrator/{account_id}/{source}`. Fetched per job at dispatch time, never cached to disk.

**APScheduler:** runs in-process. `register_pipeline` adds a cron job; `deregister_pipeline` removes it. Called from route handlers after DB commit.

## Settings

Settings in `Settings(BaseSettings)`. Fields loaded from `.env.local` by default (APP_ENV=local), or from AWS SSM when `CONFIG_PROVIDER=aws`.

Current fields: `database_url`, `aws_region`, `job_poll_interval_seconds`, `jwt_secret`, `jwt_algorithm`, `cors_origins`.

## Adding a new route

1. Add handler to the relevant `routes/*.py` file.
2. Use `Depends(get_account_id)` if the route is account-scoped.
3. Add ownership check if the route accesses a resource by ID.
4. No need to touch `main.py` unless adding a new router prefix.

## Migrations

Alembic. Run `make migrate` from the orchestrator directory. Migration files in `alembic/versions/`.
