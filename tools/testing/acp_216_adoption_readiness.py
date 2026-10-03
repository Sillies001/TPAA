#!/usr/bin/env python3
"""Independent ACP-216 adoption-readiness review; never mutates authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
PROPOSAL = ROOT / "docs" / "proposals" / "ACP-216_EXACT_PERSISTENCE_SCHEMA_PROPOSAL.json"
FIT = ROOT / "docs" / "baseline" / "PIQB-1.0" / "B2_SCHEMA_PERSISTENCE_FIT.json"
CORE = ROOT / "baseline" / "CB-1.4.0" / "canonical" / "CORE_LOGICAL_MODEL.json"
LOCK = ROOT / "baseline" / "CB-1.4.0" / "BASELINE_LOCK.json"
MIGRATIONS_README = ROOT / "migrations" / "README.md"

EXPECTED_CHANGE_COUNT = 15
EXPECTED_BLOCKER_COUNT = 13
REFERENCE = re.compile(r"^(?P<relation>[a-z0-9_]+\.[a-z0-9_]+)\((?P<column>[a-z0-9_]+)\)$")


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root must be object")
    return cast(dict[str, Any], value)


def _current_columns(core: dict[str, Any]) -> dict[str, set[str]]:
    tables = core.get("tables")
    if not isinstance(tables, dict):
        return {}
    result: dict[str, set[str]] = {}
    for relation, table in tables.items():
        if not isinstance(relation, str) or not isinstance(table, dict):
            continue
        fields = table.get("fields")
        if not isinstance(fields, list):
            continue
        result[relation] = {
            field["name"]
            for field in fields
            if isinstance(field, dict) and isinstance(field.get("name"), str)
        }
    return result


def _proposed_columns(changes: list[dict[str, Any]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for change in changes:
        relation = change.get("relation")
        columns = change.get("columns")
        if not isinstance(relation, str) or not isinstance(columns, list):
            continue
        result[relation] = {
            column["name"]
            for column in columns
            if isinstance(column, dict) and isinstance(column.get("name"), str)
        }
    return result


def _relation_shapes_valid(
    changes: list[dict[str, Any]],
    current: dict[str, set[str]],
    proposed: dict[str, set[str]],
) -> bool:
    known = current | proposed
    for change in changes:
        relation = change.get("relation")
        columns = change.get("columns")
        primary_key = change.get("primary_key")
        if (
            change.get("kind") != "ADD_RELATION"
            or not isinstance(relation, str)
            or relation in current
            or not isinstance(columns, list)
            or not isinstance(primary_key, list)
            or not primary_key
        ):
            return False
        names = [
            column.get("name")
            for column in columns
            if isinstance(column, dict)
        ]
        if (
            any(not isinstance(name, str) or not name for name in names)
            or len(names) != len(set(names))
            or not set(primary_key).issubset(set(names))
        ):
            return False
        by_name = {
            column.get("name"): column
            for column in columns
            if isinstance(column, dict) and isinstance(column.get("name"), str)
        }
        if any(by_name[name].get("nullable") is not False for name in primary_key):
            return False
        unique_keys = change.get("unique_keys", [])
        if not isinstance(unique_keys, list):
            return False
        for unique_key in unique_keys:
            if not isinstance(unique_key, list) or not set(unique_key).issubset(set(names)):
                return False
        for column in columns:
            if not isinstance(column, dict):
                return False
            reference = column.get("reference")
            if reference is None:
                continue
            if not isinstance(reference, str):
                return False
            match = REFERENCE.fullmatch(reference)
            if match is None:
                return False
            target_relation = match.group("relation")
            target_column = match.group("column")
            if target_relation not in known or target_column not in known[target_relation]:
                return False
    return True


def review(
    *,
    expected_revision: str,
    checked_out_revision: str,
    run_conclusion: str,
    required_jobs_success: int,
    required_jobs_total: int,
) -> dict[str, object]:
    proposal = _json(PROPOSAL)
    fit = _json(FIT)
    core = _json(CORE)
    lock = _json(LOCK)
    migrations = MIGRATIONS_README.read_text(encoding="utf-8")
    migrations_plain = migrations.replace("**", "")

    changes_raw = proposal.get("changes")
    changes = (
        cast(list[dict[str, Any]], changes_raw)
        if isinstance(changes_raw, list)
        and all(isinstance(item, dict) for item in changes_raw)
        else []
    )
    current = _current_columns(core)
    proposed = _proposed_columns(changes)

    expected_blockers = {
        blocker["field"]
        for family in fit.get("families", [])
        if isinstance(family, dict)
        for blocker in family.get("blockers", [])
        if isinstance(blocker, dict) and isinstance(blocker.get("field"), str)
    }
    covered_blockers = {
        blocker
        for change in changes
        for blocker in change.get("covers_blockers", [])
        if isinstance(blocker, str)
    }

    change_ids = [change.get("change_id") for change in changes]
    relations = [change.get("relation") for change in changes]
    rationales_complete = all(
        isinstance(change.get("duplicate_authority_rationale"), str)
        and bool(change["duplicate_authority_rationale"].strip())
        for change in changes
    )
    coverage_subset = all(
        set(
            blocker
            for blocker in change.get("covers_blockers", [])
            if isinstance(blocker, str)
        ).issubset(expected_blockers)
        for change in changes
    )

    lock_artifacts_raw = lock.get("artifacts")
    lock_artifacts = lock_artifacts_raw if isinstance(lock_artifacts_raw, list) else []
    core_lock = next(
        (
            item
            for item in lock_artifacts
            if isinstance(item, dict)
            and item.get("file") == "CORE_LOGICAL_MODEL.json"
        ),
        None,
    )
    core_bytes = CORE.read_bytes()
    lock_matches_core = (
        isinstance(core_lock, dict)
        and core_lock.get("sha256") == hashlib.sha256(core_bytes).hexdigest()
        and core_lock.get("bytes") == len(core_bytes)
    )

    candidate = proposal.get("candidate_authority")
    current_authority = proposal.get("current_authority")
    blocker_coverage = proposal.get("blocker_coverage")
    migration_plan = proposal.get("migration_plan")
    adoption_acceptance = proposal.get("adoption_acceptance")

    acceptance = {
        "proposal_identity_exact": (
            proposal.get("schema") == "TPAA_AUTHORITY_CHANGE_PROPOSAL_V1"
            and proposal.get("proposal_id") == "ACP-216"
            and proposal.get("issue") == 216
            and proposal.get("status") == "PROPOSED_NOT_ADOPTED"
        ),
        "current_authority_remains_1_6_0": (
            isinstance(current_authority, dict)
            and current_authority.get("core_baseline") == "CB-1.4.0"
            and current_authority.get("db_schema_version") == "1.6.0"
            and core.get("db_schema_version") == "1.6.0"
            and isinstance(lock.get("baseline"), dict)
            and lock["baseline"].get("db_schema") == "1.6.0"
            and lock_matches_core
        ),
        "candidate_1_7_0_not_adopted": (
            isinstance(candidate, dict)
            and candidate.get("db_schema_version") == "1.7.0"
            and candidate.get("adoption_state") == "NONE"
            and candidate.get("canonical_files_modified_by_this_proposal") is False
            and candidate.get("migration_created_by_this_proposal") is False
        ),
        "change_inventory_exact_15": (
            len(changes) == EXPECTED_CHANGE_COUNT
            and len(change_ids) == len(set(change_ids))
            and len(relations) == len(set(relations))
            and all(isinstance(value, str) and value for value in change_ids)
            and all(isinstance(value, str) and value for value in relations)
        ),
        "additive_relation_shapes_and_references_valid": _relation_shapes_valid(
            changes,
            current,
            proposed,
        ),
        "no_duplicate_authority_relation": (
            set(proposed).isdisjoint(current)
            and rationales_complete
        ),
        "blocker_coverage_exact_13": (
            len(expected_blockers) == EXPECTED_BLOCKER_COUNT
            and covered_blockers == expected_blockers
            and coverage_subset
            and isinstance(blocker_coverage, dict)
            and blocker_coverage.get("uncovered") == []
        ),
        "migration_discipline_ready": (
            isinstance(migration_plan, list)
            and len(migration_plan) >= 7
            and any("1.6.0 -> 1.7.0" in str(item) for item in migration_plan)
            and any("SQLite/PostgreSQL" in str(item) for item in migration_plan)
            and any("Downgrade" in str(item) for item in migration_plan)
            and "first real approved schema transition" in migrations_plain
            and "first governed Alembic revision" in migrations_plain
        ),
        "adoption_acceptance_inventory_present": (
            isinstance(adoption_acceptance, list)
            and len(adoption_acceptance) >= 8
            and any("14 required jobs" in str(item) for item in adoption_acceptance)
            and any("Protected-main" in str(item) for item in adoption_acceptance)
        ),
        "candidate_revision_exact": expected_revision == checked_out_revision,
        "required_jobs_exact": (
            required_jobs_success == 14 and required_jobs_total == 14
        ),
        "run_conclusion_success": run_conclusion == "success",
    }
    failed = sorted(key for key, ok in acceptance.items() if ok is not True)
    status = "PASS" if not failed else "FAIL"
    decision = "READY_FOR_ADOPTION" if status == "PASS" else "NO_GO"
    return {
        "schema": "TPAA_ACP216_ADOPTION_READINESS_REVIEW_V1",
        "proposal_id": "ACP-216",
        "expected_revision": expected_revision,
        "checked_out_revision": checked_out_revision,
        "status": status,
        "decision": decision,
        "failed_acceptance": failed,
        "acceptance": acceptance,
        "current_authority": "CB-1.4.0 / DB 1.6.0",
        "candidate_authority": "DB 1.7.0",
        "authority_changed": False,
        "adoption_performed": False,
        "formal_b2_unblocked": False,
        "qualification": (
            "ACP216_ADOPTION_READY"
            if status == "PASS"
            else "ACP216_NOT_READY"
        ),
        "next_gate": (
            "SEPARATE_AUTHORITY_ADOPTION_CHANGE_REQUIRED"
            if status == "PASS"
            else "REPAIR_PROPOSAL_BEFORE_ADOPTION"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--checked-out-revision", required=True)
    parser.add_argument("--run-conclusion", required=True)
    parser.add_argument("--required-jobs-success", required=True, type=int)
    parser.add_argument("--required-jobs-total", required=True, type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = review(
        expected_revision=args.expected_revision,
        checked_out_revision=args.checked_out_revision,
        run_conclusion=args.run_conclusion,
        required_jobs_success=args.required_jobs_success,
        required_jobs_total=args.required_jobs_total,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
