from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tpaa_api import create_m7_app
from tpaa_application import (
    ApplicationService,
    InMemoryM7P3WorkspaceRepository,
    M7ApplicationError,
    M7LayerEvidence,
    M7P3WorkspaceSnapshot,
    M7TwinQuery,
    M7WorkspaceQuery,
    M7WorkspaceService,
)
from tpaa_capability import (
    P3CapabilityModelBuild,
    P3CapabilityModelProduct,
    P3CapabilitySurfaceBuild,
    P3CapabilitySurfaceProduct,
    P3TwinComponentBinding,
    evaluate_twin_capability_estimate,
    publish_aircraft_twin_revision,
)
from tpaa_gui import (
    M7WorkspacePresentationError,
    build_m7_three_layer_workspace_model,
)
from tpaa_longitudinal import P3AdmissionEvidence, P3GovernanceError

ROOT = Path(__file__).resolve().parents[2]

AIRCRAFT = "87000000-0000-4000-8000-000000000001"
CONFIG = "87000000-0000-4000-8000-000000000002"
EVIDENCE = "87000000-0000-4000-8000-000000000003"
REFERENCE = "87000000-0000-4000-8000-000000000004"
TRAINING = "87000000-0000-4000-8000-000000000005"
MODEL_1 = "87000000-0000-4000-8000-000000000010"
MODEL_OBJECT_1 = "87000000-0000-4000-8000-000000000011"
SURFACE_1 = "87000000-0000-4000-8000-000000000012"
SURFACE_OBJECT_1 = "87000000-0000-4000-8000-000000000013"
MODEL_2 = "87000000-0000-4000-8000-000000000020"
MODEL_OBJECT_2 = "87000000-0000-4000-8000-000000000021"
SURFACE_2 = "87000000-0000-4000-8000-000000000022"
SURFACE_OBJECT_2 = "87000000-0000-4000-8000-000000000023"
P1_RELEASE = "87000000-0000-4000-8000-000000000100"
P2_RELEASE = "87000000-0000-4000-8000-000000000101"
P1_OBSERVATION = "87000000-0000-4000-8000-000000000102"
P2_ESTIMATE = "87000000-0000-4000-8000-000000000103"
EXPECTED_TWIN = "70e19664-804d-5a98-871d-69d217d4ffef"
EXPECTED_ESTIMATE = "4d130ceb-8bb1-5fe2-96fc-45cfd76f4d21"


class _StorageStatus:
    def execute(self):
        raise AssertionError("storage baseline is not used by M7 routes")


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _component(
    *,
    model_id: str,
    model_object_ref_id: str,
    surface_id: str,
    surface_object_ref_id: str,
    capability_type: str,
    value_offset: float,
) -> P3TwinComponentBinding:
    artifact = {"unit": "1"}
    artifact_bytes = _canonical_bytes(artifact)
    artifact_hash = hashlib.sha256(artifact_bytes).hexdigest()
    rows = [
        {
            "session_order": index,
            "value": value_offset + index,
            "uncertainty_lower": value_offset + index - 1.0,
            "uncertainty_upper": value_offset + index + 1.0,
        }
        for index in range(1, 5)
    ]
    dataset = {"rows": rows}
    dataset_bytes = _canonical_bytes(dataset)
    dataset_hash = hashlib.sha256(dataset_bytes).hexdigest()
    validity_domain = {
        "axis": "SESSION_ORDER",
        "session_order_min": 1,
        "session_order_max": 4,
        "reference_condition_id": REFERENCE,
        "extrapolation": "FORBIDDEN",
    }
    model = P3CapabilityModelProduct(
        capability_model_id=model_id,
        model_spec_id=(
            "P3_MODEL_SPEC:P3_REFERENCE_CONDITION_OLS_MAD_LONGITUDINAL"
        ),
        model_spec_version="1.0.0",
        subject_type="AIRCRAFT",
        subject_id=AIRCRAFT,
        capability_type=capability_type,
        training_dataset_snapshot_id=TRAINING,
        plugin_name="REFERENCE_CONDITION_OLS_MAD_LONGITUDINAL",
        plugin_version="1.0.0",
        model_artifact_uri=f"tpaa-object://p3-capability/models/{model_id}.json",
        model_artifact_hash=artifact_hash,
        validity_domain=validity_domain,
        validation_metrics={"status": "VALIDATED"},
        status="VALIDATED",
        trained_at="2026-09-10T02:00:00Z",
        published_at=None,
        supersedes_model_id=None,
    )
    model_build = P3CapabilityModelBuild(
        model=model,
        artifact=artifact,
        artifact_bytes=artifact_bytes,
        intercept=value_offset,
        slope=1.0,
        current_value=value_offset + 4.0,
        ewma_value=value_offset + 2.5,
        stability_mad=1.0,
        p3_uncertainty_half_width=1.0,
        session_order_origin=0,
        fit_estimate_ids=(),
    )
    surface = P3CapabilitySurfaceProduct(
        surface_id=surface_id,
        capability_model_id=model_id,
        surface_semantics="REFERENCE_CONDITION_LONGITUDINAL_SESSION_ORDER",
        axes={"x": "SESSION_ORDER", "min": 1, "max": 4, "step": 1},
        dataset_uri=f"tpaa-object://p3-capability/surfaces/{surface_id}.json",
        dataset_hash=dataset_hash,
        uncertainty_dataset_uri=None,
        validity_domain=validity_domain,
        created_at="2026-09-10T03:00:00Z",
    )
    surface_build = P3CapabilitySurfaceBuild(
        surface=surface,
        dataset=dataset,
        dataset_bytes=dataset_bytes,
    )
    return P3TwinComponentBinding(
        model_build=model_build,
        surface_build=surface_build,
        model_object_ref_id=model_object_ref_id,
        surface_object_ref_id=surface_object_ref_id,
    )


