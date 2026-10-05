from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_prcb_c2_production_jobs_commit_product_and_terminal_success_together() -> None:
    source = (ROOT / "src" / "tpaa_runtime" / "durable_jobs.py").read_text(
        encoding="utf-8"
    )
    assert source.count(").succeed(job_id)") >= 4
    assert "elif current.status is ComputeJobState.SUCCEEDED" in source
