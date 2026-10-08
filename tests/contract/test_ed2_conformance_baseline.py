from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

from tpaa_ingest import (
    PRODUCTION_INTERCHANGE_FAMILIES,
    PRODUCTION_INTERCHANGE_PROFILE_AUTHORITY_VERSION,
    PRODUCTION_INTERCHANGE_PROFILE_SCHEMA,
    SourceFamily,
    production_interchange_profile,
)
from tpaa_runtime.production_p1_source_policy import (
    PRODUCTION_P1_SOURCE_MISSING_REASON_PREFIX,
    PRODUCTION_P1_SOURCE_POLICY_SCHEMA,
    PRODUCTION_P1_SOURCE_POLICY_VERSION,
    production_p1_source_family_policy,
)

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs" / "baseline" / "ED2-CONFORMANCE"
MATRIX = BASE / "ED2_DESIGN_CONFORMANCE_MATRIX.json"
INTERCHANGE_PROFILES = BASE / "PRODUCTION_INTERCHANGE_PROFILE_AUTHORITY.json"
SOURCE_FAMILY_POLICY = BASE / "P1_SOURCE_FAMILY_POLICY.json"
CATALOG = ROOT / "baseline" / "CB-1.4.0" / "canonical" / "P1_METRIC_CATALOG.json"


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



def test_ed2_interchange_profile_authority_matches_runtime_exactly() -> None:
    raw: object = json.loads(
        INTERCHANGE_PROFILES.read_text(encoding="utf-8")
    )
    assert isinstance(raw, dict)
    authority = cast(dict[str, object], raw)
    assert (
        authority["schema"]
        == "TPAA_ED2_PRODUCTION_INTERCHANGE_PROFILE_AUTHORITY_V1"
    )
    assert (
        authority["authority_version"]
        == PRODUCTION_INTERCHANGE_PROFILE_AUTHORITY_VERSION
    )

    profiles = _mappings(authority["profiles"])
    by_family = {
        str(item["source_family"]): item
        for item in profiles
    }
    assert set(by_family) == {
        family.value
        for family in PRODUCTION_INTERCHANGE_FAMILIES
    }

    for family in sorted(
        PRODUCTION_INTERCHANGE_FAMILIES,
        key=lambda item: item.value,
    ):
        item = by_family[family.value]
        runtime = production_interchange_profile(family)
        descriptor = {
            key: item[key]
            for key in (
                "schema",
                "source_family",
                "profile_id",
                "profile_version",
                "projection_class",
                "producer_contract",
                "metric_input_binding",
                "external_decoder_required",
            )
        }
        encoded = json.dumps(
            descriptor,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        expected_hash = hashlib.sha256(encoded).hexdigest()
        assert descriptor["schema"] == PRODUCTION_INTERCHANGE_PROFILE_SCHEMA
        assert expected_hash == item["profile_hash"]
        assert runtime.source_family is SourceFamily(family.value)
        assert runtime.profile_id == item["profile_id"]
        assert runtime.profile_version == item["profile_version"]
        assert runtime.profile_hash == expected_hash
        assert runtime.projection_class == item["projection_class"]



def test_ed2_p1_source_family_policy_matches_catalog_and_runtime() -> None:
    raw: object = json.loads(
        SOURCE_FAMILY_POLICY.read_text(encoding="utf-8")
    )
    assert isinstance(raw, dict)
    authority = cast(dict[str, object], raw)
    assert authority["schema"] == PRODUCTION_P1_SOURCE_POLICY_SCHEMA
    assert authority["policy_version"] == PRODUCTION_P1_SOURCE_POLICY_VERSION

    catalog_raw: object = json.loads(CATALOG.read_text(encoding="utf-8"))
    assert isinstance(catalog_raw, dict)
    catalog = cast(dict[str, object], catalog_raw)
    metric_rows = _mappings(catalog["metrics"])
    catalog_families = {
        str(item["family"])
        for item in metric_rows
    }

    policy_rows = _mappings(authority["families"])
    by_family = {
        str(item["metric_family"]): item
        for item in policy_rows
    }
    runtime = production_p1_source_family_policy()
    assert set(by_family) == catalog_families == set(runtime)

    behavior = _mapping(authority["missing_source_behavior"])
    assert behavior == {
        "classification": "BUSINESS_INSUFFICIENCY",
        "metric_status": "INSUFFICIENT_DATA",
        "whole_job_failure": False,
        "formula_execution_when_missing": False,
        "reason_code_prefix": PRODUCTION_P1_SOURCE_MISSING_REASON_PREFIX,
        "malformed_source_contract_failure": True,
    }

    for family in sorted(catalog_families):
        raw_sources = by_family[family]["required_source_families"]
        assert isinstance(raw_sources, list)
        assert all(isinstance(item, str) for item in raw_sources)
        assert set(raw_sources) == {
            item.value
            for item in runtime[family]
        }
