#!/usr/bin/env python3
"""Validate the M6 P2 attribution/normalization C3 authority exactly."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE = REPO_ROOT / "baseline" / "CB-1.4.0"
AUTHORITY = BASELINE / "canonical" / "P2_ATTRIBUTION_NORMALIZATION_AUTHORITY.json"
LOCK = BASELINE / "BASELINE_LOCK.json"
CORE = BASELINE / "canonical" / "CORE_LOGICAL_MODEL.json"
EXPECTED_AUTHORITY_SHA256 = "1bfc6c9eb8e2142249c327af5698bc6a8925f983fd8363b1d2bd835966eea5fa"
EXPECTED_CONTRACT_HASHES = {
    "p1_eligibility_sha256": "47f19aa6534085914a4644ecf7a122ff4a669cedff2ad14cc051e77881985985",
    "feature_spec_sha256": "0b93f62d8f9a830d55c8803d9e65c0a8ed554cc77ba564c8bbaba0ed49b5e438",
    "reference_condition_sha256": (
        "45a07bd94de55a67eaf0d117c93438c18de058ed06dc0eb49f283cadae023c49"
    ),
    "cohort_specification_sha256": (
        "645e815be5d377690f51550bfaf0e3dfeae9623fac44fefbd516d13ec816adcb"
    ),
    "attribution_spec_sha256": "a48bd61d5b631a3ba0a0f1ec94deaf6c91fcdadeda378825a3ae8c47efd12588",
    "identifiability_sha256": "52ff8b6f713584f39dc94b19eb1ea60ca5d571d3a480895b0f9b34a2ee5722c9",
    "uncertainty_sha256": "e0aafe8568b8bdf1bf98111f5550f470ae621fd7b84e9dd129919227d0d37dbb",
    "factor_effect_sha256": "af4e4bf03cff7ed95816f8c496df4a387bd5eef247a90c7ecaf86ee5461403a9",
    "knowledge_time_sha256": "00b32ddcb260b80f1519c02dceea6e604623f7f3a62dbdfb189967d7d15a5a5d",
    "release_replay_sha256": "c398b55618413d1dc8e7d3d129aef5610e2ad129ed3ed894eab24f9f526e593b",
    "admission_guard_sha256": "36f41c05aded3bc893b517533616d091f8cbaf1509f7eb3c29316c442ca51bd8",
    "dto_contracts_sha256": "c7d671f75585052641a08c2686c8508bc73a8f047177322488bcfa5b88203812",
}


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _load() -> dict[str, Any]:
    raw = AUTHORITY.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != EXPECTED_AUTHORITY_SHA256:
        raise ValueError(
            f"authority hash mismatch expected={EXPECTED_AUTHORITY_SHA256} actual={actual}"
        )
    payload: object = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("authority root must be object")
    lock: object = json.loads(LOCK.read_text(encoding="utf-8"))
    if not isinstance(lock, dict) or not isinstance(lock.get("artifacts"), list):
        raise ValueError("BASELINE_LOCK invalid")
    entry = next(
        (
            item
            for item in lock["artifacts"]
            if isinstance(item, dict)
            and item.get("file") == "P2_ATTRIBUTION_NORMALIZATION_AUTHORITY.json"
        ),
        None,
    )
    if not isinstance(entry, dict):
        raise ValueError("P2 authority missing from BASELINE_LOCK")
    if entry.get("sha256") != actual or entry.get("bytes") != len(raw):
        raise ValueError("P2 authority lock binding drift")
    return payload


def _context_artifact_kind_sql() -> str:
    core: object = json.loads(CORE.read_text(encoding="utf-8"))
    if not isinstance(core, dict):
        raise ValueError("CORE_LOGICAL_MODEL root must be object")
    tables = core.get("tables")
    if not isinstance(tables, dict):
        raise ValueError("CORE_LOGICAL_MODEL tables invalid")
    table = tables.get("registry.context_artifact")
    if not isinstance(table, dict):
        raise ValueError("registry.context_artifact missing")
    fields = table.get("fields")
    if not isinstance(fields, list):
        raise ValueError("registry.context_artifact fields invalid")
    field = next(
        (
            item
            for item in fields
            if isinstance(item, dict) and item.get("name") == "artifact_kind"
        ),
        None,
    )
    if not isinstance(field, dict) or not isinstance(field.get("sql"), str):
        raise ValueError("registry.context_artifact.artifact_kind SQL missing")
    return field["sql"]


def verify() -> dict[str, object]:
    p = _load()
    artifact_kind_sql = _context_artifact_kind_sql()
    checks: dict[str, bool] = {
        "identity": p.get("authority_id") == "P2_ATTRIBUTION_NORMALIZATION_AUTHORITY",
        "version": p.get("version") == "1.0.0",
        "schema": p.get("db_schema_version") == "1.6.0",
        "core": p.get("core_baseline") == "CB-1.4.0",
        "milestone": p.get("effective_milestone") == "M6",
        "tracking_issue": p.get("tracking_issue") == 151,
        "no_schema_change": (
            p["scope"]["db_schema_change"] is False
            and p["scope"]["shadow_schema_permitted"] is False
        ),
        "p1_immutable": p["scope"]["p1_observed_layer_immutable"] is True,
        "p2_not_admitted": p["scope"]["p2_authority_frozen_not_admitted"] is True,
        "p3_p6_inactive": p["scope"]["p3_p6_active"] is False,
        "feature_existing_artifact_kind": (
            f"'{p['feature_spec_contract']['artifact_kind']}'" in artifact_kind_sql
        ),
        "reference_existing_carrier": (
            p["reference_condition_contract"]["carrier_table"]
            == "registry.context_artifact"
        ),
        "reference_existing_artifact_kind": (
            f"'{p['reference_condition_contract']['artifact_kind']}'"
            in artifact_kind_sql
        ),
        "attribution_existing_artifact_kind": (
            f"'{p['attribution_spec_contract']['artifact_kind']}'"
            in artifact_kind_sql
        ),
        "p2_subtype_disambiguation": (
            p["feature_spec_contract"]["logical_key_prefix"]
            == "P2_FACTOR_FEATURE_SPEC:"
            and p["reference_condition_contract"]["logical_key_prefix"]
            == "P2_REFERENCE_CONDITION:"
            and p["attribution_spec_contract"]["logical_key_prefix"]
            == "P2_ATTRIBUTION_SPEC:"
            and p["feature_spec_contract"]["artifact_schema_version"]
            == "TPAA_P2_FACTOR_FEATURE_SPEC_V1"
            and p["reference_condition_contract"]["artifact_schema_version"]
            == "TPAA_P2_REFERENCE_CONDITION_V1"
            and p["attribution_spec_contract"]["artifact_schema_version"]
            == "TPAA_P2_ATTRIBUTION_SPEC_V1"
        ),
        "cohort_existing_carrier": (
            p["cohort_specification_contract"]["carrier_table"]
            == "registry.dataset_snapshot"
        ),
        "not_identifiable_valid": (
            p["identifiability_contract"]["not_identifiable_is_valid_product"] is True
            and "NOT_IDENTIFIABLE" in p["identifiability_contract"]["statuses"]
        ),
        "future_forbidden": (
            p["knowledge_time_contract"]["future_information_forbidden"] is True
        ),
        "same_episode_forbidden": (
            p["knowledge_time_contract"]["same_episode_leakage_forbidden"] is True
        ),
        "historical_latest_forbidden": (
            p["release_replay_contract"]["published_p2_query_requires_exact_release_id"]
            is True
        ),
        "p1_overwrite_forbidden": (
            p["p1_eligibility_contract"]["overwrite_by_p2_forbidden"] is True
        ),
        "causal_boundary": (
            p["factor_effect_contract"][
                "causal_label_requires_independent_causal_evidence"
            ]
            is True
        ),
        "m6_exit_gate": (
            p["admission_guard"]["required_job_count"] == 14
            and p["admission_guard"]["required_m6_exit_decision"] == "GO"
        ),
    }
    section_map = {
        "p1_eligibility_sha256": p["p1_eligibility_contract"],
        "feature_spec_sha256": p["feature_spec_contract"],
        "reference_condition_sha256": p["reference_condition_contract"],
        "cohort_specification_sha256": p["cohort_specification_contract"],
        "attribution_spec_sha256": p["attribution_spec_contract"],
        "identifiability_sha256": p["identifiability_contract"],
        "uncertainty_sha256": p["uncertainty_contract"],
        "factor_effect_sha256": p["factor_effect_contract"],
        "knowledge_time_sha256": p["knowledge_time_contract"],
        "release_replay_sha256": p["release_replay_contract"],
        "admission_guard_sha256": p["admission_guard"],
        "dto_contracts_sha256": p["dto_contracts"],
    }
    for name, section in section_map.items():
        checks[f"hash:{name}"] = (
            p["contract_hashes"][name] == _canonical_hash(section)
            and p["contract_hashes"][name] == EXPECTED_CONTRACT_HASHES[name]
        )
    golden = p["golden_vectors"]
    checks.update(
        {
            "golden_not_identifiable": (
                golden["not_identifiable_valid"]["status"] == "NOT_IDENTIFIABLE"
                and golden["not_identifiable_valid"]["adjusted_value"] is None
            ),
            "golden_future_fail": (
                golden["future_information_fail"]["expected_error"]
                == "FAIL_CLOSED_P2_FUTURE_INFORMATION"
            ),
            "golden_same_episode_fail": (
                golden["same_episode_fail"]["expected_error"]
                == "FAIL_CLOSED_P2_SAME_EPISODE_LEAKAGE"
            ),
            "golden_pre_exit_fail": (
                golden["p2_pre_exit_claim_fail"]["expected_error"]
                == "FAIL_CLOSED_P2_NOT_ADMITTED"
            ),
        }
    )
    failed = sorted(name for name, ok in checks.items() if not ok)
    return {
        "schema": "TPAA_M6_C3_P2_ATTRIBUTION_AUTHORITY_EVIDENCE_V1",
        "task_id": "M6-GOV-001",
        "tracking_issue": 151,
        "status": "PASS" if not failed else "FAIL",
        "authority_sha256": EXPECTED_AUTHORITY_SHA256,
        "checks": checks,
        "failed_checks": failed,
        "task_complete": False,
        "completion_gate": "EXACT_HEAD_AND_PROTECTED_MAIN_HOSTED_CI_REQUIRED",
    }


def main() -> int:
    try:
        result = verify()
    except Exception as exc:
        result = {
            "schema": "TPAA_M6_C3_P2_ATTRIBUTION_AUTHORITY_EVIDENCE_V1",
            "task_id": "M6-GOV-001",
            "tracking_issue": 151,
            "status": "FAIL",
            "task_complete": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
