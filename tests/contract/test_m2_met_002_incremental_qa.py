from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "tools" / "dev" / "tpaa_dev.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DEV), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_m2_met_002_contract_is_formally_complete(tmp_path: Path) -> None:
    evidence_path = tmp_path / "qa.json"
    completed = _run(
        "m2-qa-foundation-incremental-check",
        "--evidence",
        str(evidence_path),
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema"] == "TPAA_M2_MET_002_INCREMENTAL_QA_EVIDENCE_V1"
    assert evidence["task_id"] == "M2-MET-002"
    assert evidence["tracking_issue"] == 97
    assert evidence["status"] == "PASS"
    assert evidence["implementation_complete"] is True
    assert evidence["task_complete"] is True
    assert evidence["formal_completion_blocked_by_authority"] is False
    assert evidence["authority_resolution_ready"] is True
    assert evidence["authority_gaps"] == {}
    assert evidence["dependency_effects"] == {}
    assert evidence["blocked_error_codes"] == {}
    assert evidence["failed_acceptance"] == []
    assert evidence["authority"]["baseline_change_issue"] == 106
    assert evidence["authority"]["authority_artifact_id"] == "M2_QA_SNS_AUTHORITY"
    assert evidence["acceptance"]["registry_uses_catalog_algorithm_identities_exact"]
    assert evidence["acceptance"]["full_qa_set_executes_through_general_engine"]
    product = evidence["logical_product"]
    assert product["dispatch_key"] == "algorithm_id+algorithm_version"
    assert len(product["engine_records"]) == 8
    assert all(
        record["algorithm_version"] and len(record["dependency_manifest_hash"]) == 64
        for record in product["engine_records"]
    )


def test_m2_met_002_cross_platform_compare_is_revision_exact(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    checked = _run(
        "m2-qa-foundation-incremental-check",
        "--evidence",
        str(source),
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    payload = json.loads(source.read_text(encoding="utf-8"))
    revision = payload["source_revision"]
    assert isinstance(revision, str)

    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    windows.write_text(json.dumps(payload), encoding="utf-8")
    linux.write_text(json.dumps(payload), encoding="utf-8")
    compared = tmp_path / "compare.json"
    result = _run(
        "m2-qa-foundation-incremental-compare",
        "--windows",
        str(windows),
        "--linux",
        str(linux),
        "--expected-revision",
        revision,
        "--evidence",
        str(compared),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    evidence = json.loads(compared.read_text(encoding="utf-8"))
    assert evidence["status"] == "PASS"
    assert evidence["implementation_complete"] is True
    assert evidence["task_complete"] is True
    assert evidence["formal_completion_blocked_by_authority"] is False
    assert evidence["authority_resolution_ready"] is True
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
