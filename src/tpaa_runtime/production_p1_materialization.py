"""Materialize the exact P1 Catalog execution into DB 1.9 release records.

The Catalog engine owns business semantics.  This module owns only deterministic
publication identity, route mapping and immutable evidence linkage.  It never
recomputes Metric values and it never invents a subject identity.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast
from uuid import UUID, uuid5

from tpaa_metric import M2MetricExecutionBatch
from tpaa_storage.publication_bundle import (
    CoreEvidenceRecord,
    CoreMetricDefinitionRef,
    CoreMetricInstanceRecord,
    CoreObservationRecord,
    CorePublicationBundle,
    CoreSystemObservationRecord,
    CoreTpaaMChainRecord,
    CoreWorldProductRecord,
    CoreWorldRelationRecord,
)

from .production_p1_catalog import ProductionP1CatalogContract

_DEFINITION_NAMESPACE = UUID("2659c1c2-4acf-41c1-9150-90de8cf48d72")
_EVIDENCE_NAMESPACE = UUID("c376f1a5-3415-49ce-ad5f-383807832d0c")
_INSTANCE_NAMESPACE = UUID("950a8296-980a-4fd5-a22c-597f2198fb8e")
_OBSERVATION_NAMESPACE = UUID("cb0d57f1-f9f9-4126-a6d7-a2fb45dd3815")
_SYSTEM_OBSERVATION_NAMESPACE = UUID("f3cbbf9a-0455-4593-9cb9-9e2158b9cd38")

_ALLOWED_ROUTES = {
    "CAPABILITY_OBSERVATION",
    "SYSTEM_PERFORMANCE_OBSERVATION",
    "METRIC_INSTANCE_EVIDENCE_ONLY",
}


class ProductionP1MaterializationError(RuntimeError):
    """Fail-closed P1 publication materialization error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True, slots=True)
class ProductionP1AircraftBinding:
    aircraft_id: str
    aircraft_model_id: str
    aircraft_instance_id: str
    subject_entity_id: str
    capability_dimension: str
    capability_type: str


@dataclass(frozen=True, slots=True)
class ProductionP1SystemBinding:
    mission_system_instance_id: str
    aircraft_id: str
    reference_truth_profile_version: str | None
    reference_quality_status: str
    reference_uncertainty_summary: Mapping[str, object]
    alignment_uncertainty_summary: Mapping[str, object]
    context_tags: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ProductionP1ReleaseContext:
    release_id: str
    release_no: int
    parent_release_id: str | None
    request_hash: str
    session_id: str
    context_id: str
    context_version: str
    context_binding_hash: str
    episode_id: str
    stage_id: str | None
    start_session_time_us: int
    end_session_time_us: int
    coverage: float
    confidence: float
    observation_schema_version: str
    world_product_versions: Mapping[str, object]
    world_product_ids: tuple[str, ...] = ()
    relation_ids: tuple[str, ...] = ()


def _json_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _require_uuid(value: str, *, field: str) -> None:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise ProductionP1MaterializationError(
            "ED2_P1_PUBLICATION_IDENTITY_INVALID",
            field,
        ) from exc
    if parsed.int == 0 or str(parsed) != value:
        raise ProductionP1MaterializationError(
            "ED2_P1_PUBLICATION_IDENTITY_INVALID",
            field,
        )


def _require_hash(value: str, *, field: str) -> None:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ProductionP1MaterializationError(
            "ED2_P1_PUBLICATION_HASH_INVALID",
            field,
        )


