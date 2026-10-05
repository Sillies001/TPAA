"""PRCB durable P1 exact-release reads over the qualified Core publication ledger."""

from __future__ import annotations

from typing import cast

from tpaa_application.m1_publication import (
    M1ApplicationError,
    M1PublishSessionCommand,
    M1PublishSessionResult,
    M1SessionEpisodeStageProjection,
)
from tpaa_generated.dto import CapabilityObservationDTO, EvaluationContextDTO
from tpaa_storage.core_publication_ledger import CorePublicationLedgerError

from .durable_repositories import RuntimeUnitOfWorkFactory

_DEFINITION_COLUMNS = (
    "metric_definition_id",
    "metric_code",
    "version",
    "catalog_version",
    "catalog_hash",
    "metric_semantic_id",
    "metric_semantic_version",
    "subject_type",
    "observation_lane",
    "publication_route",
    "definition_hash",
    "plugin_name",
    "plugin_version",
)


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise M1ApplicationError("P1_DURABLE_ROW_INVALID", field)
    return {str(key): item for key, item in value.items()}


def _rows(value: object, *, field: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise M1ApplicationError("P1_DURABLE_ROW_INVALID", field)
    return [
        _mapping(item, field=f"{field}[{index}]")
        for index, item in enumerate(value)
    ]


def _required_text(row: dict[str, object], field: str) -> str:
    value = row.get(field)
    if value is None:
        raise M1ApplicationError("P1_DURABLE_FIELD_MISSING", field)
    return str(value)


def _optional_text(row: dict[str, object], field: str) -> str | None:
    value = row.get(field)
    return None if value is None else str(value)


def _required_int(row: dict[str, object], field: str) -> int:
    value = row.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise M1ApplicationError("P1_DURABLE_FIELD_INVALID", field)
    return value


def _required_float(row: dict[str, object], field: str) -> float:
    value = row.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise M1ApplicationError("P1_DURABLE_FIELD_INVALID", field)
    return float(value)


class DurableP1ReleaseReadService:
    """Exact P1 DB reads while C2 production ingest/compute remains fail-closed."""

    def __init__(self, read_uow_factory: RuntimeUnitOfWorkFactory) -> None:
        self._read_uow_factory = read_uow_factory

    @staticmethod
    def _c2_required(action: str) -> M1ApplicationError:
        return M1ApplicationError(
            "P1_PRODUCTION_COMMAND_NOT_CONFIGURED",
            f"{action} requires PRCB C2 production ingest/worker wiring",
        )

    def import_session(
        self,
        *,
        fixture_id: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        del fixture_id, idempotency_key
        raise self._c2_required("import_session")

    def compute_session(
        self,
        *,
        fixture_id: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        del fixture_id, idempotency_key
        raise self._c2_required("compute_session")

    def publish_session(
        self,
        command: M1PublishSessionCommand,
        *,
        idempotency_key: str,
    ) -> M1PublishSessionResult:
        del command, idempotency_key
        raise self._c2_required("publish_session")

    def _snapshot(
        self,
        release_id: str,
    ) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
        try:
            with self._read_uow_factory() as uow:
                membership = uow.publication.logical_membership(release_id)
                definitions = uow.canonical_rows.many(
                    "metric.metric_definition",
                    where={},
                    columns=_DEFINITION_COLUMNS,
                    order_by=("metric_code",),
                )
                uow.commit()
        except CorePublicationLedgerError as exc:
            if exc.code == "RELEASE_CARDINALITY":
                raise M1ApplicationError("RELEASE_NOT_FOUND", release_id) from exc
            raise M1ApplicationError(exc.code, exc.detail) from exc
        by_id = {
            _required_text(row, "metric_definition_id"): row
            for row in definitions
        }
        return membership, by_id

    @staticmethod
    def _definition(
        definitions: dict[str, dict[str, object]],
        metric_definition_id: str,
    ) -> dict[str, object]:
        row = definitions.get(metric_definition_id)
        if row is None:
            raise M1ApplicationError(
                "P1_METRIC_DEFINITION_NOT_FOUND",
                metric_definition_id,
            )
        return row

    @staticmethod
    def _context_ref(
        membership: dict[str, object],
    ) -> dict[str, object]:
        refs = _rows(membership.get("context_refs"), field="context_refs")
        if len(refs) != 1:
            release = _mapping(membership.get("release"), field="release")
            raise M1ApplicationError(
                "P1_CONTEXT_BINDING_CARDINALITY",
                _required_text(release, "release_id"),
            )
        return refs[0]

    def release_summary(self, release_id: str) -> dict[str, object]:
        membership, _ = self._snapshot(release_id)
        release = _mapping(membership.get("release"), field="release")
        context_ref = self._context_ref(membership)
        metrics = _rows(membership.get("metric_instances"), field="metric_instances")
        return {
            **release,
            "context_id": _required_text(context_ref, "context_id"),
            "context_version": _required_text(context_ref, "context_version"),
            "metric_count": len(metrics),
            "durable_authority": "DB_1_9_CORE_PUBLICATION_LEDGER",
            "production_compute_configured": False,
        }

    def observations(self, release_id: str) -> list[CapabilityObservationDTO]:
        membership, definitions = self._snapshot(release_id)
        release = _mapping(membership.get("release"), field="release")
        metric_definition_by_instance: dict[str, dict[str, object]] = {}
        for metric in _rows(
            membership.get("metric_instances"),
            field="metric_instances",
        ):
            definition_id = _required_text(metric, "metric_definition_id")
            metric_definition_by_instance[
                _required_text(metric, "metric_instance_id")
            ] = self._definition(definitions, definition_id)

        result: list[CapabilityObservationDTO] = []
        for row in _rows(membership.get("observations"), field="observations"):
            metric_id = _required_text(row, "observed_metric_instance_id")
            definition = metric_definition_by_instance.get(metric_id)
            if definition is None:
                raise M1ApplicationError(
                    "P1_OBSERVATION_METRIC_NOT_FOUND",
                    metric_id,
                )
            structured = row.get("observed_value_structured")
            numeric = row.get("observed_value_numeric")
            payload: dict[str, object] = {
                "release_id": _required_text(release, "release_id"),
                "session_id": _required_text(release, "session_id"),
                "observation_id": _required_text(row, "observation_id"),
                "episode_id": _required_text(row, "episode_id"),
                "stage_id": _optional_text(row, "stage_id"),
                "aircraft_id": _required_text(row, "aircraft_id"),
                "aircraft_instance_id": _required_text(row, "aircraft_instance_id"),
                "subject_entity_id": _required_text(row, "subject_entity_id"),
                "aircraft_model_id": _required_text(row, "aircraft_model_id"),
                "context_id": _required_text(row, "context_id"),
                "capability_dimension": _required_text(row, "capability_dimension"),
                "capability_type": _required_text(row, "capability_type"),
                "capability_level": _required_text(row, "capability_level"),
                "observed_metric_instance_id": metric_id,
                "metric_code": _required_text(definition, "metric_code"),
                "metric_semantic_id": _required_text(
                    definition,
                    "metric_semantic_id",
                ),
                "metric_semantic_version": _required_int(
                    definition,
                    "metric_semantic_version",
                ),
                "unit": _required_text(row, "unit"),
                "observation_start_session_time_us": str(
                    _required_int(row, "observation_start_session_time_us")
                ),
                "observation_end_session_time_us": str(
                    _required_int(row, "observation_end_session_time_us")
                ),
                "context_tags": {},
                "evidence_set_id": _required_text(row, "evidence_set_id"),
                "coverage": _required_float(row, "coverage"),
                "confidence": _required_float(row, "confidence"),
                "eligibility_status": _required_text(row, "eligibility_status"),
                "exclusion_reason_code": _optional_text(
                    row,
                    "exclusion_reason_code",
                ),
                "comparison_key_hash": _required_text(
                    row,
                    "comparison_key_hash",
                ),
                "observation_schema_version": _required_text(
                    row,
                    "observation_schema_version",
                ),
                "value_kind": "STRUCTURED" if structured is not None else "NUMERIC",
                "value": structured if structured is not None else numeric,
            }
            result.append(cast(CapabilityObservationDTO, payload))
        return result

    def metric_list(self, release_id: str) -> list[dict[str, object]]:
        membership, definitions = self._snapshot(release_id)
        release = _mapping(membership.get("release"), field="release")
        result: list[dict[str, object]] = []
        for row in _rows(
            membership.get("metric_instances"),
            field="metric_instances",
        ):
            definition = self._definition(
                definitions,
                _required_text(row, "metric_definition_id"),
            )
            result.append(
                {
                    "release_id": _required_text(release, "release_id"),
                    "metric_instance_id": _required_text(
                        row,
                        "metric_instance_id",
                    ),
                    "metric_code": _required_text(definition, "metric_code"),
                    "definition_hash": _required_text(
                        definition,
                        "definition_hash",
                    ),
                    "status": _required_text(row, "status"),
                    "unit": _required_text(row, "unit"),
                    "value_kind": (
                        "STRUCTURED"
                        if row.get("value_structured") is not None
                        else "NUMERIC"
                    ),
                }
            )
        return sorted(result, key=lambda item: str(item["metric_code"]))

    def _metric(
        self,
        release_id: str,
        metric_code: str,
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        membership, definitions = self._snapshot(release_id)
        evidence_by_id = {
            _required_text(row, "evidence_set_id"): row
            for row in _rows(
                membership.get("evidence_sets"),
                field="evidence_sets",
            )
        }
        for row in _rows(
            membership.get("metric_instances"),
            field="metric_instances",
        ):
            definition = self._definition(
                definitions,
                _required_text(row, "metric_definition_id"),
            )
            if _required_text(definition, "metric_code") != metric_code:
                continue
            evidence_id = _required_text(row, "evidence_set_id")
            evidence = evidence_by_id.get(evidence_id)
            if evidence is None:
                raise M1ApplicationError(
                    "P1_EVIDENCE_NOT_FOUND",
                    evidence_id,
                )
            return row, definition, evidence
        raise M1ApplicationError("METRIC_NOT_FOUND", metric_code)

    def metric_detail(
        self,
        release_id: str,
        metric_code: str,
    ) -> dict[str, object]:
        row, definition, evidence = self._metric(release_id, metric_code)
        structured = row.get("value_structured")
        return {
            "release_id": release_id,
            "metric_instance_id": _required_text(row, "metric_instance_id"),
            "metric_code": metric_code,
            "status": _required_text(row, "status"),
            "reason_codes": row.get("reason_codes", []),
            "unit": _required_text(row, "unit"),
            "value_kind": "STRUCTURED" if structured is not None else "NUMERIC",
            "value": structured if structured is not None else row.get("value_numeric"),
            "definition": {
                "metric_definition_id": _required_text(
                    definition,
                    "metric_definition_id",
                ),
                "semantic_id": _required_text(
                    definition,
                    "metric_semantic_id",
                ),
                "semantic_version": _required_int(
                    definition,
                    "metric_semantic_version",
                ),
                "algorithm_id": _required_text(definition, "plugin_name"),
                "algorithm_version": _required_text(
                    definition,
                    "plugin_version",
                ),
                "publication_route": _required_text(
                    definition,
                    "publication_route",
                ),
                "catalog_version": _required_text(
                    definition,
                    "catalog_version",
                ),
                "catalog_hash": _required_text(definition, "catalog_hash"),
                "definition_hash": _required_text(
                    definition,
                    "definition_hash",
                ),
            },
            "evidence": {
                "evidence_set_id": _required_text(
                    evidence,
                    "evidence_set_id",
                ),
                "series_locator": evidence.get("series_locator"),
                "algorithm_versions": evidence.get("algorithm_versions"),
            },
        }

    def metric_evidence(
        self,
        release_id: str,
        metric_code: str,
    ) -> dict[str, object]:
        row, definition, evidence = self._metric(release_id, metric_code)
        return {
            "release_id": release_id,
            "metric_instance_id": _required_text(row, "metric_instance_id"),
            "metric_code": metric_code,
            "metric_definition_id": _required_text(
                definition,
                "metric_definition_id",
            ),
            "definition_hash": _required_text(definition, "definition_hash"),
            "evidence_set_id": _required_text(evidence, "evidence_set_id"),
            "series_locator": evidence.get("series_locator"),
            "algorithm_versions": evidence.get("algorithm_versions"),
        }

    def context_projection(self, release_id: str) -> EvaluationContextDTO:
        membership, _ = self._snapshot(release_id)
        ref = self._context_ref(membership)
        context_id = _required_text(ref, "context_id")
        with self._read_uow_factory() as uow:
            row = uow.canonical_rows.one(
                "context.evaluation_context",
                where={"context_id": context_id},
                columns=(
                    "context_id",
                    "session_id",
                    "context_version",
                    "revision_no",
                    "supersedes_context_id",
                    "scenario_id",
                    "scenario_version",
                    "syllabus_id",
                    "syllabus_version",
                    "assessment_profile_id",
                    "assessment_profile_version",
                    "rule_set_version",
                    "reference_set_version",
                    "role_model_version",
                    "metric_profile_version",
                    "longitudinal_profile_version",
                    "valid_from_session_time_us",
                    "valid_to_session_time_us",
                    "status",
                ),
            )
            uow.commit()
        if row is None:
            raise M1ApplicationError("P1_CONTEXT_NOT_FOUND", context_id)
        payload = dict(row)
        for field in ("valid_from_session_time_us", "valid_to_session_time_us"):
            if payload.get(field) is not None:
                payload[field] = str(payload[field])
        return cast(EvaluationContextDTO, payload)

    def session_episode_stage_projection(
        self,
        release_id: str,
    ) -> M1SessionEpisodeStageProjection:
        del release_id
        raise M1ApplicationError(
            "P1_PRODUCTION_TOPOLOGY_NOT_CONFIGURED",
            "release-bound topology reconstruction is deferred to PRCB C2/C4",
        )

    def replay(self, release_id: str) -> dict[str, object]:
        del release_id
        raise self._c2_required("replay")

    def series_range(
        self,
        release_id: str,
        *,
        start_session_time_us: int,
        end_session_time_us: int,
        limit: int,
    ) -> dict[str, object]:
        del release_id, start_session_time_us, end_session_time_us, limit
        raise self._c2_required("series_range")
