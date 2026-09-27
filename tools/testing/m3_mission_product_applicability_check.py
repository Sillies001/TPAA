#!/usr/bin/env python3
"""M3-WORLD-004 mission-system product/applicability qualification evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
FIXTURE = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "m3"
    / "M3_WORLD_004_MISSION_SYSTEMS_V1.json"
)
TRACKING_ISSUE = 112

TRACK_ID = "61111111-1111-4111-8111-111111111111"
IRST = "62222222-2222-4222-8222-222222222222"
EO = "63333333-3333-4333-8333-333333333333"
RWR = "64444444-4444-4444-8444-444444444444"
ESM = "65555555-5555-4555-8555-555555555555"
DL = "66666666-6666-4666-8666-666666666666"
FUS = "67777777-7777-4777-8777-777777777777"
RADAR = "68888888-8888-4888-8888-888888888888"


def _git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    value = completed.stdout.strip()
    return value if len(value) == 40 else "UNKNOWN"


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_world.m3_mission_product_applicability import (
        load_m3_mission_product_inputs,
        project_m3_family_applicability,
    )

    first = load_m3_mission_product_inputs(FIXTURE, authority_root=AUTHORITY_ROOT)
    replay = load_m3_mission_product_inputs(FIXTURE, authority_root=AUTHORITY_ROOT)

    positive_cases = (
        ("P1-TRK-*", TRACK_ID),
        ("P1-ID-*", TRACK_ID),
        ("P1-PSV-*", IRST),
        ("P1-PSV-*", EO),
        ("P1-ESM-*", RWR),
        ("P1-ESM-*", ESM),
        ("P1-DL-*", DL),
        ("P1-FUS-*", FUS),
    )
    negative_cases = (
        ("P1-TRK-*", RADAR),
        ("P1-ID-*", RADAR),
        ("P1-PSV-*", RADAR),
        ("P1-ESM-*", RADAR),
        ("P1-DL-*", RADAR),
        ("P1-FUS-*", RADAR),
    )
    positives = tuple(
        project_m3_family_applicability(
            first,
            family_code=family,
            mission_system_instance_id=subject,
        )
        for family, subject in positive_cases
    )
    negatives = tuple(
        project_m3_family_applicability(
            first,
            family_code=family,
            mission_system_instance_id=subject,
        )
        for family, subject in negative_cases
    )

    contracts = {contract.family_code: contract for contract in first.contracts}
    expected_counts = {
        "P1-TRK-*": 7,
        "P1-ID-*": 12,
        "P1-PSV-*": 7,
        "P1-ESM-*": 6,
        "P1-DL-*": 8,
        "P1-FUS-*": 8,
    }
    acceptance = {
        "explicit_mission_system_identity": (
            len(first.subjects) == 8
            and len(
                {subject.mission_system_instance_id for subject in first.subjects}
            )
            == 8
        ),
        "subject_type_exact": all(
            contract.subject_type == "MISSION_SYSTEM_INSTANCE"
            for contract in first.contracts
        ),
        "catalog_family_membership_exact": all(
            len(contracts[family].metric_codes) == count
            for family, count in expected_counts.items()
        ),
        "trk_product_capability_exact": (
            contracts["P1-TRK-*"].applicability_mode == "PRODUCT_CAPABILITY"
            and contracts["P1-TRK-*"].required_product_semantics
            == "LOCAL_TRACK_PRODUCT"
        ),
        "id_product_capability_exact": (
            contracts["P1-ID-*"].applicability_mode == "PRODUCT_CAPABILITY"
            and contracts["P1-ID-*"].required_product_semantics
            == "ASSOCIATION_IDENTIFICATION_PRODUCT"
        ),
        "psv_system_types_exact": (
            contracts["P1-PSV-*"].applicability_mode == "SYSTEM_TYPE_SET"
            and contracts["P1-PSV-*"].allowed_system_types == ("IRST", "EO")
        ),
        "esm_system_types_exact": (
            contracts["P1-ESM-*"].applicability_mode == "SYSTEM_TYPE_SET"
            and contracts["P1-ESM-*"].allowed_system_types == ("RWR", "ESM")
        ),
        "dl_system_type_exact": (
            contracts["P1-DL-*"].applicability_mode == "SYSTEM_TYPE_EXACT"
            and contracts["P1-DL-*"].allowed_system_types == ("DATALINK",)
        ),
        "fus_system_type_exact": (
            contracts["P1-FUS-*"].applicability_mode == "SYSTEM_TYPE_EXACT"
            and contracts["P1-FUS-*"].allowed_system_types == ("FUSION",)
        ),
        "positive_paths_emit_product_inputs": all(
            result.applicable
            and result.product_input_emitted
            and result.reason_code.startswith("APPLICABLE_")
            for result in positives
        ),
        "non_applicable_paths_fail_closed": all(
            not result.applicable
            and not result.product_input_emitted
            and result.reason_code.startswith("NOT_APPLICABLE_")
            for result in negatives
        ),
        "catalog_core_hashes_bound": (
            len(first.catalog_sha256) == 64
            and len(first.core_schema_sha256) == 64
        ),
        "replay_stable": first == replay,
        "logical_hash_replay_stable": first.logical_hash == replay.logical_hash,
        "metric_logic_not_executed": not first.metric_logic_executed,
        "persistence_not_executed": not first.persistence_executed,
        "publication_not_executed": not first.publication_executed,
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)

    logical_product = {
        "fixture_id": first.fixture_id,
        "fixture_version": first.fixture_version,
        "fixture_sha256": first.fixture_sha256,
        "catalog_sha256": first.catalog_sha256,
        "core_schema_sha256": first.core_schema_sha256,
        "logical_hash": first.logical_hash,
        "subjects": [
            {
                "mission_system_instance_id": subject.mission_system_instance_id,
                "system_type": subject.system_type,
                "system_code": subject.system_code,
                "product_semantics": subject.product_semantics,
                "source_identity_ref": subject.source_identity_ref,
            }
            for subject in first.subjects
        ],
        "contracts": [
            {
                "family_code": contract.family_code,
                "subject_type": contract.subject_type,
                "applicability_mode": contract.applicability_mode,
                "allowed_system_types": contract.allowed_system_types,
                "required_product_semantics": contract.required_product_semantics,
                "metric_codes": contract.metric_codes,
            }
            for contract in first.contracts
        ],
        "positive_results": [
            {
                "family_code": result.family_code,
                "mission_system_instance_id": result.mission_system_instance_id,
                "system_type": result.system_type,
                "applicable": result.applicable,
                "reason_code": result.reason_code,
                "product_input_emitted": result.product_input_emitted,
                "logical_hash": result.logical_hash,
            }
            for result in positives
        ],
        "negative_results": [
            {
                "family_code": result.family_code,
                "mission_system_instance_id": result.mission_system_instance_id,
                "system_type": result.system_type,
                "applicable": result.applicable,
                "reason_code": result.reason_code,
                "product_input_emitted": result.product_input_emitted,
                "logical_hash": result.logical_hash,
            }
            for result in negatives
        ],
    }
    return {
        "schema": "TPAA_M3_WORLD_004_MISSION_PRODUCT_APPLICABILITY_EVIDENCE_V1",
        "task_id": "M3-WORLD-004",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "source_revision": _git_revision(),
        "task_complete": not failed,
        "implementation_complete": not failed,
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    try:
        payload = verify()
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M3_WORLD_004_MISSION_PRODUCT_APPLICABILITY_EVIDENCE_V1",
            "task_id": "M3-WORLD-004",
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "source_revision": _git_revision(),
            "task_complete": False,
            "implementation_complete": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        code = 2

    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.evidence is not None:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
