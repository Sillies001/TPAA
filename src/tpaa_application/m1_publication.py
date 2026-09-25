"""M1 Batch 2 Application Service for release-bound publication and historical reads."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from tpaa_context import resolve_evaluation_context
from tpaa_generated.dto import CapabilityObservationDTO, EvaluationContextDTO
from tpaa_ingest import load_synthetic_fixture_bundle
from tpaa_metric import build_metric_context, compute_representative_metrics
from tpaa_observation import (
    AircraftPublicationIdentity,
    PublicationError,
    allocate_session_release_id,
    build_session_release,
    compare_replay,
)
from tpaa_storage.hashing import canonical_request_hash
from tpaa_storage.publication_bundle import (
    CoreEvidenceRecord,
    CoreMetricDefinitionRef,
    CoreMetricInstanceRecord,
    CoreObservationRecord,
    CorePublicationBundle,
)
from tpaa_application.m1_repository import (
    PublishCASConflict,
    PublishIdempotencyConflict,
    PublishedSessionRelease,
    ReleaseNotFound,
    SessionPublicationRepository,
)
from tpaa_world import AircraftObservedWorld, project_minimal_p1_world


class M1SessionProjection(TypedDict):
    """Explicit JSON-safe Session projection for M1 API reads."""

    session_id: str
    start_session_time_us: str
    end_session_time_us: str


class M1EpisodeProjection(TypedDict):
    """Explicit JSON-safe Episode projection for M1 API reads."""

    episode_id: str
    session_id: str


class M1StageProjection(TypedDict):
    """Explicit JSON-safe Stage projection for M1 API reads."""

    stage_id: str
    episode_id: str
    stage_type: str
    stage_order: int
    start_session_time_us: str
    end_session_time_us: str
    stage_status: str
    coverage: float
    confidence: float
    detector_version: str


class M1SessionEpisodeStageProjection(TypedDict):
    """Release-bound transport projection; no domain objects cross the boundary."""

    release_id: str
    session: M1SessionProjection
    episode: M1EpisodeProjection
    stages: list[M1StageProjection]


class M1ApplicationError(RuntimeError):
    """Transport-safe M1 Application failure with stable code."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class M1PublishSessionCommand:
    fixture_id: str
    aircraft_model_id: str
    aircraft_instance_id: str
    subject_entity_id: str
    capability_dimension: str
    capability_type: str
    expected_version_token: int

    def request_payload(self) -> dict[str, object]:
        return {
            "command": "M1_PUBLISH_SESSION",
            "fixture_id": self.fixture_id,
            "aircraft_model_id": self.aircraft_model_id,
            "aircraft_instance_id": self.aircraft_instance_id,
            "subject_entity_id": self.subject_entity_id,
            "capability_dimension": self.capability_dimension,
            "capability_type": self.capability_type,
            "expected_version_token": self.expected_version_token,
        }


@dataclass(frozen=True)
class M1PublishSessionResult:
    release_id: str
    session_id: str
    request_hash: str
    manifest_hash: str
    status: str
    version_token: int
    reused: bool


