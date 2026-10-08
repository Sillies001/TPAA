from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_prcb_c2_production_runtime_has_no_fixture_or_inmemory_authority() -> None:
    paths = [
        ROOT / "src" / "tpaa_runtime" / "production.py",
        ROOT / "src" / "tpaa_runtime" / "durable_jobs.py",
        ROOT / "src" / "tpaa_runtime" / "production_worker.py",
        ROOT / "src" / "tpaa_runtime" / "production_p1_catalog.py",
        ROOT / "src" / "tpaa_runtime" / "production_p1_materialization.py",
        ROOT / "src" / "tpaa_runtime" / "production_p1_request.py",
        ROOT / "src" / "tpaa_runtime" / "production_p1_source_policy.py",
        ROOT / "src" / "tpaa_ingest" / "production_flight_json.py",
        ROOT / "src" / "tpaa_ingest" / "production_interchange_json.py",
        ROOT / "src" / "tpaa_episode" / "production_stage.py",
        ROOT / "src" / "tpaa_runtime" / "production_p1_world.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "tests/fixtures" not in source
    assert "m1_fixture_root" not in source
    assert "InMemory" not in source


def test_prcb_c2_platform_worker_remains_business_rule_free() -> None:
    source = (ROOT / "src" / "tpaa_platform" / "worker.py").read_text(
        encoding="utf-8"
    )
    assert "GOVERNED_WORKER_HANDLERS" in source
    assert "tpaa_runtime.production_worker:execute" in source
    for forbidden in (
        "import tpaa_metric",
        "from tpaa_metric",
        "import tpaa_world",
        "from tpaa_world",
        "import tpaa_assessment",
        "from tpaa_assessment",
        "import tpaa_episode",
        "from tpaa_episode",
    ):
        assert forbidden not in source


def test_prcb_c2_qualification_source_is_outside_test_fixture_package() -> None:
    source = (
        ROOT
        / "docs"
        / "baseline"
        / "PRCB-1.0"
        / "qualification"
        / "PRCB_C2_NOMINAL_FLIGHT.json"
    )
    assert source.is_file()
    assert "tests/fixtures" not in source.as_posix()
    text = source.read_text(encoding="utf-8")
    assert '"schema": "TPAA_PRODUCTION_FLIGHT_SOURCE_V1"' in text



def test_ed2_b1_production_p1_cannot_regress_to_representative_subset() -> None:
    worker = (
        ROOT / "src" / "tpaa_runtime" / "production_worker.py"
    ).read_text(encoding="utf-8")
    catalog = (
        ROOT / "src" / "tpaa_runtime" / "production_p1_catalog.py"
    ).read_text(encoding="utf-8")

    assert "_REPRESENTATIVE_CODES" not in worker
    assert "compute_representative_metrics" not in worker
    assert "PRODUCTION_P1_CATALOG_METRIC_COUNT: Final = 116" in catalog
    assert "build_m3_metric_execution_plan" in catalog
    assert "build_m3_runtime_plugin_registry" in catalog



def test_ed2_b1_production_world_requires_stage_truth_and_machine_authority() -> None:
    worker = (
        ROOT / "src" / "tpaa_runtime" / "production_worker.py"
    ).read_text(encoding="utf-8")
    stage = (
        ROOT / "src" / "tpaa_episode" / "production_stage.py"
    ).read_text(encoding="utf-8")
    jobs = (
        ROOT / "src" / "tpaa_runtime" / "durable_jobs.py"
    ).read_text(encoding="utf-8")

    assert 'world_kind="CONTEXT"' in worker
    assert 'world_kind="TRUTH"' in worker
    assert 'world_kind="ACTION"' in worker
    assert 'world_kind="MACHINE"' in worker
    assert "project_production_basic_stages" in worker
    assert "CoreWorldRelationRecord" in worker
    assert 'relation_type="PRECEDES"' in worker
    assert '"episode.episode_stage": "stage_id"' in jobs

    assert 'PRODUCTION_STAGE_PROFILE_ID = "BASIC_FLIGHT_V1"' in stage
    assert '"SETUP_ENTRY"' in stage
    assert '"EXECUTION"' in stage
    assert '"STABILIZATION_RECOVERY"' in stage
    assert '"COMPLETION"' in stage
    assert 'PRODUCTION_STAGE_PRECEDENCE_SOURCE = "CONTEXT_OFFICIAL_MARKER"' in stage
    assert 'PRODUCTION_STAGE_DETECTION_METHOD = "CONTEXT"' in stage
    assert "tests/fixtures" not in stage
    assert "load_synthetic_fixture_bundle" not in stage
    world_policy = (
        ROOT / "src" / "tpaa_runtime" / "production_p1_world.py"
    ).read_text(encoding="utf-8")
    flight = (
        ROOT / "src" / "tpaa_ingest" / "production_flight_json.py"
    ).read_text(encoding="utf-8")
    assert 'PRODUCTION_P1_WORLD_CAPABILITY_CODE: Final = "BASIC_CORE"' in world_policy
    assert 'PRODUCTION_P1_REQUIRED_WORLD_LETTERS: Final = ("C", "W", "A", "M")' in world_policy
    assert "TPAA_ED2_BASIC_FLIGHT_ACTION_PROJECTION_V1" in flight
    assert "BASIC_FLIGHT_ACTION_V1" in flight
