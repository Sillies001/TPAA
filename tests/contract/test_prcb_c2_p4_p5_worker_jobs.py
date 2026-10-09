from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_prcb_c2_p4_p5_assessments_route_through_governed_workers() -> None:
    worker = (ROOT / "src" / "tpaa_runtime" / "production_worker.py").read_text(
        encoding="utf-8"
    )
    jobs = (ROOT / "src" / "tpaa_runtime" / "durable_jobs.py").read_text(
        encoding="utf-8"
    )
    downstream = (
        ROOT / "src" / "tpaa_runtime" / "production_downstream.py"
    ).read_text(encoding="utf-8")

    assert 'P4_ASSESSMENT_COMMAND = "P4_ASSESSMENT"' in worker
    assert 'P5_ASSESSMENT_COMMAND = "P5_ASSESSMENT"' in worker
    assert "materialize_p4_human_machine_evidence(" in worker
    assert "build_p4_assessment_revision(" in worker
    assert "annotations=()" in worker
    assert 'approval_state="DRAFT"' in worker
    assert "materialize_p5_team_mission_evidence(" in worker
    assert "build_p5_aggregation(evidence)" in worker
    assert "build_p5_assessment_revision(" in worker
    assert "supersedes=None" in worker

    assert "exact_p4_scope(" in jobs
    assert "snapshot_id" in jobs
    assert "exact_p5_selection(" in jobs
    assert "persist_p4_worker_product(" in jobs
    assert "persist_p5_worker_product(" in jobs
    assert "register_p4_revision(" in downstream
    assert "register_p5_revision(" in downstream
    assert jobs.count(").succeed(job_id)") >= 6
    assert "PRCB_C2_P4_HUMAN_INPUT_REQUIRES_MUTATION_WORKFLOW" in jobs
    assert "PRCB_C2_P4_AUTOMATION_AUTHORITY_VIOLATION" in jobs
    assert "PRCB_C2_P5_AUTOMATION_AUTHORITY_VIOLATION" in jobs

    assert "tests/fixtures" not in worker
    assert "tests/fixtures" not in jobs
    assert "InMemory" not in worker
    assert "InMemory" not in jobs
