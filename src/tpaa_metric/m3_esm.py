"""M3-MET-006 Catalog plugins for the exact P1 ESM remainder.

P1-ESM-001..006 execute through the shared CatalogMetricEngine. Applicability
is frozen to mission-system types RWR and ESM; all other system types fail
closed without manufacturing observations.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import cast

from tpaa_metric.catalog_engine import (
    CatalogMetricEngineError,
    M2MetricExecutionPlan,
    M2MetricPlugin,
    M2MetricPluginRequest,
    MetricPluginRegistry,
)

M3_ESM_CODES = tuple(f"P1-ESM-{index:03d}" for index in range(1, 7))
M3_ESM_FAMILY = "RWR_ESM"
M3_ESM_ALLOWED_SYSTEM_TYPES = ("RWR", "ESM")

_EXPECTED_OPERATORS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "P1-ESM-001": (),
        "P1-ESM-002": ("RMS_V1", "WRAP_PI_V1"),
        "P1-ESM-003": (),
        "P1-ESM-004": (),
        "P1-ESM-005": (),
        "P1-ESM-006": (),
    }
)
_EXPECTED_STATE_MACHINES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "P1-ESM-001": (),
        "P1-ESM-002": (),
        "P1-ESM-003": (),
        "P1-ESM-004": ("SM_ASSOCIATION_EPISODE_V1",),
        "P1-ESM-005": ("SM_ASSOCIATION_EPISODE_V1",),
        "P1-ESM-006": (),
    }
)
_EXPECTED_UPSTREAM: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "P1-ESM-001": (
            "CONTRACT_EMITTER_REFERENCE_EVENT_V1",
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "CONTRACT_TIME_TRANSFORM_V1",
            "CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1",
            "CONTRACT_DETECTION_CONFIRMATION_EVENT_V1",
        ),
        "P1-ESM-002": (
            "CONTRACT_EMITTER_REFERENCE_EVENT_V1",
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "CONTRACT_TIME_TRANSFORM_V1",
            "CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1",
        ),
        "P1-ESM-003": (
            "CONTRACT_EMITTER_REFERENCE_EVENT_V1",
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "CONTRACT_TIME_TRANSFORM_V1",
            "CONTRACT_DETECTION_CONFIRMATION_EVENT_V1",
            "CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1",
        ),
        "P1-ESM-004": (
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "CONTRACT_EMITTER_REFERENCE_EVENT_V1",
            "CONTRACT_TIME_TRANSFORM_V1",
        ),
        "P1-ESM-005": (
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "CONTRACT_EMITTER_REFERENCE_EVENT_V1",
            "CONTRACT_TIME_TRANSFORM_V1",
        ),
        "P1-ESM-006": (
            "CONTRACT_EMITTER_REFERENCE_EVENT_V1",
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "CONTRACT_TIME_TRANSFORM_V1",
            "CONTRACT_TRACK_VALIDITY_V1",
            "CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1",
        ),
    }
)


@dataclass(frozen=True)
class _Taxonomy:
    taxonomy_id: str
    version: str
    digest: str
    canonical_labels: frozenset[str]
    alias_map: Mapping[str, str]
    unknown_label: str

    def normalize(self, value: str) -> str:
        if value in self.canonical_labels:
            return value
        return self.alias_map.get(value, self.unknown_label)


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"M3_ESM_INPUT_INVALID:{field}")
    return cast(Mapping[str, object], value)


def _mappings(value: object, *, field: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"M3_ESM_INPUT_INVALID:{field}")
    return tuple(
        _mapping(item, field=f"{field}[{index}]")
        for index, item in enumerate(value)
    )


def _text(mapping: Mapping[str, object], name: str, *, field: str) -> str:
    value = mapping.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"M3_ESM_INPUT_INVALID:{field}.{name}")
    return value


def _integer(mapping: Mapping[str, object], name: str, *, field: str) -> int:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"M3_ESM_INPUT_INVALID:{field}.{name}")
    return value


def _finite(mapping: Mapping[str, object], name: str, *, field: str) -> float:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"M3_ESM_INPUT_INVALID:{field}.{name}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"M3_ESM_INPUT_NONFINITE:{field}.{name}")
    return result


def _sha256(value: str, *, field: str) -> str:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"M3_ESM_INPUT_INVALID:{field}")
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
        definition.metric_code not in M3_ESM_CODES
        or definition.family != M3_ESM_FAMILY
        or definition.subject_type != "MISSION_SYSTEM_INSTANCE"
        or definition.value_kind != "NUMERIC"
        or definition.observation_lane != "SYSTEM_PERFORMANCE_OBSERVATION"
        or definition.publication_route != "SYSTEM_PERFORMANCE_OBSERVATION"
        or applicability.applicability_mode != "SYSTEM_TYPE_SET"
        or applicability.allowed_system_types != M3_ESM_ALLOWED_SYSTEM_TYPES
        or expected_operators is None
        or definition.operator_bindings != expected_operators
        or expected_state_machines is None
        or definition.state_machine_bindings != expected_state_machines
        or expected_upstream is None
        or definition.upstream_dependencies != expected_upstream
    ):
        raise ValueError(f"M3_ESM_CATALOG_DEFINITION_DRIFT:{definition.metric_code}")
    system_type = _text(request.input_payload, "system_type", field=definition.metric_code)
    return system_type in M3_ESM_ALLOWED_SYSTEM_TYPES


def _operator(request: M2MetricPluginRequest, operator_id: str) -> Callable[..., object]:
    value = request.operators.get(operator_id)
    if value is None:
        raise ValueError(f"M3_ESM_OPERATOR_MISSING:{operator_id}")
    return value


def _operator_number(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"M3_ESM_OPERATOR_OUTPUT_INVALID:{field}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"M3_ESM_OPERATOR_OUTPUT_NONFINITE:{field}")
    return result


def _rms(request: M2MetricPluginRequest, values: Sequence[float]) -> float:
    return _operator_number(_operator(request, "RMS_V1")(values), field="RMS_V1")


def _wrap_pi(request: M2MetricPluginRequest, value: float) -> float:
    return _operator_number(_operator(request, "WRAP_PI_V1")(value), field="WRAP_PI_V1")


def _instance(
    *,
    status: str,
    reason_codes: Sequence[str] = (),
    value_numeric: float | None = None,
    evidence: Mapping[str, object] | None = None,
) -> dict[str, object]:
    if status == "VALID":
        if value_numeric is None or not math.isfinite(value_numeric):
            raise ValueError("M3_ESM_VALID_VALUE_INVALID")
    elif value_numeric is not None:
        raise ValueError("M3_ESM_NONVALID_VALUE_FORBIDDEN")
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
            raise ValueError(f"M3_ESM_INTERVAL_INVALID:{field}")
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


def _esm001(request: M2MetricPluginRequest) -> Mapping[str, object]:
    opportunity_profile = _identity(request.input_payload, "opportunity_profile")
    confirmation_profile = _identity(request.input_payload, "confirmation_profile")
    opportunities = _mappings(
        request.input_payload.get("emitter_opportunity_intervals"),
        field="emitter_opportunity_intervals",
    )
    confirmations = _mappings(
        request.input_payload.get("confirmation_events"),
        field="confirmation_events",
    )
    if not opportunities:
        return _missing(request, "NO_VALID_EMITTER_OPPORTUNITY")

    reference_by_opportunity: dict[str, str] = {}
    for index, item in enumerate(opportunities):
        field = f"emitter_opportunity_intervals[{index}]"
        opportunity_id = _text(item, "detection_opportunity_id", field=field)
        if opportunity_id in reference_by_opportunity:
            raise ValueError(f"M3_ESM_OPPORTUNITY_DUPLICATE:{opportunity_id}")
        start = _integer(item, "start_session_time_us", field=field)
        end = _integer(item, "end_session_time_us", field=field)
        if end <= start:
            raise ValueError(f"M3_ESM_INTERVAL_INVALID:{field}")
        reference_by_opportunity[opportunity_id] = _text(
            item,
            "reference_emitter_id",
            field=field,
        )

    detected: set[str] = set()
    event_ids: list[str] = []
    for index, event in enumerate(confirmations):
        field = f"confirmation_events[{index}]"
        event_id = _text(event, "detection_confirmation_event_id", field=field)
        opportunity_id = _text(event, "detection_opportunity_id", field=field)
        if opportunity_id not in reference_by_opportunity:
            raise ValueError(f"M3_ESM_CONFIRMATION_OPPORTUNITY_UNRESOLVED:{event_id}")
        reference_emitter_id = _text(event, "reference_emitter_id", field=field)
        if reference_emitter_id != reference_by_opportunity[opportunity_id]:
            raise ValueError(f"M3_ESM_CONFIRMATION_ASSOCIATION_MISMATCH:{event_id}")
        detected.add(opportunity_id)
        event_ids.append(event_id)

    return _output(
        request,
        value_numeric=len(detected) / len(opportunities),
        evidence={
            "opportunity_profile": list(opportunity_profile),
            "confirmation_profile": list(confirmation_profile),
            "opportunity_ids": sorted(reference_by_opportunity),
            "confirmation_event_ids": sorted(event_ids),
        },
    )


def _esm002(request: M2MetricPluginRequest) -> Mapping[str, object]:
    profile = _identity(request.input_payload, "reference_match_quality_profile")
    residuals: list[float] = []
    rejected = 0
    for index, sample in enumerate(
        _mappings(request.input_payload.get("samples"), field="samples")
    ):
        field = f"samples[{index}]"
        accepted = sample.get("reference_match_accepted")
        if not isinstance(accepted, bool):
            raise ValueError(f"M3_ESM_REFERENCE_MATCH_STATUS_INVALID:{field}")
        if _text(sample, "error_domain", field=field) != "BEARING":
            raise ValueError(f"M3_ESM_REFERENCE_ERROR_DOMAIN_INVALID:{field}")
        if not accepted:
            rejected += 1
            continue
        reported = _finite(sample, "reported_bearing_rad", field=field)
        reference = _finite(sample, "reference_bearing_rad", field=field)
        residuals.append(_wrap_pi(request, reported - reference))

    if not residuals:
        return _missing(
            request,
            "REFERENCE_MATCH_QUALITY_REJECTED_ALL",
            evidence={
                "reference_match_quality_profile": list(profile),
                "rejected_count": rejected,
            },
        )
    return _output(
        request,
        value_numeric=_rms(request, residuals),
        evidence={
            "reference_match_quality_profile": list(profile),
            "eligible_count": len(residuals),
            "rejected_count": rejected,
            "wrapped_residuals_rad": residuals,
        },
    )


def _esm003(request: M2MetricPluginRequest) -> Mapping[str, object]:
    opportunity_profile = _identity(request.input_payload, "opportunity_profile")
    confirmation_profile = _identity(request.input_payload, "confirmation_profile")
    opportunity_id = _text(
        request.input_payload,
        "detection_opportunity_id",
        field="P1-ESM-003",
    )
    confirmation_event_id = _text(
        request.input_payload,
        "detection_confirmation_event_id",
        field="P1-ESM-003",
    )
    start = _integer(
        request.input_payload,
        "opportunity_start_time_us",
        field="P1-ESM-003",
    )
    first = _integer(
        request.input_payload,
        "first_confirmed_detection_time_us",
        field="P1-ESM-003",
    )
    if first < start:
        raise ValueError("M3_ESM_CONFIRMATION_PRECEDES_OPPORTUNITY")
    return _output(
        request,
        value_numeric=(first - start) / 1_000_000.0,
        evidence={
            "detection_opportunity_id": opportunity_id,
            "detection_confirmation_event_id": confirmation_event_id,
            "opportunity_profile": list(opportunity_profile),
            "confirmation_profile": list(confirmation_profile),
        },
    )


def _esm004(request: M2MetricPluginRequest) -> Mapping[str, object]:
    intervals = _mappings(
        request.input_payload.get("association_intervals"),
        field="association_intervals",
    )
    correct_us = 0
    associated_us = 0
    for index, interval in enumerate(intervals):
        field = f"association_intervals[{index}]"
        start = _integer(interval, "start_session_time_us", field=field)
        end = _integer(interval, "end_session_time_us", field=field)
        if end <= start:
            raise ValueError(f"M3_ESM_INTERVAL_INVALID:{field}")
        _text(interval, "esm_emitter_track_id", field=field)
        _text(interval, "reference_emitter_id", field=field)
        state = _text(interval, "association_state", field=field)
        if state not in {"CORRECT", "WRONG"}:
            raise ValueError(f"M3_ESM_ASSOCIATION_STATE_INVALID:{state}")
        dwell = end - start
        associated_us += dwell
        if state == "CORRECT":
            correct_us += dwell
    if associated_us <= 0:
        return _missing(request, "NO_ELIGIBLE_ASSOCIATED_DWELL")
    return _output(
        request,
        value_numeric=correct_us / associated_us,
        evidence={
            "correct_association_duration_us": correct_us,
            "associated_duration_us": associated_us,
        },
    )


def _taxonomy(payload: Mapping[str, object]) -> _Taxonomy:
    raw = _mapping(payload.get("taxonomy"), field="taxonomy")
    taxonomy_id = _text(raw, "taxonomy_id", field="taxonomy")
    version = _text(raw, "taxonomy_version", field="taxonomy")
    digest = _sha256(
        _text(raw, "taxonomy_hash", field="taxonomy"),
        field="taxonomy_hash",
    )
    canonical_raw = raw.get("canonical_labels")
    if not isinstance(canonical_raw, Sequence) or isinstance(
        canonical_raw,
        (str, bytes),
    ):
        raise ValueError("M3_ESM_TAXONOMY_CANONICAL_LABELS_INVALID")
    if not all(isinstance(item, str) and item for item in canonical_raw):
        raise ValueError("M3_ESM_TAXONOMY_CANONICAL_LABELS_INVALID")
    labels = tuple(cast(Sequence[str], canonical_raw))
    if len(labels) != len(set(labels)):
        raise ValueError("M3_ESM_TAXONOMY_CANONICAL_LABELS_DUPLICATE")
    unknown = _text(raw, "unknown_label", field="taxonomy")
    if unknown not in labels:
        raise ValueError("M3_ESM_TAXONOMY_UNKNOWN_NOT_CANONICAL")
    alias_raw = _mapping(raw.get("alias_map"), field="taxonomy.alias_map")
    aliases: dict[str, str] = {}
    for alias, target in alias_raw.items():
        if not isinstance(target, str) or target not in labels:
            raise ValueError(f"M3_ESM_TAXONOMY_ALIAS_INVALID:{alias}")
        aliases[alias] = target

    top_identity = (
        _text(
            payload,
            "reference_classification_taxonomy_id",
            field="reference_classification_taxonomy_id",
        ),
        _text(
            payload,
            "reference_classification_taxonomy_version",
            field="reference_classification_taxonomy_version",
        ),
        _sha256(
            _text(
                payload,
                "reference_classification_taxonomy_hash",
                field="reference_classification_taxonomy_hash",
            ),
            field="reference_classification_taxonomy_hash",
        ),
    )
    if (taxonomy_id, version, digest) != top_identity:
        raise ValueError("M3_ESM_TAXONOMY_IDENTITY_MISMATCH")
    return _Taxonomy(
        taxonomy_id=taxonomy_id,
        version=version,
        digest=digest,
        canonical_labels=frozenset(labels),
        alias_map=MappingProxyType(aliases),
        unknown_label=unknown,
    )


def _esm005(request: M2MetricPluginRequest) -> Mapping[str, object]:
    taxonomy = _taxonomy(request.input_payload)
    classified: list[tuple[int, str, str]] = []
    rejected = 0
    for index, interval in enumerate(
        _mappings(
            request.input_payload.get("classification_intervals"),
            field="classification_intervals",
        )
    ):
        field = f"classification_intervals[{index}]"
        start = _integer(interval, "start_session_time_us", field=field)
        end = _integer(interval, "end_session_time_us", field=field)
        if end <= start:
            raise ValueError(f"M3_ESM_INTERVAL_INVALID:{field}")
        association_resolved = interval.get("association_resolved")
        if not isinstance(association_resolved, bool):
            raise ValueError(f"M3_ESM_INPUT_INVALID:{field}.association_resolved")
        quality = _text(interval, "reference_quality_status", field=field)
        if not association_resolved or quality != "VALID":
            rejected += 1
            continue
        reported = taxonomy.normalize(
            _text(interval, "reported_emitter_class", field=field)
        )
        reference = taxonomy.normalize(
            _text(interval, "reference_emitter_class", field=field)
        )
        if (
            reported == taxonomy.unknown_label
            or reference == taxonomy.unknown_label
        ):
            continue
        classified.append((end - start, reported, reference))

    denominator_us = sum(item[0] for item in classified)
    if denominator_us <= 0:
        return _missing(
            request,
            "NO_CLASSIFIED_ELIGIBLE_DWELL",
            evidence={
                "taxonomy_identity": [
                    taxonomy.taxonomy_id,
                    taxonomy.version,
                    taxonomy.digest,
                ],
                "rejected_interval_count": rejected,
            },
        )
    correct_us = sum(
        dwell
        for dwell, reported, reference in classified
        if reported == reference
    )
    labels = tuple(sorted(taxonomy.canonical_labels))
    confusion: dict[str, dict[str, int]] = {
        reference: {reported: 0 for reported in labels}
        for reference in labels
    }
    for dwell, reported, reference in classified:
        confusion[reference][reported] += dwell

    return _output(
        request,
        value_numeric=correct_us / denominator_us,
        evidence={
            "taxonomy_identity": [
                taxonomy.taxonomy_id,
                taxonomy.version,
                taxonomy.digest,
            ],
            "classified_eligible_dwell_us": denominator_us,
            "correct_canonical_label_dwell_us": correct_us,
            "rejected_interval_count": rejected,
            "canonical_confusion_matrix_dwell_us": confusion,
        },
    )


def _esm006(request: M2MetricPluginRequest) -> Mapping[str, object]:
    opportunity_profile = _identity(request.input_payload, "opportunity_profile")
    opportunities = _intervals(
        request.input_payload,
        "emitter_opportunity_intervals",
    )
    valid_tracks = _intervals(
        request.input_payload,
        "esm_track_valid_intervals",
    )
    opportunity_us = sum(end - start for start, end in _merged(opportunities))
    if opportunity_us <= 0:
        return _missing(request, "NO_VALID_EMITTER_OPPORTUNITY")
    valid_us = _intersection_duration(valid_tracks, opportunities)
    return _output(
        request,
        value_numeric=valid_us / opportunity_us,
        evidence={
            "opportunity_profile": list(opportunity_profile),
            "opportunity_duration_us": opportunity_us,
            "valid_esm_track_opportunity_intersection_us": valid_us,
        },
    )


_HANDLERS: Mapping[
    str,
    Callable[[M2MetricPluginRequest], Mapping[str, object]],
] = MappingProxyType(
    {
        "P1-ESM-001": _esm001,
        "P1-ESM-002": _esm002,
        "P1-ESM-003": _esm003,
        "P1-ESM-004": _esm004,
        "P1-ESM-005": _esm005,
        "P1-ESM-006": _esm006,
    }
)


def _plugin(request: M2MetricPluginRequest) -> Mapping[str, object]:
    if not _guard(request):
        return _not_applicable(request)
    handler = _HANDLERS.get(request.definition.metric_code)
    if handler is None:
        raise ValueError(f"M3_ESM_PLUGIN_MISSING:{request.definition.metric_code}")
    return handler(request)


M3_ESM_PLUGINS: Mapping[str, M2MetricPlugin] = MappingProxyType(
    {code: _plugin for code in M3_ESM_CODES}
)


def register_m3_esm_plugins(
    plan: M2MetricExecutionPlan,
    registry: MetricPluginRegistry,
) -> None:
    """Register the exact six ESM algorithms in the shared Catalog registry."""

    definitions = tuple(
        definition
        for definition in plan.definitions
        if definition.metric_code in M3_ESM_CODES
    )
    if (
        len(definitions) != 6
        or {item.metric_code for item in definitions} != set(M3_ESM_CODES)
        or {item.family for item in definitions} != {M3_ESM_FAMILY}
    ):
        raise CatalogMetricEngineError(
            "M3_ESM_DELIVERY_MEMBERSHIP_DRIFT",
            repr(tuple(item.metric_code for item in definitions)),
        )
    for definition in definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"m3-esm-remainder:{definition.metric_code}:v1",
            plugin=_plugin,
        )
