"""
JSON serialization utilities with orjson fallback.
"""

from __future__ import annotations

from typing import Any

# Try to import orjson for fast serialization
try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    import json
    HAS_ORJSON = False # type: ignore[misc]


def _serialize_to_json(data: dict[str, Any]) -> bytes:
    """Serialize a dictionary to JSON bytes (uses orjson if available)."""
    if HAS_ORJSON:
        # Fast path: orjson returns bytes directly
        return orjson.dumps(data) # type: ignore[no-any-return]
    else:
        # Fallback: standard library json returns str, encode to bytes
        return json.dumps(data, separators=(',', ':')).encode('utf-8') # type: ignore[misc]


def _is_orjson_available() -> bool:
    """Check if orjson is available for faster JSON serialization."""
    return HAS_ORJSON
