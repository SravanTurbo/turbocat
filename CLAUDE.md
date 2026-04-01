# data-pipelines

Python monorepo. Three components, each with their own `pyproject.toml` managed by Poetry.

```
connectors/   # shared pip-installable connector library
orchestrator/ # FastAPI control plane (our AWS)
agent/        # polling worker (client's AWS account)
```

## Working conventions

**Worktrees** live at `/Users/sra1/Documents/hb/backend/worktrees/{branch-slug}/`. Always work in the worktree for the current branch, not directly in `data-pipelines/`.

**Python version:** 3.13. Strict mypy (`strict = true`) in all components.

**Dependency management:** Poetry. Add deps to the relevant `pyproject.toml`, run `poetry lock && poetry install` inside that component directory.

**Makefile:** common targets at repo root — `make setup`, `make test`, `make lint`, `make migrate` (delegates to the right component).

## Architecture in one line

APScheduler (orchestrator) fires jobs → agent polls `GET /jobs/pending` → executor runs connector → writes to ClickHouse in client's AWS account. Raw data never touches our infra.

See `README.md` for full architecture and `TODO.md` for known debt.

## Component CLAUDE.md files

Each subdirectory has its own `CLAUDE.md` with component-specific context. Read that before touching files in the component.
