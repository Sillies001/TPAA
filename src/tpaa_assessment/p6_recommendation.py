"""M9 Batch 3 governed advisory recommendation revisions and approval workflow."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from uuid import UUID, uuid5

from tpaa_context.p6_governance import (
    P6AuthorityPolicy,
    P6GovernanceError,
    canonical_hash,
    exact_text,
    exact_uuid,
    utc,
)
from tpaa_context.p6_runtime_security import (
    P6RuntimeSecurityPolicy,
    P6SecurityViewer,
    assert_p6_permission,
    assert_safe_request_id,
    p6_principal_key,
)

_RECOMMENDATION_NAMESPACE = UUID("b0a421cb-b6bc-5659-bf37-aa298bdf360c")
_AUDIT_NAMESPACE = UUID("94ea85bd-a5ee-5075-aafb-90a792fc4724")
_PROHIBITED_ACTION_TOKENS = frozenset(
    {
        "WEAPON",
        "TARGETING",
        "TARGET",
        "COMMAND",
        "TACTICAL",
        "OPERATIONAL",
        "ENGAGEMENT",
        "FIRE",
    }
)


@dataclass(frozen=True, slots=True)
class P6RecommendationRevision:
    recommendation_id: str
    subject_key: str
    subject_id: str
    recommendation_spec_id: str
    recommendation_spec_version: str
    source_forecast_result_ids: tuple[str, ...]
    source_counterfactual_run_ids: tuple[str, ...]
    objective_constraints: Mapping[str, object]
    allowed_action_space: Mapping[str, object]
    rationale: Mapping[str, object]
    source_gap_refs: tuple[str, ...]
    proposed_training_items: Mapping[str, object]
    applicability_status: str
    uncertainty: Mapping[str, object]
    status: str
    approval_state: str
    reviewer_subject_key: str | None
    audit_ref: str | None
    created_at: str
    supersedes_recommendation_id: str | None
    logical_content_hash: str

    def projection(self, *, direct_subject_id: str | None = None) -> dict[str, object]:
        result: dict[str, object] = {
            "recommendation_id": self.recommendation_id,
            "subject_key": self.subject_key,
            "recommendation_spec_id": self.recommendation_spec_id,
            "recommendation_spec_version": self.recommendation_spec_version,
            "source_forecast_result_ids": list(
                self.source_forecast_result_ids
            ),
            "source_counterfactual_run_ids": list(
                self.source_counterfactual_run_ids
            ),
            "objective_constraints": dict(self.objective_constraints),
            "allowed_action_space": dict(self.allowed_action_space),
            "rationale": dict(self.rationale),
            "source_gap_refs": list(self.source_gap_refs),
            "proposed_training_items": dict(self.proposed_training_items),
            "applicability_status": self.applicability_status,
            "uncertainty": dict(self.uncertainty),
            "status": self.status,
            "approval_state": self.approval_state,
            "reviewer_subject_key": self.reviewer_subject_key,
            "audit_ref": self.audit_ref,
            "created_at": self.created_at,
            "logical_content_hash": self.logical_content_hash,
        }
        if direct_subject_id is not None:
            result["subject_id"] = direct_subject_id
        return result


@dataclass(frozen=True, slots=True)
class P6RecommendationApprovalCommand:
    request_id: str
    target_state: str
    reason: str
    created_at_utc: str
    viewer: P6SecurityViewer


@dataclass(frozen=True, slots=True)
class P6RecommendationApprovalResult:
    revision: P6RecommendationRevision
    reused: bool


def _scan_action_boundary(value: object, *, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            _scan_action_boundary(str(key), path=f"{path}.key")
            _scan_action_boundary(item, path=f"{path}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        for index, item in enumerate(value):
            _scan_action_boundary(item, path=f"{path}[{index}]")
        return
    if isinstance(value, str):
        tokens = {
            token
            for token in value.upper().replace("-", "_").replace("/", "_").split("_")
            if token
        }
        if tokens & _PROHIBITED_ACTION_TOKENS:
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_RECOMMENDATION_COMMAND_UPGRADE",
                path,
            )


def _exact_refs(
    values: Sequence[str],
    *,
    field: str,
    policy: P6AuthorityPolicy,
) -> tuple[str, ...]:
    checked = tuple(
        exact_uuid(item, field=field, policy=policy) for item in values
    )
    if len(set(checked)) != len(checked):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
            f"duplicate {field}",
        )
    return tuple(sorted(checked))


def build_p6_recommendation(
    *,
    subject_key: str,
    subject_id: str,
    recommendation_spec_id: str,
    recommendation_spec_version: str,
    source_forecast_result_ids: Sequence[str],
    source_counterfactual_run_ids: Sequence[str],
    objective_constraints: Mapping[str, object],
    allowed_action_space: Mapping[str, object],
    rationale: Mapping[str, object],
    source_gap_refs: Sequence[str],
    proposed_training_items: Mapping[str, object],
    applicability_status: str,
    uncertainty: Mapping[str, object],
    created_at_utc: str,
    supersedes_recommendation_id: str | None = None,
    policy: P6AuthorityPolicy | None = None,
) -> P6RecommendationRevision:
    p = policy or P6AuthorityPolicy.from_canonical()
    exact_text(subject_key, field="subject_key", policy=p)
    exact_uuid(subject_id, field="subject_id", policy=p)
    exact_text(
        recommendation_spec_id,
        field="recommendation_spec_id",
        policy=p,
    )
    exact_text(
        recommendation_spec_version,
        field="recommendation_spec_version",
        policy=p,
    )
    utc(created_at_utc, field="created_at_utc")
    forecasts = _exact_refs(
        source_forecast_result_ids,
        field="source_forecast_result_id",
        policy=p,
    )
    counterfactuals = _exact_refs(
        source_counterfactual_run_ids,
        field="source_counterfactual_run_id",
        policy=p,
    )
    if not forecasts and not counterfactuals:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_INPUT_SNAPSHOT_REQUIRED",
            "recommendation requires exact projection sources",
        )
    if applicability_status != "APPLICABLE":
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_APPLICABILITY_REQUIRED",
            applicability_status,
        )
    if not objective_constraints or not allowed_action_space:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_RECOMMENDATION_COMMAND_UPGRADE",
            "objective constraints and advisory action space required",
        )
    if not rationale or not proposed_training_items:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_RECOMMENDATION_COMMAND_UPGRADE",
            "rationale and proposed training items required",
        )
    _scan_action_boundary(allowed_action_space, path="allowed_action_space")
    _scan_action_boundary(proposed_training_items, path="proposed_training_items")
    objectives = dict(objective_constraints)
    actions = dict(allowed_action_space)
    rationale_value = dict(rationale)
    training_items = dict(proposed_training_items)
    uncertainty_value = dict(uncertainty)
    for value in (
        objectives,
        actions,
        rationale_value,
        training_items,
        uncertainty_value,
    ):
        canonical_hash(value)
    gaps = _exact_refs(source_gap_refs, field="source_gap_ref", policy=p)
    if supersedes_recommendation_id is not None:
        exact_uuid(
            supersedes_recommendation_id,
            field="supersedes_recommendation_id",
            policy=p,
        )
    material = {
        "subject_key": subject_key,
        "subject_id": subject_id,
        "recommendation_spec_id": recommendation_spec_id,
        "recommendation_spec_version": recommendation_spec_version,
        "source_forecast_result_ids": list(forecasts),
        "source_counterfactual_run_ids": list(counterfactuals),
        "objective_constraints": objectives,
        "allowed_action_space": actions,
        "rationale": rationale_value,
        "source_gap_refs": list(gaps),
        "proposed_training_items": training_items,
        "applicability_status": applicability_status,
        "uncertainty": uncertainty_value,
        "status": "ADVISORY",
        "approval_state": "DRAFT",
        "created_at": created_at_utc,
        "supersedes_recommendation_id": supersedes_recommendation_id,
    }
    digest = canonical_hash(material)
    recommendation_id = str(uuid5(_RECOMMENDATION_NAMESPACE, digest))
    if supersedes_recommendation_id == recommendation_id:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
            "recommendation cannot supersede itself",
        )
    return P6RecommendationRevision(
        recommendation_id=recommendation_id,
        subject_key=subject_key,
        subject_id=subject_id,
        recommendation_spec_id=recommendation_spec_id,
        recommendation_spec_version=recommendation_spec_version,
        source_forecast_result_ids=forecasts,
        source_counterfactual_run_ids=counterfactuals,
        objective_constraints=objectives,
        allowed_action_space=actions,
        rationale=rationale_value,
        source_gap_refs=gaps,
        proposed_training_items=training_items,
        applicability_status=applicability_status,
        uncertainty=uncertainty_value,
        status="ADVISORY",
        approval_state="DRAFT",
        reviewer_subject_key=None,
        audit_ref=None,
        created_at=created_at_utc,
        supersedes_recommendation_id=supersedes_recommendation_id,
        logical_content_hash=digest,
    )


class P6RecommendationWorkflow:
    """Immutable recommendation approval/release state machine with request idempotency."""

    _TRANSITIONS = frozenset(
        {
            "DRAFT->IN_REVIEW",
            "IN_REVIEW->APPROVED",
            "IN_REVIEW->REJECTED",
            "APPROVED->RELEASED",
        }
    )

    def __init__(
        self,
        security_policy: P6RuntimeSecurityPolicy | None = None,
    ) -> None:
        self._security = security_policy or P6RuntimeSecurityPolicy.from_canonical()
        self._requests: dict[
            str,
            tuple[str, P6RecommendationApprovalResult],
        ] = {}

    def transition(
        self,
        previous: P6RecommendationRevision,
        command: P6RecommendationApprovalCommand,
    ) -> P6RecommendationApprovalResult:
        p = P6AuthorityPolicy.from_canonical()
        request_id = assert_safe_request_id(
            command.request_id,
            policy=self._security,
        )
        assert_p6_permission(
            command.viewer,
            "RECOMMENDATION_APPROVAL",
            policy=self._security,
        )
        if command.viewer.actor_id is None:
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_AUTHORITY_REQUIRED",
                "recommendation reviewer actor identity required",
            )
        exact_text(command.reason, field="reason", policy=p)
        utc(command.created_at_utc, field="created_at_utc")
        transition = f"{previous.approval_state}->{command.target_state}"
        if transition not in self._TRANSITIONS:
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_RECOMMENDATION_COMMAND_UPGRADE",
                transition,
            )
        fingerprint = canonical_hash(
            {
                "request_id": request_id,
                "previous_recommendation_id": previous.recommendation_id,
                "target_state": command.target_state,
                "reason": command.reason,
                "created_at_utc": command.created_at_utc,
                "reviewer_principal": p6_principal_key(
                    command.viewer,
                    policy=self._security,
                ),
            }
        )
        existing = self._requests.get(request_id)
        if existing is not None:
            if existing[0] != fingerprint:
                raise P6GovernanceError(
                    "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
                    "request-id semantic conflict",
                )
            return replace(existing[1], reused=True)
        reviewer_key = p6_principal_key(
            command.viewer,
            policy=self._security,
        )
        audit_material = {
            "request_id": request_id,
            "action": "RECOMMENDATION_APPROVAL",
            "previous_recommendation_id": previous.recommendation_id,
            "target_state": command.target_state,
            "reviewer_subject_key": reviewer_key,
            "reason": command.reason,
            "created_at_utc": command.created_at_utc,
        }
        audit_hash = canonical_hash(audit_material)
        audit_ref = str(uuid5(_AUDIT_NAMESPACE, audit_hash))
        material = {
            **previous.projection(),
            "subject_id": previous.subject_id,
            "approval_state": command.target_state,
            "reviewer_subject_key": reviewer_key,
            "audit_ref": audit_ref,
            "created_at": command.created_at_utc,
            "supersedes_recommendation_id": previous.recommendation_id,
        }
        digest = canonical_hash(material)
        revision = replace(
            previous,
            recommendation_id=str(uuid5(_RECOMMENDATION_NAMESPACE, digest)),
            approval_state=command.target_state,
            reviewer_subject_key=reviewer_key,
            audit_ref=audit_ref,
            created_at=command.created_at_utc,
            supersedes_recommendation_id=previous.recommendation_id,
            logical_content_hash=digest,
        )
        result = P6RecommendationApprovalResult(revision=revision, reused=False)
        self._requests[request_id] = (fingerprint, result)
        return result
