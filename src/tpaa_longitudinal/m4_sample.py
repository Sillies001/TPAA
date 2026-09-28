"""M4 Batch 1 longitudinal sample and scope domain.

The module consumes the protected Canonical C3 authority.  It does not define trend
formulas, persistence schema, or API/GUI transport semantics.  Batch 1 is limited to
P1 longitudinal eligibility, exact SESSION Release-bound sample aggregation, and
governed comparison/scope identity.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast
from uuid import UUID

from tpaa_canonical import ArtifactExpectation, CanonicalArtifactLoader
from tpaa_metric import M2MetricDefinition, M2MetricExecutionPlan

M4_AUTHORITY_ID = "M4_LONGITUDINAL_DEBRIEF_AUTHORITY"
M4_AUTHORITY_VERSION = "1.0.0"
M4_DB_SCHEMA_VERSION = "1.6.0"
M4_P1_METRIC_TOTAL = 116
M4_LONGITUDINAL_ELIGIBLE_COUNT = 104
M4_LONGITUDINAL_EXCLUDED_COUNT = 12
M4_SAMPLE_UNIT = "SESSION_CONFIG"
M4_RELEASE_SCOPE_TYPE = "SESSION"
M4_VALID_STATUS = "VALID"
M4_SOURCE_ELIGIBILITY = "ELIGIBLE"
M4_SOURCE_TYPES = frozenset(
    {"CAPABILITY_OBSERVATION", "SYSTEM_PERFORMANCE_OBSERVATION"}
)
M4_NONVALID_STATUSES = frozenset(
    {"N_A", "INSUFFICIENT_DATA", "INVALID", "REVIEW_REQUIRED"}
)
M4_NO_VALID_REASON = "M4_LONGITUDINAL_NO_VALID_VALUE"

_CONTEXT_FIELDS = (
    "scenario_id",
    "scenario_version",
    "syllabus_id",
    "syllabus_version",
    "training_type_set",
    "location_or_range_id",
    "unit_id",
    "role_model_version",
    "context_version",
    "rule_set_version",
    "reference_set_version",
    "metric_profile_version",
    "world_product_versions",
)
_UUID_FIELDS = frozenset({"subject_id", "scenario_id", "unit_id"})


class M4LongitudinalError(RuntimeError):
    """Fail-closed Batch 1 error with a stable diagnostic code."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


class _ReleaseDefinition(Protocol):
    metric_code: str
    semantic_id: str
    semantic_version: int
    definition_hash: str
    subject_type: str
    value_kind: str
    p1_longitudinal_trend_eligibility: bool


class _ReleaseExecution(Protocol):
    metric_code: str
    algorithm_version: str
    definition_hash: str
    plugin_id: str


class SessionReleaseSnapshot(Protocol):
    release_id: str
    session_id: str
    catalog_version: str
    catalog_hash: str
    status: str
    execution_records: Sequence[_ReleaseExecution]

    def definition(self, metric_code: str) -> _ReleaseDefinition: ...


@dataclass(frozen=True)
class M4LongitudinalAuthority:
    version: str
    catalog_version: str
    catalog_hash: str
    sample_profile_id: str
    sample_profile_version: str
    comparison_schema: str
    comparison_required_fields: tuple[str, ...]
    trend_profile_id: str
    trend_profile_version: str
    trend_profile_hash: str
    admitted_subject_types: tuple[str, ...]
    p4_p5_human_team_assessment_active: bool
    m5_formal_product_qualification_claimed: bool


@dataclass(frozen=True)
class M4LongitudinalEligibility:
    catalog_version: str
    catalog_hash: str
    eligible: tuple[M2MetricDefinition, ...]
    excluded: tuple[M2MetricDefinition, ...]

    @property
    def eligible_codes(self) -> tuple[str, ...]:
        return tuple(item.metric_code for item in self.eligible)

    @property
    def excluded_codes(self) -> tuple[str, ...]:
        return tuple(item.metric_code for item in self.excluded)

    def require_eligible(self, metric_code: str) -> M2MetricDefinition:
        for definition in self.eligible:
            if definition.metric_code == metric_code:
                return definition
        if metric_code in self.excluded_codes:
            raise M4LongitudinalError(
                "FAIL_CLOSED_NOT_LONGITUDINAL_ELIGIBLE",
                metric_code,
            )
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_METRIC_UNKNOWN",
            metric_code,
        )


