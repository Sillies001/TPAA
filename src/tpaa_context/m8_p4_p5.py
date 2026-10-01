"""M8 Batch 1 shared P4/P5 governance, admission and role/privacy substrate."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from tpaa_canonical import (
    ArtifactExpectation,
    CanonicalArtifactError,
    CanonicalArtifactLoader,
)

_AUTHORITY_ID = "P4_P5_TRAINING_ASSESSMENT_AUTHORITY"
_ROLE_PROFILE_ID = "P4_P5_ROLE_PRIVACY_PROFILE"


class M8GovernanceError(RuntimeError):
    """Deterministic fail-closed P4/P5 governance error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _object(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise M8GovernanceError("FAIL_CLOSED_P4_P5_AUTHORITY_REQUIRED", field)
    return cast(dict[str, object], value)


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise M8GovernanceError("FAIL_CLOSED_P4_P5_AUTHORITY_REQUIRED", field)
    return value


def _strings(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise M8GovernanceError("FAIL_CLOSED_P4_P5_AUTHORITY_REQUIRED", field)
    return tuple(cast(list[str], value))


def _bool(value: object, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise M8GovernanceError("FAIL_CLOSED_P4_P5_AUTHORITY_REQUIRED", field)
    return value


@dataclass(frozen=True)
class M8RoleRule:
    role: str
    read_scope: str
    direct_actor_id: bool | str
    annotation_body: bool | str
    annotation_write: bool
    approval_write: bool
    audit_read: bool | str
    unrestricted_export: bool | str


@dataclass(frozen=True)
class M8AuthorityPolicy:
    authority_sha256: str
    role_profile_sha256: str
    forbidden_pointer_tokens: frozenset[str]
    role_profile_id: str
    role_profile_version: str
    role_artifact_kind: str
    role_binding_role: str
    role_logical_key: str
    role_schema_version: str
    required_role_status: str
    subject_key_prefix: str
    subject_key_input_template: str
    role_rules: tuple[M8RoleRule, ...]
    availability_states: tuple[str, ...]
    approved_evidence_families: tuple[str, ...]
    required_exit_jobs: int
    required_exit_event: str
    required_exit_ref: str
    required_exit_decision: str
    no_profile_behavior: str
    approval_states: tuple[str, ...]
    approval_transitions: tuple[str, ...]
    approval_audit_action_p4: str
    correction_after_terminal_creates_new_draft_revision: bool
    annotation_lifecycle_transition: str
    annotation_physical_delete_forbidden: bool

    @classmethod
    def from_canonical(
        cls,
        loader: CanonicalArtifactLoader | None = None,
    ) -> M8AuthorityPolicy:
        canonical = loader or CanonicalArtifactLoader()
        try:
            authority = canonical.load(
                _AUTHORITY_ID,
                expectation=ArtifactExpectation(
                    version="1.0.0",
                    schema_version="1.6.0",
                    required_top_level_keys=(
                        "exact_identity_rules",
                        "subject_context_contract",
                        "composition_contract",
                        "evidence_boundary_contract",
                        "status_contract",
                        "instructor_annotation_contract",
                        "approval_workflow_contract",
                        "role_privacy_contract",
                        "aggregation_contract",
                        "admission_guard",
                        "dto_contracts",
                    ),
                ),
            )
            role_profile = canonical.load(
                _ROLE_PROFILE_ID,
                expectation=ArtifactExpectation(
                    version="1.0.0",
                    schema_version="1.6.0",
                    required_top_level_keys=(
                        "context_binding_contract",
                        "pseudonymization_contract",
                        "role_matrix",
                        "projection_contract",
                        "write_authorization_contract",
                        "forbidden_fallbacks",
                    ),
                ),
            )
        except (CanonicalArtifactError, OSError, ValueError, KeyError) as exc:
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_AUTHORITY_REQUIRED",
                str(exc),
            ) from exc

        a = dict(authority.payload)
        rp = dict(role_profile.payload)
        source_bindings = _object(
            rp.get("source_bindings"),
            field="role_profile.source_bindings",
        )
        if source_bindings.get("p4_p5_authority_sha256") != authority.sha256:
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_AUTHORITY_REQUIRED",
                "role profile authority hash binding mismatch",
            )

        exact = _object(a.get("exact_identity_rules"), field="exact_identity_rules")
        evidence = _object(
            a.get("evidence_boundary_contract"),
            field="evidence_boundary_contract",
        )
        status = _object(a.get("status_contract"), field="status_contract")
        annotation = _object(
            a.get("instructor_annotation_contract"),
            field="instructor_annotation_contract",
        )
        approval = _object(
            a.get("approval_workflow_contract"),
            field="approval_workflow_contract",
        )
        role_contract = _object(
            a.get("role_privacy_contract"),
            field="role_privacy_contract",
        )
        aggregation = _object(
            a.get("aggregation_contract"),
            field="aggregation_contract",
        )
        guard = _object(a.get("admission_guard"), field="admission_guard")
        context_binding = _object(
            rp.get("context_binding_contract"),
            field="role_profile.context_binding_contract",
        )
        pseudonym = _object(
            rp.get("pseudonymization_contract"),
            field="role_profile.pseudonymization_contract",
        )

        rows = rp.get("role_matrix")
        if not isinstance(rows, list) or not rows:
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_AUTHORITY_REQUIRED",
                "role_profile.role_matrix",
            )
        rules: list[M8RoleRule] = []
        for index, raw in enumerate(rows):
            row = _object(raw, field=f"role_profile.role_matrix[{index}]")
            direct = row.get("direct_actor_id")
            annotation_body = row.get("annotation_body")
            audit_read = row.get("audit_read")
            unrestricted_export = row.get("unrestricted_export")
            for value, field in (
                (direct, "direct_actor_id"),
                (annotation_body, "annotation_body"),
                (audit_read, "audit_read"),
                (unrestricted_export, "unrestricted_export"),
            ):
                if not isinstance(value, (bool, str)):
                    raise M8GovernanceError(
                        "FAIL_CLOSED_P4_P5_AUTHORITY_REQUIRED",
                        f"role_matrix[{index}].{field}",
                    )
            rules.append(
                M8RoleRule(
                    role=_text(row.get("role"), field=f"role_matrix[{index}].role"),
                    read_scope=_text(
                        row.get("read_scope"),
                        field=f"role_matrix[{index}].read_scope",
                    ),
                    direct_actor_id=cast(bool | str, direct),
                    annotation_body=cast(bool | str, annotation_body),
                    annotation_write=_bool(
                        row.get("annotation_write"),
                        field=f"role_matrix[{index}].annotation_write",
                    ),
                    approval_write=_bool(
                        row.get("approval_write"),
                        field=f"role_matrix[{index}].approval_write",
                    ),
                    audit_read=cast(bool | str, audit_read),
                    unrestricted_export=cast(bool | str, unrestricted_export),
                )
            )

        jobs = guard.get("required_job_count")
        if isinstance(jobs, bool) or not isinstance(jobs, int) or jobs <= 0:
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_AUTHORITY_REQUIRED",
                "admission_guard.required_job_count",
            )

        expected_profile_id = _text(
            role_contract.get("required_profile_id"),
            field="role_privacy_contract.required_profile_id",
        )
        expected_profile_version = _text(
            role_contract.get("required_profile_version"),
            field="role_privacy_contract.required_profile_version",
        )
        if (
            expected_profile_id != _ROLE_PROFILE_ID
            or expected_profile_version != "1.0.0"
            or rp.get("profile_id") != expected_profile_id
            or rp.get("version") != expected_profile_version
        ):
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_AUTHORITY_REQUIRED",
                "authority/profile identity drift",
            )

        return cls(
            authority_sha256=authority.sha256,
            role_profile_sha256=role_profile.sha256,
            forbidden_pointer_tokens=frozenset(
                _strings(
                    exact.get("forbidden_pointer_tokens"),
                    field="exact_identity_rules.forbidden_pointer_tokens",
                )
            ),
            role_profile_id=expected_profile_id,
            role_profile_version=expected_profile_version,
            role_artifact_kind=_text(
                context_binding.get("artifact_kind"),
                field="context_binding.artifact_kind",
            ),
            role_binding_role=_text(
                context_binding.get("binding_role"),
                field="context_binding.binding_role",
            ),
            role_logical_key=_text(
                context_binding.get("logical_key"),
                field="context_binding.logical_key",
            ),
            role_schema_version=_text(
                context_binding.get("schema_version"),
                field="context_binding.schema_version",
            ),
            required_role_status=_text(
                context_binding.get("required_status"),
                field="context_binding.required_status",
            ),
            subject_key_prefix=_text(
                pseudonym.get("output_prefix"),
                field="pseudonymization.output_prefix",
            ),
            subject_key_input_template=_text(
                pseudonym.get("input_template"),
                field="pseudonymization.input_template",
            ),
            role_rules=tuple(rules),
            availability_states=_strings(
                status.get("evidence_availability_states"),
                field="status_contract.evidence_availability_states",
            ),
            approved_evidence_families=_strings(
                evidence.get("approved_evidence_families"),
                field="evidence_boundary_contract.approved_evidence_families",
            ),
            required_exit_jobs=jobs,
            required_exit_event=_text(
                guard.get("required_event"),
                field="admission_guard.required_event",
            ),
            required_exit_ref=_text(
                guard.get("required_git_ref"),
                field="admission_guard.required_git_ref",
            ),
            required_exit_decision=_text(
                guard.get("required_m8_exit_decision"),
                field="admission_guard.required_m8_exit_decision",
            ),
            no_profile_behavior=_text(
                aggregation.get("no_profile_behavior"),
                field="aggregation_contract.no_profile_behavior",
            ),
            approval_states=_strings(
                approval.get("allowed_states"),
                field="approval_workflow_contract.allowed_states",
            ),
            approval_transitions=_strings(
                approval.get("allowed_transitions"),
                field="approval_workflow_contract.allowed_transitions",
            ),
            approval_audit_action_p4=_text(
                approval.get("audit_action_p4"),
                field="approval_workflow_contract.audit_action_p4",
            ),
            correction_after_terminal_creates_new_draft_revision=_bool(
                approval.get("correction_after_terminal_creates_new_draft_revision"),
                field=(
                    "approval_workflow_contract."
                    "correction_after_terminal_creates_new_draft_revision"
                ),
            ),
            annotation_lifecycle_transition=_text(
                annotation.get("lifecycle_status_transition_allowed_only"),
                field=(
                    "instructor_annotation_contract."
                    "lifecycle_status_transition_allowed_only"
                ),
            ),
            annotation_physical_delete_forbidden=_bool(
                annotation.get("physical_delete_forbidden"),
                field="instructor_annotation_contract.physical_delete_forbidden",
            ),
        )

    def role_rule(self, role: str) -> M8RoleRule:
        for rule in self.role_rules:
            if rule.role == role:
                return rule
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_DIRECT_IDENTITY_NOT_AUTHORIZED",
            f"unknown role={role!r}",
        )


