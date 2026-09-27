"""M3 fusion numerical operators frozen by the P1 Metric Catalog.

The qualified M2 operator map remains immutable. This module extends the M3
operator overlay only with CV_PROPAGATION_V1 for P1-FUS-008.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType

from tpaa_metric.m3_datalink_operators import M3_DATALINK_OPERATOR_IMPLEMENTATIONS


def cv_propagation_v1(
    position: Sequence[float],
    velocity: Sequence[float],
    *,
    start_time_us: int,
    end_time_us: int,
    max_propagation_age_us: int,
) -> tuple[float, float, float]:
    """Propagate a 3D position with constant velocity inside the frozen age cap."""

    if len(position) != 3 or len(velocity) != 3:
        raise ValueError("M3_FUS_CV_VECTOR_INVALID")
    if max_propagation_age_us <= 0:
        raise ValueError("M3_FUS_CV_MAX_AGE_INVALID")
    age_us = end_time_us - start_time_us
    if age_us < 0:
        raise ValueError("M3_FUS_CV_TIME_REVERSED")
    if age_us > max_propagation_age_us:
        raise ValueError("M3_FUS_CV_AGE_EXCEEDED")
    values = tuple(float(item) for item in (*position, *velocity))
    if any(not math.isfinite(item) for item in values):
        raise ValueError("M3_FUS_CV_VECTOR_NONFINITE")
    dt_s = age_us / 1_000_000.0
    return tuple(
        float(position[index]) + float(velocity[index]) * dt_s
        for index in range(3)
    )


_overlay: dict[str, Callable[..., object]] = dict(
    M3_DATALINK_OPERATOR_IMPLEMENTATIONS
)
_overlay["CV_PROPAGATION_V1"] = cv_propagation_v1

M3_FUSION_OPERATOR_IMPLEMENTATIONS: Mapping[
    str,
    Callable[..., object],
] = MappingProxyType(_overlay)
