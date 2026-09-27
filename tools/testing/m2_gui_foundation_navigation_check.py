#!/usr/bin/env python3
"""Formal M2-GUI-001 Basic Flight foundation navigation evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
SESSION_ID = "11111111-1111-4111-8111-111111111111"


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


def _hash(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtCore, QtWidgets

    from tpaa_gui import (
        build_m2_foundation_navigation_model,
        create_m2_foundation_workspace,
    )
    from tpaa_metric import (
        CatalogMetricEngine,
        M2MetricPluginRequest,
        MetricPluginRegistry,
        build_m2_metric_execution_plan,
    )
    from tpaa_observation import (
        build_m2_publication_routing_plan,
        build_m2_release_snapshot,
    )

    plan = build_m2_metric_execution_plan(AUTHORITY_ROOT)
    routing = build_m2_publication_routing_plan(AUTHORITY_ROOT)

    def probe(request: M2MetricPluginRequest) -> dict[str, object]:
        return {
            "metric_code": request.definition.metric_code,
            "input_token": request.input_payload["input_token"],
        }

    registry = MetricPluginRegistry()
    for definition in plan.definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"m2-gui-001-navigation-probe:{definition.metric_code}:v1",
            plugin=probe,
        )
    batch = CatalogMetricEngine(plan, registry).execute(
        {
            definition.metric_code: {
                "input_token": f"M2-GUI-001::{definition.metric_code}",
            }
            for definition in plan.definitions
        },
        validate_runtime_contract=False,
    )
    snapshot = build_m2_release_snapshot(
        session_id=SESSION_ID,
        request_hash=_hash({"task": "M2-GUI-001", "session_id": SESSION_ID}),
        release_no=1,
        parent_release_id=None,
        plan=plan,
        routing=routing,
        batch=batch,
        context_snapshot={"context_version": "M2_GUI_FOUNDATION_V1"},
        world_snapshot={"world_hash": "3" * 64},
        identity_snapshot={"identity_hash": "4" * 64},
        provenance_snapshot={"source_revision": _git_revision()},
    )
    projection = snapshot.logical_membership()
    model = build_m2_foundation_navigation_model(projection)

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(["m2-gui-001-foundation-navigation"])
    root = create_m2_foundation_workspace(
        QtCore,
        QtWidgets,
        None,
        release_projection=projection,
    )
    namespace = root.findChild(QtWidgets.QComboBox, "tpaaM2FoundationNamespace")
    navigator = root.findChild(QtWidgets.QListWidget, "tpaaM2FoundationNavigator")
    detail = root.findChild(QtWidgets.QPlainTextEdit, "tpaaM2FoundationDetail")
    status = root.findChild(QtWidgets.QLabel, "tpaaM2FoundationNavigationStatus")
    if any(widget is None for widget in (namespace, navigator, detail, status)):
        raise RuntimeError("M2_GUI_001_WIDGET_MISSING")

    namespace_counts: dict[str, int] = {}
    first_codes: dict[str, str] = {}
    for value in ("ALL", "QA", "AIR", "SNS"):
        namespace.setCurrentText(value)
        app.processEvents()
        namespace_counts[value] = navigator.count()
        first = navigator.item(0)
        first_codes[value] = "" if first is None else first.text()

    namespace.setCurrentText("SNS")
    navigator.setCurrentRow(navigator.count() - 1)
    app.processEvents()
    selected_detail = json.loads(detail.toPlainText())

    source = (REPO_ROOT / "src" / "tpaa_gui" / "m2_workspace.py").read_text(
        encoding="utf-8"
    )
    forbidden_tokens = (
        "tpaa_storage",
        "tpaa_metric",
        "tpaa_world",
        "sqlite",
        "psycopg",
        "compute_representative_metrics",
        "build_m2_metric_execution_plan",
    )
    projection_only = not any(token in source for token in forbidden_tokens)

    acceptance = {
        "release_projection_exact_foundation_32": (
            len(model.items) == 32
            and model.metric_codes == snapshot.metric_codes
        ),
        "namespace_counts_exact": namespace_counts
        == {"ALL": 32, "QA": 8, "AIR": 3, "SNS": 21},
        "namespace_navigation_exact": (
            first_codes["QA"].startswith("P1-QA-")
            and first_codes["AIR"].startswith("P1-AIR-")
            and first_codes["SNS"].startswith("P1-SNS-")
        ),
        "selected_metric_is_release_bound": (
            selected_detail["release_id"] == snapshot.release_id
            and selected_detail["manifest_hash"] == snapshot.manifest_hash
            and selected_detail["definition"]["metric_code"] == "P1-SNS-021"
        ),
        "selected_definition_hash_bound": (
            len(selected_detail["definition"]["definition_hash"]) == 64
        ),
        "stable_workspace_objects_present": (
            root.objectName() == "tpaaM2FoundationWorkspace"
            and all(
                root.findChild(QtCore.QObject, object_name) is not None
                for object_name in (
                    "tpaaM2FoundationHeader",
                    "tpaaM2FoundationCount",
                    "tpaaM2FoundationNamespace",
                    "tpaaM2FoundationNavigator",
                    "tpaaM2FoundationDetail",
                    "tpaaM2FoundationNavigationStatus",
                )
            )
        ),
        "navigation_status_selected": (
            status.text() == "Navigation: SELECTED P1-SNS-021"
        ),
        "gui_module_projection_only": projection_only,
        "release_manifest_bound": len(model.manifest_hash) == 64,
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)
    root.close()
    complete = not failed
    return {
        "schema": "TPAA_M2_GUI_001_FOUNDATION_NAVIGATION_EVIDENCE_V1",
        "task_id": "M2-GUI-001",
        "tracking_issue": 98,
        "status": "PASS" if complete else "FAIL",
        "task_complete": complete,
        "implementation_complete": complete,
        "source_revision": _git_revision(),
        "logical_product": {
            "release_id": model.release_id,
            "manifest_hash": model.manifest_hash,
            "metric_codes": list(model.metric_codes),
            "namespace_counts": namespace_counts,
            "first_codes": first_codes,
            "selected_metric_code": selected_detail["definition"]["metric_code"],
            "selected_definition_hash": (
                selected_detail["definition"]["definition_hash"]
            ),
        },
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "basic_flight_foundation_navigation_only": True,
            "release_projection_only": True,
            "database_access_executed": False,
            "business_metric_semantics_executed": False,
            "metric_recomputation_in_gui": False,
            "observation_lane_presentation_deferred_to_m2_gui_002": True,
            "status_error_ux_deferred_to_m2_gui_003": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    try:
        payload = verify()
        return_code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M2_GUI_001_FOUNDATION_NAVIGATION_EVIDENCE_V1",
            "task_id": "M2-GUI-001",
            "tracking_issue": 98,
            "status": "FAIL",
            "task_complete": False,
            "implementation_complete": False,
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        return_code = 2
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.evidence is not None:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
