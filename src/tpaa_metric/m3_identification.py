"""M3-MET-004 Catalog plugins for the exact P1 ID remainder.

P1-ID-001..012 execute through the shared CatalogMetricEngine and are
applicable only when the evaluated mission-system product advertises the frozen
ASSOCIATION_IDENTIFICATION_PRODUCT semantic capability.
"""

from __future__ import annotations

import math
from collections import defaultdict
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

M3_ID_CODES = tuple(f"P1-ID-{index:03d}" for index in range(1, 13))
M3_ID_FAMILY = "ASSOCIATION_IDENTIFICATION"
M3_ID_REQUIRED_PRODUCT_SEMANTICS = "ASSOCIATION_IDENTIFICATION_PRODUCT"

_EXPECTED_STATE_MACHINES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "P1-ID-001": ("SM_ASSOCIATION_EPISODE_V1",),
        "P1-ID-002": ("SM_ASSOCIATION_EPISODE_V1",),
        "P1-ID-003": ("SM_ASSOCIATION_EPISODE_V1",),
        "P1-ID-004": ("SM_ASSOCIATION_EPISODE_V1",),
        "P1-ID-005": ("SM_ASSOCIATION_EPISODE_V1",),
        "P1-ID-006": ("SM_ASSOCIATION_EPISODE_V1",),
        "P1-ID-007": ("SM_ASSOCIATION_EPISODE_V1",),
        "P1-ID-008": ("SM_ASSOCIATION_EPISODE_V1",),
        "P1-ID-009": ("SM_ASSOCIATION_EPISODE_V1",),
        "P1-ID-010": ("SM_ASSOCIATION_EPISODE_V1",),
        "P1-ID-011": ("SM_TRACK_STABLE_V1", "SM_IDENTIFICATION_STABLE_V1"),
        "P1-ID-012": ("SM_IDENTIFICATION_STABLE_V1",),
    }
)
_EXPECTED_UPSTREAM: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "P1-ID-001": ("CONTRACT_ASSOCIATION_RELATION_V1",),
        "P1-ID-002": ("CONTRACT_ASSOCIATION_RELATION_V1",),
        "P1-ID-003": ("CONTRACT_ASSOCIATION_RELATION_V1",),
        "P1-ID-004": ("CONTRACT_ASSOCIATION_RELATION_V1",),
        "P1-ID-005": ("CONTRACT_ASSOCIATION_RELATION_V1",),
        "P1-ID-006": ("CONTRACT_ASSOCIATION_RELATION_V1",),
        "P1-ID-007": ("CONTRACT_ASSOCIATION_RELATION_V1",),
        "P1-ID-008": (
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "CONTRACT_REFERENCE_IDENTITY_CLASSIFICATION_V1",
        ),
        "P1-ID-009": (
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "CONTRACT_REFERENCE_IDENTITY_CLASSIFICATION_V1",
        ),
        "P1-ID-010": ("CONTRACT_ASSOCIATION_RELATION_V1",),
        "P1-ID-011": (
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "CONTRACT_TRACK_VALIDITY_V1",
            "CONTRACT_REFERENCE_IDENTITY_CLASSIFICATION_V1",
        ),
        "P1-ID-012": (
            "CONTRACT_ASSOCIATION_RELATION_V1",
            "CONTRACT_TRACK_VALIDITY_V1",
            "CONTRACT_REFERENCE_IDENTITY_CLASSIFICATION_V1",
        ),
    }
)


@dataclass(frozen=True)
class _RelationInterval:
    start_us: int
    end_us: int
    track_id: str
    reference_target_id: str
    association_state: str


@dataclass(frozen=True)
class _RelationSegment:
    start_us: int
    end_us: int
    pairs: frozenset[tuple[str, str]]


@dataclass(frozen=True)
class _ClassificationInterval:
    start_us: int
    end_us: int
    track_id: str
    reference_target_id: str
    reported: str
    reference: str
    association_resolved: bool
    reference_quality_status: str


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
        raise ValueError(f"M3_ID_INPUT_INVALID:{field}")
    return cast(Mapping[str, object], value)


def _mappings(value: object, *, field: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"M3_ID_INPUT_INVALID:{field}")
    return tuple(
        _mapping(item, field=f"{field}[{index}]")
        for index, item in enumerate(value)
    )


def _text(mapping: Mapping[str, object], name: str, *, field: str) -> str:
    value = mapping.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"M3_ID_INPUT_INVALID:{field}.{name}")
    return value


