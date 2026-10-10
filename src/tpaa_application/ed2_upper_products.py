"""ED-2.0 B3 immutable upper-product semantic contracts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, cast
from uuid import UUID

ED2_UPPER_PRODUCT_SCHEMA: Final = "TPAA_ED2_UPPER_PRODUCT_V1"
ED2_UPPER_KINDS: Final = frozenset(
    {
        "EVENT_RELATION_ROOT_CAUSE",
        "LONGITUDINAL_HUMAN_TEAM",
        "COURSE_UNIT_ANALYTICS",
        "TRAINING_PLUGIN_COMPOSITION",
        "JOINT_LVC_GATEWAY",
        "MEDIA_DEBRIEF",
    }
)
ED2_ROOT_CAUSE_CATEGORIES: Final = frozenset(
    {
        "FLIGHT_CONTROL",
        "INFORMATION_AVAILABILITY",
        "TRACK_ASSOCIATION",
        "PROCEDURE",
        "DECISION_TASK_MANAGEMENT",
        "COMMUNICATION",
        "TEAM_COORDINATION",
        "TRAINING_SYSTEM",
        "DATA_QUALITY",
        "EXTERNAL_SCENARIO",
        "INSTRUCTOR_DETERMINATION",
    }
)
ED2_TRAINING_PLUGIN_CONTRACTS: Final = (
    "ContextApplicabilityProfile",
    "WorldReconstructionPolicySet",
    "StageObjectiveProjector",
    "TPAAMChainBuilder",
    "EventRelationComplianceDetectors",
    "MetricSet",
    "AssessmentProfile",
)
ED2_DEBRIEF_LAYERS: Final = frozenset({"C", "W", "P", "A", "J", "M", "ASSESSMENT"})

_FORBIDDEN_DIRECT_IDENTITY_KEYS: Final = frozenset(
    {
        "actor_id",
        "person_id",
        "pilot_id",
        "name",
        "full_name",
        "email",
        "callsign",
    }
)


class ED2UpperProductError(RuntimeError):
    """Fail-closed ED-2 upper-product contract error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True, slots=True)
class ED2UpperProduct:
    kind: str
    source_release_ids: tuple[str, ...]
    as_of_utc: str
    payload: dict[str, object]
    logical_content_hash: str

    def manifest(self) -> dict[str, object]:
        return {
            "schema": ED2_UPPER_PRODUCT_SCHEMA,
            "kind": self.kind,
            "source_release_ids": list(self.source_release_ids),
            "as_of_utc": self.as_of_utc,
            "payload": self.payload,
        }


