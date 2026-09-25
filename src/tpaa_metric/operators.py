"""Frozen numerical operators used by the M1 representative Metric slice."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class TimedValue:
    session_time_us: int
    value: float


def split_validity_pieces(
    values: Sequence[TimedValue],
    *,
    max_gap_us: int,
) -> tuple[tuple[TimedValue, ...], ...]:
    """Split ordered finite values at every governed max-gap boundary."""

    if not values:
        return ()
    pieces: list[list[TimedValue]] = [[values[0]]]
    for previous, current in zip(values, values[1:], strict=False):
        gap = current.session_time_us - previous.session_time_us
        if gap <= 0:
            raise ValueError("M1_METRIC_TIME_NOT_STRICTLY_INCREASING")
        if gap > max_gap_us:
            pieces.append([])
        pieces[-1].append(current)
    return tuple(tuple(piece) for piece in pieces)


def unwrap_angles(values: Sequence[TimedValue]) -> tuple[TimedValue, ...]:
    """Unwrap radians by selecting the nearest continuous 2*pi branch."""

    if not values:
        return ()
    result = [values[0]]
    offset = 0.0
    previous_raw = values[0].value
    for item in values[1:]:
        delta = item.value - previous_raw
        if delta > math.pi:
            offset -= 2.0 * math.pi
        elif delta < -math.pi:
            offset += 2.0 * math.pi
        result.append(TimedValue(item.session_time_us, item.value + offset))
        previous_raw = item.value
    return tuple(result)


def derivative_lls(
    values: Sequence[TimedValue],
    *,
    derivative_window_s: float,
    max_gap_us: int,
) -> tuple[TimedValue, ...]:
    """Apply governed DERIVATIVE_LLS_V1 inside each validity piece."""

    half_window_us = int(derivative_window_s * 1_000_000.0 / 2.0)
    derivatives: list[TimedValue] = []
    for piece in split_validity_pieces(values, max_gap_us=max_gap_us):
        for center in piece:
            window = tuple(
                item
                for item in piece
                if abs(item.session_time_us - center.session_time_us) <= half_window_us
            )
            if len({item.session_time_us for item in window}) < 3:
                continue
            origin = window[0].session_time_us
            times = tuple((item.session_time_us - origin) / 1_000_000.0 for item in window)
            mean_t = sum(times) / len(times)
            mean_y = sum(item.value for item in window) / len(window)
            denominator = sum((time - mean_t) ** 2 for time in times)
            if denominator == 0.0:
                continue
            numerator = sum(
                (time - mean_t) * (item.value - mean_y)
                for time, item in zip(times, window, strict=True)
            )
            derivatives.append(TimedValue(center.session_time_us, numerator / denominator))
    return tuple(derivatives)


def median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    count = len(ordered)
    if count == 0:
        raise ValueError("M1_METRIC_MEDIAN_EMPTY")
    middle = count // 2
    if count % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _covered_duration_us(
    values: Sequence[TimedValue],
    *,
    start_us: int,
    end_us: int,
) -> int:
    covered = 0
    for index, item in enumerate(values):
        support_start = max(start_us, item.session_time_us)
        support_end = (
            values[index + 1].session_time_us if index + 1 < len(values) else end_us
        )
        support_end = min(end_us, support_end)
        if support_end > support_start:
            covered += support_end - support_start
    return covered


def rolling_medians(
    values: Sequence[TimedValue],
    *,
    duration_s: float,
    min_coverage: float,
    max_gap_us: int,
    window_start_us: int,
    window_end_us: int,
) -> tuple[tuple[TimedValue, int, int], ...]:
    """Apply governed centered ROLLING_MEDIAN_V1 inside each validity piece."""

    duration_us = int(duration_s * 1_000_000.0)
    if duration_us <= 0:
        raise ValueError("M1_METRIC_ROLLING_DURATION_INVALID")
    if not 0.0 < min_coverage <= 1.0:
        raise ValueError("M1_METRIC_ROLLING_COVERAGE_INVALID")
    if window_end_us <= window_start_us:
        raise ValueError("M1_METRIC_ROLLING_WINDOW_INVALID")

    half_window_us = duration_us // 2
    outputs: list[tuple[TimedValue, int, int]] = []
    for piece in split_validity_pieces(values, max_gap_us=max_gap_us):
        for center in piece:
            requested_start = center.session_time_us - half_window_us
            requested_end = requested_start + duration_us
            clipped_start = max(window_start_us, requested_start)
            clipped_end = min(window_end_us, requested_end)
            if clipped_end <= clipped_start:
                continue
            covered_duration_us = _covered_duration_us(
                piece,
                start_us=clipped_start,
                end_us=clipped_end,
            )
            coverage = covered_duration_us / duration_us
            if coverage < min_coverage:
                continue
            window = tuple(
                item
                for item in piece
                if clipped_start <= item.session_time_us < clipped_end
            )
            if not window:
                continue
            outputs.append(
                (
                    TimedValue(center.session_time_us, median([item.value for item in window])),
                    clipped_start,
                    clipped_end,
                )
            )
    return tuple(outputs)


def quantile_hf7(values: Sequence[float], probability: float) -> float:
    """Return Hyndman-Fan type 7 sample quantile."""

    if not values:
        raise ValueError("M1_METRIC_QUANTILE_EMPTY")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("M1_METRIC_QUANTILE_PROBABILITY_INVALID")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * probability
    lower = math.floor(index)
    upper = math.ceil(index)
    fraction = index - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])
