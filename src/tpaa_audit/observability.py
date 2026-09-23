"""Structured M0 observability record with secret-field fail-closed handling."""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping

_FORBIDDEN_FRAGMENTS = (
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "private_key",
    "credential",
)


class SecretFieldError(ValueError):
    pass


def _safe_value(value: object, *, field: str) -> object:
    if any(fragment in field.casefold() for fragment in _FORBIDDEN_FRAGMENTS):
        raise SecretFieldError(f"secret-bearing field rejected: {field}")
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("structured logging keys must be strings")
            result[key] = _safe_value(item, field=key)
        return result
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"unsupported structured logging value: {type(value).__name__}")


def structured_record(
    *,
    component: str,
    product_version: str,
    reason_code: str,
    fields: Mapping[str, object] | None = None,
) -> dict[str, object]:
    if not component or not product_version or not reason_code:
        raise ValueError("component/product_version/reason_code are required")
    payload: dict[str, object] = {
        "system_time_utc": dt.datetime.now(dt.UTC).isoformat(),
        "component": component,
        "product_version": product_version,
        "reason_code": reason_code,
    }
    if fields is not None:
        for key, value in fields.items():
            if not isinstance(key, str):
                raise ValueError("structured logging keys must be strings")
            payload[key] = _safe_value(value, field=key)
    return payload
