"""M3-MET-007 Catalog plugins for the exact P1 datalink remainder.

P1-DL-001..008 execute through the shared CatalogMetricEngine. Applicability
is frozen to the DATALINK mission-system type; every other type fails closed
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

M3_DL_CODES = tuple(f"P1-DL-{index:03d}" for index in range(1, 9))
M3_DL_FAMILY = "DATALINK"
M3_DL_ALLOWED_SYSTEM_TYPES = ("DATALINK",)

_EXPECTED_OPERATORS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "P1-DL-001": (),
        "P1-DL-002": ("MAD_V1", "MEDIAN_V1", "QUANTILE_HF7_V1"),
        "P1-DL-003": (),
        "P1-DL-004": (),
        "P1-DL-005": (),
        "P1-DL-006": ("RMS_V1",),
        "P1-DL-007": ("RMS_V1",),
        "P1-DL-008": (),
    }
)
_EXPECTED_STATE_MACHINES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "P1-DL-001": (),
        "P1-DL-002": ("SM_VALIDITY_PIECE_V1",),
        "P1-DL-003": ("SM_DATALINK_SEQUENCE_EPOCH_V1",),
        "P1-DL-004": ("SM_DATALINK_SEQUENCE_EPOCH_V1",),
        "P1-DL-005": (),
        "P1-DL-006": (),
        "P1-DL-007": (),
        "P1-DL-008": (),
    }
)
_EXPECTED_UPSTREAM: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "P1-DL-001": ("CONTRACT_TIME_TRANSFORM_V1",),
        "P1-DL-002": ("P1-DL-001",),
        "P1-DL-003": ("CONTRACT_TDL_SEQUENCE_EPOCH_V1",),
        "P1-DL-004": ("CONTRACT_TDL_SEQUENCE_EPOCH_V1",),
        "P1-DL-005": (
            "CONTRACT_TRACK_VALIDITY_V1",
            "CONTRACT_TIME_TRANSFORM_V1",
        ),
        "P1-DL-006": (
            "CONTRACT_TRACK_VALIDITY_V1",
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "CONTRACT_REFERENCE_RELATIVE_STATE_V1",
            "P1-QA-005",
            "CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1",
        ),
        "P1-DL-007": (
            "CONTRACT_TRACK_VALIDITY_V1",
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "CONTRACT_REFERENCE_RELATIVE_STATE_V1",
            "P1-QA-005",
            "CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1",
        ),
        "P1-DL-008": (
            "CONTRACT_TRACK_VALIDITY_V1",
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "CONTRACT_REFERENCE_RELATIVE_STATE_V1",
            "CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1",
        ),
    }
)


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"M3_DL_INPUT_INVALID:{field}")
    return cast(Mapping[str, object], value)


def _mappings(value: object, *, field: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"M3_DL_INPUT_INVALID:{field}")
    return tuple(
        _mapping(item, field=f"{field}[{index}]")
        for index, item in enumerate(value)
    )


def _text(mapping: Mapping[str, object], name: str, *, field: str) -> str:
    value = mapping.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"M3_DL_INPUT_INVALID:{field}.{name}")
    return value


def _integer(mapping: Mapping[str, object], name: str, *, field: str) -> int:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"M3_DL_INPUT_INVALID:{field}.{name}")
    return value


def _finite(mapping: Mapping[str, object], name: str, *, field: str) -> float:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"M3_DL_INPUT_INVALID:{field}.{name}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"M3_DL_INPUT_NONFINITE:{field}.{name}")
    return result


def _positive_integer(mapping: Mapping[str, object], name: str, *, field: str) -> int:
    value = _integer(mapping, name, field=field)
    if value <= 0:
        raise ValueError(f"M3_DL_INPUT_NONPOSITIVE:{field}.{name}")
    return value


def _sha256(value: str, *, field: str) -> str:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"M3_DL_INPUT_INVALID:{field}")
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
        definition.metric_code not in M3_DL_CODES
        or definition.family != M3_DL_FAMILY
        or definition.subject_type != "MISSION_SYSTEM_INSTANCE"
        or definition.value_kind != "NUMERIC"
        or definition.observation_lane != "SYSTEM_PERFORMANCE_OBSERVATION"
        or definition.publication_route != "SYSTEM_PERFORMANCE_OBSERVATION"
        or applicability.applicability_mode != "SYSTEM_TYPE_EXACT"
        or applicability.allowed_system_types != M3_DL_ALLOWED_SYSTEM_TYPES
        or expected_operators is None
        or definition.operator_bindings != expected_operators
        or expected_state_machines is None
        or definition.state_machine_bindings != expected_state_machines
        or expected_upstream is None
        or definition.upstream_dependencies != expected_upstream
    ):
        raise ValueError(f"M3_DL_CATALOG_DEFINITION_DRIFT:{definition.metric_code}")
    system_type = _text(
        request.input_payload,
        "system_type",
        field=definition.metric_code,
    )
    return system_type == "DATALINK"


def _operator(request: M2MetricPluginRequest, operator_id: str) -> Callable[..., object]:
    value = request.operators.get(operator_id)
    if value is None:
        raise ValueError(f"M3_DL_OPERATOR_MISSING:{operator_id}")
    return value


def _operator_number(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"M3_DL_OPERATOR_OUTPUT_INVALID:{field}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"M3_DL_OPERATOR_OUTPUT_NONFINITE:{field}")
    return result


def _rms(request: M2MetricPluginRequest, values: Sequence[float]) -> float:
    return _operator_number(_operator(request, "RMS_V1")(values), field="RMS_V1")


def _median(request: M2MetricPluginRequest, values: Sequence[float]) -> float:
    return _operator_number(
        _operator(request, "MEDIAN_V1")(values),
        field="MEDIAN_V1",
    )


def _mad(request: M2MetricPluginRequest, values: Sequence[float]) -> float:
    return _operator_number(_operator(request, "MAD_V1")(values), field="MAD_V1")


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
            raise ValueError("M3_DL_VALID_VALUE_INVALID")
    elif value_numeric is not None:
        raise ValueError("M3_DL_NONVALID_VALUE_FORBIDDEN")
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
    raise ValueError(f"M3_DL_UPSTREAM_RESULT_MISSING:{metric_code}")


def _vector3(value: object, *, field: str) -> tuple[float, float, float]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or len(value) != 3
    ):
        raise ValueError(f"M3_DL_VECTOR_INVALID:{field}")
    result: list[float] = []
    for index, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"M3_DL_VECTOR_INVALID:{field}[{index}]")
        number = float(item)
        if not math.isfinite(number):
            raise ValueError(f"M3_DL_VECTOR_NONFINITE:{field}[{index}]")
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
            raise ValueError(f"M3_DL_INTERVAL_INVALID:{field}")
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


def _dl001(request: M2MetricPluginRequest) -> Mapping[str, object]:
    endpoint = _text(request.input_payload, "link_endpoint_id", field="P1-DL-001")
    send = _integer(
        request.input_payload,
        "message_send_time_us",
        field="P1-DL-001",
    )
    receive = _integer(
        request.input_payload,
        "message_receive_time_us",
        field="P1-DL-001",
    )
    if receive < send:
        raise ValueError("M3_DL_NEGATIVE_MESSAGE_LATENCY")
    return _output(
        request,
        value_numeric=(receive - send) / 1_000_000.0,
        evidence={
            "link_endpoint_id": endpoint,
            "message_send_time_us": send,
            "message_receive_time_us": receive,
        },
    )


def _dl002(request: M2MetricPluginRequest) -> Mapping[str, object]:
    profile = _mapping(request.input_payload.get("profile"), field="profile")
    min_count = _positive_integer(
        profile,
        "min_message_count",
        field="profile",
    )
    max_gap_us = _positive_integer(profile, "max_gap_us", field="profile")
    latency_hash = _dependency_hash(request, "P1-DL-001")
    rows = _mappings(
        request.input_payload.get("message_latency_series"),
        field="message_latency_series",
    )
    times: list[int] = []
    latencies_us: list[float] = []
    for index, row in enumerate(rows):
        field = f"message_latency_series[{index}]"
        time_us = _integer(row, "session_time_us", field=field)
        latency_us = _finite(row, "message_latency_us", field=field)
        if latency_us < 0.0:
            raise ValueError(f"M3_DL_NEGATIVE_MESSAGE_LATENCY:{field}")
        if times and time_us <= times[-1]:
            raise ValueError("M3_DL_MESSAGE_SERIES_TIME_NOT_STRICTLY_INCREASING")
        if times and time_us - times[-1] > max_gap_us:
            return _missing(
                request,
                "MESSAGE_VALIDITY_PIECE_GAP_EXCEEDED",
                evidence={
                    "p1_dl_001_result_hash": latency_hash,
                    "min_message_count": min_count,
                    "max_gap_us": max_gap_us,
                },
            )
        times.append(time_us)
        latencies_us.append(latency_us)
    if len(latencies_us) < min_count:
        return _missing(
            request,
            "INSUFFICIENT_VALID_MESSAGE_LATENCY_SAMPLES",
            evidence={
                "p1_dl_001_result_hash": latency_hash,
                "sample_count": len(latencies_us),
                "min_message_count": min_count,
                "max_gap_us": max_gap_us,
            },
        )
    center_us = _median(request, latencies_us)
    mad_us = _mad(request, latencies_us)
    p50_us = _quantile(request, latencies_us, 0.50)
    p95_us = _quantile(request, latencies_us, 0.95)
    return _output(
        request,
        value_numeric=mad_us / 1_000_000.0,
        evidence={
            "p1_dl_001_result_hash": latency_hash,
            "sample_count": len(latencies_us),
            "min_message_count": min_count,
            "max_gap_us": max_gap_us,
            "median_latency_s": center_us / 1_000_000.0,
            "p95_minus_p50_latency_s": (p95_us - p50_us) / 1_000_000.0,
        },
    )


def _sequence_domain(
    epoch: Mapping[str, object],
    *,
    field: str,
) -> tuple[int, int, int]:
    domain = _mapping(epoch.get("expected_sequence_domain"), field=f"{field}.domain")
    minimum = _integer(domain, "minimum", field=f"{field}.domain")
    maximum = _integer(domain, "maximum", field=f"{field}.domain")
    modulus = _positive_integer(domain, "modulus", field=f"{field}.domain")
    if minimum != 0 or maximum != modulus - 1 or modulus < 2:
        raise ValueError(f"M3_DL_SEQUENCE_DOMAIN_INVALID:{field}")
    return minimum, maximum, modulus


def _sequence_ranks(
    positions: Sequence[int],
    *,
    modulus: int,
    field: str,
) -> tuple[int, ...]:
    if not positions:
        raise ValueError(f"M3_DL_SEQUENCE_POSITIONS_EMPTY:{field}")
    if any(position < 0 or position >= modulus for position in positions):
        raise ValueError(f"M3_DL_SEQUENCE_POSITION_OUT_OF_DOMAIN:{field}")
    anchor = positions[0]
    return tuple((position - anchor) % modulus for position in positions)


def _dl003(request: M2MetricPluginRequest) -> Mapping[str, object]:
    epochs = _mappings(request.input_payload.get("sequence_epochs"), field="sequence_epochs")
    if not epochs:
        return _missing(request, "SEQUENCE_EPOCH_UNAVAILABLE")
    missing_total = 0
    expected_total = 0
    evidence_epochs: list[dict[str, object]] = []
    for index, epoch in enumerate(epochs):
        field = f"sequence_epochs[{index}]"
        epoch_id = _text(epoch, "sequence_epoch_id", field=field)
        _text(epoch, "link_endpoint_id", field=field)
        _minimum, _maximum, modulus = _sequence_domain(epoch, field=field)
        raw_positions = epoch.get("observed_sequence_positions")
        if not isinstance(raw_positions, Sequence) or isinstance(
            raw_positions,
            (str, bytes),
        ):
            raise ValueError(f"M3_DL_SEQUENCE_POSITIONS_INVALID:{field}")
        if not all(isinstance(item, int) and not isinstance(item, bool) for item in raw_positions):
            raise ValueError(f"M3_DL_SEQUENCE_POSITIONS_INVALID:{field}")
        positions = tuple(cast(Sequence[int], raw_positions))
        ranks = _sequence_ranks(positions, modulus=modulus, field=field)
        unique_ranks = set(ranks)
        expected = max(unique_ranks) + 1
        missing = expected - len(unique_ranks)
        if missing < 0:
            raise ValueError(f"M3_DL_SEQUENCE_COUNT_INVALID:{field}")
        expected_total += expected
        missing_total += missing
        evidence_epochs.append(
            {
                "sequence_epoch_id": epoch_id,
                "modulus": modulus,
                "expected_positions": expected,
                "observed_unique_positions": len(unique_ranks),
                "missing_positions": missing,
            }
        )
    if expected_total <= 0:
        return _missing(request, "SEQUENCE_EXPECTED_DOMAIN_EMPTY")
    return _output(
        request,
        value_numeric=missing_total / expected_total,
        evidence={
            "sequence_epoch_count": len(epochs),
            "missing_expected_positions": missing_total,
            "expected_positions": expected_total,
            "epochs": evidence_epochs,
        },
    )


def _dl004(request: M2MetricPluginRequest) -> Mapping[str, object]:
    epochs = _mappings(request.input_payload.get("sequence_epochs"), field="sequence_epochs")
    if not epochs:
        return _missing(request, "SEQUENCE_EPOCH_UNAVAILABLE")
    received_total = 0
    out_of_order_total = 0
    evidence_epochs: list[dict[str, object]] = []
    for index, epoch in enumerate(epochs):
        field = f"sequence_epochs[{index}]"
        epoch_id = _text(epoch, "sequence_epoch_id", field=field)
        _text(epoch, "link_endpoint_id", field=field)
        _minimum, _maximum, modulus = _sequence_domain(epoch, field=field)
        messages = _mappings(epoch.get("received_messages"), field=f"{field}.messages")
        if not messages:
            continue
        ordered: list[tuple[int, int]] = []
        for message_index, message in enumerate(messages):
            message_field = f"{field}.received_messages[{message_index}]"
            receive_order = _integer(message, "receive_order", field=message_field)
            sequence_position = _integer(
                message,
                "sequence_position",
                field=message_field,
            )
            ordered.append((receive_order, sequence_position))
        ordered.sort()
        if len({item[0] for item in ordered}) != len(ordered):
            raise ValueError(f"M3_DL_RECEIVE_ORDER_DUPLICATE:{field}")
        positions = tuple(item[1] for item in ordered)
        ranks = _sequence_ranks(positions, modulus=modulus, field=field)
        maximum_seen = -1
        out_of_order = 0
        for rank in ranks:
            if rank < maximum_seen:
                out_of_order += 1
            maximum_seen = max(maximum_seen, rank)
        received_total += len(ranks)
        out_of_order_total += out_of_order
        evidence_epochs.append(
            {
                "sequence_epoch_id": epoch_id,
                "received_messages": len(ranks),
                "out_of_order_received_messages": out_of_order,
            }
        )
    if received_total <= 0:
        return _missing(request, "NO_RECEIVED_MESSAGES_IN_SEQUENCE_EPOCH")
    return _output(
        request,
        value_numeric=out_of_order_total / received_total,
        evidence={
            "received_messages": received_total,
            "out_of_order_received_messages": out_of_order_total,
            "epochs": evidence_epochs,
        },
    )


def _dl005(request: M2MetricPluginRequest) -> Mapping[str, object]:
    endpoint = _text(request.input_payload, "link_endpoint_id", field="P1-DL-005")
    valid = request.input_payload.get("remote_track_valid")
    if not isinstance(valid, bool):
        raise ValueError("M3_DL_INPUT_INVALID:P1-DL-005.remote_track_valid")
    if not valid:
        return _missing(
            request,
            "REMOTE_TRACK_NOT_VALID",
            evidence={"link_endpoint_id": endpoint},
        )
    effective = _integer(
        request.input_payload,
        "remote_track_effective_time_us",
        field="P1-DL-005",
    )
    local_use = _integer(
        request.input_payload,
        "local_use_time_us",
        field="P1-DL-005",
    )
    if local_use < effective:
        raise ValueError("M3_DL_REMOTE_TRACK_EFFECTIVE_AFTER_LOCAL_USE")
    return _output(
        request,
        value_numeric=(local_use - effective) / 1_000_000.0,
        evidence={
            "link_endpoint_id": endpoint,
            "remote_track_effective_time_us": effective,
            "local_use_time_us": local_use,
        },
    )


def _quality_vector_rmse(
    request: M2MetricPluginRequest,
    *,
    domain: str,
    remote_field: str,
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
            raise ValueError(f"M3_DL_REFERENCE_MATCH_STATUS_INVALID:{field}")
        actual_domain = _text(sample, "error_domain", field=field)
        if actual_domain != domain:
            raise ValueError(
                f"M3_DL_REFERENCE_ERROR_DOMAIN_INVALID:{field}:{actual_domain}"
            )
        if not accepted:
            rejected += 1
            continue
        if sample.get("remote_track_valid") is not True:
            raise ValueError(f"M3_DL_REMOTE_TRACK_VALIDITY_INVALID:{field}")
        if sample.get("association_resolved") is not True:
            raise ValueError(f"M3_DL_ASSOCIATION_UNRESOLVED:{field}")
        _text(sample, "link_endpoint_id", field=field)
        remote = _vector3(sample.get(remote_field), field=f"{field}.{remote_field}")
        reference = _vector3(
            sample.get(reference_field),
            field=f"{field}.{reference_field}",
        )
        residual_norms.append(
            math.sqrt(
                sum(
                    (remote[axis] - reference[axis]) ** 2
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


def _dl006(request: M2MetricPluginRequest) -> Mapping[str, object]:
    return _quality_vector_rmse(
        request,
        domain="POSITION_3D",
        remote_field="remote_track_position_ecef_m",
        reference_field="reference_target_position_ecef_m",
    )


def _dl007(request: M2MetricPluginRequest) -> Mapping[str, object]:
    return _quality_vector_rmse(
        request,
        domain="VELOCITY_3D",
        remote_field="remote_track_velocity_ecef_mps",
        reference_field="reference_target_velocity_ecef_mps",
    )


def _dl008(request: M2MetricPluginRequest) -> Mapping[str, object]:
    opportunity_profile = _identity(request.input_payload, "opportunity_profile")
    endpoint = _text(request.input_payload, "link_endpoint_id", field="P1-DL-008")
    opportunities = _intervals(
        request.input_payload,
        "remote_track_opportunity_intervals",
    )
    valid = _intervals(request.input_payload, "remote_track_valid_intervals")
    duration = sum(end - start for start, end in _merged(opportunities))
    if duration <= 0:
        return _missing(request, "NO_VALID_REMOTE_TRACK_OPPORTUNITY")
    valid_duration = _intersection_duration(valid, opportunities)
    return _output(
        request,
        value_numeric=valid_duration / duration,
        evidence={
            "opportunity_profile": list(opportunity_profile),
            "link_endpoint_id": endpoint,
            "opportunity_duration_us": duration,
            "valid_remote_track_opportunity_intersection_us": valid_duration,
        },
    )


_HANDLERS: Mapping[
    str,
    Callable[[M2MetricPluginRequest], Mapping[str, object]],
] = MappingProxyType(
    {
        "P1-DL-001": _dl001,
        "P1-DL-002": _dl002,
        "P1-DL-003": _dl003,
        "P1-DL-004": _dl004,
        "P1-DL-005": _dl005,
        "P1-DL-006": _dl006,
        "P1-DL-007": _dl007,
        "P1-DL-008": _dl008,
    }
)


def _plugin(request: M2MetricPluginRequest) -> Mapping[str, object]:
    if not _guard(request):
        return _not_applicable(request)
    handler = _HANDLERS.get(request.definition.metric_code)
    if handler is None:
        raise ValueError(f"M3_DL_PLUGIN_MISSING:{request.definition.metric_code}")
    return handler(request)


M3_DL_PLUGINS: Mapping[str, M2MetricPlugin] = MappingProxyType(
    {code: _plugin for code in M3_DL_CODES}
)


def register_m3_datalink_plugins(
    plan: M2MetricExecutionPlan,
    registry: MetricPluginRegistry,
) -> None:
    """Register the exact eight datalink algorithms in the shared registry."""

    definitions = tuple(
        definition
        for definition in plan.definitions
        if definition.metric_code in M3_DL_CODES
    )
    if (
        len(definitions) != 8
        or {item.metric_code for item in definitions} != set(M3_DL_CODES)
        or {item.family for item in definitions} != {M3_DL_FAMILY}
    ):
        raise CatalogMetricEngineError(
            "M3_DL_DELIVERY_MEMBERSHIP_DRIFT",
            repr(tuple(item.metric_code for item in definitions)),
        )
    for definition in definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"m3-datalink-remainder:{definition.metric_code}:v1",
            plugin=_plugin,
        )
