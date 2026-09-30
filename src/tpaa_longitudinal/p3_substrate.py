"""M7 Batch 1 governed P3 authority and longitudinal input substrate."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from tpaa_canonical import ArtifactExpectation, CanonicalArtifactLoader

_AUTHORITY_ID = "P3_CAPABILITY_TWIN_AUTHORITY"
_PROFILE_ARTIFACT_ID = "P3_REFERENCE_CONDITION_OLS_MAD_LONGITUDINAL_PROFILE"
_PROFILE_ID = "P3_REFERENCE_CONDITION_OLS_MAD_LONGITUDINAL"


class P3GovernanceError(RuntimeError):
    """Deterministic fail-closed P3 governance error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _object(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise P3GovernanceError("FAIL_CLOSED_P3_AUTHORITY_REQUIRED", field)
    return cast(dict[str, object], value)


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise P3GovernanceError("FAIL_CLOSED_P3_AUTHORITY_REQUIRED", field)
    return value


def _strings(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise P3GovernanceError("FAIL_CLOSED_P3_AUTHORITY_REQUIRED", field)
    return tuple(cast(list[str], value))


@dataclass(frozen=True)
class P3AuthorityPolicy:
    authority_sha256: str
    profile_sha256: str
    forbidden_pointer_tokens: frozenset[str]
    required_p2_release_status: str
    required_source_p1_release_status: str
    required_p2_status: str
    segment_snapshot_type: str
    validation_snapshot_type: str
    training_snapshot_type: str
    profile_id: str
    profile_version: str
    default_claim_level: str
    stronger_claim_level: str
    min_total_validation_points: int
    training_prefix_min_points: int
    training_prefix_max_points: int
    required_object_gc_state: str
    required_exit_jobs: int

    @classmethod
    def from_canonical(
        cls,
        loader: CanonicalArtifactLoader | None = None,
    ) -> P3AuthorityPolicy:
        canonical = loader or CanonicalArtifactLoader()
        authority = canonical.load(
            _AUTHORITY_ID,
            expectation=ArtifactExpectation(
                version="1.0.0",
                schema_version="1.6.0",
                required_top_level_keys=(
                    "exact_identity_rules",
                    "p2_eligibility_contract",
                    "lifecycle_segment_contract",
                    "validation_snapshot_contract",
                    "managed_object_contract",
                    "execution_profile_contract",
                    "claim_contract",
                    "knowledge_time_contract",
                    "release_replay_contract",
                    "admission_guard",
                    "dto_contracts",
                ),
            ),
        )
        profile = canonical.load(
            _PROFILE_ARTIFACT_ID,
            expectation=ArtifactExpectation(
                version="1.0.0",
                schema_version="1.6.0",
                required_top_level_keys=(
                    "source_bindings",
                    "runtime_binding",
                    "segmentation_contract",
                    "longitudinal_core",
                    "validation_contract",
                    "uncertainty_contract",
                    "validity_domain_contract",
                    "identity_contract",
                ),
            ),
        )
        a = dict(authority.payload)
        p = dict(profile.payload)
        exact = _object(a["exact_identity_rules"], field="exact_identity_rules")
        eligible = _object(a["p2_eligibility_contract"], field="p2_eligibility_contract")
        segment = _object(
            a["lifecycle_segment_contract"],
            field="lifecycle_segment_contract",
        )
        validation = _object(
            a["validation_snapshot_contract"],
            field="validation_snapshot_contract",
        )
        managed = _object(a["managed_object_contract"], field="managed_object_contract")
        execution = _object(
            a["execution_profile_contract"],
            field="execution_profile_contract",
        )
        claim = _object(a["claim_contract"], field="claim_contract")
        guard = _object(a["admission_guard"], field="admission_guard")
        source = _object(p["source_bindings"], field="profile.source_bindings")
        identity = _object(p["identity_contract"], field="profile.identity_contract")
        profile_validation = _object(
            p["validation_contract"],
            field="profile.validation_contract",
        )
        if source.get("p3_authority_sha256") != authority.sha256:
            raise P3GovernanceError(
                "FAIL_CLOSED_P3_AUTHORITY_REQUIRED",
                "profile authority hash binding mismatch",
            )
        if (
            execution.get("required_profile_id") != _PROFILE_ID
            or execution.get("required_profile_version") != "1.0.0"
            or identity.get("segment_snapshot_type") != segment.get("snapshot_type")
            or identity.get("validation_dataset_snapshot_type")
            != validation.get("snapshot_type")
            or identity.get("training_dataset_snapshot_type")
            != validation.get("training_snapshot_type")
        ):
            raise P3GovernanceError(
                "FAIL_CLOSED_P3_AUTHORITY_REQUIRED",
                "authority/profile contract drift",
            )
        jobs = guard.get("required_job_count")
        minimum = profile_validation.get("minimum_total_eligible_points")
        train_min = profile_validation.get("training_prefix_min_points")
        train_max = profile_validation.get("training_prefix_max_points")
        for value, field in (
            (jobs, "required_job_count"),
            (minimum, "minimum_total_eligible_points"),
            (train_min, "training_prefix_min_points"),
            (train_max, "training_prefix_max_points"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise P3GovernanceError(
                    "FAIL_CLOSED_P3_AUTHORITY_REQUIRED",
                    field,
                )
        assert isinstance(jobs, int)
        assert isinstance(minimum, int)
        assert isinstance(train_min, int)
        assert isinstance(train_max, int)
        return cls(
            authority_sha256=authority.sha256,
            profile_sha256=profile.sha256,
            forbidden_pointer_tokens=frozenset(
                _strings(
                    exact.get("forbidden_pointer_tokens"),
                    field="forbidden_pointer_tokens",
                )
            ),
            required_p2_release_status=_text(
                eligible.get("required_p2_release_status"),
                field="required_p2_release_status",
            ),
            required_source_p1_release_status=_text(
                eligible.get("required_source_p1_release_status"),
                field="required_source_p1_release_status",
            ),
            required_p2_status=_text(
                eligible.get("required_p2_status"),
                field="required_p2_status",
            ),
            segment_snapshot_type=_text(
                segment.get("snapshot_type"),
                field="segment.snapshot_type",
            ),
            validation_snapshot_type=_text(
                validation.get("snapshot_type"),
                field="validation.snapshot_type",
            ),
            training_snapshot_type=_text(
                validation.get("training_snapshot_type"),
                field="validation.training_snapshot_type",
            ),
            profile_id=_text(
                execution.get("required_profile_id"),
                field="required_profile_id",
            ),
            profile_version=_text(
                execution.get("required_profile_version"),
                field="required_profile_version",
            ),
            default_claim_level=_text(
                claim.get("default_claim_level"),
                field="default_claim_level",
            ),
            stronger_claim_level=_text(
                claim.get("stronger_claim_level"),
                field="stronger_claim_level",
            ),
            min_total_validation_points=minimum,
            training_prefix_min_points=train_min,
            training_prefix_max_points=train_max,
            required_object_gc_state=_text(
                managed.get("required_gc_state"),
                field="required_gc_state",
            ),
            required_exit_jobs=jobs,
        )


def _exact(value: str, *, field: str, policy: P3AuthorityPolicy) -> str:
    if not value.strip():
        raise P3GovernanceError("FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED", field)
    if value.strip().upper() in policy.forbidden_pointer_tokens:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_CURRENT_LATEST_DEFAULT_FORBIDDEN",
            f"{field}={value!r}",
        )
    return value


def _uuid(value: str, *, field: str, policy: P3AuthorityPolicy) -> str:
    _exact(value, field=field, policy=policy)
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        ) from exc
    if str(parsed) != value or parsed.int == 0:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        )
    return value


def _hash64(value: str, *, field: str) -> str:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        )
    return value


