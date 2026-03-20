"""
Entry point — load config, wire up the agent, handle signals.

Shutdown sequence on SIGTERM / SIGINT:
  1. Stop accepting new jobs (cancel poll + heartbeat loops).
  2. Drain any in-flight worker threads (let them finish and report status).
  3. Exit cleanly.
"""

import asyncio
import logging
import signal

from data_connectors.destinations.clickhouse.config import ClickHouseConfig

from agent.agent import Agent
from agent.settings import AgentSettings

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


async def _run() -> None:
    settings = AgentSettings()
    ch_config = ClickHouseConfig()
    agent = Agent(settings, ch_config)

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def _handle_signal() -> None:
        logger.info("Shutdown signal received — draining active jobs before exit")
        stop.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal)

    agent_task = asyncio.create_task(agent.run())

    await stop.wait()

    # Stop poll + heartbeat loops
    agent_task.cancel()
    try:
        await agent_task
    except asyncio.CancelledError:
        pass

    # Wait for in-flight worker tasks to finish
    await agent.drain()


def main() -> None:
    _setup_logging()
    asyncio.run(_run())


if __name__ == "__main__":
    main()
