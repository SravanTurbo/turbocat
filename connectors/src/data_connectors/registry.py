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