def exact_text(value: str, *, field: str, policy: M8AuthorityPolicy) -> str:
    if not isinstance(value, str) or not value.strip():
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            field,
        )
    if value.strip().upper() in policy.forbidden_pointer_tokens:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_CURRENT_LATEST_DEFAULT_FORBIDDEN",
            f"{field}={value!r}",
        )
    return value


def exact_uuid(value: str, *, field: str, policy: M8AuthorityPolicy) -> str:
    exact_text(value, field=field, policy=policy)
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        ) from exc
    if parsed.int == 0 or str(parsed) != value:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        )
    return value


def exact_hash64(value: str, *, field: str) -> str:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        )
    return value


def utc(value: str, *, field: str) -> datetime:
    if not isinstance(value, str) or "T" not in value or not value.endswith("Z"):
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        )
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        ) from exc


def canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class M8RoleModelBinding:
    context_artifact_id: str
    object_ref_id: str
    artifact_kind: str
    binding_role: str
    logical_key: str
    artifact_version: str
    schema_version: str
    artifact_sha256: str
    status: str
    sealed: bool
    effective_from_utc: str
    effective_to_utc: str | None


def validate_role_model_binding(
    binding: M8RoleModelBinding,
    *,
    as_of_utc: str,
    policy: M8AuthorityPolicy | None = None,
) -> M8RoleModelBinding:
    p = policy or M8AuthorityPolicy.from_canonical()
    exact_uuid(binding.context_artifact_id, field="context_artifact_id", policy=p)
    exact_uuid(binding.object_ref_id, field="object_ref_id", policy=p)
    exact_hash64(binding.artifact_sha256, field="artifact_sha256")
    exact_text(binding.artifact_version, field="artifact_version", policy=p)
    exact_text(binding.logical_key, field="logical_key", policy=p)
    exact_text(binding.schema_version, field="schema_version", policy=p)
    as_of = utc(as_of_utc, field="as_of_utc")
    valid_from = utc(binding.effective_from_utc, field="effective_from_utc")
    valid_to = (
        utc(binding.effective_to_utc, field="effective_to_utc")
        if binding.effective_to_utc is not None
        else None
    )
    if (
        binding.artifact_kind != p.role_artifact_kind
        or binding.binding_role != p.role_binding_role
        or binding.logical_key != p.role_logical_key
        or binding.artifact_version != p.role_profile_version
        or binding.schema_version != p.role_schema_version
        or binding.status != p.required_role_status
        or not binding.sealed
    ):
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_ROLE_MODEL_REQUIRED",
            binding.logical_key,
        )
    if valid_from > as_of or (valid_to is not None and as_of >= valid_to):
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_ROLE_MODEL_REQUIRED",
            "role model not effective at as_of",
        )
    return binding


