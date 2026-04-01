# connectors

Shared connector library. Pip-installable, imported by both `orchestrator` and `agent`.

## Source layout

```
src/data_connectors/
├── base/
│   ├── connector.py   # BaseSourceConnector, BaseDestinationConnector
│   ├── models.py      # SyncResult, TableSchema, ColumnSchema
│   └── exceptions.py  # ConnectorError, AuthenticationError, etc.
├── registry.py        # lookup(name) → (ConnectorClass, ConfigClass); build_from_credentials(); get_schemas_for_source()
├── common/
│   └── http_client.py # RetryableHTTPClient — exponential backoff, shared by all source connectors
├── sources/
│   ├── razorpay/      # RazorpayOrdersConnector, RazorpayCustomersConnector
│   └── kapture/       # KaptureTicketsConnector
└── destinations/
    └── clickhouse/    # ClickHouseDestination
```

## Adding a new source connector

1. Create `sources/{name}/` with `connector.py` and `config.py`.
2. Subclass `BaseSourceConnector`. Implement three methods:
   - `test_connection(self) -> None` — raise on auth failure
   - `get_schema(self) -> TableSchema` — declare column names + types
   - `extract(self, start_time, end_time, state) -> Iterator[dict]` — yield raw records
3. Register in `registry.py`: add `"{name}": (ConnectorClass, ConfigClass)` to the registry dict.
4. The `sync()` method on the base class handles batching, validation, ClickHouse loading, and state cursor update — don't override it.

## Config pattern

Each connector has a `*Config(BaseSettings)` class that reads credentials from env vars (agent) or is constructed from a `dict` (orchestrator, at job dispatch time). Always accept `**kwargs` and map to typed fields.

## RetryableHTTPClient

Use `self._client = RetryableHTTPClient(base_url, headers)` in `__init__`. It handles 429/5xx retries with exponential backoff. Don't use `requests` directly in connectors.