def _utc(value: str, *, field: str) -> datetime:
    if not value.endswith("Z") or "T" not in value:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        )
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        ) from exc


def _finite(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise P3GovernanceError("FAIL_CLOSED_P3_PUBLISHED_P2_REQUIRED", field)
    result = float(value)
    if not math.isfinite(result):
        raise P3GovernanceError("FAIL_CLOSED_P3_PUBLISHED_P2_REQUIRED", field)
    return result


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class P3AdjustedEstimateInput:
    estimate_id: str
    p2_release_id: str
    p2_release_status: str
    source_observation_id: str
    source_release_id: str
    source_release_status: str
    attribution_run_id: str
    aircraft_id: str
    aircraft_model_id: str
    configuration_snapshot_id: str
    configuration_snapshot_hash: str
    configuration_key: str
    session_id: str
    episode_id: str
    session_occurred_at_utc: str
    session_order_scope_id: str
    session_order_scope_status: str
    session_order_assignment_current: bool
    session_order: int
    capability_type: str
    metric_semantic_id: str
    metric_semantic_version: int
    comparison_key_hash: str
    reference_condition_id: str
    adjusted_value: float | None
    unit: str
    uncertainty_lower: float | None
    uncertainty_upper: float | None
    factor_effects: Mapping[str, object]
    claim_level: str
    status: str
    evidence_set_id: str
    knowledge_time_utc: str
    estimate_time: str
    created_at: str

    def projection(self) -> dict[str, object]:
        return {
            "estimate_id": self.estimate_id,
            "p2_release_id": self.p2_release_id,
            "source_observation_id": self.source_observation_id,
            "source_release_id": self.source_release_id,
            "attribution_run_id": self.attribution_run_id,
            "aircraft_id": self.aircraft_id,
            "aircraft_model_id": self.aircraft_model_id,
            "configuration_snapshot_id": self.configuration_snapshot_id,
            "configuration_snapshot_hash": self.configuration_snapshot_hash,
            "configuration_key": self.configuration_key,
            "session_id": self.session_id,
            "episode_id": self.episode_id,
            "session_occurred_at_utc": self.session_occurred_at_utc,
            "session_order_scope_id": self.session_order_scope_id,
            "session_order": self.session_order,
            "capability_type": self.capability_type,
            "metric_semantic_id": self.metric_semantic_id,
            "metric_semantic_version": self.metric_semantic_version,
            "comparison_key_hash": self.comparison_key_hash,
            "reference_condition_id": self.reference_condition_id,
            "adjusted_value": self.adjusted_value,
            "unit": self.unit,
            "uncertainty": {
                "lower": self.uncertainty_lower,
                "upper": self.uncertainty_upper,
            },
            "factor_effects": dict(self.factor_effects),
            "claim_level": self.claim_level,
            "status": self.status,
            "evidence_set_id": self.evidence_set_id,
            "knowledge_time_utc": self.knowledge_time_utc,
            "estimate_time": self.estimate_time,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class P3LifecycleEventInput:
    lifecycle_event_id: str
    aircraft_id: str
    event_type: str
    start_occurred_at_utc: str | None
    end_occurred_at_utc: str | None
    source_ref: str


@dataclass(frozen=True)
class P3LifecycleSegment:
    segment_snapshot_id: str
    snapshot_type: str
    frozen: bool
    aircraft_id: str
    aircraft_model_id: str
    configuration_key: str
    configuration_snapshot_ids: tuple[str, ...]
    lifecycle_event_ids: tuple[str, ...]
    session_order_scope_id: str
    first_session_order: int
    last_session_order: int
    as_of_session_order: int
    capability_type: str
    metric_semantic_id: str
    metric_semantic_version: int
    reference_condition_id: str
    unit: str
    observation_count: int
    episode_count: int
    independent_aircraft_count: int
    effective_evidence_count: float
    knowledge_cutoff_utc: str
    estimate_ids: tuple[str, ...]
    segment_hash: str

    def projection(self) -> dict[str, object]:
        return {
            "segment_snapshot_id": self.segment_snapshot_id,
            "aircraft_id": self.aircraft_id,
            "aircraft_model_id": self.aircraft_model_id,
            "configuration_key": self.configuration_key,
            "configuration_snapshot_ids": list(self.configuration_snapshot_ids),
            "lifecycle_event_ids": list(self.lifecycle_event_ids),
            "session_order_scope_id": self.session_order_scope_id,
            "first_session_order": self.first_session_order,
            "last_session_order": self.last_session_order,
            "as_of_session_order": self.as_of_session_order,
            "capability_type": self.capability_type,
            "metric_semantic_id": self.metric_semantic_id,
            "metric_semantic_version": self.metric_semantic_version,
            "reference_condition_id": self.reference_condition_id,
            "unit": self.unit,
            "observation_count": self.observation_count,
            "episode_count": self.episode_count,
            "independent_aircraft_count": self.independent_aircraft_count,
            "effective_evidence_count": self.effective_evidence_count,
            "knowledge_cutoff_utc": self.knowledge_cutoff_utc,
            "segment_hash": self.segment_hash,
        }


@dataclass(frozen=True)
class P3ModelValidationSnapshot:
    validation_snapshot_id: str
    snapshot_type: str
    frozen: bool
    training_dataset_snapshot_id: str
    profile_id: str
    profile_version: str
    aircraft_id: str
    capability_type: str
    segment_snapshot_id: str
    training_estimate_ids: tuple[str, ...]
    validation_estimate_ids: tuple[str, ...]
    independent_aircraft_count: int
    observation_count: int
    effective_evidence_count: float
    claim_evidence_tier: str
    as_of_utc: str
    data_hash: str

    def projection(self) -> dict[str, object]:
        return {
            "validation_snapshot_id": self.validation_snapshot_id,
            "training_dataset_snapshot_id": self.training_dataset_snapshot_id,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "aircraft_id": self.aircraft_id,
            "capability_type": self.capability_type,
            "segment_snapshot_id": self.segment_snapshot_id,
            "training_estimate_ids": list(self.training_estimate_ids),
            "validation_estimate_ids": list(self.validation_estimate_ids),
            "independent_aircraft_count": self.independent_aircraft_count,
            "observation_count": self.observation_count,
            "effective_evidence_count": self.effective_evidence_count,
            "claim_evidence_tier": self.claim_evidence_tier,
            "as_of_utc": self.as_of_utc,
            "data_hash": self.data_hash,
        }


@dataclass(frozen=True)
class P3ManagedObject:
    object_ref_id: str
    managed_uri: str
    artifact_sha256: str
    sealed: bool
    gc_state: str
    deleted_at: str | None


@dataclass(frozen=True)
class P3AdmissionEvidence:
    source_revision: str
    event_name: str
    git_ref: str
    protected_main: bool
    m7_exit_decision: str
    run_conclusion: str
    required_jobs_success: int
    required_jobs_total: int
    p4_p6_inactive: bool


def project_p2_adjusted_estimate(
    value: P3AdjustedEstimateInput,
    *,
    as_of_utc: str,
    policy: P3AuthorityPolicy | None = None,
) -> P3AdjustedEstimateInput:
    p = policy or P3AuthorityPolicy.from_canonical()
    for field, identity in (
        ("estimate_id", value.estimate_id),
        ("p2_release_id", value.p2_release_id),
        ("source_observation_id", value.source_observation_id),
        ("source_release_id", value.source_release_id),
        ("attribution_run_id", value.attribution_run_id),
        ("aircraft_id", value.aircraft_id),
        ("aircraft_model_id", value.aircraft_model_id),
        ("configuration_snapshot_id", value.configuration_snapshot_id),
        ("session_id", value.session_id),
        ("episode_id", value.episode_id),
        ("session_order_scope_id", value.session_order_scope_id),
        ("reference_condition_id", value.reference_condition_id),
        ("evidence_set_id", value.evidence_set_id),
    ):
        _uuid(identity, field=field, policy=p)
    _hash64(value.configuration_snapshot_hash, field="configuration_snapshot_hash")
    expected_key = f"AIRCRAFT_CONFIG_SHA256:{value.configuration_snapshot_hash}"
    if value.configuration_key != expected_key:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_CONFIGURATION_SEGMENT_REQUIRED",
            "configuration_key must derive from exact snapshot_hash",
        )
    for field, identity in (
        ("capability_type", value.capability_type),
        ("metric_semantic_id", value.metric_semantic_id),
        ("unit", value.unit),
        ("claim_level", value.claim_level),
    ):
        _exact(identity, field=field, policy=p)
    _hash64(value.comparison_key_hash, field="comparison_key_hash")
    if (
        isinstance(value.metric_semantic_version, bool)
        or not isinstance(value.metric_semantic_version, int)
        or value.metric_semantic_version <= 0
    ):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
            "metric_semantic_version",
        )
    if (
        isinstance(value.session_order, bool)
        or not isinstance(value.session_order, int)
        or value.session_order < 0
        or value.session_order_scope_status != "ACTIVE"
        or value.session_order_assignment_current is not True
    ):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_SESSION_ORDER_REQUIRED",
            value.estimate_id,
        )
    if (
        value.p2_release_status != p.required_p2_release_status
        or value.source_release_status != p.required_source_p1_release_status
    ):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_PUBLISHED_P2_REQUIRED",
            value.estimate_id,
        )
    if value.status == "NOT_IDENTIFIABLE":
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_NOT_IDENTIFIABLE_NUMERIC_USE",
            value.estimate_id,
        )
    if value.status != p.required_p2_status:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_PUBLISHED_P2_REQUIRED",
            f"status={value.status!r}",
        )
    adjusted = _finite(value.adjusted_value, field="adjusted_value")
    lower = _finite(value.uncertainty_lower, field="uncertainty_lower")
    upper = _finite(value.uncertainty_upper, field="uncertainty_upper")
    if lower > adjusted or adjusted > upper:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_UNCERTAINTY_REQUIRED",
            "uncertainty bounds must contain adjusted_value",
        )
    as_of = _utc(as_of_utc, field="as_of_utc")
    for field, timestamp in (
        ("knowledge_time_utc", value.knowledge_time_utc),
        ("session_occurred_at_utc", value.session_occurred_at_utc),
        ("estimate_time", value.estimate_time),
        ("created_at", value.created_at),
    ):
        parsed = _utc(timestamp, field=field)
        if parsed > as_of:
            raise P3GovernanceError(
                "FAIL_CLOSED_P3_LIFECYCLE_FUTURE_INFORMATION",
                field,
            )
    return value


