"""Convert common runtime values into JSON-safe structures."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping


def to_jsonable(value: Any) -> Any:
    """Recursively normalize values produced by environments and dataclasses."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]

    item_method = getattr(value, "item", None)
    if callable(item_method):
        try:
            return to_jsonable(item_method())
        except (TypeError, ValueError):
            pass
    list_method = getattr(value, "tolist", None)
    if callable(list_method):
        try:
            return to_jsonable(list_method())
        except (TypeError, ValueError):
            pass
    return repr(value)
