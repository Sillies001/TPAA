#!/usr/bin/env python3
"""M3-GUI-002 product-family and applicability-aware Desktop qualification."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
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


def _table_rows(table: Any, columns: int) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in range(table.rowCount()):
        values: list[str] = []
        for column in range(columns):
            item = table.item(row, column)
            if item is None:
                raise RuntimeError(f"table row {row} column {column} is incomplete")
            values.append(cast(Any, item).text())
        rows.append(values)
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
        M3_GUI_FAMILY_PRESENTATION,
        M3_GUI_PRODUCT_FAMILY_CODES,
        M3_GUI_TRAINING_KEYS,
        create_m3_workspace_navigation,
    )

    api_evidence = verify_api_workspace()
    if api_evidence.get("status") != "PASS":
        raise RuntimeError("M3-API-002 prerequisite qualification did not pass")
    api_product = _mapping(
        api_evidence.get("logical_product"),
        field="api logical product",
    )

    baseline = _load(
        REPO_ROOT / "docs" / "baseline" / "SDIB-1.2" / "M3_TASK_BASELINE.json"
    )
    family_authority = _mapping(
        baseline.get("family_applicability"),
        field="M3 family_applicability",
    )
    baseline_meanings: dict[str, str] = {}
    for family_code in M3_GUI_PRODUCT_FAMILY_CODES:
        contract = _mapping(
            family_authority.get(family_code),
            field=f"family_applicability.{family_code}",
        )
        meaning = contract.get("family_meaning")
        if not isinstance(meaning, str) or not meaning:
            raise RuntimeError(f"{family_code} family meaning missing")
        baseline_meanings[family_code] = meaning

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
                if path == f"/m3/releases/{release_id}/workspace":
                    return 200, cast(dict[str, Any], workspace)
            return 404, {
                "outcome": "SYSTEM_ERROR",
                "error": {"code": "RELEASE_NOT_FOUND"},
            }

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(["tpaa-m3-gui-002-check"])
    transport = ProjectionTransport()
    root = create_m3_workspace_navigation(
        QtCore,
        QtWidgets,
        None,
        transport=transport,
        release_ids_by_training=release_ids_by_training,
    )
    selector = root.findChild(QtWidgets.QComboBox, "tpaaM3TrainingSelector")
    product_table = root.findChild(
        QtWidgets.QTableWidget,
        "tpaaM3ProductFamilyPresentation",
    )
    applicability_table = root.findChild(
        QtWidgets.QTableWidget,
        "tpaaM3MetricApplicability",
    )
    status_label = root.findChild(QtWidgets.QLabel, "tpaaM3NavigationStatus")
    if any(
        widget is None
        for widget in (selector, product_table, applicability_table, status_label)
    ):
        raise RuntimeError("M3 GUI family/applicability automation surface incomplete")

    selector = cast(Any, selector)
    product_table = cast(Any, product_table)
    applicability_table = cast(Any, applicability_table)
    status_label = cast(Any, status_label)

    acceptance: dict[str, bool] = {}
    product: dict[str, object] = {}

    acceptance["family_meanings_match_frozen_baseline"] = all(
        M3_GUI_FAMILY_PRESENTATION[family_code][1]
        == baseline_meanings[family_code]
        for family_code in M3_GUI_PRODUCT_FAMILY_CODES
    )
    acceptance["family_labels_and_meanings_distinct"] = (
        len(
            {
                M3_GUI_FAMILY_PRESENTATION[family_code][0]
                for family_code in M3_GUI_PRODUCT_FAMILY_CODES
            }
        )
        == 7
        and len(set(baseline_meanings.values())) == 7
    )

    for training_key in M3_GUI_TRAINING_KEYS:
        selector.setCurrentText(training_key)
        app.processEvents()

        workspace = _mapping(
            api_product.get(training_key),
            field=f"{training_key}.workspace",
        )
        families_raw = workspace.get("families")
        metrics_raw = workspace.get("metrics")
        if not isinstance(families_raw, list) or not isinstance(metrics_raw, list):
            raise RuntimeError(f"{training_key} workspace product rows missing")

        expected_product_rows: list[list[str]] = []
        for raw_family in families_raw:
            family = _mapping(raw_family, field=f"{training_key}.family")
            family_code = family.get("family_code")
            if family_code not in M3_GUI_PRODUCT_FAMILY_CODES:
                continue
            if not isinstance(family_code, str):
                raise RuntimeError(f"{training_key} family code invalid")
            label, meaning = M3_GUI_FAMILY_PRESENTATION[family_code]
            expected_product_rows.append(
                [
                    family_code,
                    label,
                    meaning,
                    str(family.get("applicable_count")),
                    str(family.get("not_applicable_count")),
                ]
            )

        expected_metric_rows: list[list[str]] = []
        projected_non_applicable: list[str] = []
        for raw_metric in metrics_raw:
            metric = _mapping(raw_metric, field=f"{training_key}.metric")
            family_code = metric.get("family_code")
            if family_code not in M3_GUI_PRODUCT_FAMILY_CODES:
                continue
            if not isinstance(family_code, str):
                raise RuntimeError(f"{training_key} metric family invalid")
            applicability = _mapping(
                metric.get("applicability"),
                field=f"{training_key}.metric.applicability",
            )
            applicable = applicability.get("applicable")
            if not isinstance(applicable, bool):
                raise RuntimeError(f"{training_key} applicable flag invalid")
            reasons = applicability.get("reason_codes")
            instances = metric.get("instances")
            if not isinstance(reasons, list) or not all(
                isinstance(item, str) and item for item in reasons
            ):
                raise RuntimeError(f"{training_key} applicability reasons invalid")
            if not isinstance(instances, list):
                raise RuntimeError(f"{training_key} instances invalid")
            system_type = applicability.get("system_type")
            if system_type is not None and not isinstance(system_type, str):
                raise RuntimeError(f"{training_key} system type invalid")
            metric_code = metric.get("metric_code")
            if not isinstance(metric_code, str):
                raise RuntimeError(f"{training_key} metric code invalid")
            if not applicable:
                projected_non_applicable.append(metric_code)
            label, _ = M3_GUI_FAMILY_PRESENTATION[family_code]
            expected_metric_rows.append(
                [
                    metric_code,
                    family_code,
                    label,
                    "YES" if applicable else "NO",
                    ", ".join(cast(list[str], reasons)) if reasons else "—",
                    cast(str, system_type) if system_type is not None else "—",
                    str(len(instances)) if applicable else "0 · no observation",
                ]
            )

        rendered_product_rows = _table_rows(product_table, 5)
        rendered_metric_rows = _table_rows(applicability_table, 7)

        key = training_key.lower()
        acceptance[f"{key}_seven_product_families_visible"] = (
            {row[0] for row in rendered_product_rows}
            == set(M3_GUI_PRODUCT_FAMILY_CODES)
            and len(rendered_product_rows) == 7
        )
        acceptance[f"{key}_family_projection_exact"] = (
            rendered_product_rows == expected_product_rows
        )
        acceptance[f"{key}_metric_applicability_projection_exact"] = (
            rendered_metric_rows == expected_metric_rows
            and len(rendered_metric_rows) == 87
        )

        rendered_by_metric = {row[0]: row for row in rendered_metric_rows}
        acceptance[f"{key}_non_applicable_no_fake_observation"] = all(
            metric_code in rendered_by_metric
            and rendered_by_metric[metric_code][3] == "NO"
            and rendered_by_metric[metric_code][6] == "0 · no observation"
            and next(
                (
                    metric
                    for metric in metrics_raw
                    if isinstance(metric, dict)
                    and metric.get("metric_code") == metric_code
                ),
                {},
            ).get("instances")
            == []
            for metric_code in projected_non_applicable
        )
        acceptance[f"{key}_workspace_ready"] = (
            status_label.text()
            == f"Navigation: READY · {training_key} · 116 metrics"
        )
        product[training_key] = {
            "release_id": workspace.get("release_id"),
            "product_families": rendered_product_rows,
            "metric_applicability": rendered_metric_rows,
        }

    module_source = (
        REPO_ROOT / "src" / "tpaa_gui" / "m3_workspace.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "tpaa_application",
        "tpaa_metric",
        "tpaa_observation",
        "tpaa_storage",
        "CatalogMetricEngine",
        "applicability_mode",
        "allowed_system_types",
        "required_product_semantics",
        "SYSTEM_TYPE_EXACT",
        "SYSTEM_TYPE_SET",
        "PRODUCT_CAPABILITY",
        "sqlite3",
        "psycopg",
    )
    acceptance["gui_uses_projected_applicability_not_authority_rules"] = all(
        token not in module_source for token in forbidden
    )
    acceptance["gui_applicability_mode_projected"] = (
        root.property("tpaaM3ApplicabilityMode") == "PROJECTED"
    )
    acceptance["historical_release_routes_only"] = all(
        path.startswith("/m3/releases/")
        and "/latest" not in path
        and "/current" not in path
        for path in transport.requested_paths
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
        "schema": "TPAA_M3_GUI_002_FAMILY_APPLICABILITY_EVIDENCE_V1",
        "task_id": "M3-GUI-002",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "task_complete": not failed,
        "implementation_complete": not failed,
        "source_revision": _git_revision(),
        "logical_product": product,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "product_families": list(M3_GUI_PRODUCT_FAMILY_CODES),
            "applicability_consumed_from_api_projection": True,
            "applicability_recomputed_by_gui": False,
            "non_applicable_fake_observation_rendered": False,
            "database_access_executed_by_gui": False,
            "business_metric_recomputation_executed_by_gui": False,
            "historical_release_id_explicit": True,
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
        "schema": "TPAA_M3_GUI_002_FAMILY_APPLICABILITY_CROSS_PLATFORM_EVIDENCE_V1",
        "task_id": "M3-GUI-002",
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
            "schema": "TPAA_M3_GUI_002_FAMILY_APPLICABILITY_EVIDENCE_V1",
            "task_id": "M3-GUI-002",
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
