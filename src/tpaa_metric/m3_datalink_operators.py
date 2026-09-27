"""M3 datalink numerical operators frozen by the P1 Metric Catalog.

The qualified M2 operator map remains immutable. This module extends the M3
operator overlay only with MAD_V1, which is first required by P1-DL-002.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType

from tpaa_metric.m3_air_operators import M3_AIR_OPERATOR_IMPLEMENTATIONS
from tpaa_metric.operators import median


def mad_v1(values: Sequence[float]) -> float:
    """Return median absolute deviation over validity-filtered finite samples."""

    if not values:
        raise ValueError("M3_DL_MAD_EMPTY")
    numbers = tuple(float(value) for value in values)
    if any(not math.isfinite(value) for value in numbers):
        raise ValueError("M3_DL_MAD_NONFINITE")
    center = median(numbers)
    return median(tuple(abs(value - center) for value in numbers))


_overlay: dict[str, Callable[..., object]] = dict(M3_AIR_OPERATOR_IMPLEMENTATIONS)
_overlay["MAD_V1"] = mad_v1

M3_DATALINK_OPERATOR_IMPLEMENTATIONS: Mapping[
    str,
    Callable[..., object],
] = MappingProxyType(_overlay)
