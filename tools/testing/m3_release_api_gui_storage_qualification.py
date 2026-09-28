#!/usr/bin/env python3
"""M3-TST-005 Release/API/GUI/cross-platform/storage qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKING_ISSUE = 117
PLATFORM_SCHEMA = "TPAA_M3_TST_005_RELEASE_API_GUI_PLATFORM_EVIDENCE_V1"
CROSS_SCHEMA = "TPAA_M3_TST_005_RELEASE_API_GUI_CROSS_PLATFORM_EVIDENCE_V1"
QUALIFICATION_SCHEMA = "TPAA_M3_TST_005_RELEASE_API_GUI_STORAGE_QUALIFICATION_V1"
STORAGE_SCHEMA = "TPAA_M3_TST_005_STORAGE_PARITY_EVIDENCE_V1"

SOURCE_FILES = {
    "M3-TST-001": ("m3-tst-001", "catalog-coverage.json"),
    "M3-TST-002": ("m3-tst-002", "four-training-golden.json"),
    "M3-TST-003": ("m3-tst-003", "air-golden.json"),
    "M3-TST-004": ("m3-tst-004", "product-layer-golden.json"),
    "M3-OBS-001": ("m3-obs-001", "publication-routing.json"),
    "M3-OBS-002": ("m3-obs-002", "immutable-release.json"),
    "M3-OBS-003": ("m3-obs-003", "publication-replay.json"),
    "M3-API-001": ("m3-api-001", "release-query.json"),
    "M3-API-002": ("m3-api-002", "workspace.json"),
    "M3-GUI-001": ("m3-gui-001", "workspace-navigation.json"),
    "M3-GUI-002": ("m3-gui-002", "family-applicability.json"),
    "M3-GUI-003": ("m3-gui-003", "status-evidence-replay.json"),
}


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


def _load(path: Path) -> dict[str, object]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise ValueError(f"{path}: root must be a string-keyed object")
    return cast(dict[str, object], raw)


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be a string-keyed object")
    return cast(dict[str, object], value)


def _list(value: object, *, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return value


def _strings(value: object, *, field: str) -> tuple[str, ...]:
    items = _list(value, field=field)
    if not all(isinstance(item, str) for item in items):
        raise ValueError(f"{field} must contain only strings")
    return tuple(cast(list[str], items))


def _metric_codes(
    value: object,
    *,
    field: str,
) -> tuple[str, ...]:
    items = _list(value, field=field)
    result: list[str] = []
    for index, item in enumerate(items):
        row = _mapping(item, field=f"{field}[{index}]")
        code = row.get("metric_code")
        if not isinstance(code, str):
            raise ValueError(f"{field}[{index}].metric_code must be a string")
        result.append(code)
    return tuple(result)


def _hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _acceptance_all_true(evidence: dict[str, object], *, task_id: str) -> bool:
    acceptance = _mapping(evidence.get("acceptance"), field=f"{task_id}.acceptance")
    return bool(acceptance) and all(value is True for value in acceptance.values())


def check_platform(
    *,
    evidence_root: Path,
    platform: str,
    expected_revision: str,
) -> dict[str, object]:
    if platform not in {"windows", "linux"}:
        raise ValueError("platform must be windows or linux")
    if len(expected_revision) != 40:
        raise ValueError("expected_revision must be an exact 40-character Git SHA")

    sources: dict[str, dict[str, object]] = {}
    for task_id, (directory, filename) in SOURCE_FILES.items():
        path = evidence_root / directory / platform / filename
        sources[task_id] = _load(path)

    source_exact_head_pass = all(
        evidence.get("task_id") == task_id
        and evidence.get("status") == "PASS"
        and evidence.get("task_complete") is True
        and evidence.get("implementation_complete") is True
        and evidence.get("source_revision") == expected_revision
        and evidence.get("failed_acceptance") == []
        and _acceptance_all_true(evidence, task_id=task_id)
        for task_id, evidence in sources.items()
    )

    catalog = _mapping(
        sources["M3-TST-001"].get("logical_product"),
        field="M3-TST-001.logical_product",
    )
    integrated_codes = _strings(
        catalog.get("integrated_execution_codes"),
        field="M3-TST-001.integrated_execution_codes",
    )

    release = _mapping(
        sources["M3-OBS-002"].get("logical_product"),
        field="M3-OBS-002.logical_product",
    )
    release_definition_codes = _metric_codes(
        release.get("definitions"),
        field="M3-OBS-002.definitions",
    )
    release_execution_codes = _metric_codes(
        release.get("execution_records"),
        field="M3-OBS-002.execution_records",
    )
    release_evidence_codes = _metric_codes(
        release.get("evidence_bindings"),
        field="M3-OBS-002.evidence_bindings",
    )

    api_release = _mapping(
        sources["M3-API-001"].get("logical_product"),
        field="M3-API-001.logical_product",
    )
    api_codes = _strings(
        api_release.get("metric_codes"),
        field="M3-API-001.metric_codes",
    )

    obs003_scope = _mapping(
        sources["M3-OBS-003"].get("scope"),
        field="M3-OBS-003.scope",
    )
    api001_scope = _mapping(
        sources["M3-API-001"].get("scope"),
        field="M3-API-001.scope",
    )
    api002_scope = _mapping(
        sources["M3-API-002"].get("scope"),
        field="M3-API-002.scope",
    )
    gui001_scope = _mapping(
        sources["M3-GUI-001"].get("scope"),
        field="M3-GUI-001.scope",
    )
    gui002_scope = _mapping(
        sources["M3-GUI-002"].get("scope"),
        field="M3-GUI-002.scope",
    )
    gui003_scope = _mapping(
        sources["M3-GUI-003"].get("scope"),
        field="M3-GUI-003.scope",
    )

    exact_codes = (
        len(integrated_codes) == 116
        and len(set(integrated_codes)) == 116
        and release_definition_codes == integrated_codes
        and release_execution_codes == integrated_codes
        and release_evidence_codes == integrated_codes
        and api_codes == integrated_codes
    )
    prior_tst_complete = all(
        sources[f"M3-TST-{index:03d}"].get("task_complete") is True
        for index in range(1, 5)
    )
    api_gui_e2e = (
        api001_scope.get("metric_count") == 116
        and api002_scope.get("metric_membership_per_workspace") == 116
        and gui001_scope.get("gui_rendering_executed") is True
        and gui002_scope.get("gui_rendering_executed") is True
        and gui003_scope.get("gui_rendering_executed") is True
    )
    historical_replay_idempotency = (
        obs003_scope.get("historical_reads_release_id_bound") is True
        and obs003_scope.get("latest_authority_resolution_used") is False
        and gui003_scope.get("historical_replay_explicit_release_id") is True
        and gui003_scope.get("latest_authority_resolution_used") is False
    )
    no_transport_recompute = (
        api001_scope.get("business_metric_recomputation_executed") is False
        and api002_scope.get("business_metric_recomputation_executed") is False
        and gui001_scope.get("business_metric_recomputation_executed_by_gui") is False
        and gui002_scope.get("business_metric_recomputation_executed_by_gui") is False
        and gui003_scope.get("business_metric_recomputation_executed_by_gui") is False
    )
    gui_no_persistence = (
        gui001_scope.get("database_access_executed_by_gui") is False
        and gui002_scope.get("database_access_executed_by_gui") is False
        and gui003_scope.get("database_access_executed_by_gui") is False
    )

    acceptance = {
        "all_required_source_evidence_exact_head_pass": source_exact_head_pass,
        "m3_tst_001_through_004_complete_same_candidate": prior_tst_complete,
        "exact_116_release_membership_consistent": exact_codes,
        "release_api_gui_e2e_pass": api_gui_e2e,
        "history_replay_idempotency_release_bound": historical_replay_idempotency,
        "api_gui_do_not_recompute_metrics": no_transport_recompute,
        "gui_has_no_persistence_access": gui_no_persistence,
    }
    failed = sorted(name for name, passed in acceptance.items() if not passed)
    logical_product = {
        "platform": platform,
        "metric_codes": list(integrated_codes),
        "source_tasks": list(SOURCE_FILES),
        "source_schemas": {
            task_id: sources[task_id].get("schema")
            for task_id in SOURCE_FILES
        },
        "source_logical_hashes": {
            task_id: _hash(sources[task_id].get("logical_product"))
            for task_id in SOURCE_FILES
        },
        "source_acceptance_hashes": {
            task_id: _hash(sources[task_id].get("acceptance"))
            for task_id in SOURCE_FILES
        },
    }
    return {
        "schema": PLATFORM_SCHEMA,
        "task_id": "M3-TST-005",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "task_complete": not failed,
        "implementation_complete": not failed,
        "source_revision": expected_revision,
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "exact_116_release_membership": True,
            "api_gui_e2e_aggregated": True,
            "history_replay_idempotency_aggregated": True,
            "windows_linux_platform_evidence": True,
            "database_storage_parity_executed_here": False,
            "business_metric_recomputation_executed": False,
            "frozen_catalog_formulas_modified": False,
            "frozen_applicability_modified": False,
            "publication_routes_modified": False,
        },
    }


def compare_platform(
    windows_path: Path,
    linux_path: Path,
    *,
    expected_revision: str,
) -> dict[str, object]:
    windows = _load(windows_path)
    linux = _load(linux_path)
    windows_product = _mapping(
        windows.get("logical_product"),
        field="windows.logical_product",
    )
    linux_product = _mapping(
        linux.get("logical_product"),
        field="linux.logical_product",
    )
    windows_stable = dict(windows_product)
    linux_stable = dict(linux_product)
    windows_stable.pop("platform", None)
    linux_stable.pop("platform", None)

    checks = {
        "schemas_exact": (
            windows.get("schema") == linux.get("schema") == PLATFORM_SCHEMA
        ),
        "tasks_exact": windows.get("task_id") == linux.get("task_id") == "M3-TST-005",
        "statuses_pass": windows.get("status") == linux.get("status") == "PASS",
        "tasks_complete": (
            windows.get("task_complete") is True
            and linux.get("task_complete") is True
        ),
        "implementation_complete": (
            windows.get("implementation_complete") is True
            and linux.get("implementation_complete") is True
        ),
        "revisions_exact": (
            windows.get("source_revision")
            == linux.get("source_revision")
            == expected_revision
        ),
        "logical_product_equal": windows_stable == linux_stable,
        "acceptance_equal": windows.get("acceptance") == linux.get("acceptance"),
        "scope_equal": windows.get("scope") == linux.get("scope"),
        "failed_acceptance_empty": (
            windows.get("failed_acceptance") == []
            and linux.get("failed_acceptance") == []
        ),
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    logical_product = dict(windows_stable)
    return {
        "schema": CROSS_SCHEMA,
        "task_id": "M3-TST-005",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "task_complete": not failed,
        "implementation_complete": not failed,
        "source_revision": expected_revision,
        "windows_source_revision": windows.get("source_revision"),
        "linux_source_revision": linux.get("source_revision"),
        "logical_product": logical_product,
        "checks": checks,
        "failed_acceptance": failed,
    }


def qualify(
    *,
    cross_platform_path: Path,
    storage_path: Path,
    expected_revision: str,
) -> dict[str, object]:
    cross = _load(cross_platform_path)
    storage = _load(storage_path)
    cross_product = _mapping(
        cross.get("logical_product"),
        field="cross.logical_product",
    )
    platform_codes = _strings(
        cross_product.get("metric_codes"),
        field="cross.metric_codes",
    )
    storage_codes = _strings(
        storage.get("metric_codes"),
        field="storage.metric_codes",
    )
    storage_acceptance = _mapping(
        storage.get("acceptance"),
        field="storage.acceptance",
    )

    acceptance = {
        "windows_linux_logical_equivalence_pass": (
            cross.get("schema") == CROSS_SCHEMA
            and cross.get("status") == "PASS"
            and cross.get("task_complete") is True
            and cross.get("source_revision") == expected_revision
            and cross.get("failed_acceptance") == []
        ),
        "sqlite_postgres_storage_parity_pass": (
            storage.get("schema") == STORAGE_SCHEMA
            and storage.get("status") == "PASS"
            and storage.get("task_complete") is True
            and storage.get("source_revision") == expected_revision
            and storage.get("failed_acceptance") == []
            and bool(storage_acceptance)
            and all(value is True for value in storage_acceptance.values())
        ),
        "single_candidate_sha_exact": (
            cross.get("source_revision")
            == storage.get("source_revision")
            == expected_revision
        ),
        "exact_116_membership_same_across_platform_and_storage": (
            len(platform_codes) == 116
            and len(set(platform_codes)) == 116
            and storage_codes == platform_codes
        ),
        "history_replay_idempotency_api_gui_all_qualified": (
            _mapping(
                cross.get("checks"),
                field="cross.checks",
            ).get("failed_acceptance_empty")
            is True
            and storage_acceptance.get("sqlite_publish_idempotent") is True
            and storage_acceptance.get("postgres_publish_idempotent") is True
        ),
    }
    failed = sorted(name for name, passed in acceptance.items() if not passed)
    return {
        "schema": QUALIFICATION_SCHEMA,
        "task_id": "M3-TST-005",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "task_complete": not failed,
        "implementation_complete": not failed,
        "source_revision": expected_revision,
        "logical_product": {
            "metric_codes": list(platform_codes),
            "windows_linux_logical_product_hash": _hash(cross_product),
            "sqlite_membership_hash": storage.get("sqlite_membership_hash"),
            "postgres_membership_hash": storage.get("postgres_membership_hash"),
            "storage_release_id": storage.get("release_id"),
            "storage_manifest_hash": storage.get("manifest_hash"),
        },
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "exact_116_release_api_gui_cross_platform_storage": True,
            "sqlite_postgresql_logical_release_membership_parity": True,
            "api_gui_e2e": True,
            "history_replay_idempotency": True,
            "candidate_sha_single_and_exact": True,
        },
    }


def _write(payload: dict[str, object], path: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)

    check = sub.add_parser("check")
    check.add_argument("--evidence-root", type=Path, required=True)
    check.add_argument("--platform", required=True)
    check.add_argument("--expected-revision", required=True)
    check.add_argument("--evidence", type=Path, required=True)

    compare = sub.add_parser("compare")
    compare.add_argument("--windows", type=Path, required=True)
    compare.add_argument("--linux", type=Path, required=True)
    compare.add_argument("--expected-revision", required=True)
    compare.add_argument("--evidence", type=Path, required=True)

    final = sub.add_parser("qualify")
    final.add_argument("--cross-platform", type=Path, required=True)
    final.add_argument("--storage", type=Path, required=True)
    final.add_argument("--expected-revision", required=True)
    final.add_argument("--evidence", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.mode == "check":
            payload = check_platform(
                evidence_root=args.evidence_root,
                platform=args.platform,
                expected_revision=args.expected_revision,
            )
        elif args.mode == "compare":
            payload = compare_platform(
                args.windows,
                args.linux,
                expected_revision=args.expected_revision,
            )
        else:
            payload = qualify(
                cross_platform_path=args.cross_platform,
                storage_path=args.storage,
                expected_revision=args.expected_revision,
            )
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": QUALIFICATION_SCHEMA,
            "task_id": "M3-TST-005",
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "task_complete": False,
            "implementation_complete": False,
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        code = 2
    _write(payload, args.evidence)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