def build_p3_lifecycle_segment(
    *,
    segment_snapshot_id: str,
    estimates: Sequence[P3AdjustedEstimateInput],
    lifecycle_events: Sequence[P3LifecycleEventInput],
    as_of_utc: str,
    policy: P3AuthorityPolicy | None = None,
) -> P3LifecycleSegment:
    p = policy or P3AuthorityPolicy.from_canonical()
    _uuid(segment_snapshot_id, field="segment_snapshot_id", policy=p)
    if not estimates:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_CONFIGURATION_SEGMENT_REQUIRED",
            "empty segment",
        )
    ordered = tuple(
        sorted(
            (
                project_p2_adjusted_estimate(item, as_of_utc=as_of_utc, policy=p)
                for item in estimates
            ),
            key=lambda item: (item.session_order, item.estimate_id),
        )
    )
    if len({item.estimate_id for item in ordered}) != len(ordered):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
            "duplicate estimate_id",
        )
    if len({item.session_order for item in ordered}) != len(ordered):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_SESSION_ORDER_REQUIRED",
            "duplicate session_order",
        )
    dimensions = (
        "aircraft_id",
        "aircraft_model_id",
        "configuration_key",
        "capability_type",
        "metric_semantic_id",
        "metric_semantic_version",
        "reference_condition_id",
        "unit",
        "session_order_scope_id",
    )
    first = ordered[0]
    for item in ordered[1:]:
        for field in dimensions:
            if getattr(item, field) != getattr(first, field):
                raise P3GovernanceError(
                    "FAIL_CLOSED_P3_CONFIGURATION_SEGMENT_REQUIRED",
                    field,
                )
    occurred = tuple(
        _utc(item.session_occurred_at_utc, field="session_occurred_at_utc")
        for item in ordered
    )
    if any(later <= earlier for earlier, later in zip(occurred, occurred[1:], strict=False)):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_SESSION_ORDER_REQUIRED",
            "session occurred time must increase with session_order",
        )
    as_of = _utc(as_of_utc, field="as_of_utc")
    marker_ids: list[str] = []
    for event in lifecycle_events:
        _uuid(event.lifecycle_event_id, field="lifecycle_event_id", policy=p)
        _uuid(event.aircraft_id, field="lifecycle.aircraft_id", policy=p)
        _uuid(event.source_ref, field="lifecycle.source_ref", policy=p)
        _exact(event.event_type, field="lifecycle.event_type", policy=p)
        if event.aircraft_id != first.aircraft_id:
            raise P3GovernanceError(
                "FAIL_CLOSED_P3_CONFIGURATION_SEGMENT_REQUIRED",
                "lifecycle event aircraft mismatch",
            )
        start = (
            _utc(event.start_occurred_at_utc, field="lifecycle.start")
            if event.start_occurred_at_utc is not None
            else None
        )
        end = (
            _utc(event.end_occurred_at_utc, field="lifecycle.end")
            if event.end_occurred_at_utc is not None
            else None
        )
        if start is not None and end is not None and end < start:
            raise P3GovernanceError(
                "FAIL_CLOSED_P3_EXACT_IDENTITY_REQUIRED",
                "lifecycle interval inverted",
            )
        if (start is not None and start > as_of) or (end is not None and end > as_of):
            raise P3GovernanceError(
                "FAIL_CLOSED_P3_LIFECYCLE_FUTURE_INFORMATION",
                event.lifecycle_event_id,
            )
        first_time = occurred[0]
        last_time = occurred[-1]
        if (
            (start is not None and first_time < start <= last_time)
            or (end is not None and first_time < end <= last_time)
        ):
            raise P3GovernanceError(
                "FAIL_CLOSED_P3_CONFIGURATION_SEGMENT_REQUIRED",
                f"lifecycle boundary {event.lifecycle_event_id}",
            )
        if (start is None or start <= first_time) and (end is None or end <= first_time):
            marker_ids.append(event.lifecycle_event_id)
    marker_ids.sort()
    estimate_ids = tuple(item.estimate_id for item in ordered)
    snapshot_ids = tuple(item.configuration_snapshot_id for item in ordered)
    manifest = {
        "authority_sha256": p.authority_sha256,
        "profile_sha256": p.profile_sha256,
        "snapshot_type": p.segment_snapshot_type,
        "segment_snapshot_id": segment_snapshot_id,
        "aircraft_id": first.aircraft_id,
        "aircraft_model_id": first.aircraft_model_id,
        "configuration_key": first.configuration_key,
        "configuration_snapshot_ids": list(snapshot_ids),
        "lifecycle_event_ids": marker_ids,
        "session_order_scope_id": first.session_order_scope_id,
        "first_session_order": ordered[0].session_order,
        "last_session_order": ordered[-1].session_order,
        "capability_type": first.capability_type,
        "metric_semantic_id": first.metric_semantic_id,
        "metric_semantic_version": first.metric_semantic_version,
        "reference_condition_id": first.reference_condition_id,
        "unit": first.unit,
        "estimate_ids": list(estimate_ids),
        "knowledge_cutoff_utc": as_of_utc,
    }
    return P3LifecycleSegment(
        segment_snapshot_id=segment_snapshot_id,
        snapshot_type=p.segment_snapshot_type,
        frozen=True,
        aircraft_id=first.aircraft_id,
        aircraft_model_id=first.aircraft_model_id,
        configuration_key=first.configuration_key,
        configuration_snapshot_ids=snapshot_ids,
        lifecycle_event_ids=tuple(marker_ids),
        session_order_scope_id=first.session_order_scope_id,
        first_session_order=ordered[0].session_order,
        last_session_order=ordered[-1].session_order,
        as_of_session_order=ordered[-1].session_order,
        capability_type=first.capability_type,
        metric_semantic_id=first.metric_semantic_id,
        metric_semantic_version=first.metric_semantic_version,
        reference_condition_id=first.reference_condition_id,
        unit=first.unit,
        observation_count=len(ordered),
        episode_count=len({item.episode_id for item in ordered}),
        independent_aircraft_count=1,
        effective_evidence_count=float(len(ordered)),
        knowledge_cutoff_utc=as_of_utc,
        estimate_ids=estimate_ids,
        segment_hash=_canonical_hash(manifest),
    )


