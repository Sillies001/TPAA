#!/usr/bin/env python3
"""PRCB C5 final installed-product review and detached release attestation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
RELEASE_CONTRACT = ROOT / "docs" / "baseline" / "PRCB-1.0" / "C5_RELEASE_CONTRACT.json"
ACCEPTANCE_CONTRACT = (
    ROOT / "docs" / "baseline" / "PRCB-1.0" / "PRCB_ACCEPTANCE_CONTRACT.json"
)
TASK_BASELINE = ROOT / "docs" / "baseline" / "PRCB-1.0" / "PRCB_TASK_BASELINE.json"

MANDATORY_PROFILES = (
    "LINUX_DESKTOP_X64",
    "LINUX_SERVICE_X64",
    "WINDOWS_DESKTOP_X64",
    "WINDOWS_SERVICE_X64",
)
SERVICE_PROFILES = ("LINUX_SERVICE_X64", "WINDOWS_SERVICE_X64")
REQUIRED_EQ_ACCEPTANCE = (
    "exact_four_profiles",
    "same_candidate_source_revision",
    "immutable_package_sha256_all_profiles",
    "desktop_windows_linux_p2_semantic_equivalence",
    "service_windows_linux_p2_semantic_equivalence",
    "shared_p1_p3_p6_exact_identity_all_profiles",
    "desktop_installed_discovery_auth_replay_all_os",
    "service_real_postgres_rbac_recovery_all_os",
    "restart_backup_restore_exact_all_profiles",
    "formal_release_not_claimed",
)


def _json(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path}: root JSON object required")
    return cast(dict[str, Any], value)


def _hex64(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdef" for ch in value)
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_sha256(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _exact_profile_sha_map(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(cast(dict[str, Any], value)) == set(MANDATORY_PROFILES)
        and all(_hex64(item) for item in cast(dict[str, Any], value).values())
    )


def review(
    *,
    logical_equivalence: Path,
    expected_revision: str,
    checked_out_revision: str,
    event_name: str,
    git_ref: str,
    run_conclusion: str,
    required_jobs_success: int,
    required_jobs_total: int,
) -> tuple[dict[str, object], dict[str, object]]:
    contract = _json(RELEASE_CONTRACT)
    acceptance_contract = _json(ACCEPTANCE_CONTRACT)
    task_baseline = _json(TASK_BASELINE)
    equivalence = _json(logical_equivalence)

    package_policy = cast(dict[str, Any], contract.get("package_policy", {}))
    final_contract = cast(
        dict[str, Any],
        contract.get("final_qualification", {}),
    )
    invariants = cast(dict[str, Any], task_baseline.get("invariants", {}))
    eq_acceptance = equivalence.get("acceptance")
    package_hashes = equivalence.get("package_sha256_by_profile")
    evidence_hashes = equivalence.get("installed_evidence_sha256_by_profile")
    postgres_versions = equivalence.get(
        "postgres_server_version_by_service_profile"
    )
    p2_provenance = equivalence.get("p2_runtime_provenance_by_profile")
    shared_exact = equivalence.get("shared_exact_projection_by_profile")
    installed_order = acceptance_contract.get("installed_package_e2e_order")
    required_order = final_contract.get("required_installed_e2e_order")

    protected_main = (
        event_name == "push"
        and git_ref == "refs/heads/main"
        and expected_revision == checked_out_revision
    )
    acceptance = {
        "release_contract_exact": (
            contract.get("schema") == "TPAA_PRCB_C5_RELEASE_CONTRACT_V1"
            and contract.get("target_product_version") == "1.0.1"
            and contract.get("canonical_baseline") == "CB-1.4.0"
            and contract.get("db_schema_version") == "1.9.0"
            and tuple(cast(list[str], contract.get("mandatory_profiles", [])))
            == MANDATORY_PROFILES
            and package_policy.get("tests_packaged") is False
            and package_policy.get("fixtures_packaged") is False
            and package_policy.get("mutable_latest_fallback") is False
            and package_policy.get("formal_release_claimed") is False
            and package_policy.get("candidate_qualification")
            == "TPAA_1_0_1_CANDIDATE_NOT_QUALIFIED"
        ),
        "task_baseline_exact": (
            task_baseline.get("schema") == "TPAA_PRCB_TASK_BASELINE_V1"
            and task_baseline.get("target_product_version") == "1.0.1"
            and task_baseline.get("canonical_baseline") == "CB-1.4.0"
            and task_baseline.get("db_schema_version") == "1.9.0"
            and task_baseline.get("source_piqb_protected_main_sha")
            == "0ed48a85944699e0bbac1fe76b84c88a319121c1"
            and task_baseline.get("source_piqb_qualification")
            == "PIQB_1_0_QUALIFIED"
        ),
        "acceptance_contract_exact": (
            acceptance_contract.get("schema")
            == "TPAA_PRCB_ACCEPTANCE_CONTRACT_V1"
            and acceptance_contract.get("target_product_version") == "1.0.1"
            and installed_order == required_order
        ),
        "candidate_revision_exact": (
            expected_revision == checked_out_revision
            and equivalence.get("source_revision") == expected_revision
        ),
        "four_profile_logical_equivalence_pass": (
            equivalence.get("schema")
            == "TPAA_PRCB_C5_FOUR_PROFILE_LOGICAL_EQUIVALENCE_V1"
            and equivalence.get("status") == "PASS"
            and equivalence.get("qualification")
            == "TPAA_1_0_1_CANDIDATE_NOT_QUALIFIED"
            and equivalence.get("formal_release_claimed") is False
            and equivalence.get("failed_acceptance") == []
            and tuple(cast(list[str], equivalence.get("mandatory_profiles", [])))
            == MANDATORY_PROFILES
        ),
        "equivalence_acceptance_all_required_true": (
            isinstance(eq_acceptance, dict)
            and all(
                cast(dict[str, Any], eq_acceptance).get(key) is True
                for key in REQUIRED_EQ_ACCEPTANCE
            )
        ),
        "immutable_package_sha256_all_profiles": _exact_profile_sha_map(
            package_hashes
        )
        and len(
            set(cast(dict[str, str], package_hashes).values())
        )
        == 4,
        "installed_evidence_sha256_all_profiles": _exact_profile_sha_map(
            evidence_hashes
        ),
        "service_postgres_versions_recorded": (
            isinstance(postgres_versions, dict)
            and set(cast(dict[str, Any], postgres_versions))
            == set(SERVICE_PROFILES)
            and all(
                isinstance(value, str) and bool(value)
                for value in cast(dict[str, Any], postgres_versions).values()
            )
        ),
        "p2_runtime_provenance_retained": (
            isinstance(p2_provenance, dict)
            and set(cast(dict[str, Any], p2_provenance))
            == set(MANDATORY_PROFILES)
            and isinstance(equivalence.get("p2_identity_interpretation"), str)
            and bool(cast(str, equivalence.get("p2_identity_interpretation")))
        ),
        "shared_exact_projection_retained": (
            isinstance(shared_exact, dict)
            and set(cast(dict[str, Any], shared_exact))
            == set(MANDATORY_PROFILES)
            and len(
                {
                    json.dumps(value, sort_keys=True, separators=(",", ":"))
                    for value in cast(dict[str, Any], shared_exact).values()
                }
            )
            == 1
        ),
        "detached_attestation_required": (
            final_contract.get("detached_attestation_required") is True
        ),
        "protected_main_required": (
            final_contract.get("protected_main_required") is True
        ),
        "required_jobs_exact": (
            required_jobs_success == 14
            and required_jobs_total == 14
            and final_contract.get("required_jobs_success") == 14
            and final_contract.get("required_jobs_total") == 14
        ),
        "run_conclusion_success": run_conclusion == "success",
        "no_m10_p7": invariants.get("no_m10_p7") is True,
        "no_gate_weakening": invariants.get("no_gate_weakening") is True,
        "exact_fourteen_job_topology_retained": (
            invariants.get("exact_fourteen_required_job_topology") is True
        ),
        "production_fixture_dependency_forbidden": (
            invariants.get("production_test_fixture_dependency_forbidden")
            is True
        ),
        "production_inmemory_authority_forbidden": (
            invariants.get("production_inmemory_authority_forbidden") is True
        ),
    }
    failed = sorted(key for key, value in acceptance.items() if value is not True)
    status = "PASS" if not failed else "FAIL"
    decision = (
        "GO"
        if status == "PASS" and protected_main
        else "PENDING_PROTECTED_MAIN"
        if status == "PASS"
        else "NO_GO"
    )
    qualification = (
        "TPAA_1_0_1_QUALIFIED"
        if decision == "GO"
        else "TPAA_1_0_1_CANDIDATE_NOT_QUALIFIED"
        if status == "PASS"
        else "TPAA_1_0_1_NOT_QUALIFIED"
    )
    formal_release_claimed = decision == "GO"

    attestation: dict[str, object] = {
        "schema": "TPAA_PRCB_C5_DETACHED_ATTESTATION_V1",
        "baseline": "PRCB-1.0",
        "product_name": "TPAA",
        "product_version": "1.0.1",
        "canonical_baseline": "CB-1.4.0",
        "db_schema_version": "1.9.0",
        "source_revision": expected_revision,
        "event_name": event_name,
        "git_ref": git_ref,
        "protected_main_exact": protected_main,
        "required_jobs_success": required_jobs_success,
        "required_jobs_total": required_jobs_total,
        "status": status,
        "decision": decision,
        "qualification": qualification,
        "formal_release_claimed": formal_release_claimed,
        "reviewer_schema": "TPAA_PRCB_C5_EXIT_REVIEW_V1",
        "package_sha256_by_profile": package_hashes,
        "installed_evidence_sha256_by_profile": evidence_hashes,
        "four_profile_equivalence_sha256": _sha256_file(logical_equivalence),
        "release_contract_sha256": _sha256_file(RELEASE_CONTRACT),
        "acceptance_contract_sha256": _sha256_file(ACCEPTANCE_CONTRACT),
        "task_baseline_sha256": _sha256_file(TASK_BASELINE),
        "acceptance_sha256": _canonical_sha256(acceptance),
        "failed_acceptance": failed,
    }
    attestation["attestation_payload_sha256"] = _canonical_sha256(attestation)

    review_payload: dict[str, object] = {
        "schema": "TPAA_PRCB_C5_EXIT_REVIEW_V1",
        "baseline": "PRCB-1.0",
        "status": status,
        "decision": decision,
        "qualification": qualification,
        "implementation_complete": status == "PASS",
        "formal_release_claimed": formal_release_claimed,
        "formal_completion_blocked_by_protected_main": (
            status == "PASS" and not protected_main
        ),
        "protected_main_exact": protected_main,
        "event_name": event_name,
        "git_ref": git_ref,
        "source_revision": expected_revision,
        "checked_out_revision": checked_out_revision,
        "run_conclusion": run_conclusion,
        "required_jobs_success": required_jobs_success,
        "required_jobs_total": required_jobs_total,
        "product_version": "1.0.1",
        "canonical_baseline": "CB-1.4.0",
        "db_schema_version": "1.9.0",
        "package_sha256_by_profile": package_hashes,
        "installed_evidence_sha256_by_profile": evidence_hashes,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "detached_attestation_schema": attestation["schema"],
        "detached_attestation_payload_sha256": attestation[
            "attestation_payload_sha256"
        ],
        "scope": {
            "installed_four_profile_chain": status == "PASS",
            "no_m10_p7": True,
            "historical_piqb_rewritten": False,
            "mutable_latest_fallback_permitted": False,
            "formal_release_requires_protected_main": True,
        },
    }
    return review_payload, attestation


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--logical-equivalence", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--checked-out-revision", required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--git-ref", required=True)
    parser.add_argument("--run-conclusion", required=True)
    parser.add_argument("--required-jobs-success", type=int, required=True)
    parser.add_argument("--required-jobs-total", type=int, required=True)
    parser.add_argument("--review-output", type=Path, required=True)
    parser.add_argument("--attestation-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        review_payload, attestation = review(
            logical_equivalence=args.logical_equivalence,
            expected_revision=args.expected_revision,
            checked_out_revision=args.checked_out_revision,
            event_name=args.event_name,
            git_ref=args.git_ref,
            run_conclusion=args.run_conclusion,
            required_jobs_success=args.required_jobs_success,
            required_jobs_total=args.required_jobs_total,
        )
        code = 0 if review_payload["status"] == "PASS" else 2
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        review_payload = {
            "schema": "TPAA_PRCB_C5_EXIT_REVIEW_V1",
            "status": "FAIL",
            "decision": "NO_GO",
            "qualification": "TPAA_1_0_1_NOT_QUALIFIED",
            "formal_release_claimed": False,
            "failed_acceptance": ["review_exception"],
            "error": message,
        }
        attestation = {
            "schema": "TPAA_PRCB_C5_DETACHED_ATTESTATION_V1",
            "status": "FAIL",
            "decision": "NO_GO",
            "qualification": "TPAA_1_0_1_NOT_QUALIFIED",
            "formal_release_claimed": False,
            "failed_acceptance": ["review_exception"],
            "error": message,
        }
        code = 2

    _write_json(args.attestation_output, attestation)
    review_payload["detached_attestation_file_sha256"] = _sha256_file(
        args.attestation_output
    )
    _write_json(args.review_output, review_payload)
    print(
        json.dumps(
            review_payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
