import time
from datetime import datetime, timezone
from typing import Any, Iterator

import requests
from requests.auth import HTTPBasicAuth

from data_connectors.base.connector import BaseSourceConnector
from data_connectors.base.models import ColumnSchema, TableSchema


class RazorpayOrdersConnector(BaseSourceConnector):
    """Extract orders from Razorpay API."""

    connector_name = "razorpay_orders"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)

        source_config: dict[str, Any] = config.get("source_config") or {}
        self.api_key: str = source_config.get("api_key") or ""
        self.api_secret: str = source_config.get("api_secret") or ""
        self.base_url: str = source_config.get("base_url") or ""

        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(self.api_key, self.api_secret)

        self.session.headers.update({"Content-Type": "application/json"})

        self.logger.info(f"{self.connector_name} connector initialized")

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

            try:
                response = self.session.get(f"{self.base_url}/orders", params=params, timeout=10)

                if response.status_code == 429:
                    self._handle_rate_limit(response)
                    continue

                response.raise_for_status()

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

            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request failed: {e}")
                raise e

        self.logger.info(
            "Extract completed for %s - total_fetched=%d",
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
            "amount": _none_to_zero(record.get("amount")) / 100,  # Convert paise to rupees
            "amount_paid": _none_to_zero(record.get("amount_paid")) / 100,
            "amount_due": _none_to_zero(record.get("amount_due")) / 100,
            "currency": record["currency"],
            "receipt": record.get("receipt"),
            "status": record["status"],
            "created_at": datetime.fromtimestamp(record["created_at"]),
            "_extracted_at": datetime.now(timezone.utc),  # When we fetched it
        }

    def _handle_rate_limit(self, response: requests.Response) -> None:
        """
        Handle 429 Rate Limit Exceeded.

        Razorpay may include 'Retry-After' header telling us how long to wait.
        If not present, wait 60 seconds by default.

        Args:
            response: The 429 response from Razorpay
        """

        retry_after = response.headers.get("Retry-After")

        if retry_after:
            try:
                wait_seconds = int(retry_after)
            except ValueError:
                wait_seconds = 60
        else:
            wait_seconds = 60

        self.logger.warning(f"Rate limit hit (429) - waiting for {wait_seconds} seconds")

        time.sleep(wait_seconds)

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
