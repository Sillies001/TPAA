#!/usr/bin/env python3
"""Capture deterministic offscreen W4 shell evidence at governed viewports."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tpaa_gui.design_system import (  # noqa: E402
    Theme,
    configure_application_font,
    theme_stylesheet,
)
from tpaa_gui.diagnostics import DiagnosticsSnapshot  # noqa: E402
from tpaa_gui.localization import install_chinese_localization  # noqa: E402
from tpaa_gui.page_contract import PAGE_CONTRACTS  # noqa: E402
from tpaa_gui.product_shell import create_product_workspace  # noqa: E402


class _NoRequestTransport:
    """Constructor-only transport: visual baselines never make product requests."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"visual capture made an unexpected request: {name}")


def _snapshot() -> DiagnosticsSnapshot:
    return DiagnosticsSnapshot(
        readiness="READY",
        backend_state="READY",
        mismatches=(),
        failure_code=None,
        expected=None,
        observed=None,
    )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(output_dir: Path, *, dpi: float) -> dict[str, object]:
    from PySide6 import QtCore, QtGui, QtWidgets

    output_dir.mkdir(parents=True, exist_ok=True)
    app: Any = QtWidgets.QApplication.instance() or QtWidgets.QApplication(["w4-visual"])
    configure_application_font(QtGui, app)
    app.setStyleSheet(theme_stylesheet(Theme.LIGHT, dpi))
    window = QtWidgets.QMainWindow()
    window.setObjectName("tpaaW4VisualWindow")
    window.setMinimumSize(1024, 720)
    root = create_product_workspace(
        QtCore,
        QtWidgets,
        window,
        transport=_NoRequestTransport(),
        diagnostics_provider=_snapshot,
        logical_dpi=dpi,
    )
    window.setCentralWidget(root)
    localization_filter = install_chinese_localization(QtCore, QtWidgets, app, window)
    records: list[dict[str, object]] = []
    for contract in PAGE_CONTRACTS:
        width, height, slot = 1440, 900, contract.slot
        index = next(
            index for index, contract in enumerate(PAGE_CONTRACTS) if contract.slot == slot
        )
        root._tpaa_navigation.setCurrentRow(index)
        window.resize(width, height)
        window.show()
        app.processEvents()
        output = output_dir / f"w4_{slot}_{width}x{height}_{int(dpi)}dpi.png"
        if not window.grab().save(str(output), "PNG"):
            raise RuntimeError(f"W4_VISUAL_CAPTURE_FAILED:{output.name}")
        page = root._tpaa_pages[index]
        scroll = page._tpaa_scroll
        content = page._tpaa_content
        clipped_controls = []
        for control_type in (
            QtWidgets.QPushButton,
            QtWidgets.QComboBox,
            QtWidgets.QLineEdit,
        ):
            for control in content.findChildren(control_type):
                if control.isVisible() and control.width() + 2 < control.minimumSizeHint().width():
                    clipped_controls.append(control.objectName() or control_type.__name__)
        records.append(
            {
                "slot": slot,
                "viewport": [width, height],
                "dpi": dpi,
                "image": output.name,
                "sha256": _digest(output),
                "navigation_visible": root._tpaa_navigation.isVisible(),
                "detail_drawer_visible": root._tpaa_detail_drawer.isVisible(),
                "status_bar_visible": root._tpaa_status_bar.isVisible(),
                "page_object": root._tpaa_pages[index].objectName(),
                "page_visible": page.isVisible(),
                "scroll_viewport_visible": scroll.viewport().isVisible(),
                "content_width": content.width(),
                "viewport_width": scroll.viewport().width(),
                "horizontal_overflow": scroll.horizontalScrollBar().maximum() > 0,
                "clipped_controls": sorted(set(clipped_controls)),
            }
        )
    app.removeEventFilter(localization_filter)
    window.close()
    return {
        "schema": "TPAA_CURRENT_GUI_RENDER_EVIDENCE_V2",
        "qt_platform": app.platformName(),
        "records": records,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dpi", type=float, default=96.0)
    args = parser.parse_args(argv)
    result = capture(args.output_dir, dpi=args.dpi)
    manifest = args.output_dir / f"w4_visual_{int(args.dpi)}dpi.json"
    manifest.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
