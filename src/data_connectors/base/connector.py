import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from data_connectors.base.models import SyncResult, TableSchema


class BaseConnector(ABC):
    """
    Shared base for all connectors — source and destination alike.

    Holds only the two things every connector needs:
    - config:  the raw settings dict passed in at construction time
    - logger:  a named logger so every log line identifies which connector wrote it
    """

    connector_name: str = "base"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)


class BaseSourceConnector(BaseConnector):
    """
    Abstract base for all source connectors.

    One subclass = one table/entity from one data source.
    You must implement two methods:
      - extract()    — how to fetch records from the API
      - get_schema() — what columns the table has

    validate() and sync() are already implemented here and shared
    by every source connector for free.
    """

    @abstractmethod
    def extract(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        state: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """
        Fetch records from the source system one at a time.

        Args:
            start_time: Only return records after this time  (incremental sync)
            end_time:   Only return records before this time (incremental sync)
            state:      Checkpoint from the last successful sync, e.g.
                        {"cursor": "2024-01-15T12:00:00Z"}

        Yields:
            One record at a time as a plain dict:
                {"id": "T-001", "status": "open", "created_at": "2024-01-10T09:00:00Z"}

        Note:
            Use 'yield' not 'return'. This keeps memory usage flat — records
            flow out one by one instead of building a giant list first.
        """
        ...

    @abstractmethod
    def get_schema(self) -> TableSchema:
        """
        Describe the table this connector produces.

        Returns a TableSchema dataclass, for example:

            TableSchema(
                table_name="tickets",
                columns=[
                    ColumnSchema(name="id",         type="string",   required=True),
                    ColumnSchema(name="status",     type="string",   required=False),
                    ColumnSchema(name="created_at", type="datetime", required=True),
                ]
            )

        This schema is used for two things:
          1. validate()         — checks required fields in each record
          2. destination.load() — lets the destination create the table if needed
        """
        ...

    def validate(self, record: dict[str, Any]) -> bool:
        """
        Check that all required fields are present and non-null in a record.

        Called automatically inside sync() — you don't need to call this yourself.
        Returns True if valid, False if a required field is missing or None.
        """
        schema = self.get_schema()
        for field_name in schema.required_column_names():
            if field_name not in record or record[field_name] is None:
                self.logger.warning(
                    "Record skipped — missing required field '%s'", field_name
                )
                return False
        return True

    def sync(
        self,
        destination: "BaseDestinationConnector",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        state: dict[str, Any] | None = None,
        batch_size: int = 1000,
    ) -> SyncResult:
        """
        Run a full extract → validate → load cycle.

        Args:
            destination:  The destination connector to write records into
            start_time:   Start of the time window (incremental sync)
            end_time:     End of the time window (incremental sync)
            state:        Cursor from the previous sync run
            batch_size:   How many records to accumulate before flushing to destination

        Returns:
            SyncResult dataclass — the orchestrator reads next_state from it
            and stores it as the cursor for the next run.

        How batching works:
            Records stream out of extract() one by one.
            We accumulate them in a list until we hit batch_size, then
            call destination.load() for that chunk. This balances memory
            (never holding more than batch_size records) against round-trip
            cost (not calling load() for every single record).
        """
        started = time.time()
        schema = self.get_schema()

        self.logger.info(
            "Sync started — source: %s, destination: %s, table: %s",
            self.connector_name,
            destination.connector_name,
            schema.table_name,
        )

        records_extracted = 0
        records_loaded = 0
        records_failed = 0
        batch: list[dict[str, Any]] = []

        def _flush(b: list[dict[str, Any]]) -> int:
            result = destination.load(
                table_name=schema.table_name,
                records=b,
                schema=schema,
            )
            loaded: int = result.get("records_loaded", len(b))
            return loaded

        try:
            for record in self.extract(
                start_time=start_time, end_time=end_time, state=state
            ):
                records_extracted += 1

                if not self.validate(record):
                    records_failed += 1
                    continue

                batch.append(record)

                if len(batch) >= batch_size:
                    records_loaded += _flush(batch)
                    batch = []

            if batch:
                records_loaded += _flush(batch)

            duration = time.time() - started
            next_state = {"cursor": end_time.isoformat()} if end_time else (state or {})

            result = SyncResult(
                status="success",
                records_extracted=records_extracted,
                records_loaded=records_loaded,
                records_failed=records_failed,
                duration_seconds=round(duration, 3),
                next_state=next_state,
            )
            self.logger.info("Sync complete — %s", result.summary())
            return result

        except Exception as exc:
            duration = time.time() - started
            self.logger.error("Sync failed: %s", exc, exc_info=True)
            return SyncResult(
                status="error",
                records_extracted=records_extracted,
                records_loaded=records_loaded,
                records_failed=records_failed,
                duration_seconds=round(duration, 3),
                next_state=state or {},
                error=str(exc),
            )


class BaseDestinationConnector(BaseConnector):
    """
    Abstract base for all destination connectors.

    One subclass = one data store (ClickHouse, BigQuery, etc.).
    You must implement one method:
      - load() — how to write a batch of records into the data store
    """

    @abstractmethod
    def load(
        self,
        table_name: str,
        records: list[dict[str, Any]],
        schema: TableSchema,
    ) -> dict[str, Any]:
        """
        Write a batch of records to the destination.

        Args:
            table_name: The target table to write into
            records:    List of record dicts, already validated by the source
            schema:     TableSchema from get_schema() — use this to create
                        the table automatically if it does not exist yet

        Returns:
            {"records_loaded": int, "records_failed": int}
        """
        ...
