# Build context: monorepo root
FROM python:3.13-slim AS builder

WORKDIR /workspace

RUN pip install --no-cache-dir poetry

# Copy local path dependency first
COPY connectors/ /workspace/connectors/

# Copy orchestrator source
COPY orchestrator/ /workspace/orchestrator/

WORKDIR /workspace/orchestrator

RUN poetry config virtualenvs.in-project true && \
    poetry install --without dev --no-interaction

# Runtime stage
FROM python:3.13-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates tzdata && \
    rm -rf /var/lib/apt/lists/*

# Copy connectors source (needed because data-connectors is a develop/editable install)
COPY --from=builder /workspace/connectors /workspace/connectors

# Copy orchestrator + venv
COPY --from=builder /workspace/orchestrator /app

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "orchestrator.main:app", "--host", "0.0.0.0", "--port", "8000"]
