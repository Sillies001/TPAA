from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDIB_DIR = ROOT / "docs" / "baseline" / "SDIB-1.3"
SDIB = SDIB_DIR / "TPAA_软件开发实施基线_SDIB-1.3.md"
M4_TASKS = SDIB_DIR / "M4_TASK_BASELINE.json"
SOURCE_HASHES = SDIB_DIR / "SDIB-1.3_SOURCE_BASELINE.sha256"
CATALOG = ROOT / "baseline" / "CB-1.4.0" / "canonical" / "P1_METRIC_CATALOG.json"
MILESTONES = ROOT / "baseline" / "CB-1.4.0" / "canonical" / "DEVELOPMENT_MILESTONE_REGISTRY.json"
CORE = ROOT / "baseline" / "CB-1.4.0" / "canonical" / "CORE_LOGICAL_MODEL.json"

EXPECTED_WORKSTREAMS = {"WS-LONGITUDINAL","WS-OBSERVATION","WS-GUI","WS-API","WS-TEST","WS-GOVERNANCE"}
EXPECTED_CORE_TABLES = {"registry.longitudinal_scope","registry.analysis_release","registry.release_scope_pointer","registry.longitudinal_release_input","metric.longitudinal_sample","metric.performance_trend_series","metric.performance_trend_point","metric.trend_bridge","metric.trend_input_bridge","debrief.annotation"}

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _source_hashes() -> dict[str, str]:
    result: dict[str, str] = {}
    for line in SOURCE_HASHES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, filename = line.split(maxsplit=1)
            result[filename] = digest
    return result

def test_sdib_1_3_version_scope_and_source_hashes() -> None:
    text = SDIB.read_text(encoding="utf-8")
    hashes = _source_hashes()
    assert text.startswith("# 飞机机载数据评估系统软件开发实施基线 SDIB-1.3\n")
    assert "**Software Development Implementation Baseline — SDIB-1.3**" in text
    assert "M4 P1 Longitudinal & Debrief Closure 为本版新增任务级详细基线" in text
    assert "M5～M9 保持后续 Epic/Entry-Gate 级路线基线" in text
    assert hashes[SDIB.name] == _sha256(SDIB)
    assert hashes[M4_TASKS.name] == _sha256(M4_TASKS)

def test_m4_task_manifest_is_exact_and_batched_once() -> None:
    payload = json.loads(M4_TASKS.read_text(encoding="utf-8"))
    ids = [task["task_id"] for task in payload["tasks"]]
    assert payload["schema"] == "TPAA_SDIB_M4_TASK_BASELINE_V1"
    assert payload["sdib_version"] == "SDIB-1.3"
    assert payload["milestone"] == "M4"
    assert payload["task_count"] == len(ids) == len(set(ids)) == 21
    assert {task["workstream"] for task in payload["tasks"]} == EXPECTED_WORKSTREAMS
    assert [b["batch_id"] for b in payload["batches"]] == ["M4-BATCH-1","M4-BATCH-2","M4-BATCH-3","M4-BATCH-4"]
    batched = [i for b in payload["batches"] for i in b["task_ids"]]
    assert len(batched) == len(set(batched)) == 21
    assert set(batched) == set(ids)

def test_m4_catalog_longitudinal_membership_is_exact_104_12() -> None:
    payload = json.loads(M4_TASKS.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    eligible = [m for m in catalog["metrics"] if m["p1_longitudinal_trend_eligibility"] is True]
    excluded = [m for m in catalog["metrics"] if m["p1_longitudinal_trend_eligibility"] is not True]
    frozen = payload["longitudinal_eligibility"]
    assert len(catalog["metrics"]) == 116
    assert len(eligible) == frozen["eligible_count"] == 104
    assert len(excluded) == frozen["excluded_count"] == 12
    assert frozen["eligible_metric_codes"] == [m["metric_code"] for m in eligible]
    assert all(m["value_kind"] == "NUMERIC" and m["default_aggregation"] == "MEDIAN" for m in eligible)
    assert [x["metric_code"] for x in frozen["excluded_metrics"]] == [m["metric_code"] for m in excluded]
    assert all(m["default_aggregation"] == "NONE" for m in excluded)

def test_m4_manifest_matches_milestone_core_and_capability_boundary() -> None:
    payload = json.loads(M4_TASKS.read_text(encoding="utf-8"))
    milestones = json.loads(MILESTONES.read_text(encoding="utf-8"))
    core = json.loads(CORE.read_text(encoding="utf-8"))
    m4 = next(x for x in milestones["milestones"] if x["code"] == "M4")
    assert m4["name"] == "P1 Longitudinal & Debrief Closure"
    assert set(m4["required_workstreams"]) == set(payload["required_workstreams"]) == EXPECTED_WORKSTREAMS
    assert payload["entry_evidence"]["protected_main_run_number"] == 414
    assert payload["entry_evidence"]["protected_main_sha"] == "53c591adbab1dea0618d0d3a727b0bf4638e00de"
    assert payload["entry_evidence"]["exit_decision"] == "GO"
    assert payload["capability_boundary"]["admitted_phases"] == ["P1"]
    assert payload["capability_boundary"]["p4_human_assessment_active"] is False
    assert payload["capability_boundary"]["m5_product_qualification_active"] is False
    assert set(payload["core_storage_authority"]["tables"]) == EXPECTED_CORE_TABLES
    assert EXPECTED_CORE_TABLES <= set(core["tables"])
    assert payload["core_storage_authority"]["db_schema_version"] == "1.6.0"
    assert payload["core_storage_authority"]["shadow_schema_permitted"] is False

def test_m4_authority_gap_is_explicit_fail_closed() -> None:
    payload = json.loads(M4_TASKS.read_text(encoding="utf-8"))
    blocker = payload["authority_blockers"]
    tasks = {x["task_id"]: x for x in payload["tasks"]}
    assert blocker["c3_issue"] == 122
    assert blocker["fail_closed"] is True
    assert blocker["blocker_task_id"] == "M4-GOV-001"
    assert "C3 issue #122" in tasks["M4-GOV-001"]["dependencies"]
    assert payload["authority_boundaries"]["historical_current_latest_fallback_forbidden"] is True
    assert payload["authority_boundaries"]["gui_persistence_access_forbidden"] is True
    assert payload["authority_boundaries"]["api_gui_business_recomputation_forbidden"] is True
    assert payload["authority_boundaries"]["p4_assessment_forbidden"] is True

def test_markdown_task_table_matches_machine_manifest() -> None:
    text = SDIB.read_text(encoding="utf-8")
    payload = json.loads(M4_TASKS.read_text(encoding="utf-8"))
    table_ids = re.findall(r"^\| (M4-[A-Z]+-\d{3}) \|", text, flags=re.MULTILINE)
    manifest_ids = [x["task_id"] for x in payload["tasks"]]
    assert table_ids == manifest_ids
    assert len(table_ids) == 21
    assert "M4 Batch 1 — Authority closure + longitudinal sample substrate" in text
    assert "M4 Batch 4 — Coverage / parity / cold-start / Exit" in text
    assert "只有 M4 Exit GO 后，才允许细化并进入 M5 product qualification backlog。" in text
    assert re.findall(r"\bM5-[A-Z]+-\d{3}\b", text) == []
