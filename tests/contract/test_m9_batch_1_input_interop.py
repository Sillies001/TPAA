from __future__ import annotations

from dataclasses import replace

import pytest

from tpaa_capability import (
    P6ContextRef,
    P6FactualSourceRevision,
    P6P3ModelRef,
    assert_p6_input_snapshot_identity,
    build_p6_counterfactual_request_binding,
    build_p6_forecast_request_binding,
    build_p6_input_snapshot,
)
from tpaa_context import (
    P6AuthorityPolicy,
    P6GovernanceError,
    assert_p1_p5_immutable,
    assert_p6_claim_allowed,
)
from tpaa_context.p6_governance import validate_availability_numeric
from tpaa_ingest import (
    P6InteropArtifactRef,
    assert_p6_interop_snapshot_identity,
    build_p6_interop_snapshot,
)

H = "a" * 64
H2 = "b" * 64
U = {
    "p4": "11111111-1111-4111-8111-111111111111",
    "p5": "22222222-2222-4222-8222-222222222222",
    "p3": "33333333-3333-4333-8333-333333333333",
    "context": "44444444-4444-4444-8444-444444444444",
    "model": "55555555-5555-4555-8555-555555555555",
    "training": "66666666-6666-4666-8666-666666666666",
    "validation": "77777777-7777-4777-8777-777777777777",
    "session": "88888888-8888-4888-8888-888888888888",
    "source": "99999999-9999-4999-8999-999999999999",
    "stream": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "artifact1": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    "artifact2": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
}


@pytest.fixture(scope="module")
def policy() -> P6AuthorityPolicy:
    return P6AuthorityPolicy.from_canonical()


def _sources() -> tuple[P6FactualSourceRevision, ...]:
    return (
        P6FactualSourceRevision(
            phase="P4",
            revision_id=U["p4"],
            publication_status="PUBLISHED",
            knowledge_time_utc="2026-10-01T08:00:00Z",
        ),
        P6FactualSourceRevision(
            phase="P5",
            revision_id=U["p5"],
            publication_status="PUBLISHED",
            knowledge_time_utc="2026-10-01T08:30:00Z",
        ),
    )


def _snapshot(policy: P6AuthorityPolicy):
    return build_p6_input_snapshot(
        factual_sources=_sources(),
        p3_model_refs=(
            P6P3ModelRef(
                model_ref_id=U["p3"],
                publication_status="PUBLISHED",
                knowledge_time_utc="2026-10-01T07:30:00Z",
            ),
        ),
        scenario_context_refs=(
            P6ContextRef(
                context_ref_id=U["context"],
                status="ACTIVE",
                knowledge_time_utc="2026-10-01T07:00:00Z",
            ),
        ),
        target_scope="MISSION",
        subject_or_composition_ref="mission:training-001",
        forecast_origin_utc="2026-10-01T09:00:00Z",
        as_of_utc="2026-10-01T09:00:00Z",
        policy=policy,
    )


def _artifacts(payload_class: str = "FACT_SOURCE"):
    return (
        P6InteropArtifactRef(
            artifact_ref_id=U["artifact1"],
            object_hash=H,
            payload_class=payload_class,
        ),
        P6InteropArtifactRef(
            artifact_ref_id=U["artifact2"],
            object_hash=H2,
            payload_class=payload_class,
        ),
    )


def _interop(
    policy: P6AuthorityPolicy,
    *,
    artifacts=None,
    source_class: str = "FACT_SOURCE",
    payload_class: str = "FACT_SOURCE",
    external_profile_version: str = "1.0.0",
    lossless_phase_mapping: bool = True,
    release_state: str = "AUTHORIZED",
    source_available_at_utc: str = "2026-10-01T08:00:00Z",
):
    return build_p6_interop_snapshot(
        session_id=U["session"],
        session_type="LVC",
        source_id=U["source"],
        source_stream_id=U["stream"],
        artifact_refs=artifacts or _artifacts(source_class),
        producer_system="LVC-GATEWAY-A",
        external_profile_id="P6_LVC_EXCHANGE",
        external_profile_version=external_profile_version,
        adapter_id="P6_LVC_ADAPTER",
        adapter_version="1.0.0",
        unit_basis={"altitude": "m", "speed": "m/s"},
        time_basis="UTC",
        source_or_projection_class=source_class,
        payload_class=payload_class,
        canonical_entity_refs=("entity:aircraft:b", "entity:aircraft:a"),
        applicability_status="APPLICABLE",
        uncertainty={"source": "declared"},
        release_state=release_state,
        as_of_utc="2026-10-01T09:00:00Z",
        source_available_at_utc=source_available_at_utc,
        lossless_phase_mapping=lossless_phase_mapping,
        policy=policy,
    )


