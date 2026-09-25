from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "tools" / "dev" / "tpaa_dev.py"
POLICY = ROOT / "docs" / "planning" / "M1_M3_EXECUTION_BATCH_POLICY.json"


def test_execution_batch_policy_caps_m1_m2_m3_and_preserves_gate_order() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))

    assert policy["schema"] == "TPAA_M1_M3_EXECUTION_BATCH_POLICY_V1"
    assert policy["governance_issue"] == 85
    assert policy["max_open_execution_issues_per_milestone"] == 4
    assert policy["fine_issue_closure_semantics"] == "SUPERSEDED_NOT_COMPLETED"
    assert [batch["issue"] for batch in policy["m1"]["batches"]] == [86, 87, 89, 88]
    assert policy["m2"] == {
        "creation_gate": "M1_EXIT_GO",
        "max_open_execution_issues": 4,
        "import_fine_grained_open_issues_first": False,
    }
    assert policy["m3"]["max_open_execution_issues"] == 4
    assert policy["m3"]["import_fine_grained_open_issues_first"] is False


def test_batch_1_acceptance_command_emits_all_task_evidence(tmp_path: Path) -> None:
    evidence = tmp_path / "m1-batch-1-core.json"
    result = subprocess.run(
        [sys.executable, str(DEV), "m1-batch-1-core-check", "--evidence", str(evidence)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(evidence.read_text(encoding="utf-8"))

    assert payload["schema"] == "TPAA_M1_BATCH_1_CORE_EVIDENCE_V1"
    assert payload["batch_id"] == "M1-BATCH-1-CORE-PRODUCT"
    assert payload["tracking_issue"] == 86
    assert payload["status"] == "PASS"
    assert payload["fixture_count"] == 8
    assert len(payload["task_ids"]) == 14
    assert set(payload["task_ids"]) == {
        "M1-WORLD-004",
        "M1-WORLD-005",
        "M1-WORLD-006",
        "M1-WORLD-007",
        "M1-MET-001",
        "M1-MET-002",
        "M1-MET-003",
        "M1-MET-004",
        "M1-MET-005",
        "M1-MET-006",
        "M1-MET-007",
        "M1-MET-008",
        "M1-TST-002",
        "M1-TST-003",
    }
    assert payload["failed_acceptance"] == []
    assert payload["failures"] == []
    assert all(payload["acceptance"].values())
    assert len(payload["world_logical_hashes"]) == 8
    assert len(payload["metric_batch_hashes"]) == 8


def test_batch_1_compare_command_proves_exact_logical_equivalence(tmp_path: Path) -> None:
    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    comparison = tmp_path / "comparison.json"
    expected_revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()

    for evidence in (windows, linux):
        result = subprocess.run(
            [sys.executable, str(DEV), "m1-batch-1-core-check", "--evidence", str(evidence)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr

    result = subprocess.run(
        [
            sys.executable,
            str(DEV),
            "m1-batch-1-compare",
            "--windows",
            str(windows),
            "--linux",
            str(linux),
            "--expected-revision",
            expected_revision,
            "--evidence",
            str(comparison),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(comparison.read_text(encoding="utf-8"))
    assert payload == {
        "acceptance_equal": True,
        "batch_id": "M1-BATCH-1-CORE-PRODUCT",
        "exact_logical_equality": True,
        "metric_batch_hashes_equal": True,
        "schema": "TPAA_M1_BATCH_1_LOGICAL_EQUIVALENCE_V1",
        "source_revision": expected_revision,
        "source_revisions_exact": True,
        "status": "PASS",
        "world_hashes_equal": True,
    }
