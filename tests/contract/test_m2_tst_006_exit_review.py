from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.testing.m2_exit_review import TASK_EVIDENCE

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "tools" / "dev" / "tpaa_dev.py"
REVISION = "a" * 40


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DEV), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    evidence = tmp_path / "evidence"
    for task_id, pattern in TASK_EVIDENCE.items():
        for platform in ("windows", "linux"):
            path = evidence / pattern.format(platform=platform)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "schema": f"TEST::{task_id}",
                        "task_id": task_id,
                        "status": "PASS",
                        "task_complete": True,
                        "implementation_complete": True,
                        "source_revision": REVISION,
                        "failed_acceptance": [],
                    }
                ),
                encoding="utf-8",
            )

    for platform in ("windows", "linux"):
        sentinel = evidence / "m2-authority-gap" / platform / "sentinel.json"
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text(
            json.dumps(
                {
                    "schema": "TPAA_M2_BATCH_2_AUTHORITY_GAP_SENTINEL_V1",
                    "status": "PASS",
                    "source_revision": REVISION,
                    "authority_resolution_ready": True,
                    "task_complete": True,
                    "blocked_tasks": [],
                    "failed_acceptance": [],
                }
            ),
            encoding="utf-8",
        )
        cold = evidence / "devops" / platform / "cold-start.json"
        cold.parent.mkdir(parents=True, exist_ok=True)
        cold.write_text(
            json.dumps(
                {
                    "schema": "TPAA_M0_COLD_START_V2",
                    "status": "PASS",
                    "source_revision": REVISION,
                    "platform": platform,
                    "clean_clone": True,
                    "uv_sync_locked": True,
                    "m0_gates": "PASS",
                    "postgres_bootstrap": "NOT_REQUESTED",
                    "postgres_repository": "NOT_REQUESTED",
                    "worktree_clean": True,
                }
            ),
            encoding="utf-8",
        )

    tst005 = tmp_path / "tst005.json"
    tst005.write_text(
        json.dumps(
            {
                "schema": (
                    "TPAA_M2_TST_005_CROSS_PLATFORM_STORAGE_QUALIFICATION_V1"
                ),
                "task_id": "M2-TST-005",
                "status": "PASS",
                "task_complete": True,
                "implementation_complete": True,
                "source_revision": REVISION,
                "failed_acceptance": [],
                "scope": {"p1_remainder_84_executed": False},
            }
        ),
        encoding="utf-8",
    )
    postgres = tmp_path / "postgres-cold-start.json"
    postgres.write_text(
        json.dumps(
            {
                "schema": "TPAA_M0_COLD_START_V2",
                "status": "PASS",
                "source_revision": REVISION,
                "platform": "linux",
                "clean_clone": True,
                "uv_sync_locked": True,
                "m0_gates": "PASS",
                "postgres_bootstrap": "PASS",
                "postgres_repository": "PASS",
                "worktree_clean": True,
            }
        ),
        encoding="utf-8",
    )
    return evidence, tst005, postgres


def test_m2_tst_006_pr_candidate_is_complete_but_pending_protected_main(
    tmp_path: Path,
) -> None:
    evidence, tst005, postgres = _write_inputs(tmp_path)
    output = tmp_path / "review.json"
    result = _run(
        "m2-exit-review",
        "--artifact-root",
        str(evidence),
        "--tst005",
        str(tst005),
        "--postgres-cold-start",
        str(postgres),
        "--expected-revision",
        REVISION,
        "--event-name",
        "pull_request",
        "--git-ref",
        "refs/pull/109/merge",
        "--output",
        str(output),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema"] == "TPAA_M2_EXIT_REVIEW_V1"
    assert payload["task_id"] == "M2-TST-006"
    assert payload["task_count"] == 27
    assert len(payload["task_ids"]) == 27
    assert all(payload["task_acceptance"].values())
    assert payload["status"] == "PASS"
    assert payload["implementation_complete"] is True
    assert payload["task_complete"] is False
    assert payload["decision"] == "PENDING_PROTECTED_MAIN"
    assert payload["formal_completion_blocked_by_protected_main"] is True
    assert payload["failed_acceptance"] == []
    assert payload["unresolved_risks"] == []


def test_m2_tst_006_protected_main_exact_sha_issues_go(tmp_path: Path) -> None:
    evidence, tst005, postgres = _write_inputs(tmp_path)
    output = tmp_path / "review.json"
    result = _run(
        "m2-exit-review",
        "--artifact-root",
        str(evidence),
        "--tst005",
        str(tst005),
        "--postgres-cold-start",
        str(postgres),
        "--expected-revision",
        REVISION,
        "--event-name",
        "push",
        "--git-ref",
        "refs/heads/main",
        "--output",
        str(output),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "PASS"
    assert payload["decision"] == "GO"
    assert payload["task_complete"] is True
    assert payload["implementation_complete"] is True
    assert payload["protected_main_exact"] is True
    assert payload["formal_completion_blocked_by_protected_main"] is False
    assert payload["failed_acceptance"] == []