def to_core_publication_bundle(release: SessionRelease) -> CorePublicationBundle:
    """Project a decided immutable Release into driver-neutral Core row records."""

    metric_by_evidence = {
        item.evidence_set_id: item for item in release.metric_instances
    }
    observation_by_metric = {
        item.metric_instance_id: item for item in release.observations
    }
    evidence_sets = tuple(
        CoreEvidenceRecord(
            evidence_set_id=evidence.evidence_set_id,
            episode_id=evidence.episode_id,
            start_session_time_us=evidence.start_session_time_us,
            end_session_time_us=evidence.end_session_time_us,
            series_locator={
                "logical_hash": evidence.logical_hash,
                "refs": [
                    {
                        "ref_class": ref.ref_class,
                        "ref_id": ref.ref_id,
                        "logical_hash": ref.logical_hash,
                    }
                    for ref in evidence.refs
                ],
                "details": [list(item) for item in evidence.details],
            },
            algorithm_versions={
                "metric_code": metric_by_evidence[evidence.evidence_set_id].metric_code,
                "compute_version": metric_by_evidence[evidence.evidence_set_id].compute_version,
            },
        )
        for evidence in release.evidence_sets
    )
    metric_instances = tuple(
        CoreMetricInstanceRecord(
            metric_instance_id=item.metric_instance_id,
            metric_definition_id=item.metric_definition_id,
            metric_code=item.metric_code,
            episode_id=item.episode_id,
            stage_id=item.stage_id,
            subject_entity_id=item.subject_entity_id,
            value_numeric=item.value_numeric,
            value_structured=(
                None
                if item.value_structured_json is None
                else json.loads(item.value_structured_json)
            ),
            unit=item.unit,
            status=item.status,
            reason_codes=item.reason_codes,
            coverage=observation_by_metric[item.metric_instance_id].coverage,
            confidence=observation_by_metric[item.metric_instance_id].confidence,
            evidence_set_id=item.evidence_set_id,
            context_id=item.context_id,
            world_product_versions={
                "world_product_id": item.world_product_id,
                "logical_hash": item.world_logical_hash,
            },
            compute_version=item.compute_version,
            input_hash=item.input_hash,
        )
        for item in release.metric_instances
    )
    observations = tuple(
        CoreObservationRecord(
            observation_id=item.observation_id,
            episode_id=item.episode_id,
            stage_id=item.stage_id,
            aircraft_id=item.identity.aircraft_id,
            aircraft_instance_id=item.identity.aircraft_instance_id,
            subject_entity_id=item.identity.subject_entity_id,
            aircraft_model_id=item.identity.aircraft_model_id,
            context_id=item.context_id,
            capability_dimension=item.identity.capability_dimension,
            capability_type=item.identity.capability_type,
            observed_metric_instance_id=item.metric_instance_id,
            observed_value_numeric=item.value_numeric,
            observed_value_structured=(
                None
                if item.value_structured_json is None
                else json.loads(item.value_structured_json)
            ),
            unit=item.unit,
            observation_start_session_time_us=item.observation_start_session_time_us,
            observation_end_session_time_us=item.observation_end_session_time_us,
            evidence_set_id=item.evidence_set_id,
            coverage=item.coverage,
            confidence=item.confidence,
            eligibility_status=item.eligibility_status,
            exclusion_reason_code=item.exclusion_reason_code,
            comparison_key_hash=item.comparison_key_hash,
            observation_schema_version=item.observation_schema_version,
        )
        for item in release.observations
    )
    return CorePublicationBundle(
        release_id=release.release_id,
        release_no=release.release_no,
        parent_release_id=release.parent_release_id,
        request_hash=release.request_hash,
        session_id=release.session_id,
        context_id=release.context_id,
        context_version=release.context_version,
        context_binding_hash=release.context_binding_hash,
        catalog_version=release.catalog_version,
        catalog_hash=release.catalog_hash,
        manifest_hash=release.manifest_hash,
        definitions=tuple(
            CoreMetricDefinitionRef(
                metric_definition_id=item.metric_definition_id,
                metric_code=item.metric_code,
                catalog_version=item.catalog_version,
                catalog_hash=item.catalog_hash,
                metric_semantic_id=item.semantic_id,
                metric_semantic_version=item.semantic_version,
                subject_type=item.subject_type,
                observation_lane=item.observation_lane,
                publication_route=item.publication_route,
                definition_hash=item.definition_hash,
            )
            for item in release.definitions
        ),
        evidence_sets=evidence_sets,
        metric_instances=metric_instances,
        observations=observations,
    )


