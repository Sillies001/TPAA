from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_prcb_c2_p3_estimate_routes_through_durable_spawn_worker() -> None:
    worker = (ROOT / "src" / "tpaa_runtime" / "production_worker.py").read_text(
        encoding="utf-8"
    )
    jobs = (ROOT / "src" / "tpaa_runtime" / "durable_jobs.py").read_text(
        encoding="utf-8"
    )
    assert 'P3_ESTIMATE_COMMAND = "P3_ESTIMATE"' in worker
    assert "evaluate_twin_capability_estimate(" in worker
    assert "ProductionP3EstimateWorkerInput" in jobs
    assert "exact_twin_revision(" in jobs
    assert "exact_twin_components(" in jobs
    assert "register_estimate(value)" in jobs
    assert "tests/fixtures" not in worker
    assert "tests/fixtures" not in jobs
