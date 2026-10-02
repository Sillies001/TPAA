"""M9 Batch 1 governed P6 runtime authority helpers."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from tpaa_canonical import (
    ArtifactExpectation,
    CanonicalArtifactError,
    CanonicalArtifactLoader,
)

_AUTHORITY_ID = "P6_PREDICTION_COUNTERFACTUAL_AUTHORITY"
_ROLE_PROFILE_ID = "P6_ROLE_PRIVACY_RELEASE_PROFILE"


class P6GovernanceError(RuntimeError):
    """Deterministic fail-closed P6 governance error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _object(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise P6GovernanceError("FAIL_CLOSED_P6_AUTHORITY_REQUIRED", field)
    return cast(dict[str, object], value)


def _strings(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise P6GovernanceError("FAIL_CLOSED_P6_AUTHORITY_REQUIRED", field)
    return tuple(cast(list[str], value))


def _positive_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise P6GovernanceError("FAIL_CLOSED_P6_AUTHORITY_REQUIRED", field)
    return value


@dataclass(frozen=True, slots=True)
class P6AuthorityPolicy:
    """Runtime projection of the protected-main P6 C3 authority."""

    authority_sha256: str
    role_profile_sha256: str
    role_profile_id: str
    role_profile_version: str
    forbidden_pointer_tokens: frozenset[str]
    input_snapshot_type: str
    availability_states: tuple[str, ...]
    applicability_states: tuple[str, ...]
    session_types: tuple[str, ...]
    required_exit_event: str
    required_exit_ref: str
    required_exit_decision: str
    required_exit_jobs: int

    @classmethod
    def from_canonical(
        cls,
        loader: CanonicalArtifactLoader | None = None,
    ) -> P6AuthorityPolicy:
        canonical = loader or CanonicalArtifactLoader()
        try:
            authority = canonical.load(
                _AUTHORITY_ID,
                expectation=ArtifactExpectation(
                    version="1.0.0",
                    schema_version="1.6.0",
                    required_top_level_keys=(
                        "activation_rule",
                        "scope",
                        "exact_identity_rules",
                        "input_snapshot_contract",
                        "applicability_uncertainty_contract",
                        "interoperability_contract",
                        "admission_guard",
                    ),
                ),
            )
            role_profile = canonical.load(
                _ROLE_PROFILE_ID,
                expectation=ArtifactExpectation(
                    version="1.0.0",
                    schema_version="1.6.0",
                    required_top_level_keys=(
                        "source_bindings",
                        "scope",
                        "role_matrix",
                        "release_approval_contract",
                    ),
                ),
            )
        except CanonicalArtifactError as exc:
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_AUTHORITY_REQUIRED",
                str(exc),
            ) from exc

        root = dict(authority.payload)
        role = dict(role_profile.payload)
        activation = _object(root["activation_rule"], field="activation_rule")
        scope = _object(root["scope"], field="scope")
        exact = _object(root["exact_identity_rules"], field="exact_identity_rules")
        inputs = _object(root["input_snapshot_contract"], field="input_snapshot_contract")
        applicability = _object(
            root["applicability_uncertainty_contract"],
            field="applicability_uncertainty_contract",
        )
        interop = _object(
            root["interoperability_contract"],
            field="interoperability_contract",
        )
        guard = _object(root["admission_guard"], field="admission_guard")
        bindings = _object(role["source_bindings"], field="role_profile.source_bindings")
        role_scope = _object(role["scope"], field="role_profile.scope")

        if (
            bindings.get("p6_authority_sha256") != authority.sha256
            or role.get("profile_id") != _ROLE_PROFILE_ID
            or role.get("version") != "1.0.0"
            or role_scope.get("default_deny") is not True
            or scope.get("p1_p5_historical_products_immutable") is not True
            or scope.get("p6_authority_frozen_not_admitted") is not True
            or activation.get("authority_adoption_does_not_admit_p6") is not True
            or exact.get("identity_hash_serialization")
            != "UTF8_CANONICAL_JSON_SORTED_KEYS_NO_NAN"
            or inputs.get("snapshot_type") != "P6_INPUT"
            or inputs.get("frozen_required") is not True
        ):
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_AUTHORITY_REQUIRED",
                "P6 authority/profile contract drift",
            )

        return cls(
            authority_sha256=authority.sha256,
            role_profile_sha256=role_profile.sha256,
            role_profile_id=_ROLE_PROFILE_ID,
            role_profile_version="1.0.0",
            forbidden_pointer_tokens=frozenset(
                _strings(
                    exact.get("forbidden_pointer_tokens"),
                    field="exact_identity_rules.forbidden_pointer_tokens",
                )
            ),
            input_snapshot_type=cast(str, inputs["snapshot_type"]),
            availability_states=_strings(
                inputs.get("availability_states"),
                field="input_snapshot_contract.availability_states",
            ),
            applicability_states=_strings(
                applicability.get("applicability_states"),
                field="applicability_uncertainty_contract.applicability_states",
            ),
            session_types=_strings(
                interop.get("session_types"),
                field="interoperability_contract.session_types",
            ),
            required_exit_event=cast(str, guard["required_event"]),
            required_exit_ref=cast(str, guard["required_git_ref"]),
            required_exit_decision=cast(str, guard["required_m9_exit_decision"]),
            required_exit_jobs=_positive_int(
                guard.get("required_job_count"),
                field="admission_guard.required_job_count",
            ),
        )


