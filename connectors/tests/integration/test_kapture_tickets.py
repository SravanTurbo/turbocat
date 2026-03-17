"""
Integration tests for the Kapture Tickets connector.

Required env vars:
    KAPTURE_SUBDOMAIN
    KAPTURE_TOKEN
    KAPTURE_CM_ID

Optional:
    KAPTURE_TICKETS_TEMPLATE_ID   (default: 117)

Run:
    pytest tests/integration/test_kapture_tickets.py -s
"""

import logging
from datetime import datetime, timedelta, timezone

from data_connectors.sources.kapture.tickets_connector import KaptureTicketsConnector

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def test_fetch_tickets_today(kapture_config):
    connector = KaptureTicketsConnector(kapture_config)
    tickets = list(connector.extract())
    assert len(tickets) >= 0
    for t in tickets[:3]:
        print(f"  {t['ticket_id']} | {t['status']} | {t['source_type']} | {t['created_at']}")


def test_fetch_tickets_date_range(kapture_config):
    connector = KaptureTicketsConnector(kapture_config)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=3)
    tickets = list(connector.extract(start_time=start, end_time=end))
    assert len(tickets) >= 0
    print(f"  Fetched {len(tickets)} tickets over last 3 days")


def test_schema(kapture_config):
    connector = KaptureTicketsConnector(kapture_config)
    schema = connector.get_schema()
    assert schema.table_name == "kapture_tickets"
    column_names = [col.name for col in schema.columns]
    for required in ("ticket_id", "created_at", "_extracted_at"):
        assert required in column_names


def test_transform_shape(kapture_config):
    """Spot-check that transform produces expected keys and types."""
    connector = KaptureTicketsConnector(kapture_config)
    tickets = list(connector.extract())
    if not tickets:
        return
    t = tickets[0]
    assert "ticket_id" in t
    assert "status" in t
    assert "_extracted_at" in t
    assert isinstance(t["_extracted_at"], datetime)
    # Numeric fields should be int or None, never a raw string
    for field in (
        "reopen_count",
        "dispose_count",
        "agent_interaction_count",
        "customer_interaction_count",
        "total_interaction_count",
    ):
        assert t[field] is None or isinstance(t[field], int), f"{field} should be int|None, got {type(t[field])}"
