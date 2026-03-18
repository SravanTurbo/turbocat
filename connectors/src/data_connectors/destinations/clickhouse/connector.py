from typing import Any

from clickhouse_driver import Client

from data_connectors.base.connector import BaseDestinationConnector
from data_connectors.base.models import TableSchema
from data_connectors.destinations.clickhouse.config import ClickHouseConfig


class ClickHouseDestination(BaseDestinationConnector):
    """
    Destination connector for ClickHouse database.

    Features:
    - Auto-creates tables based on schema
    - Batch INSERT for efficiency
    - Type mapping (Python → ClickHouse)
    - Nullable column support

    Example usage:
        config = ClickHouseConfig(
            host="localhost",
            port=9000,
            database="analytics",
            user="default",
            password="secret",
        )

        destination = ClickHouseDestination(config)

        result = destination.load(
            table_name="orders",
            records=[{...}, {...}],
            schema=table_schema,
        )
    """

    connector_name = "clickhouse"
    config: ClickHouseConfig

    def __init__(self, config: ClickHouseConfig) -> None:
        super().__init__(config)

        try:
            self.client = Client(
                host=config.host,
                port=config.port,
                database=config.database,
                user=config.user,
                password=config.password.get_secret_value(),
                secure=config.secure,
            )

            self.client.execute("SELECT 1")

            self.logger.info(
                "ClickHouse destination initialized — host=%s, database=%s",
                config.host,
                config.database,
            )
        except Exception as e:
            self.logger.error("Failed to connect to ClickHouse: %s", e)
            raise

    def load(
        self,
        table_name: str,
        records: list[dict[str, Any]],
        schema: TableSchema,
    ) -> dict[str, Any]:
        """
        Load records into Clickhouse database.

        Process:
        1. Create table if it doesn't exist (based on schema)
        2. Convert records to tuples (ordered by schema columns)
        3. Execute batch INSERT

        Args:
            table_name: Target table name
            records: List of record dicts to insert
            schema: TableSchema defining columns and types

        Returns:
            Dict with:
                - records_loaded: Number of records successfully inserted
                - records_failed: Number of records that failed (always 0 for now)

        Raises:
            Exception: If INSERT fails
        """

        if not records:
            self.logger.warning("No records to load to table %s", table_name)
            return {"records_loaded": 0, "records_failed": 0}

        try:

            self._ensure_table_exists(table_name, schema)

            self._execute_batch_insert(table_name, records, schema)

            return {"records_loaded": len(records), "records_failed": 0}
        except Exception as e:
            raise e

    def _ensure_table_exists(self, table_name: str, schema: TableSchema) -> None:
        """
        Ensure the table exists in Clickhouse.

        Uses CREATE TABLE IF NOT EXISTS with MergeTree engine.

        Type mapping:
            string   → String
            integer  → Int64
            float    → Float64
            boolean  → UInt8
            datetime → DateTime
            json     → String (stored as JSON string)

        Nullable handling:
            - required=True  → Column type
            - required=False → Nullable(Column type)

        """

        column_defs = []
        for col in schema.columns:
            ch_type = self._map_type(col.type)

            if not col.required:
                ch_type = f"Nullable({ch_type})"

            column_defs.append(f"`{col.name}` {ch_type}")

        version_col = next(
            (col.name for col in schema.columns if col.name == "_extracted_at"), None
        )
        engine = (
            f"ReplacingMergeTree({version_col})"
            if version_col
            else "ReplacingMergeTree()"
        )
        create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(column_defs)}) ENGINE = {engine} ORDER BY (id)"

        self.logger.debug("Ensuring table exists: %s", table_name)

        try:
            self.client.execute(create_sql)
            self.logger.debug("✓ Table ready: %s", table_name)
        except Exception as e:
            self.logger.error("Failed to create table '%s': %s", table_name, e)
            raise

    def _map_type(self, type: str) -> str:
        """
        Map our schema types to ClickHouse types.

        Args:
            python_type: Type from our schema (string, integer, float, etc.)

        Returns:
            ClickHouse type (String, Int64, Float64, etc.)
        """
        type_mapping = {
            "string": "String",
            "integer": "Int64",
            "float": "Float64",
            "boolean": "UInt8",  # ClickHouse uses UInt8 for booleans
            "datetime": "DateTime",  # Stored as UNIX timestamp internally
            "json": "String",  # Stored as JSON string
        }

        return type_mapping.get(type, "String")

    def _execute_batch_insert(
        self, table_name: str, records: list[dict[str, Any]], schema: TableSchema
    ) -> None:
        # Convert records to tuples (ordered by schema columns).
        column_names = [col.name for col in schema.columns]
        rows = []
        for record in records:
            row = tuple(record[col_name] for col_name in column_names)
            rows.append(row)

        insert_sql = f"INSERT INTO {table_name} ({', '.join(column_names)}) VALUES"

        self.logger.debug("Executing batch INSERT for table: %s", table_name)

        try:
            self.client.execute(insert_sql, rows)
            self.logger.info(
                "✓ Successfully inserted %d rows into table: %s", len(rows), table_name
            )
        except Exception as e:
            self.logger.error("Failed to load records to table '%s': %s", table_name, e)
            raise