def _integer(mapping: Mapping[str, object], name: str, *, field: str) -> int:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"M3_ID_INPUT_INVALID:{field}.{name}")
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
        raise ValueError(f"M3_ID_INPUT_INVALID:{field}.{name}")
    return value


def _finite(mapping: Mapping[str, object], name: str, *, field: str) -> float:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"M3_ID_INPUT_INVALID:{field}.{name}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"M3_ID_INPUT_NONFINITE:{field}.{name}")
    return result


def _profile(payload: Mapping[str, object]) -> Mapping[str, object]:
    return _mapping(payload.get("profile"), field="profile")


def _profile_float(payload: Mapping[str, object], name: str) -> float:
    return _finite(_profile(payload), name, field="profile")


def _sha256(value: str, *, field: str) -> str:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"M3_ID_INPUT_INVALID:{field}")
    return value


def _products(payload: Mapping[str, object]) -> tuple[str, ...]:
    raw = payload.get("product_semantics")
    if not isinstance(raw, (list, tuple)) or not all(
        isinstance(item, str) and item for item in raw
    ):
        raise ValueError("M3_ID_PRODUCT_SEMANTICS_INVALID")
    values = tuple(cast(Sequence[str], raw))
    if len(values) != len(set(values)):
        raise ValueError("M3_ID_PRODUCT_SEMANTICS_DUPLICATE")
    return values


def _guard(request: M2MetricPluginRequest) -> bool:
    definition = request.definition
    applicability = definition.applicability
    expected_state_machines = _EXPECTED_STATE_MACHINES.get(definition.metric_code)
    expected_upstream = _EXPECTED_UPSTREAM.get(definition.metric_code)
    if (
        definition.metric_code not in M3_ID_CODES
        or definition.family != M3_ID_FAMILY
        or definition.subject_type != "MISSION_SYSTEM_INSTANCE"
        or definition.value_kind != "NUMERIC"
        or definition.observation_lane != "SYSTEM_PERFORMANCE_OBSERVATION"
        or definition.publication_route != "SYSTEM_PERFORMANCE_OBSERVATION"
        or applicability.applicability_mode != "PRODUCT_CAPABILITY"
        or applicability.required_product_semantics
        != M3_ID_REQUIRED_PRODUCT_SEMANTICS
        or expected_state_machines is None
        or definition.state_machine_bindings != expected_state_machines
        or expected_upstream is None
        or definition.upstream_dependencies != expected_upstream
        or definition.operator_bindings
    ):
        raise ValueError(f"M3_ID_CATALOG_DEFINITION_DRIFT:{definition.metric_code}")
    return M3_ID_REQUIRED_PRODUCT_SEMANTICS in _products(request.input_payload)


def _instance(
    *,
    status: str,
    reason_codes: Sequence[str] = (),
    value_numeric: float | None = None,
    evidence: Mapping[str, object] | None = None,
) -> dict[str, object]:
    if status == "VALID":
        if value_numeric is None or not math.isfinite(value_numeric):
            raise ValueError("M3_ID_VALID_VALUE_INVALID")
    elif value_numeric is not None:
        raise ValueError("M3_ID_NONVALID_VALUE_FORBIDDEN")
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


def _relation_intervals(
    payload: Mapping[str, object],
    name: str = "association_intervals",
) -> tuple[_RelationInterval, ...]:
    rows = _mappings(payload.get(name), field=name)
    result: list[_RelationInterval] = []
    for index, row in enumerate(rows):
        field = f"{name}[{index}]"
        start = _integer(row, "start_session_time_us", field=field)
        end = _integer(row, "end_session_time_us", field=field)
        if end <= start:
            raise ValueError(f"M3_ID_INTERVAL_INVALID:{field}")
        state_raw = row.get("association_state", "RESOLVED")
        if not isinstance(state_raw, str) or not state_raw:
            raise ValueError(f"M3_ID_INPUT_INVALID:{field}.association_state")
        result.append(
            _RelationInterval(
                start_us=start,
                end_us=end,
                track_id=_text(row, "track_id", field=field),
                reference_target_id=_text(row, "reference_target_id", field=field),
                association_state=state_raw,
            )
        )
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


