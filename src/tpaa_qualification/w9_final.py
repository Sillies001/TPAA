"""W9 single-candidate qualification status and fail-closed release decision."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType


class W9QualificationError(RuntimeError):
    """Invalid W9 evidence or an unsafe final-release claim."""


W9_EVIDENCE_CATEGORIES = (
    "FOUR_PROFILE_PACKAGES_AND_INSTALLED_RUNTIME",
    "AUTHORITY_ARCHITECTURE_DTO_OPENAPI_MIGRATION_REPLAY",
    "UNIT_GOLDEN_INTEGRATION_INSTALLED_E2E",
    "REAL_DATA_AND_EXTERNAL_SYSTEMS",
    "SECURITY_ROLE_PRIVACY_PLUGIN",
    "WORKLOAD_PERFORMANCE_RESOURCE",
    "BACKUP_RESTORE_DR_UPGRADE_ROLLBACK",
    "GUI_VISUAL_AND_HUMAN_ROLE_TASKS",
    "SBOM_PROVENANCE_SIGNATURE",
    "PROTECTED_MAIN_AND_HOSTED_CI",
)

_GATE_STATES = frozenset(
    {
        "LOCAL_EVIDENCE_COMPLETE",
        "PARTIAL_LOCAL_EVIDENCE",
        "PENDING_EXTERNAL",
        "PENDING_TARGET",
        "PENDING_HUMAN",
        "PENDING_SIGNATURE",
        "PENDING_PROTECTED_MAIN",
        "ACCEPTED",
    }
)


def _sha256(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise W9QualificationError(f"W9_SHA256_INVALID:{field}")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise W9QualificationError(f"W9_TEXT_INVALID:{field}")
    return value


def _boolean(value: object, field: str) -> bool:
    if type(value) is not bool:
        raise W9QualificationError(f"W9_BOOLEAN_INVALID:{field}")
    return value


def _finding_count(value: object, field: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0:
        raise W9QualificationError(f"W9_FINDING_COUNT_INVALID:{field}")
    return value


def _source_revision(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise W9QualificationError("W9_SOURCE_REVISION_INVALID")
    return value


def _optional_sha256(record: Mapping[str, object], field: str) -> str | None:
    value = record.get(field)
    return None if value is None else _sha256(value, field)


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class W9EvidenceGate:
    category: str
    state: str
    reason_code: str
    candidate_identity_sha256: str | None = None
    evidence_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.category not in W9_EVIDENCE_CATEGORIES:
            raise W9QualificationError(f"W9_CATEGORY_INVALID:{self.category}")
        if self.state not in _GATE_STATES:
            raise W9QualificationError(f"W9_GATE_STATE_INVALID:{self.category}")
        _text(self.reason_code, "reason_code")
        if self.state == "ACCEPTED":
            _sha256(self.candidate_identity_sha256, "candidate_identity_sha256")
            _sha256(self.evidence_sha256, "evidence_sha256")
        elif (
            self.candidate_identity_sha256 is not None
            or self.evidence_sha256 is not None
        ):
            raise W9QualificationError(
                f"W9_UNACCEPTED_EVIDENCE_BINDING_FORBIDDEN:{self.category}"
            )

    def projection(self) -> dict[str, object]:
        return {
            "category": self.category,
            "state": self.state,
            "reason_code": self.reason_code,
            "candidate_identity_sha256": self.candidate_identity_sha256,
            "evidence_sha256": self.evidence_sha256,
            "accepted": self.state == "ACCEPTED",
        }


class W9FinalQualificationStatus:
    """Final release decision over one exact, immutable candidate identity."""

    def __init__(
        self,
        gates: Sequence[W9EvidenceGate],
        *,
        candidate_identity_sha256: str | None,
        source_revision: str | None,
        unwaived_blocker_count: int | None,
        unwaived_high_count: int | None,
        protected_main_exact: bool,
        hosted_ci_success: bool,
        independent_approval_complete: bool,
        signature_sha256: str | None,
        local_stage_closed: bool,
    ) -> None:
        if tuple(gate.category for gate in gates) != W9_EVIDENCE_CATEGORIES:
            raise W9QualificationError("W9_CATEGORY_SET_OR_ORDER_INVALID")
        blocker_count = _finding_count(
            unwaived_blocker_count,
            "unwaived_blocker_count",
        )
        high_count = _finding_count(unwaived_high_count, "unwaived_high_count")
        if candidate_identity_sha256 is not None:
            _sha256(candidate_identity_sha256, "candidate_identity_sha256")
        if source_revision is not None:
            _source_revision(source_revision)
        if signature_sha256 is not None:
            _sha256(signature_sha256, "signature_sha256")
        protected_main = _boolean(protected_main_exact, "protected_main_exact")
        hosted_ci = _boolean(hosted_ci_success, "hosted_ci_success")
        independent_approval = _boolean(
            independent_approval_complete,
            "independent_approval_complete",
        )
        local_closed = _boolean(local_stage_closed, "local_stage_closed")
        self._gates = tuple(gates)
        self._candidate_identity_sha256 = candidate_identity_sha256
        self._source_revision = source_revision
        self._unwaived_blocker_count = blocker_count
        self._unwaived_high_count = high_count
        self._protected_main_exact = protected_main
        self._hosted_ci_success = hosted_ci
        self._independent_approval_complete = independent_approval
        self._signature_sha256 = signature_sha256
        self._local_stage_closed = local_closed

    @classmethod
    def local_closed(cls) -> W9FinalQualificationStatus:
        states_and_reasons = (
            (
                "PARTIAL_LOCAL_EVIDENCE",
                "FOUR_DEVELOPMENT_PACKAGES_BUILT_INSTALLED_TARGET_E2E_PENDING",
            ),
            ("LOCAL_EVIDENCE_COMPLETE", "LOCAL_CONTRACT_CHAIN_VERIFIED"),
            (
                "PARTIAL_LOCAL_EVIDENCE",
                "LOCAL_TEST_PYRAMID_PASS_INSTALLED_TARGET_E2E_PENDING",
            ),
            ("PENDING_EXTERNAL", "REAL_DATA_AND_APPROVED_EXTERNAL_ENDPOINTS_REQUIRED"),
            (
                "PARTIAL_LOCAL_EVIDENCE",
                "LOCAL_SECURITY_CONTRACTS_PASS_PRODUCTION_TRUST_ACCEPTANCE_PENDING",
            ),
            ("PENDING_TARGET", "FOUR_PROFILE_TARGET_WORKLOAD_ACCEPTANCE_REQUIRED"),
            ("PENDING_TARGET", "TARGET_DR_UPGRADE_ROLLBACK_ACCEPTANCE_REQUIRED"),
            ("PENDING_HUMAN", "HUMAN_ROLE_TASK_SIGNOFF_REQUIRED"),
            ("PENDING_SIGNATURE", "APPROVED_RELEASE_SIGNATURE_REQUIRED"),
            ("PENDING_PROTECTED_MAIN", "PROTECTED_MAIN_HOSTED_CI_REQUIRED"),
        )
        return cls(
            tuple(
                W9EvidenceGate(
                    category=category,
                    state=state,
                    reason_code=reason,
                )
                for category, (state, reason) in zip(
                    W9_EVIDENCE_CATEGORIES,
                    states_and_reasons,
                    strict=True,
                )
            ),
            candidate_identity_sha256=None,
            source_revision=None,
            # A local-only review cannot adjudicate the complete formal finding
            # population.  Null is intentionally different from a claimed zero.
            unwaived_blocker_count=None,
            unwaived_high_count=None,
            protected_main_exact=False,
            hosted_ci_success=False,
            independent_approval_complete=False,
            signature_sha256=None,
            local_stage_closed=True,
        )

    def execute(self) -> dict[str, object]:
        accepted = all(gate.state == "ACCEPTED" for gate in self._gates)
        bound_to_one_candidate = (
            self._candidate_identity_sha256 is not None
            and self._source_revision is not None
            and all(
                gate.candidate_identity_sha256 == self._candidate_identity_sha256
                for gate in self._gates
            )
        )
        release_allowed = (
            accepted
            and bound_to_one_candidate
            and self._unwaived_blocker_count == 0
            and self._unwaived_high_count == 0
            and self._protected_main_exact
            and self._hosted_ci_success
            and self._independent_approval_complete
            and self._signature_sha256 is not None
        )
        projection: dict[str, object] = {
            "schema": "TPAA_W9_FINAL_QUALIFICATION_STATUS_V1",
            "stage_status": (
                "FORMALLY_QUALIFIED"
                if release_allowed
                else "CLOSED_LOCAL_WITH_RELEASE_GATES"
                if self._local_stage_closed
                else "OPEN"
            ),
            "decision": "GO" if release_allowed else "NO_GO",
            "qualification": (
                "FORMALLY_QUALIFIED"
                if release_allowed
                else "LOCAL_CANDIDATE_NOT_FORMALLY_QUALIFIED"
            ),
            "candidate_identity_sha256": self._candidate_identity_sha256,
            "source_revision": self._source_revision,
            "all_evidence_bound_to_one_candidate": bound_to_one_candidate,
            "unwaived_findings": {
                "blocker": self._unwaived_blocker_count,
                "high": self._unwaived_high_count,
            },
            "protected_main_exact": self._protected_main_exact,
            "hosted_ci_success": self._hosted_ci_success,
            "independent_approval_complete": self._independent_approval_complete,
            "signature_sha256": self._signature_sha256,
            "gates": [gate.projection() for gate in self._gates],
            "formal_release_allowed": release_allowed,
            "formal_release_claimed": release_allowed,
        }
        return {
            **projection,
            "logical_status_sha256": _canonical_hash(projection),
        }


def build_w9_final_qualification_status(
    records: Sequence[Mapping[str, object]],
    *,
    candidate_identity_sha256: str,
    source_revision: str,
    unwaived_blocker_count: int,
    unwaived_high_count: int,
    protected_main_exact: bool,
    hosted_ci_success: bool,
    independent_approval_complete: bool,
    signature_sha256: str | None,
) -> W9FinalQualificationStatus:
    """Build an immutable final status from an approved evidence manifest."""

    gates = tuple(
        W9EvidenceGate(
            category=_text(record.get("category"), "category"),
            state=_text(record.get("state"), "state"),
            reason_code=_text(record.get("reason_code"), "reason_code"),
            candidate_identity_sha256=_optional_sha256(
                record,
                "candidate_identity_sha256",
            ),
            evidence_sha256=_optional_sha256(record, "evidence_sha256"),
        )
        for record in records
    )
    return W9FinalQualificationStatus(
        gates,
        candidate_identity_sha256=candidate_identity_sha256,
        source_revision=source_revision,
        unwaived_blocker_count=unwaived_blocker_count,
        unwaived_high_count=unwaived_high_count,
        protected_main_exact=protected_main_exact,
        hosted_ci_success=hosted_ci_success,
        independent_approval_complete=independent_approval_complete,
        signature_sha256=signature_sha256,
        local_stage_closed=False,
    )


def immutable_gate_map(
    gates: Sequence[W9EvidenceGate],
) -> Mapping[str, W9EvidenceGate]:
    """Return a read-only category map for review/reporting adapters."""

    return MappingProxyType({gate.category: gate for gate in gates})


__all__ = [
    "W9_EVIDENCE_CATEGORIES",
    "W9EvidenceGate",
    "W9FinalQualificationStatus",
    "W9QualificationError",
    "build_w9_final_qualification_status",
    "immutable_gate_map",
]
