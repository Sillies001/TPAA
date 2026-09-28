#!/usr/bin/env python3
"""M3-GUI-001 four-training Release-bound Desktop navigation qualification."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKING_ISSUE = 116


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


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise ValueError(f"{field} must be a string-keyed object")
    return cast(dict[str, object], value)


def _load(path: Path) -> dict[str, object]:
    return _mapping(json.loads(path.read_text(encoding="utf-8")), field=str(path))


def _table_product(table: Any) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in range(table.rowCount()):
        items = [table.item(row, column) for column in range(4)]
        if any(item is None for item in items):
            raise RuntimeError(f"family table row {row} is incomplete")
        text = [cast(Any, item).text() for item in items]
        rows.append(
            {
                "family_code": text[0],
                "metric_count": int(text[1]),
                "applicable_count": int(text[2]),
                "not_applicable_count": int(text[3]),
            }
        )
    return rows


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    repo_root = str(REPO_ROOT)
    if src_root not in sys.path:
        sys.path.insert(0, src_root)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtCore, QtWidgets

    from tools.testing.m3_api_workspace_check import verify as verify_api_workspace
    from tpaa_gui.m3_workspace import (
        M3_GUI_TRAINING_KEYS,
        M3_GUI_TRAINING_PRESENTATION,
        create_m3_workspace_navigation,
    )

    api_evidence = verify_api_workspace()
    if api_evidence.get("status") != "PASS":
        raise RuntimeError("M3-API-002 prerequisite qualification did not pass")
    api_product = _mapping(
        api_evidence.get("logical_product"),
        field="api logical product",
    )

    release_ids_by_training: dict[str, str] = {}
    workspace_by_release: dict[str, dict[str, object]] = {}
    for training_key in M3_GUI_TRAINING_KEYS:
        workspace = _mapping(
            api_product.get(training_key),
            field=f"api logical product {training_key}",
        )
        release_id = workspace.get("release_id")
        if not isinstance(release_id, str) or not release_id:
            raise RuntimeError(f"{training_key} release id missing")
        release_ids_by_training[training_key] = release_id
        workspace_by_release[release_id] = workspace

    class ProjectionTransport:
        def __init__(self) -> None:
            self.requested_paths: list[str] = []

        def m3_request_json(
            self,
            method: str,
            path: str,
            *,
            body: dict[str, object] | None = None,
            headers: dict[str, str] | None = None,
        ) -> tuple[int, dict[str, Any]]:
            if method != "GET" or body is not None or headers is not None:
                return 405, {
                    "outcome": "SYSTEM_ERROR",
                    "error": {"code": "GUI_TRANSPORT_METHOD_FORBIDDEN"},
                }
            self.requested_paths.append(path)
            for release_id, workspace in workspace_by_release.items():
                expected = f"/m3/releases/{release_id}/workspace"
                if path == expected:
                    return 200, cast(dict[str, Any], workspace)
            return 404, {
                "outcome": "SYSTEM_ERROR",
                "error": {"code": "RELEASE_NOT_FOUND"},
            }

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(["tpaa-m3-gui-001-check"])
    transport = ProjectionTransport()
    root = create_m3_workspace_navigation(
        QtCore,
        QtWidgets,
        None,
        transport=transport,
        release_ids_by_training=release_ids_by_training,
    )

    selector = root.findChild(QtWidgets.QComboBox, "tpaaM3TrainingSelector")
    header = root.findChild(QtWidgets.QLabel, "tpaaM3TrainingHeader")
    release_label = root.findChild(QtWidgets.QLabel, "tpaaM3ReleaseIdentity")
    episode_label = root.findChild(QtWidgets.QLabel, "tpaaM3EpisodeIdentity")
    stage_label = root.findChild(QtWidgets.QLabel, "tpaaM3StageIdentity")
    provenance_label = root.findChild(QtWidgets.QLabel, "tpaaM3ReleaseProvenance")
    family_table = root.findChild(QtWidgets.QTableWidget, "tpaaM3FamilySummary")
    status_label = root.findChild(QtWidgets.QLabel, "tpaaM3NavigationStatus")
    widgets = (
        selector,
        header,
        release_label,
        episode_label,
        stage_label,
        provenance_label,
        family_table,
        status_label,
    )
    if any(widget is None for widget in widgets):
        raise RuntimeError("M3 GUI navigation automation surface is incomplete")

    selector = cast(Any, selector)
    header = cast(Any, header)
    release_label = cast(Any, release_label)
    episode_label = cast(Any, episode_label)
    stage_label = cast(Any, stage_label)
    provenance_label = cast(Any, provenance_label)
    family_table = cast(Any, family_table)
    status_label = cast(Any, status_label)

    product: dict[str, object] = {}
    acceptance: dict[str, bool] = {}
    for training_key in M3_GUI_TRAINING_KEYS:
        selector.setCurrentText(training_key)
        app.processEvents()

        workspace = _mapping(
            api_product.get(training_key),
            field=f"{training_key}.workspace",
        )
        training = _mapping(
            workspace.get("training"),
            field=f"{training_key}.training",
        )
        expected_families = workspace.get("families")
        if not isinstance(expected_families, list):
            raise RuntimeError(f"{training_key} family projection missing")
        family_rows = _table_product(family_table)
        expected_family_rows = [
            _mapping(row, field=f"{training_key}.family")
            for row in expected_families
        ]

        label = M3_GUI_TRAINING_PRESENTATION[training_key]
        expected_release_id = release_ids_by_training[training_key]
        rendered = {
            "header": header.text(),
            "release": release_label.text(),
            "episode": episode_label.text(),
            "stage": stage_label.text(),
            "provenance": provenance_label.text(),
            "status": status_label.text(),
            "families": family_rows,
        }
        acceptance[f"{training_key.lower()}_specialized_header_exact"] = (
            rendered["header"]
            == f"{label} · {training.get('episode_type')} · "
            f"{training.get('stage_profile_id')}"
        )
        acceptance[f"{training_key.lower()}_release_identity_exact"] = (
            rendered["release"] == f"Release: {expected_release_id}"
        )
        acceptance[f"{training_key.lower()}_episode_identity_exact"] = (
            rendered["episode"]
            == f"Episode: {training.get('episode_id')} · "
            f"type={training.get('episode_type')}"
        )
        acceptance[f"{training_key.lower()}_stage_identity_exact"] = (
            rendered["stage"]
            == f"Stage: {training.get('stage_id')} · "
            f"code={training.get('stage_code')}"
        )
        acceptance[f"{training_key.lower()}_family_summary_exact"] = (
            family_rows == expected_family_rows
            and sum(cast(int, row["metric_count"]) for row in family_rows) == 116
        )
        acceptance[f"{training_key.lower()}_ready_exact_116"] = (
            rendered["status"]
            == f"Navigation: READY · {training_key} · 116 metrics"
        )
        product[training_key] = {
            "release_id": expected_release_id,
            "manifest_hash": workspace.get("manifest_hash"),
            "training": training,
            "rendered": rendered,
        }

    expected_paths = [
        f"/m3/releases/{release_ids_by_training[key]}/workspace"
        for key in M3_GUI_TRAINING_KEYS
    ]
    acceptance["four_training_routes_exact"] = (
        transport.requested_paths == expected_paths
    )
    acceptance["historical_release_ids_explicit"] = all(
        "/latest" not in path
        and "/current" not in path
        and path.startswith("/m3/releases/")
        for path in transport.requested_paths
    )

    module_source = (
        REPO_ROOT / "src" / "tpaa_gui" / "m3_workspace.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "tpaa_application",
        "tpaa_api",
        "tpaa_metric",
        "tpaa_observation",
        "tpaa_storage",
        "tpaa_world",
        "CatalogMetricEngine",
        "build_m3_metric_execution_plan",
        "sqlite3",
        "psycopg",
    )
    acceptance["gui_projection_only_no_persistence_or_engine"] = all(
        token not in module_source for token in forbidden
    )
    acceptance["api_prerequisite_task_complete"] = (
        api_evidence.get("task_complete") is True
        and api_evidence.get("implementation_complete") is True
        and api_evidence.get("failed_acceptance") == []
    )

    root.close()
    app.processEvents()

    failed = sorted(key for key, passed in acceptance.items() if not passed)
    return {
        "schema": "TPAA_M3_GUI_001_WORKSPACE_NAVIGATION_EVIDENCE_V1",
        "task_id": "M3-GUI-001",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "task_complete": not failed,
        "implementation_complete": not failed,
        "source_revision": _git_revision(),
        "logical_product": product,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "four_training_types": True,
            "release_bound_api_projection_consumed": True,
            "historical_release_id_explicit": True,
            "latest_authority_resolution_used": False,
            "database_access_executed_by_gui": False,
            "business_metric_recomputation_executed_by_gui": False,
            "gui_rendering_executed": True,
        },
    }


def compare_evidence(
    windows_path: Path,
    linux_path: Path,
    *,
    expected_revision: str,
) -> dict[str, object]:
    windows = _load(windows_path)
    linux = _load(linux_path)
    checks = {
        "windows_status_pass": windows.get("status") == "PASS",
        "linux_status_pass": linux.get("status") == "PASS",
        "windows_task_complete": windows.get("task_complete") is True,
        "linux_task_complete": linux.get("task_complete") is True,
        "windows_implementation_complete": (
            windows.get("implementation_complete") is True
        ),
        "linux_implementation_complete": linux.get("implementation_complete") is True,
        "windows_revision_exact": windows.get("source_revision") == expected_revision,
        "linux_revision_exact": linux.get("source_revision") == expected_revision,
        "logical_product_equal": (
            windows.get("logical_product") == linux.get("logical_product")
        ),
        "acceptance_equal": windows.get("acceptance") == linux.get("acceptance"),
        "failed_acceptance_empty": (
            windows.get("failed_acceptance") == []
            and linux.get("failed_acceptance") == []
        ),
    }
    failed = sorted(key for key, passed in checks.items() if not passed)
    return {
        "schema": (
            "TPAA_M3_GUI_001_WORKSPACE_NAVIGATION_CROSS_PLATFORM_EVIDENCE_V1"
        ),
        "task_id": "M3-GUI-001",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "task_complete": not failed,
        "implementation_complete": not failed,
        "source_revision": expected_revision,
        "windows_source_revision": windows.get("source_revision"),
        "linux_source_revision": linux.get("source_revision"),
        "logical_product": windows.get("logical_product"),
        "checks": checks,
        "failed_acceptance": failed,
    }


def _write(payload: dict[str, object], path: Path | None) -> None:
    rendered = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    print(rendered, end="")
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    check = sub.add_parser("check")
    check.add_argument("--evidence", type=Path)
    compare = sub.add_parser("compare")
    compare.add_argument("--windows", type=Path, required=True)
    compare.add_argument("--linux", type=Path, required=True)
    compare.add_argument("--expected-revision", required=True)
    compare.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()

    try:
        if args.mode == "check":
            payload = verify()
            evidence = args.evidence
        else:
            payload = compare_evidence(
                args.windows,
                args.linux,
                expected_revision=args.expected_revision,
            )
            evidence = args.evidence
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M3_GUI_001_WORKSPACE_NAVIGATION_EVIDENCE_V1",
            "task_id": "M3-GUI-001",
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "task_complete": False,
            "implementation_complete": False,
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        evidence = getattr(args, "evidence", None)
        code = 2
    _write(payload, evidence)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
