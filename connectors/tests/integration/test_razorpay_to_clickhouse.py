"""
End-to-end integration test: Razorpay Orders → ClickHouse.

Credentials are loaded exclusively from environment variables — never hardcoded.

Required env vars (set in .env or export in your shell):
    RAZORPAY_API_KEY
    RAZORPAY_API_SECRET
    CLICKHOUSE_HOST

Optional env vars (all have defaults):
    RAZORPAY_BASE_URL       (default: https://api.razorpay.com/v1)
    CLICKHOUSE_PORT         (default: 9000)
    CLICKHOUSE_DATABASE     (default: default)
    CLICKHOUSE_USER         (default: default)
    CLICKHOUSE_PASSWORD     (default: empty)
    CLICKHOUSE_SECURE       (default: false)

Usage:
    RAZORPAY_API_KEY=rzp_test_xxx \\
    RAZORPAY_API_SECRET=yyy \\
    CLICKHOUSE_HOST=localhost \\
    CLICKHOUSE_PASSWORD=secret \\
    python -m pytest tests/integration/test_razorpay_to_clickhouse.py -s
"""

import logging
import sys
from datetime import datetime, timedelta

from data_connectors.destinations.clickhouse import ClickHouseDestination
from data_connectors.destinations.clickhouse.config import ClickHouseConfig
from data_connectors.sources.razorpay import RazorpayOrdersConnector
from data_connectors.sources.razorpay.config import RazorpaySourceConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def test_full_pipeline() -> bool:
    """Test complete Razorpay → ClickHouse sync."""

    print("\n" + "=" * 70)
    print("Testing Complete Pipeline: Razorpay Orders → ClickHouse")
    print("=" * 70 + "\n")

    # Both configs load from environment variables.
    # Raises ValidationError immediately if a required var is missing.
    source_config = RazorpaySourceConfig()
    destination_config = ClickHouseConfig()

    print("1. Initializing connectors...")
    source = RazorpayOrdersConnector(source_config)
    destination = ClickHouseDestination(destination_config)
    print("   ✓ Connectors initialized\n")

    print("2. Starting sync (last 30 days)...")
    print("-" * 70)

    result = source.sync(
        destination=destination,
        start_time=datetime.utcnow() - timedelta(days=30),
        end_time=datetime.utcnow(),
    )

    print("-" * 70)
    print("\n3. Sync completed!")
    print(f"   {result.summary()}\n")

    print("4. Verifying data in ClickHouse...")
    print("-" * 70)

    count_result = destination.client.execute("SELECT count() FROM razorpay_orders")
    total_count = count_result[0][0]
    print(f"   Total orders in ClickHouse: {total_count}")

    if total_count > 0:
        sample_result = destination.client.execute(
            """
            SELECT
                id,
                amount,
                currency,
                status,
                created_at
            FROM razorpay_orders
            ORDER BY created_at DESC
            LIMIT 5
        """
        )

        print("\n   Sample orders (most recent):")
        for row in sample_result:
            order_id, amount, currency, status, created_at = row
            print(f"     {order_id} | ₹{amount} {currency} | {status} | {created_at}")

        stats_result = destination.client.execute(
            """
            SELECT
                status,
                count() as count,
                sum(amount) as total_amount
            FROM razorpay_orders
            GROUP BY status
        """
        )

        print("\n   Statistics by status:")
        for row in stats_result:
            status, count, total = row
            print(f"     {status:12s} | Count: {count:3d} | Total: ₹{total:.2f}")

    print("\n" + "=" * 70)
    if result.is_success():
        print("✓ TEST PASSED - Pipeline working end-to-end!")
    else:
        print("✗ TEST FAILED - Check logs above")
    print("=" * 70 + "\n")

    return result.is_success()


if __name__ == "__main__":
    success = test_full_pipeline()
    sys.exit(0 if success else 1)
