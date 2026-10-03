from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDIB_DIR = ROOT / "docs" / "baseline" / "SDIB-1.6"
SDIB = SDIB_DIR / "TPAA_软件开发实施基线_SDIB-1.6.md"
M7_TASKS = SDIB_DIR / "M7_TASK_BASELINE.json"
SOURCE_HASHES = SDIB_DIR / "SDIB-1.6_SOURCE_BASELINE.sha256"
MILESTONES = ROOT / "baseline" / "CB-1.4.0" / "canonical" / "DEVELOPMENT_MILESTONE_REGISTRY.json"
CAPABILITY = ROOT / "baseline" / "CB-1.4.0" / "canonical" / "CAPABILITY_PHASE_REGISTRY.json"
EXTENSION = ROOT / "baseline" / "CB-1.4.0" / "canonical" / "EXTENSION_CONTRACT_REGISTRY.json"
CORE = ROOT / "migrations" / "authority" / "CORE_LOGICAL_MODEL_DB_1_6_0.json"

ENTRY_SHA = "892e4a64a321be9c7252b66207a7d1d90a6ce98d"
CANONICAL_REQUIRED_WORKSTREAMS = {
    "WS-CAPABILITY", "WS-LONGITUDINAL", "WS-TEST", "WS-GUI", "WS-GOVERNANCE"
}
SUPPORTING_WORKSTREAMS = {"WS-DATA", "WS-API"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_hashes() -> dict[str, str]:
    result: dict[str, str] = {}
    for line in SOURCE_HASHES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, filename = line.split(maxsplit=1)
            result[filename] = digest
    return result


def test_sdib_1_6_version_scope_and_source_hashes() -> None:
    text = SDIB.read_text(encoding="utf-8")
    assert text.startswith("# 飞机机载数据评估系统软件开发实施基线 SDIB-1.6\n")
    assert "**Software Development Implementation Baseline — SDIB-1.6**" in text
    assert "M7 — P3 Capability/Twin Activation" in text
    hashes = _source_hashes()
    assert hashes[SDIB.name] == _sha256(SDIB)
    assert hashes[M7_TASKS.name] == _sha256(M7_TASKS)


def test_m7_task_manifest_is_exact_and_batched_once() -> None:
    payload = json.loads(M7_TASKS.read_text(encoding="utf-8"))
    ids = [task["task_id"] for task in payload["tasks"]]
    assert payload["schema"] == "TPAA_SDIB_M7_TASK_BASELINE_V1"
    assert payload["sdib_version"] == "SDIB-1.6"
    assert payload["milestone"] == "M7"
    assert payload["task_count"] == len(ids) == len(set(ids)) == 18
    assert set(payload["canonical_required_workstreams"]) == CANONICAL_REQUIRED_WORKSTREAMS
    assert set(payload["supporting_workstreams"]) == SUPPORTING_WORKSTREAMS
    assert [b["batch_id"] for b in payload["batches"]] == [
        "M7-BATCH-1", "M7-BATCH-2", "M7-BATCH-3", "M7-BATCH-4"
    ]
    batched = [item for batch in payload["batches"] for item in batch["task_ids"]]
    assert len(batched) == len(set(batched)) == 18
    assert set(batched) == set(ids)


def test_m7_matches_frozen_milestone_and_p3_contract() -> None:
    payload = json.loads(M7_TASKS.read_text(encoding="utf-8"))
    milestones = json.loads(MILESTONES.read_text(encoding="utf-8"))
    capability = json.loads(CAPABILITY.read_text(encoding="utf-8"))
    extension = json.loads(EXTENSION.read_text(encoding="utf-8"))
    m7 = next(row for row in milestones["milestones"] if row["code"] == "M7")
    p3 = next(row for row in capability["capability_phases"] if row["p_code"] == "P3")
    contract = extension["p_capability_contracts"]["P3"]
    assert m7["name"] == "P3 Capability/Twin Activation"
    assert set(m7["required_workstreams"]) == CANONICAL_REQUIRED_WORKSTREAMS
    assert set(payload["canonical_required_workstreams"]) == CANONICAL_REQUIRED_WORKSTREAMS
    assert p3["name"] == "Intrinsic Capability / Aircraft Twin"
    assert contract["name"] == "Reference-condition Longitudinal Capability / Aircraft Twin"
    assert "validated P2 estimates" in contract["inputs"]
    assert any("intrinsic wording requires" in rule for rule in contract["rules"])
    assert any("not a real-time flight-state mirror" in rule for rule in contract["rules"])


def test_m7_core_products_reuse_db_1_6_0_and_managed_objects() -> None:
    payload = json.loads(M7_TASKS.read_text(encoding="utf-8"))
    core = json.loads(CORE.read_text(encoding="utf-8"))
    for table in (
        "capability.capability_model",
        "capability.capability_surface",
        "capability.aircraft_twin_revision",
        "capability.intrinsic_capability_estimate",
    ):
        assert table in core["tables"]
        assert core["tables"][table]["schema_version"] == "1.6.0"
    model_fields = {f["name"]: f for f in core["tables"]["capability.capability_model"]["fields"]}
    surface_fields = {f["name"]: f for f in core["tables"]["capability.capability_surface"]["fields"]}
    assert model_fields["model_artifact_uri"]["nullable"] is False
    assert surface_fields["dataset_uri"]["nullable"] is False
    assert "registry.object_reference" in core["tables"]
    storage = payload["core_storage_authority"]
    assert storage["db_schema_version"] == "1.6.0"
    assert storage["shadow_schema_permitted"] is False


def test_m7_entry_boundary_blocker_and_rolling_design_are_fail_closed() -> None:
    payload = json.loads(M7_TASKS.read_text(encoding="utf-8"))
    entry = payload["entry_evidence"]
    assert entry["protected_main_sha"] == ENTRY_SHA
    assert entry["protected_main_run_number"] == 494
    assert entry["protected_main_actions_run_id"] == 36697493917
    assert entry["p2_qualification"] == "P2_M6_QUALIFIED"
    assert entry["m6_exit_decision"] == "GO"
    assert entry["p2_admitted"] is True
    assert entry["hosted_ci_required_jobs"] == 14
    boundary = payload["capability_boundary"]
    assert boundary["currently_admitted_phases"] == ["P1", "P2"]
    assert boundary["candidate_phase"] == "P3"
    assert boundary["explicitly_not_admitted"] == ["P4", "P5", "P6"]
    assert boundary["p2_not_identifiable_numeric_training_target_forbidden"] is True
    blocker = payload["authority_blockers"]
    assert blocker["c3_issue"] == 169
    assert blocker["fail_closed"] is True
    rolling = payload["rolling_design"]
    assert rolling["policy_issue"] == 149
    assert rolling["next_detailed_design_milestone"] == "M8"
    assert rolling["next_design_issue"] == 170
    assert rolling["m8_implementation_forbidden_before_m7_exit_go"] is True


def test_m7_authority_boundary_contains_no_implementation_defaults() -> None:
    payload = json.loads(M7_TASKS.read_text(encoding="utf-8"))
    b = payload["authority_boundaries"]
    assert b["implementation_invented_model_algorithm_or_threshold_forbidden"] is True
    assert b["current_latest_default_historical_resolution_forbidden"] is True
    assert b["same_episode_or_future_information_leakage_forbidden"] is True
    assert b["p2_not_identifiable_numeric_use_forbidden"] is True
    assert b["model_surface_uri_must_bind_sealed_active_managed_object"] is True
    assert b["local_file_or_mutable_model_alias_forbidden"] is True
    assert b["stronger_intrinsic_claim_requires_independent_evidence"] is True
    assert b["p4_p6_activation_forbidden"] is True


def test_m7_markdown_task_table_matches_machine_manifest() -> None:
    text = SDIB.read_text(encoding="utf-8")
    payload = json.loads(M7_TASKS.read_text(encoding="utf-8"))
    table_ids = re.findall(r"^\| (M7-[A-Z]+-\d{3}) \|", text, flags=re.MULTILINE)
    manifest_ids = [row["task_id"] for row in payload["tasks"]]
    assert table_ids == manifest_ids
    assert len(table_ids) == 18
    assert "M7 Batch 1" in text and "M7 Batch 4" in text
    assert "Only after protected-main exact M7 Exit GO may P3 be claimed admitted." in text
    assert re.findall(r"\bM8-[A-Z]+-\d{3}\b", text) == []
