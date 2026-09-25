"""Driver-neutral row bundle consumed by Core publication storage adapters.

These records contain already-decided publication values. Storage adapters map
them to frozen Core tables without importing or recomputing business semantics.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CoreMetricDefinitionRef:
    metric_definition_id: str
    metric_code: str
    catalog_version: str
    catalog_hash: str
    metric_semantic_id: str
    metric_semantic_version: int
    subject_type: str
    observation_lane: str
    publication_route: str
    definition_hash: str


@dataclass(frozen=True)
class CoreEvidenceRecord:
    evidence_set_id: str
    episode_id: str
    start_session_time_us: int
    end_session_time_us: int
    series_locator: dict[str, object]
    algorithm_versions: dict[str, object]


@dataclass(frozen=True)
class CoreMetricInstanceRecord:
    metric_instance_id: str
    metric_definition_id: str
    metric_code: str
    episode_id: str
    stage_id: str | None
    subject_entity_id: str
    value_numeric: float | None
    value_structured: dict[str, object] | None
    unit: str
    status: str
    reason_codes: tuple[str, ...]
    coverage: float
    confidence: float
    evidence_set_id: str
    context_id: str
    world_product_versions: dict[str, object]
    compute_version: str
    input_hash: str


@dataclass(frozen=True)
class CoreObservationRecord:
    observation_id: str
    episode_id: str
    stage_id: str | None
    aircraft_id: str
    aircraft_instance_id: str
    subject_entity_id: str
    aircraft_model_id: str
    context_id: str
    capability_dimension: str
    capability_type: str
    observed_metric_instance_id: str
    observed_value_numeric: float | None
    observed_value_structured: dict[str, object] | None
    unit: str
    observation_start_session_time_us: int
    observation_end_session_time_us: int
    evidence_set_id: str
    coverage: float
    confidence: float
    eligibility_status: str
    exclusion_reason_code: str | None
    comparison_key_hash: str
    observation_schema_version: str


@dataclass(frozen=True)
class CorePublicationBundle:
    release_id: str
    release_no: int
    parent_release_id: str | None
    request_hash: str
    session_id: str
    context_id: str
    context_version: str
    context_binding_hash: str
    catalog_version: str
    catalog_hash: str
    manifest_hash: str
    definitions: tuple[CoreMetricDefinitionRef, ...]
    evidence_sets: tuple[CoreEvidenceRecord, ...]
    metric_instances: tuple[CoreMetricInstanceRecord, ...]
    observations: tuple[CoreObservationRecord, ...]
