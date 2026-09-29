"""M6 Batch 1 governed P2 authority, immutable-input and leakage substrate."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from tpaa_canonical import ArtifactExpectation, CanonicalArtifactLoader

_AUTHORITY_ID = "P2_ATTRIBUTION_NORMALIZATION_AUTHORITY"


class P2GovernanceError(RuntimeError):
    """Deterministic fail-closed P2 governance error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _object(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise P2GovernanceError("FAIL_CLOSED_P2_AUTHORITY_REQUIRED", field)
    return cast(dict[str, object], value)


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise P2GovernanceError("FAIL_CLOSED_P2_AUTHORITY_REQUIRED", field)
    return value


def _strings(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise P2GovernanceError("FAIL_CLOSED_P2_AUTHORITY_REQUIRED", field)
    return tuple(cast(list[str], value))


@dataclass(frozen=True)
class P2AuthorityPolicy:
    authority_sha256: str
    forbidden_pointer_tokens: frozenset[str]
    required_release_status: str
    required_eligibility_status: str
    feature_artifact_kind: str
    reference_artifact_kind: str
    cohort_snapshot_type: str
    attribution_artifact_kind: str
    minimum_comparability_dimensions: tuple[str, ...]
    identifiability_statuses: tuple[str, ...]
    not_identifiable_reason_codes: frozenset[str]
    required_exit_jobs: int

    @classmethod
    def from_canonical(
        cls,
        loader: CanonicalArtifactLoader | None = None,
    ) -> P2AuthorityPolicy:
        canonical = loader or CanonicalArtifactLoader()
        artifact = canonical.load(
            _AUTHORITY_ID,
            expectation=ArtifactExpectation(
                version="1.0.0",
                schema_version="1.6.0",
                required_top_level_keys=(
                    "exact_identity_rules",
                    "p1_eligibility_contract",
                    "feature_spec_contract",
                    "reference_condition_contract",
                    "cohort_specification_contract",
                    "attribution_spec_contract",
                    "identifiability_contract",
                    "knowledge_time_contract",
                    "release_replay_contract",
                    "admission_guard",
                    "dto_contracts",
                ),
            ),
        )
        payload = dict(artifact.payload)
        exact = _object(payload["exact_identity_rules"], field="exact_identity_rules")
        p1 = _object(payload["p1_eligibility_contract"], field="p1_eligibility_contract")
        feature = _object(payload["feature_spec_contract"], field="feature_spec_contract")
        reference = _object(
            payload["reference_condition_contract"],
            field="reference_condition_contract",
        )
        cohort = _object(
            payload["cohort_specification_contract"],
            field="cohort_specification_contract",
        )
        attribution = _object(
            payload["attribution_spec_contract"],
            field="attribution_spec_contract",
        )
        identifiable = _object(
            payload["identifiability_contract"],
            field="identifiability_contract",
        )
        guard = _object(payload["admission_guard"], field="admission_guard")
        jobs = guard.get("required_job_count")
        if not isinstance(jobs, int) or isinstance(jobs, bool) or jobs <= 0:
            raise P2GovernanceError(
                "FAIL_CLOSED_P2_AUTHORITY_REQUIRED",
                "admission_guard.required_job_count",
            )
        return cls(
            authority_sha256=artifact.sha256,
            forbidden_pointer_tokens=frozenset(
                _strings(
                    exact.get("forbidden_pointer_tokens"),
                    field="forbidden_pointer_tokens",
                )
            ),
            required_release_status=_text(
                p1.get("required_release_status"),
                field="required_release_status",
            ),
            required_eligibility_status=_text(
                p1.get("required_observation_eligibility_status"),
                field="required_observation_eligibility_status",
            ),
            feature_artifact_kind=_text(
                feature.get("artifact_kind"),
                field="feature_spec_contract.artifact_kind",
            ),
            reference_artifact_kind=_text(
                reference.get("artifact_kind"),
                field="reference_condition_contract.artifact_kind",
            ),
            cohort_snapshot_type=_text(
                cohort.get("snapshot_type"),
                field="cohort_specification_contract.snapshot_type",
            ),
            attribution_artifact_kind=_text(
                attribution.get("artifact_kind"),
                field="attribution_spec_contract.artifact_kind",
            ),
            minimum_comparability_dimensions=_strings(
                cohort.get("minimum_comparability_dimensions"),
                field="minimum_comparability_dimensions",
            ),
            identifiability_statuses=_strings(
                identifiable.get("statuses"),
                field="identifiability_contract.statuses",
            ),
            not_identifiable_reason_codes=frozenset(
                _strings(
                    identifiable.get("reason_codes"),
                    field="identifiability_contract.reason_codes",
                )
            ),
            required_exit_jobs=jobs,
        )


def _exact(value: str, *, field: str, policy: P2AuthorityPolicy) -> str:
    if not value.strip():
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_EXACT_IDENTITY_REQUIRED",
            field,
        )
    if value.strip().upper() in policy.forbidden_pointer_tokens:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_CURRENT_LATEST_FORBIDDEN",
            f"{field}={value!r}",
        )
    return value


