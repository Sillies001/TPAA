from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDIB_DIR = ROOT / "docs" / "baseline" / "SDIB-1.5"
SDIB = SDIB_DIR / "TPAA_软件开发实施基线_SDIB-1.5.md"
M6_TASKS = SDIB_DIR / "M6_TASK_BASELINE.json"
SOURCE_HASHES = SDIB_DIR / "SDIB-1.5_SOURCE_BASELINE.sha256"
MILESTONES = ROOT / "baseline" / "CB-1.4.0" / "canonical" / "DEVELOPMENT_MILESTONE_REGISTRY.json"
CAPABILITY = ROOT / "baseline" / "CB-1.4.0" / "canonical" / "CAPABILITY_PHASE_REGISTRY.json"
EXTENSION = ROOT / "baseline" / "CB-1.4.0" / "canonical" / "EXTENSION_CONTRACT_REGISTRY.json"
CORE = ROOT / "migrations" / "authority" / "CORE_LOGICAL_MODEL_DB_1_6_0.json"

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_hashes() -> dict[str, str]:
    result: dict[str, str] = {}
    for line in SOURCE_HASHES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, filename = line.split(maxsplit=1)
            result[filename] = digest
    return result


EXPECTED_WORKSTREAMS = {
    "WS-CAPABILITY",
    "WS-DATA",
    "WS-TEST",
    "WS-GUI",
    "WS-GOVERNANCE",
}


def test_sdib_1_5_version_and_scope() -> None:
    text = SDIB.read_text(encoding="utf-8")
    assert text.startswith("# 飞机机载数据评估系统软件开发实施基线 SDIB-1.5\n")
    assert "**Software Development Implementation Baseline — SDIB-1.5**" in text
    assert "M6 — P2 Attribution Activation" in text
    assert "one-milestone-ahead rolling design" in text
    hashes = _source_hashes()
    assert hashes[SDIB.name] == _sha256(SDIB)
    assert hashes[M6_TASKS.name] == _sha256(M6_TASKS)


def test_m6_task_manifest_is_exact_and_batched_once() -> None:
    payload = json.loads(M6_TASKS.read_text(encoding="utf-8"))
    ids = [task["task_id"] for task in payload["tasks"]]
    assert payload["schema"] == "TPAA_SDIB_M6_TASK_BASELINE_V1"
    assert payload["sdib_version"] == "SDIB-1.5"
    assert payload["milestone"] == "M6"
    assert payload["task_count"] == len(ids) == len(set(ids)) == 17
    assert {task["workstream"] for task in payload["tasks"]} == EXPECTED_WORKSTREAMS
    assert [b["batch_id"] for b in payload["batches"]] == [
        "M6-BATCH-1",
        "M6-BATCH-2",
        "M6-BATCH-3",
        "M6-BATCH-4",
    ]
    batched = [item for batch in payload["batches"] for item in batch["task_ids"]]
    assert len(batched) == len(set(batched)) == 17
    assert set(batched) == set(ids)


def test_m6_matches_frozen_milestone_and_capability_contracts() -> None:
    payload = json.loads(M6_TASKS.read_text(encoding="utf-8"))
    milestones = json.loads(MILESTONES.read_text(encoding="utf-8"))
    capability = json.loads(CAPABILITY.read_text(encoding="utf-8"))
    extension = json.loads(EXTENSION.read_text(encoding="utf-8"))
    m6 = next(row for row in milestones["milestones"] if row["code"] == "M6")
    p2 = next(row for row in capability["capability_phases"] if row["p_code"] == "P2")
    assert m6["name"] == "P2 Attribution Activation"
    assert set(m6["required_workstreams"]) == EXPECTED_WORKSTREAMS
    assert set(payload["required_workstreams"]) == EXPECTED_WORKSTREAMS
    assert p2["name"] == "Context Attribution & Normalization"
    rules = extension["p_capability_contracts"]["P2"]["rules"]
    assert "NOT_IDENTIFIABLE is a valid result." in rules
    assert "No adjusted value overwrites P1 observed value." in rules
    assert "Future information and same-episode leakage are prohibited." in rules


def test_m6_core_products_and_schema_are_existing_authority() -> None:
    payload = json.loads(M6_TASKS.read_text(encoding="utf-8"))
    core = json.loads(CORE.read_text(encoding="utf-8"))
    for table in (
        "assessment.factor_feature_set",
        "assessment.attribution_run",
        "capability.adjusted_capability_estimate",
    ):
        assert table in core["tables"]
        assert core["tables"][table]["schema_version"] == "1.6.0"
        assert all(field.get("name") for field in core["tables"][table]["fields"])
    storage = payload["core_storage_authority"]
    assert storage["db_schema_version"] == "1.6.0"
    assert storage["shadow_schema_permitted"] is False


def test_m6_entry_boundary_blocker_and_rolling_design_are_fail_closed() -> None:
    payload = json.loads(M6_TASKS.read_text(encoding="utf-8"))
    entry = payload["entry_evidence"]
    assert entry["protected_main_sha"] == "aae1e692774f7c10114d66fd79acb254c2aabfef"
    assert entry["protected_main_run_number"] == 472
    assert entry["protected_main_actions_run_id"] == 36556569965
    assert entry["hosted_ci_required_jobs"] == 14
    assert entry["hosted_ci_result"] == "PASS"
    boundary = payload["capability_boundary"]
    assert boundary["currently_admitted_phases"] == ["P1"]
    assert boundary["candidate_phase"] == "P2"
    assert boundary["explicitly_not_admitted"] == ["P3", "P4", "P5", "P6"]
    assert boundary["p2_claim_before_m6_exit_forbidden"] is True
    blocker = payload["authority_blockers"]
    assert blocker["c3_issue"] == 151
    assert blocker["fail_closed"] is True
    rolling = payload["rolling_design"]
    assert rolling["policy_issue"] == 149
    assert rolling["next_detailed_design_milestone"] == "M7"
    assert rolling["m7_implementation_forbidden_before_m6_exit_go"] is True


def test_m6_markdown_task_table_matches_machine_manifest() -> None:
    text = SDIB.read_text(encoding="utf-8")
    payload = json.loads(M6_TASKS.read_text(encoding="utf-8"))
    table_ids = re.findall(r"^\| (M6-[A-Z]+-\d{3}) \|", text, flags=re.MULTILINE)
    manifest_ids = [row["task_id"] for row in payload["tasks"]]
    assert table_ids == manifest_ids
    assert len(table_ids) == 17
    assert "M6 Batch 1" in text
    assert "M6 Batch 4" in text
    assert "Only after protected-main exact M6 Exit GO may the product claim P2 admission." in text
    assert re.findall(r"\bM7-[A-Z]+-\d{3}\b", text) == []
