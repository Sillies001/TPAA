#!/usr/bin/env python3
"""Formal M2-GUI-003 applicability/quality/error-state UX evidence."""

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
        build_m2_metric_presentation_state,
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
            plugin_id=f"m2-gui-003-state-probe:{definition.metric_code}:v1",
            plugin=probe,
        )
    batch = CatalogMetricEngine(plan, registry).execute(
        {
            definition.metric_code: {
                "input_token": f"M2-GUI-003::{definition.metric_code}",
            }
            for definition in plan.definitions
        },
        validate_runtime_contract=False,
    )
    snapshot = build_m2_release_snapshot(
        session_id=SESSION_ID,
        request_hash=_hash({"task": "M2-GUI-003", "session_id": SESSION_ID}),
        release_no=1,
        parent_release_id=None,
        plan=plan,
        routing=routing,
        batch=batch,
        context_snapshot={"context_version": "M2_GUI_STATE_V1"},
        world_snapshot={"world_hash": "3" * 64},
        identity_snapshot={"identity_hash": "4" * 64},
        provenance_snapshot={"source_revision": _git_revision()},
    )

    presentation_payloads: dict[str, dict[str, object]] = {
        "P1-SNS-001": {
            "metric_code": "P1-SNS-001",
            "applicable": False,
            "system_type": "IRST",
            "applicability_reason_codes": ["WRONG_SENSOR_TYPE"],
            "instances": [],
        },
        "P1-SNS-002": {
            "metric_code": "P1-SNS-002",
            "applicable": True,
            "instances": [
                {
                    "status": "N_A",
                    "reason_codes": ["NO_ELIGIBLE_OPPORTUNITIES"],
                }
            ],
        },
        "P1-SNS-003": {
            "metric_code": "P1-SNS-003",
            "applicable": True,
            "instances": [
                {
                    "status": "INSUFFICIENT_DATA",
                    "reason_codes": ["REFERENCE_MATCH_COVERAGE_INSUFFICIENT"],
                }
            ],
        },
        "P1-SNS-004": {
            "metric_code": "P1-SNS-004",
            "applicable": True,
            "instances": [
                {
                    "status": "INVALID",
                    "reason_codes": ["REFERENCE_RANGE_INVALID"],
                }
            ],
        },
        "P1-SNS-005": {
            "metric_code": "P1-SNS-005",
            "system_error_code": "M2_METRIC_PLUGIN_FAILED",
        },
    }
    classified = {
        code: build_m2_metric_presentation_state(payload)
        for code, payload in presentation_payloads.items()
    }

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(["m2-gui-003-state-ux"])
    root = create_m2_foundation_workspace(
        QtCore,
        QtWidgets,
        None,
        release_projection=snapshot.logical_membership(),
        presentation_states=presentation_payloads,
    )
    namespace = root.findChild(QtWidgets.QComboBox, "tpaaM2FoundationNamespace")
    lane = root.findChild(QtWidgets.QComboBox, "tpaaM2ObservationLane")
    navigator = root.findChild(QtWidgets.QListWidget, "tpaaM2FoundationNavigator")
    badge = root.findChild(QtWidgets.QLabel, "tpaaM2MetricState")
    reasons = root.findChild(QtWidgets.QLabel, "tpaaM2MetricStateReasons")
    detail = root.findChild(QtWidgets.QPlainTextEdit, "tpaaM2FoundationDetail")
    if any(
        widget is None
        for widget in (namespace, lane, navigator, badge, reasons, detail)
    ):
        raise RuntimeError("M2_GUI_003_WIDGET_MISSING")

    namespace.setCurrentText("SNS")
    lane.setCurrentText("SYSTEM_PERFORMANCE_OBSERVATION")
    app.processEvents()

    rendered: dict[str, dict[str, object]] = {}
    for metric_code in presentation_payloads:
        row = next(
            (
                index
                for index in range(navigator.count())
                if navigator.item(index).text() == metric_code
            ),
            -1,
        )
        if row < 0:
            raise RuntimeError(f"M2_GUI_003_METRIC_NOT_VISIBLE:{metric_code}")
        navigator.setCurrentRow(row)
        app.processEvents()
        rendered[metric_code] = {
            "badge": badge.text(),
            "style": badge.styleSheet(),
            "reasons": reasons.text(),
            "detail": json.loads(detail.toPlainText())["metric_state"],
        }

    wrong_sensor = classified["P1-SNS-001"]
    na_state = classified["P1-SNS-002"]
    insufficient = classified["P1-SNS-003"]
    invalid = classified["P1-SNS-004"]
    system_error = classified["P1-SNS-005"]
    styles = {str(item["style"]) for item in rendered.values()}

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

    def release_bound_state_projection_is_exact(code: str) -> bool:
        detail_value = rendered[code]["detail"]
        return (
            isinstance(detail_value, dict)
            and detail_value.get("metric_code") == code
            and detail_value.get("release_bound") is True
        )

    acceptance = {
        "wrong_sensor_applicability_distinct_from_na": (
            wrong_sensor.kind == "WRONG_SENSOR_NOT_APPLICABLE"
            and wrong_sensor.kind != na_state.kind
            and wrong_sensor.reason_codes == ("WRONG_SENSOR_TYPE",)
            and wrong_sensor.system_type == "IRST"
        ),
        "na_state_preserved_with_reason": (
            na_state.kind == "N_A"
            and na_state.reason_codes == ("NO_ELIGIBLE_OPPORTUNITIES",)
        ),
        "insufficient_data_state_preserved_with_reason": (
            insufficient.kind == "INSUFFICIENT_DATA"
            and insufficient.reason_codes
            == ("REFERENCE_MATCH_COVERAGE_INSUFFICIENT",)
        ),
        "invalid_state_preserved": invalid.kind == "INVALID",
        "system_error_distinct_from_invalid": (
            system_error.kind == "SYSTEM_ERROR"
            and system_error.kind != invalid.kind
            and system_error.system_error_code == "M2_METRIC_PLUGIN_FAILED"
        ),
        "five_state_renderings_are_visually_distinct": len(styles) == 5,
        "state_badges_match_classification": all(
            str(rendered[code]["badge"]).startswith(f"State: {state.kind}")
            for code, state in classified.items()
        ),
        "release_bound_state_projection_exact": all(
            release_bound_state_projection_is_exact(code)
            for code in classified
        ),
        "reason_codes_remain_visible": (
            "WRONG_SENSOR_TYPE" in str(rendered["P1-SNS-001"]["reasons"])
            and "NO_ELIGIBLE_OPPORTUNITIES"
            in str(rendered["P1-SNS-002"]["reasons"])
            and "REFERENCE_MATCH_COVERAGE_INSUFFICIENT"
            in str(rendered["P1-SNS-003"]["reasons"])
        ),
        "stable_state_widgets_present": all(
            root.findChild(QtCore.QObject, object_name) is not None
            for object_name in (
                "tpaaM2MetricState",
                "tpaaM2MetricStateReasons",
                "tpaaM2FoundationDetail",
                "tpaaM2FoundationNavigator",
            )
        ),
        "gui_module_projection_only": not any(
            token in source for token in forbidden_tokens
        ),
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)
    root.close()
    complete = not failed
    return {
        "schema": "TPAA_M2_GUI_003_STATE_UX_EVIDENCE_V1",
        "task_id": "M2-GUI-003",
        "tracking_issue": 98,
        "status": "PASS" if complete else "FAIL",
        "task_complete": complete,
        "implementation_complete": complete,
        "source_revision": _git_revision(),
        "logical_product": {
            "release_id": snapshot.release_id,
            "manifest_hash": snapshot.manifest_hash,
            "state_kinds": {
                code: state.kind for code, state in classified.items()
            },
            "reason_codes": {
                code: list(state.reason_codes)
                for code, state in classified.items()
            },
            "system_error_code": system_error.system_error_code,
            "wrong_sensor_system_type": wrong_sensor.system_type,
            "rendered_badges": {
                code: rendered[code]["badge"] for code in classified
            },
        },
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "applicability_quality_error_state_ux_only": True,
            "release_bound_presentation_state_only": True,
            "wrong_sensor_not_collapsed_into_na": True,
            "system_error_not_collapsed_into_invalid": True,
            "database_access_executed": False,
            "business_metric_semantics_executed": False,
            "metric_recomputation_in_gui": False,
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
            "schema": "TPAA_M2_GUI_003_STATE_UX_EVIDENCE_V1",
            "task_id": "M2-GUI-003",
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
