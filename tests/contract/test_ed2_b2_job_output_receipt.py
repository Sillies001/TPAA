from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_ed2_b2_production_jobs_publish_exact_output_receipts() -> None:
    jobs = (
        ROOT / "src" / "tpaa_runtime" / "durable_jobs.py"
    ).read_text(encoding="utf-8")
    receipt = (
        ROOT / "src" / "tpaa_runtime" / "production_job_output.py"
    ).read_text(encoding="utf-8")

    assert "ProductionJobOutputRepository" in jobs
    for command in (
        "P3_BUILD_COMMAND",
        "P4_ASSESSMENT_COMMAND",
        "P5_ASSESSMENT_COMMAND",
        "P6_BUILD_COMMAND",
        "P6_FORECAST_COMMAND",
        "P6_COUNTERFACTUAL_COMMAND",
    ):
        assert f"command={command}" in jobs

    assert '"ED2_PRODUCTION_JOB_OUTPUT"' in receipt
    assert '"registry.dataset_snapshot"' in receipt
    assert "production_job_output_snapshot_id" in receipt
    assert "CURRENT" not in receipt
    assert "LATEST" not in receipt
    assert "tests/fixtures" not in receipt
    assert "InMemory" not in receipt
