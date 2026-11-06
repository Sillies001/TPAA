#!/usr/bin/env python3
"""Verify cross-file Core/DB/DTO authority consistency without inventing approval.

Exit codes:
  0 - PASS, or report-only output was requested;
  2 - hard integrity/current-physical-authority failure;
  3 - structurally valid authority with unresolved historical compatibility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

REPORT_SCHEMA = "TPAA_AUTHORITY_CONSISTENCY_V1"
EXIT_PASS = 0
EXIT_FAIL = 2
EXIT_REVIEW_REQUIRED = 3


class AuthorityConsistencyError(RuntimeError):
    """The authority root cannot be inspected safely."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AuthorityConsistencyError(f"missing JSON file: {path}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuthorityConsistencyError(f"invalid JSON file: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AuthorityConsistencyError(f"expected JSON object: {path}")
    return value


def _version(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AuthorityConsistencyError(f"missing or invalid {field}")
    return value.strip()


def _locked_entries(lock: Mapping[str, Any]) -> list[dict[str, Any]]:
    value = lock.get("artifacts")
    if not isinstance(value, list):
        raise AuthorityConsistencyError("BASELINE_LOCK artifacts must be an array")
    entries: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, dict):
            raise AuthorityConsistencyError("invalid BASELINE_LOCK artifact entry")
        name = raw.get("file")
        sha = raw.get("sha256")
        size = raw.get("bytes")
        if (
            not isinstance(name, str)
            or Path(name).name != name
            or not isinstance(sha, str)
            or len(sha) != 64
            or not isinstance(size, int)
            or size < 0
        ):
            raise AuthorityConsistencyError(f"invalid BASELINE_LOCK artifact entry: {raw!r}")
        entries.append(raw)
    names = [str(entry["file"]) for entry in entries]
    if len(names) != len(set(names)):
        raise AuthorityConsistencyError("duplicate BASELINE_LOCK artifact names")
    return entries


def _collect_db_declarations(value: object, path: str = "$") -> list[dict[str, str]]:
    declarations: list[dict[str, str]] = []
    if isinstance(value, Mapping):
        for raw_key in sorted(value, key=str):
            key = str(raw_key)
            child = value[raw_key]
            child_path = f"{path}.{key}"
            if key in {"db_schema", "db_schema_version", "db_schema_target"} and isinstance(
                child, str
            ):
                declarations.append({"path": child_path, "value": child})
            declarations.extend(_collect_db_declarations(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            declarations.extend(_collect_db_declarations(child, f"{path}[{index}]"))
    return declarations


def _count_named_declarations(value: object, names: set[str]) -> int:
    if isinstance(value, Mapping):
        return sum(
            (1 if str(key).lower() in names else 0) + _count_named_declarations(child, names)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return sum(_count_named_declarations(child, names) for child in value)
    return 0


def verify(authority_root: Path) -> dict[str, Any]:
    root = authority_root.resolve()
    lock_path = root / "BASELINE_LOCK.json"
    canonical = root / "canonical"
    if not canonical.is_dir():
        raise AuthorityConsistencyError(f"missing canonical directory: {canonical}")
    lock = _load_object(lock_path)
    baseline = lock.get("baseline")
    if not isinstance(baseline, Mapping):
        raise AuthorityConsistencyError("BASELINE_LOCK baseline must be an object")
    core_version = _version(baseline.get("core"), field="baseline.core")
    db_version = _version(baseline.get("db_schema"), field="baseline.db_schema")
    rebaseline = _version(baseline.get("rebaseline"), field="baseline.rebaseline")
    entries = _locked_entries(lock)

    hard_failures: list[dict[str, Any]] = []
    review_findings: list[dict[str, Any]] = []
    locked_names = {str(entry["file"]) for entry in entries}
    actual_names = {path.name for path in canonical.glob("*.json") if path.is_file()}
    for name in sorted(locked_names - actual_names):
        hard_failures.append({"code": "LOCKED_ARTIFACT_MISSING", "file": name})
    for name in sorted(actual_names - locked_names):
        hard_failures.append({"code": "UNCONTROLLED_CANONICAL_ARTIFACT", "file": name})

    declarations: list[dict[str, str]] = []
    artifact_core_mismatches: list[dict[str, str]] = []
    for entry in entries:
        name = str(entry["file"])
        path = canonical / name
        if not path.is_file():
            continue
        actual_hash = _sha256(path)
        actual_size = path.stat().st_size
        if actual_hash != entry["sha256"] or actual_size != entry["bytes"]:
            hard_failures.append(
                {
                    "code": "LOCKED_ARTIFACT_DRIFT",
                    "file": name,
                    "expected_sha256": entry["sha256"],
                    "actual_sha256": actual_hash,
                    "expected_bytes": entry["bytes"],
                    "actual_bytes": actual_size,
                }
            )
        payload = _load_object(path)
        artifact_core = payload.get("core_baseline")
        if isinstance(artifact_core, str) and artifact_core != core_version:
            artifact_core_mismatches.append(
                {
                    "file": name,
                    "expected": core_version,
                    "actual": artifact_core,
                }
            )
        for declaration in _collect_db_declarations(payload):
            declarations.append({"file": name, **declaration})

    core_model_path = canonical / "CORE_LOGICAL_MODEL.json"
    core_model = _load_object(core_model_path)
    if core_model.get("core_baseline") != core_version:
        hard_failures.append(
            {
                "code": "CURRENT_CORE_BASELINE_MISMATCH",
                "file": core_model_path.name,
                "expected": core_version,
                "actual": core_model.get("core_baseline"),
            }
        )
    if core_model.get("db_schema_version") != db_version:
        hard_failures.append(
            {
                "code": "CURRENT_DB_SCHEMA_MISMATCH",
                "file": core_model_path.name,
                "expected": db_version,
                "actual": core_model.get("db_schema_version"),
            }
        )
    tables = core_model.get("tables")
    if not isinstance(tables, Mapping):
        hard_failures.append({"code": "CORE_TABLES_INVALID", "file": core_model_path.name})
    else:
        for table_name in sorted(tables, key=str):
            table = tables[table_name]
            actual = table.get("schema_version") if isinstance(table, Mapping) else None
            if actual != db_version:
                hard_failures.append(
                    {
                        "code": "CURRENT_TABLE_SCHEMA_MISMATCH",
                        "file": core_model_path.name,
                        "table": str(table_name),
                        "expected": db_version,
                        "actual": actual,
                    }
                )

    dto = _load_object(canonical / "CROSS_LAYER_DTO_CONTRACTS.json")
    if dto.get("core_baseline") != core_version:
        hard_failures.append(
            {
                "code": "DTO_CORE_BASELINE_MISMATCH",
                "file": "CROSS_LAYER_DTO_CONTRACTS.json",
                "expected": core_version,
                "actual": dto.get("core_baseline"),
            }
        )

    import_provenance_path = root / "IMPORT_PROVENANCE.json"
    if import_provenance_path.is_file():
        import_provenance = _load_object(import_provenance_path)
        for declaration in _collect_db_declarations(import_provenance):
            declarations.append({"file": "IMPORT_PROVENANCE.json", **declaration})

    legacy_declarations = [item for item in declarations if item["value"] != db_version]
    compatibility_path = canonical / "SCHEMA_COMPATIBILITY_AUTHORITY.json"
    approved_compatibility: set[tuple[str, str, str]] = set()
    approved_core_inheritance: set[tuple[str, str, str]] = set()
    if compatibility_path.is_file():
        compatibility = _load_object(compatibility_path)
        if compatibility.get("core_baseline") != core_version:
            hard_failures.append(
                {
                    "code": "COMPATIBILITY_CORE_BASELINE_MISMATCH",
                    "expected": core_version,
                    "actual": compatibility.get("core_baseline"),
                }
            )
        if compatibility.get("current_db_schema") != db_version:
            hard_failures.append(
                {
                    "code": "COMPATIBILITY_CURRENT_DB_MISMATCH",
                    "expected": db_version,
                    "actual": compatibility.get("current_db_schema"),
                }
            )
        if compatibility.get("approval_status") != "APPROVED":
            hard_failures.append({"code": "COMPATIBILITY_AUTHORITY_NOT_APPROVED"})
        compatibility_entries = compatibility.get("entries")
        if not isinstance(compatibility_entries, list):
            hard_failures.append({"code": "COMPATIBILITY_ENTRIES_INVALID"})
        else:
            for entry in compatibility_entries:
                if not isinstance(entry, Mapping):
                    hard_failures.append({"code": "COMPATIBILITY_ENTRY_INVALID"})
                    continue
                file_name = entry.get("file")
                declaration_path = entry.get("path")
                value = entry.get("value")
                versions = entry.get("compatible_schema_versions")
                if (
                    not isinstance(file_name, str)
                    or not isinstance(declaration_path, str)
                    or not isinstance(value, str)
                    or entry.get("introduced_in_schema") != value
                    or not isinstance(versions, list)
                    or not all(isinstance(version, str) for version in versions)
                    or db_version not in versions
                    or entry.get("approval_status") != "APPROVED"
                ):
                    hard_failures.append(
                        {"code": "COMPATIBILITY_ENTRY_INVALID", "entry": dict(entry)}
                    )
                    continue
                identity = (file_name, declaration_path, value)
                if identity in approved_compatibility:
                    hard_failures.append(
                        {
                            "code": "COMPATIBILITY_ENTRY_DUPLICATE",
                            "file": file_name,
                            "path": declaration_path,
                            "value": value,
                        }
                    )
                approved_compatibility.add(identity)
        core_inheritance = compatibility.get("core_inheritance")
        if not isinstance(core_inheritance, list):
            hard_failures.append({"code": "CORE_INHERITANCE_INVALID"})
        else:
            for entry in core_inheritance:
                if not isinstance(entry, Mapping):
                    hard_failures.append({"code": "CORE_INHERITANCE_ENTRY_INVALID"})
                    continue
                file_name = entry.get("file")
                declared_core = entry.get("declared_core_baseline")
                compatible_core = entry.get("compatible_core_baseline")
                if (
                    not isinstance(file_name, str)
                    or not isinstance(declared_core, str)
                    or compatible_core != core_version
                    or entry.get("approval_status") != "APPROVED"
                ):
                    hard_failures.append(
                        {"code": "CORE_INHERITANCE_ENTRY_INVALID", "entry": dict(entry)}
                    )
                    continue
                identity = (file_name, declared_core, str(compatible_core))
                if identity in approved_core_inheritance:
                    hard_failures.append(
                        {
                            "code": "CORE_INHERITANCE_ENTRY_DUPLICATE",
                            "file": file_name,
                        }
                    )
                approved_core_inheritance.add(identity)
    unresolved_legacy = [
        item
        for item in legacy_declarations
        if (item["file"], item["path"], item["value"]) not in approved_compatibility
    ]
    actual_legacy = {(item["file"], item["path"], item["value"]) for item in legacy_declarations}
    for file_name, declaration_path, value in sorted(approved_compatibility - actual_legacy):
        hard_failures.append(
            {
                "code": "COMPATIBILITY_ENTRY_WITHOUT_DECLARATION",
                "file": file_name,
                "path": declaration_path,
                "value": value,
            }
        )
    if unresolved_legacy:
        review_findings.append(
            {
                "code": "HISTORICAL_DB_DECLARATIONS_REQUIRE_COMPATIBILITY_AUTHORITY",
                "current_db_schema": db_version,
                "declaration_count": len(unresolved_legacy),
                "declarations": unresolved_legacy,
                "required_resolution": (
                    "Approve explicit introduced-in/compatible-schema metadata or publish a "
                    "successor rebaseline; do not rewrite historical semantic authority in place."
                ),
            }
        )

    actual_core_inheritance = {
        (item["file"], item["actual"], item["expected"])
        for item in artifact_core_mismatches
    }
    for item in artifact_core_mismatches:
        identity = (item["file"], item["actual"], item["expected"])
        if identity not in approved_core_inheritance:
            hard_failures.append({"code": "CORE_BASELINE_MISMATCH", **item})
    for file_name, declared_core, compatible_core in sorted(
        approved_core_inheritance - actual_core_inheritance
    ):
        hard_failures.append(
            {
                "code": "CORE_INHERITANCE_WITHOUT_MISMATCH",
                "file": file_name,
                "declared_core_baseline": declared_core,
                "compatible_core_baseline": compatible_core,
            }
        )

    index_path = canonical / "PHYSICAL_INDEX_AUTHORITY.json"
    if not index_path.is_file():
        review_findings.append(
            {
                "code": "INDEX_AUTHORITY_NOT_DECLARED",
                "required_resolution": (
                    "Declare governed physical/logical indexes in the successor Core authority "
                    "or approve an explicit not-applicable rationale."
                ),
            }
        )
    else:
        index_authority = _load_object(index_path)
        indexes = index_authority.get("indexes")
        if (
            index_authority.get("core_baseline") != core_version
            or index_authority.get("db_schema_version") != db_version
            or index_authority.get("approval_status") != "APPROVED"
            or not isinstance(indexes, list)
            or not indexes
        ):
            hard_failures.append({"code": "INDEX_AUTHORITY_INVALID"})
        else:
            table_names = set(tables) if isinstance(tables, Mapping) else set()
            index_identities: set[str] = set()
            for entry in indexes:
                if not isinstance(entry, Mapping):
                    hard_failures.append({"code": "INDEX_AUTHORITY_ENTRY_INVALID"})
                    continue
                index_identity = entry.get("index_id")
                table_name = entry.get("table")
                if (
                    not isinstance(index_identity, str)
                    or index_identity in index_identities
                    or table_name not in table_names
                    or entry.get("kind") not in {"PRIMARY_KEY", "UNIQUE"}
                ):
                    hard_failures.append(
                        {"code": "INDEX_AUTHORITY_ENTRY_INVALID", "entry": dict(entry)}
                    )
                else:
                    index_identities.add(index_identity)

    route_path = canonical / "API_ROUTE_AUTHORITY.json"
    if not route_path.is_file():
        review_findings.append(
            {
                "code": "API_ROUTE_AUTHORITY_NOT_DECLARED",
                "required_resolution": (
                    "Bind governed API routes/endpoints to DTO contracts in the successor "
                    "authority or approve an explicit not-applicable rationale."
                ),
            }
        )
    else:
        route_authority = _load_object(route_path)
        routes = route_authority.get("routes")
        if (
            route_authority.get("core_baseline") != core_version
            or route_authority.get("approval_status") != "APPROVED"
            or not isinstance(routes, list)
            or not routes
        ):
            hard_failures.append({"code": "API_ROUTE_AUTHORITY_INVALID"})
        else:
            route_identities: set[tuple[str, str, str]] = set()
            for entry in routes:
                if not isinstance(entry, Mapping):
                    hard_failures.append({"code": "API_ROUTE_AUTHORITY_ENTRY_INVALID"})
                    continue
                method = entry.get("method")
                route = entry.get("path")
                module = entry.get("module")
                identity = (str(method), str(route), str(module))
                if (
                    method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}
                    or not isinstance(route, str)
                    or not route.startswith("/")
                    or not isinstance(module, str)
                    or identity in route_identities
                    or entry.get("dto_authority") != "CROSS_LAYER_DTO_CONTRACTS"
                ):
                    hard_failures.append(
                        {"code": "API_ROUTE_AUTHORITY_ENTRY_INVALID", "entry": dict(entry)}
                    )
                else:
                    route_identities.add(identity)

    decision_approved = False
    decision_path = canonical / "W0_BASELINE_AUTHORITY_DECISION.json"
    if not decision_path.is_file():
        review_findings.append(
            {
                "code": "BASELINE_AUTHORITY_DECISION_NOT_DECLARED",
                "required_resolution": "Add an approved successor version and lineage decision.",
            }
        )
    else:
        decision = _load_object(decision_path)
        version_tuple = decision.get("version_tuple")
        decision_approved = bool(
            decision.get("approval_status") == "APPROVED"
            and isinstance(version_tuple, Mapping)
            and version_tuple.get("core") == core_version
            and version_tuple.get("db_schema") == db_version
        )
        if not decision_approved:
            hard_failures.append({"code": "BASELINE_AUTHORITY_DECISION_INVALID"})

    lineage = baseline.get("lock_lineage_sha256")
    if not isinstance(lineage, list) or not lineage:
        review_findings.append(
            {
                "code": "LOCK_LINEAGE_NOT_EXPLICIT",
                "required_resolution": "Bind predecessor lock hashes in the successor baseline.",
            }
        )
    elif any(not isinstance(value, str) or len(value) != 64 for value in lineage):
        hard_failures.append({"code": "LOCK_LINEAGE_INVALID"})
    elif len(lineage) != len(set(lineage)):
        hard_failures.append({"code": "LOCK_LINEAGE_DUPLICATE"})

    if hard_failures:
        status = "FAIL"
    elif review_findings:
        status = "REVIEW_REQUIRED"
    else:
        status = "PASS"
    return {
        "schema": REPORT_SCHEMA,
        "status": status,
        "adoption_state": (
            "APPROVED_BY_AUTHORITY_DECISION" if decision_approved else "NOT_ADOPTED_BY_THIS_CHECK"
        ),
        "baseline": {
            "core": core_version,
            "db_schema": db_version,
            "rebaseline": rebaseline,
            "baseline_lock_sha256": _sha256(lock_path),
            "controlled_artifact_count": len(entries),
        },
        "hard_failures": hard_failures,
        "review_findings": review_findings,
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Always return 0 while preserving FAIL/REVIEW_REQUIRED in the payload.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        report = verify(args.authority_root)
    except AuthorityConsistencyError as exc:
        print(f"AUTHORITY_CONSISTENCY_FAIL {exc}", file=sys.stderr)
        return EXIT_FAIL
    if args.output is not None:
        _write_json(args.output, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        baseline = report["baseline"]
        print(
            f"AUTHORITY_CONSISTENCY_{report['status']} "
            f"core={baseline['core']} db={baseline['db_schema']} "
            f"controlled={baseline['controlled_artifact_count']}"
        )
        for finding in report["hard_failures"]:
            print(f"FAIL {finding['code']} {json.dumps(finding, sort_keys=True)}")
        for finding in report["review_findings"]:
            print(f"REVIEW {finding['code']} count={finding.get('declaration_count', 1)}")
    if args.report_only:
        return EXIT_PASS
    if report["status"] == "FAIL":
        return EXIT_FAIL
    if report["status"] == "REVIEW_REQUIRED":
        return EXIT_REVIEW_REQUIRED
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main())
