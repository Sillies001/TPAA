"""M9 Batch 3 exact non-causal P6 counterfactual revision products."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID, uuid5

from tpaa_context.p6_governance import (
    P6AuthorityPolicy,
    P6GovernanceError,
    canonical_hash,
    exact_hash64,
    exact_text,
    exact_uuid,
    utc,
)

from .p6_forecast import P6ModelRevision
from .p6_input import (
    P6CounterfactualRequestBinding,
    P6InputSnapshot,
    assert_p6_input_snapshot_identity,
)

_COUNTERFACTUAL_NAMESPACE = UUID("454034a4-9098-55b4-812b-a1c83f6bea73")
_DEFAULT_CLAIM = "SCENARIO_PROJECTION_NON_CAUSAL"


@dataclass(frozen=True, slots=True)
class P6CounterfactualRevision:
    counterfactual_run_id: str
    counterfactual_request_id: str
    base_product_refs: tuple[str, ...]
    scenario_definition_id: str
    interventions: Mapping[str, object]
    held_fixed_assumptions: Mapping[str, object]
    model_refs: tuple[str, ...]
    applicability_profile_ref: str
    projection_dataset_uri: str
    projection_dataset_hash: str
    applicability_status: str
    identifiability_status: str
    causal_claim_level: str
    uncertainty: Mapping[str, object]
    assumptions: Mapping[str, object]
    status: str
    as_of_utc: str
    created_at_utc: str
    supersedes_counterfactual_run_id: str | None
    logical_content_hash: str

    def projection(self) -> dict[str, object]:
        return {
            "counterfactual_run_id": self.counterfactual_run_id,
            "projection_dataset_uri": self.projection_dataset_uri,
            "projection_dataset_hash": self.projection_dataset_hash,
            "applicability_status": self.applicability_status,
            "identifiability_status": self.identifiability_status,
            "causal_claim_level": self.causal_claim_level,
            "uncertainty": dict(self.uncertainty),
            "assumptions": dict(self.assumptions),
            "model_refs": list(self.model_refs),
            "status": self.status,
            "as_of_utc": self.as_of_utc,
            "logical_content_hash": self.logical_content_hash,
        }


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
            f"canonical json: {type(exc).__name__}",
        ) from exc


def _typed_interventions(
    interventions: Mapping[str, object],
    *,
    policy: P6AuthorityPolicy,
) -> dict[str, object]:
    if not interventions:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_COUNTERFACTUAL_ASSUMPTIONS_REQUIRED",
            "typed interventions required",
        )
    normalized: dict[str, object] = {}
    for name, raw in sorted(interventions.items()):
        exact_text(name, field="intervention.name", policy=policy)
        if not isinstance(raw, Mapping):
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_COUNTERFACTUAL_ASSUMPTIONS_REQUIRED",
                f"intervention {name!r} must be object",
            )
        value = dict(raw)
        kind = value.get("type")
        if not isinstance(kind, str) or not kind:
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_COUNTERFACTUAL_ASSUMPTIONS_REQUIRED",
                f"intervention {name!r} type",
            )
        if "value" not in value:
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_COUNTERFACTUAL_ASSUMPTIONS_REQUIRED",
                f"intervention {name!r} value",
            )
        canonical_hash(value)
        normalized[name] = value
    return normalized


def execute_p6_counterfactual(
    *,
    request: P6CounterfactualRequestBinding,
    input_snapshot: P6InputSnapshot,
    models: Sequence[P6ModelRevision],
    created_at_utc: str,
    causal_claim_level: str = _DEFAULT_CLAIM,
    supersedes_counterfactual_run_id: str | None = None,
    policy: P6AuthorityPolicy | None = None,
) -> P6CounterfactualRevision:
    p = policy or P6AuthorityPolicy.from_canonical()
    assert_p6_input_snapshot_identity(input_snapshot)
    if request.input_snapshot_id != input_snapshot.input_snapshot_id:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_INPUT_SNAPSHOT_REQUIRED",
            "counterfactual input snapshot drift",
        )
    if causal_claim_level != _DEFAULT_CLAIM:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_CAUSAL_CLAIM_NOT_AUTHORIZED",
            causal_claim_level,
        )
    if not request.held_fixed_assumptions:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_COUNTERFACTUAL_ASSUMPTIONS_REQUIRED",
            "held-fixed assumptions required",
        )
    interventions = _typed_interventions(request.interventions, policy=p)
    assumptions = dict(request.held_fixed_assumptions)
    canonical_hash(assumptions)
    created = utc(created_at_utc, field="created_at_utc")
    as_of = utc(request.as_of_utc, field="request.as_of_utc")
    if created < as_of:
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_FUTURE_INFORMATION",
            "counterfactual created before as_of",
        )
    model_by_id = {model.capability_model_id: model for model in models}
    if tuple(sorted(model_by_id)) != tuple(sorted(request.model_refs)):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_MODEL_PROFILE_REQUIRED",
            "counterfactual exact model refs drift",
        )
    for model_id in request.model_refs:
        model = model_by_id[model_id]
        exact_uuid(model_id, field="counterfactual.model_ref", policy=p)
        exact_hash64(model.model_artifact_hash, field="model_artifact_hash")
        if (
            model.status != "VALIDATED"
            or model.applicability_profile_ref
            != request.applicability_profile_ref
            or utc(model.trained_at, field="model.trained_at") > as_of
        ):
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_MODEL_PROFILE_REQUIRED",
                model_id,
            )
    if not set(request.base_product_refs).issubset(
        set(input_snapshot.factual_source_refs)
    ):
        raise P6GovernanceError(
            "FAIL_CLOSED_P6_INPUT_SNAPSHOT_REQUIRED",
            "counterfactual factual baseline drift",
        )
    applicability_status = (
        "APPLICABLE"
        if input_snapshot.availability_status == "AVAILABLE"
        else (
            input_snapshot.availability_status
            if input_snapshot.availability_status
            in {"OUT_OF_DOMAIN", "INSUFFICIENT_EVIDENCE", "NOT_IDENTIFIABLE"}
            else "INSUFFICIENT_EVIDENCE"
        )
    )
    identifiability_status = "SCENARIO_ONLY_NON_CAUSAL"
    uncertainty: dict[str, object] = {
        "status": "NON_NUMERIC_ASSUMPTION_BOUND",
        "numeric_effect": None,
        "reason_codes": [
            "NO_SEPARATELY_ADOPTED_CAUSAL_EFFECT_AUTHORITY",
        ],
    }
    dataset = {
        "schema": "TPAA_P6_COUNTERFACTUAL_TRACE_V1",
        "projection_class": "P6_COUNTERFACTUAL_PROJECTION",
        "counterfactual_request_id": request.counterfactual_request_id,
        "input_snapshot_id": input_snapshot.input_snapshot_id,
        "base_product_refs": list(request.base_product_refs),
        "scenario_definition_id": request.scenario_definition_id,
        "interventions": interventions,
        "held_fixed_assumptions": assumptions,
        "model_refs": list(request.model_refs),
        "model_artifact_hashes": [
            model_by_id[model_id].model_artifact_hash
            for model_id in request.model_refs
        ],
        "applicability_status": applicability_status,
        "identifiability_status": identifiability_status,
        "causal_claim_level": causal_claim_level,
        "uncertainty": uncertainty,
        "as_of_utc": request.as_of_utc,
    }
    dataset_bytes = _canonical_bytes(dataset)
    dataset_hash = hashlib.sha256(dataset_bytes).hexdigest()
    identity_hash = canonical_hash(
        {
            "request_hash": request.request_hash,
            "projection_dataset_hash": dataset_hash,
            "applicability_status": applicability_status,
            "identifiability_status": identifiability_status,
            "causal_claim_level": causal_claim_level,
            "as_of_utc": request.as_of_utc,
            "supersedes_counterfactual_run_id": (
                supersedes_counterfactual_run_id
            ),
        }
    )
    run_id = str(uuid5(_COUNTERFACTUAL_NAMESPACE, identity_hash))
    if supersedes_counterfactual_run_id is not None:
        exact_uuid(
            supersedes_counterfactual_run_id,
            field="supersedes_counterfactual_run_id",
            policy=p,
        )
        if supersedes_counterfactual_run_id == run_id:
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
                "counterfactual cannot supersede itself",
            )
    uri = f"tpaa-object://p6-counterfactual/runs/{run_id}.json"
    logical_hash = canonical_hash(
        {
            "counterfactual_run_id": run_id,
            "counterfactual_request_id": request.counterfactual_request_id,
            "projection_dataset_hash": dataset_hash,
            "applicability_status": applicability_status,
            "identifiability_status": identifiability_status,
            "causal_claim_level": causal_claim_level,
            "uncertainty": uncertainty,
            "as_of_utc": request.as_of_utc,
        }
    )
    return P6CounterfactualRevision(
        counterfactual_run_id=run_id,
        counterfactual_request_id=request.counterfactual_request_id,
        base_product_refs=request.base_product_refs,
        scenario_definition_id=request.scenario_definition_id,
        interventions=interventions,
        held_fixed_assumptions=assumptions,
        model_refs=request.model_refs,
        applicability_profile_ref=request.applicability_profile_ref,
        projection_dataset_uri=uri,
        projection_dataset_hash=dataset_hash,
        applicability_status=applicability_status,
        identifiability_status=identifiability_status,
        causal_claim_level=causal_claim_level,
        uncertainty=uncertainty,
        assumptions={
            "held_fixed": assumptions,
            "interventions": interventions,
        },
        status="PUBLISHED_PROJECTION",
        as_of_utc=request.as_of_utc,
        created_at_utc=created_at_utc,
        supersedes_counterfactual_run_id=supersedes_counterfactual_run_id,
        logical_content_hash=logical_hash,
    )