def pseudonymous_subject_key(
    actor_id: str,
    *,
    policy: M8AuthorityPolicy | None = None,
) -> str:
    p = policy or M8AuthorityPolicy.from_canonical()
    exact_uuid(actor_id, field="actor_id", policy=p)
    marker = "<lowercase_actor_uuid>"
    if marker not in p.subject_key_input_template:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_AUTHORITY_REQUIRED",
            "pseudonymization input template",
        )
    payload = p.subject_key_input_template.replace(marker, actor_id)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{p.subject_key_prefix}{digest}"


def _identity_allowed(
    *,
    rule: M8RoleRule,
    subject_actor_id: str,
    viewer_actor_id: str | None,
    scope_match: bool,
    privileged_identity_authorized: bool,
) -> bool:
    permission = rule.direct_actor_id
    if permission is False or not scope_match:
        return False
    if permission is True:
        return True
    if permission == "OWN_ONLY":
        return viewer_actor_id == subject_actor_id
    if permission == "ASSIGNED_SCOPE_ONLY":
        return True
    if permission == "AUTHORIZED_AUDIT_SCOPE_ONLY":
        return privileged_identity_authorized
    return False


def project_direct_actor_id(
    subject_actor_id: str,
    *,
    viewer_role: str,
    viewer_actor_id: str | None,
    scope_match: bool,
    privileged_identity_authorized: bool = False,
    policy: M8AuthorityPolicy | None = None,
) -> str | None:
    p = policy or M8AuthorityPolicy.from_canonical()
    exact_uuid(subject_actor_id, field="subject_actor_id", policy=p)
    if viewer_actor_id is not None:
        exact_uuid(viewer_actor_id, field="viewer_actor_id", policy=p)
    rule = p.role_rule(viewer_role)
    if _identity_allowed(
        rule=rule,
        subject_actor_id=subject_actor_id,
        viewer_actor_id=viewer_actor_id,
        scope_match=scope_match,
        privileged_identity_authorized=privileged_identity_authorized,
    ):
        return subject_actor_id
    return None


