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
        ROOT / "src" / "tpaa_ingest" / "production_flight_json.py",
        ROOT / "src" / "tpaa_ingest" / "production_interchange_json.py",
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
