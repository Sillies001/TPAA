#!/usr/bin/env python3
"""Independent ACP-216 DB 1.7.0 authority-adoption gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
CORE = BASELINE / "canonical" / "CORE_LOGICAL_MODEL.json"
LOCK = BASELINE / "BASELINE_LOCK.json"
HISTORICAL_CORE = ROOT / "migrations" / "authority" / "CORE_LOGICAL_MODEL_DB_1_6_0.json"
PROPOSAL = ROOT / "docs" / "proposals" / "ACP-216_EXACT_PERSISTENCE_SCHEMA_PROPOSAL.json"
ADOPTION = ROOT / "docs" / "baseline" / "PIQB-1.0" / "ACP_216_DB_1_7_0_ADOPTION.json"
REVISION = ROOT / "migrations" / "versions" / "0001_acp216_db_1_7_0.py"
MIGRATION = ROOT / "tools" / "storage" / "acp216_migration.py"
README = ROOT / "migrations" / "README.md"
LOADER = ROOT / "src" / "tpaa_canonical" / "loader.py"
BOOTSTRAP = ROOT / "src" / "tpaa_storage" / "bootstrap.py"

SOURCE_MAIN_SHA = "1ae7fccd6b61f570e22b7622c74fe41a4a7fe6c8"
READINESS_SHA = "f960ed520e40d9179a450bdeba10a16c4266c2dd"
READINESS_RUN = 567
SOURCE_CORE_SHA = "cfde6638e6899167267375c899bff2f04a490ce12f32e0005be4e15dda956245"
SOURCE_LOCK_SHA = "9920b59601d8441f883879e813164f33ee5c02db81aa5e1b759e3a1772469e51"
TARGET_CORE_SHA = "dd8461ff572338006455f7b6eac5325900c60640f5d163c3b61c3f5bd5767f74"
TARGET_LOCK_SHA = "a55ccc5f75d128c4dc3c3208064596eeb2dda7ffaf340d87726a22d4b62f93c6"
EXPECTED_RELATIONS = 15
EXPECTED_SOURCE_TABLES = 77
EXPECTED_TARGET_TABLES = 92


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} root must be an object")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _old_table_payloads_preserved(
    current: dict[str, Any],
    historical: dict[str, Any],
) -> bool:
    current_tables = current.get("tables")
    historical_tables = historical.get("tables")
    if not isinstance(current_tables, dict) or not isinstance(historical_tables, dict):
        return False
    for name, old_value in historical_tables.items():
        new_value = current_tables.get(name)
        if not isinstance(old_value, dict) or not isinstance(new_value, dict):
            return False
        old_payload = {key: value for key, value in old_value.items() if key != "schema_version"}
        new_payload = {key: value for key, value in new_value.items() if key != "schema_version"}
        if old_payload != new_payload:
            return False
    return True


def review(
    *,
    postgres_migration: Path,
    expected_revision: str,
    checked_out_revision: str,
    event_name: str,
    git_ref: str,
    run_conclusion: str,
    required_jobs_success: int,
    required_jobs_total: int,
) -> dict[str, object]:
    core = _load(CORE)
    historical = _load(HISTORICAL_CORE)
    lock = _load(LOCK)
    proposal = _load(PROPOSAL)
    adoption = _load(ADOPTION)
    postgres = _load(postgres_migration)

    core_tables = core.get("tables")
    historical_tables = historical.get("tables")
    changes = proposal.get("changes")
    blocker_coverage = proposal.get("blocker_coverage")
    current_authority = proposal.get("current_authority")
    candidate_authority = proposal.get("candidate_authority")
    baseline = lock.get("baseline")
    artifacts = lock.get("artifacts")
    target_relations = adoption.get("additive_relations")

    relation_names = (
        [str(row.get("relation")) for row in changes if isinstance(row, dict)]
        if isinstance(changes, list)
        else []
    )
    core_entry = None
    if isinstance(artifacts, list):
        core_entry = next(
            (
                row
                for row in artifacts
                if isinstance(row, dict)
                and row.get("file") == "CORE_LOGICAL_MODEL.json"
            ),
            None,
        )

    checks = {
        "exact_revision": (
            bool(expected_revision)
            and expected_revision == checked_out_revision
            and postgres.get("source_revision") == expected_revision
        ),
        "hosted_ci_exact_14": (
            run_conclusion == "success"
            and required_jobs_success == 14
            and required_jobs_total == 14
        ),
        "source_authority_exact_1_6": (
            historical.get("db_schema_version") == "1.6.0"
            and isinstance(historical_tables, dict)
            and len(historical_tables) == EXPECTED_SOURCE_TABLES
            and _sha(HISTORICAL_CORE) == SOURCE_CORE_SHA
        ),
        "target_authority_exact_1_7": (
            core.get("db_schema_version") == "1.7.0"
            and isinstance(core_tables, dict)
            and len(core_tables) == EXPECTED_TARGET_TABLES
            and _sha(CORE) == TARGET_CORE_SHA
            and all(
                isinstance(value, dict) and value.get("schema_version") == "1.7.0"
                for value in core_tables.values()
            )
        ),
        "historical_table_semantics_preserved": _old_table_payloads_preserved(
            core,
            historical,
        ),
        "proposal_remains_pre_adoption_design_record": (
            proposal.get("proposal_id") == "ACP-216"
            and proposal.get("status") == "PROPOSED_NOT_ADOPTED"
            and isinstance(current_authority, dict)
            and current_authority.get("db_schema_version") == "1.6.0"
            and isinstance(candidate_authority, dict)
            and candidate_authority.get("db_schema_version") == "1.7.0"
            and candidate_authority.get("adoption_state") == "NONE"
        ),
        "exact_additive_relation_inventory": (
            len(relation_names) == EXPECTED_RELATIONS
            and relation_names == target_relations
            and isinstance(core_tables, dict)
            and isinstance(historical_tables, dict)
            and set(core_tables) - set(historical_tables) == set(relation_names)
        ),
        "blocker_coverage_exact_13": (
            isinstance(blocker_coverage, dict)
            and isinstance(blocker_coverage.get("expected"), list)
            and len(blocker_coverage["expected"]) == 13
            and blocker_coverage.get("uncovered") == []
        ),
        "baseline_lock_rebased_to_1_7": (
            isinstance(baseline, dict)
            and baseline.get("db_schema") == "1.7.0"
            and baseline.get("rebaseline") == "R5.2_ACP_216_DB_1_7_0_AUTHORITY_ADOPTION"
            and isinstance(baseline.get("lock_lineage_sha256"), list)
            and SOURCE_LOCK_SHA in baseline["lock_lineage_sha256"]
            and _sha(LOCK) == TARGET_LOCK_SHA
            and isinstance(core_entry, dict)
            and core_entry.get("sha256") == TARGET_CORE_SHA
            and core_entry.get("bytes") == len(CORE.read_bytes())
        ),
        "adoption_manifest_exact": (
            adoption.get("schema") == "TPAA_ACP216_DB_1_7_0_ADOPTION_V1"
            and adoption.get("source_protected_main_sha") == SOURCE_MAIN_SHA
            and adoption.get("readiness_candidate_sha") == READINESS_SHA
            and adoption.get("readiness_run_number") == READINESS_RUN
            and adoption.get("source_core_sha256") == SOURCE_CORE_SHA
            and adoption.get("target_core_sha256") == TARGET_CORE_SHA
            and adoption.get("source_baseline_lock_sha256") == SOURCE_LOCK_SHA
            and adoption.get("target_baseline_lock_sha256") == TARGET_LOCK_SHA
            and adoption.get("source_db_schema_version") == "1.6.0"
            and adoption.get("target_db_schema_version") == "1.7.0"
            and adoption.get("shadow_schema_created") is False
            and adoption.get("formal_adoption_claimed") is False
        ),
        "migration_authority_exact": (
            REVISION.is_file()
            and MIGRATION.is_file()
            and 'revision = "0001_acp216_db_1_7_0"' in REVISION.read_text(encoding="utf-8")
            and "DOWNGRADE_BLOCKED_NONEMPTY_RELATION"
            in MIGRATION.read_text(encoding="utf-8")
            and "current governed DB schema target is **1.7.0**"
            in README.read_text(encoding="utf-8")
        ),
        "loader_and_bootstrap_trust_target": (
            TARGET_LOCK_SHA in LOADER.read_text(encoding="utf-8")
            and 'EXPECTED_DB_SCHEMA_VERSION = "1.7.0"'
            in BOOTSTRAP.read_text(encoding="utf-8")
            and "_canonical_table_constraints"
            in BOOTSTRAP.read_text(encoding="utf-8")
        ),
        "postgres_real_transition_pass": (
            postgres.get("schema") == "TPAA_ACP216_POSTGRES_MIGRATION_V1"
            and postgres.get("status") == "PASS"
            and postgres.get("source_db_schema_version") == "1.6.0"
            and postgres.get("target_db_schema_version") == "1.7.0"
            and postgres.get("failed_acceptance") == []
            and isinstance(postgres.get("acceptance"), dict)
            and all(value is True for value in postgres["acceptance"].values())
        ),
        "no_shadow_schema": adoption.get("shadow_schema_created") is False,
    }
    failed = sorted(name for name, passed in checks.items() if passed is not True)
    implementation_ready = not failed
    protected_main = event_name == "push" and git_ref == "refs/heads/main"
    formal_adopted = implementation_ready and protected_main
    decision = (
        "GO"
        if formal_adopted
        else "PENDING_PROTECTED_MAIN"
        if implementation_ready
        else "NO_GO"
    )
    qualification = (
        "ACP216_DB_1_7_0_ADOPTED"
        if formal_adopted
        else "ACP216_DB_1_7_0_CANDIDATE"
        if implementation_ready
        else "ACP216_DB_1_7_0_NOT_QUALIFIED"
    )
    return {
        "schema": "TPAA_ACP216_AUTHORITY_ADOPTION_REVIEW_V1",
        "proposal_id": "ACP-216",
        "status": "PASS" if implementation_ready else "FAIL",
        "decision": decision,
        "qualification": qualification,
        "source_revision": expected_revision,
        "event_name": event_name,
        "git_ref": git_ref,
        "required_jobs_success": required_jobs_success,
        "required_jobs_total": required_jobs_total,
        "implementation_ready": implementation_ready,
        "formal_adopted": formal_adopted,
        "protected_main": protected_main,
        "failed_acceptance": failed,
        "acceptance": checks,
        "scope": {
            "source_db_schema_version": "1.6.0",
            "target_db_schema_version": "1.7.0",
            "new_relations": EXPECTED_RELATIONS,
            "shadow_schema_created": False,
            "b2_unblocked_by_candidate_pr": False,
            "b3_activated": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--postgres-migration", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--checked-out-revision", required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--git-ref", required=True)
    parser.add_argument("--run-conclusion", required=True)
    parser.add_argument("--required-jobs-success", type=int, required=True)
    parser.add_argument("--required-jobs-total", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = review(
            postgres_migration=args.postgres_migration,
            expected_revision=args.expected_revision,
            checked_out_revision=args.checked_out_revision,
            event_name=args.event_name,
            git_ref=args.git_ref,
            run_conclusion=args.run_conclusion,
            required_jobs_success=args.required_jobs_success,
            required_jobs_total=args.required_jobs_total,
        )
    except Exception as exc:
        result = {
            "schema": "TPAA_ACP216_AUTHORITY_ADOPTION_REVIEW_V1",
            "proposal_id": "ACP-216",
            "status": "FAIL",
            "decision": "NO_GO",
            "qualification": "ACP216_DB_1_7_0_NOT_QUALIFIED",
            "source_revision": args.expected_revision,
            "event_name": args.event_name,
            "git_ref": args.git_ref,
            "implementation_ready": False,
            "formal_adopted": False,
            "protected_main": (
                args.event_name == "push" and args.git_ref == "refs/heads/main"
            ),
            "failed_acceptance": ["reviewer_exception"],
            "error": f"{type(exc).__name__}: {exc}",
        }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
