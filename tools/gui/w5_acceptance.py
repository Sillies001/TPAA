"""Run the W5 real-file to exact-evidence local Desktop acceptance chain."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import platform
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from tools.testing.ed2_p1_full_input_builder import build_full_p1_request_contract
from tpaa_gui.design_system import Theme, configure_application_font, theme_stylesheet
from tpaa_gui.local_backend import LocalBackendController
from tpaa_gui.product_shell import create_product_workspace
from tpaa_gui.w5_projection import (
    build_session_overview,
    observation_quality_rows,
    verify_exact_replay,
)
from tpaa_security import ASSIGNMENT_SCHEMA, sign_assignment

SESSION_ID = "c2000000-0000-4000-8000-000000000001"
AIRCRAFT_ID = "c2000000-0000-4000-8000-000000000002"
CONTEXT_ID = "c2000000-0000-4000-8000-000000000003"
MODEL_ID = "c2000000-0000-4000-8000-000000000007"
INSTANCE_ID = "c2000000-0000-4000-8000-000000000008"
ENTITY_ID = "c2000000-0000-4000-8000-000000000009"


def _payload(
    result: tuple[int, dict[str, object]],
    *,
    allowed: tuple[int, ...] = (200,),
) -> dict[str, object]:
    status, payload = result
    if status not in allowed:
        raise RuntimeError(f"W5_ACCEPTANCE_HTTP_{status}:{payload!r}")
    return payload


def _request_manifest() -> dict[str, object]:
    payload = build_full_p1_request_contract(aircraft_id=AIRCRAFT_ID)
    payload.update(
        {
            "evaluation_context": {
                "context_id": CONTEXT_ID,
                "session_id": SESSION_ID,
                "context_version": "W5-CONTEXT-1.0.0",
                "revision_no": 1,
                "rule_set_version": "W5-RULES-1.0.0",
                "metric_profile_version": "W5-P1-PROFILE-1.0.0",
                "status": "ACTIVE",
            },
            "publication_identity": {
                "aircraft_model_id": MODEL_ID,
                "aircraft_instance_id": INSTANCE_ID,
                "subject_entity_id": ENTITY_ID,
                "capability_dimension": "AIRCRAFT_FLIGHT",
                "capability_type": "KINEMATIC_ENERGY_CONTROL",
                "aircraft_type_code": "W5-TYPE",
                "aircraft_model_name": "W5 Acceptance Aircraft",
                "aircraft_internal_code": "W5-AIRCRAFT",
                "entity_alias": "W5-SUBJECT",
            },
            "expected_version_token": 0,
            "parent_release_id": None,
        }
    )
    return payload


def run(work_root: Path, evidence_path: Path) -> dict[str, object]:
    work_root = work_root.resolve(strict=False)
    evidence_path = evidence_path.resolve(strict=False)
    work_root.mkdir(parents=True, exist_ok=False)
    desktop_data = work_root / "desktop-data"
    desktop_data.mkdir()
    identity_key_name = "TPAA_W5_ACCEPTANCE_IDENTITY_KEY"
    identity_key = "w5-local-acceptance-only-key"
    now = datetime.now(UTC)
    identity_payload: dict[str, object] = {
        "schema": ASSIGNMENT_SCHEMA,
        "key_id": identity_key_name,
        "account_id": getpass.getuser(),
        "device_id": platform.node(),
        "subject": "c2000000-0000-4000-8000-000000000010",
        "roles": ["INSTRUCTOR"],
        "scopes": ["*"],
        "issued_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
    }
    identity_path = desktop_data / "desktop-identity.json"
    identity_path.write_text(
        json.dumps(
            {
                **identity_payload,
                "signature": sign_assignment(identity_payload, identity_key.encode("utf-8")),
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    os.environ[identity_key_name] = identity_key
    os.environ["TPAA_DESKTOP_IDENTITY_FILE"] = str(identity_path)
    os.environ["TPAA_DESKTOP_IDENTITY_KEY_REF"] = f"env://{identity_key_name}"
    manifest_path = work_root / "W5_P1_REQUEST.json"
    raw = json.dumps(
        _request_manifest(),
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    manifest_path.write_bytes(raw)
    controller = LocalBackendController(
        product_build_version="1.0.0",
        data_root=desktop_data,
        startup_timeout_seconds=30.0,
    )
    try:
        controller.start()
        staged = _payload(
            controller.source_request_bytes(
                "/api/v1/sources/p1-request/stage",
                data=manifest_path.read_bytes(),
                content_type="application/json",
            ),
            allowed=(201,),
        )
        staged_payload = staged.get("payload")
        if not isinstance(staged_payload, dict):
            raise RuntimeError("W5_ACCEPTANCE_STAGED_PAYLOAD_INVALID")
        digest = hashlib.sha256(raw).hexdigest()
        job = _payload(
            controller.job_request_json(
                "POST",
                "/jobs",
                body={"command": "BUILD_P1_RELEASE", "payload": staged_payload},
                headers={"Idempotency-Key": f"w5-acceptance-{digest}"},
            ),
            allowed=(200, 202),
        )
        if job.get("status") != "SUCCEEDED":
            raise RuntimeError(f"W5_ACCEPTANCE_JOB_NOT_SUCCEEDED:{job!r}")
        products = _payload(
            cast(
                tuple[int, dict[str, object]],
                controller.product_request_json(
                    "GET", "/api/v1/discovery/products/P1_RELEASE"
                ),
            )
        )
        raw_items = products.get("items")
        if not isinstance(raw_items, list):
            raise RuntimeError("W5_ACCEPTANCE_RELEASE_DISCOVERY_INVALID")
        release_id = next(
            (
                str(item["exact_id"])
                for item in raw_items
                if isinstance(item, dict)
                and isinstance(item.get("metadata"), dict)
                and item["metadata"].get("session_id") == SESSION_ID
            ),
            None,
        )
        if release_id is None:
            raise RuntimeError("W5_ACCEPTANCE_RELEASE_NOT_FOUND")
        base = f"/m1/releases/{release_id}"
        release = _payload(controller.m1_request_json("GET", base))
        context = _payload(controller.m1_request_json("GET", f"{base}/context"))
        topology = _payload(controller.m1_request_json("GET", f"{base}/topology"))
        metrics = _payload(controller.m1_request_json("GET", f"{base}/metrics"))
        observations = _payload(controller.m1_request_json("GET", f"{base}/observations"))
        world = _payload(controller.m1_request_json("GET", f"{base}/world-graph"))
        replay = _payload(controller.m1_request_json("POST", f"{base}/replay"))
        projection = build_session_overview(
            release=release,
            context=context,
            topology=topology,
            metrics_payload=metrics,
            observations_payload=observations,
            world_graph=world,
        )
        replay_status = verify_exact_replay(replay, release_id)
        eligibility = observation_quality_rows(projection)
        from PySide6 import QtCore, QtGui, QtTest, QtWidgets

        app = cast(
            "QtWidgets.QApplication",
            QtWidgets.QApplication.instance()
            or QtWidgets.QApplication(["tpaa-w5-gui-acceptance"]),
        )
        configure_application_font(QtGui, app)
        app.setStyleSheet(theme_stylesheet(Theme.LIGHT, 96.0))
        window = QtWidgets.QMainWindow()
        workspace = create_product_workspace(
            QtCore,
            QtWidgets,
            window,
            transport=controller,
            diagnostics_provider=lambda: controller.diagnostics,
        )
        window.setCentralWidget(workspace)
        window.resize(1440, 900)
        window.show()
        app.processEvents()

        def exercise_page(
            row: int,
            refresh_name: str,
            load_name: str,
            status_name: str,
        ) -> dict[str, object]:
            workspace._tpaa_navigation.setCurrentRow(row)
            app.processEvents()
            page = workspace._tpaa_pages[row]
            refresh_button = page.findChild(QtWidgets.QPushButton, refresh_name)
            load_button = page.findChild(QtWidgets.QPushButton, load_name)
            QtTest.QTest.mouseClick(
                refresh_button,
                QtCore.Qt.MouseButton.LeftButton,
            )
            QtTest.QTest.mouseClick(
                load_button,
                QtCore.Qt.MouseButton.LeftButton,
            )
            app.processEvents()
            status_widget = page.findChild(QtWidgets.QLabel, status_name)
            status_text = status_widget.text()
            if "FAILURE" in status_text or "ERROR" in status_text:
                raise RuntimeError(f"W5_GUI_TASK_FAILED:{status_name}:{status_text}")
            screenshot = work_root / f"{status_name}_1440x900.png"
            if not window.grab().save(str(screenshot), "PNG"):
                raise RuntimeError(f"W5_GUI_CAPTURE_FAILED:{status_name}")
            return {
                "page": f"P{row + 1:02d}",
                "status": status_text,
                "screenshot": str(screenshot),
            }

        role_button = workspace.findChild(
            QtWidgets.QPushButton,
            "tpaaApplyRoleView",
        )
        QtTest.QTest.mouseClick(role_button, QtCore.Qt.MouseButton.LeftButton)
        app.processEvents()
        gui_tasks = [
            exercise_page(
                1,
                "tpaaP02RefreshReleases",
                "tpaaP02LoadOverview",
                "tpaaP02Status",
            ),
            exercise_page(
                2,
                "tpaaP03RefreshReleases",
                "tpaaP03LoadReplay",
                "tpaaP03Status",
            ),
            exercise_page(
                12,
                "tpaaP13RefreshGovernance",
                "tpaaP13LoadGovernance",
                "tpaaP13Status",
            ),
        ]
        final_gate = workspace._tpaa_pages[12].findChild(
            QtWidgets.QLabel,
            "tpaaP13FinalDecision",
        )
        if final_gate.property("decision") != "NO_GO":
            raise RuntimeError("W5_GUI_LOCAL_FINAL_GATE_MUST_BE_NO_GO")
        window.close()
        app.processEvents()
        result: dict[str, object] = {
            "schema": "TPAA_W5_ACCEPTANCE_EVIDENCE_V1",
            "status": "PASS",
            "real_file_import": True,
            "manifest_path": str(manifest_path),
            "manifest_sha256": digest,
            "source_document_count": staged.get("source_document_count"),
            "source_families": staged.get("source_families"),
            "job_id": job.get("job_id"),
            "job_status": job.get("status"),
            "release_id": release_id,
            "release_status": projection.release_status,
            "session_id": projection.session_id,
            "episode_id": projection.episode_id,
            "stage_count": len(projection.stages),
            "aircraft_metric_count": len(projection.aircraft_metrics),
            "mission_system_metric_count": len(projection.mission_system_metrics),
            "reference_quality_metric_count": len(projection.reference_quality_metrics),
            "observation_count": len(projection.observations),
            "eligibility_count": len(eligibility),
            "world_product_count": len(projection.world_products),
            "historical_replay_status": replay_status,
            "current_latest_fallback_used": replay.get(
                "current_latest_fallback_used", False
            ),
            "gui_role_default_page": "P03",
            "gui_tasks": gui_tasks,
            "gui_final_release_decision": final_gate.property("decision"),
            "trace_major_interactions": [
                "P01_IMPORT_AND_PUBLISH",
                "P02_LOAD_EXACT_OVERVIEW",
                "P03_LOAD_EXACT_REPLAY",
                "P13_LOAD_GOVERNANCE_AND_FINAL_GATE",
            ],
            "trace_major_interaction_count": 4,
            "pushed": False,
            "production_deployed": False,
        }
    finally:
        controller.shutdown()
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.work_root, args.evidence), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