def normalize_ed2_upper_kind(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in ED2_UPPER_KINDS:
        raise ED2UpperProductError("ED2_UPPER_KIND_INVALID", value)
    return normalized


def _uuid(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ED2UpperProductError("ED2_UPPER_UUID_INVALID", field)
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise ED2UpperProductError("ED2_UPPER_UUID_INVALID", field) from exc
    if parsed.int == 0 or str(parsed) != value:
        raise ED2UpperProductError("ED2_UPPER_UUID_INVALID", field)
    return value


def _utc(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z") or "T" not in value:
        raise ED2UpperProductError("ED2_UPPER_TIME_INVALID", field)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ED2UpperProductError("ED2_UPPER_TIME_INVALID", field) from exc
    if parsed.utcoffset() is None:
        raise ED2UpperProductError("ED2_UPPER_TIME_INVALID", field)
    return value


def _mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) for key in value
    ):
        raise ED2UpperProductError("ED2_UPPER_MAPPING_INVALID", field)
    return dict(cast(Mapping[str, object], value))


def _sequence(value: object, field: str) -> tuple[object, ...]:
    if not isinstance(value, (list, tuple)):
        raise ED2UpperProductError("ED2_UPPER_SEQUENCE_INVALID", field)
    return tuple(cast(Sequence[object], value))


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ED2UpperProductError("ED2_UPPER_TEXT_INVALID", field)
    return value


def _texts(value: object, field: str) -> tuple[str, ...]:
    result: list[str] = []
    for index, item in enumerate(_sequence(value, field)):
        result.append(_text(item, f"{field}[{index}]"))
    return tuple(result)


def _hash64(value: object, field: str) -> str:
    text = _text(value, field)
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ED2UpperProductError("ED2_UPPER_HASH_INVALID", field)
    return text


def _validate_json_native(value: object, path: str = "payload") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        raise ED2UpperProductError("ED2_UPPER_FLOAT_FORBIDDEN", path)
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ED2UpperProductError("ED2_UPPER_JSON_KEY_INVALID", path)
            _validate_json_native(item, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _validate_json_native(item, f"{path}[{index}]")
        return
    raise ED2UpperProductError(
        "ED2_UPPER_JSON_TYPE_INVALID",
        f"{path}:{type(value).__name__}",
    )


def _canonical_hash(value: object) -> str:
    _validate_json_native(value)
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _forbid_direct_identity(value: object, path: str = "payload") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if isinstance(key, str) and key.lower() in _FORBIDDEN_DIRECT_IDENTITY_KEYS:
                raise ED2UpperProductError(
                    "ED2_UPPER_DIRECT_IDENTITY_FORBIDDEN",
                    f"{path}.{key}",
                )
            _forbid_direct_identity(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _forbid_direct_identity(item, f"{path}[{index}]")


def _validate_event_relation(payload: Mapping[str, object]) -> None:
    event_refs = _texts(payload.get("event_refs"), "event_refs")
    relation_refs = _texts(payload.get("relation_refs"), "relation_refs")
    objective_refs = _texts(payload.get("objective_refs"), "objective_refs")
    compliance_refs = _texts(payload.get("compliance_refs"), "compliance_refs")
    for field, refs in (
        ("event_refs", event_refs),
        ("relation_refs", relation_refs),
    ):
        for index, item in enumerate(refs):
            _uuid(item, f"{field}[{index}]")
    if not relation_refs or not compliance_refs:
        raise ED2UpperProductError(
            "ED2_UPPER_RELATION_COMPLIANCE_REQUIRED",
            "relation_refs/compliance_refs",
        )
    for field, refs in (
        ("event_availability", event_refs),
        ("objective_availability", objective_refs),
    ):
        availability = payload.get(field)
        if availability not in {"AVAILABLE", "UNAVAILABLE"}:
            raise ED2UpperProductError(
                "ED2_UPPER_AVAILABILITY_INVALID",
                field,
            )
        if (availability == "AVAILABLE") != bool(refs):
            raise ED2UpperProductError(
                "ED2_UPPER_AVAILABILITY_REF_MISMATCH",
                field,
            )
    if payload.get("causal_upgrade") is not False:
        raise ED2UpperProductError(
            "ED2_UPPER_CAUSAL_UPGRADE_FORBIDDEN",
            "causal_upgrade",
        )
    if payload.get("knowledge_time_mode") not in {
        "ORIGINAL_AS_KNOWN",
        "RETROSPECTIVE",
    }:
        raise ED2UpperProductError(
            "ED2_UPPER_KNOWLEDGE_TIME_INVALID",
            "knowledge_time_mode",
        )
    candidates = _sequence(
        payload.get("root_cause_candidates"),
        "root_cause_candidates",
    )
    if not candidates:
        raise ED2UpperProductError(
            "ED2_UPPER_ROOT_CAUSE_CANDIDATE_REQUIRED",
            "root_cause_candidates",
        )
    for index, raw in enumerate(candidates):
        item = _mapping(raw, f"root_cause_candidates[{index}]")
        category = _text(
            item.get("category"),
            f"root_cause_candidates[{index}].category",
        )
        if category not in ED2_ROOT_CAUSE_CATEGORIES:
            raise ED2UpperProductError(
                "ED2_UPPER_ROOT_CAUSE_CATEGORY_INVALID",
                category,
            )
        if item.get("candidate_only") is not True:
            raise ED2UpperProductError(
                "ED2_UPPER_ROOT_CAUSE_MUST_BE_CANDIDATE",
                category,
            )
        if item.get("automatic_personnel_fault") is not False:
            raise ED2UpperProductError(
                "ED2_UPPER_AUTOMATIC_PERSONNEL_FAULT_FORBIDDEN",
                category,
            )


def _validate_human_team(payload: Mapping[str, object]) -> None:
    if payload.get("scope_kind") not in {"HUMAN", "TEAM"}:
        raise ED2UpperProductError("ED2_UPPER_LONGITUDINAL_SCOPE_INVALID", "scope_kind")
    if payload.get("privacy_mode") != "PSEUDONYMIZED":
        raise ED2UpperProductError("ED2_UPPER_PRIVACY_MODE_INVALID", "privacy_mode")
    if payload.get("direct_identity_present") is not False:
        raise ED2UpperProductError(
            "ED2_UPPER_DIRECT_IDENTITY_FORBIDDEN",
            "direct_identity_present",
        )
    _forbid_direct_identity(payload)
    subject_key = _text(payload.get("subject_key"), "subject_key")
    if not subject_key.startswith("pseudonym:"):
        raise ED2UpperProductError(
            "ED2_UPPER_PSEUDONYM_REQUIRED",
            "subject_key",
        )
    if not _texts(payload.get("comparison_dimensions"), "comparison_dimensions"):
        raise ED2UpperProductError(
            "ED2_UPPER_COHORT_DIMENSIONS_REQUIRED",
            "comparison_dimensions",
        )
    for index, ref in enumerate(_texts(payload.get("revision_refs"), "revision_refs")):
        _uuid(ref, f"revision_refs[{index}]")
    if payload.get("revision_aware_replay") is not True:
        raise ED2UpperProductError(
            "ED2_UPPER_REVISION_REPLAY_REQUIRED",
            "revision_aware_replay",
        )
    if not _texts(payload.get("trend_contracts"), "trend_contracts"):
        raise ED2UpperProductError(
            "ED2_UPPER_TREND_CONTRACT_REQUIRED",
            "trend_contracts",
        )


def _validate_course_unit(payload: Mapping[str, object]) -> None:
    if payload.get("scope_kind") not in {"COURSE", "UNIT"}:
        raise ED2UpperProductError("ED2_UPPER_ANALYTICS_SCOPE_INVALID", "scope_kind")
    if payload.get("privacy_mode") != "AGGREGATED":
        raise ED2UpperProductError("ED2_UPPER_PRIVACY_MODE_INVALID", "privacy_mode")
    _forbid_direct_identity(payload)
    minimum = payload.get("minimum_cohort_size")
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 2:
        raise ED2UpperProductError(
            "ED2_UPPER_COHORT_MINIMUM_INVALID",
            "minimum_cohort_size",
        )
    if payload.get("suppressed_below_minimum") is not True:
        raise ED2UpperProductError(
            "ED2_UPPER_PRIVACY_SUPPRESSION_REQUIRED",
            "suppressed_below_minimum",
        )
    if not _texts(payload.get("cohort_dimensions"), "cohort_dimensions"):
        raise ED2UpperProductError(
            "ED2_UPPER_COHORT_DIMENSIONS_REQUIRED",
            "cohort_dimensions",
        )
    if not _texts(payload.get("aggregate_refs"), "aggregate_refs"):
        raise ED2UpperProductError(
            "ED2_UPPER_AGGREGATE_REF_REQUIRED",
            "aggregate_refs",
        )


def _validate_plugin(payload: Mapping[str, object]) -> None:
    components = _sequence(payload.get("components"), "components")
    observed: list[str] = []
    for index, raw in enumerate(components):
        item = _mapping(raw, f"components[{index}]")
        if any(
            key in item
            for key in ("module_path", "import_path", "dynamic_entrypoint", "wheel_uri")
        ):
            raise ED2UpperProductError(
                "ED2_UPPER_PLUGIN_DYNAMIC_LOAD_FORBIDDEN",
                f"components[{index}]",
            )
        contract = _text(item.get("contract"), f"components[{index}].contract")
        observed.append(contract)
        _text(
            item.get("implementation_id"),
            f"components[{index}].implementation_id",
        )
        _text(
            item.get("implementation_version"),
            f"components[{index}].implementation_version",
        )
        _hash64(
            item.get("authority_hash"),
            f"components[{index}].authority_hash",
        )
        if item.get("enabled") is not True:
            raise ED2UpperProductError(
                "ED2_UPPER_PLUGIN_COMPONENT_DISABLED",
                contract,
            )
    if tuple(observed) != ED2_TRAINING_PLUGIN_CONTRACTS:
        raise ED2UpperProductError(
            "ED2_UPPER_PLUGIN_CONTRACT_SET_INVALID",
            ",".join(observed),
        )
    if payload.get("untrusted_dynamic_loading") is not False:
        raise ED2UpperProductError(
            "ED2_UPPER_PLUGIN_DYNAMIC_LOAD_FORBIDDEN",
            "untrusted_dynamic_loading",
        )


def _validate_gateway(payload: Mapping[str, object]) -> None:
    for field in (
        "external_profile_id",
        "external_profile_version",
        "adapter_id",
        "adapter_version",
        "interop_snapshot_id",
    ):
        _text(payload.get(field), field)
    _hash64(payload.get("logical_content_hash"), "logical_content_hash")
    if payload.get("external_protocol_boundary") is not True:
        raise ED2UpperProductError(
            "ED2_UPPER_GATEWAY_BOUNDARY_REQUIRED",
            "external_protocol_boundary",
        )
    if payload.get("session_type") != "LVC":
        raise ED2UpperProductError("ED2_UPPER_GATEWAY_SESSION_INVALID", "session_type")
    if payload.get("mapping_lossless") is not True:
        raise ED2UpperProductError(
            "ED2_UPPER_GATEWAY_LOSSY_MAPPING",
            "mapping_lossless",
        )
    if payload.get("fact_projection_separated") is not True:
        raise ED2UpperProductError(
            "ED2_UPPER_GATEWAY_FACT_PROJECTION_CONFLATION",
            "fact_projection_separated",
        )
    if payload.get("operational_optimization") is not False:
        raise ED2UpperProductError(
            "ED2_UPPER_OPERATIONAL_OPTIMIZATION_FORBIDDEN",
            "operational_optimization",
        )
    units = _mapping(payload.get("unit_basis"), "unit_basis")
    if not units:
        raise ED2UpperProductError(
            "ED2_UPPER_GATEWAY_UNIT_BASIS_REQUIRED",
            "unit_basis",
        )
    for key, value in units.items():
        _text(key, "unit_basis.key")
        _text(value, f"unit_basis.{key}")
    _text(payload.get("time_basis"), "time_basis")
    _texts(payload.get("canonical_entity_refs"), "canonical_entity_refs")
    _texts(payload.get("canonical_relation_refs"), "canonical_relation_refs")


def _validate_media(
    payload: Mapping[str, object],
    source_release_ids: tuple[str, ...],
) -> None:
    release_id = _uuid(payload.get("release_id"), "release_id")
    if release_id not in source_release_ids:
        raise ED2UpperProductError(
            "ED2_UPPER_MEDIA_RELEASE_MISMATCH",
            release_id,
        )
    if payload.get("mutable_alias_resolution") is not False:
        raise ED2UpperProductError(
            "ED2_UPPER_MUTABLE_ALIAS_FORBIDDEN",
            "mutable_alias_resolution",
        )
    if payload.get("business_recompute") is not False:
        raise ED2UpperProductError(
            "ED2_UPPER_PRESENTATION_RECOMPUTE_FORBIDDEN",
            "business_recompute",
        )
    if payload.get("cesium_linked") is not True:
        raise ED2UpperProductError(
            "ED2_UPPER_CESIUM_LINK_REQUIRED",
            "cesium_linked",
        )
    if payload.get("view_2d") is not True or payload.get("view_3d") is not True:
        raise ED2UpperProductError(
            "ED2_UPPER_DEBRIEF_VIEW_REQUIRED",
            "2d/3d",
        )
    layers = set(_texts(payload.get("semantic_layers"), "semantic_layers"))
    if not {"W", "P", "A", "J", "M"}.issubset(layers) or not layers.issubset(
        ED2_DEBRIEF_LAYERS
    ):
        raise ED2UpperProductError(
            "ED2_UPPER_DEBRIEF_LAYERS_INVALID",
            ",".join(sorted(layers)),
        )

    previous: int | None = None
    for index, raw in enumerate(_sequence(payload.get("timeline"), "timeline")):
        item = _mapping(raw, f"timeline[{index}]")
        time_us = item.get("session_time_us")
        if isinstance(time_us, bool) or not isinstance(time_us, int) or time_us < 0:
            raise ED2UpperProductError(
                "ED2_UPPER_TIMELINE_TIME_INVALID",
                f"timeline[{index}]",
            )
        if previous is not None and time_us < previous:
            raise ED2UpperProductError(
                "ED2_UPPER_TIMELINE_ORDER_INVALID",
                f"timeline[{index}]",
            )
        previous = time_us
        layer = _text(item.get("layer"), f"timeline[{index}].layer")
        if layer not in ED2_DEBRIEF_LAYERS:
            raise ED2UpperProductError(
                "ED2_UPPER_DEBRIEF_LAYER_INVALID",
                layer,
            )

    media_ids: set[str] = set()
    for index, raw in enumerate(_sequence(payload.get("media"), "media")):
        item = _mapping(raw, f"media[{index}]")
        media_id = _text(item.get("media_id"), f"media[{index}].media_id")
        if media_id in media_ids:
            raise ED2UpperProductError("ED2_UPPER_MEDIA_ID_DUPLICATE", media_id)
        media_ids.add(media_id)
        item_release_id = _uuid(
            item.get("source_release_id"),
            f"media[{index}].source_release_id",
        )
        if item_release_id != release_id:
            raise ED2UpperProductError(
                "ED2_UPPER_MEDIA_RELEASE_MISMATCH",
                media_id,
            )
        _text(item.get("media_type"), f"media[{index}].media_type")
        _text(item.get("uri"), f"media[{index}].uri")
        _hash64(
            item.get("artifact_sha256"),
            f"media[{index}].artifact_sha256",
        )
        transcript_status = item.get("transcript_status")
        if transcript_status not in {"AVAILABLE", "UNAVAILABLE"}:
            raise ED2UpperProductError(
                "ED2_UPPER_TRANSCRIPT_STATUS_INVALID",
                media_id,
            )
        transcript_uri = item.get("transcript_uri")
        transcript_sha256 = item.get("transcript_sha256")
        if transcript_status == "AVAILABLE":
            _text(transcript_uri, f"media[{index}].transcript_uri")
            _hash64(
                transcript_sha256,
                f"media[{index}].transcript_sha256",
            )
        elif transcript_uri is not None or transcript_sha256 is not None:
            raise ED2UpperProductError(
                "ED2_UPPER_TRANSCRIPT_REF_MISMATCH",
                media_id,
            )

    bookmark_ids: set[str] = set()
    for index, raw in enumerate(_sequence(payload.get("bookmarks"), "bookmarks")):
        item = _mapping(raw, f"bookmarks[{index}]")
        bookmark_id = _text(
            item.get("bookmark_id"),
            f"bookmarks[{index}].bookmark_id",
        )
        if bookmark_id in bookmark_ids:
            raise ED2UpperProductError(
                "ED2_UPPER_BOOKMARK_ID_DUPLICATE",
                bookmark_id,
            )
        bookmark_ids.add(bookmark_id)
        position = item.get("session_time_us")
        if isinstance(position, bool) or not isinstance(position, int) or position < 0:
            raise ED2UpperProductError(
                "ED2_UPPER_BOOKMARK_TIME_INVALID",
                bookmark_id,
            )

    for index, raw in enumerate(_sequence(payload.get("playlists"), "playlists")):
        item = _mapping(raw, f"playlists[{index}]")
        _text(item.get("playlist_id"), f"playlists[{index}].playlist_id")
        refs = _texts(item.get("item_refs"), f"playlists[{index}].item_refs")
        if any(ref not in media_ids | bookmark_ids for ref in refs):
            raise ED2UpperProductError(
                "ED2_UPPER_PLAYLIST_REF_INVALID",
                f"playlists[{index}]",
            )


def build_ed2_upper_product(
    *,
    kind: str,
    source_release_ids: Sequence[str],
    as_of_utc: str,
    payload: Mapping[str, object],
) -> ED2UpperProduct:
    normalized = normalize_ed2_upper_kind(kind)
    releases = tuple(
        sorted(
            {
                _uuid(value, f"source_release_ids[{index}]")
                for index, value in enumerate(source_release_ids)
            }
        )
    )
    if not releases:
        raise ED2UpperProductError(
            "ED2_UPPER_SOURCE_RELEASE_REQUIRED",
            normalized,
        )
    as_of = _utc(as_of_utc, "as_of_utc")
    body = _mapping(payload, "payload")
    _validate_json_native(body)

    if normalized == "EVENT_RELATION_ROOT_CAUSE":
        _validate_event_relation(body)
    elif normalized == "LONGITUDINAL_HUMAN_TEAM":
        _validate_human_team(body)
    elif normalized == "COURSE_UNIT_ANALYTICS":
        _validate_course_unit(body)
    elif normalized == "TRAINING_PLUGIN_COMPOSITION":
        _validate_plugin(body)
    elif normalized == "JOINT_LVC_GATEWAY":
        _validate_gateway(body)
    elif normalized == "MEDIA_DEBRIEF":
        _validate_media(body, releases)
    else:  # pragma: no cover - guarded by normalize
        raise AssertionError(normalized)

    manifest = {
        "schema": ED2_UPPER_PRODUCT_SCHEMA,
        "kind": normalized,
        "source_release_ids": list(releases),
        "as_of_utc": as_of,
        "payload": body,
    }
    return ED2UpperProduct(
        kind=normalized,
        source_release_ids=releases,
        as_of_utc=as_of,
        payload=body,
        logical_content_hash=_canonical_hash(manifest),
    )
