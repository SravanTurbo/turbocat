"""
Integration tests for the Razorpay Customers connector.

Required env vars:
    RAZORPAY_API_KEY
    RAZORPAY_API_SECRET

Optional:
    RAZORPAY_BASE_URL   (defaults to https://api.razorpay.com/v1)

Run:
    RAZORPAY_API_KEY=rzp_test_xxx RAZORPAY_API_SECRET=yyy pytest tests/integration/test_razorpay_customers.py -s

Note: The Razorpay customers API does not support date-range filtering, so this
connector always does a full refresh. start_time/end_time params are accepted but
have no effect on what the API returns.
"""

import logging

from data_connectors.sources.razorpay.customers_connector import RazorpayCustomersConnector

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def test_fetch_customers(razorpay_config):
    connector = RazorpayCustomersConnector(razorpay_config)
    customers = list(connector.extract())
    assert len(customers) >= 0
    for customer in customers[:5]:
        print(f"  {customer['id']} | {customer['name']} | {customer['contact']} | {customer['email']}")


def test_schema(razorpay_config):
    connector = RazorpayCustomersConnector(razorpay_config)
    schema = connector.get_schema()
    assert schema.table_name == "customers"
    column_names = [col.name for col in schema.columns]
    for required in ("id", "created_at", "_extracted_at"):
        assert required in column_names
    # contact must be string, not datetime
    contact_col = next(col for col in schema.columns if col.name == "contact")
    assert contact_col.type == "string"


def test_validate_record(razorpay_config):
    connector = RazorpayCustomersConnector(razorpay_config)
    customers = list(connector.extract())
    if not customers:
        return
    assert connector.validate(customers[0])
