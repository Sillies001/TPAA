from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_object_layout_policy_matches_platform_authority() -> None:
    policy = json.loads(
        (REPO_ROOT / "tools" / "storage" / "OBJECT_LAYOUT_POLICY.json").read_text(
            encoding="utf-8"
        )
    )
    assert policy["status"] == "FROZEN"
    assert policy["logical_schemes"] == ["tpaa-object", "tpaa-parquet"]
    assert policy["unicode_normalization"] == "NFC"
    assert policy["case_collision_comparison"] == "NFC+casefold"
    assert "absolute_path" in policy["logical_hash_excludes"]


def test_business_layers_do_not_import_platform_implementation() -> None:
    for package in (
        "tpaa_application",
        "tpaa_metric",
        "tpaa_world",
        "tpaa_episode",
        "tpaa_context",
        "tpaa_observation",
        "tpaa_assessment",
        "tpaa_longitudinal",
    ):
        root = REPO_ROOT / "src" / package
        for path in root.rglob("*.py"):
            assert "tpaa_platform" not in path.read_text(encoding="utf-8"), path
