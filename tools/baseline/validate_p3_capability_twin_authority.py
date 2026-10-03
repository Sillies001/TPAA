#!/usr/bin/env python3
"""Validate the M7 P3 capability/twin authority and execution profile exactly."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE = REPO_ROOT / "baseline" / "CB-1.4.0"
CANONICAL = BASELINE / "canonical"
AUTHORITY = CANONICAL / "P3_CAPABILITY_TWIN_AUTHORITY.json"
PROFILE = CANONICAL / "P3_REFERENCE_CONDITION_OLS_MAD_LONGITUDINAL_PROFILE.json"
DTO = CANONICAL / "CROSS_LAYER_DTO_CONTRACTS.json"
M4 = CANONICAL / "M4_LONGITUDINAL_DEBRIEF_AUTHORITY.json"
CORE = REPO_ROOT / "migrations" / "authority" / "CORE_LOGICAL_MODEL_DB_1_6_0.json"
LOCK = BASELINE / "BASELINE_LOCK.json"

EXPECTED_AUTHORITY_SHA256 = "76726fc533cde7b0a183a1575cb50276e166081cc37ebe4857ed3324ab913e3b"
EXPECTED_PROFILE_SHA256 = "d66aa780d1c2e31ec664d173a0cdbc355f98c9ff3f751a6949e84f74cdf93876"
EXPECTED_M7_DTO_SHA256 = "644370d40e42960144102e6f404b6ee31af9753686b67bb27e47690515898c41"
EXPECTED_M7_LOCK_SHA256 = "0d2f11dc5ee41038a1ef63b8b4157730bd1cd313c7a98faaa286132397b8de47"
EXPECTED_P3_DTO_SUBSET_SHA256 = "90b2f51d0c9b81ed0b3d6ff4294a945c087578a41c01a9c11a5ac7571f6ad91f"
PARENT_LOCK_SHA256 = "f95167aca59dc993ced607e55f21f01080c4e24cc0759bf97482d49654ea182b"
M4_SHA256 = "c1c073bce8870feceb90bdb6c28172c4c726de6b15fc70208e169336baa59dfa"

P3_DTO_NAMES = (
    "P3EligibleAdjustedEstimateDTO",
    "P3LifecycleSegmentDTO",
    "P3ModelValidationSnapshotDTO",
    "CapabilityModelDTO",
    "CapabilitySurfaceDTO",
    "AircraftTwinRevisionDTO",
    "IntrinsicCapabilityEstimateDTO",
    "P3AdmissionStateDTO",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} root must be object")
    return value


def _lock_entry(lock: dict[str, Any], filename: str) -> dict[str, Any]:
    artifacts = lock.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("BASELINE_LOCK artifacts invalid")
    entry = next(
        (
            item
            for item in artifacts
            if isinstance(item, dict) and item.get("file") == filename
        ),
        None,
    )
    if not isinstance(entry, dict):
        raise ValueError(f"{filename} missing from BASELINE_LOCK")
    return entry


def verify() -> dict[str, object]:
    authority = _load(AUTHORITY)
    profile = _load(PROFILE)
    dto = _load(DTO)
    m4 = _load(M4)
    core = _load(CORE)
    lock = _load(LOCK)
    dto_contracts = dto["contracts"]
    p3_dto_subset_hash = _canonical_hash(
        {name: dto_contracts.get(name, {}) for name in P3_DTO_NAMES}
    )
    lineage = lock["baseline"]["lock_lineage_sha256"]
    checks: dict[str, bool] = {
        "authority_sha": _sha(AUTHORITY) == EXPECTED_AUTHORITY_SHA256,
        "profile_sha": _sha(PROFILE) == EXPECTED_PROFILE_SHA256,
        "dto_lock_current": (
            _lock_entry(lock, "CROSS_LAYER_DTO_CONTRACTS.json").get("sha256") == _sha(DTO)
        ),
        "p3_dto_subset_preserved": p3_dto_subset_hash == EXPECTED_P3_DTO_SUBSET_SHA256,
        "m7_lock_lineage_preserved": EXPECTED_M7_LOCK_SHA256 in lineage,
        "m4_sha": _sha(M4) == M4_SHA256,
        "identity": (
            authority.get("authority_id") == "P3_CAPABILITY_TWIN_AUTHORITY"
            and authority.get("version") == "1.0.0"
            and profile.get("profile_id")
            == "P3_REFERENCE_CONDITION_OLS_MAD_LONGITUDINAL"
            and profile.get("version") == "1.0.0"
        ),
        "schema_unchanged": (
            authority["scope"]["db_schema_change"] is False
            and authority["scope"]["db_schema_version"] == "1.6.0"
            and authority["scope"]["shadow_schema_permitted"] is False
        ),
        "p1_p2_immutable": (
            authority["scope"]["p1_observed_layer_immutable"] is True
            and authority["scope"]["p2_adjusted_layer_immutable"] is True
        ),
        "p3_not_admitted": authority["scope"]["p3_authority_frozen_not_admitted"] is True,
        "later_phases_inactive": authority["scope"]["p4_p6_active"] is False,
        "not_identifiable_excluded": (
            authority["p2_eligibility_contract"]["required_p2_status"] == "IDENTIFIABLE"
            and authority["p2_eligibility_contract"][
                "not_identifiable_numeric_use_forbidden"
            ]
            is True
        ),
        "configuration_key": (
            authority["p2_eligibility_contract"]["configuration_key_rule"]
            == "AIRCRAFT_CONFIG_SHA256:<master.aircraft_configuration_snapshot.snapshot_hash>"
            and "configuration_key"
            in authority["lifecycle_segment_contract"]["profile_v1_segment_dimensions"]
            and "configuration_snapshot_id"
            not in authority["lifecycle_segment_contract"]["profile_v1_segment_dimensions"]
        ),
        "lifecycle_fail_closed": (
            authority["lifecycle_segment_contract"][
                "lifecycle_event_inside_selected_session_interval_forces_new_segment"
            ]
            is True
        ),
        "validation_no_free_threshold": (
            authority["validation_snapshot_contract"][
                "implementation_selected_threshold_forbidden"
            ]
            is True
            and authority["validation_snapshot_contract"]["minimum_total_eligible_points"]
            == 4
            and authority["validation_snapshot_contract"]["training_prefix_min_points"]
            == 3
            and authority["validation_snapshot_contract"]["training_prefix_max_points"]
            == 5
        ),
        "managed_object_fail_closed": (
            authority["managed_object_contract"]["required_gc_state"] == "ACTIVE"
            and authority["managed_object_contract"]["required_sealed"] is True
            and authority["managed_object_contract"]["required_deleted_at"] is None
            and authority["managed_object_contract"]["hash_must_equal_artifact_sha256"]
            is True
        ),
        "profile_subject_scope": (
            profile["scope"]["subject_type"] == "AIRCRAFT"
            and profile["scope"]["aircraft_model_level_supported"] is False
            and profile["scope"]["stronger_intrinsic_claim_supported"] is False
        ),
        "m4_exact_reuse": (
            profile["longitudinal_core"]["x_axis_semantics"] == "SESSION_ORDER"
            and profile["longitudinal_core"]["ewma"]["alpha_numerator"] == 1
            and profile["longitudinal_core"]["ewma"]["alpha_denominator"] == 3
            and profile["longitudinal_core"]["slope"]["estimator"]
            == "ORDINARY_LEAST_SQUARES"
            and profile["longitudinal_core"]["slope"]["min_valid_points"] == 3
            and profile["longitudinal_core"]["slope"]["max_valid_points"] == 5
            and profile["longitudinal_core"]["stability"]["statistic"]
            == "UNSCALED_MEDIAN_ABSOLUTE_DEVIATION"
            and profile["longitudinal_core"]["stability"]["min_valid_points"] == 3
            and profile["longitudinal_core"]["stability"]["max_valid_points"] == 5
            and m4["trend_profile"]["profile_hash"]
            == "87981c6e3c79f9587786d082d826a6393d15192f67b10c817612da8912982729"
        ),
        "validation_semantics": (
            profile["validation_contract"]["strategy"]
            == "TEMPORAL_LAST_POINT_HOLDOUT_THEN_FINAL_REFIT"
            and profile["validation_contract"]["acceptance"]
            == "abs(predicted-heldout_adjusted_value) <= training_prefix_MAD + heldout_input_half_width"
            and profile["validation_contract"][
                "implementation_selected_tolerance_or_multiplier_forbidden"
            ]
            is True
        ),
        "claim_boundary": (
            authority["claim_contract"]["default_claim_level"]
            == "REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE"
            and authority["claim_contract"]["stronger_claim_requires_independent_evidence"]
            is True
            and authority["claim_contract"]["profile_v1_allowed_claim_levels"]
            == ["REFERENCE_CONDITION_LONGITUDINAL_ESTIMATE"]
        ),
        "m7_exit_gate": (
            authority["admission_guard"]["required_event"] == "push"
            and authority["admission_guard"]["required_git_ref"] == "refs/heads/main"
            and authority["admission_guard"]["required_m7_exit_decision"] == "GO"
            and authority["admission_guard"]["required_job_count"] == 14
        ),
        "profile_source_binding": (
            profile["source_bindings"]["p3_authority_sha256"]
            == EXPECTED_AUTHORITY_SHA256
            and profile["source_bindings"]["cross_layer_dto_sha256"]
            == EXPECTED_M7_DTO_SHA256
            and profile["source_bindings"]["m4_longitudinal_authority_sha256"]
            == M4_SHA256
        ),
        "lock_lineage": (
            EXPECTED_M7_LOCK_SHA256 in lineage
            and PARENT_LOCK_SHA256 in lineage
            and lineage.index(EXPECTED_M7_LOCK_SHA256) < lineage.index(PARENT_LOCK_SHA256)
        ),
    }
    for filename, path, expected in (
        ("P3_CAPABILITY_TWIN_AUTHORITY.json", AUTHORITY, EXPECTED_AUTHORITY_SHA256),
        (
            "P3_REFERENCE_CONDITION_OLS_MAD_LONGITUDINAL_PROFILE.json",
            PROFILE,
            EXPECTED_PROFILE_SHA256,
        ),
        ("CROSS_LAYER_DTO_CONTRACTS.json", DTO, _sha(DTO)),
    ):
        entry = _lock_entry(lock, filename)
        checks[f"lock:{filename}"] = (
            entry.get("sha256") == expected and entry.get("bytes") == len(path.read_bytes())
        )
    section_names = (
        "p2_eligibility_contract",
        "lifecycle_segment_contract",
        "validation_snapshot_contract",
        "managed_object_contract",
        "execution_profile_contract",
        "claim_contract",
        "knowledge_time_contract",
        "release_replay_contract",
        "admission_guard",
        "dto_contracts",
    )
    for name in section_names:
        checks[f"authority_hash:{name}"] = (
            authority["contract_hashes"][f"{name}_sha256"]
            == _canonical_hash(authority[name])
        )
    for name in (
        "ordering_contract",
        "segmentation_contract",
        "longitudinal_core",
        "validation_contract",
        "uncertainty_contract",
        "validity_domain_contract",
        "output_contract",
        "managed_object_contract",
        "identity_contract",
        "forbidden_fallbacks",
        "qualification_matrix",
    ):
        checks[f"profile_hash:{name}"] = (
            profile["contract_hashes"][f"{name}_sha256"] == _canonical_hash(profile[name])
        )
    central = dto["contracts"]
    for name, expected in authority["dto_contracts"].items():
        fields = central[name]["fields"]
        checks[f"dto:{name}"] = [field["field"] for field in fields] == expected["fields"]
    tables = core["tables"]
    for table in (
        "capability.capability_model",
        "capability.capability_surface",
        "capability.aircraft_twin_revision",
        "capability.intrinsic_capability_estimate",
        "registry.dataset_snapshot",
        "registry.object_reference",
        "registry.session_order_scope",
        "registry.session_order_assignment",
        "master.aircraft_configuration_snapshot",
        "master.aircraft_lifecycle_event",
    ):
        checks[f"core:{table}"] = tables[table]["schema_version"] == "1.6.0"
    object_fields = {
        field["name"]: field for field in tables["registry.object_reference"]["fields"]
    }
    checks["core:object_gc_active"] = "'ACTIVE'" in object_fields["gc_state"]["sql"]
    failed = sorted(name for name, ok in checks.items() if not ok)
    return {
        "schema": "TPAA_M7_C3_P3_CAPABILITY_TWIN_AUTHORITY_EVIDENCE_V1",
        "task_id": "M7-GOV-001",
        "tracking_issue": 169,
        "status": "PASS" if not failed else "FAIL",
        "authority_sha256": EXPECTED_AUTHORITY_SHA256,
        "profile_sha256": EXPECTED_PROFILE_SHA256,
        "dto_sha256": _sha(DTO),
        "baseline_lock_sha256": _sha(LOCK),
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
            "schema": "TPAA_M7_C3_P3_CAPABILITY_TWIN_AUTHORITY_EVIDENCE_V1",
            "task_id": "M7-GOV-001",
            "tracking_issue": 169,
            "status": "FAIL",
            "task_complete": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
