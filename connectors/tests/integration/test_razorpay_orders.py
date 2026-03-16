"""
Integration tests for the Razorpay Orders connector.

Required env vars:
    RAZORPAY_API_KEY
    RAZORPAY_API_SECRET

Optional:
    RAZORPAY_BASE_URL   (defaults to https://api.razorpay.com/v1)

Run:
    RAZORPAY_API_KEY=rzp_test_xxx RAZORPAY_API_SECRET=yyy pytest tests/integration/test_razorpay_orders.py -s
"""

import logging
from datetime import UTC, datetime, timedelta

from data_connectors.sources.razorpay.orders_connector import RazorpayOrdersConnector

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def test_fetch_orders(razorpay_config):
    connector = RazorpayOrdersConnector(razorpay_config)
    orders = list(connector.extract())
    assert len(orders) >= 0  # just verify it runs without error
    for order in orders[:5]:
        print(f"  {order['id']} | ₹{order['amount']} | {order['status']} | {order['created_at']}")


def test_fetch_orders_incremental(razorpay_config):
    connector = RazorpayOrdersConnector(razorpay_config)
    start_time = datetime.now(UTC) - timedelta(days=7)
    end_time = datetime.now(UTC)
    orders = list(connector.extract(start_time=start_time, end_time=end_time))
    assert len(orders) >= 0


def test_schema(razorpay_config):
    connector = RazorpayOrdersConnector(razorpay_config)
    schema = connector.get_schema()
    assert schema.table_name == "razorpay_orders"
    column_names = [col.name for col in schema.columns]
    for required in ("id", "amount", "currency", "status", "created_at", "_extracted_at"):
        assert required in column_names


def test_validate_record(razorpay_config):
    connector = RazorpayOrdersConnector(razorpay_config)
    orders = list(connector.extract())
    if not orders:
        return
    assert connector.validate(orders[0])
