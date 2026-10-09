"""ED2 B2 non-numeric training-assessment semantics.

CB-1.4.0 intentionally has no adopted numeric P4/P5 scoring profile.  ED2 B2
therefore closes qualification semantics with categorical gates while keeping
all score/grade fields null and preserving unavailable/not-identifiable states.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Final

ED2_ASSESSMENT_PROFILE_SCHEMA: Final = "TPAA_ED2_TRAINING_ASSESSMENT_PROFILE_V1"
ED2_ASSESSMENT_PROFILE_ID: Final = "ED2_TRAINING_ASSESSMENT_NON_NUMERIC_GATE_V1"
ED2_ASSESSMENT_PROFILE_VERSION: Final = "1.0.0"
ED2_COMPETENCY_CODE: Final = "ED2_COMPETENCY_EVIDENCE_GROUNDED_EXECUTION"

_AVAILABILITY_PRECEDENCE: Final = (
    "NOT_IDENTIFIABLE",
    "OUT_OF_DOMAIN",
    "UNAVAILABLE",
    "AVAILABLE",
)
_ALLOWED_AVAILABILITY: Final = frozenset(_AVAILABILITY_PRECEDENCE)
_ALLOWED_P3_VALIDITY: Final = frozenset(
    {"IN_DOMAIN", "OUT_OF_DOMAIN", "UNAVAILABLE", "NOT_IDENTIFIABLE"}
)
_ALLOWED_APPROVAL: Final = frozenset({"DRAFT", "IN_REVIEW", "APPROVED", "REJECTED"})


class ED2AssessmentProfileError(RuntimeError):
    """Fail-closed assessment-profile contract violation."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True, slots=True)
class ED2AssessmentGate:
    gate_code: str
    achieved: bool | None
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ED2AssessmentProfileResult:
    profile_id: str
    profile_version: str
    availability_status: str
    competency_code: str
    competency_state: str
    critical_gates: tuple[ED2AssessmentGate, ...]
    qualification_status: str
    reason_codes: tuple[str, ...]
    numeric_score: None = None
    grade: None = None


def ed2_training_assessment_profile() -> dict[str, object]:
    return {
        "schema": ED2_ASSESSMENT_PROFILE_SCHEMA,
        "profile_id": ED2_ASSESSMENT_PROFILE_ID,
        "profile_version": ED2_ASSESSMENT_PROFILE_VERSION,
        "authority": {
            "core_baseline": "CB-1.4.0",
            "physical_db_authority": "1.9.0",
            "umbrella_issue": 245,
            "batch_issue": 247,
            "numeric_scoring_authority": "NONE",
            "p4_score_must_remain_null": True,
            "p4_grade_must_remain_null": True,
            "p5_overall_score_must_remain_null": True,
            "p5_grade_must_remain_null": True,
            "causal_upgrade_forbidden": True,
        },
        "availability_precedence": list(_AVAILABILITY_PRECEDENCE),
        "critical_gates": [
            {
                "gate_code": "ED2_GATE_EVIDENCE_SUFFICIENT",
                "source": "P4_P5_EVIDENCE_AVAILABILITY",
                "mandatory": True,
            },
            {
                "gate_code": "ED2_GATE_P3_IN_DOMAIN",
                "source": "P3_VALIDITY_DOMAIN_STATUS",
                "mandatory": True,
            },
            {
                "gate_code": "ED2_GATE_REVIEW_APPROVED",
                "source": "IMMUTABLE_APPROVAL_REVISION",
                "mandatory": True,
            },
        ],
        "diagnostic_competency": {
            "competency_code": ED2_COMPETENCY_CODE,
            "categorical_states": [
                "DEMONSTRATED",
                "NOT_DEMONSTRATED",
                "UNAVAILABLE",
                "OUT_OF_DOMAIN",
                "NOT_IDENTIFIABLE",
            ],
            "numeric_value": None,
        },
        "qualification_states": [
            "QUALIFIED",
            "NOT_QUALIFIED",
            "REVIEW_REQUIRED",
            "NOT_IDENTIFIABLE",
        ],
        "semantics": {
            "missing_or_unavailable_evidence_zero_substitution_forbidden": True,
            "not_identifiable_is_not_failure": True,
            "out_of_domain_is_not_numeric_zero": True,
            "draft_or_in_review_requires_human_review": True,
            "rejected_review_is_not_qualified": True,
            "all_mandatory_gates_required_for_qualification": True,
        },
    }