def _uuid(value: str, *, field: str, policy: P2AuthorityPolicy) -> str:
    _exact(value, field=field, policy=policy)
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        ) from exc
    if str(parsed) != value or parsed.int == 0:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        )
    return value


def _hash64(value: str, *, field: str) -> str:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        )
    return value


def _utc(value: str, *, field: str) -> datetime:
    if not value.endswith("Z") or "T" not in value:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        )
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        ) from exc
    return parsed


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
class P1ObservationInput:
    observation_id: str
    release_id: str
    release_status: str
    release_sealed: bool
    episode_id: str
    subject_entity_id: str
    aircraft_id: str
    aircraft_model_id: str
    aircraft_configuration_snapshot_id: str | None
    context_id: str
    capability_type: str
    metric_semantic_id: str
    metric_semantic_version: str
    comparison_key_hash: str
    evidence_set_id: str
    observed_value: float | None
    unit: str
    coverage: float
    confidence: float
    eligibility_status: str
    knowledge_time_utc: str

    def projection(self) -> dict[str, object]:
        return {
            "observation_id": self.observation_id,
            "release_id": self.release_id,
            "episode_id": self.episode_id,
            "subject_entity_id": self.subject_entity_id,
            "aircraft_id": self.aircraft_id,
            "aircraft_model_id": self.aircraft_model_id,
            "aircraft_configuration_snapshot_id": (
                self.aircraft_configuration_snapshot_id
            ),
            "context_id": self.context_id,
            "capability_type": self.capability_type,
            "metric_semantic_id": self.metric_semantic_id,
            "metric_semantic_version": self.metric_semantic_version,
            "comparison_key_hash": self.comparison_key_hash,
            "evidence_set_id": self.evidence_set_id,
            "observed_value": self.observed_value,
            "unit": self.unit,
            "coverage": self.coverage,
            "confidence": self.confidence,
            "knowledge_time_utc": self.knowledge_time_utc,
        }


@dataclass(frozen=True)
class P2ArtifactBinding:
    context_artifact_id: str
    object_ref_id: str
    artifact_kind: str
    logical_key: str
    artifact_version: str
    artifact_sha256: str
    status: str
    sealed: bool


@dataclass(frozen=True)
class P2ReferenceCondition:
    reference_condition_id: str
    binding: P2ArtifactBinding


@dataclass(frozen=True)
class P2AttributionSpec:
    attribution_spec_id: str
    attribution_spec_version: str
    model_plugin: str
    model_plugin_version: str
    uncertainty_method: str
    uncertainty_level: str
    binding: P2ArtifactBinding


