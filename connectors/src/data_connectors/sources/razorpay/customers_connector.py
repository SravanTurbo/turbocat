from datetime import datetime, timezone
from typing import Any, Iterator

from data_connectors.base.connector import BaseSourceConnector
from data_connectors.base.models import ColumnSchema, TableSchema
from data_connectors.common.http_client import RetryableHTTPClient
from data_connectors.sources.razorpay.config import RazorpaySourceConfig


class RazorpayCustomersConnector(BaseSourceConnector):
    """Extract customers from Razorpay API."""

    connector_name = "razorpay_customers"
    config: RazorpaySourceConfig

    def __init__(self, config: RazorpaySourceConfig) -> None:
        super().__init__(config)
        self.endpoint = "/customers"

        base_url = config.base_url
        auth = (config.api_key, config.api_secret.get_secret_value())
        headers = {"Content-Type": "application/json"}
        timeout = config.timeout
        max_retries = config.max_retries

        self.http_client = RetryableHTTPClient(
            base_url=base_url, auth=auth, headers=headers, timeout=timeout, max_retries=max_retries
        )
        self.logger.info("%s connector initialized — base_url=%s", self.connector_name, base_url)

    def extract(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        state: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Extract customers from Razorpay API."""
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

            self.logger.debug("Fetching page - params=%s", params)

            response = self.http_client.get(self.endpoint, params=params)
            data = response.json()
            customers = data.get("items", [])

            self.logger.debug("Received %d customers", len(customers))

            if not customers:
                break

            for customer in customers:
                yield self.transform(customer)

            skip += count
            total_fetched += len(customers)

            if len(customers) < count:
                break

        self.logger.info(
            "Extract complete %s - total_extracted=%d",
            self.connector_name,
            total_fetched,
        )

    def transform(self, record: dict[str, Any]) -> dict[str, Any]:
        """Convert Razorpay customer to our schema."""
        return {
            "id": record["id"],
            "name": record.get("name"),
            "contact": record["contact"],
            "email": record.get("email"),
            "gstin": record.get("gstin"),
            "notes": record.get("notes"),
            "created_at": datetime.fromtimestamp(record["created_at"]),
            "_extracted_at": datetime.now(timezone.utc),
        }

    def get_schema(self) -> TableSchema:
        """Define razorpay_customers table schema."""
        return TableSchema(
            table_name="customers",
            columns=[
                ColumnSchema(name="id", type="string", required=True),
                ColumnSchema(name="name", type="string", required=False),
                ColumnSchema(name="contact", type="string", required=False),
                ColumnSchema(name="email", type="string", required=False),
                ColumnSchema(name="gstin", type="string", required=False),
                ColumnSchema(name="notes", type="string", required=False),
                ColumnSchema(name="created_at", type="datetime", required=True),
                ColumnSchema(name="_extracted_at", type="datetime", required=True),
            ],
        )