def test_m9_batch1_policy_and_input_identity_are_exact(
    policy: P6AuthorityPolicy,
) -> None:
    assert policy.authority_sha256 == (
        "a138c97e6c9891f767ee25de8841e2bc9ca899ddf6d09b98b9e4bae73d9be79e"
    )
    assert policy.role_profile_sha256 == (
        "d5eff80dbfa912955ae7b09bc3e4a2868650466560cb1a5b1f558434e8076713"
    )
    first = _snapshot(policy)
    second = build_p6_input_snapshot(
        factual_sources=tuple(reversed(_sources())),
        p3_model_refs=first.p3_bindings,
        scenario_context_refs=first.context_bindings,
        target_scope=first.target_scope,
        subject_or_composition_ref=first.subject_or_composition_ref,
        forecast_origin_utc=first.forecast_origin_utc,
        as_of_utc=first.as_of_utc,
        policy=policy,
    )
    assert first.input_snapshot_id == second.input_snapshot_id
    assert first.input_snapshot_id.startswith("P6_INPUT_SHA256:")
    assert first.factual_source_refs == tuple(sorted(first.factual_source_refs))
    assert first.frozen is True
    assert_p6_input_snapshot_identity(first)

    with pytest.raises(P6GovernanceError) as drift:
        assert_p6_input_snapshot_identity(replace(first, data_hash=H))
    assert drift.value.code == "FAIL_CLOSED_P6_INPUT_SNAPSHOT_REQUIRED"


def test_m9_batch1_forecast_and_counterfactual_request_bindings_are_exact(
    policy: P6AuthorityPolicy,
) -> None:
    snapshot = _snapshot(policy)
    forecast = build_p6_forecast_request_binding(
        input_snapshot=snapshot,
        forecast_spec_id="P6_FORECAST_SPEC_TEST",
        forecast_spec_version="1.0.0",
        target_code="TRAINING_PERFORMANCE_DELTA",
        horizon_spec={"seconds": 60},
        capability_model_id=U["model"],
        model_profile_id="P6_MODEL_PROFILE_TEST",
        model_profile_version="1.0.0",
        training_dataset_snapshot_id=U["training"],
        validation_dataset_snapshot_id=U["validation"],
        assumption_profile_id="P6_ASSUMPTION_PROFILE_TEST",
        assumption_profile_version="1.0.0",
        policy=policy,
    )
    assert forecast.forecast_request_id.startswith("P6_FORECAST_REQUEST_SHA256:")
    assert forecast.input_snapshot_id == snapshot.input_snapshot_id
    assert forecast.training_dataset_snapshot_id != forecast.validation_dataset_snapshot_id

    counterfactual = build_p6_counterfactual_request_binding(
        input_snapshot=snapshot,
        base_product_refs=tuple(reversed(snapshot.factual_source_refs)),
        scenario_definition_id=U["context"],
        interventions={"training_condition": "changed"},
        held_fixed_assumptions={"environment": "held"},
        model_refs=(U["model"],),
        applicability_profile_ref="P6_APPLICABILITY_PROFILE_TEST:1.0.0",
        policy=policy,
    )
    assert counterfactual.counterfactual_request_id.startswith(
        "P6_COUNTERFACTUAL_REQUEST_SHA256:"
    )
    assert counterfactual.base_product_refs == tuple(
        sorted(snapshot.factual_source_refs)
    )


def test_m9_batch1_alias_future_same_outcome_and_overlap_fail_closed(
    policy: P6AuthorityPolicy,
) -> None:
    with pytest.raises(P6GovernanceError) as alias:
        build_p6_input_snapshot(
            factual_sources=(replace(_sources()[0], revision_id="LATEST"),),
            target_scope="SUBJECT",
            subject_or_composition_ref="subject:test",
            forecast_origin_utc="2026-10-01T09:00:00Z",
            as_of_utc="2026-10-01T09:00:00Z",
            policy=policy,
        )
    assert alias.value.code == "FAIL_CLOSED_P6_CURRENT_LATEST_DEFAULT_FORBIDDEN"

    with pytest.raises(P6GovernanceError) as future:
        build_p6_input_snapshot(
            factual_sources=(
                replace(
                    _sources()[0],
                    knowledge_time_utc="2026-10-01T10:00:00Z",
                ),
            ),
            target_scope="SUBJECT",
            subject_or_composition_ref="subject:test",
            forecast_origin_utc="2026-10-01T09:00:00Z",
            as_of_utc="2026-10-01T10:00:00Z",
            policy=policy,
        )
    assert future.value.code == "FAIL_CLOSED_P6_FUTURE_INFORMATION"

    with pytest.raises(P6GovernanceError) as outcome:
        build_p6_input_snapshot(
            factual_sources=(replace(_sources()[0], is_target_outcome=True),),
            target_scope="SUBJECT",
            subject_or_composition_ref="subject:test",
            forecast_origin_utc="2026-10-01T09:00:00Z",
            as_of_utc="2026-10-01T09:00:00Z",
            policy=policy,
        )
    assert outcome.value.code == "FAIL_CLOSED_P6_SAME_OUTCOME_LEAKAGE"

    snapshot = _snapshot(policy)
    with pytest.raises(P6GovernanceError) as overlap:
        build_p6_forecast_request_binding(
            input_snapshot=snapshot,
            forecast_spec_id="P6_FORECAST_SPEC_TEST",
            forecast_spec_version="1.0.0",
            target_code="TRAINING_PERFORMANCE_DELTA",
            horizon_spec={"seconds": 60},
            capability_model_id=U["model"],
            model_profile_id="P6_MODEL_PROFILE_TEST",
            model_profile_version="1.0.0",
            training_dataset_snapshot_id=U["training"],
            validation_dataset_snapshot_id=U["training"],
            assumption_profile_id="P6_ASSUMPTION_PROFILE_TEST",
            assumption_profile_version="1.0.0",
            policy=policy,
        )
    assert overlap.value.code == "FAIL_CLOSED_P6_TRAINING_VALIDATION_LEAKAGE"


