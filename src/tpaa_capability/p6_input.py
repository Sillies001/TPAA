"""M9 Batch 1 leakage-safe exact P6 input snapshot substrate."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from tpaa_context.p6_governance import (
    P6AuthorityPolicy,
    P6GovernanceError,
    canonical_hash,
    exact_text,
    exact_uuid,
    utc,
    validate_availability_numeric,
)


@dataclass(frozen=True, slots=True)
class P6FactualSourceRevision:
    phase: str
    revision_id: str
    publication_status: str
    knowledge_time_utc: str
    is_target_outcome: bool = False
    is_post_horizon_outcome: bool = False


@dataclass(frozen=True, slots=True)
class P6P3ModelRef:
    model_ref_id: str
    publication_status: str
    knowledge_time_utc: str


@dataclass(frozen=True, slots=True)
class P6ContextRef:
    context_ref_id: str
    status: str
    knowledge_time_utc: str


@dataclass(frozen=True, slots=True)
class P6InputSnapshot:
    input_snapshot_id: str
    snapshot_type: str
    factual_source_refs: tuple[str, ...]
    p3_model_refs: tuple[str, ...]
    scenario_context_refs: tuple[str, ...]
    target_scope: str
    subject_or_composition_ref: str
    forecast_origin_utc: str
    as_of_utc: str
    data_hash: str
    availability_status: str
    reason_codes: tuple[str, ...]
    source_bindings: tuple[P6FactualSourceRevision, ...]
    p3_bindings: tuple[P6P3ModelRef, ...]
    context_bindings: tuple[P6ContextRef, ...]
    frozen: bool = True


def _source_payload(source: P6FactualSourceRevision) -> dict[str, object]:
    return {
        "phase": source.phase,
        "revision_id": source.revision_id,
        "publication_status": source.publication_status,
        "knowledge_time_utc": source.knowledge_time_utc,
    }


def _p3_payload(source: P6P3ModelRef) -> dict[str, object]:
    return {
        "model_ref_id": source.model_ref_id,
        "publication_status": source.publication_status,
        "knowledge_time_utc": source.knowledge_time_utc,
    }


def _context_payload(source: P6ContextRef) -> dict[str, object]:
    return {
        "context_ref_id": source.context_ref_id,
        "status": source.status,
        "knowledge_time_utc": source.knowledge_time_utc,
    }


def _identity_material(snapshot: P6InputSnapshot) -> dict[str, object]:
    return {
        "snapshot_type": snapshot.snapshot_type,
        "factual_sources": [_source_payload(item) for item in snapshot.source_bindings],
        "p3_model_refs": [_p3_payload(item) for item in snapshot.p3_bindings],
        "scenario_context_refs": [
            _context_payload(item) for item in snapshot.context_bindings
        ],
        "target_scope": snapshot.target_scope,
        "subject_or_composition_ref": snapshot.subject_or_composition_ref,
        "forecast_origin_utc": snapshot.forecast_origin_utc,
        "as_of_utc": snapshot.as_of_utc,
        "availability_status": snapshot.availability_status,
        "reason_codes": list(snapshot.reason_codes),
        "frozen": snapshot.frozen,
    }


def build_p6_input_snapshot(
    *,
    factual_sources: Sequence[P6FactualSourceRevision],
    p3_model_refs: Sequence[P6P3ModelRef] = (),
    scenario_context_refs: Sequence[P6ContextRef] = (),
    target_scope: str,
    subject_or_composition_ref: str,
    forecast_origin_utc: str,
    as_of_utc: str,
    availability_status: str = "AVAILABLE",
    reason_codes: Sequence[str] = (),
    policy: P6AuthorityPolicy | None = None,
) -> P6InputSnapshot:
    p = policy or P6AuthorityPolicy.from_canonical()
    if target_scope not in {"SUBJECT", "COMPOSITION", "MISSION"}:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
            f"target_scope={target_scope!r}",
        )
    exact_text(
        subject_or_composition_ref,
        field="subject_or_composition_ref",
        policy=p,
    )
    origin = utc(forecast_origin_utc, field="forecast_origin_utc")
    as_of = utc(as_of_utc, field="as_of_utc")
    if origin > as_of:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_FUTURE_INFORMATION",
            "forecast_origin_utc is after as_of_utc",
        )
    if not factual_sources:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_INPUT_SNAPSHOT_REQUIRED",
            "at least one exact P4/P5 factual source is required",
        )

    normalized_sources: list[P6FactualSourceRevision] = []
    for source in factual_sources:
        if source.phase not in {"P4", "P5"}:
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_INPUT_SNAPSHOT_REQUIRED",
                f"factual source phase={source.phase!r}",
            )
        exact_uuid(source.revision_id, field="factual_source_revision_id", policy=p)
        if source.publication_status != "PUBLISHED":
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_INPUT_SNAPSHOT_REQUIRED",
                f"source status={source.publication_status!r}",
            )
        source_time = utc(source.knowledge_time_utc, field="source.knowledge_time_utc")
        if source_time > origin or source_time > as_of:
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_FUTURE_INFORMATION",
                source.revision_id,
            )
        if source.is_target_outcome or source.is_post_horizon_outcome:
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_SAME_OUTCOME_LEAKAGE",
                source.revision_id,
            )
        normalized_sources.append(source)

    normalized_p3: list[P6P3ModelRef] = []
    for source in p3_model_refs:
        exact_uuid(source.model_ref_id, field="p3_model_ref_id", policy=p)
        if source.publication_status != "PUBLISHED":
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_INPUT_SNAPSHOT_REQUIRED",
                f"P3 source status={source.publication_status!r}",
            )
        if utc(source.knowledge_time_utc, field="p3.knowledge_time_utc") > origin:
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_FUTURE_INFORMATION",
                source.model_ref_id,
            )
        normalized_p3.append(source)

    normalized_context: list[P6ContextRef] = []
    for context in scenario_context_refs:
        exact_uuid(context.context_ref_id, field="scenario_context_ref_id", policy=p)
        exact_text(context.status, field="scenario_context_status", policy=p)
        if utc(context.knowledge_time_utc, field="context.knowledge_time_utc") > origin:
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_FUTURE_INFORMATION",
                context.context_ref_id,
            )
        normalized_context.append(context)

    validate_availability_numeric(
        status=availability_status,
        numeric_value=None,
        policy=p,
    )
    normalized_reasons = tuple(
        sorted(
            {
                exact_text(reason, field="reason_code", policy=p)
                for reason in reason_codes
            }
        )
    )
    if availability_status != "AVAILABLE" and not normalized_reasons:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_INPUT_SNAPSHOT_REQUIRED",
            "non-available snapshot requires reason_codes",
        )

    sources = tuple(
        sorted(normalized_sources, key=lambda item: (item.phase, item.revision_id))
    )
    p3_refs = tuple(sorted(normalized_p3, key=lambda item: item.model_ref_id))
    contexts = tuple(sorted(normalized_context, key=lambda item: item.context_ref_id))
    snapshot = P6InputSnapshot(
        input_snapshot_id="",
        snapshot_type=p.input_snapshot_type,
        factual_source_refs=tuple(item.revision_id for item in sources),
        p3_model_refs=tuple(item.model_ref_id for item in p3_refs),
        scenario_context_refs=tuple(item.context_ref_id for item in contexts),
        target_scope=target_scope,
        subject_or_composition_ref=subject_or_composition_ref,
        forecast_origin_utc=forecast_origin_utc,
        as_of_utc=as_of_utc,
        data_hash="",
        availability_status=availability_status,
        reason_codes=normalized_reasons,
        source_bindings=sources,
        p3_bindings=p3_refs,
        context_bindings=contexts,
    )
    digest = canonical_hash(_identity_material(snapshot))
    return P6InputSnapshot(
        input_snapshot_id=f"P6_INPUT_SHA256:{digest}",
        snapshot_type=snapshot.snapshot_type,
        factual_source_refs=snapshot.factual_source_refs,
        p3_model_refs=snapshot.p3_model_refs,
        scenario_context_refs=snapshot.scenario_context_refs,
        target_scope=snapshot.target_scope,
        subject_or_composition_ref=snapshot.subject_or_composition_ref,
        forecast_origin_utc=snapshot.forecast_origin_utc,
        as_of_utc=snapshot.as_of_utc,
        data_hash=digest,
        availability_status=snapshot.availability_status,
        reason_codes=snapshot.reason_codes,
        source_bindings=snapshot.source_bindings,
        p3_bindings=snapshot.p3_bindings,
        context_bindings=snapshot.context_bindings,
    )


def assert_p6_input_snapshot_identity(snapshot: P6InputSnapshot) -> None:
    digest = canonical_hash(_identity_material(snapshot))
    if (
        not snapshot.frozen
        or snapshot.data_hash != digest
        or snapshot.input_snapshot_id != f"P6_INPUT_SHA256:{digest}"
    ):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_INPUT_SNAPSHOT_REQUIRED",
            "P6 input snapshot identity drift",
        )


@dataclass(frozen=True, slots=True)
class P6ForecastRequestBinding:
    forecast_request_id: str
    input_snapshot_id: str
    forecast_spec_id: str
    forecast_spec_version: str
    target_scope: str
    subject_ref: str
    target_code: str
    forecast_origin_utc: str
    horizon_spec: dict[str, object]
    capability_model_id: str
    model_profile_id: str
    model_profile_version: str
    training_dataset_snapshot_id: str
    validation_dataset_snapshot_id: str
    assumption_profile_id: str
    assumption_profile_version: str
    as_of_utc: str
    request_hash: str


@dataclass(frozen=True, slots=True)
class P6CounterfactualRequestBinding:
    counterfactual_request_id: str
    input_snapshot_id: str
    base_product_refs: tuple[str, ...]
    scenario_definition_id: str
    interventions: dict[str, object]
    held_fixed_assumptions: dict[str, object]
    model_refs: tuple[str, ...]
    applicability_profile_ref: str
    as_of_utc: str
    request_hash: str


def build_p6_forecast_request_binding(
    *,
    input_snapshot: P6InputSnapshot,
    forecast_spec_id: str,
    forecast_spec_version: str,
    target_code: str,
    horizon_spec: Mapping[str, object],
    capability_model_id: str,
    model_profile_id: str,
    model_profile_version: str,
    training_dataset_snapshot_id: str,
    validation_dataset_snapshot_id: str,
    assumption_profile_id: str,
    assumption_profile_version: str,
    policy: P6AuthorityPolicy | None = None,
) -> P6ForecastRequestBinding:
    p = policy or P6AuthorityPolicy.from_canonical()
    assert_p6_input_snapshot_identity(input_snapshot)
    for value, field in (
        (forecast_spec_id, "forecast_spec_id"),
        (forecast_spec_version, "forecast_spec_version"),
        (target_code, "target_code"),
        (model_profile_id, "model_profile_id"),
        (model_profile_version, "model_profile_version"),
        (assumption_profile_id, "assumption_profile_id"),
        (assumption_profile_version, "assumption_profile_version"),
    ):
        exact_text(value, field=field, policy=p)
    exact_uuid(capability_model_id, field="capability_model_id", policy=p)
    exact_uuid(
        training_dataset_snapshot_id,
        field="training_dataset_snapshot_id",
        policy=p,
    )
    exact_uuid(
        validation_dataset_snapshot_id,
        field="validation_dataset_snapshot_id",
        policy=p,
    )
    if training_dataset_snapshot_id == validation_dataset_snapshot_id:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_TRAINING_VALIDATION_LEAKAGE",
            training_dataset_snapshot_id,
        )
    if not horizon_spec:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_INPUT_SNAPSHOT_REQUIRED",
            "horizon_spec",
        )
    horizon = dict(horizon_spec)
    canonical_hash(horizon)
    material: dict[str, object] = {
        "input_snapshot_id": input_snapshot.input_snapshot_id,
        "forecast_spec_id": forecast_spec_id,
        "forecast_spec_version": forecast_spec_version,
        "target_scope": input_snapshot.target_scope,
        "subject_ref": input_snapshot.subject_or_composition_ref,
        "target_code": target_code,
        "forecast_origin_utc": input_snapshot.forecast_origin_utc,
        "horizon_spec": horizon,
        "capability_model_id": capability_model_id,
        "model_profile_id": model_profile_id,
        "model_profile_version": model_profile_version,
        "training_dataset_snapshot_id": training_dataset_snapshot_id,
        "validation_dataset_snapshot_id": validation_dataset_snapshot_id,
        "assumption_profile_id": assumption_profile_id,
        "assumption_profile_version": assumption_profile_version,
        "as_of_utc": input_snapshot.as_of_utc,
    }
    digest = canonical_hash(material)
    return P6ForecastRequestBinding(
        forecast_request_id=f"P6_FORECAST_REQUEST_SHA256:{digest}",
        input_snapshot_id=input_snapshot.input_snapshot_id,
        forecast_spec_id=forecast_spec_id,
        forecast_spec_version=forecast_spec_version,
        target_scope=input_snapshot.target_scope,
        subject_ref=input_snapshot.subject_or_composition_ref,
        target_code=target_code,
        forecast_origin_utc=input_snapshot.forecast_origin_utc,
        horizon_spec=horizon,
        capability_model_id=capability_model_id,
        model_profile_id=model_profile_id,
        model_profile_version=model_profile_version,
        training_dataset_snapshot_id=training_dataset_snapshot_id,
        validation_dataset_snapshot_id=validation_dataset_snapshot_id,
        assumption_profile_id=assumption_profile_id,
        assumption_profile_version=assumption_profile_version,
        as_of_utc=input_snapshot.as_of_utc,
        request_hash=digest,
    )


def build_p6_counterfactual_request_binding(
    *,
    input_snapshot: P6InputSnapshot,
    base_product_refs: Sequence[str],
    scenario_definition_id: str,
    interventions: Mapping[str, object],
    held_fixed_assumptions: Mapping[str, object],
    model_refs: Sequence[str],
    applicability_profile_ref: str,
    policy: P6AuthorityPolicy | None = None,
) -> P6CounterfactualRequestBinding:
    p = policy or P6AuthorityPolicy.from_canonical()
    assert_p6_input_snapshot_identity(input_snapshot)
    if not base_product_refs or not model_refs:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_INPUT_SNAPSHOT_REQUIRED",
            "counterfactual exact base/model refs",
        )
    bases = tuple(
        sorted(
            {
                exact_uuid(item, field="base_product_ref", policy=p)
                for item in base_product_refs
            }
        )
    )
    if not set(bases).issubset(set(input_snapshot.factual_source_refs)):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_INPUT_SNAPSHOT_REQUIRED",
            "counterfactual baseline is outside exact input snapshot",
        )
    exact_uuid(scenario_definition_id, field="scenario_definition_id", policy=p)
    if (
        input_snapshot.scenario_context_refs
        and scenario_definition_id not in input_snapshot.scenario_context_refs
    ):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_INPUT_SNAPSHOT_REQUIRED",
            "scenario_definition_id is outside exact input snapshot",
        )
    if not interventions or not held_fixed_assumptions:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_COUNTERFACTUAL_ASSUMPTIONS_REQUIRED",
            "interventions and held-fixed assumptions are required",
        )
    intervention_object = dict(interventions)
    assumption_object = dict(held_fixed_assumptions)
    canonical_hash(intervention_object)
    canonical_hash(assumption_object)
    models = tuple(
        sorted(
            {
                exact_uuid(item, field="counterfactual_model_ref", policy=p)
                for item in model_refs
            }
        )
    )
    exact_text(
        applicability_profile_ref,
        field="applicability_profile_ref",
        policy=p,
    )
    material: dict[str, object] = {
        "input_snapshot_id": input_snapshot.input_snapshot_id,
        "base_product_refs": list(bases),
        "scenario_definition_id": scenario_definition_id,
        "interventions": intervention_object,
        "held_fixed_assumptions": assumption_object,
        "model_refs": list(models),
        "applicability_profile_ref": applicability_profile_ref,
        "as_of_utc": input_snapshot.as_of_utc,
    }
    digest = canonical_hash(material)
    return P6CounterfactualRequestBinding(
        counterfactual_request_id=f"P6_COUNTERFACTUAL_REQUEST_SHA256:{digest}",
        input_snapshot_id=input_snapshot.input_snapshot_id,
        base_product_refs=bases,
        scenario_definition_id=scenario_definition_id,
        interventions=intervention_object,
        held_fixed_assumptions=assumption_object,
        model_refs=models,
        applicability_profile_ref=applicability_profile_ref,
        as_of_utc=input_snapshot.as_of_utc,
        request_hash=digest,
    )