@dataclass(frozen=True)
class P2CohortSnapshot:
    dataset_snapshot_id: str
    snapshot_type: str
    data_hash: str
    schema_version: str
    frozen: bool
    cohort_spec_id: str
    cohort_spec_version: str
    comparability_dimensions: tuple[tuple[str, str], ...]
    knowledge_cutoff_utc: str
    raw_record_count: int
    observation_count: int
    independent_subject_count: int
    effective_evidence_count: float
    observation_ids: tuple[str, ...]
    episode_ids: tuple[str, ...]
    subject_ids: tuple[str, ...]


@dataclass(frozen=True)
class P2InputBundle:
    target: P1ObservationInput
    feature_spec: P2ArtifactBinding
    reference_condition: P2ReferenceCondition
    cohort: P2CohortSnapshot
    attribution_spec: P2AttributionSpec
    as_of_utc: str
    input_hash: str


@dataclass(frozen=True)
class P2AdmissionEvidence:
    source_revision: str
    event_name: str
    git_ref: str
    protected_main: bool
    m6_exit_decision: str
    run_conclusion: str
    required_jobs_success: int
    required_jobs_total: int
    p3_p6_inactive: bool


@dataclass(frozen=True)
class P2GovernedResult:
    status: str
    adjusted_value: float | None
    reason_code: str | None


def project_p1_observation(
    value: P1ObservationInput,
    *,
    policy: P2AuthorityPolicy | None = None,
) -> P1ObservationInput:
    p = policy or P2AuthorityPolicy.from_canonical()
    for field, identity in (
        ("observation_id", value.observation_id),
        ("release_id", value.release_id),
        ("episode_id", value.episode_id),
        ("subject_entity_id", value.subject_entity_id),
        ("aircraft_id", value.aircraft_id),
        ("aircraft_model_id", value.aircraft_model_id),
        ("context_id", value.context_id),
        ("evidence_set_id", value.evidence_set_id),
    ):
        _uuid(identity, field=field, policy=p)
    if value.aircraft_configuration_snapshot_id is not None:
        _uuid(
            value.aircraft_configuration_snapshot_id,
            field="aircraft_configuration_snapshot_id",
            policy=p,
        )
    for field, identity in (
        ("capability_type", value.capability_type),
        ("metric_semantic_id", value.metric_semantic_id),
        ("metric_semantic_version", value.metric_semantic_version),
        ("unit", value.unit),
    ):
        _exact(identity, field=field, policy=p)
    _hash64(value.comparison_key_hash, field="comparison_key_hash")
    _utc(value.knowledge_time_utc, field="knowledge_time_utc")
    if value.release_status != p.required_release_status or not value.release_sealed:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_PUBLISHED_P1_REQUIRED",
            value.release_id,
        )
    if value.eligibility_status != p.required_eligibility_status:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_PUBLISHED_P1_REQUIRED",
            f"eligibility_status={value.eligibility_status!r}",
        )
    if not 0.0 <= value.coverage <= 1.0 or not 0.0 <= value.confidence <= 1.0:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_PUBLISHED_P1_REQUIRED",
            "coverage/confidence outside [0,1]",
        )
    if value.observed_value is not None and not math.isfinite(value.observed_value):
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_PUBLISHED_P1_REQUIRED",
            "observed_value must be finite or null",
        )
    return value


def _validate_binding(
    binding: P2ArtifactBinding,
    *,
    expected_kind: str,
    error_code: str,
    policy: P2AuthorityPolicy,
) -> P2ArtifactBinding:
    _uuid(binding.context_artifact_id, field="context_artifact_id", policy=policy)
    _uuid(binding.object_ref_id, field="object_ref_id", policy=policy)
    _exact(binding.logical_key, field="logical_key", policy=policy)
    _exact(binding.artifact_version, field="artifact_version", policy=policy)
    _hash64(binding.artifact_sha256, field="artifact_sha256")
    if (
        binding.artifact_kind != expected_kind
        or binding.status != "ACTIVE"
        or not binding.sealed
    ):
        raise P2GovernanceError(error_code, binding.logical_key)
    return binding


