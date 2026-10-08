from __future__ import annotations

import json
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs" / "baseline" / "ED2-CONFORMANCE"
MATRIX = BASE / "ED2_DESIGN_CONFORMANCE_MATRIX.json"


def _load() -> dict[str, object]:
    raw: object = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return cast(dict[str, object], raw)


def _mapping(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    assert all(isinstance(key, str) for key in value)
    return cast(dict[str, object], value)


def _mappings(value: object) -> list[dict[str, object]]:
    assert isinstance(value, list)
    return [_mapping(item) for item in value]


def test_ed2_conformance_uses_only_three_large_batches() -> None:
    baseline = _load()
    assert baseline["schema"] == "TPAA_ED2_DESIGN_CONFORMANCE_BASELINE_V1"

    governance = _mapping(baseline["governance"])
    assert governance["umbrella_issue"] == 245
    assert governance["batch_issues"] == [246, 247, 248]
    assert governance["batch_count"] == 3
    assert governance["no_m10_p7"] is True
    assert governance["exact_required_job_count"] == 14

    batches = _mappings(baseline["delivery_batches"])
    assert [item["batch"] for item in batches] == ["B1", "B2", "B3"]
    assert all(
        item["ci_policy"] == "ACCUMULATE_ON_BRANCH_THEN_SINGLE_PR_CANDIDATE"
        for item in batches
    )


def test_ed2_conformance_preserves_historical_1_0_1_qualification() -> None:
    baseline = _load()
    historical = _mapping(baseline["historical_qualification"])
    assert historical == {
        "product_version": "1.0.1",
        "protected_main_sha": "abf00eb44316c4f4927b5e7399bfe0ebab3a3f77",
        "run_number": 696,
        "actions_run_id": 37619872063,
        "qualification": "TPAA_1_0_1_QUALIFIED",
        "must_not_be_rewritten": True,
    }

    qualification = _mapping(baseline["qualification"])
    assert qualification["design_conformance_claimed"] is False
    assert qualification["status"] == "ED2_CONFORMANCE_IN_PROGRESS"


def test_ed2_b1_freezes_exact_p1_catalog_membership_gap() -> None:
    baseline = _load()
    requirements = {
        str(item["id"]): item
        for item in _mappings(baseline["requirements"])
    }
    assert requirements["ED2-P1-001"]["batch"] == "B1"
    assert requirements["ED2-P1-001"]["status"] == "OPEN"
    assert requirements["ED2-P1-002"]["status"] == "OPEN"
    requirement = str(requirements["ED2-P1-002"]["requirement"])
    assert "40 AIRCRAFT" in requirement
    assert "72 MISSION_SYSTEM_INSTANCE" in requirement
    assert "4 TARGET_PAIR" in requirement