def _validate_context(context: ProductionP1ReleaseContext) -> None:
    for field, value in (
        ("release_id", context.release_id),
        ("session_id", context.session_id),
        ("context_id", context.context_id),
        ("episode_id", context.episode_id),
    ):
        _require_uuid(value, field=field)
    if context.stage_id is not None:
        _require_uuid(context.stage_id, field="stage_id")
    if context.parent_release_id is not None:
        _require_uuid(context.parent_release_id, field="parent_release_id")
    _require_hash(context.request_hash, field="request_hash")
    _require_hash(context.context_binding_hash, field="context_binding_hash")
    if context.release_no < 1:
        raise ProductionP1MaterializationError(
            "ED2_P1_RELEASE_NUMBER_INVALID",
            str(context.release_no),
        )
    if context.end_session_time_us <= context.start_session_time_us:
        raise ProductionP1MaterializationError(
            "ED2_P1_PUBLICATION_INTERVAL_INVALID",
            context.release_id,
        )
    for field, value in (
        ("coverage", context.coverage),
        ("confidence", context.confidence),
    ):
        if not 0.0 <= value <= 1.0:
            raise ProductionP1MaterializationError(
                "ED2_P1_PUBLICATION_QUALITY_INVALID",
                field,
            )


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) for key in value
    ):
        raise ProductionP1MaterializationError(
            "ED2_P1_PLUGIN_OUTPUT_INVALID",
            field,
        )
    return cast(Mapping[str, object], value)