def validate_reference_condition(
    value: P2ReferenceCondition,
    *,
    policy: P2AuthorityPolicy | None = None,
) -> P2ReferenceCondition:
    p = policy or P2AuthorityPolicy.from_canonical()
    _uuid(
        value.reference_condition_id,
        field="reference_condition_id",
        policy=p,
    )
    _validate_binding(
        value.binding,
        expected_kind=p.reference_artifact_kind,
        error_code="FAIL_CLOSED_P2_REFERENCE_CONDITION_REQUIRED",
        policy=p,
    )
    if value.reference_condition_id != value.binding.context_artifact_id:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_REFERENCE_CONDITION_REQUIRED",
            "reference_condition_id must equal context_artifact_id",
        )
    return value


def validate_attribution_spec(
    value: P2AttributionSpec,
    *,
    policy: P2AuthorityPolicy | None = None,
) -> P2AttributionSpec:
    p = policy or P2AuthorityPolicy.from_canonical()
    _validate_binding(
        value.binding,
        expected_kind=p.attribution_artifact_kind,
        error_code="FAIL_CLOSED_P2_ATTRIBUTION_SPEC_REQUIRED",
        policy=p,
    )
    for field, identity in (
        ("attribution_spec_id", value.attribution_spec_id),
        ("attribution_spec_version", value.attribution_spec_version),
        ("model_plugin", value.model_plugin),
        ("model_plugin_version", value.model_plugin_version),
        ("uncertainty_method", value.uncertainty_method),
        ("uncertainty_level", value.uncertainty_level),
    ):
        _exact(identity, field=field, policy=p)
    if (
        value.attribution_spec_id != value.binding.logical_key
        or value.attribution_spec_version != value.binding.artifact_version
    ):
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_ATTRIBUTION_SPEC_REQUIRED",
            "spec identity/version must match sealed artifact binding",
        )
    return value


def validate_cohort_snapshot(
    value: P2CohortSnapshot,
    *,
    policy: P2AuthorityPolicy | None = None,
) -> P2CohortSnapshot:
    p = policy or P2AuthorityPolicy.from_canonical()
    _uuid(value.dataset_snapshot_id, field="dataset_snapshot_id", policy=p)
    _hash64(value.data_hash, field="data_hash")
    _exact(value.schema_version, field="schema_version", policy=p)
    _exact(value.cohort_spec_id, field="cohort_spec_id", policy=p)
    _exact(value.cohort_spec_version, field="cohort_spec_version", policy=p)
    _utc(value.knowledge_cutoff_utc, field="knowledge_cutoff_utc")
    if value.snapshot_type != p.cohort_snapshot_type or not value.frozen:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_COHORT_SNAPSHOT_REQUIRED",
            value.dataset_snapshot_id,
        )
    dimensions = dict(value.comparability_dimensions)
    if len(dimensions) != len(value.comparability_dimensions):
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_COMPARABILITY_MISMATCH",
            "duplicate comparability dimensions",
        )
    for name in p.minimum_comparability_dimensions:
        if name not in dimensions:
            raise P2GovernanceError(
                "FAIL_CLOSED_P2_COMPARABILITY_MISMATCH",
                f"missing dimension {name}",
            )
        _exact(dimensions[name], field=f"comparability.{name}", policy=p)
    if value.raw_record_count < value.observation_count:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_EVIDENCE_INDEPENDENCE",
            "raw_record_count < observation_count",
        )
    if value.observation_count != len(value.observation_ids):
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_EVIDENCE_INDEPENDENCE",
            "observation_count mismatch",
        )
    unique_subjects = len(set(value.subject_ids))
    if value.independent_subject_count != unique_subjects:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_EVIDENCE_INDEPENDENCE",
            "independent_subject_count mismatch",
        )
    if not 0.0 <= value.effective_evidence_count <= float(value.observation_count):
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_EVIDENCE_INDEPENDENCE",
            "effective_evidence_count out of range",
        )
    for identity in value.observation_ids:
        _uuid(identity, field="cohort.observation_id", policy=p)
    for identity in value.episode_ids:
        _uuid(identity, field="cohort.episode_id", policy=p)
    for identity in value.subject_ids:
        _uuid(identity, field="cohort.subject_id", policy=p)
    return value


