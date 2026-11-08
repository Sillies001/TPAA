#!/usr/bin/env python3
"""Capture v33 shared-shell fidelity screenshots (G4 post-closure correction evidence).

Read-only after bootstrap: renders the rebuilt shell across the three themes and the
two Ribbon states at the reference resolution, plus the V25 theme manager and a V26
frame. Avoids the batch-registration write path so it does not depend on the flaky
concurrent-write window exercised by the G4 acceptance loop.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

sys.path.insert(0, str(ROOT / "tools" / "gui"))
import g4_webengine_acceptance as g4  # type: ignore[import-not-found]  # noqa: E402


def _capture(workspace: Any, path: Path) -> None:
    from PySide6.QtCore import QEventLoop, QTimer

    path.parent.mkdir(parents=True, exist_ok=True)
    # WebEngine 渲染进程异步绘制：驻留事件循环，待页面完成绘制后再抓图。
    for _ in range(6):
        loop = QEventLoop()
        QTimer.singleShot(120, loop.quit)
        loop.exec()
    if not workspace.grab().save(str(path), "PNG"):
        raise RuntimeError(f"SCREENSHOT_FAILED:{path}")


def _set_theme(view: Any, theme: str) -> None:
    g4._evaluate(view, f"document.documentElement.setAttribute('data-tpaa-theme','{theme}'); true")


def _toggle_ribbon(view: Any) -> None:
    g4._evaluate(view, "document.querySelector('[data-action=\"toggle-ribbon\"]')?.click(); true")


def _nav(view: Any, module: str, target: str) -> None:
    from PySide6.QtCore import QEventLoop, QTimer

    g4._evaluate(view, f"document.querySelector('[data-module=\"{module}\"]')?.click(); true")
    loop = QEventLoop()
    QTimer.singleShot(150, loop.quit)
    loop.exec()
    g4._evaluate(view, f"document.querySelector('[data-view=\"{target}\"]')?.click(); true")


def run(output_dir: Path, *, scale: float) -> dict[str, object]:
    from PySide6.QtWidgets import QApplication

    from tpaa_gui.local_backend import LocalBackendController, LocalBackendState
    from tpaa_gui.webengine_shell import create_webengine_workspace

    app = QApplication.instance() or QApplication([sys.argv[0]])
    workspace = None
    captures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="tpaa-shell-fidelity-") as temporary:
        data_root = Path(temporary).resolve()
        g4._identity(data_root / "desktop-identity.json")
        # 不预置 SQLite：由后端子进程按自身 authority 完成 bootstrap，避免父子清单不一致。
        controller = LocalBackendController(
            product_build_version="1.0.0",
            data_root=data_root,
            child_stderr=None,
            startup_timeout_seconds=30.0,
        )
        try:
            started = controller.start()
            if started.state is not LocalBackendState.READY:
                raise RuntimeError(f"BACKEND_NOT_READY:{started}")
            status, bootstrap = controller.product_request_json("GET", "/api/v1/gui/bootstrap")
            provenance = bootstrap.get("provenance")
            if status != 200 or not isinstance(provenance, dict) or provenance.get("core_baseline") != "CB-1.9.0":
                raise RuntimeError(f"BOOTSTRAP_INVALID:{status}")
            binding = controller.webengine_binding()
            workspace = create_webengine_workspace(None, binding)
            workspace.resize(1600, 900)
            workspace.show()
            view = workspace._tpaa_web_view
            if view is None:
                raise RuntimeError("WEBENGINE_VIEW_MISSING")

            g4._wait_for(
                view,
                "document.querySelectorAll('[data-module]:disabled').length",
                lambda value: value == 0,
                label="authorization",
            )

            def snap(name: str) -> None:
                target = output_dir / name
                _capture(workspace, target)
                captures.append(name)

            # V01 default (graphite, ribbon expanded)
            snap("shell_v01_graphite_ribbon_expanded.png")
            # Ribbon collapsed
            _toggle_ribbon(view)
            snap("shell_v01_graphite_ribbon_collapsed.png")
            _toggle_ribbon(view)
            # Themes on V25 theme manager
            _nav(view, "support", "V25")
            g4._wait_for(view, "document.querySelector('.themeChoice') !== null", lambda v: v is True, label="v25")
            for theme in ("graphite", "tactical", "light"):
                _set_theme(view, theme)
                snap(f"shell_v25_{theme}.png")
            # V26 frame (N/A controlled)
            _set_theme(view, "graphite")
            _nav(view, "training", "V26")
            g4._wait_for(view, "document.querySelector('#main-content') !== null", lambda v: v is True, label="v26")
            snap("shell_v26_graphite.png")
        finally:
            if workspace is not None:
                workspace.close()
            controller.shutdown()
    _ = app
    return {"schema": "TPAA_V33_SHELL_FIDELITY_CAPTURE_V1", "scale": scale, "captures": captures}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--scale", choices=("1.0", "1.5"), default="1.0")
    args = parser.parse_args(argv)
    result = run(args.output_dir.resolve(), scale=float(args.scale))
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