def assert_annotation_body_allowed(
    *,
    viewer_role: str,
    scope_match: bool,
    visibility_authorized: bool,
    privileged_audit_authorized: bool = False,
    policy: M8AuthorityPolicy | None = None,
) -> None:
    p = policy or M8AuthorityPolicy.from_canonical()
    rule = p.role_rule(viewer_role)
    permission = rule.annotation_body
    allowed = False
    if scope_match and visibility_authorized:
        if permission is True:
            allowed = True
        elif permission == "ONLY_IF_VISIBILITY_ALSO_AUTHORIZES":
            allowed = True
        elif permission == "AUTHORIZED_AUDIT_SCOPE_AND_VISIBILITY_ONLY":
            allowed = privileged_audit_authorized
    if not allowed:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_DIRECT_IDENTITY_NOT_AUTHORIZED",
            "annotation body projection denied",
        )


def assert_write_allowed(
    action: str,
    *,
    viewer_role: str,
    scope_match: bool,
    policy: M8AuthorityPolicy | None = None,
) -> None:
    p = policy or M8AuthorityPolicy.from_canonical()
    rule = p.role_rule(viewer_role)
    if not scope_match:
        allowed = False
    elif action == "ANNOTATION":
        allowed = rule.annotation_write
    elif action == "APPROVAL":
        allowed = rule.approval_write
    else:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_APPROVAL_TRANSITION_INVALID",
            f"unknown action={action!r}",
        )
    if not allowed:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_APPROVAL_NOT_AUTHORIZED",
            f"{viewer_role}:{action}",
        )