def _relation_segments(
    intervals: Sequence[_RelationInterval],
) -> tuple[_RelationSegment, ...]:
    boundaries = sorted(
        {
            boundary
            for item in intervals
            for boundary in (item.start_us, item.end_us)
        }
    )
    segments: list[_RelationSegment] = []
    for start, end in zip(boundaries, boundaries[1:], strict=False):
        if end <= start:
            continue
        pairs = frozenset(
            (item.track_id, item.reference_target_id)
            for item in intervals
            if item.start_us <= start and item.end_us >= end
        )
        if not pairs:
            continue
        segment = _RelationSegment(start, end, pairs)
        if segments and segments[-1].end_us == start and segments[-1].pairs == pairs:
            previous = segments[-1]
            segments[-1] = _RelationSegment(
                previous.start_us,
                end,
                previous.pairs,
            )
        else:
            segments.append(segment)
    return tuple(segments)


def _qualified_multiplicity_episodes(
    intervals: Sequence[_RelationInterval],
    *,
    threshold_us: int,
    by_reference: bool,
) -> tuple[tuple[str, int, int], ...]:
    segments = _relation_segments(intervals)
    open_start: dict[str, int] = {}
    episodes: list[tuple[str, int, int]] = []

    for segment in segments:
        groups: dict[str, set[str]] = defaultdict(set)
        for track_id, reference_target_id in segment.pairs:
            if by_reference:
                groups[reference_target_id].add(track_id)
            else:
                groups[track_id].add(reference_target_id)
        active = {key for key, values in groups.items() if len(values) > 1}

        for key in tuple(open_start):
            if key not in active:
                start = open_start.pop(key)
                if segment.start_us - start >= threshold_us:
                    episodes.append((key, start, segment.start_us))
        for key in active:
            open_start.setdefault(key, segment.start_us)

    final_end = segments[-1].end_us if segments else 0
    for key, start in open_start.items():
        if final_end - start >= threshold_us:
            episodes.append((key, start, final_end))
    return tuple(sorted(episodes))


def _target_associated_dwell_us(
    intervals: Sequence[_RelationInterval],
) -> int:
    by_target: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for item in intervals:
        by_target[item.reference_target_id].append((item.start_us, item.end_us))
    return sum(
        end - start
        for target_intervals in by_target.values()
        for start, end in _merged_intervals(target_intervals)
    )


def _id001(request: M2MetricPluginRequest) -> Mapping[str, object]:
    intervals = _relation_intervals(request.input_payload)
    if not intervals:
        return _missing(request, "ASSOCIATION_RELATION_UNAVAILABLE")
    invalid_states = sorted(
        {
            item.association_state
            for item in intervals
            if item.association_state not in {"CORRECT", "WRONG"}
        }
    )
    if invalid_states:
        raise ValueError(f"M3_ID_ASSOCIATION_STATE_INVALID:{invalid_states!r}")
    total_us = sum(item.end_us - item.start_us for item in intervals)
    if total_us <= 0:
        return _missing(request, "NO_ELIGIBLE_ASSOCIATED_DWELL")
    correct_us = sum(
        item.end_us - item.start_us
        for item in intervals
        if item.association_state == "CORRECT"
    )
    return _output(
        request,
        value_numeric=correct_us / total_us,
        evidence={
            "correct_association_duration_us": correct_us,
            "associated_duration_us": total_us,
        },
    )


def _id002(request: M2MetricPluginRequest) -> Mapping[str, object]:
    intervals = _relation_intervals(request.input_payload)
    if not intervals:
        return _missing(request, "ASSOCIATION_RELATION_UNAVAILABLE")
    wrong_by_relation: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)
    for item in intervals:
        if item.association_state not in {"CORRECT", "WRONG"}:
            raise ValueError(
                f"M3_ID_ASSOCIATION_STATE_INVALID:{item.association_state}"
            )
        if item.association_state == "WRONG":
            wrong_by_relation[(item.track_id, item.reference_target_id)].append(
                (item.start_us, item.end_us)
            )
    episodes = tuple(
        (track_id, reference_target_id, start, end)
        for (track_id, reference_target_id), relation_intervals in wrong_by_relation.items()
        for start, end in _merged_intervals(relation_intervals)
    )
    return _output(
        request,
        value_numeric=float(len(episodes)),
        evidence={"wrong_association_episodes": [list(item) for item in sorted(episodes)]},
    )


def _assignment_map(segment: _RelationSegment) -> Mapping[str, str]:
    mapping: dict[str, str] = {}
    for track_id, reference_target_id in segment.pairs:
        previous = mapping.get(track_id)
        if previous is not None and previous != reference_target_id:
            raise ValueError(f"M3_ID_ASSIGNMENT_NONFUNCTIONAL:{track_id}")
        mapping[track_id] = reference_target_id
    return MappingProxyType(mapping)


