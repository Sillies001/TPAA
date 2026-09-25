from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "tools" / "dev" / "tpaa_dev.py"
SNS_CODES = ["P1-SNS-001", "P1-SNS-002", "P1-SNS-003", "P1-SNS-004"]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DEV), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_m2_met_004_exact_sns_detection_evidence(tmp_path: Path) -> None:
    path = tmp_path / "sns.json"
    completed = _run("m2-sns-detection-check", "--evidence", str(path))
    assert completed.returncode == 0, completed.stdout + completed.stderr
    evidence = json.loads(path.read_text(encoding="utf-8"))
    assert evidence["schema"] == "TPAA_M2_MET_004_SNS_DETECTION_EVIDENCE_V1"
    assert evidence["task_id"] == "M2-MET-004"
    assert evidence["tracking_issue"] == 97
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is True
    assert evidence["failed_acceptance"] == []
    assert all(evidence["acceptance"].values())
    product = evidence["logical_product"]
    assert product["delivery_membership"] == SNS_CODES
    assert product["dependency_closure"] == ["P1-QA-005", *SNS_CODES]
    assert set(product["definition_hashes"]) == set(SNS_CODES)
    assert all(output["instances"] == [] for output in product["non_radar"].values())


def test_m2_met_004_cross_platform_compare_is_revision_exact(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    checked = _run("m2-sns-detection-check", "--evidence", str(source))
    assert checked.returncode == 0, checked.stdout + checked.stderr
    payload = json.loads(source.read_text(encoding="utf-8"))
    revision = payload["source_revision"]
    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    windows.write_text(json.dumps(payload), encoding="utf-8")
    linux.write_text(json.dumps(payload), encoding="utf-8")
    compared = tmp_path / "compared.json"
    completed = _run(
        "m2-sns-detection-compare",
        "--windows",
        str(windows),
        "--linux",
        str(linux),
        "--expected-revision",
        revision,
        "--evidence",
        str(compared),
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    evidence = json.loads(compared.read_text(encoding="utf-8"))
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is True
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