def validate_availability_numeric(
    *,
    status: str,
    numeric_value: float | int | None,
    policy: M8AuthorityPolicy | None = None,
) -> None:
    p = policy or M8AuthorityPolicy.from_canonical()
    if status not in p.availability_states:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            f"availability_status={status!r}",
        )
    if status != "AVAILABLE" and numeric_value is not None:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_UNAVAILABLE_ZERO_COERCION",
            f"status={status} numeric_value={numeric_value!r}",
        )
    if numeric_value is not None:
        if isinstance(numeric_value, bool) or not isinstance(
            numeric_value,
            (int, float),
        ) or not math.isfinite(float(numeric_value)):
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
                "numeric evidence value must be finite",
            )


@dataclass(frozen=True)
class M8AdmissionEvidence:
    source_revision: str
    event_name: str
    git_ref: str
    protected_main: bool
    m8_exit_decision: str
    run_conclusion: str
    required_jobs_success: int
    required_jobs_total: int
    p4_admitted: bool
    p5_admitted: bool
    p6_inactive: bool


def assert_capability_claim_allowed(
    phase: str,
    *,
    evidence: M8AdmissionEvidence | None = None,
    policy: M8AuthorityPolicy | None = None,
) -> None:
    p = policy or M8AuthorityPolicy.from_canonical()
    if phase in {"P1", "P2", "P3"}:
        return
    if phase == "P6":
        raise M8GovernanceError("FAIL_CLOSED_P6_NOT_ADMITTED", phase)
    if phase not in {"P4", "P5"}:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_NOT_ADMITTED",
            phase,
        )
    if evidence is None:
        raise M8GovernanceError("FAIL_CLOSED_P4_P5_NOT_ADMITTED", phase)
    exact_text(evidence.source_revision, field="source_revision", policy=p)
    allowed = (
        evidence.event_name == p.required_exit_event
        and evidence.git_ref == p.required_exit_ref
        and evidence.protected_main
        and evidence.m8_exit_decision == p.required_exit_decision
        and evidence.run_conclusion == "success"
        and evidence.required_jobs_success == p.required_exit_jobs
        and evidence.required_jobs_total == p.required_exit_jobs
        and evidence.p6_inactive
        and (
            (phase == "P4" and evidence.p4_admitted)
            or (phase == "P5" and evidence.p5_admitted)
        )
    )
    if not allowed:
        raise M8GovernanceError("FAIL_CLOSED_P4_P5_NOT_ADMITTED", phase)


@dataclass(frozen=True)
class P3ClaimEnvelope:
    claim_level: str
    validity_status: str
    as_of_utc: str
    uncertainty_lower: float | None
    uncertainty_upper: float | None


def assert_p3_claim_preserved(
    source: P3ClaimEnvelope,
    projected: P3ClaimEnvelope,
) -> None:
    if source != projected:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "P3 claim/validity/as-of/uncertainty projection drift",
        )


def assert_scope_copy_allowed(source_phase: str, target_phase: str) -> None:
    if source_phase == "P5" and target_phase == "P4":
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_TEAM_TO_INDIVIDUAL_COPY",
            "P5 team result cannot be copied to P4 individual assessment",
        )
