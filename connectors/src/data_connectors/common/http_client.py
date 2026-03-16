import logging
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from urllib3.util.retry import Retry


class RetryableHTTPClient:
    """
    HTTP client wrapper with retry and rate limit handling.

    Features:
    - Automatic retry on network errors (exponential backoff)
    - Rate limit handling (respects 429 and Retry-After header)
    - Connection pooling (via Session)
    - Request logging

    Example usage:
        client = RetryableHTTPClient(
            base_url="https://api.razorpay.com/v1",
            auth=("key_id", "key_secret"),
            timeout=30
        )

        response = client.get("/orders", params={"count": 100})
        data = response.json()
    """

    def __init__(
        self,
        base_url: str = "",
        auth: tuple[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = 10,
        max_retries: int = 3,
    ):
        """
        Initialize HTTP client.

        Args:
            base_url: Base URL prepended to all requests
            auth: Tuple of (username, password) for Basic Auth
            headers: Default headers added to all requests
            timeout: Request timeout in seconds
            max_retries: Number of retry attempts on failure
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

        self.session = requests.Session()

        if auth:
            self.session.auth = HTTPBasicAuth(*auth)

        if headers:
            self.session.headers.update(headers)

        self._configure_retries()

        self.logger = logging.getLogger(self.__class__.__name__)

    def _configure_retries(self) -> None:
        """
        Configure automatic retry with exponential backoff.

        Retry strategy:
        - Retry on: 500, 502, 503, 504 (server errors)
        - Backoff: 1s, 2s, 4s (exponential)
        - Safe methods only: GET, PUT, DELETE
        """
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "PUT", "DELETE"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def get(
        self,
        endpoint: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> requests.Response:
        """
        Make a GET request with automatic retry and rate limit handling.

        Args:
            endpoint: API endpoint (e.g., "/orders")
            params: Query parameters
            headers: Additional headers (merged with defaults)

        Returns:
            Response object

        Raises:
            requests.exceptions.RequestException: On failure after all retries
        """
        return self._request("GET", endpoint, params=params, headers=headers)

    def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> requests.Response:
        """Internal request method with rate limit handling.
        Args:
            method: HTTP method
            endpoint: API endpoint (e.g. "/api/v1/customers")
            **kwargs: Additional request parameters (headers, params, data, etc.)
        Returns:
            requests.Response
        """
        url = f"{self.base_url}{endpoint}"

        self.logger.debug("%s %s", method, url)

        # Merge session-level headers with per-request headers, pop the headers key from kwargs.
        request_headers = dict(self.session.headers)
        if "headers" in kwargs and kwargs["headers"]:
            request_headers.update(kwargs.pop("headers"))

        request_kwargs = {
            "method": method,
            "url": url,
            "headers": request_headers,
            "timeout": self.timeout,
            **kwargs,
        }
        response = self.session.request(**request_kwargs)

        if response.status_code == 429:
            self._handle_rate_limit(response)
            return self._request(method, endpoint, **kwargs)

        response.raise_for_status()
        return response

    def _handle_rate_limit(self, response: requests.Response) -> None:
        """Handle 429 Rate Limit Exceeded."""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                wait_seconds = int(retry_after)
            except ValueError:
                wait_seconds = 60
        else:
            wait_seconds = 60

        self.logger.warning("Rate limit hit (429) - waiting for %s seconds", wait_seconds)
        time.sleep(wait_seconds)
