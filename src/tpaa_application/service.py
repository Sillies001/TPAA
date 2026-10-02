"""Application Service facade exposed to GUI and REST transports."""

from __future__ import annotations

from typing import Protocol

from .job_control import JobRecord, JobSubmission, M0JobControl
from .m1_publication import (
    M1PublicationService,
    M1PublishSessionCommand,
    M1PublishSessionResult,
)
from .m3_publication import M3PublicationService
from .m3_workspace import project_m3_workspace
from .m4_workspace import (
    M4AnnotationCommand,
    M4DebriefQuery,
    M4TrendQuery,
    M4WorkspaceService,
)
from .m6_workspace import (
    M6P2ComparisonQuery,
    M6P2DiagnosticsQuery,
    M6WorkspaceService,
)
from .m7_workspace import (
    M7EstimateQuery,
    M7TwinQuery,
    M7WorkspaceQuery,
    M7WorkspaceService,
)
from .m8_workspace import (
    M8AnnotationMutation,
    M8ApprovalMutation,
    M8P4Query,
    M8P5Query,
    M8WorkspaceQuery,
    M8WorkspaceService,
)
from .m9_workspace import (
    M9CounterfactualMutation,
    M9ExactQuery,
    M9ForecastMutation,
    M9ModelReleaseMutation,
    M9RecommendationApprovalMutation,
    M9RecommendationMutation,
    M9WorkspaceQuery,
    M9WorkspaceService,
)
from .models import StorageBaselineStatus
from .runtime import GetRuntimeBaselineStatus, RuntimeBaselineStatus


class StorageBaselineStatusUseCase(Protocol):
    """Structural Application dependency for persisted baseline status."""

    def execute(self) -> StorageBaselineStatus:
        """Return engine-neutral persisted baseline metadata."""
        ...


