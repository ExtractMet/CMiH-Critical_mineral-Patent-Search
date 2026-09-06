"""Critical Minerals Smart Technology & Patent Tracker — core package."""
# Restore NumPy 2.0-removed aliases before pandas/pyarrow are exercised, so the
# package works under NumPy 1.x or 2.x regardless of transitive-dep versions.
import numpy as _np
for _o, _n in {"unicode_": "str_", "string_": "bytes_", "bool8": "bool_",
               "object0": "object_", "int0": "intp", "uint0": "uintp",
               "str0": "str_", "bytes0": "bytes_", "void0": "void",
               "float_": "float64", "complex_": "complex128"}.items():
    if not hasattr(_np, _o) and hasattr(_np, _n):
        setattr(_np, _o, getattr(_np, _n))

from . import analytics, connectors, schema, seed_data, store, taxonomy  # noqa: F401,E402

__version__ = "1.0.0"
__all__ = ["analytics", "connectors", "schema", "seed_data", "store", "taxonomy"]
