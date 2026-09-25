#!/usr/bin/env python3
"""Real PySide6 M1 Batch 3 Desktop E2E evidence."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tpaa_gui import LocalBackendController, LocalBackendState, run_desktop  # noqa: E402

SCHEMA = "TPAA_M1_BATCH_3_DESKTOP_E2E_V1"
COMMON_TASKS = (
    "M1-GUI-001",
    "M1-GUI-002",
    "M1-GUI-003",
    "M1-GUI-004",
    "M1-GUI-005",
    "M1-GUI-006",
    "M1-GUI-007",
    "M1-TST-008",
)
PLATFORM_TASK = {"windows": "M1-PLAT-001", "linux": "M1-PLAT-002"}
FIXTURE_ID = "BF_M1_NOMINAL_V1"
EXPLICIT_BINDINGS = {
    "tpaaM1AircraftModelId": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "tpaaM1AircraftInstanceId": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    "tpaaM1SubjectEntityId": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    "tpaaM1CapabilityDimension": "TEST_EXPLICIT_CAPABILITY_DIMENSION",
    "tpaaM1CapabilityType": "TEST_EXPLICIT_CAPABILITY_TYPE",
}


def _platform_matches(expected: str) -> bool:
    return (expected == "windows" and sys.platform == "win32") or (
        expected == "linux" and sys.platform.startswith("linux")
    )


def _text(widget: Any) -> str:
    value = widget.text()
    return value if isinstance(value, str) else str(value)


def run(
    *,
    expected_platform: str,
    source_revision: str,
    evidence: Path,
    timeout_seconds: float = 45.0,
) -> int:
    """Run the same governed Desktop workflow on Windows and Linux."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        from PySide6 import QtCore, QtWidgets
    except ModuleNotFoundError as exc:
        payload = {
            "schema": SCHEMA,
            "tracking_issue": 89,
            "source_revision": source_revision,
            "platform": expected_platform,
            "status": "FAIL",
            "failed_acceptance": [*COMMON_TASKS, PLATFORM_TASK[expected_platform]],
            "failures": [f"PYSIDE6_DEPENDENCY_MISSING:{exc}"],
        }
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 2

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(["tpaa-m1-batch-3-desktop-e2e"])
    app.setQuitOnLastWindowClosed(True)  # type: ignore[attr-defined]

    controller = LocalBackendController(product_build_version="0.0.0")
    deadline = time.monotonic() + timeout_seconds
    failures: list[str] = []
    acceptance = {task: False for task in COMMON_TASKS}
    acceptance[PLATFORM_TASK[expected_platform]] = False
    captured: dict[str, object] = {}
    journey_started = False

    def fail(code: str) -> None:
        if not failures:
            failures.append(code)
        app.quit()

    timer = QtCore.QTimer()
    timer.setInterval(50)

    def find(name: str, kind: Any) -> Any:
        window = next(
            (
                widget
                for widget in QtWidgets.QApplication.topLevelWidgets()
                if widget.objectName() == "tpaaMainWindow"
            ),
            None,
        )
        if window is None:
            return None
        return window.findChild(kind, name)

    def poll() -> None:
        nonlocal journey_started
        if time.monotonic() >= deadline:
            fail("M1_DESKTOP_E2E_TIMEOUT")
            return

        window = next(
            (
                widget
                for widget in QtWidgets.QApplication.topLevelWidgets()
                if widget.objectName() == "tpaaMainWindow"
            ),
            None,
        )
        if window is None:
            return

        readiness = find("tpaaM1Readiness", QtWidgets.QLabel)
        run_button = find("tpaaM1RunJourney", QtWidgets.QPushButton)
        if readiness is None or run_button is None or _text(readiness) != "Readiness: READY":
            return

        if journey_started:
            return
        journey_started = True

        fixture = find("tpaaM1FixtureSelector", QtWidgets.QComboBox)
        if fixture is None or fixture.currentText() != FIXTURE_ID:
            fail("SESSION_BROWSER_FIXTURE_MISSING")
            return
        for object_name, value in EXPLICIT_BINDINGS.items():
            field = find(object_name, QtWidgets.QLineEdit)
            if field is None:
                fail(f"EXPLICIT_BINDING_FIELD_MISSING:{object_name}")
                return
            field.setText(value)

        run_button.click()

        workflow = find("tpaaM1WorkflowStatus", QtWidgets.QLabel)
        release_selector = find("tpaaM1ReleaseSelector", QtWidgets.QComboBox)
        baseline = find("tpaaM1Baseline", QtWidgets.QLabel)
        release_label = find("tpaaM1ReleaseIdentity", QtWidgets.QLabel)
        context_label = find("tpaaM1ContextIdentity", QtWidgets.QLabel)
        slider = find("tpaaM1TimelineSlider", QtWidgets.QSlider)
        cursor = find("tpaaM1CursorTime", QtWidgets.QLabel)
        metric_cursor = find("tpaaM1MetricCursor", QtWidgets.QLabel)
        evidence_cursor = find("tpaaM1EvidenceCursor", QtWidgets.QLabel)
        stages = find("tpaaM1StageLane", QtWidgets.QListWidget)
        metrics = find("tpaaM1MetricList", QtWidgets.QTableWidget)
        metric_detail = find("tpaaM1MetricDetail", QtWidgets.QPlainTextEdit)
        evidence_detail = find("tpaaM1EvidenceDetail", QtWidgets.QPlainTextEdit)
        replay_button = find("tpaaM1Replay", QtWidgets.QPushButton)
        replay_status = find("tpaaM1ReplayStatus", QtWidgets.QLabel)

        required = [
            workflow,
            release_selector,
            baseline,
            release_label,
            context_label,
            slider,
            cursor,
            metric_cursor,
            evidence_cursor,
            stages,
            metrics,
            metric_detail,
            evidence_detail,
            replay_button,
            replay_status,
        ]
        if any(widget is None for widget in required):
            fail("M1_WORKSPACE_OBJECT_MISSING")
            return

        workflow_text = _text(workflow)
        release_id = release_selector.currentText()
        acceptance["M1-GUI-001"] = (
            fixture.currentText() == FIXTURE_ID
            and bool(release_id)
            and workflow_text == "Workflow: PUBLISHED"
        )
        acceptance["M1-GUI-002"] = (
            _text(readiness) == "Readiness: READY"
            and "CB-1.4.0" in _text(baseline)
            and release_id in _text(release_label)
            and "Context:" in _text(context_label)
            and "unavailable" not in _text(context_label)
        )

        slider.setValue(500)
        cursor_value = _text(cursor).removeprefix("Cursor: ")
        acceptance["M1-GUI-003"] = (
            cursor_value
            and _text(metric_cursor) == f"Metric cursor: {cursor_value}"
            and _text(evidence_cursor) == f"Evidence cursor: {cursor_value}"
            and stages.currentRow() >= 0
        )
        acceptance["M1-GUI-004"] = stages.count() == 4

        metric_codes: list[str] = []
        metric_rows_complete = metrics.rowCount() == 5
        for row in range(metrics.rowCount()):
            row_values: list[str] = []
            for column in range(5):
                item = metrics.item(row, column)
                value = "" if item is None else item.text()
                row_values.append(value)
            metric_codes.append(row_values[0])
            metric_rows_complete = metric_rows_complete and all(
                value not in {"", "None"} for value in row_values
            )
        acceptance["M1-GUI-005"] = metric_rows_complete and metric_codes == [
            "P1-AIR-001",
            "P1-AIR-002",
            "P1-AIR-003",
            "P1-AIR-004",
            "P1-AIR-007",
        ]

        try:
            detail_json = json.loads(metric_detail.toPlainText())
            evidence_json = json.loads(evidence_detail.toPlainText())
        except json.JSONDecodeError:
            detail_json = {}
            evidence_json = {}
        acceptance["M1-GUI-006"] = (
            isinstance(detail_json, dict)
            and isinstance(evidence_json, dict)
            and detail_json.get("release_id") == release_id
            and evidence_json.get("release_id") == release_id
            and isinstance(detail_json.get("definition"), dict)
            and "definition_hash" in detail_json.get("definition", {})
            and (
                isinstance(evidence_json.get("refs"), list)
                or isinstance(evidence_json.get("details"), list)
                or "logical_hash" in evidence_json
            )
        )

        badge_names = (
            "tpaaM1StateNA",
            "tpaaM1StateINSUFFICIENT",
            "tpaaM1StateINVALID",
            "tpaaM1StateSYSTEMERROR",
        )
        badges = [find(name, QtWidgets.QLabel) for name in badge_names]
        styles = ["" if badge is None else badge.styleSheet() for badge in badges]
        acceptance["M1-GUI-007"] = (
            all(badge is not None for badge in badges)
            and len(set(styles)) == 4
            and all(styles)
        )

        replay_button.click()
        replay_text = _text(replay_status)
        acceptance["M1-TST-008"] = (
            all(acceptance[task] for task in COMMON_TASKS[:-1])
            and replay_text.startswith("Replay: PASS")
            and "exact=True" in replay_text
            and "fallback=False" in replay_text
        )
        acceptance[PLATFORM_TASK[expected_platform]] = (
            acceptance["M1-TST-008"] and _platform_matches(expected_platform)
        )

        captured.update(
            fixture_id=fixture.currentText(),
            release_id=release_id,
            metric_codes=metric_codes,
            stage_rows=[stages.item(i).text() for i in range(stages.count())],
            cursor=cursor_value,
            workflow_status=workflow_text,
            replay_status=replay_text,
            context_header=_text(context_label),
            release_header=_text(release_label),
        )

        timer.stop()
        window.close()
        QtCore.QTimer.singleShot(0, app.quit)

    timer.timeout.connect(poll)
    timer.start()

    try:
        exit_code = run_desktop(
            ["tpaa-m1-batch-3-desktop-e2e"],
            show=True,
            backend=controller,
        )
    except Exception as exc:  # noqa: BLE001 - evidence records fail-closed boundary
        failures.append(f"{type(exc).__name__}:{exc}")
        exit_code = 2

    status = controller.status
    cleanup_ok = (
        status.state is LocalBackendState.EXITED and not status.ready and status.port is None
    )
    if exit_code != 0:
        failures.append(f"GUI_EXIT_{exit_code}")
    if not cleanup_ok:
        failures.append("BACKEND_CLEANUP_FAILED")

    failed_acceptance = sorted(task for task, passed in acceptance.items() if not passed)
    result_status = "PASS" if not failures and not failed_acceptance else "FAIL"
    logical_product = {
        "fixture_id": captured.get("fixture_id"),
        "release_id": captured.get("release_id"),
        "metric_codes": captured.get("metric_codes"),
        "stage_rows": captured.get("stage_rows"),
        "cursor": captured.get("cursor"),
        "workflow_status": captured.get("workflow_status"),
        "replay_status": captured.get("replay_status"),
        "context_header": captured.get("context_header"),
        "release_header": captured.get("release_header"),
    }
    payload: dict[str, object] = {
        "schema": SCHEMA,
        "tracking_issue": 89,
        "task_ids": [*COMMON_TASKS, PLATFORM_TASK[expected_platform]],
        "source_revision": source_revision,
        "platform": expected_platform,
        "platform_matches_expected": _platform_matches(expected_platform),
        "fixture_id": FIXTURE_ID,
        "status": result_status,
        "acceptance": acceptance,
        "failed_acceptance": failed_acceptance,
        "failures": failures,
        "logical_product": logical_product,
        "backend_cleanup": cleanup_ok,
    }
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if result_status == "PASS" else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-platform", choices=("windows", "linux"), required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=45.0)
    args = parser.parse_args(argv)
    return run(
        expected_platform=args.expected_platform,
        source_revision=args.source_revision,
        evidence=args.evidence,
        timeout_seconds=args.timeout,
    )


if __name__ == "__main__":
    raise SystemExit(main())
