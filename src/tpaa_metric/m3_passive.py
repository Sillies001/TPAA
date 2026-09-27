"""M3-MET-005 Catalog plugins for the exact P1 passive-sensor remainder.

P1-PSV-001..007 execute through the shared CatalogMetricEngine.  Applicability
is frozen to mission-system types IRST and EO; all other system types fail
closed without manufacturing observations.
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

M3_PSV_CODES = tuple(f"P1-PSV-{index:03d}" for index in range(1, 8))
M3_PSV_FAMILY = "PASSIVE_SENSOR"
M3_PSV_ALLOWED_SYSTEM_TYPES = ("IRST", "EO")

_EXPECTED_OPERATORS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "P1-PSV-001": ("RMS_V1",),
        "P1-PSV-002": ("RMS_V1",),
        "P1-PSV-003": ("RMS_V1",),
        "P1-PSV-004": (),
        "P1-PSV-005": (),
        "P1-PSV-006": ("MEDIAN_V1", "QUANTILE_HF7_V1"),
        "P1-PSV-007": (),
    }
)
_EXPECTED_STATE_MACHINES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "P1-PSV-001": (),
        "P1-PSV-002": (),
        "P1-PSV-003": (),
        "P1-PSV-004": (),
        "P1-PSV-005": (),
        "P1-PSV-006": ("SM_TRACK_DROP_REACQUIRE_V1",),
        "P1-PSV-007": ("SM_TRACK_STABLE_V1", "SM_ASSOCIATION_EPISODE_V1"),
    }
)
_EXPECTED_UPSTREAM: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "P1-PSV-001": (
            "CONTRACT_REFERENCE_RELATIVE_STATE_V1",
            "P1-QA-001",
            "P1-QA-002",
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "P1-QA-005",
            "CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1",
        ),
        "P1-PSV-002": (
            "CONTRACT_REFERENCE_RELATIVE_STATE_V1",
            "P1-QA-001",
            "P1-QA-002",
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "P1-QA-005",
            "CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1",
        ),
        "P1-PSV-003": (
            "CONTRACT_REFERENCE_RELATIVE_STATE_V1",
            "P1-QA-001",
            "P1-QA-002",
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "P1-QA-005",
            "CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1",
        ),
        "P1-PSV-004": (
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1",
            "CONTRACT_DETECTION_CONFIRMATION_EVENT_V1",
        ),
        "P1-PSV-005": (
            "CONTRACT_TRACK_VALIDITY_V1",
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1",
        ),
        "P1-PSV-006": (
            "CONTRACT_TRACK_VALIDITY_V1",
            "CONTRACT_ASSOCIATION_RELATION_V1",
        ),
        "P1-PSV-007": (
            "CONTRACT_TRACK_VALIDITY_V1",
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "CONTRACT_REFERENCE_TARGET_SET_COVERAGE_V1",
        ),
    }
)


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"M3_PSV_INPUT_INVALID:{field}")
    return cast(Mapping[str, object], value)


def _mappings(value: object, *, field: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"M3_PSV_INPUT_INVALID:{field}")
    return tuple(
        _mapping(item, field=f"{field}[{index}]")
        for index, item in enumerate(value)
    )


def _text(mapping: Mapping[str, object], name: str, *, field: str) -> str:
    value = mapping.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"M3_PSV_INPUT_INVALID:{field}.{name}")
    return value


def _integer(mapping: Mapping[str, object], name: str, *, field: str) -> int:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"M3_PSV_INPUT_INVALID:{field}.{name}")
    return value


def _finite(mapping: Mapping[str, object], name: str, *, field: str) -> float:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"M3_PSV_INPUT_INVALID:{field}.{name}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"M3_PSV_INPUT_NONFINITE:{field}.{name}")
    return result


def _profile(payload: Mapping[str, object]) -> Mapping[str, object]:
    return _mapping(payload.get("profile"), field="profile")


def _profile_float(payload: Mapping[str, object], name: str) -> float:
    return _finite(_profile(payload), name, field="profile")


def _sha256(value: str, *, field: str) -> str:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"M3_PSV_INPUT_INVALID:{field}")
    return value


def _identity(payload: Mapping[str, object], prefix: str) -> tuple[str, str, str]:
    return (
        _text(payload, f"{prefix}_id", field=prefix),
        _text(payload, f"{prefix}_version", field=prefix),
        _sha256(
            _text(payload, f"{prefix}_hash", field=prefix),
            field=f"{prefix}_hash",
        ),
    )


def _guard(request: M2MetricPluginRequest) -> bool:
    definition = request.definition
    applicability = definition.applicability
    expected_operators = _EXPECTED_OPERATORS.get(definition.metric_code)
    expected_state_machines = _EXPECTED_STATE_MACHINES.get(definition.metric_code)
    expected_upstream = _EXPECTED_UPSTREAM.get(definition.metric_code)
    if (
        definition.metric_code not in M3_PSV_CODES
        or definition.family != M3_PSV_FAMILY
        or definition.subject_type != "MISSION_SYSTEM_INSTANCE"
        or definition.value_kind != "NUMERIC"
        or definition.observation_lane != "SYSTEM_PERFORMANCE_OBSERVATION"
        or definition.publication_route != "SYSTEM_PERFORMANCE_OBSERVATION"
        or applicability.applicability_mode != "SYSTEM_TYPE_SET"
        or applicability.allowed_system_types != M3_PSV_ALLOWED_SYSTEM_TYPES
        or expected_operators is None
        or definition.operator_bindings != expected_operators
        or expected_state_machines is None
        or definition.state_machine_bindings != expected_state_machines
        or expected_upstream is None
        or definition.upstream_dependencies != expected_upstream
    ):
        raise ValueError(f"M3_PSV_CATALOG_DEFINITION_DRIFT:{definition.metric_code}")
    system_type = _text(request.input_payload, "system_type", field=definition.metric_code)
    return system_type in M3_PSV_ALLOWED_SYSTEM_TYPES


def _operator(request: M2MetricPluginRequest, operator_id: str) -> Callable[..., object]:
    value = request.operators.get(operator_id)
    if value is None:
        raise ValueError(f"M3_PSV_OPERATOR_MISSING:{operator_id}")
    return value


def _operator_number(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"M3_PSV_OPERATOR_OUTPUT_INVALID:{field}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"M3_PSV_OPERATOR_OUTPUT_NONFINITE:{field}")
    return result


def _rms(request: M2MetricPluginRequest, values: Sequence[float]) -> float:
    return _operator_number(_operator(request, "RMS_V1")(values), field="RMS_V1")


def _median(request: M2MetricPluginRequest, values: Sequence[float]) -> float:
    return _operator_number(_operator(request, "MEDIAN_V1")(values), field="MEDIAN_V1")


def _quantile(
    request: M2MetricPluginRequest,
    values: Sequence[float],
    probability: float,
) -> float:
    return _operator_number(
        _operator(request, "QUANTILE_HF7_V1")(values, probability),
        field="QUANTILE_HF7_V1",
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
            raise ValueError("M3_PSV_VALID_VALUE_INVALID")
    elif value_numeric is not None:
        raise ValueError("M3_PSV_NONVALID_VALUE_FORBIDDEN")
    return {
        "status": status,
        "reason_codes": list(reason_codes),
        "value_kind": "NUMERIC",
        "value_numeric": value_numeric,
        "value_structured": None,
        "evidence": {} if evidence is None else dict(evidence),
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


def _not_applicable(request: M2MetricPluginRequest) -> Mapping[str, object]:
    return {
        "metric_code": request.definition.metric_code,
        "subject_type": request.definition.subject_type,
        "observation_lane": request.definition.observation_lane,
        "publication_route": request.definition.publication_route,
        "applicable": False,
        "instances": [],
    }


def _dependency_hash(request: M2MetricPluginRequest, metric_code: str) -> str:
    for code, digest in request.upstream_result_hashes:
        if code == metric_code:
            return digest
    raise ValueError(f"M3_PSV_UPSTREAM_RESULT_MISSING:{metric_code}")


def _vector3(value: object, *, field: str) -> tuple[float, float, float]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or len(value) != 3
    ):
        raise ValueError(f"M3_PSV_VECTOR_INVALID:{field}")
    result: list[float] = []
    for index, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"M3_PSV_VECTOR_INVALID:{field}[{index}]")
        number = float(item)
        if not math.isfinite(number):
            raise ValueError(f"M3_PSV_VECTOR_NONFINITE:{field}[{index}]")
        result.append(number)
    return result[0], result[1], result[2]


def _intervals(
    payload: Mapping[str, object],
    name: str,
) -> tuple[tuple[int, int], ...]:
    result: list[tuple[int, int]] = []
    for index, row in enumerate(_mappings(payload.get(name), field=name)):
        field = f"{name}[{index}]"
        start = _integer(row, "start_session_time_us", field=field)
        end = _integer(row, "end_session_time_us", field=field)
        if end <= start:
            raise ValueError(f"M3_PSV_INTERVAL_INVALID:{field}")
        result.append((start, end))
    return tuple(result)


def _merged(intervals: Sequence[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    if not intervals:
        return ()
    ordered = sorted(intervals)
    result: list[list[int]] = [[ordered[0][0], ordered[0][1]]]
    for start, end in ordered[1:]:
        current = result[-1]
        if start <= current[1]:
            current[1] = max(current[1], end)
        else:
            result.append([start, end])
    return tuple((item[0], item[1]) for item in result)


def _intersection_duration(
    left: Sequence[tuple[int, int]],
    right: Sequence[tuple[int, int]],
) -> int:
    return sum(
        max(0, min(left_end, right_end) - max(left_start, right_start))
        for left_start, left_end in _merged(left)
        for right_start, right_end in _merged(right)
    )


def _quality_rmse(
    request: M2MetricPluginRequest,
    *,
    domain: str,
    residual: Callable[[Mapping[str, object], str], float],
) -> Mapping[str, object]:
    profile = _identity(request.input_payload, "reference_match_quality_profile")
    qa_hashes = {
        code: _dependency_hash(request, code)
        for code in ("P1-QA-001", "P1-QA-002", "P1-QA-005")
    }
    values: list[float] = []
    rejected = 0
    for index, sample in enumerate(_mappings(request.input_payload.get("samples"), field="samples")):
        field = f"samples[{index}]"
        accepted = sample.get("reference_match_accepted")
        if not isinstance(accepted, bool):
            raise ValueError(f"M3_PSV_REFERENCE_MATCH_STATUS_INVALID:{field}")
        actual_domain = _text(sample, "error_domain", field=field)
        if actual_domain != domain:
            raise ValueError(f"M3_PSV_REFERENCE_ERROR_DOMAIN_INVALID:{field}:{actual_domain}")
        if accepted:
            values.append(residual(sample, field))
        else:
            rejected += 1
    if not values:
        return _missing(
            request,
            "REFERENCE_MATCH_QUALITY_REJECTED_ALL",
            evidence={
                "reference_match_quality_profile": list(profile),
                "qa_result_hashes": qa_hashes,
                "rejected_count": rejected,
            },
        )
    return _output(
        request,
        value_numeric=_rms(request, values),
        evidence={
            "reference_match_quality_profile": list(profile),
            "qa_result_hashes": qa_hashes,
            "eligible_count": len(values),
            "rejected_count": rejected,
            "residuals": values,
        },
    )


def _los_angular_residual(sample: Mapping[str, object], field: str) -> float:
    measured = _vector3(sample.get("measured_los_unit"), field=f"{field}.measured_los_unit")
    reference = _vector3(sample.get("reference_los_unit"), field=f"{field}.reference_los_unit")
    measured_norm = math.sqrt(sum(value * value for value in measured))
    reference_norm = math.sqrt(sum(value * value for value in reference))
    if measured_norm == 0.0 or reference_norm == 0.0:
        raise ValueError("M3_PSV_ZERO_LOS_VECTOR")
    dot = sum(
        measured[index] * reference[index]
        for index in range(3)
    ) / (measured_norm * reference_norm)
    return math.acos(max(-1.0, min(1.0, dot)))


def _los_rate_residual(sample: Mapping[str, object], field: str) -> float:
    return _finite(sample, "measured_los_rate_rad_s", field=field) - _finite(
        sample, "reference_los_rate_rad_s", field=field
    )


def _range_residual(sample: Mapping[str, object], field: str) -> float:
    return _finite(sample, "passive_range_estimate_m", field=field) - _finite(
        sample, "reference_range_m", field=field
    )


def _psv001(request: M2MetricPluginRequest) -> Mapping[str, object]:
    return _quality_rmse(
        request,
        domain="LOS_ANGLE",
        residual=_los_angular_residual,
    )


def _psv002(request: M2MetricPluginRequest) -> Mapping[str, object]:
    return _quality_rmse(
        request,
        domain="LOS_RATE",
        residual=_los_rate_residual,
    )


def _psv003(request: M2MetricPluginRequest) -> Mapping[str, object]:
    return _quality_rmse(
        request,
        domain="RANGE",
        residual=_range_residual,
    )


def _psv004(request: M2MetricPluginRequest) -> Mapping[str, object]:
    opportunity_profile = _identity(request.input_payload, "opportunity_profile")
    confirmation_profile = _identity(request.input_payload, "confirmation_profile")
    opportunities = _mappings(
        request.input_payload.get("evaluation_opportunity_intervals"),
        field="evaluation_opportunity_intervals",
    )
    confirmations = _mappings(
        request.input_payload.get("confirmation_events"),
        field="confirmation_events",
    )
    opportunity_ids: set[str] = set()
    reference_by_opportunity: dict[str, str] = {}
    for index, item in enumerate(opportunities):
        field = f"evaluation_opportunity_intervals[{index}]"
        opportunity_id = _text(item, "detection_opportunity_id", field=field)
        if opportunity_id in opportunity_ids:
            raise ValueError(f"M3_PSV_OPPORTUNITY_DUPLICATE:{opportunity_id}")
        opportunity_ids.add(opportunity_id)
        reference_by_opportunity[opportunity_id] = _text(
            item, "reference_target_id", field=field
        )
        start = _integer(item, "start_session_time_us", field=field)
        end = _integer(item, "end_session_time_us", field=field)
        if end <= start:
            raise ValueError(f"M3_PSV_INTERVAL_INVALID:{field}")
    if not opportunities:
        return _missing(request, "NO_VALID_PASSIVE_OPPORTUNITY")
    detected: set[str] = set()
    event_ids: list[str] = []
    for index, event in enumerate(confirmations):
        field = f"confirmation_events[{index}]"
        event_id = _text(event, "detection_confirmation_event_id", field=field)
        opportunity_id = _text(event, "detection_opportunity_id", field=field)
        if opportunity_id not in opportunity_ids:
            raise ValueError(f"M3_PSV_CONFIRMATION_OPPORTUNITY_UNRESOLVED:{event_id}")
        if _text(event, "reference_target_id", field=field) != reference_by_opportunity[opportunity_id]:
            raise ValueError(f"M3_PSV_CONFIRMATION_ASSOCIATION_MISMATCH:{event_id}")
        detected.add(opportunity_id)
        event_ids.append(event_id)
    return _output(
        request,
        value_numeric=len(detected) / len(opportunities),
        evidence={
            "opportunity_profile": list(opportunity_profile),
            "confirmation_profile": list(confirmation_profile),
            "opportunity_ids": sorted(opportunity_ids),
            "confirmation_event_ids": sorted(event_ids),
        },
    )


def _psv005(request: M2MetricPluginRequest) -> Mapping[str, object]:
    opportunity_profile = _identity(request.input_payload, "opportunity_profile")
    opportunities = _intervals(
        request.input_payload,
        "evaluation_opportunity_intervals",
    )
    valid = _intervals(request.input_payload, "passive_track_valid_intervals")
    duration = sum(end - start for start, end in _merged(opportunities))
    if duration <= 0:
        return _missing(request, "NO_VALID_PASSIVE_OPPORTUNITY")
    valid_duration = _intersection_duration(valid, opportunities)
    return _output(
        request,
        value_numeric=valid_duration / duration,
        evidence={
            "opportunity_profile": list(opportunity_profile),
            "opportunity_duration_us": duration,
            "valid_passive_track_opportunity_intersection_us": valid_duration,
        },
    )


def _psv006(request: M2MetricPluginRequest) -> Mapping[str, object]:
    drop_min = _profile_float(request.input_payload, "drop_min_duration_s")
    persistence = _profile_float(
        request.input_payload, "reacquisition_persistence_s"
    )
    max_gap = _profile_float(request.input_payload, "max_gap_us")
    if drop_min <= 0.0 or persistence <= 0.0 or max_gap <= 0.0:
        raise ValueError("M3_PSV_REACQUISITION_PROFILE_INVALID")
    delays: list[float] = []
    excluded = 0
    for index, event in enumerate(
        _mappings(request.input_payload.get("reacquisition_events"), field="reacquisition_events")
    ):
        field = f"reacquisition_events[{index}]"
        drop_start = _integer(event, "passive_drop_time_us", field=field)
        reacquired = _integer(event, "passive_reacquired_time_us", field=field)
        invalid_dwell = _finite(event, "invalid_dwell_s", field=field)
        stable_dwell = _finite(event, "stable_persistence_s", field=field)
        same_association = event.get("same_reference_association")
        if not isinstance(same_association, bool):
            raise ValueError(f"M3_PSV_INPUT_INVALID:{field}.same_reference_association")
        if reacquired < drop_start:
            raise ValueError(f"M3_PSV_REACQUISITION_TIME_INVALID:{field}")
        if (
            invalid_dwell < drop_min
            or stable_dwell < persistence
            or not same_association
        ):
            excluded += 1
            continue
        delays.append((reacquired - drop_start) / 1_000_000.0)
    if not delays:
        return _missing(
            request,
            "NO_QUALIFIED_PASSIVE_REACQUISITION",
            evidence={"excluded_event_count": excluded},
        )
    median = _median(request, delays)
    p95 = _quantile(request, delays, 0.95)
    return _output(
        request,
        value_numeric=median,
        evidence={
            "drop_min_duration_s": drop_min,
            "reacquisition_persistence_s": persistence,
            "max_gap_us": int(max_gap),
            "qualified_reacquisition_delays_s": delays,
            "p95_reacquisition_delay_s": p95,
            "excluded_event_count": excluded,
        },
    )


def _psv007(request: M2MetricPluginRequest) -> Mapping[str, object]:
    persistence = _profile_float(request.input_payload, "stable_track_persistence_s")
    max_gap = _profile_float(request.input_payload, "max_gap_us")
    if persistence <= 0.0 or max_gap <= 0.0:
        raise ValueError("M3_PSV_STABLE_TRACK_PROFILE_INVALID")
    coverage = _identity(request.input_payload, "reference_target_coverage")
    coverage_status = _text(
        request.input_payload,
        "reference_target_coverage_status",
        field="P1-PSV-007",
    )
    evaluation_start = _integer(
        request.input_payload, "evaluation_start_time_us", field="P1-PSV-007"
    )
    evaluation_end = _integer(
        request.input_payload, "evaluation_end_time_us", field="P1-PSV-007"
    )
    coverage_start = _integer(
        request.input_payload, "coverage_start_time_us", field="P1-PSV-007"
    )
    coverage_end = _integer(
        request.input_payload, "coverage_end_time_us", field="P1-PSV-007"
    )
    if evaluation_end <= evaluation_start or coverage_end <= coverage_start:
        raise ValueError("M3_PSV_REFERENCE_COVERAGE_INTERVAL_INVALID")
    if (
        coverage_status != "COMPLETE"
        or coverage_start > evaluation_start
        or coverage_end < evaluation_end
    ):
        return _missing(
            request,
            "REFERENCE_TARGET_SET_COVERAGE_INCOMPLETE",
            evidence={
                "reference_target_coverage": list(coverage),
                "reference_target_coverage_status": coverage_status,
            },
        )
    qualified = 0
    false_tracks = 0
    ambiguous = 0
    seen: set[str] = set()
    for index, track in enumerate(_mappings(request.input_payload.get("passive_tracks"), field="passive_tracks")):
        field = f"passive_tracks[{index}]"
        track_id = _text(track, "track_id", field=field)
        if track_id in seen:
            raise ValueError(f"M3_PSV_TRACK_DUPLICATE:{track_id}")
        seen.add(track_id)
        start = _integer(track, "stable_start_time_us", field=field)
        end = _integer(track, "stable_end_time_us", field=field)
        if end <= start:
            raise ValueError(f"M3_PSV_INTERVAL_INVALID:{field}")
        if (end - start) / 1_000_000.0 < persistence:
            continue
        association = _text(track, "association_status", field=field)
        if association == "AMBIGUOUS":
            ambiguous += 1
            continue
        if association not in {"MATCHED", "NO_MATCH"}:
            raise ValueError(f"M3_PSV_ASSOCIATION_STATUS_INVALID:{association}")
        qualified += 1
        if association == "NO_MATCH":
            false_tracks += 1
    if qualified == 0:
        return _missing(request, "NO_QUALIFIED_PASSIVE_TRACKS")
    return _output(
        request,
        value_numeric=false_tracks / qualified,
        evidence={
            "reference_target_coverage": list(coverage),
            "reference_target_coverage_status": coverage_status,
            "stable_track_persistence_s": persistence,
            "max_gap_us": int(max_gap),
            "qualified_track_count": qualified,
            "false_track_count": false_tracks,
            "excluded_ambiguous_track_count": ambiguous,
        },
    )


_HANDLERS: Mapping[
    str,
    Callable[[M2MetricPluginRequest], Mapping[str, object]],
] = MappingProxyType(
    {
        "P1-PSV-001": _psv001,
        "P1-PSV-002": _psv002,
        "P1-PSV-003": _psv003,
        "P1-PSV-004": _psv004,
        "P1-PSV-005": _psv005,
        "P1-PSV-006": _psv006,
        "P1-PSV-007": _psv007,
    }
)


def _plugin(request: M2MetricPluginRequest) -> Mapping[str, object]:
    if not _guard(request):
        return _not_applicable(request)
    handler = _HANDLERS.get(request.definition.metric_code)
    if handler is None:
        raise ValueError(f"M3_PSV_PLUGIN_MISSING:{request.definition.metric_code}")
    return handler(request)


M3_PSV_PLUGINS: Mapping[str, M2MetricPlugin] = MappingProxyType(
    {code: _plugin for code in M3_PSV_CODES}
)


def register_m3_passive_plugins(
    plan: M2MetricExecutionPlan,
    registry: MetricPluginRegistry,
) -> None:
    """Register the exact seven passive-sensor algorithms in the shared registry."""

    definitions = tuple(
        definition
        for definition in plan.definitions
        if definition.metric_code in M3_PSV_CODES
    )
    if (
        len(definitions) != 7
        or {item.metric_code for item in definitions} != set(M3_PSV_CODES)
        or {item.family for item in definitions} != {M3_PSV_FAMILY}
    ):
        raise CatalogMetricEngineError(
            "M3_PSV_DELIVERY_MEMBERSHIP_DRIFT",
            repr(tuple(item.metric_code for item in definitions)),
        )
    for definition in definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"m3-passive-remainder:{definition.metric_code}:v1",
            plugin=_plugin,
        )
