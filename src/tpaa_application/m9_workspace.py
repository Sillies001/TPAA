"""M9 exact P6 Application workspace, mutations, security and release boundary."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TypeVar, cast

from tpaa_assessment.p6_recommendation import (
    P6RecommendationApprovalCommand,
    P6RecommendationRevision,
    P6RecommendationWorkflow,
    build_p6_recommendation,
)
from tpaa_capability.p6_counterfactual import (
    P6CounterfactualRevision,
    execute_p6_counterfactual,
)
from tpaa_capability.p6_forecast import (
    P6ForecastRevision,
    P6ManagedModelObject,
    P6ModelBuild,
    P6ModelRevision,
    execute_p6_forecast,
)
from tpaa_capability.p6_input import (
    P6CounterfactualRequestBinding,
    P6ForecastRequestBinding,
    P6InputSnapshot,
)
from tpaa_context import (
    P6AdmissionEvidence,
    P6GovernanceError,
    P6RuntimeSecurityPolicy,
    P6SecurityAuditEvent,
    P6SecurityViewer,
    assert_p6_claim_allowed,
    assert_p6_permission,
    assert_safe_request_id,
    canonical_hash,
    p6_principal_key,
    project_p6_subject_id,
    pseudonymous_subject_key,
    utc,
)

_T = TypeVar("_T")
M9ViewerContext = P6SecurityViewer


class M9ApplicationError(RuntimeError):
    """Fail-closed exact-revision M9 Application error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}:{detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True, slots=True)
class M9ExactQuery:
    object_id: str
    viewer: P6SecurityViewer


@dataclass(frozen=True, slots=True)
class M9WorkspaceQuery:
    forecast_result_id: str
    counterfactual_run_id: str
    recommendation_id: str
    viewer: P6SecurityViewer


@dataclass(frozen=True, slots=True)
class M9ForecastMutation:
    request_id: str
    forecast_request_id: str
    published_at_utc: str
    viewer: P6SecurityViewer


@dataclass(frozen=True, slots=True)
class M9CounterfactualMutation:
    request_id: str
    counterfactual_request_id: str
    created_at_utc: str
    viewer: P6SecurityViewer


@dataclass(frozen=True, slots=True)
class M9RecommendationMutation:
    request_id: str
    subject_id: str
    recommendation_spec_id: str
    recommendation_spec_version: str
    source_forecast_result_ids: tuple[str, ...]
    source_counterfactual_run_ids: tuple[str, ...]
    objective_constraints: dict[str, object]
    allowed_action_space: dict[str, object]
    rationale: dict[str, object]
    source_gap_refs: tuple[str, ...]
    proposed_training_items: dict[str, object]
    created_at_utc: str
    viewer: P6SecurityViewer


@dataclass(frozen=True, slots=True)
class M9RecommendationApprovalMutation:
    recommendation_id: str
    request_id: str
    target_state: str
    reason: str
    created_at_utc: str
    viewer: P6SecurityViewer


@dataclass(frozen=True, slots=True)
class M9ModelReleaseMutation:
    capability_model_id: str
    request_id: str
    published_at_utc: str
    viewer: P6SecurityViewer


