class ConnectorError(Exception):
    """
    Base class for all connector errors.

    Catch this if you want to handle any connector failure in one place.
    Catch a subclass if you need to react differently to specific failures.
    """


class ConfigurationError(ConnectorError):
    """
    Raised at startup when the config dict is missing a required key
    or contains an invalid value (e.g. wrong subdomain format).

    This always means: fix the config, not the code.
    """


class AuthenticationError(ConnectorError):
    """
    Raised when the API rejects our credentials (401 / 403).

    This usually means the API key has expired or been revoked.
    """


class RateLimitError(ConnectorError):
    """
    Raised when the API returns 429 Too Many Requests.

    Attributes:
        retry_after: Seconds to wait before retrying, if the API told us.
                     None means the API did not specify — use your own backoff.
    """

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class APIError(ConnectorError):
    """
    Raised when the API returns any unexpected non-2xx response
    that is not a 401, 403, or 429.

    Attributes:
        status_code:   The HTTP status code (e.g. 500, 404)
        response_body: The raw response text, useful for debugging
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class AirbyteExecutorError(ConnectorError):
    """
    Raised when an Airbyte Docker container exits with a non-zero code
    or produces output that cannot be parsed as Airbyte protocol messages.
    """


class ValidationError(ConnectorError):
    """
    Raised when a record fails schema validation and you want to
    stop the entire sync rather than just skip the bad record.

    In most cases validate() returns False and the record is skipped.
    Raise this explicitly only for unrecoverable data quality failures.
    """
