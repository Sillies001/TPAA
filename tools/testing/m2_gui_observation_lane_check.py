#!/usr/bin/env python3
"""Formal M2-GUI-002 observation-lane-aware presentation evidence."""

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
        M2_OBSERVATION_LANE_COUNTS,
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
            plugin_id=f"m2-gui-002-lane-probe:{definition.metric_code}:v1",
            plugin=probe,
        )
    batch = CatalogMetricEngine(plan, registry).execute(
        {
            definition.metric_code: {
                "input_token": f"M2-GUI-002::{definition.metric_code}",
            }
            for definition in plan.definitions
        },
        validate_runtime_contract=False,
    )
    snapshot = build_m2_release_snapshot(
        session_id=SESSION_ID,
        request_hash=_hash({"task": "M2-GUI-002", "session_id": SESSION_ID}),
        release_no=1,
        parent_release_id=None,
        plan=plan,
        routing=routing,
        batch=batch,
        context_snapshot={"context_version": "M2_GUI_LANE_V1"},
        world_snapshot={"world_hash": "3" * 64},
        identity_snapshot={"identity_hash": "4" * 64},
        provenance_snapshot={"source_revision": _git_revision()},
    )
    projection = snapshot.logical_membership()
    model = build_m2_foundation_navigation_model(projection)

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(["m2-gui-002-observation-lanes"])
    root = create_m2_foundation_workspace(
        QtCore,
        QtWidgets,
        None,
        release_projection=projection,
    )
    namespace = root.findChild(QtWidgets.QComboBox, "tpaaM2FoundationNamespace")
    lane = root.findChild(QtWidgets.QComboBox, "tpaaM2ObservationLane")
    navigator = root.findChild(QtWidgets.QListWidget, "tpaaM2FoundationNavigator")
    detail = root.findChild(QtWidgets.QPlainTextEdit, "tpaaM2FoundationDetail")
    summary = root.findChild(QtWidgets.QLabel, "tpaaM2ObservationLaneSummary")
    if any(
        widget is None
        for widget in (namespace, lane, navigator, detail, summary)
    ):
        raise RuntimeError("M2_GUI_002_WIDGET_MISSING")

    lane_counts: dict[str, int] = {}
    for value in M2_OBSERVATION_LANE_COUNTS:
        namespace.setCurrentText("ALL")
        lane.setCurrentText(value)
        app.processEvents()
        lane_counts[value] = navigator.count()

    combined_counts: dict[str, int] = {}
    combinations = (
        ("AIR", "AIRCRAFT_CAP_L1_OBSERVATION"),
        ("SNS", "SYSTEM_PERFORMANCE_OBSERVATION"),
        ("QA", "QUALITY_EVIDENCE_ONLY"),
    )
    for family, lane_name in combinations:
        namespace.setCurrentText(family)
        lane.setCurrentText(lane_name)
        app.processEvents()
        combined_counts[f"{family}:{lane_name}"] = navigator.count()

    namespace.setCurrentText("QA")
    lane.setCurrentText("QUALITY_EVIDENCE_ONLY")
    navigator.setCurrentRow(navigator.count() - 1)
    app.processEvents()
    evidence_only_detail = json.loads(detail.toPlainText())
    evidence_summary = summary.text()

    namespace.setCurrentText("AIR")
    lane.setCurrentText("AIRCRAFT_CAP_L1_OBSERVATION")
    navigator.setCurrentRow(0)
    app.processEvents()
    capability_detail = json.loads(detail.toPlainText())
    capability_summary = summary.text()

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

    acceptance = {
        "observation_lane_counts_exact": lane_counts
        == {
            "AIRCRAFT_CAP_L1_OBSERVATION": 3,
            "SYSTEM_PERFORMANCE_OBSERVATION": 24,
            "QUALITY_EVIDENCE_ONLY": 5,
        },
        "combined_family_lane_filters_exact": combined_counts
        == {
            "AIR:AIRCRAFT_CAP_L1_OBSERVATION": 3,
            "SNS:SYSTEM_PERFORMANCE_OBSERVATION": 21,
            "QA:QUALITY_EVIDENCE_ONLY": 5,
        },
        "capability_presentation_exact": (
            capability_detail["definition"]["metric_code"] == "P1-AIR-001"
            and capability_detail["observation_presentation"]["lane"]
            == "AIRCRAFT_CAP_L1_OBSERVATION"
            and capability_detail["observation_presentation"]["publication_route"]
            == "CAPABILITY_OBSERVATION"
            and capability_detail["observation_presentation"][
                "observation_record_expected"
            ]
            is True
            and capability_detail["observation_presentation"]["release_bound"]
            is True
        ),
        "quality_evidence_presentation_exact": (
            evidence_only_detail["definition"]["metric_code"]
            in {
                "P1-QA-001",
                "P1-QA-002",
                "P1-QA-005",
                "P1-QA-007",
                "P1-QA-008",
            }
            and evidence_only_detail["observation_presentation"]["lane"]
            == "QUALITY_EVIDENCE_ONLY"
            and evidence_only_detail["observation_presentation"][
                "publication_route"
            ]
            == "METRIC_INSTANCE_EVIDENCE_ONLY"
            and evidence_only_detail["observation_presentation"][
                "observation_record_expected"
            ]
            is False
            and evidence_only_detail["observation_presentation"]["release_bound"]
            is True
        ),
        "lane_summary_tracks_filter": (
            evidence_summary == "Observation lane: QUALITY_EVIDENCE_ONLY · visible=5"
            and capability_summary
            == "Observation lane: AIRCRAFT_CAP_L1_OBSERVATION · visible=3"
        ),
        "model_lane_counts_exact": all(
            len(model.by_observation_lane(name)) == expected
            for name, expected in M2_OBSERVATION_LANE_COUNTS.items()
        ),
        "release_identity_preserved_in_lane_detail": (
            capability_detail["release_id"] == snapshot.release_id
            and evidence_only_detail["manifest_hash"] == snapshot.manifest_hash
        ),
        "stable_lane_widgets_present": all(
            root.findChild(QtCore.QObject, object_name) is not None
            for object_name in (
                "tpaaM2FoundationFilters",
                "tpaaM2ObservationLane",
                "tpaaM2ObservationLaneSummary",
                "tpaaM2FoundationNavigator",
                "tpaaM2FoundationDetail",
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
        "schema": "TPAA_M2_GUI_002_OBSERVATION_LANE_PRESENTATION_EVIDENCE_V1",
        "task_id": "M2-GUI-002",
        "tracking_issue": 98,
        "status": "PASS" if complete else "FAIL",
        "task_complete": complete,
        "implementation_complete": complete,
        "source_revision": _git_revision(),
        "logical_product": {
            "release_id": model.release_id,
            "manifest_hash": model.manifest_hash,
            "lane_counts": lane_counts,
            "combined_counts": combined_counts,
            "capability_metric_code": (
                capability_detail["definition"]["metric_code"]
            ),
            "capability_route": (
                capability_detail["observation_presentation"]["publication_route"]
            ),
            "quality_evidence_metric_code": (
                evidence_only_detail["definition"]["metric_code"]
            ),
            "quality_evidence_route": (
                evidence_only_detail["observation_presentation"][
                    "publication_route"
                ]
            ),
        },
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "observation_lane_aware_presentation_only": True,
            "catalog_release_metadata_projected_without_reinterpretation": True,
            "release_projection_only": True,
            "database_access_executed": False,
            "business_metric_semantics_executed": False,
            "metric_recomputation_in_gui": False,
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
            "schema": (
                "TPAA_M2_GUI_002_OBSERVATION_LANE_PRESENTATION_EVIDENCE_V1"
            ),
            "task_id": "M2-GUI-002",
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
