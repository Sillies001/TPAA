from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_prcb_c2_p2_precompute_inputs_are_durable_and_fixture_free() -> None:
    source = (
        ROOT / "src" / "tpaa_application" / "p2_persistence.py"
    ).read_text(encoding="utf-8")
    assert "TPAA_P2_DURABLE_COMPUTE_INPUT_V1" in source
    assert "def exact_compute_input(" in source
    assert "cohort_feature_sets" in source
    assert "reference_factor_values" in source
    assert "tests/fixtures" not in source

    runtime = (ROOT / "src" / "tpaa_runtime" / "durable_jobs.py").read_text(
        encoding="utf-8"
    )
    worker = (ROOT / "src" / "tpaa_runtime" / "production_worker.py").read_text(
        encoding="utf-8"
    )
    assert 'P2_ATTRIBUTION_COMMAND = "P2_ATTRIBUTION"' in worker
    assert "ProductionP2AttributionWorkerInput" in worker
    assert "execute_p2_attribution(" in worker
    assert "def _execute_p2_attribution(" in runtime
    assert "exact_compute_input(dataset_snapshot_id)" in runtime
    assert "compute_job_id=job_id" in runtime
    assert "P2ReleaseRepository(uow.canonical_rows).publish(" in runtime
    assert ").succeed(job_id)" in runtime
    assert "tests/fixtures" not in runtime
