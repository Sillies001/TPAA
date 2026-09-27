from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDIB_DIR = ROOT / "docs" / "baseline" / "SDIB-1.2"
SDIB = SDIB_DIR / "TPAA_软件开发实施基线_SDIB-1.2.md"
M3_TASKS = SDIB_DIR / "M3_TASK_BASELINE.json"
SOURCE_HASHES = SDIB_DIR / "SDIB-1.2_SOURCE_BASELINE.sha256"
CATALOG = ROOT / "baseline" / "CB-1.4.0" / "canonical" / "P1_METRIC_CATALOG.json"
MILESTONES = (
    ROOT
    / "baseline"
    / "CB-1.4.0"
    / "canonical"
    / "DEVELOPMENT_MILESTONE_REGISTRY.json"
)
STAGES = ROOT / "baseline" / "CB-1.4.0" / "canonical" / "STAGE_REGISTRY.json"


EXPECTED_WORKSTREAMS = {
    "WS-WORLD",
    "WS-METRIC",
    "WS-OBSERVATION",
    "WS-API",
    "WS-GUI",
    "WS-TEST",
}
EXPECTED_FAMILY_COUNTS = {
    "AIRCRAFT_FLIGHT": 17,
    "AIRCRAFT_ENERGY": 8,
    "AIRCRAFT_CONTROL_RESPONSE": 4,
    "AIRCRAFT_HANDLING": 4,
    "AIRCRAFT_PERSISTENCE": 3,
    "TRACK_PERFORMANCE": 7,
    "ASSOCIATION_IDENTIFICATION": 12,
    "PASSIVE_SENSOR": 7,
    "RWR_ESM": 6,
    "DATALINK": 8,
    "SENSOR_FUSION": 8,
}
EXPECTED_STAGE_PROFILES = [
    "BASIC_FLIGHT_V1",
    "WVR_ENGAGEMENT_V1",
    "BVR_KILL_CHAIN_V1",
    "STRIKE_MISSION_V1",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_hashes() -> dict[str, str]:
    result: dict[str, str] = {}
    for line in SOURCE_HASHES.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, filename = line.split(maxsplit=1)
        result[filename] = digest
    return result


def test_sdib_1_2_version_scope_and_source_hashes() -> None:
    text = SDIB.read_text(encoding="utf-8")
    hashes = _source_hashes()

    assert text.startswith("# 飞机机载数据评估系统软件开发实施基线 SDIB-1.2\n")
    assert "**Software Development Implementation Baseline — SDIB-1.2**" in text
    assert "M3 P1 Four-Training-Type Complete 为本版新增任务级详细基线" in text
    assert "M4～M9 保持后续 Epic/Entry-Gate 级路线基线" in text
    assert "M2 protected-main Exit GO" in text
    assert hashes[SDIB.name] == _sha256(SDIB)
    assert hashes[M3_TASKS.name] == _sha256(M3_TASKS)


def test_m3_task_manifest_is_exact_and_batched_once() -> None:
    payload = json.loads(M3_TASKS.read_text(encoding="utf-8"))
    tasks = payload["tasks"]
    ids = [task["task_id"] for task in tasks]

    assert payload["schema"] == "TPAA_SDIB_M3_TASK_BASELINE_V1"
    assert payload["sdib_version"] == "SDIB-1.2"
    assert payload["milestone"] == "M3"
    assert payload["task_count"] == 28
    assert len(ids) == 28
    assert len(set(ids)) == 28
    assert {task["workstream"] for task in tasks} == EXPECTED_WORKSTREAMS

    batches = payload["batches"]
    assert [batch["batch_id"] for batch in batches] == [
        "M3-BATCH-1",
        "M3-BATCH-2",
        "M3-BATCH-3",
        "M3-BATCH-4",
    ]
    batched = [task_id for batch in batches for task_id in batch["task_ids"]]
    assert len(batched) == 28
    assert len(set(batched)) == 28
    assert set(batched) == set(ids)


def test_m3_catalog_delivery_is_exact_remainder_84_and_total_116() -> None:
    payload = json.loads(M3_TASKS.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))

    remainder = [
        metric
        for metric in catalog["metrics"]
        if metric["delivery_milestone"] == "M3"
        and metric["delivery_batch"] == "P1_REMAINDER_84"
    ]
    foundation = [
        metric
        for metric in catalog["metrics"]
        if metric["delivery_milestone"] == "M2"
        and metric["delivery_batch"] == "P1_FOUNDATION_32"
    ]
    frozen = payload["catalog_delivery"]

    assert len(remainder) == frozen["count"] == 84
    assert len(foundation) == 32
    assert len(catalog["metrics"]) == 116
    assert len({item["metric_code"] for item in catalog["metrics"]}) == 116
    assert frozen["delivery_milestone"] == "M3"
    assert frozen["delivery_batch"] == "P1_REMAINDER_84"
    assert frozen["metric_codes"] == [item["metric_code"] for item in remainder]
    assert payload["integrated_p1_delivery"]["total_count"] == 116


