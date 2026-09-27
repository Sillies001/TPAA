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
        timeout=240,
    )


def test_m2_tst_002_qa_air_golden_negative_evidence(
    tmp_path: Path,
) -> None:
    source = tmp_path / "qa-air-golden-negative.json"
    checked = _run(
        "m2-qa-air-golden-check",
        "--evidence",
        str(source),
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr

    payload = json.loads(source.read_text(encoding="utf-8"))
    assert payload["schema"] == (
        "TPAA_M2_TST_002_QA_AIR_GOLDEN_NEGATIVE_EVIDENCE_V1"
    )
    assert payload["task_id"] == "M2-TST-002"
    assert payload["tracking_issue"] == 99
    assert payload["status"] == "PASS"
    assert payload["task_complete"] is True
    assert payload["implementation_complete"] is True
    assert payload["failed_acceptance"] == []
    assert all(payload["acceptance"].values())
    assert len(payload["logical_product"]["qa_metric_codes"]) == 8
    assert payload["logical_product"]["air_metric_codes"] == [
        "P1-AIR-001",
        "P1-AIR-002",
        "P1-AIR-003",
    ]
    assert payload["scope"]["business_metric_semantics_executed"] is True

    revision = payload["source_revision"]
    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    windows.write_text(json.dumps(payload), encoding="utf-8")
    linux.write_text(json.dumps(payload), encoding="utf-8")
    compared = tmp_path / "compared.json"
    result = _run(
        "m2-qa-air-golden-compare",
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
    assert evidence["schema"] == (
        "TPAA_M2_TST_002_QA_AIR_GOLDEN_NEGATIVE_"
        "CROSS_PLATFORM_EVIDENCE_V1"
    )
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is True
    assert evidence["implementation_complete"] is True
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