def build_p3_validation_snapshot(
    *,
    validation_snapshot_id: str,
    training_dataset_snapshot_id: str,
    segment: P3LifecycleSegment,
    estimates: Sequence[P3AdjustedEstimateInput],
    as_of_utc: str,
    policy: P3AuthorityPolicy | None = None,
) -> P3ModelValidationSnapshot:
    p = policy or P3AuthorityPolicy.from_canonical()
    _uuid(validation_snapshot_id, field="validation_snapshot_id", policy=p)
    _uuid(
        training_dataset_snapshot_id,
        field="training_dataset_snapshot_id",
        policy=p,
    )
    if segment.snapshot_type != p.segment_snapshot_type or not segment.frozen:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_VALIDATION_SNAPSHOT_REQUIRED",
            "segment snapshot must be frozen",
        )
    ordered = tuple(
        sorted(
            (
                project_p2_adjusted_estimate(item, as_of_utc=as_of_utc, policy=p)
                for item in estimates
            ),
            key=lambda item: (item.session_order, item.estimate_id),
        )
    )
    if tuple(item.estimate_id for item in ordered) != segment.estimate_ids:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_VALIDATION_SNAPSHOT_REQUIRED",
            "validation inputs must equal exact segment membership",
        )
    if len(ordered) < p.min_total_validation_points:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_VALIDATION_SNAPSHOT_REQUIRED",
            "minimum total eligible points not met",
        )
    validation = ordered[-1:]
    training_all = ordered[:-1]
    training = training_all[-p.training_prefix_max_points :]
    if len(training) < p.training_prefix_min_points:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_VALIDATION_SNAPSHOT_REQUIRED",
            "training prefix minimum not met",
        )
    training_ids = tuple(item.estimate_id for item in training)
    validation_ids = tuple(item.estimate_id for item in validation)
    if set(training_ids) & set(validation_ids):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_TRAINING_VALIDATION_LEAKAGE",
            "estimate identity overlap",
        )
    if {item.episode_id for item in training} & {
        item.episode_id for item in validation
    }:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_TRAINING_VALIDATION_LEAKAGE",
            "episode overlap",
        )
    as_of = _utc(as_of_utc, field="as_of_utc")
    if any(
        _utc(item.knowledge_time_utc, field="knowledge_time_utc") > as_of
        for item in ordered
    ):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_LIFECYCLE_FUTURE_INFORMATION",
            "validation input after as_of",
        )
    manifest = {
        "authority_sha256": p.authority_sha256,
        "profile_sha256": p.profile_sha256,
        "snapshot_type": p.validation_snapshot_type,
        "validation_snapshot_id": validation_snapshot_id,
        "training_dataset_snapshot_id": training_dataset_snapshot_id,
        "segment_snapshot_id": segment.segment_snapshot_id,
        "segment_hash": segment.segment_hash,
        "training_estimate_ids": list(training_ids),
        "validation_estimate_ids": list(validation_ids),
        "as_of_utc": as_of_utc,
    }
    return P3ModelValidationSnapshot(
        validation_snapshot_id=validation_snapshot_id,
        snapshot_type=p.validation_snapshot_type,
        frozen=True,
        training_dataset_snapshot_id=training_dataset_snapshot_id,
        profile_id=p.profile_id,
        profile_version=p.profile_version,
        aircraft_id=segment.aircraft_id,
        capability_type=segment.capability_type,
        segment_snapshot_id=segment.segment_snapshot_id,
        training_estimate_ids=training_ids,
        validation_estimate_ids=validation_ids,
        independent_aircraft_count=1,
        observation_count=len(training) + len(validation),
        effective_evidence_count=float(len(training) + len(validation)),
        claim_evidence_tier=p.default_claim_level,
        as_of_utc=as_of_utc,
        data_hash=_canonical_hash(manifest),
    )


