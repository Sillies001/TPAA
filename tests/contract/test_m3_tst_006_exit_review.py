from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tools" / "testing" / "m3_exit_review.py"


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location("tpaa_m3_exit_review", CHECK)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _cold(platform: str, revision: str, *, postgres: bool) -> dict[str, object]:
    return {
        "schema": "TPAA_M0_COLD_START_V2",
        "task": "M0-DEV-006",
        "status": "PASS",
        "source_revision": revision,
        "platform": platform,
        "clean_clone": True,
        "uv_sync_locked": True,
        "m0_gates": "PASS",
        "postgres_bootstrap": "PASS" if postgres else "NOT_REQUESTED",
        "postgres_repository": "PASS" if postgres else "NOT_REQUESTED",
        "worktree_clean": True,
    }


def _fixture(tmp_path: Path, revision: str) -> dict[str, Path]:
    module = _load_module()
    logical = tmp_path / "logical"
    platform = tmp_path / "platform"
    codes = [f"P1-QA-{index:03d}" for index in range(1, 117)]

    for task_id, filename in module.TASK_EVIDENCE.items():
        logical_product: dict[str, object] = {"task": task_id}
        if task_id == "M3-MET-009":
            logical_product = {"metric_codes": codes}
        _write(
            logical / filename,
            {
                "schema": f"TEST::{task_id}",
                "task_id": task_id,
                "status": "PASS",
                "task_complete": True,
                "implementation_complete": True,
                "source_revision": revision,
                "logical_product": logical_product,
                "failed_acceptance": [],
            },
        )

    tst005 = tmp_path / "tst005.json"
    _write(
        tst005,
        {
            "schema": (
                "TPAA_M3_TST_005_RELEASE_API_GUI_STORAGE_QUALIFICATION_V1"
            ),
            "task_id": "M3-TST-005",
            "status": "PASS",
            "task_complete": True,
            "implementation_complete": True,
            "source_revision": revision,
            "logical_product": {"metric_codes": codes},
            "acceptance": {"synthetic_contract_probe": True},
            "failed_acceptance": [],
        },
    )
    _write(
        platform / "devops" / "windows" / "cold-start.json",
        _cold("windows", revision, postgres=False),
    )
    _write(
        platform / "devops" / "linux" / "cold-start.json",
        _cold("linux", revision, postgres=False),
    )
    postgres = tmp_path / "postgres-cold-start.json"
    _write(postgres, _cold("linux", revision, postgres=True))
    return {
        "logical": logical,
        "platform": platform,
        "tst005": tst005,
        "postgres": postgres,
    }


def test_m3_tst_006_candidate_is_pending_protected_main(tmp_path: Path) -> None:
    module = _load_module()
    revision = "1" * 40
    fixture = _fixture(tmp_path, revision)
    payload = module.review(
        logical_root=fixture["logical"],
        platform_artifact_root=fixture["platform"],
        tst005_path=fixture["tst005"],
        postgres_cold_start_path=fixture["postgres"],
        expected_revision=revision,
        event_name="pull_request",
        git_ref="refs/pull/119/merge",
    )
    assert payload["status"] == "PASS"
    assert payload["decision"] == "PENDING_PROTECTED_MAIN"
    assert payload["implementation_complete"] is True
    assert payload["task_complete"] is False
    assert payload["protected_main_exact"] is False
    assert payload["failed_acceptance"] == []
    assert payload["task_count"] == 28
    assert len(payload["task_acceptance"]) == 28
    assert all(payload["task_acceptance"].values())
    assert len(payload["metric_codes"]) == 116
    assert all(payload["acceptance"].values())


def test_m3_tst_006_protected_main_is_go(tmp_path: Path) -> None:
    module = _load_module()
    revision = "2" * 40
    fixture = _fixture(tmp_path, revision)
    payload = module.review(
        logical_root=fixture["logical"],
        platform_artifact_root=fixture["platform"],
        tst005_path=fixture["tst005"],
        postgres_cold_start_path=fixture["postgres"],
        expected_revision=revision,
        event_name="push",
        git_ref="refs/heads/main",
    )
    assert payload["status"] == "PASS"
    assert payload["decision"] == "GO"
    assert payload["implementation_complete"] is True
    assert payload["task_complete"] is True
    assert payload["protected_main_exact"] is True
    assert payload["formal_completion_blocked_by_protected_main"] is False
    assert payload["failed_acceptance"] == []