@dataclass(frozen=True)
class M4SourceObservation:
    observation_type: str
    observation_id: str
    release_id: str
    session_id: str
    metric_code: str
    subject_type: str
    subject_id: str
    configuration_key: str
    episode_id: str | None
    eligibility: str
    status: str
    value_numeric: float | None
    reason_codes: tuple[str, ...]
    coverage: float
    confidence: float


@dataclass(frozen=True)
class M4LongitudinalSample:
    sample_id: str
    release_id: str
    release_scope_type: str
    subject_type: str
    subject_id: str
    aircraft_id: str | None
    mission_system_instance_id: str | None
    session_id: str
    session_order_scope_id: str | None
    session_order: int | None
    occurred_at_utc: str | None
    configuration_key: str
    metric_definition_id: str
    metric_semantic_id: str
    metric_semantic_version: int
    comparison_key_hash: str
    sample_unit: str
    aggregation_method: str
    value_numeric: float | None
    status: str
    reason_codes: tuple[str, ...]
    source_observation_refs: tuple[tuple[str, str, str], ...]
    source_episode_count: int
    coverage: float
    confidence: float
    sample_profile_version: str
    logical_content_hash: str

    def projection(self) -> dict[str, object]:
        return {
            "sample_id": self.sample_id,
            "release_id": self.release_id,
            "release_scope_type": self.release_scope_type,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "aircraft_id": self.aircraft_id,
            "mission_system_instance_id": self.mission_system_instance_id,
            "session_id": self.session_id,
            "session_order_scope_id": self.session_order_scope_id,
            "session_order": self.session_order,
            "occurred_at_utc": self.occurred_at_utc,
            "configuration_key": self.configuration_key,
            "metric_definition_id": self.metric_definition_id,
            "metric_semantic_id": self.metric_semantic_id,
            "metric_semantic_version": self.metric_semantic_version,
            "comparison_key_hash": self.comparison_key_hash,
            "sample_unit": self.sample_unit,
            "aggregation_method": self.aggregation_method,
            "value_numeric": self.value_numeric,
            "status": self.status,
            "reason_codes_json": list(self.reason_codes),
            "source_observation_refs_json": [
                {
                    "type": ref_type,
                    "observation_id": observation_id,
                    "release_id": release_id,
                }
                for ref_type, observation_id, release_id in self.source_observation_refs
            ],
            "source_episode_count": self.source_episode_count,
            "coverage": self.coverage,
            "confidence": self.confidence,
            "sample_profile_version": self.sample_profile_version,
            "logical_content_hash": self.logical_content_hash,
        }


@dataclass(frozen=True)
class M4LongitudinalScope:
    longitudinal_scope_key: str
    subject_type: str
    subject_id: str
    metric_semantic_id: str
    metric_semantic_version: int
    comparison_key_hash: str
    session_order_scope_id: str
    trend_profile_version: str
    descriptor_json: str
    descriptor_hash: str

    def projection(self) -> dict[str, object]:
        return {
            "longitudinal_scope_key": self.longitudinal_scope_key,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "aircraft_id": self.subject_id if self.subject_type == "AIRCRAFT" else None,
            "mission_system_instance_id": (
                self.subject_id
                if self.subject_type == "MISSION_SYSTEM_INSTANCE"
                else None
            ),
            "metric_semantic_id": self.metric_semantic_id,
            "metric_semantic_version": self.metric_semantic_version,
            "comparison_key_hash": self.comparison_key_hash,
            "session_order_scope_id": self.session_order_scope_id,
            "trend_profile_version": self.trend_profile_version,
            "descriptor_json": self.descriptor_json,
            "descriptor_hash": self.descriptor_hash,
        }


def _text(value: object, *, field: str, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value:
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_FIELD_INVALID",
            field,
        )
    normalized = unicodedata.normalize("NFC", value)
    if normalized != value:
        value = normalized
    return value