def _id003(request: M2MetricPluginRequest) -> Mapping[str, object]:
    intervals = _relation_intervals(request.input_payload)
    persistence_s = _profile_float(request.input_payload, "swap_persistence_s")
    if persistence_s <= 0.0:
        raise ValueError("M3_ID_SWAP_PERSISTENCE_INVALID")
    threshold_us = int(persistence_s * 1_000_000.0)
    segments = _relation_segments(intervals)
    swaps: list[tuple[int, int, str, str, str, str]] = []
    for previous, current in zip(segments, segments[1:], strict=False):
        if previous.end_us != current.start_us:
            continue
        previous_map = _assignment_map(previous)
        current_map = _assignment_map(current)
        changed = sorted(
            track_id
            for track_id in set(previous_map) & set(current_map)
            if previous_map[track_id] != current_map[track_id]
        )
        if len(changed) != 2 or current.end_us - current.start_us < threshold_us:
            continue
        left, right = changed
        if (
            previous_map[left] != previous_map[right]
            and previous_map[left] == current_map[right]
            and previous_map[right] == current_map[left]
        ):
            swaps.append(
                (
                    current.start_us,
                    current.end_us,
                    left,
                    right,
                    current_map[left],
                    current_map[right],
                )
            )
    return _output(
        request,
        value_numeric=float(len(swaps)),
        evidence={
            "swap_persistence_s": persistence_s,
            "qualified_swaps": [list(item) for item in swaps],
        },
    )


def _id004(request: M2MetricPluginRequest) -> Mapping[str, object]:
    intervals = _relation_intervals(request.input_payload)
    persistence_s = _profile_float(request.input_payload, "split_persistence_s")
    if persistence_s <= 0.0:
        raise ValueError("M3_ID_SPLIT_PERSISTENCE_INVALID")
    episodes = _qualified_multiplicity_episodes(
        intervals,
        threshold_us=int(persistence_s * 1_000_000.0),
        by_reference=True,
    )
    return _output(
        request,
        value_numeric=float(len(episodes)),
        evidence={
            "split_persistence_s": persistence_s,
            "qualified_split_episodes": [list(item) for item in episodes],
        },
    )


def _id005(request: M2MetricPluginRequest) -> Mapping[str, object]:
    intervals = _relation_intervals(request.input_payload)
    persistence_s = _profile_float(request.input_payload, "merge_persistence_s")
    if persistence_s <= 0.0:
        raise ValueError("M3_ID_MERGE_PERSISTENCE_INVALID")
    episodes = _qualified_multiplicity_episodes(
        intervals,
        threshold_us=int(persistence_s * 1_000_000.0),
        by_reference=False,
    )
    return _output(
        request,
        value_numeric=float(len(episodes)),
        evidence={
            "merge_persistence_s": persistence_s,
            "qualified_merge_episodes": [list(item) for item in episodes],
        },
    )


def _id006(request: M2MetricPluginRequest) -> Mapping[str, object]:
    intervals = _relation_intervals(request.input_payload)
    persistence_s = _profile_float(request.input_payload, "duplicate_persistence_s")
    if persistence_s <= 0.0:
        raise ValueError("M3_ID_DUPLICATE_PERSISTENCE_INVALID")
    denominator_us = _target_associated_dwell_us(intervals)
    if denominator_us <= 0:
        return _missing(request, "NO_ELIGIBLE_ASSOCIATED_DWELL")
    episodes = _qualified_multiplicity_episodes(
        intervals,
        threshold_us=int(persistence_s * 1_000_000.0),
        by_reference=True,
    )
    numerator_us = sum(end - start for _target, start, end in episodes)
    return _output(
        request,
        value_numeric=numerator_us / denominator_us,
        evidence={
            "duplicate_persistence_s": persistence_s,
            "duplicate_episode_duration_us": numerator_us,
            "eligible_associated_target_duration_us": denominator_us,
            "qualified_duplicate_episodes": [list(item) for item in episodes],
        },
    )


