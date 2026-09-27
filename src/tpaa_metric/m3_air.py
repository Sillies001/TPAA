"""M3-MET-002 Catalog plugins for the exact P1 AIR remainder.

All 36 P1-AIR-004..039 algorithms execute through the shared
:class:`CatalogMetricEngine`.  Inputs are canonical, already-authorized series
or event products; this module does not perform source adaptation, persistence,
publication, or tactical inference.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType
from typing import cast

from tpaa_metric.catalog_engine import (
    CatalogMetricEngineError,
    M2MetricExecutionPlan,
    M2MetricPlugin,
    M2MetricPluginRequest,
    MetricPluginRegistry,
)
from tpaa_metric.operators import (
    TimedValue,
    quantile_hf7,
    split_validity_pieces,
    unwrap_angles,
)
from tpaa_metric.operators import (
    median as governed_median,
)
from tpaa_metric.operators import (
    rms as governed_rms,
)

M3_AIR_CODES = tuple(f"P1-AIR-{index:03d}" for index in range(4, 40))
M3_AIR_STRUCTURED_CODES = (
    "P1-AIR-007",
    "P1-AIR-019",
    "P1-AIR-025",
    "P1-AIR-030",
    "P1-AIR-035",
    "P1-AIR-039",
)
M3_AIR_FAMILY_COUNTS: Mapping[str, int] = MappingProxyType(
    {
        "AIRCRAFT_FLIGHT": 17,
        "AIRCRAFT_ENERGY": 8,
        "AIRCRAFT_CONTROL_RESPONSE": 4,
        "AIRCRAFT_HANDLING": 4,
        "AIRCRAFT_PERSISTENCE": 3,
    }
)

G0_MPS2 = 9.80665
ENERGY_DENOM_EPS_J_PER_KG = 0.000001
ENERGY_RATE_EPS_W_PER_KG = 1e-9
FUEL_BURN_RATE_EPS_KG_S = 1e-9


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"M3_AIR_INPUT_INVALID:{field}")
    return cast(Mapping[str, object], value)


def _mappings(value: object, *, field: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"M3_AIR_INPUT_INVALID:{field}")
    return tuple(_mapping(item, field=f"{field}[{index}]") for index, item in enumerate(value))


def _text(mapping: Mapping[str, object], name: str, *, field: str) -> str:
    value = mapping.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"M3_AIR_INPUT_INVALID:{field}.{name}")
    return value


def _integer(mapping: Mapping[str, object], name: str, *, field: str) -> int:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"M3_AIR_INPUT_INVALID:{field}.{name}")
    return value


def _finite(mapping: Mapping[str, object], name: str, *, field: str) -> float:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"M3_AIR_INPUT_INVALID:{field}.{name}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"M3_AIR_INPUT_NONFINITE:{field}.{name}")
    return result


def _profile(payload: Mapping[str, object]) -> Mapping[str, object]:
    return _mapping(payload.get("profile"), field="profile")


def _profile_float(payload: Mapping[str, object], name: str) -> float:
    return _finite(_profile(payload), name, field="profile")


def _profile_int(payload: Mapping[str, object], name: str) -> int:
    return _integer(_profile(payload), name, field="profile")


def _series(
    payload: Mapping[str, object],
    name: str,
    *,
    value_name: str = "value",
    allow_empty: bool = False,
) -> tuple[TimedValue, ...]:
    rows = _mappings(payload.get(name), field=name)
    output: list[TimedValue] = []
    previous: int | None = None
    for index, row in enumerate(rows):
        field = f"{name}[{index}]"
        session_time_us = _integer(row, "session_time_us", field=field)
        value = _finite(row, value_name, field=field)
        if previous is not None and session_time_us <= previous:
            raise ValueError(f"M3_AIR_TIME_NOT_STRICTLY_INCREASING:{name}")
        previous = session_time_us
        output.append(TimedValue(session_time_us, value))
    if not output and not allow_empty:
        raise ValueError(f"M3_AIR_SERIES_EMPTY:{name}")
    return tuple(output)


def _optional_series(
    payload: Mapping[str, object],
    name: str,
    *,
    value_name: str = "value",
) -> tuple[TimedValue, ...]:
    if name not in payload:
        return ()
    return _series(payload, name, value_name=value_name, allow_empty=True)


def _operator(request: M2MetricPluginRequest, operator_id: str) -> Callable[..., object]:
    value = request.operators.get(operator_id)
    if value is None:
        raise ValueError(f"M3_AIR_OPERATOR_MISSING:{operator_id}")
    return value


def _derivative(
    request: M2MetricPluginRequest,
    values: Sequence[TimedValue],
    *,
    derivative_window_s: float,
    max_gap_us: int,
) -> tuple[TimedValue, ...]:
    raw = _operator(request, "DERIVATIVE_LLS_V1")(
        values,
        derivative_window_s=derivative_window_s,
        max_gap_us=max_gap_us,
    )
    if not isinstance(raw, tuple) or not all(isinstance(item, TimedValue) for item in raw):
        raise ValueError("M3_AIR_DERIVATIVE_OUTPUT_INVALID")
    return cast(tuple[TimedValue, ...], raw)


def _rolling(
    request: M2MetricPluginRequest,
    values: Sequence[TimedValue],
    *,
    duration_s: float,
    min_coverage: float,
    max_gap_us: int,
) -> tuple[tuple[TimedValue, int, int], ...]:
    raw = _operator(request, "ROLLING_MEDIAN_V1")(
        values,
        sustain_duration_s=duration_s,
        min_coverage=min_coverage,
        max_gap_us=max_gap_us,
    )
    if not isinstance(raw, tuple):
        raise ValueError("M3_AIR_ROLLING_OUTPUT_INVALID")
    return cast(tuple[tuple[TimedValue, int, int], ...], raw)


def _scalar_operator(
    request: M2MetricPluginRequest,
    operator_id: str,
    values: Sequence[float],
    *args: object,
) -> float:
    raw = _operator(request, operator_id)(values, *args)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f"M3_AIR_OPERATOR_OUTPUT_INVALID:{operator_id}")
    result = float(raw)
    if not math.isfinite(result):
        raise ValueError(f"M3_AIR_OPERATOR_OUTPUT_NONFINITE:{operator_id}")
    return result


def _median(request: M2MetricPluginRequest, values: Sequence[float]) -> float:
    if "MEDIAN_V1" in request.operators:
        return _scalar_operator(request, "MEDIAN_V1", values)
    return governed_median(values)


def _quantile(
    request: M2MetricPluginRequest,
    values: Sequence[float],
    probability: float,
) -> float:
    if "QUANTILE_HF7_V1" in request.operators:
        return _scalar_operator(request, "QUANTILE_HF7_V1", values, probability)
    return quantile_hf7(values, probability)


def _rms(request: M2MetricPluginRequest, values: Sequence[float]) -> float:
    if "RMS_V1" in request.operators:
        return _scalar_operator(request, "RMS_V1", values)
    return governed_rms(values)


def _instance(
    request: M2MetricPluginRequest,
    *,
    status: str,
    reason_codes: Sequence[str] = (),
    value_numeric: float | None = None,
    value_structured: Mapping[str, object] | None = None,
    evidence: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return {
        "status": status,
        "reason_codes": list(reason_codes),
        "value_kind": request.definition.value_kind,
        "value_numeric": value_numeric,
        "value_structured": None if value_structured is None else dict(value_structured),
        "evidence": {} if evidence is None else dict(evidence),
    }


def _output(
    request: M2MetricPluginRequest,
    instance: Mapping[str, object],
) -> dict[str, object]:
    return {
        "metric_code": request.definition.metric_code,
        "subject_type": request.definition.subject_type,
        "observation_lane": request.definition.observation_lane,
        "publication_route": request.definition.publication_route,
        "applicable": True,
        "instances": [dict(instance)],
    }


def _valid_numeric(
    request: M2MetricPluginRequest,
    value: float,
    *,
    evidence: Mapping[str, object] | None = None,
) -> Mapping[str, object]:
    if not math.isfinite(value):
        raise ValueError("M3_AIR_VALID_VALUE_NONFINITE")
    return _output(
        request,
        _instance(request, status="VALID", value_numeric=value, evidence=evidence),
    )


def _valid_structured(
    request: M2MetricPluginRequest,
    value: Mapping[str, object],
    *,
    evidence: Mapping[str, object] | None = None,
) -> Mapping[str, object]:
    return _output(
        request,
        _instance(request, status="VALID", value_structured=value, evidence=evidence),
    )


def _missing(
    request: M2MetricPluginRequest,
    reason: str,
    *,
    status: str = "INSUFFICIENT_DATA",
    evidence: Mapping[str, object] | None = None,
) -> Mapping[str, object]:
    return _output(
        request,
        _instance(
            request,
            status=status,
            reason_codes=(reason,),
            evidence=evidence,
        ),
    )


def _guard(request: M2MetricPluginRequest) -> None:
    definition = request.definition
    code = definition.metric_code
    if (
        code not in M3_AIR_CODES
        or definition.subject_type != "AIRCRAFT"
        or definition.observation_lane != "AIRCRAFT_CAP_L1_OBSERVATION"
        or definition.publication_route != "CAPABILITY_OBSERVATION"
    ):
        raise ValueError(f"M3_AIR_CATALOG_DEFINITION_DRIFT:{code}")
    expected_structured = code in M3_AIR_STRUCTURED_CODES
    if expected_structured != (definition.value_kind == "STRUCTURED"):
        raise ValueError(f"M3_AIR_VALUE_KIND_DRIFT:{code}")
    if expected_structured and definition.structured_output_schema_id is None:
        raise ValueError(f"M3_AIR_STRUCTURED_SCHEMA_DRIFT:{code}")
    if not expected_structured and (
        definition.value_kind != "NUMERIC" or definition.structured_output_schema_id is not None
    ):
        raise ValueError(f"M3_AIR_NUMERIC_SCHEMA_DRIFT:{code}")


def _rolling_peak(
    request: M2MetricPluginRequest,
    values: Sequence[TimedValue],
    *,
    duration_s: float,
    min_coverage: float,
    max_gap_us: int,
) -> tuple[float, tuple[int, int]] | None:
    windows = _rolling(
        request,
        values,
        duration_s=duration_s,
        min_coverage=min_coverage,
        max_gap_us=max_gap_us,
    )
    if not windows:
        return None
    best = max(windows, key=lambda item: item[0].value)
    return best[0].value, (best[1], best[2])


def _series_map(values: Sequence[TimedValue]) -> dict[int, float]:
    return {item.session_time_us: item.value for item in values}


def _paired_series(
    left: Sequence[TimedValue],
    right: Sequence[TimedValue],
) -> tuple[tuple[int, float, float], ...]:
    right_by_time = _series_map(right)
    return tuple(
        (item.session_time_us, item.value, right_by_time[item.session_time_us])
        for item in left
        if item.session_time_us in right_by_time
    )


def _crossing_time_us(left: TimedValue, right: TimedValue, bound: float) -> float:
    if right.value == left.value:
        return float(right.session_time_us)
    fraction = (bound - left.value) / (right.value - left.value)
    return left.session_time_us + fraction * (right.session_time_us - left.session_time_us)


def _band_elapsed(
    values: Sequence[TimedValue],
    *,
    first_bound: float,
    second_bound: float,
    upward: bool,
    max_gap_us: int,
) -> tuple[float, tuple[float, float]] | None:
    if first_bound >= second_bound:
        raise ValueError("M3_AIR_SPEED_BOUNDS_INVALID")
    for piece in split_validity_pieces(values, max_gap_us=max_gap_us):
        first_crossing: float | None = None
        for left, right in zip(piece, piece[1:], strict=False):
            if upward:
                crossed_first = left.value < first_bound <= right.value
                crossed_second = left.value < second_bound <= right.value
            else:
                crossed_first = left.value > second_bound >= right.value
                crossed_second = left.value > first_bound >= right.value
            if first_crossing is None and crossed_first:
                first_crossing = _crossing_time_us(
                    left,
                    right,
                    first_bound if upward else second_bound,
                )
            if first_crossing is not None and crossed_second:
                second_crossing = _crossing_time_us(
                    left,
                    right,
                    second_bound if upward else first_bound,
                )
                if second_crossing >= first_crossing:
                    return (
                        (second_crossing - first_crossing) / 1_000_000.0,
                        (first_crossing, second_crossing),
                    )
    return None


def _energy_series(payload: Mapping[str, object]) -> tuple[TimedValue, ...]:
    dependency = _optional_series(payload, "P1-AIR-016.specific_mechanical_energy")
    if dependency:
        return dependency
    tas = _series(payload, "tas_mps")
    altitude = _series(payload, "alt_msl_m")
    return tuple(
        TimedValue(time, G0_MPS2 * height + 0.5 * speed * speed)
        for time, speed, height in _paired_series(tas, altitude)
    )


def _identity_guard(payload: Mapping[str, object], prefix: str) -> None:
    for suffix in ("id", "version", "hash"):
        _text(payload, f"{prefix}_{suffix}", field=prefix)


def _persistent_sample_time(
    values: Sequence[TimedValue],
    *,
    threshold: float,
    persistence_s: float,
    max_gap_us: int,
    sign: float = 1.0,
    start_us: int | None = None,
    end_us: int | None = None,
) -> int | None:
    if persistence_s < 0.0:
        raise ValueError("M3_AIR_PERSISTENCE_INVALID")
    required_us = int(persistence_s * 1_000_000.0)
    for piece in split_validity_pieces(values, max_gap_us=max_gap_us):
        for index, item in enumerate(piece):
            if start_us is not None and item.session_time_us < start_us:
                continue
            if end_us is not None and item.session_time_us > end_us:
                break
            if sign * item.value < threshold:
                continue
            target_us = item.session_time_us + required_us
            last_time = item.session_time_us
            eligible = True
            for following in piece[index:]:
                if end_us is not None and following.session_time_us > end_us:
                    break
                if following.session_time_us > target_us:
                    break
                if sign * following.value < threshold:
                    eligible = False
                    break
                last_time = following.session_time_us
            if eligible and last_time >= target_us:
                return item.session_time_us
    return None


def _air004(request: M2MetricPluginRequest) -> Mapping[str, object]:
    values = _series(request.input_payload, "P1-AIR-003.heading_rate_rad_s")
    peak = _rolling_peak(
        request,
        values,
        duration_s=_profile_float(request.input_payload, "sustain_duration_s"),
        min_coverage=_profile_float(request.input_payload, "min_coverage"),
        max_gap_us=_profile_int(request.input_payload, "max_gap_us"),
    )
    if peak is None:
        return _missing(request, "INSUFFICIENT_CONTINUOUS_DURATION")
    return _valid_numeric(
        request,
        peak[0],
        evidence={"support_interval_us": list(peak[1])},
    )


def _air005(request: M2MetricPluginRequest) -> Mapping[str, object]:
    speed = _series(request.input_payload, "ground_speed_mps")
    track = unwrap_angles(_series(request.input_payload, "track_true_rad"))
    derivative = _derivative(
        request,
        track,
        derivative_window_s=_profile_float(request.input_payload, "derivative_window_s"),
        max_gap_us=_profile_int(request.input_payload, "max_gap_us"),
    )
    speed_by_time = _series_map(speed)
    threshold = _profile_float(request.input_payload, "min_turn_rate_rad_s")
    radii = [
        speed_by_time[item.session_time_us] / abs(item.value)
        for item in derivative
        if item.session_time_us in speed_by_time and abs(item.value) >= threshold
    ]
    if not radii:
        return _missing(request, "NO_VALID_TURN_INTERVAL")
    return _valid_numeric(
        request,
        _median(request, radii),
        evidence={"minimum_radius_m": min(radii), "eligible_count": len(radii)},
    )


def _air006(request: M2MetricPluginRequest) -> Mapping[str, object]:
    peak = _rolling_peak(
        request,
        _series(request.input_payload, "nz_g"),
        duration_s=_profile_float(request.input_payload, "sustain_duration_s"),
        min_coverage=_profile_float(request.input_payload, "min_coverage"),
        max_gap_us=_profile_int(request.input_payload, "max_gap_us"),
    )
    if peak is None:
        return _missing(request, "INSUFFICIENT_VALID_DWELL")
    return _valid_numeric(
        request,
        peak[0],
        evidence={"support_interval_us": list(peak[1])},
    )


def _envelope_channel(
    request: M2MetricPluginRequest,
    values: Sequence[TimedValue],
    *,
    suffix: str,
) -> dict[str, object]:
    if not values:
        fields = {
            f"min{suffix}": None,
            f"max{suffix}": None,
            f"p05{suffix}": None,
            f"p50{suffix}": None,
            f"p95{suffix}": None,
        }
        return {"status": "INSUFFICIENT_DATA", "n": 0, **fields}
    raw = [item.value for item in values]
    return {
        "status": "VALID",
        "n": len(raw),
        f"min{suffix}": min(raw),
        f"max{suffix}": max(raw),
        f"p05{suffix}": _quantile(request, raw, 0.05),
        f"p50{suffix}": _quantile(request, raw, 0.50),
        f"p95{suffix}": _quantile(request, raw, 0.95),
    }


def _air007(request: M2MetricPluginRequest) -> Mapping[str, object]:
    tas = _optional_series(request.input_payload, "tas_mps")
    mach = _optional_series(request.input_payload, "mach")
    structured = {
        "tas": _envelope_channel(request, tas, suffix="_mps"),
        "mach": _envelope_channel(request, mach, suffix=""),
    }
    if not tas and not mach:
        return _missing(
            request,
            "TAS_AND_MACH_INSUFFICIENT",
            status="N_A",
            evidence={"structured_preview": structured},
        )
    return _valid_structured(request, structured)


def _air008(request: M2MetricPluginRequest) -> Mapping[str, object]:
    derivative = _derivative(
        request,
        _series(request.input_payload, "tas_mps"),
        derivative_window_s=_profile_float(request.input_payload, "derivative_window_s"),
        max_gap_us=_profile_int(request.input_payload, "max_gap_us"),
    )
    if not derivative:
        return _missing(request, "DERIVATIVE_UNAVAILABLE")
    return _valid_numeric(request, max(item.value for item in derivative))


def _air009(request: M2MetricPluginRequest) -> Mapping[str, object]:
    derivative = _derivative(
        request,
        _series(request.input_payload, "tas_mps"),
        derivative_window_s=_profile_float(request.input_payload, "derivative_window_s"),
        max_gap_us=_profile_int(request.input_payload, "max_gap_us"),
    )
    if not derivative:
        return _missing(request, "DERIVATIVE_UNAVAILABLE")
    peak = _rolling_peak(
        request,
        derivative,
        duration_s=_profile_float(request.input_payload, "sustain_duration_s"),
        min_coverage=_profile_float(request.input_payload, "min_coverage"),
        max_gap_us=_profile_int(request.input_payload, "max_gap_us"),
    )
    if peak is None:
        return _missing(request, "NO_SUSTAINED_ACCELERATION_INTERVAL")
    return _valid_numeric(request, peak[0], evidence={"support_interval_us": list(peak[1])})


def _speed_band(
    request: M2MetricPluginRequest,
    *,
    upward: bool,
) -> Mapping[str, object]:
    result = _band_elapsed(
        _series(request.input_payload, "tas_mps"),
        first_bound=_profile_float(request.input_payload, "lower_speed_bound_mps"),
        second_bound=_profile_float(request.input_payload, "upper_speed_bound_mps"),
        upward=upward,
        max_gap_us=_profile_int(request.input_payload, "max_gap_us"),
    )
    if result is None:
        return _missing(request, "SPEED_BAND_CROSSING_UNRESOLVED", status="N_A")
    return _valid_numeric(
        request,
        result[0],
        evidence={"crossing_session_time_us": [str(item) for item in result[1]]},
    )


def _air010(request: M2MetricPluginRequest) -> Mapping[str, object]:
    return _speed_band(request, upward=True)


def _air011(request: M2MetricPluginRequest) -> Mapping[str, object]:
    derivative = _derivative(
        request,
        _series(request.input_payload, "tas_mps"),
        derivative_window_s=_profile_float(request.input_payload, "derivative_window_s"),
        max_gap_us=_profile_int(request.input_payload, "max_gap_us"),
    )
    negative = [item.value for item in derivative if item.value < 0.0]
    if not negative:
        return _missing(request, "NO_VALID_DECELERATION_INTERVAL")
    return _valid_numeric(request, abs(min(negative)))


def _air012(request: M2MetricPluginRequest) -> Mapping[str, object]:
    return _speed_band(request, upward=False)


def _air013(request: M2MetricPluginRequest) -> Mapping[str, object]:
    derivative = _derivative(
        request,
        _series(request.input_payload, "alt_msl_m"),
        derivative_window_s=_profile_float(request.input_payload, "derivative_window_s"),
        max_gap_us=_profile_int(request.input_payload, "max_gap_us"),
    )
    positive = [item.value for item in derivative if item.value > 0.0]
    if not positive:
        return _missing(request, "NO_POSITIVE_CLIMB_INTERVAL")
    evidence: dict[str, object] = {"derivative_count": len(derivative)}
    optional = _optional_series(request.input_payload, "vertical_speed_mps")
    if optional:
        evidence["vertical_speed_cross_check_count"] = len(optional)
    return _valid_numeric(request, max(positive), evidence=evidence)


def _air014(request: M2MetricPluginRequest) -> Mapping[str, object]:
    derivative = _derivative(
        request,
        _series(request.input_payload, "alt_msl_m"),
        derivative_window_s=_profile_float(request.input_payload, "derivative_window_s"),
        max_gap_us=_profile_int(request.input_payload, "max_gap_us"),
    )
    peak = _rolling_peak(
        request,
        derivative,
        duration_s=_profile_float(request.input_payload, "sustain_duration_s"),
        min_coverage=_profile_float(request.input_payload, "min_coverage"),
        max_gap_us=_profile_int(request.input_payload, "max_gap_us"),
    )
    if peak is None:
        return _missing(request, "NO_SUSTAINED_CLIMB_INTERVAL")
    return _valid_numeric(request, peak[0], evidence={"support_interval_us": list(peak[1])})


def _air015(request: M2MetricPluginRequest) -> Mapping[str, object]:
    max_gap = _profile_int(request.input_payload, "max_gap_us")
    window = _profile_float(request.input_payload, "derivative_window_s")
    tas_rate = _derivative(
        request,
        _series(request.input_payload, "tas_mps"),
        derivative_window_s=window,
        max_gap_us=max_gap,
    )
    alt_rate = _derivative(
        request,
        _series(request.input_payload, "alt_msl_m"),
        derivative_window_s=window,
        max_gap_us=max_gap,
    )
    threshold = _profile_float(request.input_payload, "min_descent_rate_mps")
    paired = [
        (time, tas_value, alt_value)
        for time, tas_value, alt_value in _paired_series(tas_rate, alt_rate)
        if alt_value <= -threshold
    ]
    if not paired:
        return _missing(request, "NO_VALID_DIVE_INTERVAL")
    intervals: list[list[int]] = []
    for time, _tas, _alt in paired:
        if not intervals or time - intervals[-1][1] > max_gap:
            intervals.append([time, time])
        else:
            intervals[-1][1] = time
    values = [item[1] for item in paired]
    return _valid_numeric(
        request,
        _quantile(request, values, 0.95),
        evidence={
            "dive_eligible_intervals": [
                {
                    "start_session_time_us": str(start),
                    "end_session_time_us": str(end),
                }
                for start, end in intervals
            ],
            "eligible_acceleration_count": len(values),
        },
    )


def _air016(request: M2MetricPluginRequest) -> Mapping[str, object]:
    values = _energy_series(request.input_payload)
    if not values:
        return _missing(request, "ENERGY_INPUTS_UNAVAILABLE")
    energies = [item.value for item in values]
    return _valid_numeric(
        request,
        _median(request, energies),
        evidence={
            "specific_mechanical_energy_series": [
                {"session_time_us": str(item.session_time_us), "value": item.value}
                for item in values
            ],
            "g0_mps2": G0_MPS2,
        },
    )


def _air017(request: M2MetricPluginRequest) -> Mapping[str, object]:
    derivative = _derivative(
        request,
        _energy_series(request.input_payload),
        derivative_window_s=_profile_float(request.input_payload, "derivative_window_s"),
        max_gap_us=_profile_int(request.input_payload, "max_gap_us"),
    )
    if not derivative:
        return _missing(request, "ENERGY_RATE_DERIVATIVE_UNAVAILABLE")
    values = [item.value for item in derivative]
    return _valid_numeric(
        request,
        _median(request, values),
        evidence={
            "specific_energy_rate_series": [
                {"session_time_us": str(item.session_time_us), "value": item.value}
                for item in derivative
            ]
        },
    )


def _air018(request: M2MetricPluginRequest) -> Mapping[str, object]:
    max_gap = _profile_int(request.input_payload, "max_gap_us")
    window = _profile_float(request.input_payload, "derivative_window_s")
    tas = _series(request.input_payload, "tas_mps")
    tas_rate = _derivative(request, tas, derivative_window_s=window, max_gap_us=max_gap)
    alt_rate = _derivative(
        request,
        _series(request.input_payload, "alt_msl_m"),
        derivative_window_s=window,
        max_gap_us=max_gap,
    )
    tas_by_time = _series_map(tas)
    rates: list[float] = []
    for time, d_tas, d_alt in _paired_series(tas_rate, alt_rate):
        speed = tas_by_time.get(time)
        if speed is not None:
            rates.append(d_alt + (speed / G0_MPS2) * d_tas)
    if not rates:
        return _missing(request, "SPECIFIC_EXCESS_POWER_UNAVAILABLE")
    return _valid_numeric(request, _median(request, rates), evidence={"sample_count": len(rates)})


def _air019(request: M2MetricPluginRequest) -> Mapping[str, object]:
    energy = _series(request.input_payload, "P1-AIR-016.specific_mechanical_energy")
    rate = _optional_series(request.input_payload, "P1-AIR-017.specific_energy_rate")
    start = _integer(request.input_payload, "window_start_us", field="P1-AIR-019")
    end = _integer(request.input_payload, "window_end_us", field="P1-AIR-019")
    energy_by_time = _series_map(energy)
    if start not in energy_by_time or end not in energy_by_time:
        return _missing(request, "ENERGY_ENDPOINT_UNAVAILABLE", status="N_A")
    start_energy = energy_by_time[start]
    end_energy = energy_by_time[end]
    if abs(start_energy) <= ENERGY_DENOM_EPS_J_PER_KG:
        return _missing(request, "ENERGY_DENOMINATOR_INELIGIBLE", status="N_A")
    interior = [item.value for item in rate if start < item.session_time_us < end]
    structured: dict[str, object] = {
        "retention_ratio": end_energy / start_energy,
        "delta_E_s_j_per_kg": end_energy - start_energy,
        "median_energy_rate_w_per_kg": (
            _median(request, interior) if interior else None
        ),
        "median_energy_rate_status": (
            "VALID" if interior else "INSUFFICIENT_RATE_SAMPLES"
        ),
    }
    return _valid_structured(request, structured)


def _air020(request: M2MetricPluginRequest) -> Mapping[str, object]:
    energy = _series(request.input_payload, "specific_mechanical_energy")
    maneuver_end = _integer(
        request.input_payload,
        "maneuver_end_time_us",
        field="P1-AIR-020",
    )
    reference = _finite(
        request.input_payload,
        "pre_event_reference_energy",
        field="P1-AIR-020",
    )
    minimum = _finite(
        request.input_payload,
        "post_event_min_energy",
        field="P1-AIR-020",
    )
    loss = reference - minimum
    if loss <= 0.0:
        return _missing(request, "NONPOSITIVE_ENERGY_LOSS", status="N_A")
    fraction = _profile_float(request.input_payload, "recovery_fraction")
    if not 0.0 < fraction <= 1.0:
        raise ValueError("M3_AIR_RECOVERY_FRACTION_INVALID")
    target = minimum + fraction * loss
    max_window_us = int(
        _profile_float(request.input_payload, "max_recovery_window_s") * 1_000_000.0
    )
    crossing = _persistent_sample_time(
        energy,
        threshold=target,
        persistence_s=_profile_float(request.input_payload, "min_crossing_persistence_s"),
        max_gap_us=_profile_int(request.input_payload, "max_gap_us"),
        start_us=maneuver_end,
        end_us=maneuver_end + max_window_us,
    )
    if crossing is None:
        return _missing(request, "RECOVERY_TARGET_NOT_REACHED", status="N_A")
    return _valid_numeric(
        request,
        (crossing - maneuver_end) / 1_000_000.0,
        evidence={"recovery_target_j_per_kg": target, "crossing_session_time_us": str(crossing)},
    )


def _air021(request: M2MetricPluginRequest) -> Mapping[str, object]:
    window = _mapping(request.input_payload.get("recovery_window"), field="recovery_window")
    if window.get("resolved") is not True:
        return _missing(request, "RECOVERY_WINDOW_UNRESOLVED", status="N_A")
    start = _integer(window, "start_session_time_us", field="recovery_window")
    end = _integer(window, "end_session_time_us", field="recovery_window")
    if end <= start:
        raise ValueError("M3_AIR_RECOVERY_WINDOW_INVALID")
    max_gap = _profile_int(request.input_payload, "max_gap_us")
    rates = _series(request.input_payload, "specific_energy_rate")
    positive: list[float] = []
    for piece in split_validity_pieces(rates, max_gap_us=max_gap):
        positive.extend(
            item.value for item in piece if start < item.session_time_us < end and item.value > 0.0
        )
    if not positive:
        return _missing(request, "NO_POSITIVE_RECOVERY_RATE")
    return _valid_numeric(request, _median(request, positive), evidence={"positive_count": len(positive)})


def _air022(request: M2MetricPluginRequest) -> Mapping[str, object]:
    values = tuple(
        TimedValue(item.session_time_us, abs(item.value))
        for item in _series(request.input_payload, "body_p_rad_s")
    )
    peak = _rolling_peak(
        request,
        values,
        duration_s=_profile_float(request.input_payload, "sustain_duration_s"),
        min_coverage=_profile_float(request.input_payload, "min_coverage"),
        max_gap_us=_profile_int(request.input_payload, "max_gap_us"),
    )
    if peak is None:
        return _missing(request, "NO_SUSTAINED_ROLL_INTERVAL")
    return _valid_numeric(request, peak[0], evidence={"support_interval_us": list(peak[1])})


def _air023(request: M2MetricPluginRequest) -> Mapping[str, object]:
    roll = _series(request.input_payload, "roll_rad")
    onset = _integer(request.input_payload, "roll_onset_time_us", field="P1-AIR-023")
    by_time = _series_map(roll)
    if onset not in by_time:
        return _missing(request, "ROLL_ONSET_UNRESOLVED", status="N_A")
    baseline = by_time[onset]
    delta = _profile_float(request.input_payload, "bank_delta_rad")
    tolerance = _profile_float(request.input_payload, "bank_tolerance_rad")
    persistence_us = int(
        _profile_float(request.input_payload, "achievement_persistence_s") * 1_000_000.0
    )
    max_gap = _profile_int(request.input_payload, "max_gap_us")
    for piece in split_validity_pieces(roll, max_gap_us=max_gap):
        if not piece or not (piece[0].session_time_us <= onset <= piece[-1].session_time_us):
            continue
        for index, item in enumerate(piece):
            if item.session_time_us < onset or abs(item.value - baseline) < delta:
                continue
            sign = 1.0 if item.value >= baseline else -1.0
            target = baseline + sign * delta
            end_target = item.session_time_us + persistence_us
            last = item.session_time_us
            stable = True
            for following in piece[index:]:
                if following.session_time_us > end_target:
                    break
                if abs(following.value - target) > tolerance:
                    stable = False
                    break
                last = following.session_time_us
            if stable and last >= end_target:
                return _valid_numeric(
                    request,
                    (item.session_time_us - onset) / 1_000_000.0,
                    evidence={"target_bank_rad": target},
                )
    return _missing(request, "BANK_CHANGE_NOT_ACHIEVED", status="N_A")


def _rotate_boresight(row: Mapping[str, object], *, field: str) -> tuple[float, float, float]:
    w = _finite(row, "w", field=field)
    x = _finite(row, "x", field=field)
    y = _finite(row, "y", field=field)
    z = _finite(row, "z", field=field)
    norm = math.sqrt(w * w + x * x + y * y + z * z)
    if norm == 0.0:
        raise ValueError("M3_AIR_QUATERNION_ZERO")
    w, x, y, z = w / norm, x / norm, y / norm, z / norm
    return (
        1.0 - 2.0 * (y * y + z * z),
        2.0 * (x * y + w * z),
        2.0 * (x * z - w * y),
    )


def _air024(request: M2MetricPluginRequest) -> Mapping[str, object]:
    rows = _mappings(request.input_payload.get("attitude_quat"), field="attitude_quat")
    vectors: list[tuple[float, float, float]] = []
    times: list[int] = []
    previous: int | None = None
    for index, row in enumerate(rows):
        field = f"attitude_quat[{index}]"
        session_time = _integer(row, "session_time_us", field=field)
        if previous is not None and session_time <= previous:
            raise ValueError("M3_AIR_QUATERNION_TIME_INVALID")
        previous = session_time
        times.append(session_time)
        vectors.append(_rotate_boresight(row, field=field))
    raw = _operator(request, "GEODESIC_PAIR_RATE_V1")(
        vectors,
        times,
        max_gap_us=_profile_int(request.input_payload, "max_gap_us"),
    )
    rates = cast(tuple[TimedValue, ...], raw)
    if not rates:
        return _missing(request, "NO_ELIGIBLE_GEODESIC_PAIR", status="N_A")
    values = [item.value for item in rates]
    return _valid_numeric(
        request,
        _quantile(request, values, 0.95),
        evidence={"pair_rate_count": len(values)},
    )


def _air025(request: M2MetricPluginRequest) -> Mapping[str, object]:
    aoa = _optional_series(request.input_payload, "aoa_rad")
    if not aoa:
        return _missing(request, "AOA_UNAVAILABLE", status="N_A")
    values = [item.value for item in aoa]
    structured = {
        "sample_count": len(values),
        "min_rad": min(values),
        "max_rad": max(values),
        "p05_rad": _quantile(request, values, 0.05),
        "p50_rad": _quantile(request, values, 0.50),
        "p95_rad": _quantile(request, values, 0.95),
    }
    return _valid_structured(request, structured)


def _air026(request: M2MetricPluginRequest) -> Mapping[str, object]:
    aoa = _series(request.input_payload, "aoa_rad")
    threshold = _profile_float(request.input_payload, "aoa_threshold_rad")
    min_dwell_us = int(_profile_float(request.input_payload, "min_dwell_s") * 1_000_000.0)
    max_gap = _profile_int(request.input_payload, "max_gap_us")
    eligible_us = 0
    high_us = 0
    episode_count = 0
    for piece in split_validity_pieces(aoa, max_gap_us=max_gap):
        if len(piece) < 2:
            continue
        eligible_us += piece[-1].session_time_us - piece[0].session_time_us
        start: int | None = None
        last: int | None = None
        for item in piece:
            if item.value >= threshold:
                if start is None:
                    start = item.session_time_us
                last = item.session_time_us
            elif start is not None and last is not None:
                duration = last - start
                if duration >= min_dwell_us:
                    high_us += duration
                    episode_count += 1
                start = None
                last = None
        if start is not None and last is not None:
            duration = last - start
            if duration >= min_dwell_us:
                high_us += duration
                episode_count += 1
    if eligible_us <= 0:
        return _missing(request, "NO_ELIGIBLE_AOA_TIME", status="N_A")
    return _valid_numeric(
        request,
        high_us / eligible_us,
        evidence={"qualified_episode_count": episode_count, "eligible_time_us": eligible_us},
    )


def _event_series(
    event: Mapping[str, object],
    name: str,
    *,
    event_id: str,
) -> tuple[TimedValue, ...]:
    return _series(event, name)


def _response_event_delays(
    payload: Mapping[str, object],
) -> tuple[tuple[str, float], ...]:
    _identity_guard(payload, "control_calibration")
    _identity_guard(payload, "control_response_map")
    profile = _profile(payload)
    command_deadband = _finite(profile, "command_deadband", field="profile")
    command_persistence = _finite(profile, "command_persistence_s", field="profile")
    response_threshold = _finite(profile, "response_threshold", field="profile")
    response_persistence = _finite(profile, "response_persistence_s", field="profile")
    max_search_us = int(_finite(profile, "max_search_s", field="profile") * 1_000_000.0)
    max_gap = _integer(profile, "max_gap_us", field="profile")
    results: list[tuple[str, float]] = []
    for index, event in enumerate(
        _mappings(payload.get("command_response_events"), field="command_response_events")
    ):
        field = f"command_response_events[{index}]"
        event_id = _text(event, "event_id", field=field)
        command = _event_series(event, "command", event_id=event_id)
        response = _event_series(event, "response", event_id=event_id)
        _text(event, "mode", field=field)
        command_candidates = [
            item for item in command if abs(item.value) > command_deadband
        ]
        if not command_candidates:
            continue
        sign = 1.0 if command_candidates[0].value > 0.0 else -1.0
        command_onset = _persistent_sample_time(
            command,
            threshold=command_deadband,
            persistence_s=command_persistence,
            max_gap_us=max_gap,
            sign=sign,
        )
        if command_onset is None:
            continue
        response_onset = _persistent_sample_time(
            response,
            threshold=response_threshold,
            persistence_s=response_persistence,
            max_gap_us=max_gap,
            sign=sign,
            start_us=command_onset,
            end_us=command_onset + max_search_us,
        )
        if response_onset is None or response_onset < command_onset:
            continue
        results.append((event_id, (response_onset - command_onset) / 1_000_000.0))
    return tuple(results)


def _air027(request: M2MetricPluginRequest) -> Mapping[str, object]:
    delays = _response_event_delays(request.input_payload)
    if not delays:
        return _missing(request, "RESPONSE_ONSET_UNRESOLVED", status="N_A")
    values = [item[1] for item in delays]
    return _valid_numeric(
        request,
        _median(request, values),
        evidence={"event_delays_s": [{"event_id": item[0], "delay_s": item[1]} for item in delays]},
    )


def _air028(request: M2MetricPluginRequest) -> Mapping[str, object]:
    _identity_guard(request.input_payload, "control_calibration")
    deadband = _profile_float(request.input_payload, "control_deadband")
    filtered = tuple(
        item for item in _series(request.input_payload, "control_input")
        if abs(item.value) > deadband
    )
    derivative = _derivative(
        request,
        filtered,
        derivative_window_s=_profile_float(request.input_payload, "derivative_window_s"),
        max_gap_us=_profile_int(request.input_payload, "max_gap_us"),
    )
    if not derivative:
        return _missing(request, "CONTROL_RATE_UNAVAILABLE", status="N_A")
    return _valid_numeric(request, _rms(request, [item.value for item in derivative]))


def _air029(request: M2MetricPluginRequest) -> Mapping[str, object]:
    _identity_guard(request.input_payload, "control_calibration")
    values = _series(request.input_payload, "control_input")
    deadband = _profile_float(request.input_payload, "control_deadband")
    persistence_us = int(
        _profile_float(request.input_payload, "reversal_persistence_s") * 1_000_000.0
    )
    max_gap = _profile_int(request.input_payload, "max_gap_us")
    count = 0
    previous_sign = 0
    for piece in split_validity_pieces(values, max_gap_us=max_gap):
        index = 0
        while index < len(piece):
            value = piece[index].value
            sign = 1 if value > deadband else -1 if value < -deadband else 0
            if sign == 0 or sign == previous_sign:
                if sign:
                    previous_sign = sign
                index += 1
                continue
            target = piece[index].session_time_us + persistence_us
            last = piece[index].session_time_us
            persistent = True
            for following in piece[index:]:
                if following.session_time_us > target:
                    break
                following_sign = (
                    1 if following.value > deadband else -1 if following.value < -deadband else 0
                )
                if following_sign != sign:
                    persistent = False
                    break
                last = following.session_time_us
            if persistent and last >= target:
                if previous_sign != 0:
                    count += 1
                previous_sign = sign
            index += 1
    return _valid_numeric(request, float(count), evidence={"reversal_count": count})


def _air030(request: M2MetricPluginRequest) -> Mapping[str, object]:
    profile = _profile(request.input_payload)
    fields = {
        "low_hz": _finite(profile, "low_hz", field="profile"),
        "high_hz": _finite(profile, "high_hz", field="profile"),
        "min_window_s": _finite(profile, "min_window_s", field="profile"),
        "min_coverage": _finite(profile, "min_coverage", field="profile"),
        "max_gap_us": _integer(profile, "max_gap_us", field="profile"),
        "resample_rate_hz": _finite(profile, "resample_rate_hz", field="profile"),
        "filter_padding_s": _finite(profile, "filter_padding_s", field="profile"),
    }
    structured: dict[str, object] = {}
    valid_axes = 0
    for axis, key in (("roll", "roll_rad"), ("pitch", "pitch_rad")):
        source = _optional_series(request.input_payload, key)
        raw: object = ()
        if source:
            raw = _operator(request, "BANDPASS_BUTTERWORTH4_ZP_V1")(source, **fields)
        filtered = cast(tuple[float, ...], raw)
        if filtered:
            rms_value = _rms(request, filtered)
            structured[axis] = {
                "status": "VALID",
                "rms_rad": float(format(rms_value, ".15g")),
            }
            valid_axes += 1
        else:
            structured[axis] = {"status": "INSUFFICIENT_DATA", "rms_rad": None}
    if valid_axes == 0:
        return _missing(
            request,
            "ATTITUDE_FILTER_INTERVAL_UNAVAILABLE",
            status="N_A",
            evidence={"structured_preview": structured},
        )
    return _valid_structured(request, structured)


def _air031(request: M2MetricPluginRequest) -> Mapping[str, object]:
    rows = _mappings(
        request.input_payload.get("accel_body_mps2_xyz"),
        field="accel_body_mps2_xyz",
    )
    axes: dict[str, list[TimedValue]] = {"x": [], "y": [], "z": []}
    previous: int | None = None
    for index, row in enumerate(rows):
        field = f"accel_body_mps2_xyz[{index}]"
        time = _integer(row, "session_time_us", field=field)
        if previous is not None and time <= previous:
            raise ValueError("M3_AIR_JERK_TIME_INVALID")
        previous = time
        for axis in axes:
            axes[axis].append(TimedValue(time, _finite(row, axis, field=field)))
    window = _profile_float(request.input_payload, "derivative_window_s")
    max_gap = _profile_int(request.input_payload, "max_gap_us")
    derivatives = {
        axis: _derivative(
            request,
            values,
            derivative_window_s=window,
            max_gap_us=max_gap,
        )
        for axis, values in axes.items()
    }
    by_axis = {axis: _series_map(values) for axis, values in derivatives.items()}
    common = sorted(set(by_axis["x"]) & set(by_axis["y"]) & set(by_axis["z"]))
    if not common:
        return _missing(request, "SIMULTANEOUS_3D_JERK_UNAVAILABLE", status="N_A")
    norms = [
        math.sqrt(sum(by_axis[axis][time] ** 2 for axis in ("x", "y", "z")))
        for time in common
    ]
    return _valid_numeric(request, _rms(request, norms), evidence={"sample_count": len(norms)})


def _air032(request: M2MetricPluginRequest) -> Mapping[str, object]:
    flow = _series(request.input_payload, "fuel_flow_kg_s")
    values = [item.value for item in flow]
    return _valid_numeric(
        request,
        _median(request, values),
        evidence={"p95_fuel_flow_kg_s": _quantile(request, values, 0.95)},
    )


def _air033(request: M2MetricPluginRequest) -> Mapping[str, object]:
    fuel = _series(request.input_payload, "fuel_remaining_kg")
    threshold = _profile_float(request.input_payload, "refuel_jump_threshold_kg")
    guard_us = int(_profile_float(request.input_payload, "event_guard_s") * 1_000_000.0)
    event_times: set[int] = set()
    for previous, current in zip(fuel, fuel[1:], strict=False):
        if current.value - previous.value >= threshold:
            event_times.add(current.session_time_us)
    for marker in _mappings(
        request.input_payload.get("fuel_event_markers", ()),
        field="fuel_event_markers",
    ):
        event_times.add(_integer(marker, "session_time_us", field="fuel_event_marker"))
    guarded = tuple(
        item
        for item in fuel
        if all(abs(item.session_time_us - event_time) > guard_us for event_time in event_times)
    )
    derivative = _derivative(
        request,
        guarded,
        derivative_window_s=_profile_float(request.input_payload, "derivative_window_s"),
        max_gap_us=_profile_int(request.input_payload, "max_gap_us"),
    )
    burn = [
        TimedValue(item.session_time_us, -item.value)
        for item in derivative
        if -item.value >= 0.0
    ]
    if not burn:
        return _missing(request, "FUEL_BURN_RATE_UNAVAILABLE", status="N_A")
    return _valid_numeric(
        request,
        _median(request, [item.value for item in burn]),
        evidence={
            "fuel_burn_rate_series": [
                {"session_time_us": str(item.session_time_us), "value": item.value}
                for item in burn
            ],
            "event_times_us": [str(item) for item in sorted(event_times)],
        },
    )


def _interpolate_value(values: Sequence[TimedValue], session_time_us: int) -> float | None:
    for item in values:
        if item.session_time_us == session_time_us:
            return item.value
    for left, right in zip(values, values[1:], strict=False):
        if left.session_time_us < session_time_us < right.session_time_us:
            fraction = (
                (session_time_us - left.session_time_us)
                / (right.session_time_us - left.session_time_us)
            )
            return left.value + fraction * (right.value - left.value)
    return None


def _air034(request: M2MetricPluginRequest) -> Mapping[str, object]:
    fuel = _series(request.input_payload, "fuel_remaining_kg")
    burn = tuple(
        item
        for item in _series(request.input_payload, "P1-AIR-033.fuel_burn_rate_kg_s")
        if item.value > 0.0
    )
    windows = _rolling(
        request,
        burn,
        duration_s=_profile_float(request.input_payload, "burn_rate_window_s"),
        min_coverage=_profile_float(request.input_payload, "min_coverage"),
        max_gap_us=_profile_int(request.input_payload, "max_gap_us"),
    )
    estimates: list[float] = []
    for smoothed, _start, _end in windows:
        remaining = _interpolate_value(fuel, smoothed.session_time_us)
        if remaining is not None and smoothed.value > FUEL_BURN_RATE_EPS_KG_S:
            estimates.append(remaining / smoothed.value)
    if not estimates:
        return _missing(request, "ENDURANCE_PROXY_DENOMINATOR_INELIGIBLE", status="N_A")
    return _valid_numeric(
        request,
        _median(request, estimates),
        evidence={"estimate_count": len(estimates)},
    )


def _air035(request: M2MetricPluginRequest) -> Mapping[str, object]:
    _identity_guard(request.input_payload, "control_calibration")
    _identity_guard(request.input_payload, "control_response_map")
    profile = _profile(request.input_payload)
    event_window_us = int(_finite(profile, "event_window_s", field="profile") * 1_000_000.0)
    min_levels = _integer(profile, "min_unique_command_levels", field="profile")
    deadband = _finite(profile, "command_deadband", field="profile")
    max_gap = _integer(profile, "max_gap_us", field="profile")
    grouped: dict[tuple[str, str, str, str, str], list[tuple[int, str, float]]] = {}
    for index, event in enumerate(
        _mappings(
            request.input_payload.get("command_response_events"),
            field="command_response_events",
        )
    ):
        field = f"command_response_events[{index}]"
        event_id = _text(event, "event_id", field=field)
        start = _integer(event, "start_session_time_us", field=field)
        command = _series(event, "command")
        response = _series(event, "response")
        response_by_time = _series_map(response)
        eligible = [
            item
            for item in command
            if item.session_time_us <= start + event_window_us
            and abs(item.value) > deadband
            and item.session_time_us in response_by_time
        ]
        if len(eligible) < min_levels:
            continue
        if any(
            right.session_time_us - left.session_time_us > max_gap
            for left, right in zip(eligible, eligible[1:], strict=False)
        ):
            continue
        command_values = [item.value for item in eligible]
        response_values = [response_by_time[item.session_time_us] for item in eligible]
        try:
            gain_raw = _operator(request, "THEIL_SEN_GAIN_V1")(
                command_values,
                response_values,
                min_unique_command_levels=min_levels,
            )
        except ValueError:
            continue
        gain = float(cast(float, gain_raw))
        group = (
            _text(event, "control_axis", field=field),
            _text(event, "mode", field=field),
            _text(event, "response_channel", field=field),
            _text(event, "response_unit", field=field),
            _text(event, "gain_unit", field=field),
        )
        grouped.setdefault(group, []).append((start, event_id, gain))
    if not grouped:
        return _missing(request, "CONTROL_GAIN_EVENTS_INSUFFICIENT", status="N_A")
    groups: list[dict[str, object]] = []
    for group in sorted(grouped):
        events = sorted(grouped[group])
        groups.append(
            {
                "control_axis": group[0],
                "mode": group[1],
                "response_channel": group[2],
                "response_unit": group[3],
                "gain_unit": group[4],
                "n_events": len(events),
                "event_gains": [
                    {"event_id": event_id, "gain": gain}
                    for _start, event_id, gain in events
                ],
            }
        )
    return _valid_structured(request, {"groups": groups})


def _air036(request: M2MetricPluginRequest) -> Mapping[str, object]:
    _identity_guard(request.input_payload, "control_calibration")
    _identity_guard(request.input_payload, "control_response_map")
    profile = _profile(request.input_payload)
    response_threshold = _finite(profile, "response_threshold", field="profile")
    persistence = _finite(profile, "command_persistence_s", field="profile")
    minimum_events = _integer(profile, "min_event_count", field="profile")
    max_gap = _integer(profile, "max_gap_us", field="profile")
    candidates: list[float] = []
    for event in _mappings(
        request.input_payload.get("command_response_events"),
        field="command_response_events",
    ):
        command = _series(event, "command")
        response = _series(event, "response")
        for item in command:
            if item.value == 0.0:
                continue
            sign = 1.0 if item.value > 0.0 else -1.0
            onset = _persistent_sample_time(
                command,
                threshold=abs(item.value),
                persistence_s=persistence,
                max_gap_us=max_gap,
                sign=sign,
                start_us=item.session_time_us,
            )
            response_onset = _persistent_sample_time(
                response,
                threshold=response_threshold,
                persistence_s=0.0,
                max_gap_us=max_gap,
                sign=sign,
                start_us=item.session_time_us,
            )
            if onset is not None and response_onset is not None:
                candidates.append(abs(item.value))
                break
    if len(candidates) < minimum_events:
        return _missing(request, "CONTROL_DEADBAND_EVENTS_INSUFFICIENT", status="N_A")
    return _valid_numeric(
        request,
        min(candidates),
        evidence={"qualified_event_count": len(candidates)},
    )


def _air037(request: M2MetricPluginRequest) -> Mapping[str, object]:
    _identity_guard(request.input_payload, "control_response_map")
    profile = _profile(request.input_payload)
    threshold = _finite(profile, "response_threshold", field="profile")
    reversal = _finite(profile, "reversal_threshold", field="profile")
    max_gap = _integer(profile, "max_gap_us", field="profile")
    minimum_events = _integer(profile, "min_event_count", field="profile")
    qualified = 0
    durations: list[float] = []
    for index, event in enumerate(
        _mappings(
            request.input_payload.get("command_response_events"),
            field="command_response_events",
        )
    ):
        field = f"command_response_events[{index}]"
        onset = _integer(event, "response_onset_time_us", field=field)
        sign_value = _finite(event, "response_sign", field=field)
        sign = 1.0 if sign_value >= 0.0 else -1.0
        response = _series(event, "response")
        qualified += 1
        previous_time: int | None = None
        completed_at: int | None = None
        for item in response:
            if item.session_time_us < onset:
                continue
            if previous_time is not None and item.session_time_us - previous_time > max_gap:
                completed_at = previous_time
                break
            projected = sign * item.value
            if projected < threshold or projected <= -reversal:
                completed_at = item.session_time_us
                break
            previous_time = item.session_time_us
        if completed_at is not None and completed_at >= onset:
            durations.append((completed_at - onset) / 1_000_000.0)
    if qualified < minimum_events or not durations:
        return _missing(request, "RESPONSE_PERSISTENCE_EVENTS_INSUFFICIENT", status="N_A")
    return _valid_numeric(
        request,
        _median(request, durations),
        evidence={
            "p95_duration_s": _quantile(request, durations, 0.95),
            "completion_ratio": len(durations) / qualified,
            "completed_events": len(durations),
            "qualified_events": qualified,
        },
    )


def _air038(request: M2MetricPluginRequest) -> Mapping[str, object]:
    energy_rate = _series(request.input_payload, "P1-AIR-017.specific_energy_rate")
    altitude_rate = _derivative(
        request,
        _series(request.input_payload, "alt_msl_m"),
        derivative_window_s=_profile_float(request.input_payload, "derivative_window_s"),
        max_gap_us=_profile_int(request.input_payload, "max_gap_us"),
    )
    energy_by_time = _series_map(energy_rate)
    values: list[float] = []
    outside = 0
    for item in altitude_rate:
        total = energy_by_time.get(item.session_time_us)
        if total is None or total <= ENERGY_RATE_EPS_W_PER_KG or item.value <= 0.0:
            continue
        value = G0_MPS2 * item.value / total
        values.append(value)
        if not 0.0 <= value <= 1.0:
            outside += 1
    if not values:
        return _missing(request, "POSITIVE_ENERGY_CLIMB_UNAVAILABLE", status="N_A")
    return _valid_numeric(
        request,
        _median(request, values),
        evidence={
            "outside_unit_interval_count": outside,
            "outside_unit_interval_flag": outside > 0,
        },
    )


def _air039(request: M2MetricPluginRequest) -> Mapping[str, object]:
    energy = _series(request.input_payload, "P1-AIR-016.specific_mechanical_energy")
    rate = _optional_series(request.input_payload, "P1-AIR-017.specific_energy_rate")
    intervals = _mappings(
        request.input_payload.get("P1-AIR-015.dive_eligible_intervals"),
        field="P1-AIR-015.dive_eligible_intervals",
    )
    energy_by_time = _series_map(energy)
    output: list[dict[str, object]] = []
    previous_start: int | None = None
    for index, interval in enumerate(intervals):
        field = f"P1-AIR-015.dive_eligible_intervals[{index}]"
        start = _integer(interval, "start_session_time_us", field=field)
        end = _integer(interval, "end_session_time_us", field=field)
        if end <= start or (previous_start is not None and start < previous_start):
            raise ValueError("M3_AIR_DIVE_INTERVAL_ORDER_INVALID")
        previous_start = start
        if start not in energy_by_time or end not in energy_by_time:
            continue
        interior = [item.value for item in rate if start < item.session_time_us < end]
        output.append(
            {
                "start_session_time_us": str(start),
                "end_session_time_us": str(end),
                "delta_E_s_j_per_kg": energy_by_time[end] - energy_by_time[start],
                "median_energy_rate_w_per_kg": (
                    _median(request, interior) if interior else None
                ),
                "median_energy_rate_status": (
                    "VALID" if interior else "INSUFFICIENT_RATE_SAMPLES"
                ),
            }
        )
    if not output:
        return _missing(request, "NO_VALID_DIVE_INTERVAL", status="N_A")
    return _valid_structured(
        request,
        {"interval_count": len(output), "intervals": output},
    )


_HANDLERS: Mapping[
    str,
    Callable[[M2MetricPluginRequest], Mapping[str, object]],
] = MappingProxyType(
    {
        "P1-AIR-004": _air004,
        "P1-AIR-005": _air005,
        "P1-AIR-006": _air006,
        "P1-AIR-007": _air007,
        "P1-AIR-008": _air008,
        "P1-AIR-009": _air009,
        "P1-AIR-010": _air010,
        "P1-AIR-011": _air011,
        "P1-AIR-012": _air012,
        "P1-AIR-013": _air013,
        "P1-AIR-014": _air014,
        "P1-AIR-015": _air015,
        "P1-AIR-016": _air016,
        "P1-AIR-017": _air017,
        "P1-AIR-018": _air018,
        "P1-AIR-019": _air019,
        "P1-AIR-020": _air020,
        "P1-AIR-021": _air021,
        "P1-AIR-022": _air022,
        "P1-AIR-023": _air023,
        "P1-AIR-024": _air024,
        "P1-AIR-025": _air025,
        "P1-AIR-026": _air026,
        "P1-AIR-027": _air027,
        "P1-AIR-028": _air028,
        "P1-AIR-029": _air029,
        "P1-AIR-030": _air030,
        "P1-AIR-031": _air031,
        "P1-AIR-032": _air032,
        "P1-AIR-033": _air033,
        "P1-AIR-034": _air034,
        "P1-AIR-035": _air035,
        "P1-AIR-036": _air036,
        "P1-AIR-037": _air037,
        "P1-AIR-038": _air038,
        "P1-AIR-039": _air039,
    }
)


def _plugin(request: M2MetricPluginRequest) -> Mapping[str, object]:
    _guard(request)
    handler = _HANDLERS.get(request.definition.metric_code)
    if handler is None:
        raise ValueError(f"M3_AIR_PLUGIN_MISSING:{request.definition.metric_code}")
    return handler(request)


M3_AIR_PLUGINS: Mapping[str, M2MetricPlugin] = MappingProxyType(
    {code: _plugin for code in M3_AIR_CODES}
)


def register_m3_air_plugins(
    plan: M2MetricExecutionPlan,
    registry: MetricPluginRegistry,
) -> None:
    """Register exact M3 AIR algorithms in the shared Catalog registry."""

    definitions = tuple(
        definition for definition in plan.definitions if definition.metric_code in M3_AIR_CODES
    )
    if len(definitions) != 36 or {item.metric_code for item in definitions} != set(M3_AIR_CODES):
        raise CatalogMetricEngineError("M3_AIR_DELIVERY_MEMBERSHIP_DRIFT", repr(plan.metric_codes))
    counts: dict[str, int] = {}
    for definition in definitions:
        counts[definition.family] = counts.get(definition.family, 0) + 1
    if counts != dict(M3_AIR_FAMILY_COUNTS):
        raise CatalogMetricEngineError("M3_AIR_FAMILY_COUNTS_DRIFT", repr(counts))
    for definition in definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"m3-air-remainder:{definition.metric_code}:v1",
            plugin=_plugin,
        )
