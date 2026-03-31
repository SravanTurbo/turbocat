"""
Connector registry — factory and discovery for all source connectors.

Usage:
    from data_connectors.registry import build, lookup, list_connectors

    connector = build("razorpay_orders")          # config loaded from env vars
    cls, cfg_cls = lookup("razorpay_orders")      # caller handles instantiation

    print(list_connectors())

Adding a new connector:
    1. Import its class and config below
    2. Add an entry to _REGISTRY
"""

from data_connectors.base.connector import BaseSourceConnector
from data_connectors.sources.kapture.config import KaptureSourceConfig
from data_connectors.sources.kapture.tickets_connector import KaptureTicketsConnector
from data_connectors.sources.razorpay.config import RazorpaySourceConfig
from data_connectors.sources.razorpay.customers_connector import (
    RazorpayCustomersConnector,
)
from data_connectors.sources.razorpay.orders_connector import RazorpayOrdersConnector

# Maps connector name -> (ConnectorClass, ConfigClass)
# Config is always loaded from environment variables via pydantic-settings.
_REGISTRY: dict[str, tuple[type[BaseSourceConnector], type]] = {
    "razorpay_orders": (RazorpayOrdersConnector, RazorpaySourceConfig),
    "razorpay_customers": (RazorpayCustomersConnector, RazorpaySourceConfig),
    "kapture_tickets": (KaptureTicketsConnector, KaptureSourceConfig),
}

# Maps source name -> (representative ConnectorClass, ConfigClass)
# One entry per source; the representative connector is used for connection testing.
_SOURCE_REGISTRY: dict[str, tuple[type[BaseSourceConnector], type]] = {
    "razorpay": (RazorpayOrdersConnector, RazorpaySourceConfig),
    "kapture": (KaptureTicketsConnector, KaptureSourceConfig),
}


def build(name: str) -> BaseSourceConnector:
    """
    Instantiate a connector by name. Config is loaded from environment variables.

    Args:
        name: Registered connector name, e.g. "razorpay_orders"

    Returns:
        An initialised BaseSourceConnector instance

    Raises:
        KeyError: if the name is not in the registry
    """
    if name not in _REGISTRY:
        available = list(_REGISTRY)
        raise KeyError(f"Unknown connector {name!r}. Available: {available}")
    connector_cls, config_cls = _REGISTRY[name]
    return connector_cls(config_cls())


def lookup(name: str) -> tuple[type[BaseSourceConnector], type]:
    """
    Return (ConnectorClass, ConfigClass) for the given connector name.

    The caller is responsible for instantiating the config and the connector.
    Use this when you need to inject credentials or params directly rather than
    reading from environment variables (e.g. in the agent executor).

    Raises:
        KeyError: if the name is not in the registry
    """
    if name not in _REGISTRY:
        raise KeyError(f"Unknown connector {name!r}. Available: {list(_REGISTRY)}")
    return _REGISTRY[name]


def list_connectors() -> list[str]:
    """Return the names of all registered connectors."""
    return list(_REGISTRY)


def build_from_credentials(
    source: str, credentials: dict[str, str]
) -> BaseSourceConnector:
    """
    Instantiate the representative connector for a source using caller-supplied credentials.

    Unlike build(), this does NOT read from environment variables — credentials
    are passed directly and override any env vars that happen to be present.

    Args:
        source:      Source name, e.g. "razorpay" or "kapture"
        credentials: Flat dict of credential key/value pairs matching the
                     source's config fields (e.g. {"api_key": "...", "api_secret": "..."})

    Returns:
        An initialised BaseSourceConnector ready to call test_connection()

    Raises:
        KeyError:            if source is not in _SOURCE_REGISTRY
        ValidationError:     if credentials are missing required fields
    """
    if source not in _SOURCE_REGISTRY:
        available = list(_SOURCE_REGISTRY)
        raise KeyError(f"Unknown source {source!r}. Available: {available}")
    connector_cls, config_cls = _SOURCE_REGISTRY[source]
    config = config_cls(**credentials)
    return connector_cls(config)


def list_sources() -> list[str]:
    """Return the names of all registered sources."""
    return list(_SOURCE_REGISTRY)