def _merge_relation_identity(
    intervals: Sequence[tuple[int, int]],
    *,
    max_gap_us: int,
) -> tuple[tuple[int, int, int], ...]:
    if not intervals:
        return ()
    ordered = sorted(intervals)
    start, end = ordered[0]
    dwell = end - start
    result: list[tuple[int, int, int]] = []
    for next_start, next_end in ordered[1:]:
        if next_start - end <= max_gap_us:
            dwell += next_end - next_start
            end = max(end, next_end)
        else:
            result.append((start, end, dwell))
            start, end = next_start, next_end
            dwell = next_end - next_start
    result.append((start, end, dwell))
    return tuple(result)


def _id007(request: M2MetricPluginRequest) -> Mapping[str, object]:
    intervals = _relation_intervals(request.input_payload)
    persistence_s = _profile_float(request.input_payload, "identity_persistence_s")
    max_gap = _finite(_profile(request.input_payload), "max_gap_us", field="profile")
    if persistence_s <= 0.0 or max_gap < 0.0:
        raise ValueError("M3_ID_IDENTITY_CONTINUITY_PROFILE_INVALID")
    denominator_us = _target_associated_dwell_us(intervals)
    if denominator_us <= 0:
        return _missing(request, "NO_ELIGIBLE_ASSOCIATED_DWELL")
    by_relation: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)
    for item in intervals:
        by_relation[(item.track_id, item.reference_target_id)].append(
            (item.start_us, item.end_us)
        )
    threshold_us = int(persistence_s * 1_000_000.0)
    eligible: list[tuple[str, str, int, int, int]] = []
    for (track_id, reference_target_id), relation_intervals in by_relation.items():
        for start, end, dwell in _merge_relation_identity(
            relation_intervals,
            max_gap_us=int(max_gap),
        ):
            if end - start >= threshold_us:
                eligible.append(
                    (track_id, reference_target_id, start, end, dwell)
                )
    if not eligible:
        return _missing(
            request,
            "NO_ELIGIBLE_IDENTITY_SEGMENT",
            evidence={"eligible_associated_target_duration_us": denominator_us},
        )
    longest_us = max(item[4] for item in eligible)
    return _output(
        request,
        value_numeric=longest_us / denominator_us,
        evidence={
            "identity_persistence_s": persistence_s,
            "max_gap_us": int(max_gap),
            "longest_identity_dwell_us": longest_us,
            "eligible_associated_target_duration_us": denominator_us,
            "eligible_identity_segments": [list(item) for item in sorted(eligible)],
        },
    )


def _taxonomy(payload: Mapping[str, object]) -> _Taxonomy:
    raw = _mapping(payload.get("taxonomy"), field="taxonomy")
    taxonomy_id = _text(raw, "taxonomy_id", field="taxonomy")
    version = _text(raw, "taxonomy_version", field="taxonomy")
    digest = _sha256(_text(raw, "taxonomy_hash", field="taxonomy"), field="taxonomy_hash")
    canonical_raw = raw.get("canonical_labels")
    if not isinstance(canonical_raw, Sequence) or isinstance(
        canonical_raw,
        (str, bytes),
    ):
        raise ValueError("M3_ID_TAXONOMY_CANONICAL_LABELS_INVALID")
    if not all(isinstance(item, str) and item for item in canonical_raw):
        raise ValueError("M3_ID_TAXONOMY_CANONICAL_LABELS_INVALID")
    labels = tuple(cast(Sequence[str], canonical_raw))
    if len(labels) != len(set(labels)):
        raise ValueError("M3_ID_TAXONOMY_CANONICAL_LABELS_DUPLICATE")
    unknown = _text(raw, "unknown_label", field="taxonomy")
    if unknown not in labels:
        raise ValueError("M3_ID_TAXONOMY_UNKNOWN_NOT_CANONICAL")
    alias_raw = _mapping(raw.get("alias_map"), field="taxonomy.alias_map")
    aliases: dict[str, str] = {}
    for alias, target in alias_raw.items():
        if not isinstance(target, str) or target not in labels:
            raise ValueError(f"M3_ID_TAXONOMY_ALIAS_INVALID:{alias}")
        aliases[alias] = target

    top_id = _text(
        payload,
        "reference_classification_taxonomy_id",
        field="reference_classification_taxonomy_id",
    )
    top_version = _text(
        payload,
        "reference_classification_taxonomy_version",
        field="reference_classification_taxonomy_version",
    )
    top_digest = _sha256(
        _text(
            payload,
            "reference_classification_taxonomy_hash",
            field="reference_classification_taxonomy_hash",
        ),
        field="reference_classification_taxonomy_hash",
    )
    if (taxonomy_id, version, digest) != (top_id, top_version, top_digest):
        raise ValueError("M3_ID_TAXONOMY_IDENTITY_MISMATCH")
    return _Taxonomy(
        taxonomy_id=taxonomy_id,
        version=version,
        digest=digest,
        canonical_labels=frozenset(labels),
        alias_map=MappingProxyType(aliases),
        unknown_label=unknown,
    )