def _components() -> tuple[P3TwinComponentBinding, ...]:
    return (
        _component(
            model_id=MODEL_1,
            model_object_ref_id=MODEL_OBJECT_1,
            surface_id=SURFACE_1,
            surface_object_ref_id=SURFACE_OBJECT_1,
            capability_type="KINEMATIC_ENERGY_CONTROL",
            value_offset=9.0,
        ),
        _component(
            model_id=MODEL_2,
            model_object_ref_id=MODEL_OBJECT_2,
            surface_id=SURFACE_2,
            surface_object_ref_id=SURFACE_OBJECT_2,
            capability_type="SENSOR_TRACK_QUALITY",
            value_offset=99.0,
        ),
    )


def _twin(
    *,
    components: tuple[P3TwinComponentBinding, ...] | None = None,
):
    return publish_aircraft_twin_revision(
        aircraft_id=AIRCRAFT,
        components=components or _components(),
        config_snapshot_id=CONFIG,
        evidence_snapshot_id=EVIDENCE,
        valid_from_utc="2026-09-01T00:00:00Z",
        valid_to_utc=None,
        as_of_data_time_utc="2026-09-10T00:00:00Z",
        published_at_utc="2026-09-10T03:00:00Z",
    )


def _estimate(*, session_order: int = 4):
    components = _components()
    twin = _twin(components=components)
    estimate = evaluate_twin_capability_estimate(
        twin=twin,
        components=components,
        capability_type="KINEMATIC_ENERGY_CONTROL",
        condition_point={
            "session_order": session_order,
            "reference_condition_id": REFERENCE,
        },
        as_of_time_utc="2026-09-10T00:00:00Z",
        created_at_utc="2026-09-10T04:00:00Z",
    )
    return twin, estimate, components


def _layer_evidence() -> tuple[M7LayerEvidence, M7LayerEvidence]:
    observed = {
        "observation_id": P1_OBSERVATION,
        "release_id": P1_RELEASE,
        "observed_value": 17.0,
        "unit": "1",
    }
    adjusted = {
        "estimate_id": P2_ESTIMATE,
        "p2_release_id": P2_RELEASE,
        "adjusted_value": 15.0,
        "unit": "1",
        "claim_level": "ASSOCIATION_ONLY",
    }
    return (
        M7LayerEvidence(
            layer="P1_OBSERVED",
            release_id=P1_RELEASE,
            logical_hash=_canonical_hash(observed),
            projection=observed,
        ),
        M7LayerEvidence(
            layer="P2_ADJUSTED",
            release_id=P2_RELEASE,
            logical_hash=_canonical_hash(adjusted),
            projection=adjusted,
        ),
    )


def _snapshot(*, session_order: int = 4) -> M7P3WorkspaceSnapshot:
    twin, estimate, components = _estimate(session_order=session_order)
    observed, adjusted = _layer_evidence()
    return M7P3WorkspaceSnapshot(
        observed=observed,
        adjusted=adjusted,
        twin=twin,
        estimate=estimate,
        components=components,
    )


def _admission() -> P3AdmissionEvidence:
    return P3AdmissionEvidence(
        source_revision="1" * 40,
        event_name="push",
        git_ref="refs/heads/main",
        protected_main=True,
        m7_exit_decision="GO",
        run_conclusion="success",
        required_jobs_success=14,
        required_jobs_total=14,
        p4_p6_inactive=True,
    )


