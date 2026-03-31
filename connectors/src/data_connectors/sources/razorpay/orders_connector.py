from datetime import datetime, timezone
from typing import Any, Iterator

from data_connectors.base.connector import BaseSourceConnector
from data_connectors.base.models import ColumnSchema, TableSchema
from data_connectors.common.http_client import RetryableHTTPClient
from data_connectors.sources.razorpay.config import RazorpaySourceConfig


class RazorpayOrdersConnector(BaseSourceConnector):
    """Extract orders from Razorpay API."""

    connector_name = "razorpay_orders"
    config: RazorpaySourceConfig

    def __init__(self, config: RazorpaySourceConfig) -> None:
        super().__init__(config)
        self.endpoint = "/orders"

        base_url = config.base_url
        auth = (config.api_key, config.api_secret.get_secret_value())
        headers = {"Content-Type": "application/json"}
        timeout = config.timeout
        max_retries = config.max_retries
        self.http_client = RetryableHTTPClient(
            base_url=base_url,
            auth=auth,
            headers=headers,
            timeout=timeout,
            max_retries=max_retries,
        )
        self.logger.info(
            "%s connector initialized — base_url=%s", self.connector_name, base_url
        )

    def test_connection(self) -> None:
        """Fetch one order to confirm credentials are valid."""
        self.http_client.get(self.endpoint, params={"count": 1})

    def extract(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        state: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Fetch orders from Razorpay with pagination."""
        skip = 0
        count = 100
        total_fetched = 0

        self.logger.info(
            "Starting extract for %s - start_time: %s, end_time: %s",
            self.connector_name,
            start_time,
            end_time,
        )

        while True:
            params = {"skip": skip, "count": count}

            if start_time:
                params["from"] = int(start_time.timestamp())

            if end_time:
                params["to"] = int(end_time.timestamp())

            self.logger.debug("Fetching page - params=%s", params)

            response = self.http_client.get(self.endpoint, params=params)
            data = response.json()
            orders = data.get("items", [])

            self.logger.debug(f"Received {len(orders)} orders")

            if not orders:
                break

            for order in orders:
                yield self.transform(order)

            skip += count
            total_fetched += len(orders)

            if len(orders) < count:
                break

        self.logger.info(
            "Extract complete %s - total_extracted=%d",
            self.connector_name,
            total_fetched,
        )

    def transform(self, record: dict[str, Any]) -> dict[str, Any]:
        """
        Convert Razorpay API response to our schema format.

        Transformations:
        - amount: paise → rupees (divide by 100)
        - created_at: UNIX timestamp → datetime
        - Add _extracted_at for tracking

        Args:
            order: Raw order dict from Razorpay API

        Returns:
            Transformed order dict matching our schema
        """

        def _none_to_zero(value: Any) -> float:
            return float(value) if value is not None else 0.0

        return {
            "id": record["id"],
            "amount": _none_to_zero(record.get("amount"))
            / 100,  # Convert paise to rupees
            "amount_paid": _none_to_zero(record.get("amount_paid")) / 100,
            "amount_due": _none_to_zero(record.get("amount_due")) / 100,
            "currency": record["currency"],
            "receipt": record.get("receipt"),
            "status": record["status"],
            "created_at": datetime.fromtimestamp(record["created_at"]),
            "_extracted_at": datetime.now(timezone.utc),  # When we fetched it
        }

    def get_schema(self) -> TableSchema:
        """Define razorpay_orders table schema."""
        return TableSchema(
            table_name="razorpay_orders",
            columns=[
                ColumnSchema(name="id", type="string", required=True),
                ColumnSchema(name="amount", type="float", required=True),
                ColumnSchema(name="amount_paid", type="float", required=False),
                ColumnSchema(name="amount_due", type="float", required=False),
                ColumnSchema(name="currency", type="string", required=True),
                ColumnSchema(name="receipt", type="string", required=False),
                ColumnSchema(name="status", type="string", required=True),
                ColumnSchema(name="created_at", type="datetime", required=True),
                ColumnSchema(name="_extracted_at", type="datetime", required=True),
            ],
        )