def test_m9_batch1_unavailable_and_ood_zero_coercion_fail_closed(
    policy: P6AuthorityPolicy,
) -> None:
    with pytest.raises(P6GovernanceError) as unavailable:
        validate_availability_numeric(
            status="UNAVAILABLE",
            numeric_value=0.0,
            policy=policy,
        )
    assert unavailable.value.code == "FAIL_CLOSED_P6_OOD_ZERO_COERCION"

    with pytest.raises(P6GovernanceError) as ood:
        validate_availability_numeric(
            status="OUT_OF_DOMAIN",
            numeric_value=0,
            policy=policy,
        )
    assert ood.value.code == "FAIL_CLOSED_P6_OOD_ZERO_COERCION"


def test_m9_batch1_interop_identity_is_order_stable(
    policy: P6AuthorityPolicy,
) -> None:
    first = _interop(policy)
    second = _interop(policy, artifacts=tuple(reversed(_artifacts())))
    assert first.interop_snapshot_id == second.interop_snapshot_id
    assert first.interop_snapshot_id.startswith("P6_INTEROP_SHA256:")
    assert first.artifact_refs == tuple(sorted(first.artifact_refs))
    assert first.canonical_entity_refs == tuple(sorted(first.canonical_entity_refs))
    assert_p6_interop_snapshot_identity(first)

    with pytest.raises(P6GovernanceError) as drift:
        assert_p6_interop_snapshot_identity(replace(first, logical_content_hash=H))
    assert drift.value.code == "FAIL_CLOSED_P6_INTEROP_PROFILE_REQUIRED"


def test_m9_batch1_interop_alias_lossy_conflation_and_future_fail_closed(
    policy: P6AuthorityPolicy,
) -> None:
    with pytest.raises(P6GovernanceError) as alias:
        _interop(policy, external_profile_version="LATEST")
    assert alias.value.code == "FAIL_CLOSED_P6_CURRENT_LATEST_DEFAULT_FORBIDDEN"

    with pytest.raises(P6GovernanceError) as lossy:
        _interop(policy, lossless_phase_mapping=False)
    assert lossy.value.code == "FAIL_CLOSED_P6_INTEROP_LOSSY_MAPPING"

    with pytest.raises(P6GovernanceError) as conflation:
        _interop(policy, payload_class="P6_PROJECTION")
    assert conflation.value.code == "FAIL_CLOSED_P6_FACT_PROJECTION_CONFLATION"

    with pytest.raises(P6GovernanceError) as future:
        _interop(policy, source_available_at_utc="2026-10-01T10:00:00Z")
    assert future.value.code == "FAIL_CLOSED_P6_FUTURE_INFORMATION"


def test_m9_batch1_p6_release_and_p1_p5_mutation_remain_fail_closed(
    policy: P6AuthorityPolicy,
) -> None:
    with pytest.raises(P6GovernanceError) as release:
        _interop(
            policy,
            artifacts=_artifacts("P6_PROJECTION"),
            source_class="P6_PROJECTION",
            payload_class="P6_PROJECTION",
            release_state="RELEASED",
        )
    assert release.value.code == "FAIL_CLOSED_P6_NOT_ADMITTED"

    with pytest.raises(P6GovernanceError) as claim:
        assert_p6_claim_allowed("P6", policy=policy)
    assert claim.value.code == "FAIL_CLOSED_P6_NOT_ADMITTED"

    assert_p1_p5_immutable({"revision": U["p4"]}, {"revision": U["p4"]})
    with pytest.raises(P6GovernanceError) as mutation:
        assert_p1_p5_immutable(
            {"revision": U["p4"]},
            {"revision": U["p5"]},
        )
    assert mutation.value.code == "FAIL_CLOSED_P6_P1_P5_MUTATION_FORBIDDEN"
