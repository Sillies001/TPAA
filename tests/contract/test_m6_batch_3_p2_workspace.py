from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tpaa_api import create_m6_app
from tpaa_application import (
    ApplicationService,
    InMemoryM6P2WorkspaceRepository,
    M6ApplicationError,
    M6P2ComparisonQuery,
    M6P2DiagnosticsQuery,
    M6P2WorkspaceSnapshot,
    M6WorkspaceService,
)
from tpaa_assessment import (
    P1ObservationInput,
    P2AdjustedCapabilityEstimate,
    P2ArtifactBinding,
    P2AttributionRunProduct,
    P2AttributionSpec,
    P2CohortSnapshot,
    P2FactorFeatureSet,
    P2InputBundle,
    P2ReferenceCondition,
)
from tpaa_gui import (
    M6_P2_STATUS_STYLES,
    M6WorkspacePresentationError,
    build_m6_comparison_workspace_model,
    build_m6_diagnostics_workspace_model,
)

ROOT = Path(__file__).resolve().parents[2]
P2_RELEASE = "86000000-0000-4000-8000-000000000001"
ESTIMATE = "86000000-0000-4000-8000-000000000002"
SOURCE_OBSERVATION = "86000000-0000-4000-8000-000000000003"
SOURCE_RELEASE = "86000000-0000-4000-8000-000000000004"
RUN = "86000000-0000-4000-8000-000000000005"
REFERENCE = "86000000-0000-4000-8000-000000000006"
FEATURE_SET = "86000000-0000-4000-8000-000000000007"
COHORT = "86000000-0000-4000-8000-000000000008"
EVIDENCE = "86000000-0000-4000-8000-000000000009"
AIRCRAFT = "86000000-0000-4000-8000-000000000010"


class _StorageStatus:
    def execute(self):
        raise AssertionError("storage baseline is not used by M6 routes")


def _artifact(
    *,
    identity: str,
    object_ref: str,
    kind: str,
    logical_key: str,
    schema: str,
    sha: str,
) -> P2ArtifactBinding:
    return P2ArtifactBinding(
        context_artifact_id=identity,
        object_ref_id=object_ref,
        artifact_kind=kind,
        logical_key=logical_key,
        artifact_version="1.0.0",
        schema_version=schema,
        artifact_sha256=sha,
        status="ACTIVE",
        sealed=True,
    )


