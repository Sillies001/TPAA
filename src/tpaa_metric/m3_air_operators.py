"""M3 AIR numerical operators frozen by the P1 Metric Catalog.

The M2 operator map is intentionally left unchanged.  This module overlays only
AIR-owned M3 operators while retaining fail-closed sentinels for M3 operators
owned by later family tasks.
"""

from __future__ import annotations

import cmath
import math
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType

from tpaa_metric.m3_general_engine import M3_CONTRACT_OPERATOR_IMPLEMENTATIONS
from tpaa_metric.operators import TimedValue, median, rolling_medians, split_validity_pieces


def rolling_median_v1(
    values: Sequence[TimedValue],
    *,
    sustain_duration_s: float,
    min_coverage: float,
    max_gap_us: int,
) -> tuple[tuple[TimedValue, int, int], ...]:
    """Apply the frozen centered rolling-median contract inside validity pieces."""

    if not values:
        return ()
    return rolling_medians(
        values,
        duration_s=sustain_duration_s,
        min_coverage=min_coverage,
        max_gap_us=max_gap_us,
        window_start_us=values[0].session_time_us,
        window_end_us=values[-1].session_time_us + 1,
    )


def geodesic_pair_rate_v1(
    vectors: Sequence[tuple[float, float, float]],
    times_us: Sequence[int],
    *,
    max_gap_us: int,
) -> tuple[TimedValue, ...]:
    """Compute unsmoothed geodesic rates for consecutive unit-vector pairs."""

    if len(vectors) != len(times_us):
        raise ValueError("M3_AIR_GEODESIC_LENGTH_MISMATCH")
    if max_gap_us <= 0:
        raise ValueError("M3_AIR_GEODESIC_GAP_INVALID")
    result: list[TimedValue] = []
    for index in range(1, len(vectors)):
        dt_us = times_us[index] - times_us[index - 1]
        if dt_us <= 0:
            raise ValueError("M3_AIR_GEODESIC_TIME_NOT_STRICTLY_INCREASING")
        if dt_us > max_gap_us:
            continue
        left = vectors[index - 1]
        right = vectors[index]
        left_norm = math.sqrt(sum(item * item for item in left))
        right_norm = math.sqrt(sum(item * item for item in right))
        if left_norm == 0.0 or right_norm == 0.0:
            raise ValueError("M3_AIR_GEODESIC_ZERO_VECTOR")
        a = tuple(item / left_norm for item in left)
        b = tuple(item / right_norm for item in right)
        cross = (
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        )
        cross_norm = math.sqrt(sum(item * item for item in cross))
        dot = max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b, strict=True))))
        theta = math.atan2(cross_norm, dot)
        result.append(TimedValue(times_us[index], theta / (dt_us / 1_000_000.0)))
    return tuple(result)


def theil_sen_gain_v1(
    command: Sequence[float],
    response: Sequence[float],
    *,
    min_unique_command_levels: int,
) -> float:
    """Return the median slope between distinct eligible command levels."""

    if len(command) != len(response):
        raise ValueError("M3_AIR_THEIL_SEN_LENGTH_MISMATCH")
    if min_unique_command_levels < 2:
        raise ValueError("M3_AIR_THEIL_SEN_MIN_LEVELS_INVALID")
    if len(set(command)) < min_unique_command_levels:
        raise ValueError("M3_AIR_THEIL_SEN_COMMAND_LEVELS_INSUFFICIENT")
    slopes: list[float] = []
    for left in range(len(command)):
        for right in range(left + 1, len(command)):
            delta_command = command[right] - command[left]
            if delta_command == 0.0:
                continue
            slope = (response[right] - response[left]) / delta_command
            if math.isfinite(slope):
                slopes.append(slope)
    if not slopes:
        raise ValueError("M3_AIR_THEIL_SEN_SLOPES_INSUFFICIENT")
    return median(slopes)


