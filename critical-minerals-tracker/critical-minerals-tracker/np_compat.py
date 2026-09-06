"""
NumPy 2.0 compatibility shim.

NumPy 2.0 removed a set of long-deprecated scalar-type aliases (``np.unicode_``,
``np.string_``, ``np.bool8`` ...). Some third-party packages that a Streamlit app
pulls in transitively (older ``pyarrow`` / ``pandas`` / ``altair`` builds) still
reference these names and crash with::

    AttributeError: `np.unicode_` was removed in the NumPy 2.0 release.

Importing this module *before* those packages are used restores the aliases at
runtime, so the app works whether NumPy is 1.x or 2.x, without pinning anything.
It is a no-op on NumPy < 2.0 (the aliases already exist) and never overwrites a
name that is present.

`import np_compat` at the very top of the entry point, before pandas / plotly /
streamlit are exercised. (Streamlit imports pyarrow lazily, at the first
DataFrame render, so this runs in time.)
"""

from __future__ import annotations

import numpy as _np

# removed alias  ->  current canonical name
_ALIASES = {
    "unicode_": "str_",
    "string_": "bytes_",
    "bool8": "bool_",
    "object0": "object_",
    "int0": "intp",
    "uint0": "uintp",
    "str0": "str_",
    "bytes0": "bytes_",
    "void0": "void",
    "float_": "float64",
    "complex_": "complex128",
    "longfloat": "longdouble",
    "singlecomplex": "complex64",
    "cfloat": "complex128",
    "clongfloat": "clongdouble",
}

_patched: list[str] = []
for _old, _new in _ALIASES.items():
    if not hasattr(_np, _old) and hasattr(_np, _new):
        setattr(_np, _old, getattr(_np, _new))
        _patched.append(_old)


def patched() -> list[str]:
    """Return the list of aliases this shim had to restore (empty on NumPy 1.x)."""
    return list(_patched)