def _contains_forbidden_pointer(
    value: str,
    *,
    policy: P6AuthorityPolicy,
) -> bool:
    parts = re.split(r"[^A-Z0-9]+", value.upper())
    return any(part in policy.forbidden_pointer_tokens for part in parts)


def exact_text(value: str, *, field: str, policy: P6AuthorityPolicy) -> str:
    if not isinstance(value, str) or not value.strip():
        raise P6GovernanceError("FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED", field)
    if _contains_forbidden_pointer(value, policy=policy):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_CURRENT_LATEST_DEFAULT_FORBIDDEN",
            f"{field}={value!r}",
        )
    return value


def exact_uuid(value: str, *, field: str, policy: P6AuthorityPolicy) -> str:
    exact_text(value, field=field, policy=policy)
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        ) from exc
    if parsed.int == 0 or str(parsed) != value:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        )
    return value


def exact_hash64(value: str, *, field: str) -> str:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        )
    return value


def utc(value: str, *, field: str) -> datetime:
    if not isinstance(value, str) or "T" not in value or not value.endswith("Z"):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        )
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
            f"{field}={value!r}",
        ) from exc


def canonical_hash(value: object) -> str:
    try:
        raw = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
            f"canonical json: {type(exc).__name__}",
        ) from exc
    return hashlib.sha256(raw).hexdigest()


def validate_availability_numeric(
    *,
    status: str,
    numeric_value: float | int | None,
    policy: P6AuthorityPolicy | None = None,
) -> None:
    p = policy or P6AuthorityPolicy.from_canonical()
    allowed = frozenset((*p.availability_states, *p.applicability_states))
    if status not in allowed:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_APPLICABILITY_REQUIRED",
            f"status={status!r}",
        )
    if status not in {"AVAILABLE", "APPLICABLE"} and numeric_value is not None:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_OOD_ZERO_COERCION",
            f"status={status} numeric_value={numeric_value!r}",
        )
    if numeric_value is not None and (
        isinstance(numeric_value, bool)
        or not isinstance(numeric_value, (int, float))
        or not math.isfinite(float(numeric_value))
    ):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
            "numeric value must be finite",
        )


@dataclass(frozen=True, slots=True)
class P6AdmissionEvidence:
    source_revision: str
    event_name: str
    git_ref: str
    protected_main: bool
    m9_exit_decision: str
    run_conclusion: str
    required_jobs_success: int
    required_jobs_total: int
    p6_admitted: bool


def assert_p6_claim_allowed(
    phase: str,
    *,
    evidence: P6AdmissionEvidence | None = None,
    policy: P6AuthorityPolicy | None = None,
) -> None:
    if phase in {"P1", "P2", "P3", "P4", "P5"}:
        return
    if phase != "P6":
        raise P6GovernanceError("FAIL_CLOSED_P6_NOT_ADMITTED", phase)

    p = policy or P6AuthorityPolicy.from_canonical()
    if evidence is None:
        raise P6GovernanceError("FAIL_CLOSED_P6_NOT_ADMITTED", phase)
    exact_text(evidence.source_revision, field="source_revision", policy=p)
    allowed = (
        evidence.event_name == p.required_exit_event
        and evidence.git_ref == p.required_exit_ref
        and evidence.protected_main
        and evidence.m9_exit_decision == p.required_exit_decision
        and evidence.run_conclusion == "success"
        and evidence.required_jobs_success == p.required_exit_jobs
        and evidence.required_jobs_total == p.required_exit_jobs
        and evidence.p6_admitted
    )
    if not allowed:
        raise P6GovernanceError("FAIL_CLOSED_P6_NOT_ADMITTED", phase)


def assert_p1_p5_immutable(before: object, after: object) -> None:
    if canonical_hash(before) != canonical_hash(after):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_P1_P5_MUTATION_FORBIDDEN",
            "upstream P1-P5 logical content changed",
        )