def _instances(output: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    raw = output.get("instances")
    if raw is None:
        if "status" not in output:
            raise ProductionP1MaterializationError(
                "ED2_P1_PLUGIN_OUTPUT_INVALID",
                "instances",
            )
        return (output,)
    if not isinstance(raw, list):
        raise ProductionP1MaterializationError(
            "ED2_P1_PLUGIN_OUTPUT_INVALID",
            "instances",
        )
    result: list[Mapping[str, object]] = []
    for index, item in enumerate(raw):
        result.append(_mapping(item, field=f"instances[{index}]"))
    return tuple(result)


def _reason_codes(instance: Mapping[str, object]) -> tuple[str, ...]:
    raw = instance.get("reason_codes")
    if not isinstance(raw, list) or not all(
        isinstance(item, str) and item for item in raw
    ):
        raise ProductionP1MaterializationError(
            "ED2_P1_PLUGIN_OUTPUT_INVALID",
            "reason_codes",
        )
    return tuple(cast(list[str], raw))


def _eligibility(
    status: str,
    reasons: tuple[str, ...],
) -> tuple[str, str | None]:
    if status == "VALID":
        return "ELIGIBLE", None
    if status == "REVIEW_REQUIRED":
        return "REVIEW_REQUIRED", reasons[0] if reasons else "REVIEW_REQUIRED"
    if status in {"N_A", "INSUFFICIENT_DATA", "INVALID"}:
        return "EXCLUDED", reasons[0] if reasons else status
    raise ProductionP1MaterializationError(
        "ED2_P1_PLUGIN_STATUS_UNSUPPORTED",
        status,
    )


def _system_binding(
    *,
    metric_code: str,
    binding_by_metric: Mapping[str, ProductionP1SystemBinding],
    input_payload: Mapping[str, object],
) -> ProductionP1SystemBinding:
    binding = binding_by_metric.get(metric_code)
    if binding is None:
        raise ProductionP1MaterializationError(
            "ED2_P1_SYSTEM_BINDING_MISSING",
            metric_code,
        )
    _require_uuid(
        binding.mission_system_instance_id,
        field=f"{metric_code}.mission_system_instance_id",
    )
    _require_uuid(binding.aircraft_id, field=f"{metric_code}.aircraft_id")
    input_system = input_payload.get("mission_system_instance_id")
    if (
        input_system is not None
        and input_system != binding.mission_system_instance_id
    ):
        raise ProductionP1MaterializationError(
            "ED2_P1_SYSTEM_BINDING_DRIFT",
            metric_code,
        )
    return binding


def materialize_production_p1_release(
    *,
    contract: ProductionP1CatalogContract,
    batch: M2MetricExecutionBatch,
    inputs: Mapping[str, Mapping[str, object]],
    context: ProductionP1ReleaseContext,
    aircraft: ProductionP1AircraftBinding,
    system_bindings: Mapping[str, ProductionP1SystemBinding],
    world_products: tuple[CoreWorldProductRecord, ...] = (),
    world_relations: tuple[CoreWorldRelationRecord, ...] = (),
    tpaa_m_chains: tuple[CoreTpaaMChainRecord, ...] = (),
) -> CorePublicationBundle:
    """Materialize all applicable plugin instances into one immutable Release."""

    _validate_context(context)
    for field, value in (
        ("aircraft_id", aircraft.aircraft_id),
        ("aircraft_model_id", aircraft.aircraft_model_id),
        ("aircraft_instance_id", aircraft.aircraft_instance_id),
        ("subject_entity_id", aircraft.subject_entity_id),
    ):
        _require_uuid(value, field=field)

    if batch.plan_hash != contract.plan.logical_hash:
        raise ProductionP1MaterializationError(
            "ED2_P1_EXECUTION_PLAN_DRIFT",
            batch.plan_hash,
        )
    if batch.metric_codes != contract.metric_codes:
        raise ProductionP1MaterializationError(
            "ED2_P1_EXECUTION_MEMBERSHIP_DRIFT",
            repr(batch.metric_codes),
        )
    if set(inputs) != set(contract.metric_codes):
        raise ProductionP1MaterializationError(
            "ED2_P1_INPUT_MEMBERSHIP_INCOMPLETE",
            str(len(inputs)),
        )

    definitions: list[CoreMetricDefinitionRef] = []
    evidence_sets: list[CoreEvidenceRecord] = []
    metric_instances: list[CoreMetricInstanceRecord] = []
    observations: list[CoreObservationRecord] = []
    system_observations: list[CoreSystemObservationRecord] = []

    definition_by_code = {
        definition.metric_code: definition
        for definition in contract.plan.definitions
    }
    for record in batch.records:
        definition = definition_by_code[record.metric_code]
        if definition.publication_route not in _ALLOWED_ROUTES:
            raise ProductionP1MaterializationError(
                "ED2_P1_PUBLICATION_ROUTE_UNSUPPORTED",
                definition.publication_route,
            )
        definition_id = str(
            uuid5(
                _DEFINITION_NAMESPACE,
                (
                    f"{contract.plan.catalog_sha256}|"
                    f"{definition.metric_code}|{definition.definition_hash}"
                ),
            )
        )
        definitions.append(
            CoreMetricDefinitionRef(
                metric_definition_id=definition_id,
                metric_code=definition.metric_code,
                catalog_version=contract.plan.catalog_version,
                catalog_hash=contract.plan.catalog_sha256,
                metric_semantic_id=definition.semantic_id,
                metric_semantic_version=definition.semantic_version,
                subject_type=definition.subject_type,
                observation_lane=definition.observation_lane,
                publication_route=definition.publication_route,
                definition_hash=definition.definition_hash,
            )
        )

        output = record.plugin_output
        if output is None:
            raise ProductionP1MaterializationError(
                "ED2_P1_PLUGIN_OUTPUT_MISSING",
                record.metric_code,
            )
        if _json_hash(dict(output)) != record.plugin_output_hash:
            raise ProductionP1MaterializationError(
                "ED2_P1_PLUGIN_OUTPUT_HASH_DRIFT",
                record.metric_code,
            )
        applicable = output.get("applicable")
        if applicable is False:
            if _instances(output):
                raise ProductionP1MaterializationError(
                    "ED2_P1_NOT_APPLICABLE_INSTANCE_FORBIDDEN",
                    record.metric_code,
                )
            continue

        input_payload = inputs[record.metric_code]
        if _json_hash(dict(input_payload)) != record.input_payload_hash:
            raise ProductionP1MaterializationError(
                "ED2_P1_INPUT_PAYLOAD_HASH_DRIFT",
                record.metric_code,
            )
        raw_source_lineage = input_payload.get("_source_lineage")
        if not isinstance(raw_source_lineage, list):
            raise ProductionP1MaterializationError(
                "ED2_P1_SOURCE_LINEAGE_MISSING",
                record.metric_code,
            )
        raw_source_sufficiency = input_payload.get("_source_sufficiency")
        if not isinstance(raw_source_sufficiency, Mapping) or not all(
            isinstance(key, str)
            for key in raw_source_sufficiency
        ):
            raise ProductionP1MaterializationError(
                "ED2_P1_SOURCE_SUFFICIENCY_MISSING",
                record.metric_code,
            )
        source_sufficiency = dict(raw_source_sufficiency)
        source_status = source_sufficiency.get("status")
        if source_status not in {"READY", "INSUFFICIENT_DATA"}:
            raise ProductionP1MaterializationError(
                "ED2_P1_SOURCE_SUFFICIENCY_INVALID",
                f"{record.metric_code}:{source_status!r}",
            )
        missing_sources = source_sufficiency.get(
            "missing_source_families"
        )
        source_reasons = source_sufficiency.get("reason_codes")
        if source_status == "READY":
            if raw_source_lineage == []:
                raise ProductionP1MaterializationError(
                    "ED2_P1_SOURCE_LINEAGE_MISSING",
                    record.metric_code,
                )
            if missing_sources != [] or source_reasons != []:
                raise ProductionP1MaterializationError(
                    "ED2_P1_SOURCE_SUFFICIENCY_INVALID",
                    record.metric_code,
                )
        elif (
            not isinstance(missing_sources, list)
            or not missing_sources
            or not all(
                isinstance(item, str) and item
                for item in missing_sources
            )
            or not isinstance(source_reasons, list)
            or not source_reasons
            or not all(
                isinstance(item, str) and item
                for item in source_reasons
            )
        ):
            raise ProductionP1MaterializationError(
                "ED2_P1_SOURCE_SUFFICIENCY_INVALID",
                record.metric_code,
            )
        source_lineage: list[dict[str, object]] = []
        for lineage_index, raw_lineage in enumerate(raw_source_lineage):
            source_lineage.append(
                dict(
                    _mapping(
                        raw_lineage,
                        field=(
                            f"{record.metric_code}."
                            f"_source_lineage[{lineage_index}]"
                        ),
                    )
                )
            )
        source_lineage_hash = _json_hash(source_lineage)
        source_sufficiency_hash = _json_hash(source_sufficiency)
        system: ProductionP1SystemBinding | None = None
        if definition.subject_type == "MISSION_SYSTEM_INSTANCE":
            system = _system_binding(
                metric_code=record.metric_code,
                binding_by_metric=system_bindings,
                input_payload=input_payload,
            )
            if system.aircraft_id != aircraft.aircraft_id:
                raise ProductionP1MaterializationError(
                    "ED2_P1_SYSTEM_AIRCRAFT_SCOPE_DRIFT",
                    record.metric_code,
                )

        for index, instance in enumerate(_instances(output)):
            status_raw = instance.get("status")
            if not isinstance(status_raw, str):
                raise ProductionP1MaterializationError(
                    "ED2_P1_PLUGIN_OUTPUT_INVALID",
                    f"{record.metric_code}.status",
                )
            status = status_raw
            reasons = _reason_codes(instance)
            eligibility, exclusion = _eligibility(status, reasons)
            value_numeric = instance.get("value_numeric")
            if value_numeric is not None and (
                isinstance(value_numeric, bool)
                or not isinstance(value_numeric, (int, float))
            ):
                raise ProductionP1MaterializationError(
                    "ED2_P1_PLUGIN_OUTPUT_INVALID",
                    f"{record.metric_code}.value_numeric",
                )
            structured_raw = instance.get("value_structured")
            if structured_raw is not None:
                structured = dict(
                    _mapping(
                        structured_raw,
                        field=f"{record.metric_code}.value_structured",
                    )
                )
            else:
                structured = None
            evidence_payload = instance.get("evidence", {})
            evidence_mapping = dict(
                _mapping(
                    evidence_payload,
                    field=f"{record.metric_code}.evidence",
                )
            )

            identity = (
                f"{context.release_id}|{record.metric_code}|{index}|"
                f"{record.logical_hash}"
            )
            evidence_id = str(uuid5(_EVIDENCE_NAMESPACE, identity))
            metric_instance_id = str(uuid5(_INSTANCE_NAMESPACE, identity))
            evidence_sets.append(
                CoreEvidenceRecord(
                    evidence_set_id=evidence_id,
                    episode_id=context.episode_id,
                    start_session_time_us=context.start_session_time_us,
                    end_session_time_us=context.end_session_time_us,
                    series_locator={
                        "metric_code": record.metric_code,
                        "instance_index": index,
                        "plugin_evidence": evidence_mapping,
                        "execution_record_hash": record.logical_hash,
                        "plugin_output_hash": record.plugin_output_hash,
                        "input_payload_hash": record.input_payload_hash,
                        "source_lineage": source_lineage,
                        "source_lineage_hash": source_lineage_hash,
                        "source_sufficiency": source_sufficiency,
                        "source_sufficiency_hash": source_sufficiency_hash,
                    },
                    algorithm_versions={
                        "algorithm_id": record.algorithm_id,
                        "algorithm_version": record.algorithm_version,
                        "plugin_id": record.plugin_id,
                        "plan_hash": record.plan_hash,
                    },
                    world_product_ids=context.world_product_ids,
                    relation_ids=context.relation_ids,
                )
            )
            subject_entity_id = (
                aircraft.subject_entity_id
                if definition.subject_type == "AIRCRAFT"
                else None
            )
            metric_instances.append(
                CoreMetricInstanceRecord(
                    metric_instance_id=metric_instance_id,
                    metric_definition_id=definition_id,
                    metric_code=record.metric_code,
                    episode_id=context.episode_id,
                    stage_id=context.stage_id,
                    subject_entity_id=subject_entity_id,
                    mission_system_instance_id=(
                        None if system is None else system.mission_system_instance_id
                    ),
                    tpaa_chain_id=(
                        tpaa_m_chains[0].chain_id if tpaa_m_chains else None
                    ),
                    value_numeric=(
                        None if value_numeric is None else float(value_numeric)
                    ),
                    value_structured=structured,
                    unit=definition.unit,
                    status=status,
                    reason_codes=reasons,
                    coverage=context.coverage,
                    confidence=context.confidence,
                    evidence_set_id=evidence_id,
                    context_id=context.context_id,
                    world_product_versions={
                        **dict(context.world_product_versions),
                        "metric_execution_plan_hash": contract.plan.logical_hash,
                        "execution_record_hash": record.logical_hash,
                    },
                    compute_version=(
                        f"{record.algorithm_id}@{record.algorithm_version}"
                    ),
                    input_hash=record.input_payload_hash,
                )
            )

            comparison_key = _json_hash(
                {
                    "metric_code": record.metric_code,
                    "subject_type": definition.subject_type,
                    "subject_entity_id": subject_entity_id,
                    "mission_system_instance_id": (
                        None if system is None else system.mission_system_instance_id
                    ),
                    "context_id": context.context_id,
                    "stage_id": context.stage_id,
                }
            )
            if definition.publication_route == "CAPABILITY_OBSERVATION":
                if definition.subject_type != "AIRCRAFT":
                    raise ProductionP1MaterializationError(
                        "ED2_P1_CAPABILITY_SUBJECT_INVALID",
                        record.metric_code,
                    )
                observations.append(
                    CoreObservationRecord(
                        observation_id=str(
                            uuid5(_OBSERVATION_NAMESPACE, identity)
                        ),
                        episode_id=context.episode_id,
                        stage_id=context.stage_id,
                        aircraft_id=aircraft.aircraft_id,
                        aircraft_instance_id=aircraft.aircraft_instance_id,
                        subject_entity_id=aircraft.subject_entity_id,
                        aircraft_model_id=aircraft.aircraft_model_id,
                        context_id=context.context_id,
                        capability_dimension=aircraft.capability_dimension,
                        capability_type=aircraft.capability_type,
                        observed_metric_instance_id=metric_instance_id,
                        observed_value_numeric=(
                            None if value_numeric is None else float(value_numeric)
                        ),
                        observed_value_structured=structured,
                        unit=definition.unit,
                        observation_start_session_time_us=(
                            context.start_session_time_us
                        ),
                        observation_end_session_time_us=(
                            context.end_session_time_us
                        ),
                        evidence_set_id=evidence_id,
                        coverage=context.coverage,
                        confidence=context.confidence,
                        eligibility_status=eligibility,
                        exclusion_reason_code=exclusion,
                        comparison_key_hash=comparison_key,
                        observation_schema_version=(
                            context.observation_schema_version
                        ),
                    )
                )
            elif definition.publication_route == "SYSTEM_PERFORMANCE_OBSERVATION":
                if system is None:
                    raise ProductionP1MaterializationError(
                        "ED2_P1_SYSTEM_BINDING_MISSING",
                        record.metric_code,
                    )
                system_observations.append(
                    CoreSystemObservationRecord(
                        system_observation_id=str(
                            uuid5(_SYSTEM_OBSERVATION_NAMESPACE, identity)
                        ),
                        episode_id=context.episode_id,
                        stage_id=context.stage_id,
                        aircraft_id=system.aircraft_id,
                        mission_system_instance_id=(
                            system.mission_system_instance_id
                        ),
                        observed_metric_instance_id=metric_instance_id,
                        reference_truth_profile_version=(
                            system.reference_truth_profile_version
                        ),
                        reference_quality_status=system.reference_quality_status,
                        reference_uncertainty_summary=dict(
                            system.reference_uncertainty_summary
                        ),
                        alignment_uncertainty_summary=dict(
                            system.alignment_uncertainty_summary
                        ),
                        observation_start_session_time_us=(
                            context.start_session_time_us
                        ),
                        observation_end_session_time_us=(
                            context.end_session_time_us
                        ),
                        context_tags=dict(system.context_tags),
                        evidence_set_id=evidence_id,
                        coverage=context.coverage,
                        confidence=context.confidence,
                        eligibility_status=eligibility,
                        exclusion_reason_code=exclusion,
                        comparison_key_hash=comparison_key,
                        observation_schema_version=(
                            context.observation_schema_version
                        ),
                    )
                )

    manifest_hash = _json_hash(
        {
            "schema": "TPAA_ED2_P1_RELEASE_MANIFEST_V1",
            "release_id": context.release_id,
            "request_hash": context.request_hash,
            "catalog_hash": contract.plan.catalog_sha256,
            "plan_hash": contract.plan.logical_hash,
            "execution_batch_hash": batch.logical_hash,
            "definition_ids": [
                item.metric_definition_id for item in definitions
            ],
            "evidence_ids": [item.evidence_set_id for item in evidence_sets],
            "metric_instance_ids": [
                item.metric_instance_id for item in metric_instances
            ],
            "observation_ids": [item.observation_id for item in observations],
            "system_observation_ids": [
                item.system_observation_id for item in system_observations
            ],
            "world_product_ids": [
                item.world_product_id for item in world_products
            ],
            "world_relation_ids": [
                item.relation_id for item in world_relations
            ],
            "tpaa_m_chain_ids": [item.chain_id for item in tpaa_m_chains],
        }
    )
    return CorePublicationBundle(
        release_id=context.release_id,
        release_no=context.release_no,
        parent_release_id=context.parent_release_id,
        request_hash=context.request_hash,
        session_id=context.session_id,
        context_id=context.context_id,
        context_version=context.context_version,
        context_binding_hash=context.context_binding_hash,
        catalog_version=contract.plan.catalog_version,
        catalog_hash=contract.plan.catalog_sha256,
        manifest_hash=manifest_hash,
        definitions=tuple(definitions),
        evidence_sets=tuple(evidence_sets),
        metric_instances=tuple(metric_instances),
        observations=tuple(observations),
        system_observations=tuple(system_observations),
        world_products=world_products,
        world_relations=world_relations,
        tpaa_m_chains=tpaa_m_chains,
    )