def _classification_intervals(
    payload: Mapping[str, object],
) -> tuple[_ClassificationInterval, ...]:
    rows = _mappings(payload.get("classification_intervals"), field="classification_intervals")
    result: list[_ClassificationInterval] = []
    for index, row in enumerate(rows):
        field = f"classification_intervals[{index}]"
        start = _integer(row, "start_session_time_us", field=field)
        end = _integer(row, "end_session_time_us", field=field)
        if end <= start:
            raise ValueError(f"M3_ID_INTERVAL_INVALID:{field}")
        association_resolved = row.get("association_resolved")
        if not isinstance(association_resolved, bool):
            raise ValueError(f"M3_ID_INPUT_INVALID:{field}.association_resolved")
        result.append(
            _ClassificationInterval(
                start_us=start,
                end_us=end,
                track_id=_text(row, "track_id", field=field),
                reference_target_id=_text(row, "reference_target_id", field=field),
                reported=_text(row, "reported_classification", field=field),
                reference=_text(row, "reference_classification", field=field),
                association_resolved=association_resolved,
                reference_quality_status=_text(
                    row,
                    "reference_quality_status",
                    field=field,
                ),
            )
        )
    return tuple(result)


def _normalized_eligible(
    payload: Mapping[str, object],
) -> tuple[
    _Taxonomy,
    tuple[tuple[_ClassificationInterval, str, str], ...],
    int,
]:
    taxonomy = _taxonomy(payload)
    intervals = _classification_intervals(payload)
    eligible: list[tuple[_ClassificationInterval, str, str]] = []
    rejected = 0
    for item in intervals:
        if not item.association_resolved or item.reference_quality_status != "VALID":
            rejected += 1
            continue
        eligible.append(
            (
                item,
                taxonomy.normalize(item.reported),
                taxonomy.normalize(item.reference),
            )
        )
    return taxonomy, tuple(eligible), rejected


def _classification_accuracy(
    request: M2MetricPluginRequest,
    *,
    correct: bool,
) -> Mapping[str, object]:
    taxonomy, eligible, rejected = _normalized_eligible(request.input_payload)
    classified = tuple(
        item
        for item in eligible
        if item[2] != taxonomy.unknown_label and item[1] != taxonomy.unknown_label
    )
    denominator_us = sum(item[0].end_us - item[0].start_us for item in classified)
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
    matching_us = sum(
        item[0].end_us - item[0].start_us
        for item in classified
        if (item[1] == item[2]) is correct
    )
    canonical_labels = tuple(sorted(taxonomy.canonical_labels))
    confusion: dict[str, dict[str, int]] = {
        reference: {reported: 0 for reported in canonical_labels}
        for reference in canonical_labels
    }
    for interval, reported, reference in classified:
        confusion[reference][reported] += interval.end_us - interval.start_us
    return _output(
        request,
        value_numeric=matching_us / denominator_us,
        evidence={
            "taxonomy_identity": [
                taxonomy.taxonomy_id,
                taxonomy.version,
                taxonomy.digest,
            ],
            "classified_eligible_dwell_us": denominator_us,
            (
                "correct_canonical_label_dwell_us"
                if correct
                else "incorrect_canonical_label_dwell_us"
            ): matching_us,
            "canonical_confusion_dwell_us": confusion,
            "rejected_interval_count": rejected,
        },
    )


def _id008(request: M2MetricPluginRequest) -> Mapping[str, object]:
    return _classification_accuracy(request, correct=True)


def _id009(request: M2MetricPluginRequest) -> Mapping[str, object]:
    return _classification_accuracy(request, correct=False)


