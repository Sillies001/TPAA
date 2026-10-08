"""Governed hash-safe JSON transport for production P1 metric inputs."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Final

P1_FLOAT64_DECIMAL_MARKER: Final = "__tpaa_float64_decimal_v1__"


class ProductionP1TransportError(ValueError):
    """P1 input cannot be represented by the governed JSON transport."""


def encode_production_p1_transport(
    value: object,
    *,
    field: str = "$",
) -> object:
    """Encode finite floats as explicit canonical decimal-string marker objects."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ProductionP1TransportError(f"{field}: non-finite float")
        return {P1_FLOAT64_DECIMAL_MARKER: repr(value)}
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ProductionP1TransportError(
                    f"{field}: mapping key must be str"
                )
            result[key] = encode_production_p1_transport(
                item,
                field=f"{field}.{key}",
            )
        return result
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return [
            encode_production_p1_transport(item, field=f"{field}[]")
            for item in value
        ]
    raise ProductionP1TransportError(
        f"{field}: unsupported type {type(value).__name__}"
    )


def decode_production_p1_transport(
    value: object,
    *,
    field: str = "$",
) -> object:
    """Restore only explicitly marked finite binary64 values; reject raw floats."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        raise ProductionP1TransportError(
            f"{field}: raw float is forbidden in request transport"
        )
    if isinstance(value, Mapping):
        if P1_FLOAT64_DECIMAL_MARKER in value:
            if len(value) != 1:
                raise ProductionP1TransportError(
                    f"{field}: decimal marker object has extra fields"
                )
            raw = value[P1_FLOAT64_DECIMAL_MARKER]
            if not isinstance(raw, str) or not raw or raw.strip() != raw:
                raise ProductionP1TransportError(
                    f"{field}: decimal marker value must be canonical text"
                )
            try:
                restored = float(raw)
            except ValueError as exc:
                raise ProductionP1TransportError(
                    f"{field}: decimal marker value is invalid"
                ) from exc
            if not math.isfinite(restored) or repr(restored) != raw:
                raise ProductionP1TransportError(
                    f"{field}: decimal marker value is non-canonical"
                )
            return restored
        result: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ProductionP1TransportError(
                    f"{field}: mapping key must be str"
                )
            result[key] = decode_production_p1_transport(
                item,
                field=f"{field}.{key}",
            )
        return result
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return [
            decode_production_p1_transport(item, field=f"{field}[]")
            for item in value
        ]
    raise ProductionP1TransportError(
        f"{field}: unsupported type {type(value).__name__}"
    )
