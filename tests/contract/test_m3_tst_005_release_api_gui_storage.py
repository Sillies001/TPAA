from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tools" / "testing" / "m3_release_api_gui_storage_qualification.py"

SOURCE_FILES = {
    "M3-TST-001": ("m3-tst-001", "catalog-coverage.json"),
    "M3-TST-002": ("m3-tst-002", "four-training-golden.json"),
    "M3-TST-003": ("m3-tst-003", "air-golden.json"),
    "M3-TST-004": ("m3-tst-004", "product-layer-golden.json"),
    "M3-OBS-001": ("m3-obs-001", "publication-routing.json"),
    "M3-OBS-002": ("m3-obs-002", "immutable-release.json"),
    "M3-OBS-003": ("m3-obs-003", "publication-replay.json"),
    "M3-API-001": ("m3-api-001", "release-query.json"),
    "M3-API-002": ("m3-api-002", "workspace.json"),
    "M3-GUI-001": ("m3-gui-001", "workspace-navigation.json"),
    "M3-GUI-002": ("m3-gui-002", "family-applicability.json"),
    "M3-GUI-003": ("m3-gui-003", "status-evidence-replay.json"),
}


def _revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECK), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _write_sources(root: Path, platform: str, revision: str) -> tuple[str, ...]:
    codes = tuple(f"P1-QA-{index:03d}" for index in range(1, 117))
    for task_id, (directory, filename) in SOURCE_FILES.items():
        logical: dict[str, object] = {"task": task_id}
        scope: dict[str, object] = {}
        if task_id == "M3-TST-001":
            logical = {"integrated_execution_codes": list(codes)}
        elif task_id == "M3-OBS-002":
            logical = {
                "definitions": [{"metric_code": code} for code in codes],
                "execution_records": [{"metric_code": code} for code in codes],
                "evidence_bindings": [{"metric_code": code} for code in codes],
            }
        elif task_id == "M3-API-001":
            logical = {"metric_codes": list(codes)}
            scope = {
                "metric_count": 116,
                "business_metric_recomputation_executed": False,
            }
        elif task_id == "M3-API-002":
            scope = {
                "metric_membership_per_workspace": 116,
                "business_metric_recomputation_executed": False,
            }
        elif task_id == "M3-OBS-003":
            scope = {
                "historical_reads_release_id_bound": True,
                "latest_authority_resolution_used": False,
            }
        elif task_id == "M3-GUI-001":
            scope = {
                "gui_rendering_executed": True,
                "database_access_executed_by_gui": False,
                "business_metric_recomputation_executed_by_gui": False,
            }
        elif task_id == "M3-GUI-002":
            scope = {
                "gui_rendering_executed": True,
                "database_access_executed_by_gui": False,
                "business_metric_recomputation_executed_by_gui": False,
            }
        elif task_id == "M3-GUI-003":
            scope = {
                "gui_rendering_executed": True,
                "historical_replay_explicit_release_id": True,
                "latest_authority_resolution_used": False,
                "database_access_executed_by_gui": False,
                "business_metric_recomputation_executed_by_gui": False,
            }
        payload = {
            "schema": f"TEST::{task_id}",
            "task_id": task_id,
            "status": "PASS",
            "task_complete": True,
            "implementation_complete": True,
            "source_revision": revision,
            "logical_product": logical,
            "acceptance": {"synthetic_contract_probe": True},
            "failed_acceptance": [],
            "scope": scope,
        }
        path = root / directory / platform / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    return codes


def test_m3_tst_005_platform_and_cross_contract(tmp_path: Path) -> None:
    revision = _revision()
    evidence_root = tmp_path / "evidence"
    codes = _write_sources(evidence_root, "windows", revision)
    _write_sources(evidence_root, "linux", revision)

    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    for platform, output in (("windows", windows), ("linux", linux)):
        result = _run(
            "check",
            "--evidence-root",
            str(evidence_root),
            "--platform",
            platform,
            "--expected-revision",
            revision,
            "--evidence",
            str(output),
        )
        assert result.returncode == 0, result.stdout + result.stderr

    cross = tmp_path / "cross.json"
    result = _run(
        "compare",
        "--windows",
        str(windows),
        "--linux",
        str(linux),
        "--expected-revision",
        revision,
        "--evidence",
        str(cross),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(cross.read_text(encoding="utf-8"))
    assert payload["status"] == "PASS"
    assert payload["task_complete"] is True
    assert payload["failed_acceptance"] == []
    assert tuple(payload["logical_product"]["metric_codes"]) == codes
    assert all(payload["checks"].values())


def test_m3_tst_005_final_qualification_contract(tmp_path: Path) -> None:
    revision = _revision()
    codes = [f"P1-QA-{index:03d}" for index in range(1, 117)]
    cross = {
        "schema": "TPAA_M3_TST_005_RELEASE_API_GUI_CROSS_PLATFORM_EVIDENCE_V1",
        "task_id": "M3-TST-005",
        "status": "PASS",
        "task_complete": True,
        "source_revision": revision,
        "logical_product": {"metric_codes": codes},
        "checks": {"failed_acceptance_empty": True},
        "failed_acceptance": [],
    }
    storage = {
        "schema": "TPAA_M3_TST_005_STORAGE_PARITY_EVIDENCE_V1",
        "task_id": "M3-TST-005",
        "status": "PASS",
        "task_complete": True,
        "source_revision": revision,
        "metric_codes": codes,
        "release_id": "release",
        "manifest_hash": "manifest",
        "sqlite_membership_hash": "a" * 64,
        "postgres_membership_hash": "a" * 64,
        "acceptance": {
            "sqlite_publish_idempotent": True,
            "postgres_publish_idempotent": True,
        },
        "failed_acceptance": [],
    }
    cross_path = tmp_path / "cross.json"
    storage_path = tmp_path / "storage.json"
    output = tmp_path / "qualification.json"
    cross_path.write_text(json.dumps(cross), encoding="utf-8")
    storage_path.write_text(json.dumps(storage), encoding="utf-8")

    result = _run(
        "qualify",
        "--cross-platform",
        str(cross_path),
        "--storage",
        str(storage_path),
        "--expected-revision",
        revision,
        "--evidence",
        str(output),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema"] == (
        "TPAA_M3_TST_005_RELEASE_API_GUI_STORAGE_QUALIFICATION_V1"
    )
    assert payload["status"] == "PASS"
    assert payload["task_complete"] is True
    assert payload["failed_acceptance"] == []
    assert all(payload["acceptance"].values())
