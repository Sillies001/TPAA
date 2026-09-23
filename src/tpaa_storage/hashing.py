"""Distinct M0 request/logical/artifact hash primitives."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
type JSONPrimitive = str | int | bool | None
type CanonicalValue = JSONPrimitive | list[CanonicalValue] | dict[str, CanonicalValue]


class HashInputError(ValueError):
    """Input cannot be serialized under the deterministic M0 hash contract."""


def artifact_byte_hash(data: bytes) -> str:
    """Hash exact artifact bytes without normalization."""

    return hashlib.sha256(data).hexdigest()


def _normalize(value: object, *, field: str = "$") -> CanonicalValue:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        raise HashInputError(f"{field}: float is forbidden; use governed decimal-string semantics")
    if isinstance(value, Mapping):
        result: dict[str, CanonicalValue] = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise HashInputError(f"{field}: mapping key must be str")
            result[key] = _normalize(value[key], field=f"{field}.{key}")
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize(item, field=f"{field}[]") for item in value]
    raise HashInputError(f"{field}: unsupported type {type(value).__name__}")


def _canonical_bytes(value: object) -> bytes:
    normalized = _normalize(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_request_hash(request: object) -> str:
    """Hash the canonical command/request body; Idempotency-Key remains a separate key."""

    return hashlib.sha256(_canonical_bytes(request)).hexdigest()


def logical_content_hash(logical_product: object) -> str:
    """Hash governed logical content only; callers must not pass physical deployment metadata."""

    return hashlib.sha256(_canonical_bytes(logical_product)).hexdigest()