def _pair_conjugate_poles(
    poles: Sequence[complex],
) -> tuple[tuple[complex, complex], ...]:
    remaining = list(poles)
    pairs: list[tuple[complex, complex]] = []
    while remaining:
        first = remaining.pop(0)
        if not remaining:
            raise ValueError("M3_AIR_BANDPASS_POLE_PAIRING_INVALID")
        match_index = min(
            range(len(remaining)),
            key=lambda index: abs(remaining[index] - first.conjugate()),
        )
        second = remaining.pop(match_index)
        if abs(second - first.conjugate()) > 1e-9:
            raise ValueError("M3_AIR_BANDPASS_POLE_PAIRING_INVALID")
        pairs.append((first, second))
    return tuple(pairs)


def _sos_frequency_response(
    sections: Sequence[tuple[float, float, float, float, float]],
    omega: float,
) -> complex:
    z1 = cmath.exp(-1j * omega)
    z2 = z1 * z1
    response = 1.0 + 0.0j
    for b0, b1, b2, a1, a2 in sections:
        response *= (b0 + b1 * z1 + b2 * z2) / (1.0 + a1 * z1 + a2 * z2)
    return response


def _design_bandpass_sos(
    *,
    low_hz: float,
    high_hz: float,
    sample_rate_hz: float,
) -> tuple[tuple[float, float, float, float, float], ...]:
    if not (0.0 < low_hz < high_hz < sample_rate_hz / 2.0):
        raise ValueError("M3_AIR_BANDPASS_FREQUENCY_INVALID")

    warp_low = 2.0 * sample_rate_hz * math.tan(math.pi * low_hz / sample_rate_hz)
    warp_high = 2.0 * sample_rate_hz * math.tan(math.pi * high_hz / sample_rate_hz)
    bandwidth = warp_high - warp_low
    center = math.sqrt(warp_low * warp_high)
    analog_poles: list[complex] = []
    order = 4
    for index in range(order):
        angle = math.pi * (2 * index + 1 + order) / (2 * order)
        prototype = cmath.exp(1j * angle)
        discriminant = cmath.sqrt((bandwidth * prototype) ** 2 - 4.0 * center**2)
        analog_poles.extend(
            (
                (bandwidth * prototype + discriminant) / 2.0,
                (bandwidth * prototype - discriminant) / 2.0,
            )
        )
    digital_poles = tuple(
        (2.0 * sample_rate_hz + pole) / (2.0 * sample_rate_hz - pole)
        for pole in analog_poles
    )
    sections: list[tuple[float, float, float, float, float]] = []
    for first, second in _pair_conjugate_poles(digital_poles):
        a1 = float(-(first + second).real)
        a2 = float((first * second).real)
        sections.append((1.0, 0.0, -1.0, a1, a2))

    center_hz = sample_rate_hz / math.pi * math.atan(center / (2.0 * sample_rate_hz))
    omega = 2.0 * math.pi * center_hz / sample_rate_hz
    gain = abs(_sos_frequency_response(sections, omega))
    if not math.isfinite(gain) or gain == 0.0:
        raise ValueError("M3_AIR_BANDPASS_GAIN_INVALID")
    b0, b1, b2, a1, a2 = sections[0]
    sections[0] = (b0 / gain, b1 / gain, b2 / gain, a1, a2)
    return tuple(sections)


def _sos_filter(
    values: Sequence[float],
    sections: Sequence[tuple[float, float, float, float, float]],
) -> list[float]:
    output = list(values)
    for b0, b1, b2, a1, a2 in sections:
        state1 = 0.0
        state2 = 0.0
        stage: list[float] = []
        for value in output:
            current = b0 * value + state1
            state1 = b1 * value - a1 * current + state2
            state2 = b2 * value - a2 * current
            stage.append(current)
        output = stage
    return output


