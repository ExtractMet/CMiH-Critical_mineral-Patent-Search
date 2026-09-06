"""Critical Minerals Smart Technology & Patent Tracker — core package."""
from . import analytics, connectors, schema, seed_data, store, taxonomy  # noqa: F401

__version__ = "1.0.0"
__all__ = ["analytics", "connectors", "schema", "seed_data", "store", "taxonomy"]
