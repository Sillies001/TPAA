from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_ed2_b2_continuous_producers_are_runtime_owned_and_worker_governed() -> None:
    worker = (
        ROOT / "src" / "tpaa_runtime" / "production_worker.py"
    ).read_text(encoding="utf-8")
    jobs = (
        ROOT / "src" / "tpaa_runtime" / "durable_jobs.py"
    ).read_text(encoding="utf-8")
    downstream = (
        ROOT / "src" / "tpaa_runtime" / "production_downstream.py"
    ).read_text(encoding="utf-8")

    assert 'P3_BUILD_COMMAND = "P3_BUILD_PRODUCTS"' in worker
    assert 'P6_BUILD_COMMAND = "P6_BUILD_PRODUCTS"' in worker
    assert "execute_capability_model(" in worker
    assert "build_capability_surface(" in worker
    assert "publish_aircraft_twin_revision(" in worker
    assert "execute_p6_model_training(" in worker
    assert "build_p6_input_snapshot(" in worker
    assert "build_p4_subject_context(" in worker
    assert "build_p5_composition_snapshot(" in worker
    assert "evaluate_ed2_training_assessment(" in worker
    p6_build = worker.split("def _execute_p6_build", maxsplit=1)[1].split(
        "def _execute_p6_forecast",
        maxsplit=1,
    )[0]
    assert "model_as_of_utc: str" in worker
    assert "as_of_utc=body.model_as_of_utc" in p6_build
    assert "as_of_utc=body.as_of_utc" in p6_build
    assert 'production_input.get("model_as_of_utc")' in downstream

    assert "prepare_p2_compute_input(" in jobs
    assert "prepare_p3_build_worker_input(" in jobs
    assert "prepare_p4_build_worker_input(" in jobs
    assert "prepare_p5_build_worker_input(" in jobs
    assert "prepare_p6_build_worker_input(" in jobs
    assert "persist_p3_worker_product(" in jobs
    assert "persist_p4_worker_product(" in jobs
    assert "persist_p5_worker_product(" in jobs
    assert "persist_p6_worker_product(" in jobs

    assert "P2PersistenceRepository" in downstream
    assert "P3PersistenceRepository" in downstream
    assert "P4P5PersistenceRepository" in downstream
    assert "P6PersistenceRepository" in downstream
    for source in (worker, jobs, downstream):
        assert "tpaa_qualification" not in source
        assert "prcb_c5" not in source.lower()
        assert "tests/fixtures" not in source
        assert "InMemory" not in source


def test_ed2_b2_assessment_profile_is_additive_to_frozen_cb_1_4_0() -> None:
    profile_path = (
        ROOT
        / "docs"
        / "baseline"
        / "ED2-CONFORMANCE"
        / "TRAINING_ASSESSMENT_PROFILE.json"
    )
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    assert profile["profile_id"] == "ED2_TRAINING_ASSESSMENT_NON_NUMERIC_GATE_V1"
    assert profile["authority"]["core_baseline"] == "CB-1.4.0"
    assert profile["authority"]["physical_db_authority"] == "1.9.0"
    assert profile["authority"]["numeric_scoring_authority"] == "NONE"
    assert profile["authority"]["p4_score_must_remain_null"] is True
    assert profile["authority"]["p5_overall_score_must_remain_null"] is True
    assert profile["authority"]["causal_upgrade_forbidden"] is True

    frozen = ROOT / "baseline" / "CB-1.4.0" / "canonical"
    assert not (frozen / "TRAINING_ASSESSMENT_PROFILE.json").exists()


def test_ed2_b2_installed_chain_binds_p6_scenario_and_eight_session_report() -> None:
    qualification = (
        ROOT / "src" / "tpaa_qualification" / "ed2_b2_continuous.py"
    ).read_text(encoding="utf-8")
    assert '"context_ref_id": scenario_definition_id' in qualification
    assert '"scenario_definition_id": scenario_definition_id' in qualification

    for path in (
        ROOT / "tools" / "testing" / "prcb_c5_installed_desktop_qualification.py",
        ROOT / "tools" / "testing" / "prcb_c5_installed_service_qualification.py",
    ):
        source = path.read_text(encoding="utf-8")
        assert 'ed2_b2.get("session_ids", []))) != 8' in source
        assert 'ed2_b2.get("p1_release_ids", []))) != 8' in source
