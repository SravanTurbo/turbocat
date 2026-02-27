"""
Unit tests for RetryableHTTPClient.

All HTTP calls and time.sleep are mocked — no network access, no real waiting.
"""

from unittest.mock import MagicMock, call, patch

import pytest
import requests
from requests.adapters import HTTPAdapter

from data_connectors.common.http_client import RetryableHTTPClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_response(status_code: int, headers: dict[str, str] | None = None) -> MagicMock:
    """Build a mock requests.Response with the given status code and headers."""
    response = MagicMock(spec=requests.Response)
    response.status_code = status_code
    response.headers = headers or {}
    # 429 is handled before raise_for_status() is ever called in _request(),
    # so only wire up the side-effect for other error codes.
    if status_code >= 400 and status_code != 429:
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
    else:
        response.raise_for_status.return_value = None
    return response


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestInit:
    def test_trailing_slash_stripped_from_base_url(self) -> None:
        client = RetryableHTTPClient(base_url="https://api.example.com/")
        assert client.base_url == "https://api.example.com"

    def test_base_url_without_trailing_slash_unchanged(self) -> None:
        client = RetryableHTTPClient(base_url="https://api.example.com")
        assert client.base_url == "https://api.example.com"

    def test_default_timeout_is_10(self) -> None:
        assert RetryableHTTPClient().timeout == 10

    def test_default_max_retries_is_3(self) -> None:
        assert RetryableHTTPClient().max_retries == 3

    def test_custom_timeout_is_stored(self) -> None:
        assert RetryableHTTPClient(timeout=30).timeout == 30

    def test_auth_tuple_sets_basic_auth(self) -> None:
        client = RetryableHTTPClient(auth=("mykey", "mysecret"))
        assert client.session.auth is not None
        assert client.session.auth.username == "mykey"  # type: ignore[union-attr]
        assert client.session.auth.password == "mysecret"  # type: ignore[union-attr]

    def test_no_auth_when_not_provided(self) -> None:
        assert RetryableHTTPClient().session.auth is None

    def test_custom_headers_added_to_session(self) -> None:
        client = RetryableHTTPClient(headers={"Content-Type": "application/json"})
        assert client.session.headers["Content-Type"] == "application/json"

    def test_retry_adapter_mounted_for_https(self) -> None:
        client = RetryableHTTPClient()
        assert isinstance(client.session.get_adapter("https://x.com"), HTTPAdapter)

    def test_retry_adapter_mounted_for_http(self) -> None:
        client = RetryableHTTPClient()
        assert isinstance(client.session.get_adapter("http://x.com"), HTTPAdapter)

    def test_retry_adapter_respects_max_retries(self) -> None:
        client = RetryableHTTPClient(max_retries=5)
        adapter = client.session.get_adapter("https://x.com")
        assert isinstance(adapter, HTTPAdapter)
        assert adapter.max_retries.total == 5


# ---------------------------------------------------------------------------
# Successful GET requests
# ---------------------------------------------------------------------------


class TestGet:
    def setup_method(self) -> None:
        self.client = RetryableHTTPClient(base_url="https://api.example.com", timeout=15)

    def _mock_request(self, status_code: int = 200) -> MagicMock:
        mock = MagicMock(return_value=make_response(status_code))
        self.client.session.request = mock  # type: ignore[method-assign]
        return mock

    def test_returns_response_on_200(self) -> None:
        mock = self._mock_request(200)
        result = self.client.get("/items")
        assert result is mock.return_value

    def test_url_is_base_url_plus_endpoint(self) -> None:
        mock = self._mock_request()
        self.client.get("/orders")
        assert mock.call_args.kwargs["url"] == "https://api.example.com/orders"

    def test_method_is_get(self) -> None:
        mock = self._mock_request()
        self.client.get("/orders")
        assert mock.call_args.kwargs["method"] == "GET"

    def test_params_passed_through(self) -> None:
        mock = self._mock_request()
        self.client.get("/orders", params={"skip": 0, "count": 100})
        assert mock.call_args.kwargs["params"] == {"skip": 0, "count": 100}

    def test_configured_timeout_used(self) -> None:
        mock = self._mock_request()
        self.client.get("/orders")
        assert mock.call_args.kwargs["timeout"] == 15

    def test_per_request_headers_merged_with_session_defaults(self) -> None:
        self.client.session.headers.update({"Content-Type": "application/json"})
        mock = self._mock_request()
        self.client.get("/orders", headers={"X-Request-ID": "abc"})
        merged = mock.call_args.kwargs["headers"]
        assert merged["Content-Type"] == "application/json"
        assert merged["X-Request-ID"] == "abc"

    def test_per_request_headers_override_session_defaults(self) -> None:
        self.client.session.headers.update({"X-Version": "1"})
        mock = self._mock_request()
        self.client.get("/orders", headers={"X-Version": "2"})
        assert mock.call_args.kwargs["headers"]["X-Version"] == "2"

    def test_raises_http_error_on_404(self) -> None:
        self.client.session.request = MagicMock(return_value=make_response(404))  # type: ignore[method-assign]
        with pytest.raises(requests.HTTPError):
            self.client.get("/not-found")

    def test_raises_http_error_on_500(self) -> None:
        self.client.session.request = MagicMock(return_value=make_response(500))  # type: ignore[method-assign]
        with pytest.raises(requests.HTTPError):
            self.client.get("/broken")

    def test_raises_http_error_on_401(self) -> None:
        self.client.session.request = MagicMock(return_value=make_response(401))  # type: ignore[method-assign]
        with pytest.raises(requests.HTTPError):
            self.client.get("/secure")


