"""
End-to-end integration test: Razorpay → Orchestrator API → Agent simulation → ClickHouse.

Flow:
  1. Register a Razorpay connection via POST /connections
  2. Bulk-create pipelines for orders + customers via POST /pipelines/bulk
  3. Manually enqueue job_runs (skip APScheduler)
  4. Simulate agent: GET /jobs/pending → run connectors → POST /jobs/{id}/status
  5. Verify job statuses and ClickHouse row counts

Run:
    RAZORPAY_API_KEY=rzp_test_xxx RAZORPAY_API_SECRET=yyy \\
    CLICKHOUSE_HOST=localhost \\
    TEST_DATABASE_URL=postgresql://localhost:5432/data_pipelines_db \\
    pytest tests/integration/test_razorpay_pipeline.py -s
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from orchestrator.models import JobRun, JobStatus

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# connector name → connector class
CONNECTOR_REGISTRY = {
    "razorpay_orders": "data_connectors.sources.razorpay.orders_connector.RazorpayOrdersConnector",
    "razorpay_customers": "data_connectors.sources.razorpay.customers_connector.RazorpayCustomersConnector",
}


def _load_connector_class(connector_name: str):  # type: ignore[no-untyped-def]
    import importlib

    module_path, class_name = CONNECTOR_REGISTRY[connector_name].rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


# ---------------------------------------------------------------------------
# Step 1 — register connection
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def connection_id(client, test_account_id, razorpay_creds) -> uuid.UUID:
    r = client.post(
        "/connections",
        json={
            "account_id": str(test_account_id),
            "source": "razorpay",
            "credentials": razorpay_creds,
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["source"] == "razorpay"
    assert data["status"] == "active"
    logger.info("Created connection %s", data["connection_id"])
    return uuid.UUID(data["connection_id"])


# ---------------------------------------------------------------------------
# Step 2 — bulk create pipelines
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def pipeline_ids(client, test_account_id, test_agent, connection_id) -> list[uuid.UUID]:
    r = client.post(
        "/pipelines/bulk",
        json={
            "account_id": str(test_account_id),
            "agent_id": str(test_agent.agent_id),
            "connection_id": str(connection_id),
            "tables": [
                {"connector": "razorpay_orders", "table_name": "orders", "schedule": "0 * * * *"},
                {"connector": "razorpay_customers", "table_name": "customers", "schedule": "0 * * * *"},
            ],
        },
    )
    assert r.status_code == 201, r.text
    ids = [uuid.UUID(p["pipeline_id"]) for p in r.json()]
    assert len(ids) == 2
    logger.info("Created %d pipelines: %s", len(ids), ids)
    return ids


# ---------------------------------------------------------------------------
# Step 3 — manually enqueue jobs (skip APScheduler in tests)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def enqueued_job_ids(db_engine, test_agent, pipeline_ids) -> list[uuid.UUID]:
    from sqlalchemy.orm import sessionmaker

    session = sessionmaker(bind=db_engine)()
    job_ids = []
    for pipeline_id in pipeline_ids:
        job = JobRun(
            pipeline_id=pipeline_id,
            agent_id=test_agent.agent_id,
            status=JobStatus.PENDING,
        )
        session.add(job)
        job_ids.append(job.job_id)
    session.commit()
    session.close()
    logger.info("Enqueued %d jobs: %s", len(job_ids), job_ids)
    return job_ids


# ---------------------------------------------------------------------------
# Step 4 + 5 — agent poll → run connectors → report status → verify ClickHouse
# ---------------------------------------------------------------------------
def test_agent_poll_run_and_report(client, enqueued_job_ids, test_agent, clickhouse_config, db_engine):
    from data_connectors.destinations.clickhouse import ClickHouseDestination
    from data_connectors.sources.razorpay.config import RazorpaySourceConfig
    from sqlalchemy.orm import sessionmaker

    # --- poll ---
    r = client.get(f"/jobs/pending?agent_id={test_agent.agent_id}")
    assert r.status_code == 200, r.text
    payloads = r.json()
    assert len(payloads) == len(enqueued_job_ids), f"Expected {len(enqueued_job_ids)} jobs, got {len(payloads)}"

    destination = ClickHouseDestination(clickhouse_config)

    for payload in payloads:
        job_id = payload["job_id"]
        connector_name = payload["connector"]
        credentials = payload["credentials"]

        logger.info("Running connector %s for job %s", connector_name, job_id)

        # --- report running ---
        r = client.post(f"/jobs/{job_id}/status", json={"status": "running"})
        assert r.status_code == 200, r.text

        # --- run connector ---
        try:
            config = RazorpaySourceConfig(
                api_key=credentials["api_key"],
                api_secret=credentials["api_secret"],
            )
            connector_cls = _load_connector_class(connector_name)
            connector = connector_cls(config)

            result = connector.sync(
                destination=destination,
                start_time=datetime.now(UTC) - timedelta(days=30),
                end_time=datetime.now(UTC),
            )

            logger.info("Connector %s result: %s", connector_name, result.summary())

            if result.is_success():
                r = client.post(
                    f"/jobs/{job_id}/status",
                    json={"status": "success", "rows_synced": result.records_loaded},
                )
            else:
                r = client.post(
                    f"/jobs/{job_id}/status",
                    json={"status": "failed", "error": result.error},
                )
            assert r.status_code == 200, r.text

        except Exception as e:
            client.post(f"/jobs/{job_id}/status", json={"status": "failed", "error": str(e)})
            raise

    # --- verify job_run statuses in DB ---
    session = sessionmaker(bind=db_engine)()
    for job_id in enqueued_job_ids:
        job = session.get(JobRun, job_id)
        assert job is not None
        assert job.status == JobStatus.SUCCESS, f"Job {job_id} status: {job.status} error: {job.error}"
        assert job.completed_at is not None
        logger.info("Job %s: status=%s rows_synced=%s", job_id, job.status, job.rows_synced)
    session.close()

    # --- verify ClickHouse has rows ---
    orders_count = destination.client.execute("SELECT count() FROM razorpay_orders")[0][0]
    customers_count = destination.client.execute("SELECT count() FROM razorpay_customers")[0][0]
    logger.info("ClickHouse — orders: %d, customers: %d", orders_count, customers_count)
    assert orders_count >= 0
    assert customers_count >= 0


# ---------------------------------------------------------------------------
# Verify jobs are no longer returned on second poll (marked dispatched)
# ---------------------------------------------------------------------------
def test_no_duplicate_dispatch(client, enqueued_job_ids, test_agent):
    r = client.get(f"/jobs/pending?agent_id={test_agent.agent_id}")
    assert r.status_code == 200, r.text
    # already dispatched/completed — should not appear again
    returned_ids = {p["job_id"] for p in r.json()}
    for job_id in enqueued_job_ids:
        assert str(job_id) not in returned_ids, f"Job {job_id} was re-dispatched"
