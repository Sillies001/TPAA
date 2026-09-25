from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

from tpaa_world import (
    CORE_WORLD_MANIFEST_WRITABLE_FIELDS,
    CoreWorldManifest,
)

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


def test_world_001_manifest_shape_is_exact_core_1_6_0_authority() -> None:
    core = json.loads(
        (AUTHORITY / "CORE_LOGICAL_MODEL.json").read_text(encoding="utf-8")
    )
    policy = json.loads(
        (AUTHORITY / "WORLD_CAPABILITY_REGISTRY.json").read_text(encoding="utf-8")
    )
    authority_fields = tuple(
        item["name"]
        for item in core["tables"]["world.world_product_manifest"]["fields"]
        if item["name"] != "created_at"
    )

    assert core["db_schema_version"] == "1.6.0"
    assert authority_fields == CORE_WORLD_MANIFEST_WRITABLE_FIELDS
    assert tuple(item.name for item in fields(CoreWorldManifest)) == authority_fields
    assert policy["registry_id"] == "WORLD_CAPABILITY_REGISTRY"
    assert policy["version"] == "1.0.0"
    assert "W" in policy["worlds"]
    assert "M" in policy["worlds"]


def test_world_001_evidence_preserves_reference_time_authority(tmp_path: Path) -> None:
    evidence_path = tmp_path / "world.json"
    result = _run(
        "m2-reference-time-world-check",
        "--evidence",
        str(evidence_path),
    )
    assert result.returncode == 0, result.stdout + result.stderr

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema"] == "TPAA_M2_WORLD_001_REFERENCE_TIME_EVIDENCE_V1"
    assert evidence["task_id"] == "M2-WORLD-001"
    assert evidence["tracking_issue"] == 96
    assert evidence["status"] == "PASS"
    assert evidence["failed_acceptance"] == []
    assert all(evidence["acceptance"].values())

    product = evidence["logical_product"]
    assert product["reference_world"]["world_kind"] == "TRUTH"
    assert product["time_world"]["world_kind"] == "MACHINE"
    assert product["reference_world"]["world_version"] == "M2_REFERENCE_TRUTH_WORLD_V1"
    assert product["time_world"]["world_version"] == "M2_TIME_ALIGNMENT_WORLD_V1"
    assert len(product["reference_world"]["logical_content_hash"]) == 64
    assert len(product["time_world"]["logical_content_hash"]) == 64
    assert len(product["bundle_logical_hash"]) == 64


def test_world_001_cross_platform_compare_is_revision_exact(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    checked = _run(
        "m2-reference-time-world-check",
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
        "m2-reference-time-world-compare",
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
    assert evidence["schema"] == "TPAA_M2_WORLD_001_CROSS_PLATFORM_EVIDENCE_V1"
    assert evidence["task_id"] == "M2-WORLD-001"
    assert evidence["status"] == "PASS"
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