class InMemoryM9P6Repository:
    """Exact-ID immutable/candidate P6 registry for Application and transport tests."""

    def __init__(self) -> None:
        self._inputs: dict[str, P6InputSnapshot] = {}
        self._forecast_requests: dict[str, P6ForecastRequestBinding] = {}
        self._counterfactual_requests: dict[
            str,
            P6CounterfactualRequestBinding,
        ] = {}
        self._model_builds: dict[str, P6ModelBuild] = {}
        self._managed_objects: dict[str, P6ManagedModelObject] = {}
        self._forecasts: dict[str, P6ForecastRevision] = {}
        self._counterfactuals: dict[str, P6CounterfactualRevision] = {}
        self._recommendations: dict[str, P6RecommendationRevision] = {}

    @staticmethod
    def _register_exact(
        target: dict[str, _T],
        key: str,
        value: _T,
    ) -> None:
        current = target.get(key)
        if current is not None and current != value:
            raise M9ApplicationError("M9_IMMUTABLE_CONFLICT", key)
        target[key] = value

    def register_input(self, value: P6InputSnapshot) -> None:
        self._register_exact(self._inputs, value.input_snapshot_id, value)

    def register_forecast_request(self, value: P6ForecastRequestBinding) -> None:
        self._register_exact(
            self._forecast_requests,
            value.forecast_request_id,
            value,
        )

    def register_counterfactual_request(
        self,
        value: P6CounterfactualRequestBinding,
    ) -> None:
        self._register_exact(
            self._counterfactual_requests,
            value.counterfactual_request_id,
            value,
        )

    def register_model_build(
        self,
        build: P6ModelBuild,
        managed_object: P6ManagedModelObject,
    ) -> None:
        self._register_exact(
            self._model_builds,
            build.model.capability_model_id,
            build,
        )
        self._register_exact(
            self._managed_objects,
            build.model.capability_model_id,
            managed_object,
        )

    def register_forecast(self, value: P6ForecastRevision) -> None:
        self._register_exact(
            self._forecasts,
            value.forecast_result_id,
            value,
        )

    def register_counterfactual(self, value: P6CounterfactualRevision) -> None:
        self._register_exact(
            self._counterfactuals,
            value.counterfactual_run_id,
            value,
        )

    def register_recommendation(self, value: P6RecommendationRevision) -> None:
        self._register_exact(
            self._recommendations,
            value.recommendation_id,
            value,
        )

    def replace_model_release(self, model: P6ModelRevision) -> None:
        build = self.exact_model_build(model.capability_model_id)
        previous = build.model
        if (
            previous.capability_model_id != model.capability_model_id
            or previous.model_artifact_hash != model.model_artifact_hash
            or previous.training_dataset_snapshot_id
            != model.training_dataset_snapshot_id
            or previous.validation_dataset_snapshot_id
            != model.validation_dataset_snapshot_id
            or previous.model_spec_id != model.model_spec_id
            or previous.model_spec_version != model.model_spec_version
            or previous.plugin_name != model.plugin_name
            or previous.plugin_version != model.plugin_version
        ):
            raise M9ApplicationError(
                "M9_IMMUTABLE_CONFLICT",
                model.capability_model_id,
            )
        self._model_builds[model.capability_model_id] = replace(
            build,
            model=model,
        )

    def exact_input(self, object_id: str) -> P6InputSnapshot:
        return self._exact(self._inputs, object_id, "M9_INPUT_NOT_FOUND")

    def exact_forecast_request(
        self,
        object_id: str,
    ) -> P6ForecastRequestBinding:
        return self._exact(
            self._forecast_requests,
            object_id,
            "M9_FORECAST_REQUEST_NOT_FOUND",
        )

    def exact_counterfactual_request(
        self,
        object_id: str,
    ) -> P6CounterfactualRequestBinding:
        return self._exact(
            self._counterfactual_requests,
            object_id,
            "M9_COUNTERFACTUAL_REQUEST_NOT_FOUND",
        )

    def exact_model_build(self, object_id: str) -> P6ModelBuild:
        return self._exact(
            self._model_builds,
            object_id,
            "M9_MODEL_NOT_FOUND",
        )

    def exact_managed_object(self, model_id: str) -> P6ManagedModelObject:
        return self._exact(
            self._managed_objects,
            model_id,
            "M9_MODEL_OBJECT_NOT_FOUND",
        )

    def exact_forecast(self, object_id: str) -> P6ForecastRevision:
        return self._exact(
            self._forecasts,
            object_id,
            "M9_FORECAST_NOT_FOUND",
        )

    def exact_counterfactual(
        self,
        object_id: str,
    ) -> P6CounterfactualRevision:
        return self._exact(
            self._counterfactuals,
            object_id,
            "M9_COUNTERFACTUAL_NOT_FOUND",
        )

    def exact_recommendation(
        self,
        object_id: str,
    ) -> P6RecommendationRevision:
        return self._exact(
            self._recommendations,
            object_id,
            "M9_RECOMMENDATION_NOT_FOUND",
        )

    @staticmethod
    def _exact(
        source: dict[str, _T],
        object_id: str,
        code: str,
    ) -> _T:
        try:
            return source[object_id]
        except KeyError as exc:
            raise M9ApplicationError(code, object_id) from exc