def validate_managed_object(
    value: P3ManagedObject,
    *,
    expected_uri: str,
    expected_hash: str,
    policy: P3AuthorityPolicy | None = None,
) -> P3ManagedObject:
    p = policy or P3AuthorityPolicy.from_canonical()
    _uuid(value.object_ref_id, field="object_ref_id", policy=p)
    _hash64(value.artifact_sha256, field="artifact_sha256")
    _hash64(expected_hash, field="expected_hash")
    _exact(value.managed_uri, field="managed_uri", policy=p)
    upper_uri = (
        value.managed_uri.upper()
        .replace("://", "/")
        .replace(":", "/")
        .replace("?", "/")
        .replace("#", "/")
        .replace("=", "/")
    )
    uri_tokens = {token for token in upper_uri.split("/") if token}
    if value.managed_uri.startswith("file://") or (
        uri_tokens & p.forbidden_pointer_tokens
    ):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_MANAGED_OBJECT_REQUIRED",
            value.managed_uri,
        )
    if (
        value.managed_uri != expected_uri
        or not value.sealed
        or value.gc_state != p.required_object_gc_state
        or value.deleted_at is not None
    ):
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_MANAGED_OBJECT_REQUIRED",
            value.managed_uri,
        )
    if value.artifact_sha256 != expected_hash:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_MANAGED_OBJECT_HASH_MISMATCH",
            value.object_ref_id,
        )
    return value


