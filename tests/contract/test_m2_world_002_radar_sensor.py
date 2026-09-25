from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
DEV = ROOT / "tools" / "dev" / "tpaa_dev.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DEV), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_world_002_authority_is_radar_only_and_m2_foundation_exact() -> None:
    catalog = json.loads(
        (AUTHORITY / "P1_METRIC_CATALOG.json").read_text(encoding="utf-8")
    )
    matrix = json.loads(
        (AUTHORITY / "METRIC_INPUT_AUTHORITY_MATRIX.json").read_text(
            encoding="utf-8"
        )
    )

    contract = catalog["family_applicability_contracts"]["P1-SNS-*"]
    assert contract["subject_type"] == "MISSION_SYSTEM_INSTANCE"
    assert contract["applicability_mode"] == "SYSTEM_TYPE_EXACT"
    assert contract["allowed_system_types"] == ["RADAR"]

    sns = [
        metric
        for metric in catalog["metrics"]
        if metric["metric_code"].startswith("P1-SNS-")
    ]
    assert [metric["metric_code"] for metric in sns] == [
        f"P1-SNS-{index:03d}" for index in range(1, 22)
    ]
    assert all(metric["delivery_milestone"] == "M2" for metric in sns)
    assert all(metric["delivery_batch"] == "P1_FOUNDATION_32" for metric in sns)

    bindings = [
        binding
        for binding in matrix["bindings"]
        if binding["metric_code"].startswith("P1-SNS-")
    ]
    authorities = {binding["authority_id"] for binding in bindings}
    assert "CANONICAL_MISSION_SYSTEM_MEASUREMENT_V1" in authorities
    assert "CONTRACT_REFERENCE_RELATIVE_STATE_V1" in authorities
    assert "CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1" in authorities
    assert "CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1" in authorities
    assert "CONTRACT_DETECTION_CONFIRMATION_EVENT_V1" in authorities


def test_world_002_evidence_preserves_radar_subject_and_quality(tmp_path: Path) -> None:
    evidence_path = tmp_path / "world.json"
    result = _run(
        "m2-radar-sensor-world-check",
        "--evidence",
        str(evidence_path),
    )
    assert result.returncode == 0, result.stdout + result.stderr

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema"] == "TPAA_M2_WORLD_002_RADAR_SENSOR_EVIDENCE_V1"
    assert evidence["task_id"] == "M2-WORLD-002"
    assert evidence["tracking_issue"] == 96
    assert evidence["status"] == "PASS"
    assert evidence["failed_acceptance"] == []
    assert all(evidence["acceptance"].values())
    assert evidence["non_radar_error_code"] == "M2_MISSION_SYSTEM_NOT_APPLICABLE"

    product = evidence["logical_product"]
    assert product["world_kind"] == "MACHINE"
    assert product["world_version"] == "M2_RADAR_SENSOR_WORLD_V1"
    assert product["subject"]["subject_type"] == "MISSION_SYSTEM_INSTANCE"
    assert product["subject"]["system_type"] == "RADAR"
    assert product["applicability"] == {
        "mode": "SYSTEM_TYPE_EXACT",
        "allowed_system_types": ["RADAR"],
    }
    assert product["alignment"]["row_count"] > 0
    assert len(product["logical_content_hash"]) == 64
    assert len(product["bundle_logical_hash"]) == 64


def test_world_002_cross_platform_compare_is_revision_exact(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    checked = _run(
        "m2-radar-sensor-world-check",
        "--evidence",
        str(source),
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    payload = json.loads(source.read_text(encoding="utf-8"))
    revision = payload["source_revision"]

    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    windows.write_text(json.dumps(payload), encoding="utf-8")
    linux.write_text(json.dumps(payload), encoding="utf-8")
    compared = tmp_path / "compared.json"

    result = _run(
        "m2-radar-sensor-world-compare",
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
    assert evidence["schema"] == "TPAA_M2_WORLD_002_CROSS_PLATFORM_EVIDENCE_V1"
    assert evidence["task_id"] == "M2-WORLD-002"
    assert evidence["status"] == "PASS"
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
