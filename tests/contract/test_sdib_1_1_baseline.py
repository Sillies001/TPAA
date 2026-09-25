from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SDIB_DIR = ROOT / "docs" / "baseline" / "SDIB-1.1"
SDIB = SDIB_DIR / "TPAA_软件开发实施基线_SDIB-1.1.md"
M2_TASKS = SDIB_DIR / "M2_TASK_BASELINE.json"
SOURCE_HASHES = SDIB_DIR / "SDIB-1.1_SOURCE_BASELINE.sha256"
CATALOG = ROOT / "baseline" / "CB-1.4.0" / "canonical" / "P1_METRIC_CATALOG.json"
MILESTONES = ROOT / "baseline" / "CB-1.4.0" / "canonical" / "DEVELOPMENT_MILESTONE_REGISTRY.json"


EXPECTED_WORKSTREAMS = {
    "WS-DATA",
    "WS-WORLD",
    "WS-METRIC",
    "WS-OBSERVATION",
    "WS-GUI",
    "WS-TEST",
}


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


def test_sdib_1_1_version_scope_and_source_hashes() -> None:
    text = SDIB.read_text(encoding="utf-8")
    hashes = _source_hashes()

    assert text.startswith("# 飞机机载数据评估系统软件开发实施基线 SDIB-1.1\n")
    assert "**Software Development Implementation Baseline — SDIB-1.1**" in text
    assert "M2 P1 Basic Flight Complete 为本版新增任务级详细基线" in text
    assert "M3～M9 保持后续 Epic/Entry-Gate 级路线基线" in text
    assert "不改变 116 项指标、661 输入绑定、Stage 或 DB schema 1.6.0" in text
    assert hashes[SDIB.name] == _sha256(SDIB)
    assert hashes[M2_TASKS.name] == _sha256(M2_TASKS)


def test_m2_task_manifest_is_exact_and_batched_once() -> None:
    payload = json.loads(M2_TASKS.read_text(encoding="utf-8"))
    tasks = payload["tasks"]
    ids = [task["task_id"] for task in tasks]

    assert payload["schema"] == "TPAA_SDIB_M2_TASK_BASELINE_V1"
    assert payload["sdib_version"] == "SDIB-1.1"
    assert payload["milestone"] == "M2"
    assert payload["task_count"] == 27
    assert len(ids) == 27
    assert len(set(ids)) == 27
    assert {task["workstream"] for task in tasks} == EXPECTED_WORKSTREAMS

    batches = payload["batches"]
    assert [batch["batch_id"] for batch in batches] == [
        "M2-BATCH-1",
        "M2-BATCH-2",
        "M2-BATCH-3",
        "M2-BATCH-4",
    ]
    batched = [task_id for batch in batches for task_id in batch["task_ids"]]
    assert len(batched) == 27
    assert len(set(batched)) == 27
    assert set(batched) == set(ids)


def test_m2_catalog_delivery_is_exact_foundation_32() -> None:
    payload = json.loads(M2_TASKS.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))

    authoritative = [
        metric["metric_code"]
        for metric in catalog["metrics"]
        if metric["delivery_milestone"] == "M2"
        and metric["delivery_batch"] == "P1_FOUNDATION_32"
    ]
    frozen = payload["catalog_delivery"]

    assert len(authoritative) == 32
    assert frozen["delivery_milestone"] == "M2"
    assert frozen["delivery_batch"] == "P1_FOUNDATION_32"
    assert frozen["count"] == 32
    assert frozen["metric_codes"] == authoritative
    assert len(set(authoritative)) == 32

    sns = catalog["family_applicability_contracts"]["P1-SNS-*"]
    assert sns["subject_type"] == "MISSION_SYSTEM_INSTANCE"
    assert sns["applicability_mode"] == "SYSTEM_TYPE_EXACT"
    assert sns["allowed_system_types"] == ["RADAR"]


def test_m2_manifest_matches_canonical_milestone_workstreams() -> None:
    payload = json.loads(M2_TASKS.read_text(encoding="utf-8"))
    milestones = json.loads(MILESTONES.read_text(encoding="utf-8"))
    m2 = next(item for item in milestones["milestones"] if item["code"] == "M2")

    assert m2["name"] == "P1 Basic Flight Complete"
    assert set(m2["required_workstreams"]) == EXPECTED_WORKSTREAMS
    assert set(payload["required_workstreams"]) == EXPECTED_WORKSTREAMS


def test_markdown_task_table_matches_machine_manifest() -> None:
    text = SDIB.read_text(encoding="utf-8")
    payload = json.loads(M2_TASKS.read_text(encoding="utf-8"))
    table_ids = re.findall(r"^\| (M2-[A-Z]+-\d{3}) \|", text, flags=re.MULTILINE)
    manifest_ids = [task["task_id"] for task in payload["tasks"]]

    assert table_ids == manifest_ids
    assert len(table_ids) == 27
    assert "M2 Batch 1 — Data + World foundations" in text
    assert "M2 Batch 2 — General Metric Engine + P1_FOUNDATION_32" in text
    assert "M2 Batch 3 — Publication + GUI product closure" in text
    assert "M2 Batch 4 — Golden / parity / cold-start / Exit" in text
    assert "只有 M2 Exit GO 后，才允许细化并进入 M3 实施 backlog。" in text
    assert re.findall(r"\bM3-[A-Z]+-\d{3}\b", text) == []