def _id010(request: M2MetricPluginRequest) -> Mapping[str, object]:
    rows = _mappings(
        request.input_payload.get("reported_classification_intervals"),
        field="reported_classification_intervals",
    )
    eligible: list[tuple[int, int, str]] = []
    for index, row in enumerate(rows):
        field = f"reported_classification_intervals[{index}]"
        start = _integer(row, "start_session_time_us", field=field)
        end = _integer(row, "end_session_time_us", field=field)
        if end <= start:
            raise ValueError(f"M3_ID_INTERVAL_INVALID:{field}")
        association_resolved = row.get("association_resolved")
        if not isinstance(association_resolved, bool):
            raise ValueError(f"M3_ID_INPUT_INVALID:{field}.association_resolved")
        if association_resolved:
            eligible.append(
                (
                    start,
                    end,
                    _text(row, "reported_classification", field=field),
                )
            )
    denominator_us = sum(end - start for start, end, _reported in eligible)
    if denominator_us <= 0:
        return _missing(request, "NO_ELIGIBLE_TRACK_DWELL")
    unknown_us = sum(
        end - start
        for start, end, reported in eligible
        if reported == "UNKNOWN"
    )
    return _output(
        request,
        value_numeric=unknown_us / denominator_us,
        evidence={
            "unknown_dwell_us": unknown_us,
            "eligible_track_dwell_us": denominator_us,
        },
    )


def _id011(request: M2MetricPluginRequest) -> Mapping[str, object]:
    taxonomy = _taxonomy(request.input_payload)
    stable_track_persistence = _profile_float(
        request.input_payload,
        "stable_track_persistence_s",
    )
    id_stability_persistence = _profile_float(
        request.input_payload,
        "id_stability_persistence_s",
    )
    max_gap = _finite(_profile(request.input_payload), "max_gap_us", field="profile")
    if (
        stable_track_persistence <= 0.0
        or id_stability_persistence <= 0.0
        or max_gap < 0.0
    ):
        raise ValueError("M3_ID_IDENTIFICATION_LATENCY_PROFILE_INVALID")
    stable_track_start = _optional_integer(
        request.input_payload,
        "stable_track_start_time_us",
        field="P1-ID-011",
    )
    first_stable_id = _optional_integer(
        request.input_payload,
        "first_stable_non_unknown_correct_id_time_us",
        field="P1-ID-011",
    )
    if stable_track_start is None or first_stable_id is None:
        return _missing(request, "IDENTIFICATION_STABLE_ONSET_UNAVAILABLE")
    if first_stable_id < stable_track_start:
        raise ValueError("M3_ID_IDENTIFICATION_PRECEDES_STABLE_TRACK")
    return _output(
        request,
        value_numeric=(first_stable_id - stable_track_start) / 1_000_000.0,
        evidence={
            "taxonomy_identity": [
                taxonomy.taxonomy_id,
                taxonomy.version,
                taxonomy.digest,
            ],
            "stable_track_persistence_s": stable_track_persistence,
            "id_stability_persistence_s": id_stability_persistence,
            "max_gap_us": int(max_gap),
            "stable_track_start_time_us": stable_track_start,
            "first_stable_non_unknown_correct_id_time_us": first_stable_id,
        },
    )


def _stable_classification_episodes(
    normalized: Sequence[tuple[_ClassificationInterval, str, str]],
    *,
    max_gap_us: int,
) -> tuple[tuple[int, int, str, str, str, str], ...]:
    ordered = sorted(normalized, key=lambda item: (item[0].start_us, item[0].end_us))
    result: list[tuple[int, int, str, str, str, str]] = []
    current: tuple[int, int, str, str, str, str] | None = None
    for interval, reported, reference in ordered:
        identity = (
            interval.track_id,
            interval.reference_target_id,
            reported,
            reference,
        )
        if current is None:
            current = (
                interval.start_us,
                interval.end_us,
                identity[0],
                identity[1],
                identity[2],
                identity[3],
            )
            continue
        start, end, track_id, reference_target_id, current_reported, current_reference = (
            current
        )
        if (
            identity
            == (
                track_id,
                reference_target_id,
                current_reported,
                current_reference,
            )
            and interval.start_us - end <= max_gap_us
        ):
            current = (
                start,
                max(end, interval.end_us),
                track_id,
                reference_target_id,
                current_reported,
                current_reference,
            )
        else:
            result.append(current)
            current = (
                interval.start_us,
                interval.end_us,
                identity[0],
                identity[1],
                identity[2],
                identity[3],
            )
    if current is not None:
        result.append(current)
    return tuple(result)


