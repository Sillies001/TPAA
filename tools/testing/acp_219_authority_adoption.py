#!/usr/bin/env python3
"""Independent ACP-219 DB 1.8.0 authority-correction adoption gate."""

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
HISTORICAL_CORE = ROOT / "migrations" / "authority" / "CORE_LOGICAL_MODEL_DB_1_7_0.json"
PROPOSAL = ROOT / "docs" / "proposals" / "ACP-219_M8_ORDERED_TEXT_PERSISTENCE_CORRECTION.json"
ADOPTION = ROOT / "docs" / "baseline" / "PIQB-1.0" / "ACP_219_DB_1_8_0_ADOPTION.json"
REVISION = ROOT / "migrations" / "versions" / "0002_acp219_db_1_8_0.py"
MIGRATION = ROOT / "tools" / "storage" / "acp219_migration.py"
README = ROOT / "migrations" / "README.md"
LOADER = ROOT / "src" / "tpaa_canonical" / "loader.py"
BOOTSTRAP = ROOT / "src" / "tpaa_storage" / "bootstrap.py"

SOURCE_MAIN_SHA = "d5be58189d7fbd81f7fb3e49506eb0a61544db46"
SOURCE_CORE_SHA = "dd8461ff572338006455f7b6eac5325900c60640f5d163c3b61c3f5bd5767f74"
SOURCE_LOCK_SHA = "a55ccc5f75d128c4dc3c3208064596eeb2dda7ffaf340d87726a22d4b62f93c6"
TARGET_CORE_SHA = "cbb15c1e0029be45213e4d7ab57a78fac47d7cc09c4627a9c388fafdadd2d44e"
TARGET_LOCK_SHA = "2f3690d5e74e585a34ae35fdef9fb1e0cccb5504c6983d0c97417bb6a106b389"
EXPECTED_RELATIONS = (
    "assessment.actor_assessment_machine_evidence_ref",
    "assessment.mission_assessment_objective_ref",
)
EXPECTED_SOURCE_TABLES = 92
EXPECTED_TARGET_TABLES = 94


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} root must be object")
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
        old_payload = {k: v for k, v in old_value.items() if k != "schema_version"}
        new_payload = {k: v for k, v in new_value.items() if k != "schema_version"}
        if old_payload != new_payload:
            return False
    return True


