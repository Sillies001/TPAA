"""ED2 B2 installed continuous Source-to-P6 qualification orchestration.

This module is qualification-only orchestration.  All domain construction is
performed by the production application Jobs and governed spawn worker.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol, cast

from tpaa_application import (
    ED2AssessmentResultRepository,
    JobStatus,
    M8ApprovalMutation,
    M8ViewerContext,
    P3PersistenceRepository,
    P4P5PersistenceRepository,
    P6PersistenceRepository,
)
from tpaa_observation import allocate_session_release_id
from tpaa_runtime.production import ProductionRuntime
from tpaa_runtime.production_job_output import ProductionJobOutputRepository
from tpaa_storage import ComputeJobRepository, LocalObjectStore
from tpaa_storage.canonical_rows import CanonicalRowRepository
from tpaa_storage.hashing import canonical_request_hash

ED2_B2_CONTINUOUS_QUALIFICATION_SCHEMA = (
    "TPAA_ED2_B2_CONTINUOUS_QUALIFICATION_PLAN_V1"
)


class QualificationUnitOfWork(Protocol):
    canonical_rows: CanonicalRowRepository

    def __enter__(self) -> QualificationUnitOfWork: ...

    def __exit__(
        self,
        exc_type: object,
        exc_val: object,
        exc_tb: object,
    ) -> None: ...

    def commit(self) -> None: ...


QualificationUowFactory = Callable[
    [bool],
    AbstractContextManager[QualificationUnitOfWork],
]


@dataclass(frozen=True, slots=True)
class ED2B2ContinuousQualificationResult:
    session_ids: tuple[str, ...]
    p1_release_ids: tuple[str, ...]
    comparison_key_hash: str
    p2_estimate_ids: tuple[str, ...]
    p3_twin_revision_id: str
    p3_estimate_ids: tuple[str, ...]
    p4_draft_revision_ids: tuple[str, ...]
    p4_approved_revision_ids: tuple[str, ...]
    p5_draft_revision_id: str
    p5_approved_revision_id: str
    p6_model_id: str
    p6_forecast_request_id: str
    p6_counterfactual_request_id: str
    p6_forecast_result_id: str
    p6_counterfactual_run_id: str

    def report(self) -> dict[str, object]:
        return {
            "schema": "TPAA_ED2_B2_CONTINUOUS_QUALIFICATION_RESULT_V1",
            "session_ids": list(self.session_ids),
            "p1_release_ids": list(self.p1_release_ids),
            "comparison_key_hash": self.comparison_key_hash,
            "p2_estimate_ids": list(self.p2_estimate_ids),
            "p3_twin_revision_id": self.p3_twin_revision_id,
            "p3_estimate_ids": list(self.p3_estimate_ids),
            "p4_draft_revision_ids": list(self.p4_draft_revision_ids),
            "p4_approved_revision_ids": list(self.p4_approved_revision_ids),
            "p5_draft_revision_id": self.p5_draft_revision_id,
            "p5_approved_revision_id": self.p5_approved_revision_id,
            "p6_model_id": self.p6_model_id,
            "p6_forecast_request_id": self.p6_forecast_request_id,
            "p6_counterfactual_request_id": self.p6_counterfactual_request_id,
            "p6_forecast_result_id": self.p6_forecast_result_id,
            "p6_counterfactual_run_id": self.p6_counterfactual_run_id,
            "production_seed_dependency": False,
        }


def _mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) for key in value
    ):
        raise RuntimeError(f"ED2_B2_QUALIFICATION_FIELD_INVALID:{field}")
    return dict(cast(Mapping[str, object], value))


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"ED2_B2_QUALIFICATION_FIELD_INVALID:{field}")
    return value


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"ED2_B2_QUALIFICATION_FIELD_INVALID:{field}")
    return value


def _sequence_of_mappings(
    value: object,
    field: str,
) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list):
        raise RuntimeError(f"ED2_B2_QUALIFICATION_FIELD_INVALID:{field}")
    return tuple(
        _mapping(item, f"{field}[{index}]")
        for index, item in enumerate(value)
    )


def load_ed2_b2_continuous_plan(path: Path) -> dict[str, object]:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "ED2_B2_CONTINUOUS_QUALIFICATION_PLAN_UNREADABLE"
        ) from exc
    plan = _mapping(raw, "plan")
    if plan.get("schema") != ED2_B2_CONTINUOUS_QUALIFICATION_SCHEMA:
        raise RuntimeError("ED2_B2_CONTINUOUS_QUALIFICATION_SCHEMA_DRIFT")
    sessions = _sequence_of_mappings(plan.get("sessions"), "sessions")
    if len(sessions) != 5:
        raise RuntimeError("ED2_B2_CONTINUOUS_QUALIFICATION_SESSION_COUNT")
    ordinals = tuple(
        _integer(item.get("ordinal"), "sessions.ordinal")
        for item in sessions
    )
    if ordinals != (1, 2, 3, 4, 5):
        raise RuntimeError("ED2_B2_CONTINUOUS_QUALIFICATION_SESSION_ORDER")
    return plan


def _submit(
    runtime: ProductionRuntime,
    *,
    uow_factory: QualificationUowFactory,
    key: str,
    command: str,
    payload: dict[str, object],
    actor: str,
) -> str:
    submission = runtime.application.submit_job(
        idempotency_key=key,
        command=command,
        payload=payload,
        actor=actor,
    )
    if submission.reused or submission.record.status is not JobStatus.SUCCEEDED:
        failure_reason = "NOT_FAILED"
        if submission.record.status is JobStatus.FAILED:
            with uow_factory(False) as uow:
                failed = ComputeJobRepository(uow.canonical_rows).exact(
                    submission.record.job_id
                )
                failure_reason = ",".join(failed.reason_codes)
                if failed.error_detail is not None:
                    failure_reason = f"{failure_reason}:{failed.error_detail}"
                uow.commit()
        raise RuntimeError(
            f"ED2_B2_QUALIFICATION_JOB_FAILED:{command}:"
            f"{submission.record.job_id}:{submission.record.status.value}:"
            f"{failure_reason}"
        )
    return submission.record.job_id


def _p1_release_id(session_id: str, payload: dict[str, object]) -> str:
    request_hash = canonical_request_hash(
        {"job_type": "BUILD_P1_RELEASE", "payload": payload}
    )
    return allocate_session_release_id(
        session_id=session_id,
        request_hash=request_hash,
    )


def _common_observations(
    rows: CanonicalRowRepository,
    release_ids: tuple[str, ...],
) -> tuple[str, tuple[str, ...]]:
    by_release: list[dict[str, str]] = []
    for release_id in release_ids:
        candidates = rows.many(
            "metric.capability_observation",
            where={
                "release_id": release_id,
                "eligibility_status": "ELIGIBLE",
            },
            columns=(
                "observation_id",
                "comparison_key_hash",
                "observed_value_numeric",
                "subject_entity_id",
            ),
            order_by=("observation_id",),
        )
        mapping: dict[str, str] = {}
        for row in candidates:
            value = row["observed_value_numeric"]
            if (
                row["subject_entity_id"] is not None
                and isinstance(value, (int, float))
                and not isinstance(value, bool)
            ):
                key = str(row["comparison_key_hash"])
                if key in mapping:
                    raise RuntimeError(
                        "ED2_B2_QUALIFICATION_COMPARISON_KEY_AMBIGUOUS"
                    )
                mapping[key] = str(row["observation_id"])
        by_release.append(mapping)
    common = set(by_release[0])
    for mapping in by_release[1:]:
        common &= set(mapping)
    if not common:
        raise RuntimeError(
            "ED2_B2_QUALIFICATION_COMPARABLE_OBSERVATION_MISSING"
        )
    comparison_key = sorted(common)[0]
    observation_ids = tuple(
        mapping[comparison_key] for mapping in by_release
    )
    subjects = []
    for observation_id in observation_ids:
        subject_row = rows.one(
            "metric.capability_observation",
            where={"observation_id": observation_id},
            columns=("subject_entity_id",),
        )
        if subject_row is None:
            raise RuntimeError(
                "ED2_B2_QUALIFICATION_OBSERVATION_NOT_FOUND"
            )
        subjects.append(str(subject_row["subject_entity_id"]))
    if len(set(subjects)) != 5:
        raise RuntimeError(
            "ED2_B2_QUALIFICATION_INDEPENDENT_SUBJECTS_REQUIRED"
        )
    return comparison_key, observation_ids


def _estimate_for_job(
    rows: CanonicalRowRepository,
    job_id: str,
) -> str:
    binding = rows.one(
        "assessment.attribution_run_request_binding",
        where={"compute_job_id": job_id},
        columns=("attribution_run_id",),
    )
    if binding is None:
        raise RuntimeError("ED2_B2_QUALIFICATION_P2_BINDING_MISSING")
    estimates = rows.many(
        "capability.adjusted_capability_estimate",
        where={"attribution_run_id": str(binding["attribution_run_id"])},
        columns=("estimate_id", "status"),
        order_by=("estimate_id",),
    )
    if len(estimates) != 1 or estimates[0]["status"] != "IDENTIFIABLE":
        raise RuntimeError(
            "ED2_B2_QUALIFICATION_P2_ESTIMATE_NOT_IDENTIFIABLE"
        )
    return str(estimates[0]["estimate_id"])


def _parse_utc(value: str) -> datetime:
    if not value.endswith("Z"):
        raise RuntimeError("ED2_B2_QUALIFICATION_TIME_INVALID")
    return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(
        UTC
    )


def _offset(value: str, minutes: int) -> str:
    result = _parse_utc(value) + timedelta(minutes=minutes)
    return result.isoformat().replace("+00:00", "Z")


def _approve_p4(
    runtime: ProductionRuntime,
    *,
    draft_id: str,
    reviewer_actor_id: str,
    ordinal: int,
    base_time: str,
) -> str:
    viewer = M8ViewerContext(
        viewer_role="INSTRUCTOR_EVALUATOR",
        viewer_actor_id=reviewer_actor_id,
        scope_match=True,
    )
    review = runtime.application.m8_p4_approval(
        M8ApprovalMutation(
            target_revision_id=draft_id,
            request_id=f"ed2-b2-p4-review-{ordinal}",
            target_state="IN_REVIEW",
            reason="ED2 B2 installed qualification review",
            created_at_utc=_offset(base_time, ordinal * 2),
            viewer=viewer,
        )
    )
    review_id = _text(
        review.get("actor_assessment_id"),
        "p4.review.actor_assessment_id",
    )
    approved = runtime.application.m8_p4_approval(
        M8ApprovalMutation(
            target_revision_id=review_id,
            request_id=f"ed2-b2-p4-approve-{ordinal}",
            target_state="APPROVED",
            reason="ED2 B2 installed qualification approval",
            created_at_utc=_offset(base_time, ordinal * 2 + 1),
            viewer=viewer,
        )
    )
    return _text(
        approved.get("actor_assessment_id"),
        "p4.approved.actor_assessment_id",
    )


def _approve_p5(
    runtime: ProductionRuntime,
    *,
    draft_id: str,
    reviewer_actor_id: str,
    base_time: str,
) -> str:
    viewer = M8ViewerContext(
        viewer_role="INSTRUCTOR_EVALUATOR",
        viewer_actor_id=reviewer_actor_id,
        scope_match=True,
    )
    review = runtime.application.m8_p5_approval(
        M8ApprovalMutation(
            target_revision_id=draft_id,
            request_id="ed2-b2-p5-review",
            target_state="IN_REVIEW",
            reason="ED2 B2 installed qualification review",
            created_at_utc=_offset(base_time, 1),
            viewer=viewer,
        )
    )
    review_id = _text(
        review.get("mission_assessment_id"),
        "p5.review.mission_assessment_id",
    )
    approved = runtime.application.m8_p5_approval(
        M8ApprovalMutation(
            target_revision_id=review_id,
            request_id="ed2-b2-p5-approve",
            target_state="APPROVED",
            reason="ED2 B2 installed qualification approval",
            created_at_utc=_offset(base_time, 2),
            viewer=viewer,
        )
    )
    return _text(
        approved.get("mission_assessment_id"),
        "p5.approved.mission_assessment_id",
    )


def run_ed2_b2_continuous_qualification(
    *,
    runtime: ProductionRuntime,
    uow_factory: QualificationUowFactory,
    object_store: LocalObjectStore,
    plan_path: Path,
    actor: str,
) -> ED2B2ContinuousQualificationResult:
    plan = load_ed2_b2_continuous_plan(plan_path)
    sessions = _sequence_of_mappings(plan["sessions"], "sessions")
    session_ids = tuple(
        _text(item.get("session_id"), "session_id") for item in sessions
    )

    p1_release_ids: list[str] = []
    for item in sessions:
        ordinal = _integer(item.get("ordinal"), "ordinal")
        payload = _mapping(item.get("p1_payload"), "p1_payload")
        _submit(
            runtime,
            uow_factory=uow_factory,
            key=f"ed2-b2-continuous-p1-{ordinal}",
            command="BUILD_P1_RELEASE",
            payload=payload,
            actor=actor,
        )
        p1_release_ids.append(
            _p1_release_id(
                _text(item.get("session_id"), "session_id"),
                payload,
            )
        )

    with uow_factory(False) as uow:
        comparison_key, observation_ids = _common_observations(
            uow.canonical_rows,
            tuple(p1_release_ids),
        )
        uow.commit()

    p2_profile = _mapping(plan["p2_profile"], "p2_profile")
    factors_raw = _mapping(
        p2_profile.get("factor_values_by_ordinal"),
        "factor_values_by_ordinal",
    )
    factor_order_raw = p2_profile.get("factor_order")
    if not isinstance(factor_order_raw, list) or not all(
        isinstance(item, str) for item in factor_order_raw
    ):
        raise RuntimeError("ED2_B2_QUALIFICATION_FACTOR_ORDER_INVALID")
    factor_order = cast(list[str], factor_order_raw)
    factor_values_by_observation = {
        observation_ids[index]: {
            factor_order[0]: factors_raw[str(index + 1)]
        }
        for index in range(5)
    }
    p2_as_of = _text(
        p2_profile.get("as_of_utc", "2029-12-31T23:30:00Z"),
        "p2.as_of_utc",
    )
    p2_estimate_ids: list[str] = []
    for target_index in range(4):
        cohort_ids = [
            observation_id
            for index, observation_id in enumerate(observation_ids)
            if index != target_index
        ]
        production_input: dict[str, object] = {
            "target_observation_id": observation_ids[target_index],
            "cohort_observation_ids": cohort_ids,
            "feature_spec": _mapping(
                p2_profile.get("feature_spec"),
                "p2.feature_spec",
            ),
            "reference_condition": _mapping(
                p2_profile.get("reference_condition"),
                "p2.reference_condition",
            ),
            "attribution_spec": _mapping(
                p2_profile.get("attribution_spec"),
                "p2.attribution_spec",
            ),
            "factor_order": factor_order,
            "factor_values_by_observation": factor_values_by_observation,
            "reference_factor_values": _mapping(
                p2_profile.get("reference_factor_values"),
                "p2.reference_factor_values",
            ),
            "as_of_utc": p2_as_of,
            "cohort_spec_id": _text(
                p2_profile.get("cohort_spec_id"),
                "p2.cohort_spec_id",
            ),
            "cohort_spec_version": _text(
                p2_profile.get("cohort_spec_version"),
                "p2.cohort_spec_version",
            ),
        }
        execution_time = _offset(p2_as_of, target_index + 1)
        job_id = _submit(
            runtime,
            uow_factory=uow_factory,
            key=f"ed2-b2-continuous-p2-{target_index + 1}",
            command="P2_ATTRIBUTION",
            payload={
                "production_input": production_input,
                "execution_time_utc": execution_time,
                "expected_version_token": 0,
                "supersedes_estimate_id": None,
            },
            actor=actor,
        )
        with uow_factory(False) as uow:
            p2_estimate_ids.append(
                _estimate_for_job(uow.canonical_rows, job_id)
            )
            uow.commit()

    p3_profile = _mapping(plan["p3_profile"], "p3_profile")
    session_order = {
        session_ids[index]: index + 1 for index in range(4)
    }
    occurred = {
        session_ids[index]: _text(
            sessions[index].get("occurred_at_utc"),
            "occurred_at_utc",
        )
        for index in range(4)
    }
    p3_input: dict[str, object] = {
        "p2_estimate_ids": p2_estimate_ids,
        "session_order_by_session": session_order,
        "session_occurred_at_utc_by_session": occurred,
        "session_order_scope": _mapping(
            p3_profile.get("session_order_scope"),
            "p3.session_order_scope",
        ),
        "configuration": _mapping(
            p3_profile.get("configuration"),
            "p3.configuration",
        ),
        "as_of_utc": _text(p3_profile.get("as_of_utc"), "p3.as_of_utc"),
        "training_created_at_utc": _text(
            p3_profile.get("training_created_at_utc"),
            "p3.training_created_at_utc",
        ),
        "trained_at_utc": _text(
            p3_profile.get("trained_at_utc"),
            "p3.trained_at_utc",
        ),
        "surface_created_at_utc": _text(
            p3_profile.get("surface_created_at_utc"),
            "p3.surface_created_at_utc",
        ),
        "twin_valid_from_utc": _text(
            p3_profile.get("twin_valid_from_utc"),
            "p3.twin_valid_from_utc",
        ),
        "twin_published_at_utc": _text(
            p3_profile.get("twin_published_at_utc"),
            "p3.twin_published_at_utc",
        ),
        "estimate_created_at_utc": _text(
            p3_profile.get("estimate_created_at_utc"),
            "p3.estimate_created_at_utc",
        ),
    }
    p3_job_id = _submit(
        runtime,
        uow_factory=uow_factory,
        key="ed2-b2-continuous-p3-build",
        command="P3_BUILD_PRODUCTS",
        payload={"production_input": p3_input},
        actor=actor,
    )
    aircraft_id = _text(plan.get("aircraft_id"), "aircraft_id")
    with uow_factory(False) as uow:
        p3_output = ProductionJobOutputRepository(
            uow.canonical_rows
        ).exact(
            job_id=p3_job_id,
            command="P3_BUILD_PRODUCTS",
        ).mapping()
        twin_id = _text(
            p3_output.get("twin_revision_id"),
            "p3_output.twin_revision_id",
        )
        p3_repo = P3PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        )
        twin = p3_repo.exact_twin_revision(twin_id)
        if twin.aircraft_id != aircraft_id:
            raise RuntimeError(
                "ED2_B2_QUALIFICATION_P3_TWIN_AIRCRAFT_DRIFT"
            )
        p3_estimate_ids = tuple(
            _text(
                p3_output.get(f"estimate_{index}"),
                f"p3_output.estimate_{index}",
            )
            for index in range(1, 5)
        )
        p3_estimates = tuple(
            p3_repo.exact_capability_estimate(estimate_id)
            for estimate_id in p3_estimate_ids
        )
        ordered_p3 = tuple(
            sorted(
                p3_estimates,
                key=lambda value: _integer(
                    value.condition_point.get("session_order"),
                    "p3.condition_point.session_order",
                ),
            )
        )
        if (
            len(ordered_p3) != 4
            or tuple(
                _integer(
                    value.condition_point.get("session_order"),
                    "p3.condition_point.session_order",
                )
                for value in ordered_p3
            )
            != (1, 2, 3, 4)
            or any(value.validity_domain_status != "IN_DOMAIN" for value in ordered_p3)
        ):
            raise RuntimeError(
                "ED2_B2_QUALIFICATION_P3_ESTIMATE_SET_INVALID"
            )
        p3_estimate_ids = tuple(
            value.estimate_id for value in ordered_p3
        )
        eval_episode = uow.canonical_rows.one(
            "episode.training_episode",
            where={"session_id": session_ids[4]},
            columns=("episode_id",),
        )
        if eval_episode is None:
            raise RuntimeError(
                "ED2_B2_QUALIFICATION_EVALUATION_EPISODE_MISSING"
            )
        eval_episode_id = str(eval_episode["episode_id"])
        action_world = uow.canonical_rows.one(
            "world.world_product_manifest",
            where={
                "release_id": p1_release_ids[4],
                "episode_id": eval_episode_id,
                "world_kind": "ACTION",
                "status": "READY",
            },
            columns=("world_product_id",),
        )
        if action_world is None:
            raise RuntimeError(
                "ED2_B2_QUALIFICATION_ACTION_WORLD_MISSING"
            )
        action_world_id = str(action_world["world_product_id"])
        uow.commit()

    p4_profile = _mapping(plan["p4_profile"], "p4_profile")
    p4_drafts: list[str] = []
    p4_approved: list[str] = []
    p4_base_time = _text(
        p4_profile.get("created_at_utc"),
        "p4.created_at_utc",
    )
    reviewer_actor_id = _text(
        p4_profile.get("instructor_actor_id"),
        "p4.instructor_actor_id",
    )
    for index, estimate_id in enumerate(p3_estimate_ids, start=1):
        created_at = _offset(p4_base_time, (index - 1) * 10)
        p4_job_id = _submit(
            runtime,
            uow_factory=uow_factory,
            key=f"ed2-b2-continuous-p4-{index}",
            command="P4_ASSESSMENT",
            payload={
                "production_input": {
                    "p3_estimate_id": estimate_id,
                    "session_id": session_ids[4],
                    "episode_id": eval_episode_id,
                    "source_observation_id": observation_ids[4],
                    "world_product_id": action_world_id,
                    "actor_id": _text(
                        p4_profile.get("actor_id"),
                        "p4.actor_id",
                    ),
                    "role_code": _text(
                        p4_profile.get("role_code"),
                        "p4.role_code",
                    ),
                    "seat_code": p4_profile.get("seat_code"),
                    "function_code": p4_profile.get("function_code"),
                    "evidence_family": _text(
                        p4_profile.get("evidence_family"),
                        "p4.evidence_family",
                    ),
                    "evidence_availability_status": _text(
                        p4_profile.get(
                            "evidence_availability_status"
                        ),
                        "p4.evidence_availability_status",
                    ),
                },
                "confidence": _text(
                    p4_profile.get("confidence"),
                    "p4.confidence",
                ),
                "created_at_utc": created_at,
            },
            actor=actor,
        )
        with uow_factory(False) as uow:
            p45 = P4P5PersistenceRepository(uow.canonical_rows)
            p4_output = ProductionJobOutputRepository(
                uow.canonical_rows
            ).exact(
                job_id=p4_job_id,
                command="P4_ASSESSMENT",
            ).mapping()
            draft_id = _text(
                p4_output.get("actor_assessment_id"),
                "p4_output.actor_assessment_id",
            )
            draft = p45.exact_p4_revision(draft_id)
            result = ED2AssessmentResultRepository(
                uow.canonical_rows
            ).exact(draft_id)
            if (
                draft.score is not None
                or draft.grade is not None
                or result.qualification_status != "REVIEW_REQUIRED"
            ):
                raise RuntimeError(
                    "ED2_B2_QUALIFICATION_P4_DRAFT_SEMANTICS"
                )
            uow.commit()
        p4_drafts.append(draft_id)
        approved_id = _approve_p4(
            runtime,
            draft_id=draft_id,
            reviewer_actor_id=reviewer_actor_id,
            ordinal=index,
            base_time=_offset(created_at, 1),
        )
        with uow_factory(False) as uow:
            approved_revision = P4P5PersistenceRepository(
                uow.canonical_rows
            ).exact_p4_revision(approved_id)
            approved_result = ED2AssessmentResultRepository(
                uow.canonical_rows
            ).exact(approved_id)
            if (
                approved_revision.approval_state != "APPROVED"
                or approved_revision.score is not None
                or approved_revision.grade is not None
                or approved_result.qualification_status != "QUALIFIED"
            ):
                raise RuntimeError(
                    "ED2_B2_QUALIFICATION_P4_APPROVAL_SEMANTICS"
                )
            uow.commit()
        p4_approved.append(approved_id)

    p5_profile = _mapping(plan["p5_profile"], "p5_profile")
    p5_job_id = _submit(
        runtime,
        uow_factory=uow_factory,
        key="ed2-b2-continuous-p5",
        command="P5_ASSESSMENT",
        payload={
            "production_input": {
                "p4_revision_ids": [p4_approved[0]],
                "session_id": session_ids[4],
                "mission_episode_id": eval_episode_id,
                "team_id": p5_profile.get("team_id"),
                "objective_result_refs": p5_profile.get(
                    "objective_result_refs",
                    [],
                ),
                "as_of_utc": _text(
                    p5_profile.get("as_of_utc"),
                    "p5.as_of_utc",
                ),
            },
            "confidence": _text(
                p5_profile.get("confidence"),
                "p5.confidence",
            ),
            "created_at_utc": _text(
                p5_profile.get("created_at_utc"),
                "p5.created_at_utc",
            ),
        },
        actor=actor,
    )
    with uow_factory(False) as uow:
        p5_output = ProductionJobOutputRepository(
            uow.canonical_rows
        ).exact(
            job_id=p5_job_id,
            command="P5_ASSESSMENT",
        ).mapping()
        p5_draft = _text(
            p5_output.get("mission_assessment_id"),
            "p5_output.mission_assessment_id",
        )
        p5_revision = P4P5PersistenceRepository(
            uow.canonical_rows
        ).exact_p5_revision(p5_draft)
        p5_result = ED2AssessmentResultRepository(
            uow.canonical_rows
        ).exact(p5_draft)
        if (
            p5_revision.overall_score is not None
            or p5_revision.grade is not None
            or p5_result.qualification_status != "REVIEW_REQUIRED"
        ):
            raise RuntimeError(
                "ED2_B2_QUALIFICATION_P5_DRAFT_SEMANTICS"
            )
        uow.commit()
    p5_approved = _approve_p5(
        runtime,
        draft_id=p5_draft,
        reviewer_actor_id=reviewer_actor_id,
        base_time=_offset(
            _text(
                p5_profile.get("created_at_utc"),
                "p5.created_at_utc",
            ),
            1,
        ),
    )
    with uow_factory(False) as uow:
        p5_revision = P4P5PersistenceRepository(
            uow.canonical_rows
        ).exact_p5_revision(p5_approved)
        p5_result = ED2AssessmentResultRepository(
            uow.canonical_rows
        ).exact(p5_approved)
        if (
            p5_revision.approval_state != "APPROVED"
            or p5_revision.overall_score is not None
            or p5_revision.grade is not None
            or p5_result.qualification_status != "QUALIFIED"
        ):
            raise RuntimeError(
                "ED2_B2_QUALIFICATION_P5_APPROVAL_SEMANTICS"
            )
        uow.commit()

    p6_profile = _mapping(plan["p6_profile"], "p6_profile")
    p6_production_input: dict[str, object] = {
        "training_rows": [
            {
                "p3_estimate_id": p3_estimate_ids[index],
                "p4_revision_id": p4_approved[index],
            }
            for index in range(4)
        ],
        "factual_sources": [
            {"phase": "P4", "revision_id": p4_approved[0]},
            {"phase": "P5", "revision_id": p5_approved},
        ],
        "scenario_context_refs": [
            {
                "context_ref_id": _text(
                    sessions[4].get("context_id"),
                    "evaluation.context_id",
                ),
                "status": "ACTIVE",
                "knowledge_time_utc": _text(
                    p5_profile.get("created_at_utc"),
                    "p5.created_at_utc",
                ),
            }
        ],
        "target_scope": _text(
            p6_profile.get("target_scope"),
            "p6.target_scope",
        ),
        "subject_or_composition_ref": _text(
            p6_profile.get("subject_or_composition_ref"),
            "p6.subject_or_composition_ref",
        ),
        "forecast_origin_utc": _text(
            p6_profile.get("forecast_origin_utc"),
            "p6.forecast_origin_utc",
        ),
        "as_of_utc": _text(
            p6_profile.get("as_of_utc"),
            "p6.as_of_utc",
        ),
        "trained_at_utc": _text(
            p6_profile.get("trained_at_utc"),
            "p6.trained_at_utc",
        ),
        "sealed_at_utc": _text(
            p6_profile.get("sealed_at_utc"),
            "p6.sealed_at_utc",
        ),
        "forecast": _mapping(
            p6_profile.get("forecast"),
            "p6.forecast",
        ),
        "counterfactual": {
            **_mapping(
                p6_profile.get("counterfactual"),
                "p6.counterfactual",
            ),
            "base_product_refs": [p4_approved[0], p5_approved],
        },
    }
    p6_build_job_id = _submit(
        runtime,
        uow_factory=uow_factory,
        key="ed2-b2-continuous-p6-build",
        command="P6_BUILD_PRODUCTS",
        payload={"production_input": p6_production_input},
        actor=actor,
    )

    with uow_factory(False) as uow:
        p6_output = ProductionJobOutputRepository(
            uow.canonical_rows
        ).exact(
            job_id=p6_build_job_id,
            command="P6_BUILD_PRODUCTS",
        ).mapping()
        model_id = _text(
            p6_output.get("capability_model_id"),
            "p6_output.capability_model_id",
        )
        forecast_request_id = _text(
            p6_output.get("forecast_request_id"),
            "p6_output.forecast_request_id",
        )
        counterfactual_request_id = _text(
            p6_output.get("counterfactual_request_id"),
            "p6_output.counterfactual_request_id",
        )
        p6_repo = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        )
        model = p6_repo.exact_model_revision(model_id)
        if model.subject_id != aircraft_id:
            raise RuntimeError(
                "ED2_B2_QUALIFICATION_P6_MODEL_SUBJECT_DRIFT"
            )
        p6_repo.exact_forecast_request(forecast_request_id)
        p6_repo.exact_counterfactual_request(
            counterfactual_request_id
        )
        uow.commit()

    forecast_job = _submit(
        runtime,
        uow_factory=uow_factory,
        key="ed2-b2-continuous-p6-forecast",
        command="P6_FORECAST",
        payload={
            "forecast_request_id": forecast_request_id,
            "published_at_utc": _offset(
                _text(
                    p6_profile.get("sealed_at_utc"),
                    "p6.sealed_at_utc",
                ),
                1,
            ),
        },
        actor=actor,
    )
    counterfactual_job = _submit(
        runtime,
        uow_factory=uow_factory,
        key="ed2-b2-continuous-p6-counterfactual",
        command="P6_COUNTERFACTUAL",
        payload={
            "counterfactual_request_id": counterfactual_request_id,
            "created_at_utc": _offset(
                _text(
                    p6_profile.get("sealed_at_utc"),
                    "p6.sealed_at_utc",
                ),
                2,
            ),
        },
        actor=actor,
    )
    with uow_factory(False) as uow:
        forecast_output = ProductionJobOutputRepository(
            uow.canonical_rows
        ).exact(
            job_id=forecast_job,
            command="P6_FORECAST",
        ).mapping()
        counterfactual_output = ProductionJobOutputRepository(
            uow.canonical_rows
        ).exact(
            job_id=counterfactual_job,
            command="P6_COUNTERFACTUAL",
        ).mapping()
        forecast_result_id = _text(
            forecast_output.get("forecast_result_id"),
            "p6_forecast_output.forecast_result_id",
        )
        counterfactual_run_id = _text(
            counterfactual_output.get("counterfactual_run_id"),
            "p6_counterfactual_output.counterfactual_run_id",
        )
        p6_repo = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        )
        p6_repo.exact_forecast(forecast_result_id)
        p6_repo.exact_counterfactual(counterfactual_run_id)
        uow.commit()

    return ED2B2ContinuousQualificationResult(
        session_ids=session_ids,
        p1_release_ids=tuple(p1_release_ids),
        comparison_key_hash=comparison_key,
        p2_estimate_ids=tuple(p2_estimate_ids),
        p3_twin_revision_id=twin_id,
        p3_estimate_ids=p3_estimate_ids,
        p4_draft_revision_ids=tuple(p4_drafts),
        p4_approved_revision_ids=tuple(p4_approved),
        p5_draft_revision_id=p5_draft,
        p5_approved_revision_id=p5_approved,
        p6_model_id=model_id,
        p6_forecast_request_id=forecast_request_id,
        p6_counterfactual_request_id=counterfactual_request_id,
        p6_forecast_result_id=forecast_result_id,
        p6_counterfactual_run_id=counterfactual_run_id,
    )