def ed2_training_assessment_profile_sha256() -> str:
    raw = json.dumps(
        ed2_training_assessment_profile(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _availability(statuses: tuple[str, ...]) -> str:
    if not statuses:
        return "UNAVAILABLE"
    invalid = sorted(set(statuses) - _ALLOWED_AVAILABILITY)
    if invalid:
        raise ED2AssessmentProfileError(
            "ED2_ASSESSMENT_AVAILABILITY_INVALID",
            ",".join(invalid),
        )
    observed = set(statuses)
    for status in _AVAILABILITY_PRECEDENCE:
        if status in observed:
            return status
    raise AssertionError("availability precedence is exhaustive")


def _p3_gate(statuses: tuple[str, ...]) -> ED2AssessmentGate:
    invalid = sorted(set(statuses) - _ALLOWED_P3_VALIDITY)
    if invalid:
        raise ED2AssessmentProfileError(
            "ED2_ASSESSMENT_P3_VALIDITY_INVALID",
            ",".join(invalid),
        )
    if not statuses or any(
        status in {"UNAVAILABLE", "NOT_IDENTIFIABLE"} for status in statuses
    ):
        return ED2AssessmentGate(
            gate_code="ED2_GATE_P3_IN_DOMAIN",
            achieved=None,
            reason_codes=("ED2_P3_VALIDITY_UNAVAILABLE",),
        )
    if any(status == "OUT_OF_DOMAIN" for status in statuses):
        return ED2AssessmentGate(
            gate_code="ED2_GATE_P3_IN_DOMAIN",
            achieved=False,
            reason_codes=("ED2_P3_OUT_OF_DOMAIN",),
        )
    return ED2AssessmentGate(
        gate_code="ED2_GATE_P3_IN_DOMAIN",
        achieved=True,
        reason_codes=(),
    )


def _approval_gate(states: tuple[str, ...]) -> ED2AssessmentGate:
    invalid = sorted(set(states) - _ALLOWED_APPROVAL)
    if invalid:
        raise ED2AssessmentProfileError(
            "ED2_ASSESSMENT_APPROVAL_INVALID",
            ",".join(invalid),
        )
    if not states or any(state in {"DRAFT", "IN_REVIEW"} for state in states):
        return ED2AssessmentGate(
            gate_code="ED2_GATE_REVIEW_APPROVED",
            achieved=None,
            reason_codes=("ED2_HUMAN_REVIEW_REQUIRED",),
        )
    if any(state == "REJECTED" for state in states):
        return ED2AssessmentGate(
            gate_code="ED2_GATE_REVIEW_APPROVED",
            achieved=False,
            reason_codes=("ED2_REVIEW_REJECTED",),
        )
    return ED2AssessmentGate(
        gate_code="ED2_GATE_REVIEW_APPROVED",
        achieved=True,
        reason_codes=(),
    )


def evaluate_ed2_training_assessment(
    *,
    evidence_availability: tuple[str, ...],
    p3_validity_statuses: tuple[str, ...],
    approval_states: tuple[str, ...],
) -> ED2AssessmentProfileResult:
    availability = _availability(evidence_availability)
    evidence_gate = ED2AssessmentGate(
        gate_code="ED2_GATE_EVIDENCE_SUFFICIENT",
        achieved=(True if availability == "AVAILABLE" else None),
        reason_codes=(
            ()
            if availability == "AVAILABLE"
            else (f"ED2_EVIDENCE_{availability}",)
        ),
    )
    p3_gate = _p3_gate(p3_validity_statuses)
    approval_gate = _approval_gate(approval_states)
    gates = (evidence_gate, p3_gate, approval_gate)

    if availability == "NOT_IDENTIFIABLE":
        competency = "NOT_IDENTIFIABLE"
        qualification = "NOT_IDENTIFIABLE"
    elif availability == "OUT_OF_DOMAIN":
        competency = "OUT_OF_DOMAIN"
        qualification = "NOT_QUALIFIED"
    elif availability == "UNAVAILABLE":
        competency = "UNAVAILABLE"
        qualification = "REVIEW_REQUIRED"
    elif p3_gate.achieved is False:
        competency = "NOT_DEMONSTRATED"
        qualification = "NOT_QUALIFIED"
    elif p3_gate.achieved is None:
        competency = "UNAVAILABLE"
        qualification = "REVIEW_REQUIRED"
    elif approval_gate.achieved is False:
        competency = "DEMONSTRATED"
        qualification = "NOT_QUALIFIED"
    elif approval_gate.achieved is None:
        competency = "DEMONSTRATED"
        qualification = "REVIEW_REQUIRED"
    else:
        competency = "DEMONSTRATED"
        qualification = "QUALIFIED"

    reasons = tuple(
        sorted(
            {
                reason
                for gate in gates
                for reason in gate.reason_codes
            }
        )
    )
    return ED2AssessmentProfileResult(
        profile_id=ED2_ASSESSMENT_PROFILE_ID,
        profile_version=ED2_ASSESSMENT_PROFILE_VERSION,
        availability_status=availability,
        competency_code=ED2_COMPETENCY_CODE,
        competency_state=competency,
        critical_gates=gates,
        qualification_status=qualification,
        reason_codes=reasons,
    )