def _ordered_text_relations_exact(core: dict[str, Any]) -> bool:
    tables = core.get("tables")
    if not isinstance(tables, dict):
        return False
    p4 = tables.get(EXPECTED_RELATIONS[0])
    p5 = tables.get(EXPECTED_RELATIONS[1])
    if not isinstance(p4, dict) or not isinstance(p5, dict):
        return False

    def projection(value: dict[str, Any]) -> tuple[list[tuple[object, object, object]], list[object]]:
        fields = value.get("fields")
        constraints = value.get("constraints")
        if not isinstance(fields, list) or not isinstance(constraints, list):
            return [], []
        return (
            [
                (field.get("name"), field.get("type"), field.get("nullable"))
                for field in fields
                if isinstance(field, dict)
            ],
            constraints,
        )

    return (
        projection(p4)
        == (
            [
                ("actor_assessment_id", "uuid", False),
                ("ref_order", "integer", False),
                ("evidence_ref", "text", False),
            ],
            [
                "PRIMARY KEY (actor_assessment_id, ref_order)",
                "UNIQUE (actor_assessment_id, evidence_ref)",
            ],
        )
        and projection(p5)
        == (
            [
                ("mission_assessment_id", "uuid", False),
                ("ref_order", "integer", False),
                ("objective_ref", "text", False),
            ],
            [
                "PRIMARY KEY (mission_assessment_id, ref_order)",
                "UNIQUE (mission_assessment_id, objective_ref)",
            ],
        )
    )


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
        "source_authority_exact_1_7": (
            historical.get("db_schema_version") == "1.7.0"
            and isinstance(historical_tables, dict)
            and len(historical_tables) == EXPECTED_SOURCE_TABLES
            and _sha(HISTORICAL_CORE) == SOURCE_CORE_SHA
        ),
        "target_authority_exact_1_8": (
            core.get("db_schema_version") == "1.8.0"
            and isinstance(core_tables, dict)
            and len(core_tables) == EXPECTED_TARGET_TABLES
            and _sha(CORE) == TARGET_CORE_SHA
            and all(
                isinstance(value, dict) and value.get("schema_version") == "1.8.0"
                for value in core_tables.values()
            )
        ),
        "historical_table_semantics_preserved": _old_table_payloads_preserved(
            core,
            historical,
        ),
        "ordered_text_relation_contract_exact": _ordered_text_relations_exact(core),
        "proposal_remains_pre_adoption_design_record": (
            proposal.get("proposal_id") == "ACP-219"
            and proposal.get("status") == "PROPOSED_NOT_ADOPTED"
            and isinstance(current_authority, dict)
            and current_authority.get("db_schema_version") == "1.7.0"
            and isinstance(candidate_authority, dict)
            and candidate_authority.get("db_schema_version") == "1.8.0"
            and candidate_authority.get("adoption_state") == "NONE"
        ),
        "exact_additive_relation_inventory": (
            relation_names == list(EXPECTED_RELATIONS)
            and target_relations == list(EXPECTED_RELATIONS)
            and isinstance(core_tables, dict)
            and isinstance(historical_tables, dict)
            and set(core_tables) - set(historical_tables) == set(EXPECTED_RELATIONS)
        ),
        "blocker_coverage_exact_2": (
            isinstance(blocker_coverage, dict)
            and isinstance(blocker_coverage.get("expected"), list)
            and len(blocker_coverage["expected"]) == 2
            and blocker_coverage.get("uncovered") == []
        ),
        "baseline_lock_rebased_to_1_8": (
            isinstance(baseline, dict)
            and baseline.get("db_schema") == "1.8.0"
            and baseline.get("rebaseline")
            == "R5.3_ACP_219_DB_1_8_0_ORDERED_TEXT_REF_AUTHORITY_CORRECTION"
            and isinstance(baseline.get("lock_lineage_sha256"), list)
            and SOURCE_LOCK_SHA in baseline["lock_lineage_sha256"]
            and _sha(LOCK) == TARGET_LOCK_SHA
            and isinstance(core_entry, dict)
            and core_entry.get("sha256") == TARGET_CORE_SHA
            and core_entry.get("bytes") == len(CORE.read_bytes())
        ),
        "adoption_manifest_exact": (
            adoption.get("schema") == "TPAA_ACP219_DB_1_8_0_ADOPTION_V1"
            and adoption.get("source_protected_main_sha") == SOURCE_MAIN_SHA
            and adoption.get("source_core_sha256") == SOURCE_CORE_SHA
            and adoption.get("target_core_sha256") == TARGET_CORE_SHA
            and adoption.get("source_baseline_lock_sha256") == SOURCE_LOCK_SHA
            and adoption.get("target_baseline_lock_sha256") == TARGET_LOCK_SHA
            and adoption.get("source_db_schema_version") == "1.7.0"
            and adoption.get("target_db_schema_version") == "1.8.0"
            and adoption.get("additive_relation_count") == 2
            and adoption.get("shadow_schema_created") is False
            and adoption.get("formal_adoption_claimed") is False
        ),
        "migration_authority_exact": (
            REVISION.is_file()
            and MIGRATION.is_file()
            and 'revision = "0002_acp219_db_1_8_0"'
            in REVISION.read_text(encoding="utf-8")
            and 'down_revision: str | None = "0001_acp216_db_1_7_0"'
            in REVISION.read_text(encoding="utf-8")
            and "DOWNGRADE_BLOCKED_NONEMPTY_RELATION"
            in MIGRATION.read_text(encoding="utf-8")
            and "current governed DB schema target is **1.8.0**"
            in README.read_text(encoding="utf-8")
        ),
        "loader_and_bootstrap_trust_target": (
            TARGET_LOCK_SHA in LOADER.read_text(encoding="utf-8")
            and 'EXPECTED_DB_SCHEMA_VERSION = "1.8.0"'
            in BOOTSTRAP.read_text(encoding="utf-8")
        ),
        "postgres_real_transition_pass": (
            postgres.get("schema") == "TPAA_ACP219_POSTGRES_MIGRATION_V1"
            and postgres.get("status") == "PASS"
            and postgres.get("source_db_schema_version") == "1.7.0"
            and postgres.get("target_db_schema_version") == "1.8.0"
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
        "ACP219_DB_1_8_0_ADOPTED"
        if formal_adopted
        else "ACP219_DB_1_8_0_CANDIDATE"
        if implementation_ready
        else "ACP219_DB_1_8_0_NOT_QUALIFIED"
    )
    return {
        "schema": "TPAA_ACP219_AUTHORITY_ADOPTION_REVIEW_V1",
        "proposal_id": "ACP-219",
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
            "source_db_schema_version": "1.7.0",
            "target_db_schema_version": "1.8.0",
            "new_relations": 2,
            "ordered_text_identity_preserved": True,
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
            "schema": "TPAA_ACP219_AUTHORITY_ADOPTION_REVIEW_V1",
            "proposal_id": "ACP-219",
            "status": "FAIL",
            "decision": "NO_GO",
            "qualification": "ACP219_DB_1_8_0_NOT_QUALIFIED",
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
