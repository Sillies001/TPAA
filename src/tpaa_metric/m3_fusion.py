"""M3-MET-008 Catalog plugins for the exact P1 fusion remainder.

P1-FUS-001..008 execute through the shared CatalogMetricEngine. Applicability
is frozen to the FUSION mission-system type; every other type fails closed
without manufacturing observations.
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

M3_FUS_CODES = tuple(f"P1-FUS-{index:03d}" for index in range(1, 9))
M3_FUS_FAMILY = "SENSOR_FUSION"
M3_FUS_ALLOWED_SYSTEM_TYPES = ("FUSION",)

_EXPECTED_OPERATORS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "P1-FUS-001": ("RMS_V1",),
        "P1-FUS-002": ("RMS_V1",),
        "P1-FUS-003": (),
        "P1-FUS-004": (),
        "P1-FUS-005": (),
        "P1-FUS-006": (),
        "P1-FUS-007": (),
        "P1-FUS-008": ("CV_PROPAGATION_V1",),
    }
)
_EXPECTED_STATE_MACHINES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "P1-FUS-001": (),
        "P1-FUS-002": (),
        "P1-FUS-003": ("SM_FUSION_CAUSAL_MATCH_V1",),
        "P1-FUS-004": (),
        "P1-FUS-005": ("SM_ASSOCIATION_EPISODE_V1",),
        "P1-FUS-006": ("SM_ASSOCIATION_EPISODE_V1",),
        "P1-FUS-007": (),
        "P1-FUS-008": (),
    }
)
_EXPECTED_UPSTREAM: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "P1-FUS-001": (
            "CONTRACT_FUSION_PROVENANCE_V1",
            "CONTRACT_TRACK_VALIDITY_V1",
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "CONTRACT_REFERENCE_RELATIVE_STATE_V1",
            "P1-QA-005",
            "CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1",
        ),
        "P1-FUS-002": (
            "CONTRACT_FUSION_PROVENANCE_V1",
            "CONTRACT_TRACK_VALIDITY_V1",
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "CONTRACT_REFERENCE_RELATIVE_STATE_V1",
            "P1-QA-005",
            "CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1",
        ),
        "P1-FUS-003": (
            "CONTRACT_FUSION_PROVENANCE_V1",
            "CONTRACT_TIME_TRANSFORM_V1",
        ),
        "P1-FUS-004": (
            "CONTRACT_FUSION_PROVENANCE_V1",
            "CONTRACT_TRACK_VALIDITY_V1",
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "CONTRACT_REFERENCE_RELATIVE_STATE_V1",
            "CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1",
        ),
        "P1-FUS-005": (
            "CONTRACT_FUSION_PROVENANCE_V1",
            "CONTRACT_ASSOCIATION_RELATION_V1",
        ),
        "P1-FUS-006": (
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "CONTRACT_FUSION_PROVENANCE_V1",
        ),
        "P1-FUS-007": (
            "CONTRACT_FUSION_PROVENANCE_V1",
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "CONTRACT_FUSION_HANDOVER_EVENT_V1",
        ),
        "P1-FUS-008": (
            "CONTRACT_FUSION_PROVENANCE_V1",
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "CONTRACT_FUSION_HANDOVER_EVENT_V1",
        ),
    }
)


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"M3_FUS_INPUT_INVALID:{field}")
    return cast(Mapping[str, object], value)


def _mappings(value: object, *, field: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"M3_FUS_INPUT_INVALID:{field}")
    return tuple(
        _mapping(item, field=f"{field}[{index}]")
        for index, item in enumerate(value)
    )


def _text(mapping: Mapping[str, object], name: str, *, field: str) -> str:
    value = mapping.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"M3_FUS_INPUT_INVALID:{field}.{name}")
    return value


def _integer(mapping: Mapping[str, object], name: str, *, field: str) -> int:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"M3_FUS_INPUT_INVALID:{field}.{name}")
    return value


def _finite(mapping: Mapping[str, object], name: str, *, field: str) -> float:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"M3_FUS_INPUT_INVALID:{field}.{name}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"M3_FUS_INPUT_NONFINITE:{field}.{name}")
    return result


def _positive_float(mapping: Mapping[str, object], name: str, *, field: str) -> float:
    value = _finite(mapping, name, field=field)
    if value <= 0.0:
        raise ValueError(f"M3_FUS_INPUT_NONPOSITIVE:{field}.{name}")
    return value


def _positive_integer(mapping: Mapping[str, object], name: str, *, field: str) -> int:
    value = _integer(mapping, name, field=field)
    if value <= 0:
        raise ValueError(f"M3_FUS_INPUT_NONPOSITIVE:{field}.{name}")
    return value


def _sha256(value: str, *, field: str) -> str:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"M3_FUS_INPUT_INVALID:{field}")
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
        definition.metric_code not in M3_FUS_CODES
        or definition.family != M3_FUS_FAMILY
        or definition.subject_type != "MISSION_SYSTEM_INSTANCE"
        or definition.value_kind != "NUMERIC"
        or definition.observation_lane != "SYSTEM_PERFORMANCE_OBSERVATION"
        or definition.publication_route != "SYSTEM_PERFORMANCE_OBSERVATION"
        or applicability.applicability_mode != "SYSTEM_TYPE_EXACT"
        or applicability.allowed_system_types != M3_FUS_ALLOWED_SYSTEM_TYPES
        or expected_operators is None
        or definition.operator_bindings != expected_operators
        or expected_state_machines is None
        or definition.state_machine_bindings != expected_state_machines
        or expected_upstream is None
        or definition.upstream_dependencies != expected_upstream
    ):
        raise ValueError(f"M3_FUS_CATALOG_DEFINITION_DRIFT:{definition.metric_code}")
    system_type = _text(
        request.input_payload,
        "system_type",
        field=definition.metric_code,
    )
    return system_type == "FUSION"


def _operator(request: M2MetricPluginRequest, operator_id: str) -> Callable[..., object]:
    value = request.operators.get(operator_id)
    if value is None:
        raise ValueError(f"M3_FUS_OPERATOR_MISSING:{operator_id}")
    return value


def _operator_number(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"M3_FUS_OPERATOR_OUTPUT_INVALID:{field}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"M3_FUS_OPERATOR_OUTPUT_NONFINITE:{field}")
    return result


def _rms(request: M2MetricPluginRequest, values: Sequence[float]) -> float:
    return _operator_number(_operator(request, "RMS_V1")(values), field="RMS_V1")


def _instance(
    *,
    status: str,
    reason_codes: Sequence[str] = (),
    value_numeric: float | None = None,
    evidence: Mapping[str, object] | None = None,
) -> dict[str, object]:
    if status == "VALID":
        if value_numeric is None or not math.isfinite(value_numeric):
            raise ValueError("M3_FUS_VALID_VALUE_INVALID")
    elif value_numeric is not None:
        raise ValueError("M3_FUS_NONVALID_VALUE_FORBIDDEN")
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
    raise ValueError(f"M3_FUS_UPSTREAM_RESULT_MISSING:{metric_code}")


def _vector3(value: object, *, field: str) -> tuple[float, float, float]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or len(value) != 3
    ):
        raise ValueError(f"M3_FUS_VECTOR_INVALID:{field}")
    result: list[float] = []
    for index, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"M3_FUS_VECTOR_INVALID:{field}[{index}]")
        number = float(item)
        if not math.isfinite(number):
            raise ValueError(f"M3_FUS_VECTOR_NONFINITE:{field}[{index}]")
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
            raise ValueError(f"M3_FUS_INTERVAL_INVALID:{field}")
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


def _duration(intervals: Sequence[tuple[int, int]]) -> int:
    return sum(end - start for start, end in _merged(intervals))


def _intersection_duration(
    left: Sequence[tuple[int, int]],
    right: Sequence[tuple[int, int]],
) -> int:
    return sum(
        max(0, min(left_end, right_end) - max(left_start, right_start))
        for left_start, left_end in _merged(left)
        for right_start, right_end in _merged(right)
    )


def _quality_vector_rmse(
    request: M2MetricPluginRequest,
    *,
    domain: str,
    fused_field: str,
    reference_field: str,
) -> Mapping[str, object]:
    profile = _identity(request.input_payload, "reference_match_quality_profile")
    qa005_hash = _dependency_hash(request, "P1-QA-005")
    residual_norms: list[float] = []
    rejected = 0
    for index, sample in enumerate(
        _mappings(request.input_payload.get("samples"), field="samples")
    ):
        field = f"samples[{index}]"
        accepted = sample.get("reference_match_accepted")
        if not isinstance(accepted, bool):
            raise ValueError(f"M3_FUS_REFERENCE_MATCH_STATUS_INVALID:{field}")
        actual_domain = _text(sample, "error_domain", field=field)
        if actual_domain != domain:
            raise ValueError(
                f"M3_FUS_REFERENCE_ERROR_DOMAIN_INVALID:{field}:{actual_domain}"
            )
        if not accepted:
            rejected += 1
            continue
        if sample.get("fused_track_valid") is not True:
            raise ValueError(f"M3_FUS_TRACK_VALIDITY_INVALID:{field}")
        if sample.get("fusion_provenance_resolved") is not True:
            raise ValueError(f"M3_FUS_PROVENANCE_UNRESOLVED:{field}")
        if sample.get("association_resolved") is not True:
            raise ValueError(f"M3_FUS_ASSOCIATION_UNRESOLVED:{field}")
        source_members = sample.get("source_member_ids")
        if (
            not isinstance(source_members, Sequence)
            or isinstance(source_members, (str, bytes))
            or not source_members
            or not all(isinstance(item, str) and item for item in source_members)
        ):
            raise ValueError(f"M3_FUS_SOURCE_MEMBERSHIP_INVALID:{field}")
        fused = _vector3(sample.get(fused_field), field=f"{field}.{fused_field}")
        reference = _vector3(
            sample.get(reference_field),
            field=f"{field}.{reference_field}",
        )
        residual_norms.append(
            math.sqrt(
                sum(
                    (fused[axis] - reference[axis]) ** 2
                    for axis in range(3)
                )
            )
        )
    if not residual_norms:
        return _missing(
            request,
            "REFERENCE_MATCH_QUALITY_REJECTED_ALL",
            evidence={
                "reference_match_quality_profile": list(profile),
                "p1_qa_005_result_hash": qa005_hash,
                "rejected_count": rejected,
            },
        )
    return _output(
        request,
        value_numeric=_rms(request, residual_norms),
        evidence={
            "reference_match_quality_profile": list(profile),
            "p1_qa_005_result_hash": qa005_hash,
            "eligible_count": len(residual_norms),
            "rejected_count": rejected,
            "residual_norms": residual_norms,
        },
    )


def _fus001(request: M2MetricPluginRequest) -> Mapping[str, object]:
    return _quality_vector_rmse(
        request,
        domain="POSITION_3D",
        fused_field="fused_track_position_ecef_m",
        reference_field="reference_target_position_ecef_m",
    )


def _fus002(request: M2MetricPluginRequest) -> Mapping[str, object]:
    return _quality_vector_rmse(
        request,
        domain="VELOCITY_3D",
        fused_field="fused_track_velocity_ecef_mps",
        reference_field="reference_target_velocity_ecef_mps",
    )


def _fus003(request: M2MetricPluginRequest) -> Mapping[str, object]:
    fused_update_id = _text(
        request.input_payload,
        "fused_update_id",
        field="P1-FUS-003",
    )
    fused_time = _integer(
        request.input_payload,
        "fused_state_effective_time_us",
        field="P1-FUS-003",
    )
    sources = _mappings(
        request.input_payload.get("provenance_source_updates"),
        field="provenance_source_updates",
    )
    eligible: list[tuple[int, str, int, str]] = []
    for index, source in enumerate(sources):
        field = f"provenance_source_updates[{index}]"
        source_id = _text(source, "source_id", field=field)
        sequence = _integer(source, "sequence", field=field)
        update_id = _text(source, "source_update_id", field=field)
        source_time = _integer(source, "source_update_effective_time_us", field=field)
        if source_time <= fused_time:
            eligible.append((source_time, source_id, sequence, update_id))
    if not eligible:
        return _missing(request, "FUSION_CAUSAL_SOURCE_UPDATE_UNRESOLVED")
    latest_time = max(item[0] for item in eligible)
    latest = min(
        (item for item in eligible if item[0] == latest_time),
        key=lambda item: (item[1], item[2], item[3]),
    )
    latency_s = (fused_time - latest[0]) / 1_000_000.0
    return _output(
        request,
        value_numeric=latency_s,
        evidence={
            "fused_update_id": fused_update_id,
            "selected_source_update_id": latest[3],
            "selected_source_id": latest[1],
            "selected_source_sequence": latest[2],
            "source_update_effective_time_us": latest[0],
            "fused_state_effective_time_us": fused_time,
        },
    )


def _fus004(request: M2MetricPluginRequest) -> Mapping[str, object]:
    opportunity_profile = _identity(request.input_payload, "opportunity_profile")
    if request.input_payload.get("fusion_provenance_resolved") is not True:
        return _missing(request, "FUSION_PROVENANCE_UNRESOLVED")
    if request.input_payload.get("association_resolved") is not True:
        return _missing(request, "FUSION_ASSOCIATION_UNRESOLVED")
    opportunities = _intervals(
        request.input_payload,
        "fused_opportunity_intervals",
    )
    valid = _intervals(request.input_payload, "fused_track_valid_intervals")
    duration = _duration(opportunities)
    if duration <= 0:
        return _missing(request, "NO_VALID_FUSED_OPPORTUNITY")
    valid_duration = _intersection_duration(valid, opportunities)
    return _output(
        request,
        value_numeric=valid_duration / duration,
        evidence={
            "opportunity_profile": list(opportunity_profile),
            "opportunity_duration_us": duration,
            "valid_fused_track_opportunity_intersection_us": valid_duration,
        },
    )


def _fus005(request: M2MetricPluginRequest) -> Mapping[str, object]:
    profile = _mapping(request.input_payload.get("profile"), field="profile")
    persistence_s = _positive_float(
        profile,
        "duplicate_persistence_s",
        field="profile",
    )
    if request.input_payload.get("fusion_provenance_resolved") is not True:
        return _missing(request, "FUSION_PROVENANCE_UNRESOLVED")
    if request.input_payload.get("association_resolved") is not True:
        return _missing(request, "FUSION_ASSOCIATION_UNRESOLVED")
    eligible = _intervals(request.input_payload, "eligible_target_intervals")
    duplicate_episodes = _intervals(request.input_payload, "duplicate_episode_intervals")
    eligible_duration = _duration(eligible)
    if eligible_duration <= 0:
        return _missing(request, "NO_ELIGIBLE_ASSOCIATED_TARGET_DWELL")
    minimum_us = int(round(persistence_s * 1_000_000.0))
    qualified = tuple(
        interval
        for interval in duplicate_episodes
        if interval[1] - interval[0] >= minimum_us
    )
    duplicate_duration = _intersection_duration(qualified, eligible)
    if duplicate_duration > eligible_duration:
        raise ValueError("M3_FUS_DUPLICATE_DWELL_EXCEEDS_ELIGIBLE")
    return _output(
        request,
        value_numeric=1.0 - duplicate_duration / eligible_duration,
        evidence={
            "duplicate_persistence_s": persistence_s,
            "eligible_target_dwell_us": eligible_duration,
            "duplicate_fused_track_dwell_us": duplicate_duration,
            "qualified_duplicate_episode_count": len(qualified),
        },
    )


def _fus006(request: M2MetricPluginRequest) -> Mapping[str, object]:
    intervals = _mappings(
        request.input_payload.get("source_track_membership"),
        field="source_track_membership",
    )
    correct_us = 0
    fused_associated_us = 0
    for index, interval in enumerate(intervals):
        field = f"source_track_membership[{index}]"
        start = _integer(interval, "start_session_time_us", field=field)
        end = _integer(interval, "end_session_time_us", field=field)
        if end <= start:
            raise ValueError(f"M3_FUS_INTERVAL_INVALID:{field}")
        _text(interval, "fused_track_id", field=field)
        _text(interval, "source_track_id", field=field)
        _text(interval, "reference_target_id", field=field)
        correct = interval.get("membership_correct")
        if not isinstance(correct, bool):
            raise ValueError(f"M3_FUS_MEMBERSHIP_CORRECT_INVALID:{field}")
        dwell = end - start
        fused_associated_us += dwell
        if correct:
            correct_us += dwell
    if fused_associated_us <= 0:
        return _missing(request, "NO_ELIGIBLE_FUSED_ASSOCIATED_DWELL")
    return _output(
        request,
        value_numeric=correct_us / fused_associated_us,
        evidence={
            "correct_membership_dwell_us": correct_us,
            "fused_associated_dwell_us": fused_associated_us,
        },
    )


def _fus007(request: M2MetricPluginRequest) -> Mapping[str, object]:
    events = _mappings(request.input_payload.get("handover_events"), field="handover_events")
    qualified = 0
    preserved = 0
    event_ids: list[str] = []
    profile_identities: set[tuple[str, str, str]] = set()
    for index, event in enumerate(events):
        field = f"handover_events[{index}]"
        event_id = _text(event, "handover_event_id", field=field)
        _text(event, "reference_target_id", field=field)
        _text(event, "pre_fused_track_id", field=field)
        _text(event, "post_fused_track_id", field=field)
        _integer(event, "handover_time_us", field=field)
        status = _text(event, "qualification_status", field=field)
        if status not in {"QUALIFIED", "REJECTED"}:
            raise ValueError(f"M3_FUS_HANDOVER_QUALIFICATION_INVALID:{field}")
        profile = (
            _text(event, "handover_profile_id", field=field),
            _text(event, "handover_profile_version", field=field),
            _sha256(
                _text(event, "handover_profile_hash", field=field),
                field=f"{field}.handover_profile_hash",
            ),
        )
        profile_identities.add(profile)
        if status != "QUALIFIED":
            continue
        identity_preserved = event.get("identity_preserved")
        if not isinstance(identity_preserved, bool):
            raise ValueError(f"M3_FUS_HANDOVER_IDENTITY_INVALID:{field}")
        if event.get("association_resolved") is not True:
            raise ValueError(f"M3_FUS_HANDOVER_ASSOCIATION_UNRESOLVED:{field}")
        if event.get("fusion_provenance_resolved") is not True:
            raise ValueError(f"M3_FUS_HANDOVER_PROVENANCE_UNRESOLVED:{field}")
        qualified += 1
        preserved += int(identity_preserved)
        event_ids.append(event_id)
    if len(profile_identities) > 1:
        raise ValueError("M3_FUS_HANDOVER_PROFILE_MIXED")
    if qualified == 0:
        return _missing(request, "NO_CANONICAL_QUALIFIED_HANDOVER_EVENT")
    return _output(
        request,
        value_numeric=preserved / qualified,
        evidence={
            "qualified_handover_event_ids": sorted(event_ids),
            "qualified_handover_event_count": qualified,
            "identity_preserved_event_count": preserved,
            "handover_profile": (
                list(next(iter(profile_identities)))
                if profile_identities
                else None
            ),
        },
    )


def _fus008(request: M2MetricPluginRequest) -> Mapping[str, object]:
    event_id = _text(request.input_payload, "handover_event_id", field="P1-FUS-008")
    _text(request.input_payload, "pre_fused_track_id", field="P1-FUS-008")
    _text(request.input_payload, "post_fused_track_id", field="P1-FUS-008")
    _text(request.input_payload, "reference_target_id", field="P1-FUS-008")
    if _text(
        request.input_payload,
        "qualification_status",
        field="P1-FUS-008",
    ) != "QUALIFIED":
        return _missing(request, "HANDOVER_EVENT_NOT_QUALIFIED")
    _identity(request.input_payload, "handover_profile")
    handover_time = _integer(
        request.input_payload,
        "handover_time_us",
        field="P1-FUS-008",
    )
    pre_time = _integer(
        request.input_payload,
        "pre_handover_state_time_us",
        field="P1-FUS-008",
    )
    profile = _mapping(request.input_payload.get("profile"), field="profile")
    max_age_us = _positive_integer(
        profile,
        "max_propagation_age_us",
        field="profile",
    )
    age_us = handover_time - pre_time
    if age_us < 0:
        raise ValueError("M3_FUS_HANDOVER_PRE_STATE_AFTER_EVENT")
    if age_us > max_age_us:
        return _missing(
            request,
            "PRE_HANDOVER_STATE_PROPAGATION_AGE_EXCEEDED",
            evidence={
                "handover_event_id": event_id,
                "propagation_age_us": age_us,
                "max_propagation_age_us": max_age_us,
            },
        )
    before = _vector3(
        request.input_payload.get("fused_position_before"),
        field="fused_position_before",
    )
    velocity = _vector3(
        request.input_payload.get("fused_velocity_before"),
        field="fused_velocity_before",
    )
    after = _vector3(
        request.input_payload.get("fused_position_after"),
        field="fused_position_after",
    )
    propagated_raw = _operator(request, "CV_PROPAGATION_V1")(
        before,
        velocity,
        start_time_us=pre_time,
        end_time_us=handover_time,
        max_propagation_age_us=max_age_us,
    )
    propagated = _vector3(propagated_raw, field="cv_propagated_position")
    jump = math.sqrt(
        sum((after[axis] - propagated[axis]) ** 2 for axis in range(3))
    )
    return _output(
        request,
        value_numeric=jump,
        evidence={
            "handover_event_id": event_id,
            "propagation_age_us": age_us,
            "max_propagation_age_us": max_age_us,
            "predicted_position_at_handover_m": list(propagated),
        },
    )


_HANDLERS: Mapping[
    str,
    Callable[[M2MetricPluginRequest], Mapping[str, object]],
] = MappingProxyType(
    {
        "P1-FUS-001": _fus001,
        "P1-FUS-002": _fus002,
        "P1-FUS-003": _fus003,
        "P1-FUS-004": _fus004,
        "P1-FUS-005": _fus005,
        "P1-FUS-006": _fus006,
        "P1-FUS-007": _fus007,
        "P1-FUS-008": _fus008,
    }
)


def _plugin(request: M2MetricPluginRequest) -> Mapping[str, object]:
    if not _guard(request):
        return _not_applicable(request)
    handler = _HANDLERS.get(request.definition.metric_code)
    if handler is None:
        raise ValueError(f"M3_FUS_PLUGIN_MISSING:{request.definition.metric_code}")
    return handler(request)


M3_FUS_PLUGINS: Mapping[str, M2MetricPlugin] = MappingProxyType(
    {code: _plugin for code in M3_FUS_CODES}
)


def register_m3_fusion_plugins(
    plan: M2MetricExecutionPlan,
    registry: MetricPluginRegistry,
) -> None:
    """Register the exact eight fusion algorithms in the shared registry."""

    definitions = tuple(
        definition
        for definition in plan.definitions
        if definition.metric_code in M3_FUS_CODES
    )
    if (
        len(definitions) != 8
        or {item.metric_code for item in definitions} != set(M3_FUS_CODES)
        or {item.family for item in definitions} != {M3_FUS_FAMILY}
    ):
        raise CatalogMetricEngineError(
            "M3_FUS_DELIVERY_MEMBERSHIP_DRIFT",
            repr(tuple(item.metric_code for item in definitions)),
        )
    for definition in definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"m3-fusion-remainder:{definition.metric_code}:v1",
            plugin=_plugin,
        )
