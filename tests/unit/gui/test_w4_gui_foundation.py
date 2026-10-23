from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, cast

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tpaa_gui.design_system import Theme, scaled_metrics, theme_stylesheet
from tpaa_gui.diagnostics import DiagnosticsSnapshot
from tpaa_gui.m1_workspace import create_m1_workspace
from tpaa_gui.page_contract import PAGE_CONTRACTS, page_contract, validate_page_contracts
from tpaa_gui.product_shell import create_product_workspace
from tpaa_gui.shell_state import ApplicationShellState, ShellStateError


def _snapshot() -> DiagnosticsSnapshot:
    return DiagnosticsSnapshot(
        readiness="READY",
        backend_state="READY",
        mismatches=(),
        failure_code=None,
        expected=None,
        observed=None,
    )


def test_w4_page_contract_matches_governed_json() -> None:
    validate_page_contracts()
    assert tuple(item.slot for item in PAGE_CONTRACTS) == tuple(
        f"P{index:02d}" for index in range(1, 14)
    )
    assert page_contract("P06").key == "AIRCRAFT_CAPABILITY_TWIN"
    assert page_contract("P08").key == "CONTEXT_ADJUSTMENT"
    assert page_contract("P12").key == "DATA_QUALITY_ELIGIBILITY"
    contract_path = Path("docs/gui/W4_PAGE_CONTRACT.json")
    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    assert [item["slot"] for item in payload["slots"]] == [
        item.slot for item in PAGE_CONTRACTS
    ]
    assert [item["key"] for item in payload["slots"]] == [
        item.key for item in PAGE_CONTRACTS
    ]


def test_shell_state_propagates_selection_and_fails_closed() -> None:
    state = ApplicationShellState()
    events: list[frozenset[str]] = []
    state.subscribe(lambda _selection, changed: events.append(changed))
    state.select_session("SESSION-001")
    state.select_episode("EPISODE-001")
    state.select_stage("STAGE-001")
    state.select_page("P08")
    assert state.selection.page_id == "P08"
    assert state.selection.stage_id == "STAGE-001"
    assert events[-1] == frozenset({"page_id"})
    state.select_session(None)
    assert state.selection.episode_id is None
    assert state.selection.stage_id is None
    with pytest.raises(ShellStateError, match="EPISODE_REQUIRES_SESSION"):
        state.select_episode("EPISODE-ORPHAN")
    with pytest.raises(ShellStateError, match="TIME_RANGE_INCOMPLETE"):
        state.update(time_start_us=1)


def test_design_metrics_cover_100_to_200_percent_dpi() -> None:
    metrics = [scaled_metrics(dpi) for dpi in (96.0, 120.0, 144.0, 192.0)]
    assert [item.control_height for item in metrics] == [34, 42, 51, 68]
    assert [item.table_row_height for item in metrics] == [32, 40, 48, 64]
    assert scaled_metrics(240.0) == metrics[-1]
    for theme in Theme:
        style = theme_stylesheet(theme, 144.0)
        assert "QListWidget::item" in style
        assert "border: 2px solid" in style


def test_w4_visual_baseline_manifest_matches_images() -> None:
    baseline = Path("docs/gui/baselines")
    manifest = json.loads(
        (baseline / "w4_visual_96dpi.json").read_text(encoding="utf-8")
    )
    assert manifest["schema"] == "TPAA_W4_VISUAL_EVIDENCE_V1"
    assert [record["slot"] for record in manifest["records"]] == [
        "P01",
        "P08",
        "P12",
    ]
    for record in manifest["records"]:
        image = baseline / record["image"]
        assert image.is_file()
        assert hashlib.sha256(image.read_bytes()).hexdigest() == record["sha256"]


def test_real_qt_shell_has_13_independent_scrollable_pages_and_no_fixture() -> None:
    pytest.importorskip("PySide6")
    from PySide6 import QtCore, QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(["w4-test"])
    root = create_product_workspace(
        QtCore,
        QtWidgets,
        None,
        transport=cast(Any, object()),
        diagnostics_provider=_snapshot,
    )
    root.resize(1440, 900)
    root.show()
    app.processEvents()
    assert root._tpaa_navigation.count() == 13
    assert root._tpaa_stack.count() == 13
    assert root._tpaa_row_to_page == tuple(range(13))
    assert root.findChild(QtWidgets.QComboBox, "tpaaM1FixtureSelector") is None
    for index, contract in enumerate(PAGE_CONTRACTS):
        root._tpaa_navigation.setCurrentRow(index)
        app.processEvents()
        assert root._tpaa_shell_state.selection.page_id == contract.slot
        page = root._tpaa_pages[index]
        assert page.objectName() == contract.object_name
        assert page._tpaa_scroll.widgetResizable() is True
    effects = root.findChild(QtWidgets.QTableWidget, "tpaaM6FactorEffects")
    assert effects is not None
    assert effects.columnWidth(1) >= 240
    assert effects.horizontalHeaderItem(1).text() == "Association contribution"
    root.close()


def test_m1_qualification_form_rows_have_readable_spacing() -> None:
    pytest.importorskip("PySide6")
    from PySide6 import QtCore, QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(["w4-m1-test"])
    root = create_m1_workspace(
        QtCore,
        QtWidgets,
        None,
        transport=cast(Any, object()),
        diagnostics_provider=_snapshot,
    )
    browser = root.findChild(QtWidgets.QGroupBox, "tpaaM1SessionBrowser")
    assert browser is not None
    layout = cast(QtWidgets.QGridLayout, browser.layout())
    assert layout.verticalSpacing() >= 10
    for row in range(7):
        assert layout.rowMinimumHeight(row) >= 32
    for object_name in (
        "tpaaM1AircraftModelId",
        "tpaaM1AircraftInstanceId",
        "tpaaM1SubjectEntityId",
        "tpaaM1CapabilityDimension",
        "tpaaM1CapabilityType",
    ):
        widget = root.findChild(QtWidgets.QLineEdit, object_name)
        assert widget is not None and widget.minimumHeight() >= 30
    root.close()
    app.processEvents()
