"""High-performance JSON helpers.

This module tries to import the ultra-fast ``orjson`` library and falls back to
Python's built-in ``json`` module when ``orjson`` is not available.  It exposes
``dumps`` and ``loads`` functions with signatures compatible with the standard
library for drop-in replacement.

Usage:
    from utils import json_util as json
    json.dumps(obj)
    json.loads(data)

The default ``dumps`` returns **str** instead of ``bytes`` to preserve the same
behaviour as the standard ``json.dumps``.
"""
from __future__ import annotations

from typing import Any, Union, overload

try:
    import orjson as _json_impl  # type: ignore

    def _dumps(obj: Any, *, default=None, option=_json_impl.OPT_NON_STR_KEYS) -> str:  # type: ignore
        """Serialize *obj* to JSON str using orjson.

        orjson.dumps returns *bytes*, so we decode to str for compatibility.
        """
        return _json_impl.dumps(obj, default=default, option=option).decode("utf-8")

    def _loads(s: Union[str, bytes, bytearray], *, option=None) -> Any:  # type: ignore
        return _json_impl.loads(s) if option is None else _json_impl.loads(s, option=option)

except ModuleNotFoundError:  # pragma: no cover – fallback path
    import json as _json_impl  # type: ignore

    def _dumps(obj: Any, **kwargs) -> str:  # type: ignore
        return _json_impl.dumps(obj, ensure_ascii=False, separators=(",", ":"), **kwargs)

    def _loads(s: Union[str, bytes, bytearray], **kwargs) -> Any:  # type: ignore
        return _json_impl.loads(s, **kwargs)

# Re-export public API

loads = _loads  # type: ignore
"""Dump Python object *obj* to a JSON-formatted **str**.

Parameters mirror ``orjson.dumps``/``json.dumps`` loosely, but return type is
always ``str``.
"""

dumps = _dumps  # type: ignore
__all__ = ["dumps", "loads"]