def _workspace(
    snapshot: M7P3WorkspaceSnapshot,
    *,
    admitted: bool,
) -> tuple[ApplicationService, M7WorkspaceService]:
    repository = InMemoryM7P3WorkspaceRepository()
    repository.register(snapshot)
    service = M7WorkspaceService(
        repository,
        admission_evidence=_admission() if admitted else None,
    )
    application = ApplicationService(
        get_storage_baseline_status=_StorageStatus(),
        m7_workspace=service,
    )
    return application, service


def test_m7_cap_004_twin_identity_is_ordered_immutable_and_exact() -> None:
    components = _components()
    first = _twin(components=components)
    replay = _twin(components=components)
    reversed_twin = _twin(components=tuple(reversed(components)))
    assert first.twin_revision_id == EXPECTED_TWIN
    assert replay == first
    assert first.component_model_refs == (MODEL_1, MODEL_2)
    assert reversed_twin.component_model_refs == (MODEL_2, MODEL_1)
    assert reversed_twin.twin_revision_id != first.twin_revision_id
    assert first.revision_no == 1
    assert first.supersedes_twin_revision_id is None
    assert first.status == "PUBLISHED"
    assert first.as_of_data_time == "2026-09-10T00:00:00Z"


def test_m7_cap_004_supersession_is_new_revision_without_mutating_history() -> None:
    first = _twin()
    second = publish_aircraft_twin_revision(
        aircraft_id=AIRCRAFT,
        components=_components(),
        config_snapshot_id="87000000-0000-4000-8000-000000000030",
        evidence_snapshot_id="87000000-0000-4000-8000-000000000031",
        valid_from_utc="2026-09-11T00:00:00Z",
        valid_to_utc=None,
        as_of_data_time_utc="2026-09-11T00:00:00Z",
        published_at_utc="2026-09-11T03:00:00Z",
        previous_revision=first,
    )
    assert second.revision_no == 2
    assert second.supersedes_twin_revision_id == first.twin_revision_id
    assert second.twin_revision_id != first.twin_revision_id
    assert first.revision_no == 1
    assert first.supersedes_twin_revision_id is None

    with pytest.raises(P3GovernanceError, match="successor valid_from must increase"):
        publish_aircraft_twin_revision(
            aircraft_id=AIRCRAFT,
            components=_components(),
            config_snapshot_id="87000000-0000-4000-8000-000000000030",
            evidence_snapshot_id="87000000-0000-4000-8000-000000000031",
            valid_from_utc="2026-08-31T00:00:00Z",
            valid_to_utc=None,
            as_of_data_time_utc="2026-09-11T00:00:00Z",
            published_at_utc="2026-09-11T03:00:00Z",
            previous_revision=first,
        )


def test_m7_cap_005_estimate_is_exact_claim_bound_and_ood_is_null() -> None:
    twin, estimate, components = _estimate(session_order=4)
    assert twin.twin_revision_id == EXPECTED_TWIN
    assert estimate.estimate_id == EXPECTED_ESTIMATE
    assert estimate.value == 13.0
    assert estimate.uncertainty["lower"] == 12.0
    assert estimate.uncertainty["upper"] == 14.0
    assert estimate.validity_domain_status == "IN_DOMAIN"
    assert estimate.claim_level == "REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE"

    out_of_domain = evaluate_twin_capability_estimate(
        twin=twin,
        components=components,
        capability_type="KINEMATIC_ENERGY_CONTROL",
        condition_point={
            "session_order": 5,
            "reference_condition_id": REFERENCE,
        },
        as_of_time_utc="2026-09-10T00:00:00Z",
        created_at_utc="2026-09-10T04:00:00Z",
    )
    assert out_of_domain.validity_domain_status == "OUT_OF_DOMAIN"
    assert out_of_domain.value is None
    assert out_of_domain.uncertainty["lower"] is None
    assert out_of_domain.uncertainty["upper"] is None

    with pytest.raises(
        P3GovernanceError,
        match="FAIL_CLOSED_P3_CLAIM_EVIDENCE_REQUIRED",
    ):
        evaluate_twin_capability_estimate(
            twin=twin,
            components=components,
            capability_type="KINEMATIC_ENERGY_CONTROL",
            condition_point={
                "session_order": 4,
                "reference_condition_id": REFERENCE,
            },
            as_of_time_utc="2026-09-10T00:00:00Z",
            created_at_utc="2026-09-10T04:00:00Z",
            claim_level="INTRINSIC_CAPABILITY_ESTIMATE",
        )


