#!/usr/bin/env python3
"""Produce a deterministic, non-adopting diff between two authority roots.

The report is evidence for a rebaseline review.  It never modifies either
authority root and deliberately carries no approval/adoption state.
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

REPORT_SCHEMA = "TPAA_AUTHORITY_DIFF_V1"


class AuthorityDiffError(RuntimeError):
    """The requested authority roots cannot be compared safely."""


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
        raise AuthorityDiffError(f"missing JSON file: {path}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuthorityDiffError(f"invalid JSON file: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AuthorityDiffError(f"expected JSON object: {path}")
    return value


def _resolve_layout(root: Path) -> tuple[Path, Path]:
    resolved = root.resolve()
    if resolved.name == "canonical":
        canonical = resolved
        candidates = (resolved / "BASELINE_LOCK.json", resolved.parent / "BASELINE_LOCK.json")
    else:
        canonical = resolved / "canonical"
        candidates = (resolved / "BASELINE_LOCK.json", canonical / "BASELINE_LOCK.json")
    if not canonical.is_dir():
        raise AuthorityDiffError(f"canonical directory is unavailable: {canonical}")
    lock = next((path for path in candidates if path.is_file()), None)
    if lock is None:
        raise AuthorityDiffError(f"BASELINE_LOCK.json is unavailable under: {resolved}")
    return canonical, lock


def _baseline_metadata(lock: Mapping[str, Any]) -> dict[str, Any]:
    raw = lock.get("baseline")
    if not isinstance(raw, Mapping):
        raise AuthorityDiffError("BASELINE_LOCK.json is missing baseline metadata")
    return {str(key): raw[key] for key in sorted(raw)}


def _controlled_names(lock: Mapping[str, Any]) -> list[str]:
    raw = lock.get("artifacts")
    if not isinstance(raw, list):
        raise AuthorityDiffError("BASELINE_LOCK.json is missing artifacts")
    names: list[str] = []
    for entry in raw:
        if not isinstance(entry, Mapping) or not isinstance(entry.get("file"), str):
            raise AuthorityDiffError("BASELINE_LOCK.json has an invalid artifact entry")
        names.append(str(entry["file"]))
    if len(names) != len(set(names)):
        raise AuthorityDiffError("BASELINE_LOCK.json contains duplicate artifacts")
    return sorted(names)


def _top_level_delta(
    reference: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, list[str]]:
    reference_keys = {str(key) for key in reference}
    candidate_keys = {str(key) for key in candidate}
    shared = reference_keys & candidate_keys
    return {
        "added": sorted(candidate_keys - reference_keys),
        "removed": sorted(reference_keys - candidate_keys),
        "changed": sorted(key for key in shared if reference[key] != candidate[key]),
    }


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


def _named_object_map(value: object, *, key: str, context: str) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        raise AuthorityDiffError(f"{context} must be an array")
    result: dict[str, dict[str, Any]] = {}
    for item in value:
        if not isinstance(item, dict) or not isinstance(item.get(key), str):
            raise AuthorityDiffError(f"{context} contains an invalid {key!r} entry")
        name = str(item[key])
        if name in result:
            raise AuthorityDiffError(f"{context} contains duplicate {key}: {name}")
        result[name] = item
    return result


def _object_map_delta(
    reference: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    include_values: bool = False,
) -> dict[str, Any]:
    reference_names = set(reference)
    candidate_names = set(candidate)
    modified_names = sorted(
        name for name in reference_names & candidate_names if reference[name] != candidate[name]
    )
    modified: list[dict[str, Any]] = []
    for name in modified_names:
        item = {
            "name": name,
            "changed_keys": _top_level_delta(reference[name], candidate[name]),
        }
        if include_values:
            item["reference"] = reference[name]
            item["candidate"] = candidate[name]
        modified.append(item)
    return {
        "summary": {
            "added": len(candidate_names - reference_names),
            "removed": len(reference_names - candidate_names),
            "modified": len(modified_names),
            "unchanged": len(reference_names & candidate_names) - len(modified_names),
        },
        "added": sorted(candidate_names - reference_names),
        "removed": sorted(reference_names - candidate_names),
        "modified": modified,
    }


def _table_semantic_delta(
    reference: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, Any]:
    reference_tables = reference.get("tables")
    candidate_tables = candidate.get("tables")
    if not isinstance(reference_tables, Mapping) or not isinstance(candidate_tables, Mapping):
        raise AuthorityDiffError("CORE_LOGICAL_MODEL tables must be objects")
    reference_table_map = {str(name): value for name, value in reference_tables.items()}
    candidate_table_map = {str(name): value for name, value in candidate_tables.items()}
    if not all(isinstance(value, dict) for value in reference_table_map.values()):
        raise AuthorityDiffError("reference CORE_LOGICAL_MODEL has invalid table entries")
    if not all(isinstance(value, dict) for value in candidate_table_map.values()):
        raise AuthorityDiffError("candidate CORE_LOGICAL_MODEL has invalid table entries")

    table_delta = _object_map_delta(reference_table_map, candidate_table_map)
    details: list[dict[str, Any]] = []
    for name in sorted(set(reference_table_map) & set(candidate_table_map)):
        reference_table = reference_table_map[name]
        candidate_table = candidate_table_map[name]
        if reference_table == candidate_table:
            continue
        reference_fields = _named_object_map(
            reference_table.get("fields"),
            key="name",
            context=f"reference table {name} fields",
        )
        candidate_fields = _named_object_map(
            candidate_table.get("fields"),
            key="name",
            context=f"candidate table {name} fields",
        )
        reference_metadata = {
            key: value for key, value in reference_table.items() if key != "fields"
        }
        candidate_metadata = {
            key: value for key, value in candidate_table.items() if key != "fields"
        }
        details.append(
            {
                "table": name,
                "metadata": _top_level_delta(reference_metadata, candidate_metadata),
                "fields": _object_map_delta(
                    reference_fields, candidate_fields, include_values=True
                ),
            }
        )

    def check_fields(tables: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
        checks: dict[str, dict[str, Any]] = {}
        for table_name in sorted(tables):
            table = tables[table_name]
            fields = _named_object_map(
                table.get("fields"), key="name", context=f"table {table_name} fields"
            )
            for field_name, field in fields.items():
                sql = field.get("sql")
                if isinstance(sql, str) and "CHECK" in sql.upper():
                    checks[f"{table_name}.{field_name}"] = field
        return checks

    index_keys = {"index", "indexes", "indices"}

    def count_index_declarations(value: object) -> int:
        if isinstance(value, Mapping):
            return sum(
                (1 if str(key).lower() in index_keys else 0) + count_index_declarations(child)
                for key, child in value.items()
            )
        if isinstance(value, list):
            return sum(count_index_declarations(child) for child in value)
        return 0

    reference_index_count = count_index_declarations(reference)
    candidate_index_count = count_index_declarations(candidate)
    return {
        "tables": table_delta,
        "added_table_definitions": {
            name: candidate_table_map[name] for name in table_delta["added"]
        },
        "removed_table_definitions": {
            name: reference_table_map[name] for name in table_delta["removed"]
        },
        "modified_table_details": details,
        "enum_and_check_constraints": _object_map_delta(
            check_fields(reference_table_map),
            check_fields(candidate_table_map),
            include_values=True,
        ),
        "indexes": {
            "reference_declaration_count": reference_index_count,
            "candidate_declaration_count": candidate_index_count,
            "status": (
                "EXPLICITLY_COMPARED"
                if reference_index_count or candidate_index_count
                else "NOT_DECLARED_IN_COMPARED_CORE_AUTHORITY"
            ),
        },
    }


def _dto_api_semantic_delta(
    reference: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, Any]:
    reference_contracts = reference.get("contracts")
    candidate_contracts = candidate.get("contracts")
    if not isinstance(reference_contracts, Mapping) or not isinstance(candidate_contracts, Mapping):
        raise AuthorityDiffError("CROSS_LAYER_DTO_CONTRACTS contracts must be objects")
    reference_contract_map = {str(name): value for name, value in reference_contracts.items()}
    candidate_contract_map = {str(name): value for name, value in candidate_contracts.items()}
    if not all(isinstance(value, dict) for value in reference_contract_map.values()):
        raise AuthorityDiffError("reference DTO contracts contain invalid entries")
    if not all(isinstance(value, dict) for value in candidate_contract_map.values()):
        raise AuthorityDiffError("candidate DTO contracts contain invalid entries")

    details: list[dict[str, Any]] = []
    for name in sorted(set(reference_contract_map) & set(candidate_contract_map)):
        reference_contract = reference_contract_map[name]
        candidate_contract = candidate_contract_map[name]
        if reference_contract == candidate_contract:
            continue
        reference_fields = _named_object_map(
            reference_contract.get("fields", []),
            key="field",
            context=f"reference contract {name} fields",
        )
        candidate_fields = _named_object_map(
            candidate_contract.get("fields", []),
            key="field",
            context=f"candidate contract {name} fields",
        )
        reference_metadata = {
            key: value for key, value in reference_contract.items() if key != "fields"
        }
        candidate_metadata = {
            key: value for key, value in candidate_contract.items() if key != "fields"
        }
        details.append(
            {
                "contract": name,
                "metadata": _top_level_delta(reference_metadata, candidate_metadata),
                "fields": _object_map_delta(
                    reference_fields, candidate_fields, include_values=True
                ),
            }
        )

    reference_transport = reference.get("transport_rules", {})
    candidate_transport = candidate.get("transport_rules", {})
    if not isinstance(reference_transport, Mapping) or not isinstance(candidate_transport, Mapping):
        raise AuthorityDiffError("transport_rules must be objects")
    reference_transport_map = {
        str(name): {"value": value} for name, value in reference_transport.items()
    }
    candidate_transport_map = {
        str(name): {"value": value} for name, value in candidate_transport.items()
    }
    route_keys = {"api", "apis", "endpoint", "endpoints", "route", "routes"}

    def count_route_declarations(value: object) -> int:
        if isinstance(value, Mapping):
            return sum(
                (1 if str(key).lower() in route_keys else 0) + count_route_declarations(child)
                for key, child in value.items()
            )
        if isinstance(value, list):
            return sum(count_route_declarations(child) for child in value)
        return 0

    reference_route_count = count_route_declarations(reference)
    candidate_route_count = count_route_declarations(candidate)
    return {
        "dto_contracts": _object_map_delta(reference_contract_map, candidate_contract_map),
        "added_contract_definitions": {
            name: candidate_contract_map[name]
            for name in sorted(set(candidate_contract_map) - set(reference_contract_map))
        },
        "removed_contract_definitions": {
            name: reference_contract_map[name]
            for name in sorted(set(reference_contract_map) - set(candidate_contract_map))
        },
        "modified_contract_details": details,
        "api_transport_rules": _object_map_delta(
            reference_transport_map, candidate_transport_map, include_values=True
        ),
        "api_routes": {
            "reference_declaration_count": reference_route_count,
            "candidate_declaration_count": candidate_route_count,
            "status": (
                "EXPLICITLY_COMPARED"
                if reference_route_count or candidate_route_count
                else "NOT_DECLARED_IN_COMPARED_DTO_AUTHORITY"
            ),
        },
    }


def build_report(
    *,
    reference_root: Path,
    candidate_root: Path,
    reference_label: str,
    candidate_label: str,
) -> dict[str, Any]:
    reference_canonical, reference_lock_path = _resolve_layout(reference_root)
    candidate_canonical, candidate_lock_path = _resolve_layout(candidate_root)
    reference_lock = _load_object(reference_lock_path)
    candidate_lock = _load_object(candidate_lock_path)
    reference_names = _controlled_names(reference_lock)
    candidate_names = _controlled_names(candidate_lock)
    union = sorted(set(reference_names) | set(candidate_names))

    changes: list[dict[str, Any]] = []
    status_counts = {"ADDED": 0, "REMOVED": 0, "MODIFIED": 0, "UNCHANGED": 0}
    for name in union:
        reference_path = reference_canonical / name
        candidate_path = candidate_canonical / name
        reference_exists = name in reference_names and reference_path.is_file()
        candidate_exists = name in candidate_names and candidate_path.is_file()
        if reference_exists and candidate_exists:
            reference_hash = _sha256(reference_path)
            candidate_hash = _sha256(candidate_path)
            status = "UNCHANGED" if reference_hash == candidate_hash else "MODIFIED"
        elif candidate_exists:
            reference_hash = None
            candidate_hash = _sha256(candidate_path)
            status = "ADDED"
        elif reference_exists:
            reference_hash = _sha256(reference_path)
            candidate_hash = None
            status = "REMOVED"
        else:
            raise AuthorityDiffError(f"locked artifact is missing from both roots: {name}")

        status_counts[status] += 1
        item: dict[str, Any] = {
            "file": name,
            "status": status,
            "reference": {
                "sha256": reference_hash,
                "bytes": reference_path.stat().st_size if reference_exists else None,
            },
            "candidate": {
                "sha256": candidate_hash,
                "bytes": candidate_path.stat().st_size if candidate_exists else None,
            },
        }
        if status == "MODIFIED":
            reference_json = _load_object(reference_path)
            candidate_json = _load_object(candidate_path)
            item["json_summary"] = {
                "top_level_keys": _top_level_delta(reference_json, candidate_json),
                "reference_db_declarations": _collect_db_declarations(reference_json),
                "candidate_db_declarations": _collect_db_declarations(candidate_json),
            }
            if name == "CORE_LOGICAL_MODEL.json":
                item["semantic_diff"] = {
                    "database": _table_semantic_delta(reference_json, candidate_json)
                }
            elif name == "CROSS_LAYER_DTO_CONTRACTS.json":
                item["semantic_diff"] = {
                    "dto_and_api": _dto_api_semantic_delta(reference_json, candidate_json)
                }
        changes.append(item)

    reference_metadata = _baseline_metadata(reference_lock)
    candidate_metadata = _baseline_metadata(candidate_lock)
    has_difference = any(status_counts[key] for key in ("ADDED", "REMOVED", "MODIFIED"))
    return {
        "schema": REPORT_SCHEMA,
        "status": "DIFFERENT" if has_difference else "IDENTICAL",
        "adoption_state": "DIFF_ONLY_NOT_ADOPTED",
        "reference": {
            "label": reference_label,
            "baseline": reference_metadata,
            "baseline_lock_sha256": _sha256(reference_lock_path),
            "controlled_artifact_count": len(reference_names),
        },
        "candidate": {
            "label": candidate_label,
            "baseline": candidate_metadata,
            "baseline_lock_sha256": _sha256(candidate_lock_path),
            "controlled_artifact_count": len(candidate_names),
        },
        "baseline_metadata_delta": _top_level_delta(reference_metadata, candidate_metadata),
        "semantic_coverage": {
            "tables": "EXPLICIT",
            "fields": "EXPLICIT",
            "enum_and_check_constraints": "EXPLICIT_FROM_FIELD_SQL",
            "indexes": "EXPLICIT_OR_REPORTED_NOT_DECLARED",
            "dto_contracts": "EXPLICIT",
            "api_transport_rules": "EXPLICIT",
            "api_routes": "EXPLICIT_OR_REPORTED_NOT_DECLARED",
        },
        "candidate_governance_extensions": {
            "schema_compatibility": (
                "GOVERNED_BY_SCHEMA_COMPATIBILITY_AUTHORITY"
                if "SCHEMA_COMPATIBILITY_AUTHORITY.json" in candidate_names
                else "NOT_DECLARED"
            ),
            "indexes": (
                "GOVERNED_BY_PHYSICAL_INDEX_AUTHORITY"
                if "PHYSICAL_INDEX_AUTHORITY.json" in candidate_names
                else "NOT_DECLARED"
            ),
            "api_routes": (
                "GOVERNED_BY_API_ROUTE_AUTHORITY"
                if "API_ROUTE_AUTHORITY.json" in candidate_names
                else "NOT_DECLARED"
            ),
            "baseline_decision": (
                "GOVERNED_BY_W0_BASELINE_AUTHORITY_DECISION"
                if "W0_BASELINE_AUTHORITY_DECISION.json" in candidate_names
                else "NOT_DECLARED"
            ),
        },
        "summary": status_counts,
        "artifacts": changes,
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
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--reference-label", default="REFERENCE")
    parser.add_argument("--candidate-label", default="CANDIDATE")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--fail-on-difference",
        action="store_true",
        help="Return 2 when the report status is DIFFERENT.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        report = build_report(
            reference_root=args.reference_root,
            candidate_root=args.candidate_root,
            reference_label=str(args.reference_label),
            candidate_label=str(args.candidate_label),
        )
    except AuthorityDiffError as exc:
        print(f"AUTHORITY_DIFF_FAIL {exc}", file=sys.stderr)
        return 2
    if args.output is not None:
        _write_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if args.fail_on_difference and report["status"] == "DIFFERENT":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
