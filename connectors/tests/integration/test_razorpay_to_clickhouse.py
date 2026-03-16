"""
End-to-end integration test: Razorpay Orders → ClickHouse.

Required env vars:
    RAZORPAY_API_KEY
    RAZORPAY_API_SECRET
    CLICKHOUSE_HOST

Optional:
    RAZORPAY_BASE_URL       (default: https://api.razorpay.com/v1)
    CLICKHOUSE_PORT         (default: 9000)
    CLICKHOUSE_DATABASE     (default: default)
    CLICKHOUSE_USER         (default: default)
    CLICKHOUSE_PASSWORD     (default: empty)
    CLICKHOUSE_SECURE       (default: false)

Run:
    RAZORPAY_API_KEY=rzp_test_xxx RAZORPAY_API_SECRET=yyy CLICKHOUSE_HOST=localhost \\
    pytest tests/integration/test_razorpay_to_clickhouse.py -s
"""

import logging
from datetime import datetime, timedelta

from data_connectors.destinations.clickhouse import ClickHouseDestination
from data_connectors.sources.razorpay import RazorpayOrdersConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def test_full_pipeline(razorpay_config, clickhouse_config):
    source = RazorpayOrdersConnector(razorpay_config)
    destination = ClickHouseDestination(clickhouse_config)

    result = source.sync(
        destination=destination,
        start_time=datetime.utcnow() - timedelta(days=30),
        end_time=datetime.utcnow(),
    )

    print(result.summary())
    assert result.is_success(), f"Sync failed: {result.error}"

    count = destination.client.execute("SELECT count() FROM razorpay_orders")[0][0]
    assert count >= 0
    print(f"Total orders in ClickHouse: {count}")
