#!/usr/bin/env python3
"""M3-GUI-003 status, Evidence, and explicit historical replay qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, cast
from uuid import NAMESPACE_URL, uuid5

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


def _table_rows(table: Any, columns: int) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in range(table.rowCount()):
        values: list[str] = []
        for column in range(columns):
            item = table.item(row, column)
            if item is None:
                raise RuntimeError(f"table row {row} column {column} incomplete")
            values.append(cast(Any, item).text())
        rows.append(values)
    return rows


def _execution_hash(release_id: str, metric_code: str) -> str:
    return hashlib.sha256(
        f"{release_id}:{metric_code}:execution".encode("utf-8")
    ).hexdigest()


def _evidence_projection(
    workspace: dict[str, object],
    metric: dict[str, object],
) -> dict[str, object]:
    release_id = workspace.get("release_id")
    manifest_hash = workspace.get("manifest_hash")
    metric_code = metric.get("metric_code")
    definition_hash = metric.get("definition_hash")
    evidence_hash = metric.get("evidence_hash")
    if not all(
        isinstance(value, str) and value
        for value in (
            release_id,
            manifest_hash,
            metric_code,
            definition_hash,
            evidence_hash,
        )
    ):
        raise RuntimeError("workspace metric Evidence identity incomplete")
    release_id = cast(str, release_id)
    metric_code = cast(str, metric_code)
    provenance = _mapping(
        workspace.get("release_provenance"),
        field="release_provenance",
    )
    applicability = _mapping(
        metric.get("applicability"),
        field=f"{metric_code}.applicability",
    )
    reasons = applicability.get("reason_codes")
    instances = metric.get("instances")
    if not isinstance(reasons, list) or not isinstance(instances, list):
        raise RuntimeError(f"{metric_code} projected Evidence rows invalid")
    return {
        "release_id": release_id,
        "metric_code": metric_code,
        "definition_hash": definition_hash,
        "execution_record_hash": _execution_hash(release_id, metric_code),
        "evidence_hash": evidence_hash,
        "payload": {
            "workspace_contract": "M3_API_002_WORKSPACE_EVIDENCE_V1",
            "training": workspace.get("training"),
            "family_code": metric.get("family_code"),
            "applicable": applicability.get("applicable"),
            "applicability_reason_codes": reasons,
            "system_type": applicability.get("system_type"),
            "instances": instances,
        },
        "release_provenance": {
            "manifest_hash": manifest_hash,
            "provenance_hash": provenance.get("provenance_hash"),
        },
    }


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    repo_root = str(REPO_ROOT)
    if src_root not in sys.path:
        sys.path.insert(0, src_root)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtCore, QtWidgets

    from tools.testing.m3_api_release_query_check import (
        verify as verify_api_release_query,
    )
    from tools.testing.m3_api_workspace_check import verify as verify_api_workspace
    from tools.testing.m3_idempotent_publication_check import (
        verify as verify_publication_replay,
    )
    from tpaa_gui.m3_status import (
        M3_GUI_RESULT_STATUSES,
        M3_GUI_STATUS_STYLES,
    )
    from tpaa_gui.m3_workspace import (
        M3_GUI_TRAINING_KEYS,
        create_m3_workspace_navigation,
    )

    api_workspace_evidence = verify_api_workspace()
    api_release_evidence = verify_api_release_query()
    replay_evidence = verify_publication_replay()
    for name, evidence in (
        ("M3-API-002", api_workspace_evidence),
        ("M3-API-001", api_release_evidence),
        ("M3-OBS-003", replay_evidence),
    ):
        if (
            evidence.get("status") != "PASS"
            or evidence.get("task_complete") is not True
            or evidence.get("failed_acceptance") != []
        ):
            raise RuntimeError(f"{name} prerequisite qualification did not pass")

    api_product = _mapping(
        api_workspace_evidence.get("logical_product"),
        field="api workspace logical product",
    )
    release_ids_by_training: dict[str, str] = {}
    historical_ids_by_training: dict[str, str] = {}
    workspace_by_release: dict[str, dict[str, object]] = {}
    evidence_by_path: dict[str, dict[str, object]] = {}

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

        historical_id = str(
            uuid5(NAMESPACE_URL, f"m3-gui-003:{training_key}:historical")
        )
        historical_ids_by_training[training_key] = historical_id
        historical_workspace = deepcopy(workspace)
        historical_workspace["release_id"] = historical_id
        historical_metrics = historical_workspace.get("metrics")
        if not isinstance(historical_metrics, list):
            raise RuntimeError(f"{training_key} historical metrics missing")
        for raw_metric in historical_metrics:
            metric = _mapping(raw_metric, field=f"{training_key}.historical.metric")
            metric["release_id"] = historical_id
        workspace_by_release[historical_id] = historical_workspace

    for release_id, workspace in workspace_by_release.items():
        raw_metrics = workspace.get("metrics")
        if not isinstance(raw_metrics, list):
            raise RuntimeError(f"{release_id} metrics missing")
        for raw_metric in raw_metrics:
            metric = _mapping(raw_metric, field=f"{release_id}.metric")
            metric_code = metric.get("metric_code")
            if not isinstance(metric_code, str) or not metric_code:
                raise RuntimeError(f"{release_id} metric code invalid")
            path = f"/m3/releases/{release_id}/metrics/{metric_code}/evidence"
            evidence_by_path[path] = _evidence_projection(workspace, metric)

    class ProjectionTransport:
        def __init__(self) -> None:
            self.requested_paths: list[str] = []
            self.fail_next_evidence = False

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
            if path.endswith("/evidence"):
                if self.fail_next_evidence:
                    self.fail_next_evidence = False
                    return 503, {
                        "outcome": "SYSTEM_ERROR",
                        "error": {"code": "EVIDENCE_UNAVAILABLE"},
                    }
                payload = evidence_by_path.get(path)
                if payload is None:
                    return 404, {
                        "outcome": "SYSTEM_ERROR",
                        "error": {"code": "METRIC_NOT_FOUND"},
                    }
                return 200, cast(dict[str, Any], payload)

            for candidate_release_id, workspace in workspace_by_release.items():
                if path == f"/m3/releases/{candidate_release_id}/workspace":
                    return 200, cast(dict[str, Any], workspace)
            return 404, {
                "outcome": "SYSTEM_ERROR",
                "error": {"code": "RELEASE_NOT_FOUND"},
            }

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(["tpaa-m3-gui-003-check"])
    transport = ProjectionTransport()
    root = create_m3_workspace_navigation(
        QtCore,
        QtWidgets,
        None,
        transport=transport,
        release_ids_by_training=release_ids_by_training,
    )

    selector = root.findChild(QtWidgets.QComboBox, "tpaaM3TrainingSelector")
    replay_input = root.findChild(QtWidgets.QLineEdit, "tpaaM3HistoricalReleaseInput")
    replay_button = root.findChild(QtWidgets.QPushButton, "tpaaM3HistoricalReplayLoad")
    replay_identity = root.findChild(QtWidgets.QLabel, "tpaaM3HistoricalReplayIdentity")
    result_table = root.findChild(QtWidgets.QTableWidget, "tpaaM3MetricStatus")
    selected_status = root.findChild(QtWidgets.QLabel, "tpaaM3SelectedMetricStatus")
    evidence_button = root.findChild(QtWidgets.QPushButton, "tpaaM3EvidenceDrilldown")
    evidence_status = root.findChild(QtWidgets.QLabel, "tpaaM3EvidenceStatus")
    evidence_detail = root.findChild(QtWidgets.QPlainTextEdit, "tpaaM3EvidenceDetail")
    navigation_status = root.findChild(QtWidgets.QLabel, "tpaaM3NavigationStatus")
    widgets = (
        selector,
        replay_input,
        replay_button,
        replay_identity,
        result_table,
        selected_status,
        evidence_button,
        evidence_status,
        evidence_detail,
        navigation_status,
    )
    if any(widget is None for widget in widgets):
        raise RuntimeError("M3 GUI status/Evidence/replay automation surface incomplete")

    selector = cast(Any, selector)
    replay_input = cast(Any, replay_input)
    replay_button = cast(Any, replay_button)
    replay_identity = cast(Any, replay_identity)
    result_table = cast(Any, result_table)
    selected_status = cast(Any, selected_status)
    evidence_button = cast(Any, evidence_button)
    evidence_status = cast(Any, evidence_status)
    evidence_detail = cast(Any, evidence_detail)
    navigation_status = cast(Any, navigation_status)

    acceptance: dict[str, bool] = {}
    product: dict[str, object] = {}

    acceptance["status_styles_distinct_including_system_error"] = (
        len(
            {
                M3_GUI_STATUS_STYLES[key]
                for key in (
                    "VALID",
                    "N_A",
                    "INSUFFICIENT_DATA",
                    "INVALID",
                    "REVIEW_REQUIRED",
                    "NOT_APPLICABLE",
                    "SYSTEM_ERROR",
                )
            }
        )
        == 7
    )

    for training_key in M3_GUI_TRAINING_KEYS:
        selector.setCurrentText(training_key)
        app.processEvents()
        base_release_id = release_ids_by_training[training_key]
        historical_id = historical_ids_by_training[training_key]

        replay_input.setText(historical_id)
        replay_button.click()
        app.processEvents()

        rows = _table_rows(result_table, 7)
        row_kinds = {row[3] for row in rows}
        key = training_key.lower()
        acceptance[f"{key}_all_five_result_states_visible"] = (
            M3_GUI_RESULT_STATUSES <= row_kinds
        )
        acceptance[f"{key}_not_applicable_not_conflated_with_n_a"] = (
            "NOT_APPLICABLE" in row_kinds
            and "N_A" in row_kinds
            and "NOT_APPLICABLE" != "N_A"
        )
        acceptance[f"{key}_historical_release_identity_exact"] = (
            replay_identity.text()
            == (
                f"Historical replay: RELEASE_BOUND · Release: {historical_id} · "
                f"Manifest: {workspace_by_release[historical_id].get('manifest_hash')}"
            )
            and navigation_status.text()
            == f"Navigation: READY · {training_key} · 116 metrics"
            and all(row[6] == historical_id for row in rows)
        )

        n_a_row = next(
            (
                index
                for index, row in enumerate(rows)
                if row[3] == "N_A"
            ),
            None,
        )
        if n_a_row is None:
            raise RuntimeError(f"{training_key} N_A row missing")
        result_table.setCurrentCell(n_a_row, 0)
        app.processEvents()
        metric_code = rows[n_a_row][0]
        expected_evidence = evidence_by_path[
            f"/m3/releases/{historical_id}/metrics/{metric_code}/evidence"
        ]
        evidence_button.click()
        app.processEvents()
        rendered_evidence = _mapping(
            json.loads(evidence_detail.toPlainText()),
            field=f"{training_key}.rendered_evidence",
        )
        acceptance[f"{key}_n_a_status_style_distinct"] = (
            selected_status.text() == f"Metric status: N_A · {metric_code}"
            and selected_status.styleSheet() == M3_GUI_STATUS_STYLES["N_A"]
        )
        acceptance[f"{key}_evidence_drilldown_exact"] = (
            evidence_status.text()
            == f"Evidence: READY · {metric_code} · Release: {historical_id}"
            and rendered_evidence.get("release_id") == historical_id
            and rendered_evidence.get("metric_code") == metric_code
            and rendered_evidence.get("evidence_hash")
            == expected_evidence.get("evidence_hash")
        )

        transport.fail_next_evidence = True
        evidence_button.click()
        app.processEvents()
        acceptance[f"{key}_evidence_system_error_distinct"] = (
            evidence_status.text().startswith("Evidence: SYSTEM_ERROR ")
            and f"Release: {historical_id}" in evidence_status.text()
            and evidence_status.styleSheet()
            == M3_GUI_STATUS_STYLES["SYSTEM_ERROR"]
            and evidence_detail.toPlainText() == ""
        )
        evidence_button.click()
        app.processEvents()

        replay_input.setText("missing-historical-release")
        replay_button.click()
        app.processEvents()
        acceptance[f"{key}_historical_system_error_distinct"] = (
            navigation_status.text().startswith("Navigation: SYSTEM_ERROR ")
            and replay_identity.text()
            == (
                "Historical replay: SYSTEM_ERROR · "
                "Release: missing-historical-release"
            )
            and replay_identity.styleSheet()
            == M3_GUI_STATUS_STYLES["SYSTEM_ERROR"]
        )

        replay_input.setText(historical_id)
        replay_button.click()
        app.processEvents()
        product[training_key] = {
            "base_release_id": base_release_id,
            "historical_release_id": historical_id,
            "result_states": sorted(row_kinds),
            "n_a_metric_code": metric_code,
            "evidence_hash": expected_evidence.get("evidence_hash"),
            "historical_identity": replay_identity.text(),
        }

    acceptance["all_gui_routes_explicit_release_bound"] = all(
        path.startswith("/m3/releases/")
        and "/latest" not in path
        and "/current" not in path
        for path in transport.requested_paths
    )
    acceptance["historical_replay_mode_explicit_release_id"] = (
        root.property("tpaaM3HistoricalReplayMode") == "EXPLICIT_RELEASE_ID"
        and root.property("tpaaM3StatusMode") == "PROJECTED"
    )
    acceptance["api_release_evidence_prerequisite_complete"] = (
        api_release_evidence.get("task_complete") is True
        and api_release_evidence.get("failed_acceptance") == []
    )
    acceptance["api_workspace_prerequisite_complete"] = (
        api_workspace_evidence.get("task_complete") is True
        and api_workspace_evidence.get("failed_acceptance") == []
    )
    acceptance["publication_replay_prerequisite_complete"] = (
        replay_evidence.get("task_complete") is True
        and replay_evidence.get("failed_acceptance") == []
    )

    combined_source = (
        REPO_ROOT / "src" / "tpaa_gui" / "m3_workspace.py"
    ).read_text(encoding="utf-8") + (
        REPO_ROOT / "src" / "tpaa_gui" / "m3_status.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "tpaa_application",
        "tpaa_metric",
        "tpaa_observation",
        "tpaa_storage",
        "CatalogMetricEngine",
        "build_m3_metric_execution_plan",
        "sqlite3",
        "psycopg",
        '"/latest"',
        '"/current"',
    )
    acceptance["gui_projection_only_no_recompute_or_persistence"] = all(
        token not in combined_source for token in forbidden
    )

    root.close()
    app.processEvents()

    failed = sorted(key for key, passed in acceptance.items() if not passed)
    return {
        "schema": "TPAA_M3_GUI_003_STATUS_EVIDENCE_REPLAY_EVIDENCE_V1",
        "task_id": "M3-GUI-003",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "task_complete": not failed,
        "implementation_complete": not failed,
        "source_revision": _git_revision(),
        "logical_product": product,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "result_states_distinct": True,
            "system_error_distinct": True,
            "evidence_drilldown_release_bound": True,
            "historical_replay_explicit_release_id": True,
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
            "TPAA_M3_GUI_003_STATUS_EVIDENCE_REPLAY_CROSS_PLATFORM_EVIDENCE_V1"
        ),
        "task_id": "M3-GUI-003",
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
            "schema": "TPAA_M3_GUI_003_STATUS_EVIDENCE_REPLAY_EVIDENCE_V1",
            "task_id": "M3-GUI-003",
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
