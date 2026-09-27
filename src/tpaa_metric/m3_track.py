"""M3-MET-003 Catalog plugins for the exact P1 TRK remainder.

P1-TRK-001..007 execute through the shared CatalogMetricEngine and are
applicable only when the evaluated mission-system product advertises the frozen
LOCAL_TRACK_PRODUCT semantic capability.
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

M3_TRK_CODES = tuple(f"P1-TRK-{index:03d}" for index in range(1, 8))
M3_TRK_FAMILY = "TRACK_PERFORMANCE"
M3_TRK_REQUIRED_PRODUCT_SEMANTICS = "LOCAL_TRACK_PRODUCT"


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"M3_TRK_INPUT_INVALID:{field}")
    return cast(Mapping[str, object], value)


def _mappings(value: object, *, field: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"M3_TRK_INPUT_INVALID:{field}")
    return tuple(
        _mapping(item, field=f"{field}[{index}]")
        for index, item in enumerate(value)
    )


def _text(mapping: Mapping[str, object], name: str, *, field: str) -> str:
    value = mapping.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"M3_TRK_INPUT_INVALID:{field}.{name}")
    return value


def _integer(mapping: Mapping[str, object], name: str, *, field: str) -> int:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"M3_TRK_INPUT_INVALID:{field}.{name}")
    return value


def _optional_integer(
    mapping: Mapping[str, object],
    name: str,
    *,
    field: str,
) -> int | None:
    value = mapping.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"M3_TRK_INPUT_INVALID:{field}.{name}")
    return value


def _finite(mapping: Mapping[str, object], name: str, *, field: str) -> float:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"M3_TRK_INPUT_INVALID:{field}.{name}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"M3_TRK_INPUT_NONFINITE:{field}.{name}")
    return result


def _profile(payload: Mapping[str, object]) -> Mapping[str, object]:
    return _mapping(payload.get("profile"), field="profile")


def _profile_float(payload: Mapping[str, object], name: str) -> float:
    return _finite(_profile(payload), name, field="profile")


def _sha256(value: str, *, field: str) -> str:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"M3_TRK_INPUT_INVALID:{field}")
    return value


def _identity(payload: Mapping[str, object], prefix: str) -> tuple[str, str, str]:
    identity = _text(payload, f"{prefix}_id", field=prefix)
    version = _text(payload, f"{prefix}_version", field=prefix)
    digest = _sha256(
        _text(payload, f"{prefix}_hash", field=prefix),
        field=f"{prefix}_hash",
    )
    return identity, version, digest


def _opportunity_identity(
    payload: Mapping[str, object],
) -> tuple[str, str, str, str]:
    opportunity_id = _text(
        payload,
        "detection_opportunity_id",
        field="detection_opportunity_id",
    )
    profile_id, profile_version, profile_hash = _identity(
        payload,
        "opportunity_profile",
    )
    return opportunity_id, profile_id, profile_version, profile_hash


def _products(payload: Mapping[str, object]) -> tuple[str, ...]:
    raw = payload.get("product_semantics")
    if not isinstance(raw, (list, tuple)) or not all(
        isinstance(item, str) and item for item in raw
    ):
        raise ValueError("M3_TRK_PRODUCT_SEMANTICS_INVALID")
    values = tuple(cast(Sequence[str], raw))
    if len(values) != len(set(values)):
        raise ValueError("M3_TRK_PRODUCT_SEMANTICS_DUPLICATE")
    return values


def _guard(request: M2MetricPluginRequest) -> bool:
    definition = request.definition
    applicability = definition.applicability
    if (
        definition.metric_code not in M3_TRK_CODES
        or definition.family != M3_TRK_FAMILY
        or definition.subject_type != "MISSION_SYSTEM_INSTANCE"
        or definition.value_kind != "NUMERIC"
        or definition.observation_lane != "SYSTEM_PERFORMANCE_OBSERVATION"
        or definition.publication_route != "SYSTEM_PERFORMANCE_OBSERVATION"
        or applicability.applicability_mode != "PRODUCT_CAPABILITY"
        or applicability.required_product_semantics
        != M3_TRK_REQUIRED_PRODUCT_SEMANTICS
    ):
        raise ValueError(f"M3_TRK_CATALOG_DEFINITION_DRIFT:{definition.metric_code}")
    return M3_TRK_REQUIRED_PRODUCT_SEMANTICS in _products(request.input_payload)


def _operator(request: M2MetricPluginRequest, operator_id: str) -> Callable[..., object]:
    value = request.operators.get(operator_id)
    if value is None:
        raise ValueError(f"M3_TRK_OPERATOR_MISSING:{operator_id}")
    return value


def _operator_number(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"M3_TRK_OPERATOR_OUTPUT_INVALID:{field}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"M3_TRK_OPERATOR_OUTPUT_NONFINITE:{field}")
    return result


def _median(request: M2MetricPluginRequest, values: Sequence[float]) -> float:
    return _operator_number(
        _operator(request, "MEDIAN_V1")(values),
        field="MEDIAN_V1",
    )


def _quantile(
    request: M2MetricPluginRequest,
    values: Sequence[float],
    probability: float,
) -> float:
    return _operator_number(
        _operator(request, "QUANTILE_HF7_V1")(values, probability),
        field="QUANTILE_HF7_V1",
    )


def _rms(request: M2MetricPluginRequest, values: Sequence[float]) -> float:
    return _operator_number(
        _operator(request, "RMS_V1")(values),
        field="RMS_V1",
    )


def _instance(
    *,
    status: str,
    reason_codes: Sequence[str] = (),
    value_numeric: float | None = None,
    evidence: Mapping[str, object] | None = None,
) -> dict[str, object]:
    if status == "VALID":
        if value_numeric is None or not math.isfinite(value_numeric):
            raise ValueError("M3_TRK_VALID_VALUE_INVALID")
    elif value_numeric is not None:
        raise ValueError("M3_TRK_NONVALID_VALUE_FORBIDDEN")
    return {
        "status": status,
        "reason_codes": list(reason_codes),
        "value_kind": "NUMERIC",
        "value_numeric": value_numeric,
        "value_structured": None,
        "evidence": {} if evidence is None else dict(evidence),
    }


def _not_applicable(request: M2MetricPluginRequest) -> Mapping[str, object]:
    return {
        "metric_code": request.definition.metric_code,
        "subject_type": request.definition.subject_type,
        "observation_lane": request.definition.observation_lane,
        "publication_route": request.definition.publication_route,
        "applicable": False,
        "instances": [],
    }


def _output(
    request: M2MetricPluginRequest,
    *,
    status: str = "VALID",
    reason_codes: Sequence[str] = (),
    value_numeric: float | None = None,
    evidence: Mapping[str, object] | None = None,
) -> Mapping[str, object]:
    return {
        "metric_code": request.definition.metric_code,
        "subject_type": request.definition.subject_type,
        "observation_lane": request.definition.observation_lane,
        "publication_route": request.definition.publication_route,
        "applicable": True,
        "instances": [
            _instance(
                status=status,
                reason_codes=reason_codes,
                value_numeric=value_numeric,
                evidence=evidence,
            )
        ],
    }


def _missing(
    request: M2MetricPluginRequest,
    reason: str,
    *,
    evidence: Mapping[str, object] | None = None,
) -> Mapping[str, object]:
    return _output(
        request,
        status="N_A",
        reason_codes=(reason,),
        evidence=evidence,
    )


def _dependency_hash(request: M2MetricPluginRequest, metric_code: str) -> str:
    for code, digest in request.upstream_result_hashes:
        if code == metric_code:
            return digest
    raise ValueError(f"M3_TRK_UPSTREAM_RESULT_MISSING:{metric_code}")


def _vector3(value: object, *, field: str) -> tuple[float, float, float]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or len(value) != 3
    ):
        raise ValueError(f"M3_TRK_VECTOR_INVALID:{field}")
    output: list[float] = []
    for index, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"M3_TRK_VECTOR_INVALID:{field}[{index}]")
        number = float(item)
        if not math.isfinite(number):
            raise ValueError(f"M3_TRK_VECTOR_NONFINITE:{field}[{index}]")
        output.append(number)
    return output[0], output[1], output[2]


def _intervals(
    payload: Mapping[str, object],
    name: str,
) -> tuple[tuple[int, int], ...]:
    rows = _mappings(payload.get(name), field=name)
    result: list[tuple[int, int]] = []
    for index, row in enumerate(rows):
        field = f"{name}[{index}]"
        start = _integer(row, "start_session_time_us", field=field)
        end = _integer(row, "end_session_time_us", field=field)
        if end <= start:
            raise ValueError(f"M3_TRK_INTERVAL_INVALID:{field}")
        result.append((start, end))
    return tuple(result)


def _merged_intervals(
    intervals: Sequence[tuple[int, int]],
) -> tuple[tuple[int, int], ...]:
    if not intervals:
        return ()
    ordered = sorted(intervals)
    merged: list[list[int]] = [[ordered[0][0], ordered[0][1]]]
    for start, end in ordered[1:]:
        current = merged[-1]
        if start <= current[1]:
            current[1] = max(current[1], end)
        else:
            merged.append([start, end])
    return tuple((item[0], item[1]) for item in merged)


def _intersection_duration_us(
    left: Sequence[tuple[int, int]],
    right: Sequence[tuple[int, int]],
) -> int:
    total = 0
    for left_start, left_end in _merged_intervals(left):
        for right_start, right_end in _merged_intervals(right):
            start = max(left_start, right_start)
            end = min(left_end, right_end)
            if end > start:
                total += end - start
    return total


def _trk001(request: M2MetricPluginRequest) -> Mapping[str, object]:
    confirmation_event_id = _text(
        request.input_payload,
        "detection_confirmation_event_id",
        field="P1-TRK-001",
    )
    confirmation_profile = _identity(request.input_payload, "confirmation_profile")
    persistence = _profile_float(request.input_payload, "stable_track_persistence_s")
    max_gap = _finite(_profile(request.input_payload), "max_gap_us", field="profile")
    if persistence <= 0.0 or max_gap <= 0.0:
        raise ValueError("M3_TRK_STABLE_PROFILE_INVALID")
    first = _optional_integer(
        request.input_payload,
        "first_confirmed_detection_time_us",
        field="P1-TRK-001",
    )
    stable = _optional_integer(
        request.input_payload,
        "stable_track_start_time_us",
        field="P1-TRK-001",
    )
    if first is None or stable is None:
        return _missing(request, "STABLE_TRACK_ONSET_UNAVAILABLE")
    if stable < first:
        raise ValueError("M3_TRK_STABLE_TRACK_PRECEDES_CONFIRMATION")
    return _output(
        request,
        value_numeric=(stable - first) / 1_000_000.0,
        evidence={
            "detection_confirmation_event_id": confirmation_event_id,
            "confirmation_profile": list(confirmation_profile),
            "stable_track_persistence_s": persistence,
            "max_gap_us": int(max_gap),
        },
    )


def _reference_rmse(
    request: M2MetricPluginRequest,
    *,
    track_field: str,
    reference_field: str,
    error_domain: str,
) -> Mapping[str, object]:
    profile = _identity(request.input_payload, "reference_match_quality_profile")
    qa_hash = _dependency_hash(request, "P1-QA-005")
    samples = _mappings(request.input_payload.get("samples"), field="samples")
    residuals: list[float] = []
    rejected = 0
    for index, sample in enumerate(samples):
        field = f"samples[{index}]"
        accepted = sample.get("reference_match_accepted")
        if not isinstance(accepted, bool):
            raise ValueError(f"M3_TRK_REFERENCE_MATCH_STATUS_INVALID:{field}")
        domain = _text(sample, "error_domain", field=field)
        if domain != error_domain:
            raise ValueError(f"M3_TRK_REFERENCE_ERROR_DOMAIN_INVALID:{field}:{domain}")
        if not accepted:
            rejected += 1
            continue
        track = _vector3(sample.get(track_field), field=f"{field}.{track_field}")
        reference = _vector3(
            sample.get(reference_field),
            field=f"{field}.{reference_field}",
        )
        residuals.append(
            math.sqrt(
                sum(
                    (track[axis] - reference[axis]) ** 2
                    for axis in range(3)
                )
            )
        )
    if not residuals:
        return _missing(
            request,
            "REFERENCE_MATCH_QUALITY_REJECTED_ALL",
            evidence={
                "reference_match_quality_profile": list(profile),
                "qa_005_result_hash": qa_hash,
                "rejected_count": rejected,
            },
        )
    return _output(
        request,
        value_numeric=_rms(request, residuals),
        evidence={
            "reference_match_quality_profile": list(profile),
            "qa_005_result_hash": qa_hash,
            "eligible_count": len(residuals),
            "rejected_count": rejected,
            "residual_norms": residuals,
        },
    )


def _trk002(request: M2MetricPluginRequest) -> Mapping[str, object]:
    return _reference_rmse(
        request,
        track_field="track_position_ecef_m",
        reference_field="reference_target_position_ecef_m",
        error_domain="POSITION_3D",
    )


def _trk003(request: M2MetricPluginRequest) -> Mapping[str, object]:
    return _reference_rmse(
        request,
        track_field="track_velocity_ecef_mps",
        reference_field="reference_target_velocity_ecef_mps",
        error_domain="VELOCITY_3D",
    )


def _trk004(request: M2MetricPluginRequest) -> Mapping[str, object]:
    identity = _opportunity_identity(request.input_payload)
    opportunities = _intervals(
        request.input_payload,
        "evaluation_opportunity_intervals",
    )
    valid = _intervals(request.input_payload, "valid_track_intervals")
    opportunity_us = sum(
        end - start for start, end in _merged_intervals(opportunities)
    )
    if opportunity_us <= 0:
        return _missing(request, "NO_VALID_OPPORTUNITIES")
    valid_us = _intersection_duration_us(valid, opportunities)
    return _output(
        request,
        value_numeric=valid_us / opportunity_us,
        evidence={
            "opportunity_identity": list(identity),
            "opportunity_duration_us": opportunity_us,
            "valid_track_opportunity_intersection_us": valid_us,
        },
    )


def _trk005(request: M2MetricPluginRequest) -> Mapping[str, object]:
    identity = _opportunity_identity(request.input_payload)
    opportunities = _intervals(request.input_payload, "opportunity_intervals")
    valid = _merged_intervals(_intervals(request.input_payload, "valid_track_intervals"))
    threshold_s = _profile_float(request.input_payload, "drop_min_duration_s")
    if threshold_s <= 0.0:
        raise ValueError("M3_TRK_DROP_DURATION_INVALID")
    threshold_us = int(threshold_s * 1_000_000.0)
    if not opportunities:
        return _missing(request, "NO_VALID_OPPORTUNITIES")

    qualified: list[tuple[int, int]] = []
    short_glitches: list[tuple[int, int]] = []
    for opportunity_start, opportunity_end in _merged_intervals(opportunities):
        clipped = [
            (max(start, opportunity_start), min(end, opportunity_end))
            for start, end in valid
            if min(end, opportunity_end) > max(start, opportunity_start)
        ]
        clipped = list(_merged_intervals(clipped))
        for index, (_start, valid_end) in enumerate(clipped):
            next_valid_start = (
                clipped[index + 1][0]
                if index + 1 < len(clipped)
                else opportunity_end
            )
            if next_valid_start <= valid_end:
                continue
            dwell = next_valid_start - valid_end
            target = (
                qualified
                if dwell >= threshold_us
                else short_glitches
            )
            target.append((valid_end, next_valid_start))
    return _output(
        request,
        value_numeric=float(len(qualified)),
        evidence={
            "opportunity_identity": list(identity),
            "qualified_drop_intervals_us": [list(item) for item in qualified],
            "short_invalid_glitches_us": [list(item) for item in short_glitches],
            "drop_min_duration_s": threshold_s,
        },
    )


def _trk006(request: M2MetricPluginRequest) -> Mapping[str, object]:
    identity = _opportunity_identity(request.input_payload)
    drop_min = _profile_float(request.input_payload, "drop_min_duration_s")
    reacquisition_persistence = _profile_float(
        request.input_payload,
        "reacquisition_persistence_s",
    )
    if drop_min <= 0.0 or reacquisition_persistence <= 0.0:
        raise ValueError("M3_TRK_REACQUISITION_PROFILE_INVALID")
    events = _mappings(
        request.input_payload.get("reacquisition_events"),
        field="reacquisition_events",
    )
    delays: list[float] = []
    rejected = 0
    for index, event in enumerate(events):
        field = f"reacquisition_events[{index}]"
        if _text(event, "detection_opportunity_id", field=field) != identity[0]:
            raise ValueError(f"M3_TRK_REACQUISITION_OPPORTUNITY_MISMATCH:{index}")
        drop_start = _integer(event, "track_drop_start_time_us", field=field)
        stable = _integer(
            event,
            "reacquired_stable_track_time_us",
            field=field,
        )
        invalid_dwell = _finite(event, "invalid_dwell_s", field=field)
        stable_dwell = _finite(event, "stable_persistence_s", field=field)
        if stable < drop_start:
            raise ValueError(f"M3_TRK_REACQUISITION_TIME_INVALID:{index}")
        if invalid_dwell < drop_min or stable_dwell < reacquisition_persistence:
            rejected += 1
            continue
        delays.append((stable - drop_start) / 1_000_000.0)
    if not delays:
        return _missing(
            request,
            "NO_QUALIFIED_REACQUISITIONS",
            evidence={
                "opportunity_identity": list(identity),
                "rejected_count": rejected,
            },
        )
    return _output(
        request,
        value_numeric=_median(request, delays),
        evidence={
            "opportunity_identity": list(identity),
            "qualified_reacquisition_delays_s": delays,
            "p95_reacquisition_delay_s": _quantile(request, delays, 0.95),
            "qualified_count": len(delays),
            "rejected_count": rejected,
        },
    )


def _integer_series(
    payload: Mapping[str, object],
    name: str,
) -> tuple[int, ...]:
    raw = payload.get(name)
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise ValueError(f"M3_TRK_INPUT_INVALID:{name}")
    output: list[int] = []
    for index, value in enumerate(raw):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"M3_TRK_INPUT_INVALID:{name}[{index}]")
        output.append(value)
    return tuple(output)


def _trk007(request: M2MetricPluginRequest) -> Mapping[str, object]:
    track_times = _integer_series(request.input_payload, "track_state_time_us")
    measurement_times = _integer_series(
        request.input_payload,
        "last_measurement_effective_time_us",
    )
    if len(track_times) != len(measurement_times):
        raise ValueError("M3_TRK_TRACK_AGE_LENGTH_MISMATCH")
    ages: list[float] = []
    for index, (track_time, measurement_time) in enumerate(
        zip(track_times, measurement_times, strict=True)
    ):
        if measurement_time > track_time:
            raise ValueError(f"M3_TRK_TRACK_AGE_NEGATIVE:{index}")
        ages.append((track_time - measurement_time) / 1_000_000.0)
    if not ages:
        return _missing(request, "TRACK_AGE_UNAVAILABLE")
    return _output(
        request,
        value_numeric=_median(request, ages),
        evidence={
            "p95_track_age_s": _quantile(request, ages, 0.95),
            "max_track_age_s": max(ages),
            "sample_count": len(ages),
        },
    )


_HANDLERS: Mapping[
    str,
    Callable[[M2MetricPluginRequest], Mapping[str, object]],
] = MappingProxyType(
    {
        "P1-TRK-001": _trk001,
        "P1-TRK-002": _trk002,
        "P1-TRK-003": _trk003,
        "P1-TRK-004": _trk004,
        "P1-TRK-005": _trk005,
        "P1-TRK-006": _trk006,
        "P1-TRK-007": _trk007,
    }
)


def _plugin(request: M2MetricPluginRequest) -> Mapping[str, object]:
    if not _guard(request):
        return _not_applicable(request)
    handler = _HANDLERS.get(request.definition.metric_code)
    if handler is None:
        raise ValueError(f"M3_TRK_PLUGIN_MISSING:{request.definition.metric_code}")
    return handler(request)


M3_TRK_PLUGINS: Mapping[str, M2MetricPlugin] = MappingProxyType(
    {code: _plugin for code in M3_TRK_CODES}
)


def register_m3_track_plugins(
    plan: M2MetricExecutionPlan,
    registry: MetricPluginRegistry,
) -> None:
    """Register the exact seven TRK algorithms in the shared Catalog registry."""

    definitions = tuple(
        definition
        for definition in plan.definitions
        if definition.metric_code in M3_TRK_CODES
    )
    if (
        len(definitions) != 7
        or {item.metric_code for item in definitions} != set(M3_TRK_CODES)
        or {item.family for item in definitions} != {M3_TRK_FAMILY}
    ):
        raise CatalogMetricEngineError(
            "M3_TRK_DELIVERY_MEMBERSHIP_DRIFT",
            repr(tuple(item.metric_code for item in definitions)),
        )
    for definition in definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"m3-track-remainder:{definition.metric_code}:v1",
            plugin=_plugin,
        )