def _canonical_uuid(value: object, *, field: str, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    text = _text(value, field=field)
    assert text is not None
    try:
        parsed = UUID(text)
    except ValueError as exc:
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_UUID_INVALID",
            f"{field}={text!r}",
        ) from exc
    canonical = str(parsed)
    if canonical != text or parsed.int == 0:
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_UUID_INVALID",
            f"{field}={text!r}",
        )
    return canonical


def _hash64(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    assert text is not None
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_HASH_INVALID",
            f"{field}={text!r}",
        )
    return text


def _canonical_json_bytes(value: object) -> bytes:
    try:
        rendered = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_CANONICAL_JSON_INVALID",
            type(exc).__name__,
        ) from exc
    return unicodedata.normalize("NFC", rendered).encode("utf-8")


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def load_m4_longitudinal_authority(
    baseline_root: Path,
) -> M4LongitudinalAuthority:
    loader = CanonicalArtifactLoader(baseline_root)
    artifact = loader.load(
        M4_AUTHORITY_ID,
        expectation=ArtifactExpectation(
            version=M4_AUTHORITY_VERSION,
            schema_version=M4_DB_SCHEMA_VERSION,
            required_top_level_keys=(
                "scope",
                "catalog_binding",
                "sample_profile",
                "comparison_key_contract",
                "longitudinal_scope_contract",
                "trend_profile",
            ),
        ),
    )
    payload = artifact.payload
    scope = payload["scope"]
    catalog = payload["catalog_binding"]
    sample = payload["sample_profile"]
    comparison = payload["comparison_key_contract"]
    trend = payload["trend_profile"]
    if not all(
        isinstance(value, Mapping)
        for value in (scope, catalog, sample, comparison, trend)
    ):
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_AUTHORITY_SHAPE_INVALID",
            M4_AUTHORITY_ID,
        )
    subjects = scope.get("admitted_subject_types")
    required_fields = comparison.get("required_fields")
    if not isinstance(subjects, list) or not all(
        isinstance(item, str) for item in subjects
    ):
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_AUTHORITY_SHAPE_INVALID",
            "scope.admitted_subject_types",
        )
    if not isinstance(required_fields, list) or not all(
        isinstance(item, str) for item in required_fields
    ):
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_AUTHORITY_SHAPE_INVALID",
            "comparison_key_contract.required_fields",
        )
    if (
        catalog.get("p1_total") != M4_P1_METRIC_TOTAL
        or catalog.get("longitudinal_eligible_count")
        != M4_LONGITUDINAL_ELIGIBLE_COUNT
        or catalog.get("excluded_count") != M4_LONGITUDINAL_EXCLUDED_COUNT
        or catalog.get("eligible_value_kind") != "NUMERIC"
        or catalog.get("eligible_default_aggregation") != "MEDIAN"
        or sample.get("sample_unit") != M4_SAMPLE_UNIT
        or sample.get("release_scope_type") != M4_RELEASE_SCOPE_TYPE
    ):
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_AUTHORITY_CONTRACT_DRIFT",
            M4_AUTHORITY_ID,
        )
    if (
        scope.get("p4_p5_human_team_assessment_active") is not False
        or scope.get("m5_formal_product_qualification_claimed") is not False
    ):
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_AUTHORITY_CONTRACT_DRIFT",
            "M4 scope activation flags",
        )
    return M4LongitudinalAuthority(
        version=artifact.declared_version or "",
        catalog_version=str(catalog["catalog_version"]),
        catalog_hash=_hash64(catalog["catalog_sha256"], field="catalog_sha256"),
        sample_profile_id=str(sample["profile_id"]),
        sample_profile_version=str(sample["profile_version"]),
        comparison_schema=str(comparison["schema"]),
        comparison_required_fields=tuple(cast(str, item) for item in required_fields),
        trend_profile_id=str(trend["profile_id"]),
        trend_profile_version=str(trend["profile_version"]),
        trend_profile_hash=_hash64(
            trend["profile_hash"],
            field="trend_profile.profile_hash",
        ),
        admitted_subject_types=tuple(cast(str, item) for item in subjects),
        p4_p5_human_team_assessment_active=cast(
            bool,
            scope.get("p4_p5_human_team_assessment_active"),
        ),
        m5_formal_product_qualification_claimed=cast(
            bool,
            scope.get("m5_formal_product_qualification_claimed"),
        ),
    )


