from __future__ import annotations

import os
from typing import Any, cast

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tpaa_gui.diagnostics import DiagnosticsSnapshot
from tpaa_gui.localization import (
    install_chinese_localization,
    translate_visible_text,
)
from tpaa_gui.product_shell import create_product_workspace


def _snapshot() -> DiagnosticsSnapshot:
    return DiagnosticsSnapshot(
        readiness="READY",
        backend_state="READY",
        mismatches=(),
        failure_code=None,
        expected=None,
        observed=None,
    )


def test_critical_desktop_language_is_chinese_and_identifiers_are_preserved() -> None:
    assert translate_visible_text("Application shell initialized") == "应用程序界面已初始化"
    assert translate_visible_text("Training Session List") == "训练会话列表"
    assert translate_visible_text("Final Release Gate") == "最终发布门禁"
    assert translate_visible_text("Readiness: READY") == "就绪状态: 就绪"
    assert translate_visible_text("ACTIVE") == "有效"
    assert translate_visible_text("release_id") == "release_id"
    assert translate_visible_text("SHA-256") == "SHA-256"
    assert translate_visible_text("NO_GO") == "NO_GO"


def test_real_product_workspace_navigation_is_localized() -> None:
    pytest.importorskip("PySide6")
    from PySide6 import QtCore, QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(["tpaa-localization-test"])
    root = create_product_workspace(
        QtCore,
        QtWidgets,
        None,
        transport=cast(Any, object()),
        diagnostics_provider=_snapshot,
    )
    event_filter = install_chinese_localization(QtCore, QtWidgets, app, root)
    navigation = root._tpaa_navigation
    assert navigation.item(0).text() == "P01  Training Session List"
    assert (
        navigation.itemDelegate().displayText(navigation.item(0).text(), QtCore.QLocale())
        == "P01  训练会话列表"
    )
    assert (
        navigation.itemDelegate().displayText(navigation.item(12).text(), QtCore.QLocale())
        == "P13  画像／版本／发布／模型治理"
    )
    assert root.findChild(QtWidgets.QLabel, "tpaaP03Title").text() == ("P03  交互式证据／架次复盘")
    assert root.findChild(QtWidgets.QPushButton, "tpaaP13LoadGovernance").text() == (
        "加载精确治理快照"
    )
    subject_lane = root.findChild(QtWidgets.QComboBox, "tpaaP10SubjectLane")
    assert subject_lane.currentText() == "HUMAN"
    assert (
        subject_lane.itemDelegate().displayText(subject_lane.currentText(), QtCore.QLocale())
        == "个人"
    )
    app.removeEventFilter(event_filter)
    root.close()