def test_m7_api_001_pre_exit_service_is_fail_closed() -> None:
    application, service = _workspace(_snapshot(), admitted=False)
    with pytest.raises(M7ApplicationError, match="M7_P3_NOT_ADMITTED"):
        service.twin(M7TwinQuery(EXPECTED_TWIN))

    client = TestClient(create_m7_app(application))
    response = client.get(f"/m7/p3/twins/{EXPECTED_TWIN}")
    assert response.status_code == 423
    assert response.json()["error"]["code"] == "M7_P3_NOT_ADMITTED"


def test_m7_api_001_exact_revision_reads_and_replay() -> None:
    snapshot = _snapshot()
    application, service = _workspace(snapshot, admitted=True)
    client = TestClient(create_m7_app(application))

    twin_response = client.get(f"/m7/p3/twins/{EXPECTED_TWIN}")
    estimate_response = client.get(
        f"/m7/p3/twins/{EXPECTED_TWIN}/estimates/{EXPECTED_ESTIMATE}"
    )
    workspace_response = client.get(
        f"/m7/p3/twins/{EXPECTED_TWIN}/estimates/{EXPECTED_ESTIMATE}/workspace"
    )
    assert twin_response.status_code == 200
    assert estimate_response.status_code == 200
    assert workspace_response.status_code == 200
    assert twin_response.json()["twin"]["twin_revision_id"] == EXPECTED_TWIN
    assert estimate_response.json()["estimate"]["estimate_id"] == EXPECTED_ESTIMATE

    first = service.workspace(
        M7WorkspaceQuery(EXPECTED_TWIN, EXPECTED_ESTIMATE)
    )
    second = application.m7_p3_workspace(
        M7WorkspaceQuery(EXPECTED_TWIN, EXPECTED_ESTIMATE)
    )
    assert first["logical_product_hash"] == second["logical_product_hash"]
    assert workspace_response.json()["logical_product_hash"] == (
        first["logical_product_hash"]
    )

    missing = "87000000-0000-4000-8000-000000000099"
    not_found = client.get(f"/m7/p3/twins/{missing}")
    assert not_found.status_code == 404
    mismatch = client.get(
        f"/m7/p3/twins/{missing}/estimates/{EXPECTED_ESTIMATE}"
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["code"] == "M7_TWIN_ESTIMATE_MISMATCH"


def test_m7_gui_001_three_layers_are_visibly_distinct_and_exact() -> None:
    application, _service = _workspace(_snapshot(), admitted=True)
    payload = application.m7_p3_workspace(
        M7WorkspaceQuery(EXPECTED_TWIN, EXPECTED_ESTIMATE)
    )
    model = build_m7_three_layer_workspace_model(
        payload,
        expected_twin_revision_id=EXPECTED_TWIN,
        expected_estimate_id=EXPECTED_ESTIMATE,
    )
    assert model.observed.layer == "P1_OBSERVED"
    assert model.observed.release_id == P1_RELEASE
    assert model.adjusted.layer == "P2_ADJUSTED"
    assert model.adjusted.release_id == P2_RELEASE
    assert model.p3.twin_revision_id == EXPECTED_TWIN
    assert model.p3.estimate_id == EXPECTED_ESTIMATE
    assert model.p3.value == 13.0
    assert model.p3.validity_domain_status == "IN_DOMAIN"
    assert model.p3.claim_level == "REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE"
    assert model.p3.reference_condition_id == REFERENCE

    ood_application, _ood_service = _workspace(
        _snapshot(session_order=5),
        admitted=True,
    )
    ood_payload = ood_application.m7_p3_workspace(
        M7WorkspaceQuery(
            EXPECTED_TWIN,
            _snapshot(session_order=5).estimate.estimate_id,
        )
    )
    ood = build_m7_three_layer_workspace_model(
        ood_payload,
        expected_twin_revision_id=EXPECTED_TWIN,
        expected_estimate_id=_snapshot(session_order=5).estimate.estimate_id,
    )
    assert ood.p3.validity_domain_status == "OUT_OF_DOMAIN"
    assert ood.p3.value is None
    assert ood.p3.uncertainty_lower is None
    assert ood.p3.uncertainty_upper is None


def test_m7_tst_004_p1_p2_hashes_are_nonregressing_and_repository_is_immutable() -> None:
    snapshot = _snapshot()
    observed_before = dict(snapshot.observed.projection)
    adjusted_before = dict(snapshot.adjusted.projection)
    observed_hash = snapshot.observed.logical_hash
    adjusted_hash = snapshot.adjusted.logical_hash

    repository = InMemoryM7P3WorkspaceRepository()
    repository.register(snapshot)
    service = M7WorkspaceService(repository, admission_evidence=_admission())
    service.workspace(M7WorkspaceQuery(EXPECTED_TWIN, EXPECTED_ESTIMATE))

    assert dict(snapshot.observed.projection) == observed_before
    assert dict(snapshot.adjusted.projection) == adjusted_before
    assert snapshot.observed.logical_hash == observed_hash
    assert snapshot.adjusted.logical_hash == adjusted_hash
    assert _canonical_hash(observed_before) == observed_hash
    assert _canonical_hash(adjusted_before) == adjusted_hash

    changed_observed = {**observed_before, "observed_value": 99.0}
    changed_layer = replace(
        snapshot.observed,
        logical_hash=_canonical_hash(changed_observed),
        projection=changed_observed,
    )
    with pytest.raises(M7ApplicationError, match="M7_P3_IMMUTABLE_CONFLICT"):
        repository.register(replace(snapshot, observed=changed_layer))


def test_m7_tst_004_gui_rejects_transport_hash_and_claim_drift() -> None:
    application, _service = _workspace(_snapshot(), admitted=True)
    payload = application.m7_p3_workspace(
        M7WorkspaceQuery(EXPECTED_TWIN, EXPECTED_ESTIMATE)
    )
    payload["logical_product_hash"] = "0" * 64
    with pytest.raises(
        M7WorkspacePresentationError,
        match="M7_GUI_LOGICAL_HASH_MISMATCH",
    ):
        build_m7_three_layer_workspace_model(
            payload,
            expected_twin_revision_id=EXPECTED_TWIN,
            expected_estimate_id=EXPECTED_ESTIMATE,
        )

    valid = application.m7_p3_workspace(
        M7WorkspaceQuery(EXPECTED_TWIN, EXPECTED_ESTIMATE)
    )
    p3 = valid["p3"]
    assert isinstance(p3, dict)
    estimate = p3["estimate"]
    assert isinstance(estimate, dict)
    estimate["claim_level"] = "INTRINSIC_CAPABILITY_ESTIMATE"
    material = {key: value for key, value in valid.items() if key != "logical_product_hash"}
    valid["logical_product_hash"] = _canonical_hash(material)
    with pytest.raises(
        M7WorkspacePresentationError,
        match="M7_GUI_CLAIM_LEVEL_INVALID",
    ):
        build_m7_three_layer_workspace_model(
            valid,
            expected_twin_revision_id=EXPECTED_TWIN,
            expected_estimate_id=EXPECTED_ESTIMATE,
        )


def test_m7_tst_004_read_paths_have_no_current_latest_or_recompute() -> None:
    sources = [
        ROOT / "src" / "tpaa_application" / "m7_workspace.py",
        ROOT / "src" / "tpaa_api" / "m7_app.py",
        ROOT / "src" / "tpaa_gui" / "m7_workspace.py",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    for forbidden in (
        '"/latest"',
        '"/current"',
        "execute_capability_model(",
        "evaluate_twin_capability_estimate(",
        "sqlite3",
        "psycopg",
    ):
        assert forbidden not in text


def test_m7_tst_004_schema_and_later_phases_remain_fail_closed() -> None:
    lock = json.loads(
        (
            ROOT / "baseline" / "CB-1.4.0" / "BASELINE_LOCK.json"
        ).read_text(encoding="utf-8")
    )
    assert lock["baseline"]["db_schema"] in {"1.6.0", "1.7.0"}
    authority = json.loads(
        (
            ROOT
            / "baseline"
            / "CB-1.4.0"
            / "canonical"
            / "P3_CAPABILITY_TWIN_AUTHORITY.json"
        ).read_text(encoding="utf-8")
    )
    assert authority["scope"]["p3_authority_frozen_not_admitted"] is True
    assert authority["scope"]["p4_p6_active"] is False
    assert authority["claim_contract"]["profile_v1_allowed_claim_levels"] == [
        "REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE"
    ]


def test_m7_tst_004_gui_and_api_respect_architecture_boundary() -> None:
    gui_source = (
        ROOT / "src" / "tpaa_gui" / "m7_workspace.py"
    ).read_text(encoding="utf-8")
    api_source = (
        ROOT / "src" / "tpaa_api" / "m7_app.py"
    ).read_text(encoding="utf-8")
    assert "tpaa_capability" not in gui_source
    assert "tpaa_application" not in gui_source
    assert "tpaa_capability" not in api_source
    assert "from tpaa_application import" in api_source
