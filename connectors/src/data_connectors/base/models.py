from dataclasses import dataclass, field
from typing import Any


@dataclass
class ColumnSchema:
    """
    Describes a single column in a table.

    Attributes:
        name:     Column name as it will appear in the destination table.
        type:     Data type — one of:
                    "string", "integer", "float", "boolean", "datetime", "json"
        required: If True, any record missing this field (or with None) is
                  rejected by validate() and counted as records_failed.
    """

    name: str
    type: str
    required: bool = False


@dataclass
class TableSchema:
    """
    Describes the full shape of one table produced by a source connector.

    Returned by get_schema() on every source connector.
    Passed to destination.load() so the destination can create
    the table automatically if it does not exist yet.

    Attributes:
        table_name: The name of the destination table, e.g. "tickets"
        columns:    Ordered list of columns the table has
    """

    table_name: str
    columns: list[ColumnSchema]

    def required_column_names(self) -> list[str]:
        """Convenience: returns just the names of required columns."""
        return [col.name for col in self.columns if col.required]


@dataclass
class SyncResult:
    """
    Returned by BaseSourceConnector.sync() after every run.

    The orchestrator uses this to:
      - log and monitor sync health
      - persist next_state so the next run knows where to resume

    Attributes:
        status:            "success" if the sync completed without an exception,
                           "error" if an exception was caught mid-sync.
        records_extracted: Total records yielded by extract()
        records_loaded:    Records successfully written to the destination
        records_failed:    Records that failed validate() and were skipped
        duration_seconds:  Wall-clock time for the full sync
        next_state:        Cursor dict the orchestrator should store and pass
                           back as `state` on the next run.
                           e.g. {"last_sync_at": "2024-01-02T00:00:00Z"}
        error:             Exception message, only set when status == "error"
    """

    status: str
    records_extracted: int
    records_loaded: int
    records_failed: int
    duration_seconds: float
    next_state: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def is_success(self) -> bool:
        return self.status == "success"

    def summary(self) -> str:
        """One-line human readable summary, useful for logging."""
        parts = [
            f"status={self.status}",
            f"extracted={self.records_extracted}",
            f"loaded={self.records_loaded}",
            f"failed={self.records_failed}",
            f"duration={self.duration_seconds:.1f}s",
        ]
        if self.error:
            parts.append(f"error={self.error!r}")
        return " ".join(parts)
