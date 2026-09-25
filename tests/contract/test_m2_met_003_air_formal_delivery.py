from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "tools" / "dev" / "tpaa_dev.py"
AIR_CODES = ["P1-AIR-001", "P1-AIR-002", "P1-AIR-003"]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DEV), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_m2_met_003_requalifies_exact_air_delivery(tmp_path: Path) -> None:
    evidence_path = tmp_path / "air.json"
    completed = _run(
        "m2-air-formal-delivery-check",
        "--evidence",
        str(evidence_path),
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema"] == "TPAA_M2_MET_003_AIR_FORMAL_DELIVERY_EVIDENCE_V1"
    assert evidence["task_id"] == "M2-MET-003"
    assert evidence["tracking_issue"] == 97
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is True
    assert evidence["failed_acceptance"] == []
    assert all(evidence["acceptance"].values())

    product = evidence["logical_product"]
    assert product["delivery_membership"] == AIR_CODES
    assert product["implementation_reuse"] == ("tpaa_metric.engine.compute_representative_metrics")
    assert [record["metric_code"] for record in product["engine_records"]] == AIR_CODES
    assert len(product["release_membership"]["definition_hashes"]) == 3
    assert len(product["release_membership"]["metric_instance_hashes"]) == 3
    assert len(product["release_membership"]["observation_ids"]) == 3
    assert set(product["catalog_definition_hashes"]) == set(AIR_CODES)
    assert all(len(value) == 64 for value in product["catalog_definition_hashes"].values())
    assert product["release_replay"]["exact_logical_products_equal"] is True


def test_m2_met_003_cross_platform_compare_is_revision_exact(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    checked = _run(
        "m2-air-formal-delivery-check",
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
    compared = tmp_path / "compared.json"

    completed = _run(
        "m2-air-formal-delivery-compare",
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
    assert evidence["schema"] == "TPAA_M2_MET_003_AIR_CROSS_PLATFORM_EVIDENCE_V1"
    assert evidence["task_id"] == "M2-MET-003"
    assert evidence["tracking_issue"] == 97
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is True
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
