"""
Main agent loop — poll for jobs, dispatch workers, send heartbeats.

Concurrency model:
  - asyncio event loop on the main thread drives the poll and heartbeat loops.
  - Each job is dispatched as an asyncio Task that runs the sync work inside
    a ThreadPoolExecutor thread (connectors are synchronous + I/O-bound).
  - A Semaphore caps concurrent workers at max_workers. The poll loop only
    fetches jobs when there is capacity — it does not claim more jobs than it
    can immediately start.
  - Active tasks are tracked in a set so graceful shutdown can drain them
    before the process exits.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from data_connectors.destinations.clickhouse.config import ClickHouseConfig

from agent.client import JobPayload, OrchestratorClient
from agent.executor import run_job
from agent.settings import AgentSettings

logger = logging.getLogger(__name__)


class Agent:
    def __init__(self, settings: AgentSettings, ch_config: ClickHouseConfig) -> None:
        self._settings = settings
        self._ch_config = ch_config
        self._client = OrchestratorClient(
            settings.orchestrator_url, settings.id, settings.api_key
        )
        self._semaphore = asyncio.Semaphore(settings.max_workers)
        self._executor = ThreadPoolExecutor(
            max_workers=settings.max_workers, thread_name_prefix="worker"
        )
        self._active_tasks: set[asyncio.Task[None]] = set()

    async def run(self) -> None:
        logger.info(
            "Agent %s started — max_workers=%d poll_interval=%ds heartbeat_interval=%ds",
            self._settings.id,
            self._settings.max_workers,
            self._settings.poll_interval,
            self._settings.heartbeat_interval,
        )
        await asyncio.gather(
            self._poll_loop(),
            self._heartbeat_loop(),
        )

    async def drain(self) -> None:
        """Wait for all in-flight worker tasks to finish. Called on shutdown."""
        if not self._active_tasks:
            return
        logger.info(
            "Draining %d active job(s) before shutdown...", len(self._active_tasks)
        )
        await asyncio.gather(*self._active_tasks, return_exceptions=True)
        logger.info("All jobs drained.")

    async def _poll_loop(self) -> None:
        while True:
            available = self._settings.max_workers - len(self._active_tasks)
            if available > 0:
                try:
                    jobs = await asyncio.to_thread(self._client.get_pending_jobs)
                    for job in jobs:
                        self._spawn(job)
                except Exception as exc:
                    logger.warning("Poll error: %s", exc)
            await asyncio.sleep(self._settings.poll_interval)

    def _spawn(self, job: JobPayload) -> None:
        task = asyncio.create_task(self._run_job(job), name=f"job-{job.job_id}")
        self._active_tasks.add(task)
        task.add_done_callback(self._active_tasks.discard)

    async def _run_job(self, job: JobPayload) -> None:
        async with self._semaphore:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                self._executor,
                run_job,
                job,
                self._ch_config,
                self._client,
            )

    async def _heartbeat_loop(self) -> None:
        while True:
            try:
                await asyncio.to_thread(self._client.heartbeat)
                logger.debug("Heartbeat sent")
            except Exception as exc:
                logger.warning("Heartbeat failed: %s", exc)
            await asyncio.sleep(self._settings.heartbeat_interval)