class M1PublicationService:
    """Application orchestration over exact Batch 1 products and repository ports."""

    def __init__(
        self,
        *,
        fixture_root: Path,
        authority_root: Path,
        repository: SessionPublicationRepository,
    ) -> None:
        self._fixture_root = fixture_root
        self._authority_root = authority_root
        self._repository = repository
        self._command_lock = threading.Lock()
        self._command_results: dict[
            tuple[str, str],
            tuple[str, dict[str, object]],
        ] = {}

    def _bundle_path(self, fixture_id: str) -> Path:
        if not fixture_id or "/" in fixture_id or "\\" in fixture_id or ".." in fixture_id:
            raise M1ApplicationError("M1_FIXTURE_ID_INVALID", fixture_id)
        path = self._fixture_root / fixture_id
        if not path.is_dir():
            raise M1ApplicationError("M1_FIXTURE_NOT_FOUND", fixture_id)
        return path


    def _idempotent_command(
        self,
        *,
        command: str,
        idempotency_key: str,
        payload: dict[str, object],
        execute: Callable[[], dict[str, object]],
    ) -> dict[str, object]:
        if not idempotency_key.strip():
            raise M1ApplicationError("IDEMPOTENCY_KEY_REQUIRED", "")
        request_hash = canonical_request_hash(payload)
        key = (command, idempotency_key)
        with self._command_lock:
            prior = self._command_results.get(key)
            if prior is not None:
                prior_hash, prior_result = prior
                if prior_hash != request_hash:
                    raise M1ApplicationError("IDEMPOTENCY_KEY_CONFLICT", idempotency_key)
                return {**prior_result, "request_hash": request_hash, "reused": True}

            result = execute()
            stored = {**result, "request_hash": request_hash, "reused": False}
            self._command_results[key] = (request_hash, stored)
            return dict(stored)

    def import_session(
        self,
        *,
        fixture_id: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "command": "M1_IMPORT_SESSION",
            "fixture_id": fixture_id,
        }

        def execute() -> dict[str, object]:
            bundle = load_synthetic_fixture_bundle(self._bundle_path(fixture_id))
            return {
                "command": "M1_IMPORT_SESSION",
                "fixture_id": bundle.identity.fixture_id,
                "fixture_version": bundle.identity.fixture_version,
                "session_id": bundle.session.session_id,
                "aircraft_id": bundle.aircraft.aircraft_id,
                "source_ref": bundle.identity.stable_source_ref,
                "input_sha256": bundle.identity.input_sha256,
                "source_sha256": bundle.identity.source_sha256,
                "context_sha256": bundle.identity.context_sha256,
                "source_row_count": len(bundle.rows),
                "status": "VALIDATED",
            }

        return self._idempotent_command(
            command="M1_IMPORT_SESSION",
            idempotency_key=idempotency_key,
            payload=payload,
            execute=execute,
        )

    def compute_session(
        self,
        *,
        fixture_id: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "command": "M1_COMPUTE_SESSION",
            "fixture_id": fixture_id,
        }

        def execute() -> dict[str, object]:
            bundle_path = self._bundle_path(fixture_id)
            bundle = load_synthetic_fixture_bundle(bundle_path)
            request_hash = canonical_request_hash(payload)
            candidate_release_id = allocate_session_release_id(
                session_id=bundle.session.session_id,
                request_hash=request_hash,
            )
            world = project_minimal_p1_world(
                bundle_path,
                authority_root=self._authority_root,
                release_id=candidate_release_id,
            )
            context = build_metric_context(
                bundle_path,
                authority_root=self._authority_root,
                world=world,
            )
            batch = compute_representative_metrics(context, world)
            return {
                "command": "M1_COMPUTE_SESSION",
                "fixture_id": fixture_id,
                "candidate_release_id": candidate_release_id,
                "session_id": world.session_id,
                "context_id": context.context_id,
                "metric_context_id": context.metric_context_id,
                "world_product_id": world.world_product_id,
                "world_logical_hash": world.logical_content_hash,
                "metric_batch_hash": batch.logical_hash,
                "metric_results": [
                    {
                        "metric_code": item.metric_code,
                        "status": item.status,
                        "logical_hash": item.logical_hash,
                    }
                    for item in batch.results
                ],
                "database_persistence_executed": batch.database_persistence_executed,
                "publication_executed": batch.publication_executed,
                "status": batch.staging_status,
            }

        return self._idempotent_command(
            command="M1_COMPUTE_SESSION",
            idempotency_key=idempotency_key,
            payload=payload,
            execute=execute,
        )

    def publish_session(
        self,
        command: M1PublishSessionCommand,
        *,
        idempotency_key: str,
    ) -> M1PublishSessionResult:
        if command.expected_version_token < 0:
            raise M1ApplicationError(
                "M1_EXPECTED_VERSION_TOKEN_INVALID",
                str(command.expected_version_token),
            )
        if not idempotency_key.strip():
            raise M1ApplicationError("IDEMPOTENCY_KEY_REQUIRED", "")

        bundle_path = self._bundle_path(command.fixture_id)
        bundle = load_synthetic_fixture_bundle(bundle_path)
        request_hash = canonical_request_hash(command.request_payload())
        release_id = allocate_session_release_id(
            session_id=bundle.session.session_id,
            request_hash=request_hash,
        )

        try:
            reused = self._repository.idempotency_lookup(
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
        except PublishIdempotencyConflict as exc:
            raise M1ApplicationError("IDEMPOTENCY_KEY_CONFLICT", str(exc)) from exc
        if reused is not None:
            return M1PublishSessionResult(
                release_id=reused.release.release_id,
                session_id=reused.release.session_id,
                request_hash=reused.release.request_hash,
                manifest_hash=reused.release.manifest_hash,
                status=reused.status,
                version_token=reused.version_token,
                reused=True,
            )

        if command.expected_version_token == 0:
            parent_release_id = None
        else:
            current = self._repository.current(bundle.session.session_id)
            if current is None or current.version_token != command.expected_version_token:
                actual = 0 if current is None else current.version_token
                raise M1ApplicationError(
                    "PUBLISH_CAS_CONFLICT",
                    f"expected={command.expected_version_token} actual={actual}",
                )
            parent_release_id = current.release.release_id

        world = project_minimal_p1_world(
            bundle_path,
            authority_root=self._authority_root,
            release_id=release_id,
        )
        context = build_metric_context(
            bundle_path,
            authority_root=self._authority_root,
            world=world,
        )
        resolved_context = resolve_evaluation_context(
            bundle_path,
            authority_root=self._authority_root,
        )
        batch = compute_representative_metrics(context, world)
        context_snapshot: EvaluationContextDTO = {
            "context_id": resolved_context.context_id,
            "session_id": resolved_context.session_id,
            "context_version": resolved_context.context_version,
            "revision_no": resolved_context.revision_no,
            "rule_set_version": resolved_context.rule_set_version,
            "metric_profile_version": resolved_context.metric_profile_version,
            "status": resolved_context.status,
        }
        if resolved_context.supersedes_context_id is not None:
            context_snapshot["supersedes_context_id"] = resolved_context.supersedes_context_id
        identity = AircraftPublicationIdentity(
            aircraft_id=world.aircraft_id,
            aircraft_model_id=command.aircraft_model_id,
            aircraft_instance_id=command.aircraft_instance_id,
            subject_entity_id=command.subject_entity_id,
            capability_dimension=command.capability_dimension,
            capability_type=command.capability_type,
        )
        try:
            release = build_session_release(
                release_id=release_id,
                request_hash=request_hash,
                release_no=command.expected_version_token + 1,
                parent_release_id=parent_release_id,
                context=context,
                context_version=resolved_context.context_version,
                context_projection=context_snapshot,
                world=world,
                batch=batch,
                identity=identity,
            )
            result = self._repository.publish(
                release,
                idempotency_key=idempotency_key,
                expected_version_token=command.expected_version_token,
            )
        except PublishCASConflict as exc:
            raise M1ApplicationError("PUBLISH_CAS_CONFLICT", str(exc)) from exc
        except PublishIdempotencyConflict as exc:
            raise M1ApplicationError("IDEMPOTENCY_KEY_CONFLICT", str(exc)) from exc
        except PublicationError as exc:
            raise M1ApplicationError(exc.code, exc.detail) from exc

        return M1PublishSessionResult(
            release_id=result.published.release.release_id,
            session_id=result.published.release.session_id,
            request_hash=result.published.release.request_hash,
            manifest_hash=result.published.release.manifest_hash,
            status=result.published.status,
            version_token=result.published.version_token,
            reused=result.reused,
        )

    def _release(self, release_id: str) -> PublishedSessionRelease:
        try:
            return self._repository.get_release(release_id)
        except ReleaseNotFound as exc:
            raise M1ApplicationError("RELEASE_NOT_FOUND", release_id) from exc

    def _release_provenance(self, release: SessionRelease) -> dict[str, object]:
        return {
            "fixture_id": release.fixture_id,
            "session_id": release.session_id,
            "context": {
                "context_id": release.context_id,
                "context_version": release.context_version,
                "context_binding_hash": release.context_binding_hash,
            },
            "catalog": {
                "catalog_version": release.catalog_version,
                "catalog_hash": release.catalog_hash,
            },
            "world": {
                "world_product_id": release.world_product_id,
                "world_logical_hash": release.world_logical_hash,
            },
            "request_hash": release.request_hash,
            "manifest_hash": release.manifest_hash,
        }

    def release_summary(self, release_id: str) -> dict[str, object]:
        published = self._release(release_id)
        release = published.release
        return {
            "release_id": release.release_id,
            "release_no": release.release_no,
            "parent_release_id": release.parent_release_id,
            "fixture_id": release.fixture_id,
            "scope_type": release.scope_type,
            "scope_key": release.scope_key,
            "session_id": release.session_id,
            "context_id": release.context_id,
            "context_version": release.context_version,
            "context_binding_hash": release.context_binding_hash,
            "catalog_version": release.catalog_version,
            "catalog_hash": release.catalog_hash,
            "world_product_id": release.world_product_id,
            "world_logical_hash": release.world_logical_hash,
            "manifest_hash": release.manifest_hash,
            "request_hash": release.request_hash,
            "status": published.status,
            "version_token": published.version_token,
            "identity": {
                "release_id": release.release_id,
                "scope_type": release.scope_type,
                "scope_key": release.scope_key,
                "release_no": release.release_no,
                "parent_release_id": release.parent_release_id,
            },
            "provenance": self._release_provenance(release),
        }

    def observations(self, release_id: str) -> list[CapabilityObservationDTO]:
        release = self._release(release_id).release
        return [item.dto() for item in release.observations]

    def metric_list(self, release_id: str) -> list[dict[str, object]]:
        release = self._release(release_id).release
        definitions = {item.metric_code: item for item in release.definitions}
        return [
            {
                "metric_instance_id": item.metric_instance_id,
                "metric_code": item.metric_code,
                "definition_hash": definitions[item.metric_code].definition_hash,
                "status": item.status,
                "unit": item.unit,
                "value_kind": item.value_kind,
                "release_id": release.release_id,
            }
            for item in release.metric_instances
        ]

    def metric_detail(self, release_id: str, metric_code: str) -> dict[str, object]:
        release = self._release(release_id).release
        instance = next(
            (item for item in release.metric_instances if item.metric_code == metric_code),
            None,
        )
        definition = next(
            (item for item in release.definitions if item.metric_code == metric_code),
            None,
        )
        if instance is None or definition is None:
            raise M1ApplicationError("METRIC_NOT_FOUND", metric_code)
        evidence = next(
            item for item in release.evidence_sets if item.evidence_set_id == instance.evidence_set_id
        )
        return {
            "release_id": release.release_id,
            "metric_instance_id": instance.metric_instance_id,
            "metric_code": instance.metric_code,
            "status": instance.status,
            "reason_codes": list(instance.reason_codes),
            "unit": instance.unit,
            "value_kind": instance.value_kind,
            "value": instance.value(),
            "definition": {
                "metric_definition_id": definition.metric_definition_id,
                "semantic_id": definition.semantic_id,
                "semantic_version": definition.semantic_version,
                "algorithm_id": definition.algorithm_id,
                "algorithm_version": definition.algorithm_version,
                "publication_route": definition.publication_route,
                "catalog_version": definition.catalog_version,
                "catalog_hash": definition.catalog_hash,
                "definition_hash": definition.definition_hash,
            },
            "evidence": {
                "evidence_set_id": evidence.evidence_set_id,
                "logical_hash": evidence.logical_hash,
                "refs": [
                    {
                        "ref_class": ref.ref_class,
                        "ref_id": ref.ref_id,
                        "logical_hash": ref.logical_hash,
                    }
                    for ref in evidence.refs
                ],
                "details": [list(item) for item in evidence.details],
            },
        }

    def metric_evidence(self, release_id: str, metric_code: str) -> dict[str, object]:
        release = self._release(release_id).release
        instance = next(
            (item for item in release.metric_instances if item.metric_code == metric_code),
            None,
        )
        definition = next(
            (item for item in release.definitions if item.metric_code == metric_code),
            None,
        )
        if instance is None or definition is None:
            raise M1ApplicationError("METRIC_NOT_FOUND", metric_code)
        evidence = next(
            item for item in release.evidence_sets if item.evidence_set_id == instance.evidence_set_id
        )
        return {
            "release_id": release.release_id,
            "metric_instance_id": instance.metric_instance_id,
            "metric_code": instance.metric_code,
            "metric_definition_id": definition.metric_definition_id,
            "definition_hash": definition.definition_hash,
            "evidence_set_id": evidence.evidence_set_id,
            "logical_hash": evidence.logical_hash,
            "refs": [
                {
                    "ref_class": ref.ref_class,
                    "ref_id": ref.ref_id,
                    "logical_hash": ref.logical_hash,
                }
                for ref in evidence.refs
            ],
            "details": [list(item) for item in evidence.details],
        }

    def context_projection(self, release_id: str) -> EvaluationContextDTO:
        release = self._release(release_id).release
        return release.context_dto()

    def session_episode_stage_projection(
        self,
        release_id: str,
    ) -> M1SessionEpisodeStageProjection:
        release = self._release(release_id).release
        world = self._replay_world(release_id)
        stages: list[M1StageProjection] = []
        for stage in world.stages:
            stages.append(
                {
                    "stage_id": stage.stage_id,
                    "episode_id": stage.episode_id,
                    "stage_type": stage.stage_type,
                    "stage_order": stage.stage_order,
                    "start_session_time_us": str(stage.start_session_time_us),
                    "end_session_time_us": str(stage.end_session_time_us),
                    "stage_status": stage.stage_status,
                    "coverage": stage.coverage,
                    "confidence": stage.confidence,
                    "detector_version": stage.detector_version,
                }
            )
        return {
            "release_id": release.release_id,
            "session": {
                "session_id": world.session_id,
                "start_session_time_us": str(world.start_session_time_us),
                "end_session_time_us": str(world.end_session_time_us),
            },
            "episode": {
                "episode_id": world.episode_id,
                "session_id": world.session_id,
            },
            "stages": stages,
        }

    def _replay_world(self, release_id: str) -> AircraftObservedWorld:
        release = self._release(release_id).release
        world = project_minimal_p1_world(
            self._bundle_path(release.fixture_id),
            authority_root=self._authority_root,
            release_id=release.release_id,
        )
        if (
            world.world_product_id != release.world_product_id
            or world.logical_content_hash != release.world_logical_hash
        ):
            raise M1ApplicationError("HISTORICAL_WORLD_DRIFT", release.release_id)
        return world

    def replay(self, release_id: str) -> dict[str, object]:
        published = self._release(release_id)
        release = published.release
        bundle_path = self._bundle_path(release.fixture_id)
        world = self._replay_world(release_id)
        context = build_metric_context(
            bundle_path,
            authority_root=self._authority_root,
            world=world,
        )
        resolved = resolve_evaluation_context(bundle_path, authority_root=self._authority_root)
        batch = compute_representative_metrics(context, world)
        comparison = compare_replay(
            release,
            context=context,
            context_version=resolved.context_version,
            world=world,
            batch=batch,
        )
        return {
            "release_id": release.release_id,
            "release_status": published.status,
            "status": "PASS" if comparison.exact_logical_products_equal else "FAIL",
            "provenance": self._release_provenance(release),
            "world_equal": comparison.world_equal,
            "metric_batch_equal": comparison.metric_batch_equal,
            "context_equal": comparison.context_equal,
            "exact_logical_products_equal": comparison.exact_logical_products_equal,
            "current_latest_fallback_used": False,
        }

    def series_range(
        self,
        release_id: str,
        *,
        start_session_time_us: int,
        end_session_time_us: int,
        limit: int,
    ) -> dict[str, object]:
        if start_session_time_us >= end_session_time_us:
            raise M1ApplicationError("SERIES_RANGE_INVALID", "start must be < end")
        if not 1 <= limit <= 5000:
            raise M1ApplicationError("SERIES_LIMIT_INVALID", str(limit))
        world = self._replay_world(release_id)
        selected = [
            row
            for row in world.canonical_rows
            if start_session_time_us <= row.session_time_us < end_session_time_us
        ][:limit]
        return {
            "release_id": release_id,
            "start_session_time_us": str(start_session_time_us),
            "end_session_time_us": str(end_session_time_us),
            "limit": limit,
            "returned": len(selected),
            "rows": [
                {
                    "session_time_us": str(row.session_time_us),
                    "body_p_rad_s": row.body_p_rad_s,
                    "nz_g": row.nz_g,
                    "heading_true_rad": row.heading_true_rad,
                    "tas_mps": row.tas_mps,
                    "mach": row.mach,
                    "quality_mask": row.quality_mask,
                }
                for row in selected
            ],
        }