def validate_m4_product_scope(
    authority: M4LongitudinalAuthority,
    *,
    capability_phase: str,
    subject_type: str,
    claims_m5_formal_product_qualification: bool,
) -> None:
    if capability_phase != "P1":
        raise M4LongitudinalError(
            "M4_GOV_P1_ONLY",
            capability_phase,
        )
    if subject_type not in authority.admitted_subject_types:
        raise M4LongitudinalError(
            "FAIL_CLOSED_LONGITUDINAL_SUBJECT_FORBIDDEN",
            subject_type,
        )
    if authority.p4_p5_human_team_assessment_active:
        raise M4LongitudinalError(
            "M4_GOV_P4_P5_ASSESSMENT_MUST_REMAIN_INACTIVE",
            "authority",
        )
    if (
        authority.m5_formal_product_qualification_claimed
        or claims_m5_formal_product_qualification
    ):
        raise M4LongitudinalError(
            "M4_GOV_M5_QUALIFICATION_CLAIM_FORBIDDEN",
            subject_type,
        )


def build_m4_longitudinal_eligibility(
    authority: M4LongitudinalAuthority,
    plan: M2MetricExecutionPlan,
) -> M4LongitudinalEligibility:
    if (
        plan.catalog_version != authority.catalog_version
        or plan.catalog_sha256 != authority.catalog_hash
        or len(plan.definitions) != M4_P1_METRIC_TOTAL
    ):
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_CATALOG_BINDING_MISMATCH",
            plan.catalog_sha256,
        )
    eligible = tuple(
        definition
        for definition in plan.definitions
        if definition.p1_longitudinal_trend_eligibility
    )
    excluded = tuple(
        definition
        for definition in plan.definitions
        if not definition.p1_longitudinal_trend_eligibility
    )
    if (
        len(eligible) != M4_LONGITUDINAL_ELIGIBLE_COUNT
        or len(excluded) != M4_LONGITUDINAL_EXCLUDED_COUNT
    ):
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_MEMBERSHIP_COUNT_DRIFT",
            f"{len(eligible)}/{len(excluded)}",
        )
    for definition in eligible:
        if (
            definition.value_kind != "NUMERIC"
            or definition.default_aggregation != "MEDIAN"
            or definition.subject_type not in authority.admitted_subject_types
            or definition.observation_lane == "QUALITY_EVIDENCE_ONLY"
        ):
            raise M4LongitudinalError(
                "M4_LONGITUDINAL_ELIGIBILITY_CONTRACT_DRIFT",
                definition.metric_code,
            )
    for definition in excluded:
        if definition.p1_longitudinal_trend_eligibility:
            raise M4LongitudinalError(
                "M4_LONGITUDINAL_EXCLUSION_CONTRACT_DRIFT",
                definition.metric_code,
            )
    return M4LongitudinalEligibility(
        catalog_version=plan.catalog_version,
        catalog_hash=plan.catalog_sha256,
        eligible=eligible,
        excluded=excluded,
    )


