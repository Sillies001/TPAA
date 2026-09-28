from __future__ import annotations

import json
from pathlib import Path

from tools.testing.m4_release_api_gui_storage_qualification import (
    PLATFORM_SCHEMA,
    PRE_TST005_TASKS,
    check_platform,
    compare_platform,
)


def _source(path: Path, task_ids: list[str], revision: str, logical: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": "SOURCE",
                "task_ids": task_ids,
                "status": "PASS",
                "implementation_complete": True,
                "task_complete": False,
                "source_revision": revision,
                "logical_product": logical,
                "acceptance": {"ok": True},
                "failed_acceptance": [],
                "scope": {
                    "shadow_schema_created": False,
                    "p4_p5_human_team_assessment_active": False,
                    "m5_formal_product_qualification_claimed": False,
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def test_m4_tst_005_platform_aggregation_and_compare(tmp_path: Path) -> None:
    revision = "a" * 40
    groups = {
        "m4-batch-1": (
            ["M4-GOV-001","M4-GOV-002","M4-LONG-001","M4-LONG-002","M4-LONG-003","M4-TST-001"],
            "longitudinal-sample.json",
            {"batch": 1},
        ),
        "m4-batch-2": (
            ["M4-LONG-004","M4-LONG-005","M4-OBS-001","M4-OBS-002","M4-OBS-003","M4-TST-002"],
            "trend-release.json",
            {"batch": 2},
        ),
        "m4-batch-3": (
            ["M4-API-001","M4-API-002","M4-GUI-001","M4-GUI-002","M4-GUI-003","M4-TST-003"],
            "api-gui-debrief.json",
            {"batch": 3},
        ),
        "m4-tst-004": (
            ["M4-TST-004"],
            "coverage.json",
            {
                "eligible": [{"metric_code": f"E{i:03d}"} for i in range(104)],
                "excluded": [{"metric_code": f"X{i:03d}"} for i in range(12)],
            },
        ),
    }
    for platform in ("windows","linux"):
        for directory,(tasks,filename,logical) in groups.items():
            _source(tmp_path/directory/platform/filename,tasks,revision,logical)
    windows = check_platform(evidence_root=tmp_path,platform="windows",expected_revision=revision)
    linux = check_platform(evidence_root=tmp_path,platform="linux",expected_revision=revision)
    assert windows["schema"] == PLATFORM_SCHEMA
    assert windows["status"] == "PASS"
    assert tuple(windows["logical_product"]["source_task_ids"]) == PRE_TST005_TASKS
    wp = tmp_path / "windows.json"
    lp = tmp_path / "linux.json"
    wp.write_text(json.dumps(windows),encoding="utf-8")
    lp.write_text(json.dumps(linux),encoding="utf-8")
    cross=compare_platform(wp,lp,expected_revision=revision)
    assert cross["status"] == "PASS"
    assert cross["failed_acceptance"] == []
