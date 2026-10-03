from __future__ import annotations

import json
import re
from pathlib import Path

from tools.testing.acp_219_authority_adoption import review

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "cross-platform-ci.yml"


def _postgres_evidence(path: Path, revision: str) -> Path:
    payload = {
        "schema": "TPAA_ACP219_POSTGRES_MIGRATION_V1",
        "proposal_id": "ACP-219",
        "source_revision": revision,
        "status": "PASS",
        "source_db_schema_version": "1.7.0",
        "target_db_schema_version": "1.8.0",
        "acceptance": {
            "historical_1_7_bootstrap_verified": True,
            "upgrade_to_1_8_verified": True,
            "historical_row_exact_after_upgrade": True,
            "ordered_text_probe_exact": True,
            "nonempty_downgrade_fail_closed": True,
            "failed_downgrade_preserves_1_8": True,
            "empty_downgrade_to_1_7_verified": True,
            "forward_reupgrade_to_1_8": True,
            "historical_row_exact_after_reupgrade": True,
        },
        "failed_acceptance": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_acp_219_candidate_passes_but_cannot_self_adopt(tmp_path: Path) -> None:
    revision = "candidate-revision"
    result = review(
        postgres_migration=_postgres_evidence(tmp_path / "pg.json", revision),
        expected_revision=revision,
        checked_out_revision=revision,
        event_name="pull_request",
        git_ref="refs/pull/999/merge",
        run_conclusion="success",
        required_jobs_success=14,
        required_jobs_total=14,
    )
    assert result["status"] == "PASS"
    assert result["decision"] == "PENDING_PROTECTED_MAIN"
    assert result["qualification"] == "ACP219_DB_1_8_0_CANDIDATE"
    assert result["formal_adopted"] is False
    assert result["failed_acceptance"] == []


def test_acp_219_only_exact_protected_main_can_formally_adopt(tmp_path: Path) -> None:
    revision = "protected-main-revision"
    result = review(
        postgres_migration=_postgres_evidence(tmp_path / "pg.json", revision),
        expected_revision=revision,
        checked_out_revision=revision,
        event_name="push",
        git_ref="refs/heads/main",
        run_conclusion="success",
        required_jobs_success=14,
        required_jobs_total=14,
    )
    assert result["status"] == "PASS"
    assert result["decision"] == "GO"
    assert result["qualification"] == "ACP219_DB_1_8_0_ADOPTED"
    assert result["formal_adopted"] is True


def test_acp_219_fails_non_exact_ci_or_postgres_evidence(tmp_path: Path) -> None:
    result = review(
        postgres_migration=_postgres_evidence(tmp_path / "pg.json", "wrong"),
        expected_revision="candidate",
        checked_out_revision="candidate",
        event_name="pull_request",
        git_ref="refs/pull/999/merge",
        run_conclusion="success",
        required_jobs_success=13,
        required_jobs_total=14,
    )
    assert result["status"] == "FAIL"
    assert "exact_revision" in result["failed_acceptance"]
    assert "hosted_ci_exact_14" in result["failed_acceptance"]


def test_acp_219_workflow_preserves_exact_fourteen_jobs_and_gate_steps() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    jobs = re.findall(r"(?m)^  ([a-z0-9-]+):\n", workflow)
    assert len(jobs) == 14
    assert len(set(jobs)) == 14
    assert "Execute ACP-219 PostgreSQL 1.7.0 to 1.8.0 migration qualification" in workflow
    assert "Review ACP-219 DB 1.8.0 authority adoption gate" in workflow
    assert "downloaded/postgres/acp219-postgres-migration.json" in workflow
    assert "--required-jobs-success 14" in workflow
    assert "--required-jobs-total 14" in workflow