def build_comparison_key(
    authority: M4LongitudinalAuthority,
    values: Mapping[str, object],
) -> tuple[dict[str, object], str]:
    if set(values) != set(authority.comparison_required_fields):
        raise M4LongitudinalError(
            "FAIL_CLOSED_COMPARISON_KEY_INCOMPLETE",
            repr(sorted(set(authority.comparison_required_fields) - set(values))),
        )
    result: dict[str, object] = {}
    for field in authority.comparison_required_fields:
        value = values[field]
        if field == "metric_semantic_version":
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise M4LongitudinalError(
                    "M4_COMPARISON_KEY_INTEGER_INVALID",
                    field,
                )
            result[field] = value
            continue
        if field == "training_type_set":
            if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
                raise M4LongitudinalError(
                    "M4_COMPARISON_KEY_SET_INVALID",
                    field,
                )
            items = tuple(_text(item, field=field) for item in value)
            if any(item is None for item in items):
                raise M4LongitudinalError(
                    "M4_COMPARISON_KEY_SET_INVALID",
                    field,
                )
            typed_items = tuple(str(item) for item in items)
            if len(set(typed_items)) != len(typed_items):
                raise M4LongitudinalError(
                    "FAIL_CLOSED_SET_ARRAY_DUPLICATE",
                    field,
                )
            result[field] = sorted(typed_items)
            continue
        if field == "world_product_versions":
            if not isinstance(value, Mapping) or not all(
                isinstance(key, str) and isinstance(item, str)
                for key, item in value.items()
            ):
                raise M4LongitudinalError(
                    "M4_COMPARISON_KEY_OBJECT_INVALID",
                    field,
                )
            result[field] = {
                unicodedata.normalize("NFC", key): unicodedata.normalize("NFC", item)
                for key, item in value.items()
            }
            continue
        if field in _UUID_FIELDS:
            result[field] = _canonical_uuid(value, field=field, nullable=True)
            continue
        if field in {
            "catalog_hash",
            "metric_definition_hash",
            "longitudinal_profile_hash",
        }:
            result[field] = _hash64(value, field=field)
            continue
        result[field] = _text(
            value,
            field=field,
            nullable=field in _CONTEXT_FIELDS,
        )
    if result["schema"] != authority.comparison_schema:
        raise M4LongitudinalError(
            "M4_COMPARISON_KEY_SCHEMA_INVALID",
            repr(result["schema"]),
        )
    subject_type = result["subject_type"]
    if subject_type not in authority.admitted_subject_types:
        raise M4LongitudinalError(
            "FAIL_CLOSED_LONGITUDINAL_SUBJECT_FORBIDDEN",
            str(subject_type),
        )
    if result["subject_id"] is None:
        raise M4LongitudinalError(
            "M4_COMPARISON_KEY_SUBJECT_ID_REQUIRED",
            "subject_id",
        )
    if result["configuration_key"] is None:
        raise M4LongitudinalError(
            "FAIL_CLOSED_CONFIGURATION_IDENTITY_REQUIRED",
            "configuration_key",
        )
    canonical_raw: object = json.loads(
        _canonical_json_bytes(result).decode("utf-8")
    )
    if not isinstance(canonical_raw, dict):
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_CANONICAL_JSON_INVALID",
            "comparison key root",
        )
    canonical = cast(dict[str, object], canonical_raw)
    return canonical, _canonical_hash(canonical)


def _execution_for(
    release: SessionReleaseSnapshot,
    metric_code: str,
) -> _ReleaseExecution:
    matches = tuple(
        item for item in release.execution_records if item.metric_code == metric_code
    )
    if len(matches) != 1:
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_RELEASE_EXECUTION_BINDING_INVALID",
            metric_code,
        )
    return matches[0]


def _comparison_values(
    *,
    authority: M4LongitudinalAuthority,
    release: SessionReleaseSnapshot,
    definition: _ReleaseDefinition,
    execution: _ReleaseExecution,
    subject_type: str,
    subject_id: str,
    configuration_key: str,
    comparison_context: Mapping[str, object],
) -> dict[str, object]:
    if set(comparison_context) != set(_CONTEXT_FIELDS):
        raise M4LongitudinalError(
            "FAIL_CLOSED_COMPARISON_KEY_INCOMPLETE",
            "comparison_context",
        )
    return {
        "schema": authority.comparison_schema,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "configuration_key": configuration_key,
        "metric_semantic_id": definition.semantic_id,
        "metric_semantic_version": definition.semantic_version,
        "catalog_version": release.catalog_version,
        "catalog_hash": release.catalog_hash,
        **dict(comparison_context),
        "metric_definition_hash": definition.definition_hash,
        "plugin_name": execution.plugin_id,
        "plugin_version": execution.algorithm_version,
        "longitudinal_profile_id": authority.trend_profile_id,
        "longitudinal_profile_version": authority.trend_profile_version,
        "longitudinal_profile_hash": authority.trend_profile_hash,
    }


def _finite_unit_interval(value: float, *, field: str) -> float:
    if not isinstance(value, float) or not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_QUALITY_INVALID",
            field,
        )
    return value


