import os
import socket

import pytest
from dotenv import load_dotenv

from data_connectors.destinations.clickhouse.config import ClickHouseConfig
from data_connectors.sources.razorpay.config import RazorpaySourceConfig

load_dotenv()


@pytest.fixture(scope="session")
def razorpay_config():
    if not os.getenv("RAZORPAY_API_KEY") or not os.getenv("RAZORPAY_API_SECRET"):
        pytest.skip("RAZORPAY_API_KEY and RAZORPAY_API_SECRET required")
    return RazorpaySourceConfig()


@pytest.fixture(scope="session")
def clickhouse_config():
    if not os.getenv("CLICKHOUSE_HOST"):
        pytest.skip("CLICKHOUSE_HOST required")
    host = os.getenv("CLICKHOUSE_HOST", "localhost")
    port = int(os.getenv("CLICKHOUSE_PORT", "9000"))
    try:
        with socket.create_connection((host, port), timeout=2):
            pass
    except OSError:
        pytest.skip(f"ClickHouse not reachable at {host}:{port}")
    return ClickHouseConfig()
