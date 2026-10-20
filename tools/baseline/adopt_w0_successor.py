#!/usr/bin/env python3
"""Build the approved W0 successor baseline without mutating its predecessor."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0"
TARGET_ROOT = REPO_ROOT / "baseline" / "CB-1.5.0"
OLD_CORE = "CB-1.4.0"
NEW_CORE = "CB-1.5.0"
DECISION_ID = "W0-AUTHORITY-CONVERGENCE-2026-10-19"
REBASELINE_ID = "R6.0_W0_CORE_1_5_0_AUTHORITY_CONVERGENCE"
APPROVAL_DATE = "2026-10-19"
COMPATIBLE_SCHEMAS = ["1.6.0", "1.7.0", "1.8.0", "1.9.0"]


class SuccessorBuildError(RuntimeError):
    """The successor baseline cannot be built deterministically."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SuccessorBuildError(f"expected JSON object: {path}")
    return value


def _write_object(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _replace_core(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _replace_core(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_replace_core(child) for child in value]
    if isinstance(value, str):
        return value.replace(OLD_CORE, NEW_CORE)
    return value


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


def _compatibility_authority(target: Path) -> dict[str, Any]:
    canonical = target / "canonical"
    declarations: list[dict[str, str]] = []
    core_inheritance: list[dict[str, str]] = []
    for path in sorted(canonical.glob("*.json"), key=lambda item: item.name):
        payload = _load_object(path)
        artifact_core = payload.get("core_baseline")
        if isinstance(artifact_core, str) and artifact_core != NEW_CORE:
            core_inheritance.append(
                {
                    "file": path.name,
                    "declared_core_baseline": artifact_core,
                    "compatible_core_baseline": NEW_CORE,
                    "approval_status": "APPROVED",
                }
            )
        for declaration in _collect_db_declarations(payload):
            if declaration["value"] != "1.9.0":
                declarations.append({"file": path.name, **declaration})
    provenance = target / "IMPORT_PROVENANCE.json"
    if provenance.is_file():
        for declaration in _collect_db_declarations(_load_object(provenance)):
            if declaration["value"] != "1.9.0":
                declarations.append({"file": provenance.name, **declaration})
    return {
        "authority_id": "SCHEMA_COMPATIBILITY_AUTHORITY",
        "authority_version": "1.0.0",
        "core_baseline": NEW_CORE,
        "current_db_schema": "1.9.0",
        "decision_id": DECISION_ID,
        "approval_status": "APPROVED",
        "approval_date": APPROVAL_DATE,
        "approval_basis": (
            "Project owner delegated the four W0 baseline decisions to the implementation "
            "agent in the local remediation session."
        ),
        "compatibility_policy": (
            "Historical semantic declarations retain their introduced schema identity. "
            "Compatibility is approved only through the additive ACP-216/219/221 migration "
            "lineage and does not authorize in-place history rewriting."
        ),
        "core_inheritance": core_inheritance,
        "entries": [
            {
                **declaration,
                "introduced_in_schema": declaration["value"],
                "compatible_schema_versions": COMPATIBLE_SCHEMAS,
                "compatibility_kind": "ADDITIVE_FORWARD_COMPATIBLE",
                "approval_status": "APPROVED",
            }
            for declaration in declarations
        ],
    }


def _index_authority(core: Mapping[str, Any]) -> dict[str, Any]:
    raw_tables = core.get("tables")
    if not isinstance(raw_tables, Mapping):
        raise SuccessorBuildError("CORE_LOGICAL_MODEL tables must be an object")
    indexes: list[dict[str, Any]] = []
    for raw_table in sorted(raw_tables, key=str):
        table_name = str(raw_table)
        table = raw_tables[raw_table]
        if not isinstance(table, Mapping):
            raise SuccessorBuildError(f"invalid table definition: {table_name}")
        fields = table.get("fields")
        if not isinstance(fields, list):
            raise SuccessorBuildError(f"invalid fields: {table_name}")
        for field in fields:
            if not isinstance(field, Mapping):
                raise SuccessorBuildError(f"invalid field: {table_name}")
            field_name = field.get("name")
            sql = field.get("sql")
            if not isinstance(field_name, str) or not isinstance(sql, str):
                continue
            upper = sql.upper()
            kinds = []
            if "PRIMARY KEY" in upper:
                kinds.append("PRIMARY_KEY")
            if "UNIQUE" in upper:
                kinds.append("UNIQUE")
            for kind in kinds:
                indexes.append(
                    {
                        "index_id": f"{table_name}.{field_name}.{kind}",
                        "table": table_name,
                        "fields": [field_name],
                        "kind": kind,
                        "source_sql": sql,
                        "derivation": "CORE_LOGICAL_MODEL.tables[].fields[].sql",
                    }
                )
        constraints = table.get("constraints", [])
        if not isinstance(constraints, list):
            raise SuccessorBuildError(f"invalid constraints: {table_name}")
        for position, constraint in enumerate(constraints):
            if not isinstance(constraint, str):
                raise SuccessorBuildError(f"invalid constraint: {table_name}")
            upper = constraint.upper()
            if "PRIMARY KEY" in upper:
                kind = "PRIMARY_KEY"
            elif "UNIQUE" in upper:
                kind = "UNIQUE"
            else:
                continue
            indexes.append(
                {
                    "index_id": f"{table_name}.table_constraint_{position}.{kind}",
                    "table": table_name,
                    "fields": [],
                    "kind": kind,
                    "source_sql": constraint,
                    "derivation": "CORE_LOGICAL_MODEL.tables[].constraints[]",
                }
            )
    return {
        "authority_id": "PHYSICAL_INDEX_AUTHORITY",
        "authority_version": "1.0.0",
        "core_baseline": NEW_CORE,
        "db_schema_version": "1.9.0",
        "decision_id": DECISION_ID,
        "approval_status": "APPROVED",
        "secondary_index_policy": (
            "Only primary-key and unique indexes declared by the Core model are governed in "
            "CB-1.5.0. Additional performance indexes require a successor authority change."
        ),
        "indexes": indexes,
    }


def _decorator_route(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
            continue
        method = decorator.func.attr.upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            continue
        if not decorator.args or not isinstance(decorator.args[0], ast.Constant):
            raise SuccessorBuildError(f"route path must be a literal: {node.name}")
        path = decorator.args[0].value
        if not isinstance(path, str):
            raise SuccessorBuildError(f"route path must be a string: {node.name}")
        keywords = {keyword.arg: keyword.value for keyword in decorator.keywords if keyword.arg}
        operation = keywords.get("operation_id")
        response = keywords.get("response_model")
        routes.append(
            {
                "method": method,
                "path": path,
                "handler": node.name,
                "operation_id": (operation.value if isinstance(operation, ast.Constant) else None),
                "response_model": ast.unparse(response) if response is not None else None,
            }
        )
    return routes


def _api_route_authority() -> dict[str, Any]:
    routes: list[dict[str, Any]] = []
    for path in sorted((REPO_ROOT / "src" / "tpaa_api").glob("*.py"), key=lambda p: p.name):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for route in _decorator_route(node):
                    routes.append(
                        {
                            **route,
                            "module": f"tpaa_api.{path.stem}",
                            "dto_authority": "CROSS_LAYER_DTO_CONTRACTS",
                        }
                    )
    routes.sort(key=lambda item: (item["path"], item["method"], item["module"], item["handler"]))
    identities = [(item["method"], item["path"], item["module"]) for item in routes]
    if len(identities) != len(set(identities)):
        raise SuccessorBuildError("duplicate API route declaration")
    return {
        "authority_id": "API_ROUTE_AUTHORITY",
        "authority_version": "1.0.0",
        "core_baseline": NEW_CORE,
        "api_version": "v1",
        "decision_id": DECISION_ID,
        "approval_status": "APPROVED",
        "scope": (
            "All statically declared FastAPI routes under src/tpaa_api; runtime composition "
            "and role admission remain governed by their profile and security authorities."
        ),
        "routes": routes,
    }


def _decision_authority(predecessor_hash: str) -> dict[str, Any]:
    return {
        "authority_id": "W0_BASELINE_AUTHORITY_DECISION",
        "authority_version": "1.0.0",
        "decision_id": DECISION_ID,
        "approval_status": "APPROVED",
        "approval_date": APPROVAL_DATE,
        "approval_basis": (
            "Explicit project-owner delegation to confirm all four W0 decisions and close W0."
        ),
        "version_tuple": {
            "overall": "TPAA V8.0",
            "engineering": "ED-2.0",
            "core": NEW_CORE,
            "db_schema": "1.9.0",
            "product": "P1_METRIC_CATALOG-1.14.0",
        },
        "predecessor": {
            "core": OLD_CORE,
            "source_baseline_lock_sha256": predecessor_hash,
            "r3_3_reference_lock_sha256": (
                "9d96a7eb0ba2b1fb13b11d76943171f773fd42497df74bf79c01928cfa26e7fa"
            ),
            "immutability": "R3.3 remains byte-identical and is never overwritten.",
        },
        "decisions": {
            "successor_required": True,
            "historical_schema_compatibility": "APPROVED_PER_DECLARATION",
            "index_authority": "REQUIRED_AND_ADDED",
            "api_route_authority": "REQUIRED_AND_ADDED",
            "production_release_claim": False,
        },
    }


def build_successor(destination: Path) -> None:
    if destination.exists():
        raise SuccessorBuildError(f"destination already exists: {destination}")
    source_lock = SOURCE_ROOT / "BASELINE_LOCK.json"
    predecessor_hash = _sha256(source_lock)
    shutil.copytree(SOURCE_ROOT, destination)
    canonical = destination / "canonical"
    promoted_files = {
        "CORE_LOGICAL_MODEL.json",
        "CROSS_LAYER_DTO_CONTRACTS.json",
        "P6_P3_CAPABILITY_OLS_MAD_FORECAST_PROFILE.json",
        "P6_ROLE_PRIVACY_RELEASE_PROFILE.json",
    }
    for name in sorted(promoted_files):
        path = canonical / name
        _write_object(path, _replace_core(_load_object(path)))  # type: ignore[arg-type]

    dto_hash = _sha256(canonical / "CROSS_LAYER_DTO_CONTRACTS.json")
    predecessor_dto_hash = (
        "28f7209e40709fb4eb53ceffdfee3542e867f060c4e63605cc1ad149a8e3819a"
    )
    for name in (
        "P6_P3_CAPABILITY_OLS_MAD_FORECAST_PROFILE.json",
        "P6_ROLE_PRIVACY_RELEASE_PROFILE.json",
    ):
        path = canonical / name
        payload = _load_object(path)
        replaced = json.loads(
            json.dumps(payload).replace(predecessor_dto_hash, dto_hash)
        )
        _write_object(path, replaced)

    core = _load_object(canonical / "CORE_LOGICAL_MODEL.json")
    _write_object(
        canonical / "SCHEMA_COMPATIBILITY_AUTHORITY.json",
        _compatibility_authority(destination),
    )
    _write_object(canonical / "PHYSICAL_INDEX_AUTHORITY.json", _index_authority(core))
    _write_object(canonical / "API_ROUTE_AUTHORITY.json", _api_route_authority())
    _write_object(
        canonical / "W0_BASELINE_AUTHORITY_DECISION.json",
        _decision_authority(predecessor_hash),
    )

    source_lock_payload = _load_object(source_lock)
    source_baseline = source_lock_payload.get("baseline")
    if not isinstance(source_baseline, Mapping):
        raise SuccessorBuildError("source BASELINE_LOCK baseline is invalid")
    lineage = source_baseline.get("lock_lineage_sha256")
    if not isinstance(lineage, list) or not all(isinstance(item, str) for item in lineage):
        raise SuccessorBuildError("source lock lineage is invalid")
    artifacts = [
        {
            "file": path.name,
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(canonical.glob("*.json"), key=lambda item: item.name)
    ]
    lock = {
        "baseline": {
            "overall": "TPAA V8.0",
            "methodology": "TPAA V8.0 Training Evaluation Methodology",
            "engineering": "ED-2.0",
            "core": NEW_CORE,
            "db_schema": "1.9.0",
            "product": "P1_METRIC_CATALOG-1.14.0",
            "date": APPROVAL_DATE,
            "rebaseline": REBASELINE_ID,
            "decision_id": DECISION_ID,
            "lock_lineage_sha256": [*lineage, predecessor_hash],
        },
        "artifacts": artifacts,
    }
    _write_object(destination / "BASELINE_LOCK.json", lock)
    readme = destination / "README.md"
    readme.write_text(
        "# CB-1.5.0 W0 successor baseline\n\n"
        f"Decision: `{DECISION_ID}`.\n\n"
        f"Predecessor lock SHA-256: `{predecessor_hash}`.\n\n"
        "This package is the locally approved W0 successor. R3.3 and CB-1.4.0 are "
        "immutable predecessors. This approval does not authorize repository push or "
        "production deployment.\n",
        encoding="utf-8",
    )


def _directory_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.check:
            if not TARGET_ROOT.is_dir():
                raise SuccessorBuildError(f"successor is missing: {TARGET_ROOT}")
            with tempfile.TemporaryDirectory(prefix="tpaa-w0-") as temporary:
                generated = Path(temporary) / NEW_CORE
                build_successor(generated)
                expected = _directory_digest(generated)
                actual = _directory_digest(TARGET_ROOT)
                if actual != expected:
                    raise SuccessorBuildError(
                        f"successor drift: expected={expected} actual={actual}"
                    )
                print(f"W0_SUCCESSOR_PASS core={NEW_CORE} digest={actual}")
        else:
            build_successor(TARGET_ROOT)
            print(
                f"W0_SUCCESSOR_BUILT core={NEW_CORE} "
                f"lock_sha256={_sha256(TARGET_ROOT / 'BASELINE_LOCK.json')}"
            )
    except (OSError, ValueError, json.JSONDecodeError, SuccessorBuildError) as exc:
        print(f"W0_SUCCESSOR_FAIL {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
