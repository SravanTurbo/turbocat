from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from data_connectors.base.connector import BaseSourceConnector
from data_connectors.base.models import ColumnSchema, TableSchema
from data_connectors.common.http_client import RetryableHTTPClient
from data_connectors.sources.kapture.config import KaptureSourceConfig

_ENDPOINT = "/ms/kreport/generic-report/pull-data"


class KaptureTicketsConnector(BaseSourceConnector):
    """
    Extract support tickets from Kapture CRM via the reporting endpoint.

    Iterates day-by-day over the requested range, fetching all tickets
    created within each day. The session cookie issued on first auth is
    stored and forwarded automatically by requests.Session.
    """

    connector_name = "kapture_tickets"
    config: KaptureSourceConfig

    def __init__(self, config: KaptureSourceConfig) -> None:
        super().__init__(config)
        self._template_id = config.tickets_template_id
        self.http_client = RetryableHTTPClient(
            base_url=config.base_url,
            headers={"Authorization": f"Basic {config.token.get_secret_value()}"},
            timeout=config.timeout,
            max_retries=config.max_retries,
        )
        self.logger.info(
            "%s connector initialized — base_url=%s template_id=%d",
            self.connector_name,
            config.base_url,
            self._template_id,
        )

    def test_connection(self) -> None:
        """Hit the reporting endpoint with a minimal payload to confirm credentials."""
        now = datetime.now(timezone.utc)
        self.http_client.post(
            _ENDPOINT,
            json={
                "templateId": self._template_id,
                "startDate": now.strftime("%Y-%m-%d"),
                "endDate": now.strftime("%Y-%m-%d"),
                "pageNo": 1,
                "pageSize": 1,
            },
        )

    def extract(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        state: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """
        Fetch tickets day by day between start_time and end_time.

        Defaults to today if no range is given.
        """
        now = datetime.now(timezone.utc)
        effective_start = start_time or now.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        effective_end = end_time or now

        self.logger.info(
            "Starting extract for %s - start=%s end=%s",
            self.connector_name,
            effective_start,
            effective_end,
        )

        total_fetched = 0
        current = effective_start.replace(hour=0, minute=0, second=0, microsecond=0)

        while current.date() <= effective_end.date():
            # Request format: MM/DD/YYYY (what the URL expects)
            date_param = current.strftime("%m/%d/%Y")
            params = {
                "reportType": "T",
                "start_date": date_param,
                "end_date": date_param,
                "start_time": "00:00:00",
                "end_time": "23:59:59",
                "templateId": self._template_id,
                "employee_ids": -2,
            }

            self.logger.debug("Fetching tickets for %s", date_param)
            response = self.http_client.post(_ENDPOINT, params=params)
            tickets = response.json()

            if not isinstance(tickets, list):
                self.logger.warning(
                    "Unexpected response shape for %s: %s", date_param, type(tickets)
                )
                current += timedelta(days=1)
                continue

            for ticket in tickets:
                total_fetched += 1
                yield self.transform(ticket)

            self.logger.debug("Fetched %d tickets for %s", len(tickets), date_param)
            current += timedelta(days=1)

        self.logger.info(
            "Extract complete %s - total_extracted=%d",
            self.connector_name,
            total_fetched,
        )

    def transform(self, record: dict[str, Any]) -> dict[str, Any]:
        ticket = record.get("ticket") or {}
        customer = record.get("customer") or {}
        contact = record.get("contact") or {}
        folder_levels = record.get("dispositionFolderLevel") or {}

        return {
            "ticket_id": record.get("ticketId"),
            "task_id": ticket.get("Task Id"),
            "task_title": ticket.get("Task Title"),
            "status": ticket.get("Status"),
            "sub_status": ticket.get("Sub Status"),
            "priority": ticket.get("Priority Name"),
            "tat": ticket.get("TAT") or None,
            "sla": ticket.get("SLA") or None,
            "created_at": _parse_dt(record.get("createDate"), record.get("createTime")),
            "last_conversation_at": _parse_dt(
                record.get("lastConversationDate"),
                record.get("lastConversationTime"),
            ),
            "source_type": record.get("sourceType"),
            "create_source_type": record.get("createSourceType"),
            "create_reason": record.get("createReason"),
            "landing_folder": record.get("landingFolder") or None,
            "disposed_folder": record.get("disposedFolder") or None,
            "folder_level_1": folder_levels.get("Folder level 1") or None,
            "folder_level_2": folder_levels.get("Folder level 2") or None,
            "folder_level_3": folder_levels.get("Folder level 3") or None,
            "current_queue": record.get("currentQueue") or None,
            "landing_queue": record.get("landingQueue") or None,
            "dispose_by": record.get("disposeBy") or None,
            "first_response_by": record.get("firstResponseBy") or None,
            "last_response_by": record.get("lastresponseBy") or None,
            "first_assign_emp": record.get("firstAssignEmpName") or None,
            "reopen_count": _to_int(record.get("reopenCount")),
            "dispose_count": _to_int(record.get("disposeCount")),
            "customer_interaction_count": _to_int(
                record.get("customerInteractioncount")
            ),
            "agent_interaction_count": _to_int(record.get("agentInteractionCount")),
            "total_interaction_count": _to_int(record.get("totalInteractionCount")),
            "conversation_count": _to_int(ticket.get("Conversation Count")),
            "ftr": record.get("ftr"),
            "first_response_time": record.get("firstResponseTime") or None,
            "avg_agent_response_time": record.get("avgAgentResponseTime") or None,
            "avg_handling_time": record.get("avgHandlingTime") or None,
            "time_to_resolve": record.get("diffCreateAndResolve") or None,
            "ticket_url": record.get("ticketUrl"),
            "email": ticket.get("Email") or None,
            "phone": ticket.get("Phone") or None,
            "customer_name": customer.get("Customer Name") or None,
            "customer_code": customer.get("Customer Code") or None,
            "contact_name": contact.get("Contact Person") or None,
            "contact_email": contact.get("Email") or None,
            "contact_phone": contact.get("Phone") or None,
            "_extracted_at": datetime.now(timezone.utc),
        }

    def get_schema(self) -> TableSchema:
        return TableSchema(
            table_name="kapture_tickets",
            columns=[
                ColumnSchema(name="ticket_id", type="string", required=True),
                ColumnSchema(name="task_id", type="string", required=False),
                ColumnSchema(name="task_title", type="string", required=False),
                ColumnSchema(name="status", type="string", required=False),
                ColumnSchema(name="sub_status", type="string", required=False),
                ColumnSchema(name="priority", type="string", required=False),
                ColumnSchema(name="tat", type="string", required=False),
                ColumnSchema(name="sla", type="string", required=False),
                ColumnSchema(name="created_at", type="datetime", required=False),
                ColumnSchema(
                    name="last_conversation_at", type="datetime", required=False
                ),
                ColumnSchema(name="source_type", type="string", required=False),
                ColumnSchema(name="create_source_type", type="string", required=False),
                ColumnSchema(name="create_reason", type="string", required=False),
                ColumnSchema(name="landing_folder", type="string", required=False),
                ColumnSchema(name="disposed_folder", type="string", required=False),
                ColumnSchema(name="folder_level_1", type="string", required=False),
                ColumnSchema(name="folder_level_2", type="string", required=False),
                ColumnSchema(name="folder_level_3", type="string", required=False),
                ColumnSchema(name="current_queue", type="string", required=False),
                ColumnSchema(name="landing_queue", type="string", required=False),
                ColumnSchema(name="dispose_by", type="string", required=False),
                ColumnSchema(name="first_response_by", type="string", required=False),
                ColumnSchema(name="last_response_by", type="string", required=False),
                ColumnSchema(name="first_assign_emp", type="string", required=False),
                ColumnSchema(name="reopen_count", type="integer", required=False),
                ColumnSchema(name="dispose_count", type="integer", required=False),
                ColumnSchema(
                    name="customer_interaction_count",
                    type="integer",
                    required=False,
                ),
                ColumnSchema(
                    name="agent_interaction_count",
                    type="integer",
                    required=False,
                ),
                ColumnSchema(
                    name="total_interaction_count",
                    type="integer",
                    required=False,
                ),
                ColumnSchema(name="conversation_count", type="integer", required=False),
                ColumnSchema(name="ftr", type="string", required=False),
                ColumnSchema(name="first_response_time", type="string", required=False),
                ColumnSchema(
                    name="avg_agent_response_time", type="string", required=False
                ),
                ColumnSchema(name="avg_handling_time", type="string", required=False),
                ColumnSchema(name="time_to_resolve", type="string", required=False),
                ColumnSchema(name="ticket_url", type="string", required=False),
                ColumnSchema(name="email", type="string", required=False),
                ColumnSchema(name="phone", type="string", required=False),
                ColumnSchema(name="customer_name", type="string", required=False),
                ColumnSchema(name="customer_code", type="string", required=False),
                ColumnSchema(name="contact_name", type="string", required=False),
                ColumnSchema(name="contact_email", type="string", required=False),
                ColumnSchema(name="contact_phone", type="string", required=False),
                ColumnSchema(name="_extracted_at", type="datetime", required=True),
            ],
        )


def _parse_dt(date_str: str | None, time_str: str | None) -> datetime | None:
    """Parse Kapture's DD/MM/YYYY + HH:MM:SS response format."""
    if not date_str:
        return None
    raw = f"{date_str.strip()} {(time_str or '00:00:00').strip()}"
    try:
        return datetime.strptime(raw, "%d/%m/%Y %H:%M:%S")
    except ValueError:
        return None


def _to_int(value: Any) -> int | None:
    if value is None or value == "null" or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