def build_p2_input_bundle(
    *,
    target: P1ObservationInput,
    feature_spec: P2ArtifactBinding,
    reference_condition: P2ReferenceCondition,
    cohort: P2CohortSnapshot,
    attribution_spec: P2AttributionSpec,
    as_of_utc: str,
    policy: P2AuthorityPolicy | None = None,
) -> P2InputBundle:
    p = policy or P2AuthorityPolicy.from_canonical()
    target = project_p1_observation(target, policy=p)
    feature_spec = _validate_binding(
        feature_spec,
        expected_kind=p.feature_artifact_kind,
        error_code="FAIL_CLOSED_P2_FEATURE_SPEC_REQUIRED",
        policy=p,
    )
    reference_condition = validate_reference_condition(reference_condition, policy=p)
    cohort = validate_cohort_snapshot(cohort, policy=p)
    attribution_spec = validate_attribution_spec(attribution_spec, policy=p)
    as_of = _utc(as_of_utc, field="as_of_utc")
    if _utc(target.knowledge_time_utc, field="target.knowledge_time_utc") > as_of:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_FUTURE_INFORMATION",
            "target observation is not known by as_of_utc",
        )
    if _utc(cohort.knowledge_cutoff_utc, field="cohort.knowledge_cutoff_utc") > as_of:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_FUTURE_INFORMATION",
            "cohort snapshot contains information after as_of_utc",
        )
    if target.observation_id in cohort.observation_ids:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_SAME_EPISODE_LEAKAGE",
            "target observation is present in cohort",
        )
    if target.episode_id in cohort.episode_ids:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_SAME_EPISODE_LEAKAGE",
            "target episode is present in cohort",
        )
    target_dimensions = {
        "capability_type": target.capability_type,
        "metric_semantic_id": target.metric_semantic_id,
        "metric_semantic_version": target.metric_semantic_version,
        "unit": target.unit,
        "aircraft_model_id": target.aircraft_model_id,
        "comparison_key_hash": target.comparison_key_hash,
    }
    cohort_dimensions = dict(cohort.comparability_dimensions)
    for name in p.minimum_comparability_dimensions:
        if cohort_dimensions[name] != target_dimensions[name]:
            raise P2GovernanceError(
                "FAIL_CLOSED_P2_COMPARABILITY_MISMATCH",
                name,
            )
    manifest = {
        "authority_sha256": p.authority_sha256,
        "target": target.projection(),
        "feature_spec": {
            "context_artifact_id": feature_spec.context_artifact_id,
            "logical_key": feature_spec.logical_key,
            "artifact_version": feature_spec.artifact_version,
            "artifact_sha256": feature_spec.artifact_sha256,
        },
        "reference_condition": {
            "reference_condition_id": reference_condition.reference_condition_id,
            "artifact_sha256": reference_condition.binding.artifact_sha256,
        },
        "cohort": {
            "dataset_snapshot_id": cohort.dataset_snapshot_id,
            "data_hash": cohort.data_hash,
            "cohort_spec_id": cohort.cohort_spec_id,
            "cohort_spec_version": cohort.cohort_spec_version,
            "knowledge_cutoff_utc": cohort.knowledge_cutoff_utc,
        },
        "attribution_spec": {
            "attribution_spec_id": attribution_spec.attribution_spec_id,
            "attribution_spec_version": attribution_spec.attribution_spec_version,
            "model_plugin": attribution_spec.model_plugin,
            "model_plugin_version": attribution_spec.model_plugin_version,
            "artifact_sha256": attribution_spec.binding.artifact_sha256,
        },
        "as_of_utc": as_of_utc,
    }
    return P2InputBundle(
        target=target,
        feature_spec=feature_spec,
        reference_condition=reference_condition,
        cohort=cohort,
        attribution_spec=attribution_spec,
        as_of_utc=as_of_utc,
        input_hash=_canonical_hash(manifest),
    )