def _snapshot(
    *,
    identifiable: bool = True,
) -> M6P2WorkspaceSnapshot:
    target = P1ObservationInput(
        observation_id=SOURCE_OBSERVATION,
        release_id=SOURCE_RELEASE,
        release_status="PUBLISHED",
        release_sealed=True,
        episode_id="86000000-0000-4000-8000-000000000011",
        subject_entity_id="86000000-0000-4000-8000-000000000012",
        aircraft_id=AIRCRAFT,
        aircraft_model_id="86000000-0000-4000-8000-000000000013",
        aircraft_configuration_snapshot_id=(
            "86000000-0000-4000-8000-000000000014"
        ),
        context_id="86000000-0000-4000-8000-000000000015",
        capability_type="KINEMATIC_ENERGY_CONTROL",
        metric_semantic_id="metric.test.p2.workspace",
        metric_semantic_version=1,
        comparison_key_hash="1" * 64,
        evidence_set_id="86000000-0000-4000-8000-000000000016",
        observed_value=17.0,
        unit="1",
        coverage=1.0,
        confidence=0.9,
        eligibility_status="ELIGIBLE",
        knowledge_time_utc="2026-09-01T00:00:00Z",
    )
    feature_spec = _artifact(
        identity="86000000-0000-4000-8000-000000000017",
        object_ref="86000000-0000-4000-8000-000000000018",
        kind="ASSESSMENT_PROFILE",
        logical_key="P2_FACTOR_FEATURE_SPEC:QUALIFICATION_V1",
        schema="TPAA_P2_FACTOR_FEATURE_SPEC_V1",
        sha="2" * 64,
    )
    reference_binding = _artifact(
        identity=REFERENCE,
        object_ref="86000000-0000-4000-8000-000000000019",
        kind="REFERENCE_SET",
        logical_key="P2_REFERENCE_CONDITION:QUALIFICATION_V1",
        schema="TPAA_P2_REFERENCE_CONDITION_V1",
        sha="3" * 64,
    )
    reference = P2ReferenceCondition(
        reference_condition_id=REFERENCE,
        binding=reference_binding,
    )
    spec_binding = _artifact(
        identity="86000000-0000-4000-8000-000000000020",
        object_ref="86000000-0000-4000-8000-000000000021",
        kind="ASSESSMENT_PROFILE",
        logical_key="P2_ATTRIBUTION_SPEC:P2_LINEAR_REFERENCE_ADJUSTMENT",
        schema="TPAA_P2_ATTRIBUTION_SPEC_V1",
        sha="4" * 64,
    )
    spec = P2AttributionSpec(
        attribution_spec_id="P2_ATTRIBUTION_SPEC:P2_LINEAR_REFERENCE_ADJUSTMENT",
        attribution_spec_version="1.0.0",
        model_plugin="LINEAR_REFERENCE_ADJUSTMENT",
        model_plugin_version="1.0.0",
        uncertainty_method="JACKKNIFE_LEAVE_ONE_INDEPENDENT_SUBJECT_OUT",
        uncertainty_level="0.95",
        binding=spec_binding,
    )
    cohort = P2CohortSnapshot(
        dataset_snapshot_id=COHORT,
        snapshot_type="P2_ATTRIBUTION_COHORT",
        data_hash="5" * 64,
        schema_version="1.6.0",
        frozen=True,
        cohort_spec_id="P2_COHORT_QUALIFICATION_V1",
        cohort_spec_version="1.0.0",
        comparability_dimensions=(
            ("capability_type", target.capability_type),
            ("metric_semantic_id", target.metric_semantic_id),
            ("metric_semantic_version", 1),
            ("unit", target.unit),
            ("aircraft_model_id", target.aircraft_model_id),
            ("comparison_key_hash", target.comparison_key_hash),
        ),
        knowledge_cutoff_utc="2026-09-01T00:00:00Z",
        raw_record_count=5,
        observation_count=5,
        independent_subject_count=5,
        effective_evidence_count=5.0,
        observation_ids=tuple(
            f"86000000-0000-4000-8000-{index:012d}"
            for index in range(30, 35)
        ),
        episode_ids=tuple(
            f"86000000-0000-4000-8000-{index:012d}"
            for index in range(40, 45)
        ),
        subject_ids=tuple(
            f"86000000-0000-4000-8000-{index:012d}"
            for index in range(50, 55)
        ),
    )
    bundle = P2InputBundle(
        target=target,
        feature_spec=feature_spec,
        reference_condition=reference,
        cohort=cohort,
        attribution_spec=spec,
        as_of_utc="2026-09-10T00:00:00Z",
        input_hash="6" * 64,
    )
    feature = P2FactorFeatureSet(
        factor_feature_set_id=FEATURE_SET,
        feature_spec_id=feature_spec.logical_key,
        feature_spec_version=feature_spec.artifact_version,
        source_observation_id=SOURCE_OBSERVATION,
        reference_condition_id=REFERENCE,
        feature_values=(("x", 3.0),),
        missing_mask=(("x", False),),
        world_refs=("86000000-0000-4000-8000-000000000022",),
        coverage=1.0,
        confidence=0.9,
        input_hash="7" * 64,
        created_at="2026-09-10T00:00:00Z",
    )
    diagnostics = {
        "reason_codes": [] if identifiable else ["MODEL_SPEC_DIAGNOSTIC_FAILURE"],
        "run_request_hash": "8" * 64,
        "rank_ratio": "0.5",
        "observation_count": 5,
        "independent_subject_count": 5,
        "uncertainty_method": spec.uncertainty_method,
        "uncertainty_level": spec.uncertainty_level,
        "factor_effect_semantics": "MODEL_CONDITIONED_ASSOCIATION",
        "claim_level": "ASSOCIATION_ONLY",
    }
    model_artifact = {
        "profile_id": "P2_LINEAR_REFERENCE_ADJUSTMENT",
        "profile_version": "1.0.0",
        "factor_order": ["x"],
        "diagnostics": diagnostics,
    }
    model_json = (
        json.dumps(
            model_artifact,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        if identifiable
        else None
    )
    model_hash = (
        hashlib.sha256(model_json.encode("ascii")).hexdigest()
        if model_json is not None
        else None
    )
    status = "IDENTIFIABLE" if identifiable else "NOT_IDENTIFIABLE"
    run = P2AttributionRunProduct(
        attribution_run_id=RUN,
        attribution_spec_id=spec.attribution_spec_id,
        attribution_spec_version=spec.attribution_spec_version,
        model_plugin=spec.model_plugin,
        model_plugin_version=spec.model_plugin_version,
        training_dataset_snapshot_id=COHORT,
        reference_condition_id=REFERENCE,
        status=status,
        diagnostics_json=json.dumps(
            diagnostics,
            sort_keys=True,
            separators=(",", ":"),
        ),
        model_artifact_uri=None,
        model_artifact_hash=model_hash,
        started_at="2026-09-10T00:00:00Z",
        completed_at="2026-09-10T00:00:00Z",
        created_by="M6-TST-004",
        run_request_hash="8" * 64,
    )
    estimate = P2AdjustedCapabilityEstimate(
        estimate_id=ESTIMATE,
        source_observation_id=SOURCE_OBSERVATION,
        source_release_id=SOURCE_RELEASE,
        p2_release_id=P2_RELEASE,
        attribution_run_id=RUN,
        aircraft_id=AIRCRAFT,
        capability_type=target.capability_type,
        reference_condition_id=REFERENCE,
        adjusted_value=15.0 if identifiable else None,
        unit=target.unit,
        uncertainty_lower=14.5 if identifiable else None,
        uncertainty_upper=15.5 if identifiable else None,
        uncertainty_method=spec.uncertainty_method,
        uncertainty_level=spec.uncertainty_level,
        residual=1.0 if identifiable else None,
        factor_effects=(("x", -2.0),) if identifiable else (),
        claim_level="ASSOCIATION_ONLY",
        status=status,
        reason_codes=(
            ()
            if identifiable
            else ("MODEL_SPEC_DIAGNOSTIC_FAILURE",)
        ),
        evidence_set_id=EVIDENCE,
        estimate_time="2026-09-10T00:00:00Z",
        created_at="2026-09-10T00:00:00Z",
        supersedes_estimate_id=None,
        logical_hash="9" * 64,
    )
    return M6P2WorkspaceSnapshot(
        p2_release_id=P2_RELEASE,
        p2_release_status="PUBLISHED",
        p2_release_sealed=True,
        p2_published_at_utc="2026-09-10T00:01:00Z",
        input_bundle=bundle,
        target_feature_set=feature,
        attribution_run=run,
        adjusted_estimate=estimate,
        model_artifact_json=model_json,
    )


def _workspace(
    snapshot: M6P2WorkspaceSnapshot,
) -> tuple[ApplicationService, M6WorkspaceService]:
    repository = InMemoryM6P2WorkspaceRepository()
    repository.register(snapshot)
    workspace = M6WorkspaceService(repository)
    application = ApplicationService(
        get_storage_baseline_status=_StorageStatus(),
        m6_workspace=workspace,
    )
    return application, workspace


def test_m6_gui_001_observed_and_adjusted_are_distinct_exact_products() -> None:
    snapshot = _snapshot()
    application, _workspace_service = _workspace(snapshot)
    payload = application.m6_p2_comparison(
        M6P2ComparisonQuery(P2_RELEASE, ESTIMATE)
    )
    model = build_m6_comparison_workspace_model(
        payload,
        expected_p2_release_id=P2_RELEASE,
        expected_estimate_id=ESTIMATE,
    )
    assert model.observed.source_release_id == SOURCE_RELEASE
    assert model.observed.observed_value == 17.0
    assert model.adjusted.p2_release_id == P2_RELEASE
    assert model.adjusted.attribution_spec_id == (
        "P2_ATTRIBUTION_SPEC:P2_LINEAR_REFERENCE_ADJUSTMENT"
    )
    assert model.adjusted.attribution_spec_version == "1.0.0"
    assert model.adjusted.model_plugin == "LINEAR_REFERENCE_ADJUSTMENT"
    assert model.adjusted.model_plugin_version == "1.0.0"
    assert model.adjusted.p2_published_at_utc == "2026-09-10T00:01:00Z"
    assert model.adjusted.adjusted_value == 15.0
    assert model.adjusted.residual == 1.0
    assert model.adjusted.factor_effects == (("x", -2.0),)
    assert model.adjusted.factor_effect_semantics == "MODEL_CONDITIONED_ASSOCIATION"
    assert model.adjusted.claim_level == "ASSOCIATION_ONLY"
    assert model.adjusted.presentation_kind == "P2_IDENTIFIABLE"
    assert snapshot.input_bundle.target.observed_value == 17.0
    assert snapshot.input_bundle.target.release_id == SOURCE_RELEASE


def test_m6_gui_001_not_identifiable_is_not_zero_na_or_error() -> None:
    application, _workspace_service = _workspace(_snapshot(identifiable=False))
    payload = application.m6_p2_comparison(
        M6P2ComparisonQuery(P2_RELEASE, ESTIMATE)
    )
    model = build_m6_comparison_workspace_model(
        payload,
        expected_p2_release_id=P2_RELEASE,
        expected_estimate_id=ESTIMATE,
    )
    assert model.adjusted.presentation_kind == "P2_NOT_IDENTIFIABLE"
    assert model.adjusted.adjusted_value is None
    assert model.adjusted.residual is None
    assert model.adjusted.factor_effects == ()
    assert model.adjusted.reason_codes == ("MODEL_SPEC_DIAGNOSTIC_FAILURE",)
    assert M6_P2_STATUS_STYLES["P2_NOT_IDENTIFIABLE"] != (
        M6_P2_STATUS_STYLES["P2_SYSTEM_ERROR"]
    )


def test_m6_gui_002_diagnostics_exposes_exact_provenance_without_recompute() -> None:
    application, _workspace_service = _workspace(_snapshot())
    payload = application.m6_p2_diagnostics(
        M6P2DiagnosticsQuery(P2_RELEASE, ESTIMATE)
    )
    model = build_m6_diagnostics_workspace_model(
        payload,
        expected_p2_release_id=P2_RELEASE,
        expected_estimate_id=ESTIMATE,
    )
    assert model.source_release_id == SOURCE_RELEASE
    assert model.source_observation_id == SOURCE_OBSERVATION
    assert model.attribution_run_id == RUN
    assert model.reference_condition_id == REFERENCE
    assert model.p1_knowledge_time_utc == "2026-09-01T00:00:00Z"
    assert model.p2_estimate_time == "2026-09-10T00:00:00Z"
    assert model.as_of_utc == "2026-09-10T00:00:00Z"
    assert model.feature["input_hash"] == "7" * 64
    assert model.cohort["independent_subject_count"] == 5
    assert model.result["factor_effect_semantics"] == (
        "MODEL_CONDITIONED_ASSOCIATION"
    )
    assert model.result["claim_level"] == "ASSOCIATION_ONLY"


def test_m6_api_routes_are_exact_release_bound_and_fail_closed() -> None:
    application, _workspace_service = _workspace(_snapshot())
    client = TestClient(create_m6_app(application))
    comparison = client.get(
        f"/m6/p2/releases/{P2_RELEASE}/estimates/{ESTIMATE}/comparison"
    )
    diagnostics = client.get(
        f"/m6/p2/releases/{P2_RELEASE}/estimates/{ESTIMATE}/diagnostics"
    )
    assert comparison.status_code == 200
    assert diagnostics.status_code == 200
    assert comparison.json()["identity"]["source_release_id"] == SOURCE_RELEASE
    assert diagnostics.json()["identity"]["attribution_run_id"] == RUN

    other_release = "86000000-0000-4000-8000-000000000099"
    mismatch = client.get(
        f"/m6/p2/releases/{other_release}/estimates/{ESTIMATE}/comparison"
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["code"] == "M6_P2_RELEASE_MISMATCH"


def test_m6_tst_004_replay_logical_hashes_are_stable() -> None:
    application, workspace = _workspace(_snapshot())
    first_comparison = workspace.comparison(
        M6P2ComparisonQuery(P2_RELEASE, ESTIMATE)
    )
    second_comparison = application.m6_p2_comparison(
        M6P2ComparisonQuery(P2_RELEASE, ESTIMATE)
    )
    first_diagnostics = workspace.diagnostics(
        M6P2DiagnosticsQuery(P2_RELEASE, ESTIMATE)
    )
    second_diagnostics = application.m6_p2_diagnostics(
        M6P2DiagnosticsQuery(P2_RELEASE, ESTIMATE)
    )
    assert first_comparison["logical_product_hash"] == (
        second_comparison["logical_product_hash"]
    )
    assert first_diagnostics["logical_product_hash"] == (
        second_diagnostics["logical_product_hash"]
    )


def test_m6_tst_004_model_artifact_hash_drift_fails_closed() -> None:
    snapshot = _snapshot()
    run = replace(snapshot.attribution_run, model_artifact_hash="f" * 64)
    repository = InMemoryM6P2WorkspaceRepository()
    with pytest.raises(
        M6ApplicationError,
        match="M6_P2_MODEL_ARTIFACT_HASH_MISMATCH",
    ):
        repository.register(replace(snapshot, attribution_run=run))


def test_m6_tst_004_gui_rejects_transport_logical_hash_drift() -> None:
    application, _workspace_service = _workspace(_snapshot())
    payload = application.m6_p2_comparison(
        M6P2ComparisonQuery(P2_RELEASE, ESTIMATE)
    )
    payload["logical_product_hash"] = "0" * 64
    with pytest.raises(
        M6WorkspacePresentationError,
        match="M6_GUI_LOGICAL_HASH_MISMATCH",
    ):
        build_m6_comparison_workspace_model(
            payload,
            expected_p2_release_id=P2_RELEASE,
            expected_estimate_id=ESTIMATE,
        )


def test_m6_tst_004_read_paths_have_no_current_latest_or_recompute() -> None:
    sources = [
        ROOT / "src" / "tpaa_application" / "m6_workspace.py",
        ROOT / "src" / "tpaa_api" / "m6_app.py",
        ROOT / "src" / "tpaa_gui" / "m6_workspace.py",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    for forbidden in (
        '"/latest"',
        '"/current"',
        "execute_p2_attribution(",
        "materialize_factor_feature_set(",
        "sqlite3",
        "psycopg",
    ):
        assert forbidden not in text


def test_m6_tst_004_baseline_schema_and_later_phases_remain_inactive() -> None:
    lock = json.loads(
        (
            ROOT / "baseline" / "CB-1.4.0" / "BASELINE_LOCK.json"
        ).read_text(encoding="utf-8")
    )
    assert lock["baseline"]["db_schema"] == "1.6.0"

    registry = json.loads(
        (
            ROOT
            / "baseline"
            / "CB-1.4.0"
            / "canonical"
            / "CAPABILITY_PHASE_REGISTRY.json"
        ).read_text(encoding="utf-8")
    )
    phases = {
        item["p_code"]: item["baseline_status"]
        for item in registry["capability_phases"]
    }
    assert phases["P1"] == "CURRENT_BASELINE"
    assert phases["P2"] == "DESIGN_CONTRACT_FROZEN"
    for p_code in ("P3", "P4", "P5", "P6"):
        assert phases[p_code] == "DESIGN_CONTRACT_FROZEN"


def test_m6_tst_004_gui_and_api_respect_architecture_boundary() -> None:
    gui_source = (
        ROOT / "src" / "tpaa_gui" / "m6_workspace.py"
    ).read_text(encoding="utf-8")
    api_source = (
        ROOT / "src" / "tpaa_api" / "m6_app.py"
    ).read_text(encoding="utf-8")
    assert "tpaa_assessment" not in gui_source
    assert "tpaa_application" not in gui_source
    assert "tpaa_assessment" not in api_source
    assert "from tpaa_application import" in api_source