def _uniform_resample_piece(
    piece: Sequence[TimedValue],
    *,
    sample_rate_hz: float,
) -> tuple[float, ...]:
    if len(piece) < 2:
        return ()
    first = float(piece[0].session_time_us)
    last = float(piece[-1].session_time_us)
    step_us = 1_000_000.0 / sample_rate_hz
    count = math.floor((last - first) / step_us) + 1
    values: list[float] = []
    right_index = 1
    for index in range(count):
        sample_time = first + index * step_us
        while (
            right_index < len(piece) - 1
            and float(piece[right_index].session_time_us) < sample_time
        ):
            right_index += 1
        left = piece[right_index - 1]
        right = piece[right_index]
        if sample_time == float(left.session_time_us):
            values.append(left.value)
            continue
        if sample_time == float(right.session_time_us):
            values.append(right.value)
            continue
        span = right.session_time_us - left.session_time_us
        if span <= 0:
            raise ValueError("M3_AIR_BANDPASS_TIME_NOT_STRICTLY_INCREASING")
        fraction = (sample_time - left.session_time_us) / span
        values.append(left.value + fraction * (right.value - left.value))
    return tuple(values)


def _odd_reflect(values: Sequence[float], pad_count: int) -> list[float]:
    if pad_count <= 0:
        return list(values)
    if len(values) <= pad_count:
        raise ValueError("M3_AIR_BANDPASS_PADDING_INSUFFICIENT")
    left = [2.0 * values[0] - values[index] for index in range(pad_count, 0, -1)]
    right = [
        2.0 * values[-1] - values[-2 - index]
        for index in range(pad_count)
    ]
    return left + list(values) + right


def bandpass_butterworth4_zp_v1(
    values: Sequence[TimedValue],
    *,
    low_hz: float,
    high_hz: float,
    min_window_s: float,
    min_coverage: float,
    max_gap_us: int,
    resample_rate_hz: float,
    filter_padding_s: float,
) -> tuple[float, ...]:
    """Apply the frozen fourth-order zero-phase Butterworth band-pass contract."""

    if min_window_s <= 0.0 or not 0.0 < min_coverage <= 1.0:
        raise ValueError("M3_AIR_BANDPASS_WINDOW_INVALID")
    if max_gap_us <= 0 or resample_rate_hz <= 0.0 or filter_padding_s < 0.0:
        raise ValueError("M3_AIR_BANDPASS_PROFILE_INVALID")
    sections = _design_bandpass_sos(
        low_hz=low_hz,
        high_hz=high_hz,
        sample_rate_hz=resample_rate_hz,
    )
    pad_count = math.ceil(filter_padding_s * resample_rate_hz)
    minimum_samples = math.ceil(min_window_s * resample_rate_hz)
    filtered: list[float] = []
    for piece in split_validity_pieces(values, max_gap_us=max_gap_us):
        if len(piece) < 2:
            continue
        duration_us = piece[-1].session_time_us - piece[0].session_time_us
        if duration_us < min_window_s * 1_000_000.0:
            continue
        covered_us = sum(
            current.session_time_us - previous.session_time_us
            for previous, current in zip(piece, piece[1:], strict=False)
        )
        if duration_us <= 0 or covered_us / duration_us < min_coverage:
            continue
        grid = _uniform_resample_piece(piece, sample_rate_hz=resample_rate_hz)
        if len(grid) < minimum_samples or len(grid) <= pad_count:
            continue
        padded = _odd_reflect(grid, pad_count)
        forward = _sos_filter(padded, sections)
        reverse = _sos_filter(tuple(reversed(forward)), sections)
        zero_phase = list(reversed(reverse))
        if pad_count:
            zero_phase = zero_phase[pad_count:-pad_count]
        if any(not math.isfinite(item) for item in zero_phase):
            raise ValueError("M3_AIR_BANDPASS_NONFINITE")
        filtered.extend(zero_phase)
    return tuple(filtered)


_overlay: dict[str, Callable[..., object]] = dict(M3_CONTRACT_OPERATOR_IMPLEMENTATIONS)
_overlay.update(
    {
        "BANDPASS_BUTTERWORTH4_ZP_V1": bandpass_butterworth4_zp_v1,
        "GEODESIC_PAIR_RATE_V1": geodesic_pair_rate_v1,
        "ROLLING_MEDIAN_V1": rolling_median_v1,
        "THEIL_SEN_GAIN_V1": theil_sen_gain_v1,
    }
)
M3_AIR_OPERATOR_IMPLEMENTATIONS: Mapping[str, Callable[..., object]] = MappingProxyType(
    _overlay
)