def assert_p1_observed_value_immutable(original: object, proposed: object) -> None:
    if original != proposed:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_P1_MUTATION_FORBIDDEN",
            "P2 may not overwrite the P1 observed value",
        )


def validate_factor_effect_semantics(
    *,
    semantics: str,
    causal_evidence_set_id: str | None,
    policy: P2AuthorityPolicy | None = None,
) -> None:
    p = policy or P2AuthorityPolicy.from_canonical()
    if semantics == "CAUSAL":
        if causal_evidence_set_id is None:
            raise P2GovernanceError(
                "FAIL_CLOSED_P2_CAUSAL_EVIDENCE_REQUIRED",
                "causal label requires independent causal evidence",
            )
        _uuid(causal_evidence_set_id, field="causal_evidence_set_id", policy=p)
    elif semantics != "MODEL_CONDITIONED_ASSOCIATION":
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_CAUSAL_EVIDENCE_REQUIRED",
            f"unsupported factor-effect semantics {semantics!r}",
        )


def governed_result(
    *,
    status: str,
    adjusted_value: float | None,
    reason_code: str | None,
    policy: P2AuthorityPolicy | None = None,
) -> P2GovernedResult:
    p = policy or P2AuthorityPolicy.from_canonical()
    if status not in p.identifiability_statuses:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_AUTHORITY_REQUIRED",
            f"unknown identifiability status {status!r}",
        )
    if status == "NOT_IDENTIFIABLE":
        if adjusted_value is not None or reason_code not in p.not_identifiable_reason_codes:
            raise P2GovernanceError(
                "FAIL_CLOSED_P2_AUTHORITY_REQUIRED",
                "NOT_IDENTIFIABLE requires null value and governed reason code",
            )
    else:
        if adjusted_value is None or not math.isfinite(adjusted_value):
            raise P2GovernanceError(
                "FAIL_CLOSED_P2_AUTHORITY_REQUIRED",
                "IDENTIFIABLE requires a finite adjusted value",
            )
        if reason_code is not None:
            raise P2GovernanceError(
                "FAIL_CLOSED_P2_AUTHORITY_REQUIRED",
                "IDENTIFIABLE does not carry a NOT_IDENTIFIABLE reason",
            )
    return P2GovernedResult(
        status=status,
        adjusted_value=adjusted_value,
        reason_code=reason_code,
    )


def assert_capability_claim_allowed(
    phase: str,
    *,
    evidence: P2AdmissionEvidence | None = None,
    policy: P2AuthorityPolicy | None = None,
) -> None:
    if phase == "P1":
        return
    p = policy or P2AuthorityPolicy.from_canonical()
    if phase in {"P3", "P4", "P5", "P6"}:
        raise P2GovernanceError("FAIL_CLOSED_P3_P6_NOT_ADMITTED", phase)
    if phase != "P2" or evidence is None:
        raise P2GovernanceError("FAIL_CLOSED_P2_NOT_ADMITTED", phase)
    revision_ok = (
        len(evidence.source_revision) == 40
        and all(ch in "0123456789abcdef" for ch in evidence.source_revision)
    )
    admitted = (
        revision_ok
        and evidence.event_name == "push"
        and evidence.git_ref == "refs/heads/main"
        and evidence.protected_main
        and evidence.m6_exit_decision == "GO"
        and evidence.run_conclusion == "success"
        and evidence.required_jobs_success == p.required_exit_jobs
        and evidence.required_jobs_total == p.required_exit_jobs
        and evidence.p3_p6_inactive
    )
    if not admitted:
        raise P2GovernanceError(
            "FAIL_CLOSED_P2_NOT_ADMITTED",
            "protected-main M6 Exit GO evidence is incomplete",
        )
