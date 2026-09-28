from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDIB_DIR = ROOT / "docs" / "baseline" / "SDIB-1.4"
SDIB = SDIB_DIR / "TPAA_软件开发实施基线_SDIB-1.4.md"
M5_TASKS = SDIB_DIR / "M5_TASK_BASELINE.json"
SOURCE_HASHES = SDIB_DIR / "SDIB-1.4_SOURCE_BASELINE.sha256"
MILESTONES = ROOT / "baseline" / "CB-1.4.0" / "canonical" / "DEVELOPMENT_MILESTONE_REGISTRY.json"
PLATFORM = ROOT / "baseline" / "CB-1.4.0" / "canonical" / "PLATFORM_COMPATIBILITY_REGISTRY.json"

EXPECTED_WORKSTREAMS = {
    "WS-PLATFORM",
    "WS-PERFORMANCE",
    "WS-SECURITY",
    "WS-DEVOPS",
    "WS-TEST",
    "WS-GOVERNANCE",
}
EXPECTED_PROFILES = [
    "WINDOWS_DESKTOP_X64",
    "LINUX_DESKTOP_X64",
    "WINDOWS_SERVICE_X64",
    "LINUX_SERVICE_X64",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_hashes() -> dict[str, str]:
    result: dict[str, str] = {}
    for line in SOURCE_HASHES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, filename = line.split(maxsplit=1)
            result[filename] = digest
    return result


def test_sdib_1_4_version_scope_and_source_hashes() -> None:
    text = SDIB.read_text(encoding="utf-8")
    hashes = _source_hashes()
    assert text.startswith(
        "# 飞机机载数据评估系统软件开发实施基线 SDIB-1.4\n"
    )
    assert (
        "**Software Development Implementation Baseline — SDIB-1.4**"
        in text
    )
    assert (
        "M5 P1 Product Qualification & Release 为本版新增任务级详细基线"
        in text
    )
    assert "M6～M9 保持后续 Epic/Entry-Gate 级路线基线" in text
    assert hashes[SDIB.name] == _sha256(SDIB)
    assert hashes[M5_TASKS.name] == _sha256(M5_TASKS)


def test_m5_task_manifest_is_exact_and_batched_once() -> None:
    payload = json.loads(M5_TASKS.read_text(encoding="utf-8"))
    ids = [task["task_id"] for task in payload["tasks"]]
    assert payload["schema"] == "TPAA_SDIB_M5_TASK_BASELINE_V1"
    assert payload["sdib_version"] == "SDIB-1.4"
    assert payload["milestone"] == "M5"
    assert payload["task_count"] == len(ids) == len(set(ids)) == 23
    assert {
        task["workstream"] for task in payload["tasks"]
    } == EXPECTED_WORKSTREAMS
    assert [b["batch_id"] for b in payload["batches"]] == [
        "M5-BATCH-1",
        "M5-BATCH-2",
        "M5-BATCH-3",
        "M5-BATCH-4",
    ]
    batched = [i for b in payload["batches"] for i in b["task_ids"]]
    assert len(batched) == len(set(batched)) == 23
    assert set(batched) == set(ids)


def test_m5_manifest_matches_milestone_and_exact_four_profiles() -> None:
    payload = json.loads(M5_TASKS.read_text(encoding="utf-8"))
    milestones = json.loads(MILESTONES.read_text(encoding="utf-8"))
    platform = json.loads(PLATFORM.read_text(encoding="utf-8"))
    m5 = next(x for x in milestones["milestones"] if x["code"] == "M5")
    assert m5["name"] == "P1 Product Qualification & Release"
    assert (
        set(m5["required_workstreams"])
        == set(payload["required_workstreams"])
        == EXPECTED_WORKSTREAMS
    )
    profiles = platform["certification_profiles"]
    required = [key for key, value in profiles.items() if value["required"]]
    assert required == EXPECTED_PROFILES
    frozen = payload["certification_profiles"]
    assert frozen["authority"] == "PLATFORM_COMPATIBILITY_REGISTRY.json"
    assert frozen["required_profile_count"] == 4
    assert frozen["required_profile_ids"] == EXPECTED_PROFILES
    assert frozen["additional_implicit_profiles_forbidden"] is True


def test_m5_entry_evidence_and_capability_boundary_are_exact() -> None:
    payload = json.loads(M5_TASKS.read_text(encoding="utf-8"))
    entry = payload["entry_evidence"]
    assert entry["predecessor_milestone"] == "M4"
    assert (
        entry["protected_main_sha"]
        == "de42de880e25102b9dfb5b06ffff18a37ca1fdc1"
    )
    assert entry["protected_main_run_number"] == 435
    assert entry["protected_main_actions_run_id"] == 36430788368
    assert entry["exit_review_schema"] == "TPAA_M4_EXIT_REVIEW_V1"
    assert entry["exit_decision"] == "GO"
    assert entry["protected_main_exact"] is True
    assert entry["task_complete"] is True
    assert entry["implementation_complete"] is True
    assert entry["failed_acceptance"] == []
    boundary = payload["capability_boundary"]
    assert boundary["admitted_phases"] == ["P1"]
    assert boundary["explicitly_not_admitted"] == [
        "P2",
        "P3",
        "P4",
        "P5",
        "P6",
    ]
    assert boundary["m5_formal_product_qualification_target"] is True
    assert (
        boundary["formal_qualification_claim_before_m5_exit_forbidden"]
        is True
    )


def test_m5_authority_gap_is_explicit_fail_closed() -> None:
    payload = json.loads(M5_TASKS.read_text(encoding="utf-8"))
    blocker = payload["authority_blockers"]
    tasks = {x["task_id"]: x for x in payload["tasks"]}
    assert blocker["c3_issue"] == 136
    assert blocker["fail_closed"] is True
    assert blocker["blocker_task_id"] == "M5-GOV-001"
    assert "C3 issue #136" in tasks["M5-GOV-001"]["dependencies"]
    assert "M5-PERF-001" in blocker["dependent_task_ids"]
    assert "M5-SEC-001" in blocker["dependent_task_ids"]
    assert "M5-DEV-003" in blocker["dependent_task_ids"]
    authority = payload["authority_boundaries"]
    assert (
        authority["implementation_selected_performance_thresholds_forbidden"]
        is True
    )
    assert (
        authority["implementation_selected_security_waivers_forbidden"]
        is True
    )
    assert (
        authority["implementation_selected_release_acceptance_forbidden"]
        is True
    )
    assert authority["db_shadow_schema_forbidden"] is True


def test_markdown_task_table_matches_machine_manifest() -> None:
    text = SDIB.read_text(encoding="utf-8")
    payload = json.loads(M5_TASKS.read_text(encoding="utf-8"))
    table_ids = re.findall(
        r"^\| (M5-[A-Z]+-\d{3}) \|",
        text,
        flags=re.MULTILINE,
    )
    manifest_ids = [x["task_id"] for x in payload["tasks"]]
    assert table_ids == manifest_ids
    assert len(table_ids) == 23
    assert (
        "M5 Batch 1 — Qualification authority + profile substrate"
        in text
    )
    assert (
        "M5 Batch 4 — Same-candidate parity / cold-start / Exit"
        in text
    )
    assert (
        "只有 M5 Exit GO 后，才允许把 candidate artifact 声称为正式 P1 "
        "M5-qualified release"
        in text
    )
    assert re.findall(r"\bM6-[A-Z]+-\d{3}\b", text) == []