class ApplicationService:
    """Typed facade that is the transport-facing business-entry boundary."""

    def __init__(
        self,
        *,
        get_storage_baseline_status: StorageBaselineStatusUseCase,
        get_runtime_baseline_status: GetRuntimeBaselineStatus | None = None,
        job_control: M0JobControl | None = None,
        m1_publication: M1PublicationService | None = None,
        m3_publication: M3PublicationService | None = None,
        m4_workspace: M4WorkspaceService | None = None,
        m6_workspace: M6WorkspaceService | None = None,
        m7_workspace: M7WorkspaceService | None = None,
        m8_workspace: M8WorkspaceService | None = None,
        m9_workspace: M9WorkspaceService | None = None,
    ) -> None:
        self._get_storage_baseline_status = get_storage_baseline_status
        self._get_runtime_baseline_status = get_runtime_baseline_status
        self._job_control = job_control or M0JobControl()
        self._m1_publication = m1_publication
        self._m3_publication = m3_publication
        self._m4_workspace = m4_workspace
        self._m6_workspace = m6_workspace
        self._m7_workspace = m7_workspace
        self._m8_workspace = m8_workspace
        self._m9_workspace = m9_workspace

    def storage_baseline_status(self) -> StorageBaselineStatus:
        """Return persisted storage baseline provenance via an Application use case."""

        return self._get_storage_baseline_status.execute()

    def runtime_baseline_status(self) -> RuntimeBaselineStatus:
        """Return the Core-authoritative runtime handshake projection.

        M0-API-002 requires this use case to be wired before exposing readiness/version.
        """

        if self._get_runtime_baseline_status is None:
            raise RuntimeError("runtime baseline status use case is not configured")
        return self._get_runtime_baseline_status.execute()


    def submit_job(
        self,
        *,
        idempotency_key: str,
        command: str,
        payload: dict[str, object],
        actor: str,
    ) -> JobSubmission:
        """Submit an M0 control-plane job skeleton with canonical request identity."""

        return self._job_control.submit(
            idempotency_key=idempotency_key,
            command=command,
            payload=payload,
            actor=actor,
        )

    def job(self, job_id: str) -> JobRecord:
        """Return an M0 job record without transport-specific behavior."""

        return self._job_control.get(job_id)

    def cancel_job(self, *, job_id: str, actor: str, reason: str) -> JobRecord:
        """Cancel an M0 job skeleton; this does not implement M1 compute cancellation."""

        return self._job_control.cancel(job_id=job_id, actor=actor, reason=reason)


    def _m1(self) -> M1PublicationService:
        if self._m1_publication is None:
            raise RuntimeError("M1 publication service is not configured")
        return self._m1_publication

    def import_m1_session(
        self,
        *,
        fixture_id: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        """Validate one governed source fixture through the M1 import command."""

        return self._m1().import_session(
            fixture_id=fixture_id,
            idempotency_key=idempotency_key,
        )

    def compute_m1_session(
        self,
        *,
        fixture_id: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        """Compute one staged M1 World/Metric product without publication."""

        return self._m1().compute_session(
            fixture_id=fixture_id,
            idempotency_key=idempotency_key,
        )

    def publish_m1_session(
        self,
        command: M1PublishSessionCommand,
        *,
        idempotency_key: str,
    ) -> M1PublishSessionResult:
        """Publish one exact SESSION Release through the M1 Application service."""

        return self._m1().publish_session(command, idempotency_key=idempotency_key)

    def m1_release(self, release_id: str) -> dict[str, object]:
        return self._m1().release_summary(release_id)

    def m1_observations(self, release_id: str) -> list[dict[str, object]]:
        return [dict(item) for item in self._m1().observations(release_id)]

    def m1_metrics(self, release_id: str) -> list[dict[str, object]]:
        return self._m1().metric_list(release_id)

    def m1_metric(self, release_id: str, metric_code: str) -> dict[str, object]:
        return self._m1().metric_detail(release_id, metric_code)

    def m1_metric_evidence(self, release_id: str, metric_code: str) -> dict[str, object]:
        return self._m1().metric_evidence(release_id, metric_code)

    def m1_context(self, release_id: str) -> dict[str, object]:
        return dict(self._m1().context_projection(release_id))

    def m1_session_episode_stages(self, release_id: str) -> dict[str, object]:
        return dict(self._m1().session_episode_stage_projection(release_id))

    def replay_m1_release(self, release_id: str) -> dict[str, object]:
        return self._m1().replay(release_id)

    def m1_series_range(
        self,
        release_id: str,
        *,
        start_session_time_us: int,
        end_session_time_us: int,
        limit: int,
    ) -> dict[str, object]:
        return self._m1().series_range(
            release_id,
            start_session_time_us=start_session_time_us,
            end_session_time_us=end_session_time_us,
            limit=limit,
        )


    def _m3(self) -> M3PublicationService:
        if self._m3_publication is None:
            raise RuntimeError("M3 publication service is not configured")
        return self._m3_publication

    def m3_release(self, release_id: str) -> dict[str, object]:
        return self._m3().release_summary(release_id)

    def m3_metrics(self, release_id: str) -> list[dict[str, object]]:
        return self._m3().metric_list(release_id)

    def m3_metric(self, release_id: str, metric_code: str) -> dict[str, object]:
        return self._m3().metric_detail(release_id, metric_code)

    def m3_metric_evidence(
        self,
        release_id: str,
        metric_code: str,
    ) -> dict[str, object]:
        return self._m3().metric_evidence(release_id, metric_code)

    def m3_workspace(self, release_id: str) -> dict[str, object]:
        release = self._m3().historical_release(release_id).release
        return project_m3_workspace(release)

    def _m4(self) -> M4WorkspaceService:
        if self._m4_workspace is None:
            raise RuntimeError("M4 workspace service is not configured")
        return self._m4_workspace

    def m4_trend(self, query: M4TrendQuery) -> dict[str, object]:
        return self._m4().trend(query)

    def m4_debrief(self, query: M4DebriefQuery) -> dict[str, object]:
        return self._m4().debrief(query)

    def m4_annotation(
        self,
        command: M4AnnotationCommand,
    ) -> dict[str, object]:
        return self._m4().annotation(command)

    def _m6(self) -> M6WorkspaceService:
        if self._m6_workspace is None:
            raise RuntimeError("M6 workspace service is not configured")
        return self._m6_workspace

    def m6_p2_comparison(
        self,
        query: M6P2ComparisonQuery,
    ) -> dict[str, object]:
        return self._m6().comparison(query)

    def m6_p2_diagnostics(
        self,
        query: M6P2DiagnosticsQuery,
    ) -> dict[str, object]:
        return self._m6().diagnostics(query)

    def _m7(self) -> M7WorkspaceService:
        if self._m7_workspace is None:
            raise RuntimeError("M7 workspace service is not configured")
        return self._m7_workspace

    def m7_p3_twin(self, query: M7TwinQuery) -> dict[str, object]:
        return self._m7().twin(query)

    def m7_p3_estimate(self, query: M7EstimateQuery) -> dict[str, object]:
        return self._m7().estimate(query)

    def m7_p3_workspace(self, query: M7WorkspaceQuery) -> dict[str, object]:
        return self._m7().workspace(query)


    def _m8(self) -> M8WorkspaceService:
        if self._m8_workspace is None:
            raise RuntimeError("M8 workspace service is not configured")
        return self._m8_workspace

    def m8_p4(self, query: M8P4Query) -> dict[str, object]:
        return self._m8().p4(query)

    def m8_p5(self, query: M8P5Query) -> dict[str, object]:
        return self._m8().p5(query)

    def m8_workspace(self, query: M8WorkspaceQuery) -> dict[str, object]:
        return self._m8().workspace(query)

    def m8_annotation(
        self,
        mutation: M8AnnotationMutation,
    ) -> dict[str, object]:
        return self._m8().annotate_p4(mutation)

    def m8_p4_approval(
        self,
        mutation: M8ApprovalMutation,
    ) -> dict[str, object]:
        return self._m8().approve_p4(mutation)

    def m8_p5_approval(
        self,
        mutation: M8ApprovalMutation,
    ) -> dict[str, object]:
        return self._m8().approve_p5(mutation)

    def m8_export(self, query: M8WorkspaceQuery) -> dict[str, object]:
        return self._m8().export_exact(query)


    def _m9(self) -> M9WorkspaceService:
        if self._m9_workspace is None:
            raise RuntimeError("M9 workspace service is not configured")
        return self._m9_workspace

    def m9_model(self, query: M9ExactQuery) -> dict[str, object]:
        return self._m9().model(query)

    def m9_forecast_request(
        self,
        query: M9ExactQuery,
    ) -> dict[str, object]:
        return self._m9().forecast_request(query)

    def m9_counterfactual_request(
        self,
        query: M9ExactQuery,
    ) -> dict[str, object]:
        return self._m9().counterfactual_request(query)

    def m9_forecast(self, query: M9ExactQuery) -> dict[str, object]:
        return self._m9().forecast(query)

    def m9_counterfactual(self, query: M9ExactQuery) -> dict[str, object]:
        return self._m9().counterfactual(query)

    def m9_recommendation(self, query: M9ExactQuery) -> dict[str, object]:
        return self._m9().recommendation(query)

    def m9_workspace(self, query: M9WorkspaceQuery) -> dict[str, object]:
        return self._m9().workspace(query)

    def m9_run_forecast(
        self,
        mutation: M9ForecastMutation,
    ) -> dict[str, object]:
        return self._m9().run_forecast(mutation)

    def m9_run_counterfactual(
        self,
        mutation: M9CounterfactualMutation,
    ) -> dict[str, object]:
        return self._m9().run_counterfactual(mutation)

    def m9_create_recommendation(
        self,
        mutation: M9RecommendationMutation,
    ) -> dict[str, object]:
        return self._m9().create_recommendation(mutation)

    def m9_approve_recommendation(
        self,
        mutation: M9RecommendationApprovalMutation,
    ) -> dict[str, object]:
        return self._m9().approve_recommendation(mutation)

    def m9_release_model(
        self,
        mutation: M9ModelReleaseMutation,
    ) -> dict[str, object]:
        return self._m9().release_model(mutation)

    def m9_export(self, query: M9WorkspaceQuery) -> dict[str, object]:
        return self._m9().export_exact(query)