def _id012(request: M2MetricPluginRequest) -> Mapping[str, object]:
    taxonomy, eligible, rejected = _normalized_eligible(request.input_payload)
    persistence_s = _profile_float(request.input_payload, "id_stability_persistence_s")
    max_gap = _finite(_profile(request.input_payload), "max_gap_us", field="profile")
    if persistence_s <= 0.0 or max_gap < 0.0:
        raise ValueError("M3_ID_IDENTIFICATION_STABILITY_PROFILE_INVALID")
    if not eligible:
        return _missing(request, "REFERENCE_CLASSIFICATION_UNAVAILABLE")
    persistence_us = int(persistence_s * 1_000_000.0)
    episodes = _stable_classification_episodes(
        eligible,
        max_gap_us=int(max_gap),
    )
    correct_episodes = tuple(
        episode
        for episode in episodes
        if episode[4] == episode[5]
        and episode[4] != taxonomy.unknown_label
        and episode[1] - episode[0] >= persistence_us
    )
    if not correct_episodes:
        return _missing(
            request,
            "NO_STABLE_CORRECT_IDENTIFICATION",
            evidence={"rejected_interval_count": rejected},
        )
    first_stable_time = min(episode[0] + persistence_us for episode in correct_episodes)

    denominator_us = sum(
        max(0, item.end_us - max(item.start_us, first_stable_time))
        for item, _reported, reference in eligible
        if reference != taxonomy.unknown_label and item.end_us > first_stable_time
    )
    if denominator_us <= 0:
        return _missing(request, "NO_POST_IDENTIFICATION_ELIGIBLE_DWELL")

    stable_correct_us = sum(
        max(
            0,
            episode[1]
            - max(first_stable_time, episode[0] + persistence_us),
        )
        for episode in correct_episodes
        if episode[1] > first_stable_time
    )

    post = sorted(
        (
            max(item.start_us, first_stable_time),
            item.end_us,
            reported,
        )
        for item, reported, reference in eligible
        if reference != taxonomy.unknown_label and item.end_us > first_stable_time
    )
    labels: list[str] = []
    for _start, _end, label in post:
        if not labels or labels[-1] != label:
            labels.append(label)
    transition_count = max(0, len(labels) - 1)

    return _output(
        request,
        value_numeric=stable_correct_us / denominator_us,
        evidence={
            "taxonomy_identity": [
                taxonomy.taxonomy_id,
                taxonomy.version,
                taxonomy.digest,
            ],
            "id_stability_persistence_s": persistence_s,
            "max_gap_us": int(max_gap),
            "first_stable_correct_identification_time_us": first_stable_time,
            "stable_correct_canonical_classified_dwell_us": stable_correct_us,
            "post_identification_eligible_dwell_us": denominator_us,
            "canonical_label_transition_count": transition_count,
            "rejected_interval_count": rejected,
        },
    )


_HANDLERS: Mapping[
    str,
    Callable[[M2MetricPluginRequest], Mapping[str, object]],
] = MappingProxyType(
    {
        "P1-ID-001": _id001,
        "P1-ID-002": _id002,
        "P1-ID-003": _id003,
        "P1-ID-004": _id004,
        "P1-ID-005": _id005,
        "P1-ID-006": _id006,
        "P1-ID-007": _id007,
        "P1-ID-008": _id008,
        "P1-ID-009": _id009,
        "P1-ID-010": _id010,
        "P1-ID-011": _id011,
        "P1-ID-012": _id012,
    }
)


def _plugin(request: M2MetricPluginRequest) -> Mapping[str, object]:
    if not _guard(request):
        return _not_applicable(request)
    handler = _HANDLERS.get(request.definition.metric_code)
    if handler is None:
        raise ValueError(f"M3_ID_PLUGIN_MISSING:{request.definition.metric_code}")
    return handler(request)


M3_ID_PLUGINS: Mapping[str, M2MetricPlugin] = MappingProxyType(
    {code: _plugin for code in M3_ID_CODES}
)


def register_m3_identification_plugins(
    plan: M2MetricExecutionPlan,
    registry: MetricPluginRegistry,
) -> None:
    """Register the exact twelve ID algorithms in the shared Catalog registry."""

    definitions = tuple(
        definition
        for definition in plan.definitions
        if definition.metric_code in M3_ID_CODES
    )
    if (
        len(definitions) != 12
        or {item.metric_code for item in definitions} != set(M3_ID_CODES)
        or {item.family for item in definitions} != {M3_ID_FAMILY}
    ):
        raise CatalogMetricEngineError(
            "M3_ID_DELIVERY_MEMBERSHIP_DRIFT",
            repr(tuple(item.metric_code for item in definitions)),
        )
    for definition in definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"m3-identification-remainder:{definition.metric_code}:v1",
            plugin=_plugin,
        )