def _float_hash_token(value: float | None) -> str | None:
    if value is None:
        return None
    return struct.pack(">d", value).hex()


def build_longitudinal_sample(
    *,
    authority: M4LongitudinalAuthority,
    eligibility: M4LongitudinalEligibility,
    release: SessionReleaseSnapshot,
    sample_id: str,
    metric_definition_id: str,
    metric_code: str,
    subject_type: str,
    subject_id: str,
    configuration_key: str,
    comparison_context: Mapping[str, object],
    observations: Sequence[M4SourceObservation],
    session_order_scope_id: str | None = None,
    session_order: int | None = None,
    occurred_at_utc: str | None = None,
) -> M4LongitudinalSample:
    validate_m4_product_scope(
        authority,
        capability_phase="P1",
        subject_type=subject_type,
        claims_m5_formal_product_qualification=False,
    )
    _canonical_uuid(sample_id, field="sample_id")
    _canonical_uuid(metric_definition_id, field="metric_definition_id")
    canonical_subject_id = _canonical_uuid(subject_id, field="subject_id")
    assert canonical_subject_id is not None
    canonical_release_id = _canonical_uuid(release.release_id, field="release_id")
    canonical_session_id = _canonical_uuid(release.session_id, field="session_id")
    assert canonical_release_id is not None and canonical_session_id is not None
    if release.status not in {"VALIDATED", "PUBLISHED"}:
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_RELEASE_NOT_IMMUTABLE",
            release.status,
        )
    if (
        release.catalog_version != authority.catalog_version
        or release.catalog_hash != authority.catalog_hash
    ):
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_RELEASE_CATALOG_MISMATCH",
            release.catalog_hash,
        )
    catalog_definition = eligibility.require_eligible(metric_code)
    release_definition = release.definition(metric_code)
    if (
        release_definition.semantic_id != catalog_definition.semantic_id
        or release_definition.semantic_version != catalog_definition.semantic_version
        or release_definition.definition_hash != catalog_definition.definition_hash
        or release_definition.subject_type != catalog_definition.subject_type
        or release_definition.value_kind != "NUMERIC"
        or release_definition.p1_longitudinal_trend_eligibility is not True
    ):
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_RELEASE_DEFINITION_MISMATCH",
            metric_code,
        )
    if subject_type != release_definition.subject_type:
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_SUBJECT_TYPE_MISMATCH",
            f"{metric_code}:{subject_type}",
        )
    execution = _execution_for(release, metric_code)
    if execution.definition_hash != release_definition.definition_hash:
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_RELEASE_EXECUTION_BINDING_INVALID",
            metric_code,
        )
    if not configuration_key:
        raise M4LongitudinalError(
            "FAIL_CLOSED_CONFIGURATION_IDENTITY_REQUIRED",
            metric_code,
        )
    if not observations:
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_NO_SOURCE_OBSERVATIONS",
            metric_code,
        )

    canonical_observations: list[M4SourceObservation] = []
    for observation in observations:
        if observation.observation_type not in M4_SOURCE_TYPES:
            raise M4LongitudinalError(
                "M4_LONGITUDINAL_SOURCE_TYPE_INVALID",
                observation.observation_type,
            )
        _canonical_uuid(observation.observation_id, field="observation_id")
        if observation.release_id != canonical_release_id:
            raise M4LongitudinalError(
                "M4_LONGITUDINAL_RELEASE_LINEAGE_MISMATCH",
                observation.observation_id,
            )
        if observation.session_id != canonical_session_id:
            raise M4LongitudinalError(
                "M4_LONGITUDINAL_SESSION_LINEAGE_MISMATCH",
                observation.observation_id,
            )
        if (
            observation.metric_code != metric_code
            or observation.subject_type != subject_type
            or observation.subject_id != canonical_subject_id
            or observation.configuration_key != configuration_key
        ):
            raise M4LongitudinalError(
                "M4_LONGITUDINAL_SOURCE_BINDING_MISMATCH",
                observation.observation_id,
            )
        if observation.eligibility != M4_SOURCE_ELIGIBILITY:
            raise M4LongitudinalError(
                "M4_LONGITUDINAL_SOURCE_NOT_ELIGIBLE",
                observation.observation_id,
            )
        if observation.status == M4_VALID_STATUS:
            if (
                observation.value_numeric is None
                or isinstance(observation.value_numeric, bool)
                or not math.isfinite(observation.value_numeric)
            ):
                raise M4LongitudinalError(
                    "M4_LONGITUDINAL_VALID_VALUE_INVALID",
                    observation.observation_id,
                )
        elif observation.status in M4_NONVALID_STATUSES:
            if observation.value_numeric is not None:
                raise M4LongitudinalError(
                    "M4_LONGITUDINAL_NONVALID_VALUE_MUST_BE_NULL",
                    observation.observation_id,
                )
        else:
            raise M4LongitudinalError(
                "M4_LONGITUDINAL_STATUS_INVALID",
                observation.status,
            )
        _finite_unit_interval(observation.coverage, field="coverage")
        _finite_unit_interval(observation.confidence, field="confidence")
        if observation.episode_id is not None:
            _canonical_uuid(observation.episode_id, field="episode_id")
        canonical_observations.append(observation)

    comparison_values = _comparison_values(
        authority=authority,
        release=release,
        definition=release_definition,
        execution=execution,
        subject_type=subject_type,
        subject_id=canonical_subject_id,
        configuration_key=configuration_key,
        comparison_context=comparison_context,
    )
    _, comparison_key_hash = build_comparison_key(authority, comparison_values)

    valid = tuple(
        item for item in canonical_observations if item.status == M4_VALID_STATUS
    )
    if valid:
        values = sorted(
            item.value_numeric
            for item in valid
            if item.value_numeric is not None
        )
        midpoint = len(values) // 2
        if len(values) % 2:
            value_numeric = values[midpoint]
        else:
            value_numeric = (values[midpoint - 1] + values[midpoint]) / 2.0
        status = M4_VALID_STATUS
        reason_codes: tuple[str, ...] = ()
        quality_sources = valid
    else:
        precedence = ("REVIEW_REQUIRED", "INVALID", "INSUFFICIENT_DATA", "N_A")
        status = next(
            candidate
            for candidate in precedence
            if any(item.status == candidate for item in canonical_observations)
        )
        reason_codes = tuple(
            sorted(
                {
                    M4_NO_VALID_REASON,
                    *(
                        reason
                        for item in canonical_observations
                        for reason in item.reason_codes
                    ),
                }
            )
        )
        value_numeric = None
        quality_sources = tuple(canonical_observations)

    coverage = min(item.coverage for item in quality_sources)
    confidence = min(item.confidence for item in quality_sources)
    episode_count = len(
        {
            item.episode_id
            for item in valid
            if item.episode_id is not None
        }
    )
    refs = tuple(
        sorted(
            {
                (item.observation_type, item.observation_id, item.release_id)
                for item in canonical_observations
            }
        )
    )
    canonical_scope_id = (
        _canonical_uuid(
            session_order_scope_id,
            field="session_order_scope_id",
            nullable=True,
        )
        if session_order_scope_id is not None
        else None
    )
    if session_order is not None and (
        isinstance(session_order, bool)
        or not isinstance(session_order, int)
        or session_order < 0
    ):
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_SESSION_ORDER_INVALID",
            repr(session_order),
        )
    aircraft_id = canonical_subject_id if subject_type == "AIRCRAFT" else None
    mission_system_instance_id = (
        canonical_subject_id
        if subject_type == "MISSION_SYSTEM_INSTANCE"
        else None
    )
    hash_material = {
        "release_id": canonical_release_id,
        "release_scope_type": M4_RELEASE_SCOPE_TYPE,
        "subject_type": subject_type,
        "subject_id": canonical_subject_id,
        "aircraft_id": aircraft_id,
        "mission_system_instance_id": mission_system_instance_id,
        "session_id": canonical_session_id,
        "session_order_scope_id": canonical_scope_id,
        "session_order": session_order,
        "occurred_at_utc": occurred_at_utc,
        "configuration_key": configuration_key,
        "metric_definition_id": metric_definition_id,
        "metric_semantic_id": release_definition.semantic_id,
        "metric_semantic_version": release_definition.semantic_version,
        "comparison_key_hash": comparison_key_hash,
        "sample_unit": M4_SAMPLE_UNIT,
        "aggregation_method": catalog_definition.default_aggregation,
        "value_numeric_ieee754_binary64_be_hex": _float_hash_token(value_numeric),
        "status": status,
        "reason_codes_json": list(reason_codes),
        "source_observation_refs_json": [
            {
                "type": ref_type,
                "observation_id": observation_id,
                "release_id": source_release_id,
            }
            for ref_type, observation_id, source_release_id in refs
        ],
        "source_episode_count": episode_count,
        "coverage": coverage,
        "confidence": confidence,
        "sample_profile_version": authority.sample_profile_version,
    }
    logical_content_hash = _canonical_hash(hash_material)
    return M4LongitudinalSample(
        sample_id=sample_id,
        release_id=canonical_release_id,
        release_scope_type=M4_RELEASE_SCOPE_TYPE,
        subject_type=subject_type,
        subject_id=canonical_subject_id,
        aircraft_id=aircraft_id,
        mission_system_instance_id=mission_system_instance_id,
        session_id=canonical_session_id,
        session_order_scope_id=canonical_scope_id,
        session_order=session_order,
        occurred_at_utc=occurred_at_utc,
        configuration_key=configuration_key,
        metric_definition_id=metric_definition_id,
        metric_semantic_id=release_definition.semantic_id,
        metric_semantic_version=release_definition.semantic_version,
        comparison_key_hash=comparison_key_hash,
        sample_unit=M4_SAMPLE_UNIT,
        aggregation_method=catalog_definition.default_aggregation,
        value_numeric=value_numeric,
        status=status,
        reason_codes=reason_codes,
        source_observation_refs=refs,
        source_episode_count=episode_count,
        coverage=coverage,
        confidence=confidence,
        sample_profile_version=authority.sample_profile_version,
        logical_content_hash=logical_content_hash,
    )