class M9WorkspaceService:
    """Exact P6 candidate/release service; transports never recompute business products."""

    def __init__(
        self,
        repository: InMemoryM9P6Repository,
        *,
        admission_evidence: P6AdmissionEvidence | None = None,
        security_policy: P6RuntimeSecurityPolicy | None = None,
        recommendation_workflow: P6RecommendationWorkflow | None = None,
    ) -> None:
        self._repo = repository
        self._p6_admission_evidence = admission_evidence
        try:
            assert_p6_claim_allowed("P6", evidence=admission_evidence)
        except P6GovernanceError:
            self._p6_admitted = False
        else:
            self._p6_admitted = True
        self._security = (
            security_policy or P6RuntimeSecurityPolicy.from_canonical()
        )
        self._recommendation_workflow = (
            recommendation_workflow
            or P6RecommendationWorkflow(self._security)
        )
        self._audit: list[P6SecurityAuditEvent] = []
        self._mutation_requests: dict[str, tuple[str, dict[str, object]]] = {}

    def security_events(self) -> tuple[P6SecurityAuditEvent, ...]:
        return tuple(self._audit)

    def _record(
        self,
        viewer: P6SecurityViewer,
        *,
        action: str,
        object_ref: str,
        outcome: str,
        request_id: str | None = None,
    ) -> None:
        self._audit.append(
            P6SecurityAuditEvent(
                principal_key=p6_principal_key(
                    viewer,
                    policy=self._security,
                ),
                action=action,
                object_ref=object_ref,
                outcome=outcome,
                request_id=request_id,
            )
        )

    def _read_allowed(
        self,
        viewer: P6SecurityViewer,
        *,
        released: bool,
    ) -> None:
        rule = self._security.role_rule(viewer.role)
        if not viewer.scope_match:
            raise M9ApplicationError(
                "M9_PROJECTION_NOT_AUTHORIZED",
                f"{viewer.role}:scope",
            )
        if viewer.role in {"SUBJECT_SELF", "TEAM_LEAD"}:
            if not self._p6_admitted or not released:
                raise M9ApplicationError(
                    "M9_P6_NOT_ADMITTED",
                    viewer.role,
                )
        if not rule.projection_read_scope:
            raise M9ApplicationError(
                "M9_PROJECTION_NOT_AUTHORIZED",
                viewer.role,
            )

    def _idempotent(
        self,
        request_id: str,
        fingerprint: str,
    ) -> dict[str, object] | None:
        existing = self._mutation_requests.get(request_id)
        if existing is None:
            return None
        if existing[0] != fingerprint:
            raise M9ApplicationError(
                "M9_IDEMPOTENCY_CONFLICT",
                request_id,
            )
        return dict(existing[1])

    def _store_idempotent(
        self,
        request_id: str,
        fingerprint: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        self._mutation_requests[request_id] = (
            fingerprint,
            dict(payload),
        )
        return payload

    def model(self, query: M9ExactQuery) -> dict[str, object]:
        build = self._repo.exact_model_build(query.object_id)
        released = build.model.status == "PUBLISHED"
        self._read_allowed(query.viewer, released=released)
        rule = self._security.role_rule(query.viewer.role)
        if rule.model_metadata_read is False:
            raise M9ApplicationError(
                "M9_MODEL_NOT_AUTHORIZED",
                query.viewer.role,
            )
        direct = project_p6_subject_id(
            build.model.subject_id,
            query.viewer,
            policy=self._security,
        )
        payload = build.model.projection()
        if direct is None:
            payload.pop("subject_id", None)
        if rule.model_metadata_read == "RELEASED_MODEL_SUMMARY":
            payload.pop("model_artifact_uri", None)
            payload.pop("training_dataset_snapshot_id", None)
            payload.pop("validation_dataset_snapshot_id", None)
        payload["release_state"] = (
            "ADMITTED_RELEASE"
            if self._p6_admitted and released
            else "CANDIDATE_NOT_ADMITTED"
        )
        self._record(
            query.viewer,
            action="MODEL_READ",
            object_ref=query.object_id,
            outcome="ALLOW",
        )
        return payload

    def forecast_request(self, query: M9ExactQuery) -> dict[str, object]:
        value = self._repo.exact_forecast_request(query.object_id)
        self._read_allowed(query.viewer, released=False)
        payload: dict[str, object] = {
            "forecast_request_id": value.forecast_request_id,
            "input_snapshot_id": value.input_snapshot_id,
            "forecast_spec_id": value.forecast_spec_id,
            "forecast_spec_version": value.forecast_spec_version,
            "target_scope": value.target_scope,
            "subject_ref": value.subject_ref,
            "target_code": value.target_code,
            "forecast_origin_utc": value.forecast_origin_utc,
            "horizon_spec": dict(value.horizon_spec),
            "capability_model_id": value.capability_model_id,
            "model_profile_id": value.model_profile_id,
            "model_profile_version": value.model_profile_version,
            "training_dataset_snapshot_id": value.training_dataset_snapshot_id,
            "validation_dataset_snapshot_id": value.validation_dataset_snapshot_id,
            "assumption_profile_id": value.assumption_profile_id,
            "assumption_profile_version": value.assumption_profile_version,
            "as_of_utc": value.as_of_utc,
            "request_hash": value.request_hash,
            "release_state": "CANDIDATE_NOT_ADMITTED",
        }
        self._record(
            query.viewer,
            action="FORECAST_REQUEST_READ",
            object_ref=query.object_id,
            outcome="ALLOW",
        )
        return payload

    def counterfactual_request(
        self,
        query: M9ExactQuery,
    ) -> dict[str, object]:
        value = self._repo.exact_counterfactual_request(query.object_id)
        self._read_allowed(query.viewer, released=False)
        payload: dict[str, object] = {
            "counterfactual_request_id": value.counterfactual_request_id,
            "input_snapshot_id": value.input_snapshot_id,
            "base_product_refs": list(value.base_product_refs),
            "scenario_definition_id": value.scenario_definition_id,
            "interventions": dict(value.interventions),
            "held_fixed_assumptions": dict(value.held_fixed_assumptions),
            "model_refs": list(value.model_refs),
            "applicability_profile_ref": value.applicability_profile_ref,
            "as_of_utc": value.as_of_utc,
            "request_hash": value.request_hash,
            "release_state": "CANDIDATE_NOT_ADMITTED",
        }
        self._record(
            query.viewer,
            action="COUNTERFACTUAL_REQUEST_READ",
            object_ref=query.object_id,
            outcome="ALLOW",
        )
        return payload

    def forecast(self, query: M9ExactQuery) -> dict[str, object]:
        value = self._repo.exact_forecast(query.object_id)
        request = self._repo.exact_forecast_request(
            value.forecast_request_id
        )
        self._read_allowed(query.viewer, released=False)
        payload = value.projection()
        payload["forecast_request_id"] = request.forecast_request_id
        payload["model_artifact_hash"] = value.model_artifact_hash
        payload["forecast_origin_utc"] = value.forecast_origin_utc
        payload["assumptions"] = {
            "assumption_profile_id": request.assumption_profile_id,
            "assumption_profile_version": request.assumption_profile_version,
            "horizon_spec": dict(request.horizon_spec),
        }
        payload["projection_class"] = "P6_FORECAST_PROJECTION"
        payload["release_state"] = (
            "ADMITTED_RELEASE" if self._p6_admitted else "CANDIDATE_NOT_ADMITTED"
        )
        self._record(
            query.viewer,
            action="FORECAST_READ",
            object_ref=query.object_id,
            outcome="ALLOW",
        )
        return payload

    def counterfactual(self, query: M9ExactQuery) -> dict[str, object]:
        value = self._repo.exact_counterfactual(query.object_id)
        request = self._repo.exact_counterfactual_request(
            value.counterfactual_request_id
        )
        self._read_allowed(query.viewer, released=False)
        payload = value.projection()
        payload["counterfactual_request_id"] = request.counterfactual_request_id
        payload["base_product_refs"] = list(request.base_product_refs)
        payload["scenario_definition_id"] = request.scenario_definition_id
        payload["interventions"] = dict(request.interventions)
        payload["projection_class"] = "P6_COUNTERFACTUAL_PROJECTION"
        payload["release_state"] = (
            "ADMITTED_RELEASE" if self._p6_admitted else "CANDIDATE_NOT_ADMITTED"
        )
        self._record(
            query.viewer,
            action="COUNTERFACTUAL_READ",
            object_ref=query.object_id,
            outcome="ALLOW",
        )
        return payload

    def recommendation(self, query: M9ExactQuery) -> dict[str, object]:
        value = self._repo.exact_recommendation(query.object_id)
        released = value.approval_state == "RELEASED"
        self._read_allowed(query.viewer, released=released)
        direct = project_p6_subject_id(
            value.subject_id,
            query.viewer,
            policy=self._security,
        )
        payload = value.projection(direct_subject_id=direct)
        payload["projection_class"] = "P6_TRAINING_ADVISORY"
        payload["release_state"] = (
            "ADMITTED_RELEASE"
            if self._p6_admitted and released
            else "CANDIDATE_NOT_ADMITTED"
        )
        self._record(
            query.viewer,
            action="RECOMMENDATION_READ",
            object_ref=query.object_id,
            outcome="ALLOW",
        )
        return payload

    def run_forecast(
        self,
        mutation: M9ForecastMutation,
    ) -> dict[str, object]:
        try:
            assert_p6_permission(
                mutation.viewer,
                "FORECAST_RUN",
                policy=self._security,
            )
            request_id = assert_safe_request_id(
                mutation.request_id,
                policy=self._security,
            )
            utc(mutation.published_at_utc, field="published_at_utc")
        except P6GovernanceError as exc:
            raise M9ApplicationError(exc.code, exc.detail) from exc
        request = self._repo.exact_forecast_request(
            mutation.forecast_request_id
        )
        fingerprint = canonical_hash(
            {
                "request_id": request_id,
                "forecast_request_id": request.forecast_request_id,
                "published_at_utc": mutation.published_at_utc,
            }
        )
        reused = self._idempotent(request_id, fingerprint)
        if reused is not None:
            return reused
        build = self._repo.exact_model_build(request.capability_model_id)
        input_snapshot = self._repo.exact_input(request.input_snapshot_id)
        managed = self._repo.exact_managed_object(request.capability_model_id)
        try:
            value = execute_p6_forecast(
                request=request,
                input_snapshot=input_snapshot,
                model_build=build,
                managed_object=managed,
                published_at_utc=mutation.published_at_utc,
            )
        except P6GovernanceError as exc:
            self._record(
                mutation.viewer,
                action="FORECAST_RUN",
                object_ref=request.forecast_request_id,
                outcome="DENY",
                request_id=request_id,
            )
            raise M9ApplicationError(exc.code, exc.detail) from exc
        self._repo.register_forecast(value)
        payload = {
            "forecast_result_id": value.forecast_result_id,
            "forecast_run_id": value.forecast_run_id,
            "applicability_status": value.applicability_status,
            "request_id": request_id,
            "reused": False,
        }
        self._record(
            mutation.viewer,
            action="FORECAST_RUN",
            object_ref=value.forecast_result_id,
            outcome="ALLOW",
            request_id=request_id,
        )
        return self._store_idempotent(request_id, fingerprint, payload)

    def run_counterfactual(
        self,
        mutation: M9CounterfactualMutation,
    ) -> dict[str, object]:
        try:
            assert_p6_permission(
                mutation.viewer,
                "COUNTERFACTUAL_RUN",
                policy=self._security,
            )
            request_id = assert_safe_request_id(
                mutation.request_id,
                policy=self._security,
            )
        except P6GovernanceError as exc:
            raise M9ApplicationError(exc.code, exc.detail) from exc
        request = self._repo.exact_counterfactual_request(
            mutation.counterfactual_request_id
        )
        fingerprint = canonical_hash(
            {
                "request_id": request_id,
                "counterfactual_request_id": request.counterfactual_request_id,
                "created_at_utc": mutation.created_at_utc,
            }
        )
        reused = self._idempotent(request_id, fingerprint)
        if reused is not None:
            return reused
        models = tuple(
            self._repo.exact_model_build(model_id).model
            for model_id in request.model_refs
        )
        input_snapshot = self._repo.exact_input(request.input_snapshot_id)
        try:
            value = execute_p6_counterfactual(
                request=request,
                input_snapshot=input_snapshot,
                models=models,
                created_at_utc=mutation.created_at_utc,
            )
        except P6GovernanceError as exc:
            self._record(
                mutation.viewer,
                action="COUNTERFACTUAL_RUN",
                object_ref=request.counterfactual_request_id,
                outcome="DENY",
                request_id=request_id,
            )
            raise M9ApplicationError(exc.code, exc.detail) from exc
        self._repo.register_counterfactual(value)
        payload = {
            "counterfactual_run_id": value.counterfactual_run_id,
            "applicability_status": value.applicability_status,
            "identifiability_status": value.identifiability_status,
            "causal_claim_level": value.causal_claim_level,
            "request_id": request_id,
            "reused": False,
        }
        self._record(
            mutation.viewer,
            action="COUNTERFACTUAL_RUN",
            object_ref=value.counterfactual_run_id,
            outcome="ALLOW",
            request_id=request_id,
        )
        return self._store_idempotent(request_id, fingerprint, payload)

    def create_recommendation(
        self,
        mutation: M9RecommendationMutation,
    ) -> dict[str, object]:
        try:
            assert_p6_permission(
                mutation.viewer,
                "RECOMMENDATION_APPROVAL",
                policy=self._security,
            )
            request_id = assert_safe_request_id(
                mutation.request_id,
                policy=self._security,
            )
        except P6GovernanceError as exc:
            raise M9ApplicationError(exc.code, exc.detail) from exc
        forecasts = tuple(
            self._repo.exact_forecast(item)
            for item in mutation.source_forecast_result_ids
        )
        counterfactuals = tuple(
            self._repo.exact_counterfactual(item)
            for item in mutation.source_counterfactual_run_ids
        )
        if not forecasts and not counterfactuals:
            raise M9ApplicationError(
                "M9_RECOMMENDATION_SOURCE_REQUIRED",
                mutation.request_id,
            )
        for forecast in forecasts:
            model = self._repo.exact_model_build(
                forecast.model_revision_id
            ).model
            if (
                model.subject_id != mutation.subject_id
                or forecast.applicability_status != "APPLICABLE"
            ):
                raise M9ApplicationError(
                    "M9_RECOMMENDATION_SOURCE_SCOPE_MISMATCH",
                    forecast.forecast_result_id,
                )
        for counterfactual in counterfactuals:
            if counterfactual.applicability_status != "APPLICABLE":
                raise M9ApplicationError(
                    "M9_RECOMMENDATION_SOURCE_SCOPE_MISMATCH",
                    counterfactual.counterfactual_run_id,
                )
            for model_id in counterfactual.model_refs:
                if (
                    self._repo.exact_model_build(model_id).model.subject_id
                    != mutation.subject_id
                ):
                    raise M9ApplicationError(
                        "M9_RECOMMENDATION_SOURCE_SCOPE_MISMATCH",
                        counterfactual.counterfactual_run_id,
                    )
        uncertainty = {
            "forecast": {
                item.forecast_result_id: dict(item.uncertainty)
                for item in forecasts
            },
            "counterfactual": {
                item.counterfactual_run_id: dict(item.uncertainty)
                for item in counterfactuals
            },
        }
        fingerprint = canonical_hash(
            {
                "request_id": request_id,
                "subject_id": mutation.subject_id,
                "source_forecast_result_ids": list(
                    mutation.source_forecast_result_ids
                ),
                "source_counterfactual_run_ids": list(
                    mutation.source_counterfactual_run_ids
                ),
                "objective_constraints": mutation.objective_constraints,
                "allowed_action_space": mutation.allowed_action_space,
                "rationale": mutation.rationale,
                "proposed_training_items": mutation.proposed_training_items,
            }
        )
        reused = self._idempotent(request_id, fingerprint)
        if reused is not None:
            return reused
        try:
            value = build_p6_recommendation(
                subject_key=pseudonymous_subject_key(mutation.subject_id),
                subject_id=mutation.subject_id,
                recommendation_spec_id=mutation.recommendation_spec_id,
                recommendation_spec_version=(
                    mutation.recommendation_spec_version
                ),
                source_forecast_result_ids=(
                    mutation.source_forecast_result_ids
                ),
                source_counterfactual_run_ids=(
                    mutation.source_counterfactual_run_ids
                ),
                objective_constraints=mutation.objective_constraints,
                allowed_action_space=mutation.allowed_action_space,
                rationale=mutation.rationale,
                source_gap_refs=mutation.source_gap_refs,
                proposed_training_items=mutation.proposed_training_items,
                applicability_status="APPLICABLE",
                uncertainty=uncertainty,
                created_at_utc=mutation.created_at_utc,
            )
        except P6GovernanceError as exc:
            raise M9ApplicationError(exc.code, exc.detail) from exc
        self._repo.register_recommendation(value)
        payload = {
            "recommendation_id": value.recommendation_id,
            "approval_state": value.approval_state,
            "status": value.status,
            "request_id": request_id,
            "reused": False,
        }
        self._record(
            mutation.viewer,
            action="RECOMMENDATION_CREATE",
            object_ref=value.recommendation_id,
            outcome="ALLOW",
            request_id=request_id,
        )
        return self._store_idempotent(request_id, fingerprint, payload)

    def approve_recommendation(
        self,
        mutation: M9RecommendationApprovalMutation,
    ) -> dict[str, object]:
        previous = self._repo.exact_recommendation(
            mutation.recommendation_id
        )
        if mutation.target_state == "RELEASED":
            for forecast_id in previous.source_forecast_result_ids:
                forecast = self._repo.exact_forecast(forecast_id)
                if (
                    forecast.status != "PUBLISHED_PROJECTION"
                    or forecast.applicability_status != "APPLICABLE"
                ):
                    raise M9ApplicationError(
                        "M9_RECOMMENDATION_SOURCE_NOT_RELEASEABLE",
                        forecast_id,
                    )
            for counterfactual_id in previous.source_counterfactual_run_ids:
                counterfactual = self._repo.exact_counterfactual(
                    counterfactual_id
                )
                if (
                    counterfactual.status != "PUBLISHED_PROJECTION"
                    or counterfactual.applicability_status != "APPLICABLE"
                ):
                    raise M9ApplicationError(
                        "M9_RECOMMENDATION_SOURCE_NOT_RELEASEABLE",
                        counterfactual_id,
                    )
        try:
            result = self._recommendation_workflow.transition(
                previous,
                P6RecommendationApprovalCommand(
                    request_id=mutation.request_id,
                    target_state=mutation.target_state,
                    reason=mutation.reason,
                    created_at_utc=mutation.created_at_utc,
                    viewer=mutation.viewer,
                ),
            )
        except P6GovernanceError as exc:
            self._record(
                mutation.viewer,
                action="RECOMMENDATION_APPROVAL",
                object_ref=mutation.recommendation_id,
                outcome="DENY",
                request_id=mutation.request_id,
            )
            raise M9ApplicationError(exc.code, exc.detail) from exc
        self._repo.register_recommendation(result.revision)
        self._record(
            mutation.viewer,
            action="RECOMMENDATION_APPROVAL",
            object_ref=result.revision.recommendation_id,
            outcome="ALLOW",
            request_id=mutation.request_id,
        )
        return {
            "recommendation_id": result.revision.recommendation_id,
            "approval_state": result.revision.approval_state,
            "supersedes_recommendation_id": (
                result.revision.supersedes_recommendation_id
            ),
            "audit_ref": result.revision.audit_ref,
            "request_id": mutation.request_id,
            "reused": result.reused,
        }

    def release_model(
        self,
        mutation: M9ModelReleaseMutation,
    ) -> dict[str, object]:
        try:
            assert_p6_permission(
                mutation.viewer,
                "MODEL_RELEASE",
                policy=self._security,
            )
            request_id = assert_safe_request_id(
                mutation.request_id,
                policy=self._security,
            )
        except P6GovernanceError as exc:
            raise M9ApplicationError(exc.code, exc.detail) from exc
        build = self._repo.exact_model_build(mutation.capability_model_id)
        published_at = utc(
            mutation.published_at_utc,
            field="published_at_utc",
        )
        if published_at < utc(
            build.model.trained_at,
            field="model.trained_at",
        ):
            raise M9ApplicationError(
                "M9_MODEL_RELEASE_NOT_QUALIFIED",
                "published_at precedes trained_at",
            )
        fingerprint = canonical_hash(
            {
                "request_id": request_id,
                "capability_model_id": mutation.capability_model_id,
                "model_artifact_hash": build.model.model_artifact_hash,
                "published_at_utc": mutation.published_at_utc,
            }
        )
        reused = self._idempotent(request_id, fingerprint)
        if reused is not None:
            return reused
        if (
            build.model.status != "VALIDATED"
            or build.applicability.status != "APPLICABLE"
            or build.uncertainty.status != "CALIBRATED"
        ):
            raise M9ApplicationError(
                "M9_MODEL_RELEASE_NOT_QUALIFIED",
                mutation.capability_model_id,
            )
        published_model = replace(
            build.model,
            status="PUBLISHED",
            published_at=mutation.published_at_utc,
        )
        self._repo.replace_model_release(published_model)
        payload: dict[str, object] = {
            "capability_model_id": published_model.capability_model_id,
            "status": published_model.status,
            "published_at": published_model.published_at,
            "request_id": request_id,
            "reused": False,
        }
        self._record(
            mutation.viewer,
            action="MODEL_RELEASE",
            object_ref=published_model.capability_model_id,
            outcome="ALLOW",
            request_id=request_id,
        )
        return self._store_idempotent(request_id, fingerprint, payload)

    def workspace(self, query: M9WorkspaceQuery) -> dict[str, object]:
        forecast = self.forecast(
            M9ExactQuery(query.forecast_result_id, query.viewer)
        )
        counterfactual = self.counterfactual(
            M9ExactQuery(query.counterfactual_run_id, query.viewer)
        )
        recommendation = self.recommendation(
            M9ExactQuery(query.recommendation_id, query.viewer)
        )
        fact_refs = tuple(
            cast(list[str], forecast["factual_source_refs"])
        )
        product = {
            "fact_layer": {
                "layer": "P1_P5_FACTUAL_HISTORY",
                "exact_source_refs": list(fact_refs),
                "immutable": True,
            },
            "forecast": forecast,
            "counterfactual": counterfactual,
            "recommendation": recommendation,
            "presentation_contract": {
                "business_recompute": False,
                "persistence_access": False,
                "projection_to_fact_upgrade": False,
            },
        }
        return {
            **product,
            "logical_product_hash": canonical_hash(product),
        }

    def export_exact(
        self,
        query: M9WorkspaceQuery,
    ) -> dict[str, object]:
        try:
            assert_p6_permission(
                query.viewer,
                "INTEROP_EXPORT",
                policy=self._security,
            )
        except P6GovernanceError as exc:
            self._record(
                query.viewer,
                action="P6_EXPORT",
                object_ref=query.recommendation_id,
                outcome="DENY",
            )
            raise M9ApplicationError(exc.code, exc.detail) from exc
        if not self._p6_admitted:
            raise M9ApplicationError(
                "M9_P6_NOT_ADMITTED",
                "external export before M9 Exit",
            )
        payload = self.workspace(query)
        self._record(
            query.viewer,
            action="P6_EXPORT",
            object_ref=query.recommendation_id,
            outcome="ALLOW",
        )
        return payload