def test_m3_family_counts_structured_and_applicability_are_exact() -> None:
    payload = json.loads(M3_TASKS.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    remainder = [
        metric
        for metric in catalog["metrics"]
        if metric["delivery_milestone"] == "M3"
        and metric["delivery_batch"] == "P1_REMAINDER_84"
    ]

    actual_counts: dict[str, int] = {}
    for metric in remainder:
        actual_counts[metric["family"]] = actual_counts.get(metric["family"], 0) + 1
    assert actual_counts == EXPECTED_FAMILY_COUNTS
    assert payload["family_counts"] == EXPECTED_FAMILY_COUNTS

    m3_structured = [
        metric["metric_code"]
        for metric in remainder
        if metric["value_kind"] == "STRUCTURED"
    ]
    all_structured = [
        metric["metric_code"]
        for metric in catalog["metrics"]
        if metric["value_kind"] == "STRUCTURED"
    ]
    structured = payload["structured_output_contract"]
    assert structured["m3_structured_count"] == len(m3_structured) == 6
    assert structured["total_p1_structured_count"] == len(all_structured) == 9
    assert structured["m3_metric_codes"] == m3_structured

    contracts = catalog["family_applicability_contracts"]
    frozen = payload["family_applicability"]
    for key in (
        "P1-AIR-*",
        "P1-TRK-*",
        "P1-ID-*",
        "P1-PSV-*",
        "P1-ESM-*",
        "P1-DL-*",
        "P1-FUS-*",
    ):
        assert frozen[key] == contracts[key]


def test_m3_manifest_matches_milestone_and_stage_authority() -> None:
    payload = json.loads(M3_TASKS.read_text(encoding="utf-8"))
    milestones = json.loads(MILESTONES.read_text(encoding="utf-8"))
    stages = json.loads(STAGES.read_text(encoding="utf-8"))
    m3 = next(item for item in milestones["milestones"] if item["code"] == "M3")

    assert m3["name"] == "P1 Four-Training-Type Complete"
    assert set(m3["required_workstreams"]) == EXPECTED_WORKSTREAMS
    assert set(payload["required_workstreams"]) == EXPECTED_WORKSTREAMS
    assert payload["training_stage_profiles"] == EXPECTED_STAGE_PROFILES
    assert all(profile in stages["profiles"] for profile in EXPECTED_STAGE_PROFILES)
    assert payload["entry_evidence"]["exit_decision"] == "GO"
    assert payload["entry_evidence"]["protected_main_run_number"] == 338


def test_markdown_task_table_matches_machine_manifest() -> None:
    text = SDIB.read_text(encoding="utf-8")
    payload = json.loads(M3_TASKS.read_text(encoding="utf-8"))
    table_ids = re.findall(r"^\| (M3-[A-Z]+-\d{3}) \|", text, flags=re.MULTILINE)
    manifest_ids = [task["task_id"] for task in payload["tasks"]]

    assert table_ids == manifest_ids
    assert len(table_ids) == 28
    assert "M3 Batch 1 — Four-training World/Event + fixture foundations" in text
    assert "M3 Batch 2 — General Metric expansion + P1_REMAINDER_84" in text
    assert "M3 Batch 3 — Publication + API + GUI product closure" in text
    assert "M3 Batch 4 — Golden / parity / cold-start / Exit" in text
    assert "只有 M3 Exit GO 后，才允许细化并进入 M4 实施 backlog。" in text
    assert re.findall(r"\bM4-[A-Z]+-\d{3}\b", text) == []