def build_longitudinal_scope(
    *,
    authority: M4LongitudinalAuthority,
    sample: M4LongitudinalSample,
    session_order_scope_id: str,
) -> M4LongitudinalScope:
    canonical_scope_id = _canonical_uuid(
        session_order_scope_id,
        field="session_order_scope_id",
    )
    assert canonical_scope_id is not None
    if sample.subject_type not in authority.admitted_subject_types:
        raise M4LongitudinalError(
            "FAIL_CLOSED_LONGITUDINAL_SUBJECT_FORBIDDEN",
            sample.subject_type,
        )
    if (
        sample.session_order_scope_id is not None
        and sample.session_order_scope_id != canonical_scope_id
    ):
        raise M4LongitudinalError(
            "M4_LONGITUDINAL_SESSION_ORDER_SCOPE_MISMATCH",
            sample.sample_id,
        )
    descriptor = {
        "schema": "TPAA_M4_LONGITUDINAL_SCOPE_DESCRIPTOR_V1",
        "subject_type": sample.subject_type,
        "subject_id": sample.subject_id,
        "metric_semantic_id": sample.metric_semantic_id,
        "metric_semantic_version": sample.metric_semantic_version,
        "comparison_key_hash": sample.comparison_key_hash,
        "session_order_scope_id": canonical_scope_id,
        "x_axis_semantics": "SESSION_ORDER",
        "trend_profile_id": authority.trend_profile_id,
        "trend_profile_version": authority.trend_profile_version,
        "trend_profile_hash": authority.trend_profile_hash,
    }
    descriptor_json = _canonical_json_bytes(descriptor).decode("utf-8")
    descriptor_hash = hashlib.sha256(descriptor_json.encode("utf-8")).hexdigest()
    return M4LongitudinalScope(
        longitudinal_scope_key=descriptor_hash,
        subject_type=sample.subject_type,
        subject_id=sample.subject_id,
        metric_semantic_id=sample.metric_semantic_id,
        metric_semantic_version=sample.metric_semantic_version,
        comparison_key_hash=sample.comparison_key_hash,
        session_order_scope_id=canonical_scope_id,
        trend_profile_version=authority.trend_profile_version,
        descriptor_json=descriptor_json,
        descriptor_hash=descriptor_hash,
    )