# ---------------------------------------------------------------------------
# Rate limit (429) handling
# ---------------------------------------------------------------------------


class TestRateLimitHandling:
    def setup_method(self) -> None:
        self.client = RetryableHTTPClient(base_url="https://api.example.com")

    @patch("data_connectors.common.http_client.time.sleep")
    def test_retry_after_header_determines_sleep_duration(self, mock_sleep: MagicMock) -> None:
        self.client.session.request = MagicMock(  # type: ignore[method-assign]
            side_effect=[
                make_response(429, headers={"Retry-After": "30"}),
                make_response(200),
            ]
        )
        self.client.get("/items")
        mock_sleep.assert_called_once_with(30)

    @patch("data_connectors.common.http_client.time.sleep")
    def test_missing_retry_after_defaults_to_60_seconds(self, mock_sleep: MagicMock) -> None:
        self.client.session.request = MagicMock(  # type: ignore[method-assign]
            side_effect=[
                make_response(429, headers={}),
                make_response(200),
            ]
        )
        self.client.get("/items")
        mock_sleep.assert_called_once_with(60)

    @patch("data_connectors.common.http_client.time.sleep")
    def test_non_numeric_retry_after_defaults_to_60_seconds(self, mock_sleep: MagicMock) -> None:
        self.client.session.request = MagicMock(  # type: ignore[method-assign]
            side_effect=[
                make_response(429, headers={"Retry-After": "tomorrow"}),
                make_response(200),
            ]
        )
        self.client.get("/items")
        mock_sleep.assert_called_once_with(60)

    @patch("data_connectors.common.http_client.time.sleep")
    def test_retries_after_sleep_and_returns_success_response(self, mock_sleep: MagicMock) -> None:
        success = make_response(200)
        self.client.session.request = MagicMock(  # type: ignore[method-assign]
            side_effect=[
                make_response(429, headers={"Retry-After": "1"}),
                success,
            ]
        )
        result = self.client.get("/items")
        assert result is success
        assert self.client.session.request.call_count == 2

    @patch("data_connectors.common.http_client.time.sleep")
    def test_multiple_consecutive_429s_each_trigger_sleep_and_retry(self, mock_sleep: MagicMock) -> None:
        success = make_response(200)
        self.client.session.request = MagicMock(  # type: ignore[method-assign]
            side_effect=[
                make_response(429, headers={"Retry-After": "10"}),
                make_response(429, headers={"Retry-After": "20"}),
                success,
            ]
        )
        result = self.client.get("/items")
        assert result is success
        assert mock_sleep.call_count == 2
        mock_sleep.assert_has_calls([call(10), call(20)])

    @patch("data_connectors.common.http_client.time.sleep")
    def test_rate_limit_does_not_call_raise_for_status(self, mock_sleep: MagicMock) -> None:
        """429 should sleep+retry, never raise."""
        rate_limited = make_response(429, headers={"Retry-After": "1"})
        self.client.session.request = MagicMock(  # type: ignore[method-assign]
            side_effect=[rate_limited, make_response(200)]
        )
        self.client.get("/items")
        rate_limited.raise_for_status.assert_not_called()
