from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_prcb_c2_p6_compute_is_routed_through_governed_worker() -> None:
    worker = (ROOT / "src" / "tpaa_runtime" / "production_worker.py").read_text(
        encoding="utf-8"
    )
    jobs = (ROOT / "src" / "tpaa_runtime" / "durable_jobs.py").read_text(
        encoding="utf-8"
    )
    assert 'P6_FORECAST_COMMAND = "P6_FORECAST"' in worker
    assert 'P6_COUNTERFACTUAL_COMMAND = "P6_COUNTERFACTUAL"' in worker
    assert "execute_p6_forecast(" in worker
    assert "execute_p6_counterfactual(" in worker
    assert "P6PersistenceRepository" in jobs
    assert "ProductionP6ForecastWorkerInput" in jobs
    assert "ProductionP6CounterfactualWorkerInput" in jobs
    assert "tests/fixtures" not in worker
    assert "tests/fixtures" not in jobs