def assert_p1_p2_immutable(original: object, proposed: object) -> None:
    if original != proposed:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_P1_P2_MUTATION_FORBIDDEN",
            "P3 may not overwrite P1/P2 evidence",
        )


def assert_p3_claim_level(
    claim_level: str,
    *,
    independent_evidence_set_id: str | None = None,
    policy: P3AuthorityPolicy | None = None,
) -> None:
    p = policy or P3AuthorityPolicy.from_canonical()
    if claim_level == p.default_claim_level:
        if independent_evidence_set_id is not None:
            _uuid(
                independent_evidence_set_id,
                field="independent_evidence_set_id",
                policy=p,
            )
        return
    if claim_level == p.stronger_claim_level:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_CLAIM_EVIDENCE_REQUIRED",
            "profile v1 does not authorize stronger intrinsic wording",
        )
    raise P3GovernanceError(
        "FAIL_CLOSED_P3_CLAIM_EVIDENCE_REQUIRED",
        claim_level,
    )


def assert_capability_claim_allowed(
    phase: str,
    *,
    evidence: P3AdmissionEvidence | None = None,
    policy: P3AuthorityPolicy | None = None,
) -> None:
    if phase in {"P1", "P2"}:
        return
    p = policy or P3AuthorityPolicy.from_canonical()
    if phase in {"P4", "P5", "P6"}:
        raise P3GovernanceError("FAIL_CLOSED_P4_P6_NOT_ADMITTED", phase)
    if phase != "P3" or evidence is None:
        raise P3GovernanceError("FAIL_CLOSED_P3_NOT_ADMITTED", phase)
    revision_ok = (
        len(evidence.source_revision) == 40
        and all(ch in "0123456789abcdef" for ch in evidence.source_revision)
    )
    admitted = (
        revision_ok
        and evidence.event_name == "push"
        and evidence.git_ref == "refs/heads/main"
        and evidence.protected_main
        and evidence.m7_exit_decision == "GO"
        and evidence.run_conclusion == "success"
        and evidence.required_jobs_success == p.required_exit_jobs
        and evidence.required_jobs_total == p.required_exit_jobs
        and evidence.p4_p6_inactive
    )
    if not admitted:
        raise P3GovernanceError(
            "FAIL_CLOSED_P3_NOT_ADMITTED",
            "protected-main M7 Exit GO evidence is incomplete",
        )
