#!/usr/bin/env python3
"""G10 view-closure WebEngine acceptance over CB-1.15.0 (V09 data-driven + V11 P3 controlled)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tools" / "gui"))
import g4_webengine_acceptance as g4  # type: ignore[import-not-found]  # noqa: E402
import g6_webengine_acceptance as g6  # type: ignore[import-not-found]  # noqa: E402
import g7_webengine_acceptance as g7  # type: ignore[import-not-found]  # noqa: E402

AUTHORITY = ROOT / "baseline" / "CB-1.15.0" / "canonical"
EVIDENCE_DIR = ROOT / "evidence" / "gui-g10-v33-webengine"
EVIDENCE_JSON = ROOT / "evidence" / "gui-g10-v33-webengine.json"

OVERLAP_SCRIPT = """(() => {
  const rects = [];
  document.querySelectorAll('#main-content .p').forEach((e) => rects.push(e.getBoundingClientRect()));
  let overlaps = 0;
  for (let i = 0; i < rects.length; i++) for (let j = i + 1; j < rects.length; j++) {
    const a = rects[i], b = rects[j];
    const ix = Math.min(a.right, b.right) - Math.max(a.left, b.left);
    const iy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
    if (ix > 0.5 && iy > 0.5) overlaps++;
  }
  const main = document.getElementById('main-content')?.getBoundingClientRect();
  const overflow = main ? (main.right > window.innerWidth + 0.5 || main.bottom > window.innerHeight + 0.5) : true;
  return JSON.stringify({ overlapCount: overlaps, overflow: overflow,
    themeAttr: document.documentElement.getAttribute('data-tpaa-theme') || '' });
})()"""


class G10WebEngineAcceptanceError(RuntimeError):
    pass


def _capture(workspace: Any, path: Path) -> None:
    from PySide6.QtCore import QEventLoop, QTimer

    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(6):
        loop = QEventLoop()
        QTimer.singleShot(120, loop.quit)
        loop.exec()
    if not workspace.grab().save(str(path), "PNG"):
        raise G10WebEngineAcceptanceError(f"SCREENSHOT_FAILED:{path}")


def _box_model(view: Any) -> dict[str, Any]:
    result = g4._evaluate(view, OVERLAP_SCRIPT)
    if not isinstance(result, str) or not result:
        raise G10WebEngineAcceptanceError(f"BOX_MODEL_EVAL_INVALID:{result!r}")
    decoded = json.loads(result)
    if not isinstance(decoded, dict):
        raise G10WebEngineAcceptanceError(f"BOX_MODEL_EVAL_INVALID:{decoded!r}")
    return decoded


def _goto(view: Any, view_id: str) -> None:
    module = "equipment" if view_id in ("V09", "V10", "V11", "V12", "V13", "V14", "V15", "V16") else "training"
    if view_id in ("V17", "V18", "V22"):
        module = "support"
    g4._evaluate(view, f"document.querySelector('[data-module=\"{module}\"]')?.click(); true")
    g4._evaluate(view, f"document.querySelector('[data-view=\"{view_id}\"]')?.click(); true")
    g4._wait_for(view, "document.querySelectorAll('#main-content .p').length", lambda v: v >= 4, label=view_id)
    time.sleep(0.6)


def run() -> dict[str, object]:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication

    from tpaa_gui.local_backend import LocalBackendController, LocalBackendState
    from tpaa_gui.webengine_shell import create_webengine_workspace

    app = QApplication.instance() or QApplication([sys.argv[0]])
    workspace = None
    captures: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="tpaa-g10-webengine-") as temporary:
        data_root = Path(temporary).resolve()
        g4._identity(data_root / "desktop-identity.json")
        g7.AUTHORITY = ROOT / "baseline" / "CB-1.14.0" / "canonical"
        g7._seed_database(data_root)
        controller = LocalBackendController(
            product_build_version="1.0.0", data_root=data_root,
            child_stderr=None, startup_timeout_seconds=30.0,
        )
        try:
            started = controller.start()
            if started.state is not LocalBackendState.READY:
                raise G10WebEngineAcceptanceError(f"BACKEND_NOT_READY:{started}")
            status, bootstrap = controller.product_request_json("GET", "/api/v1/gui/bootstrap")
            catalog = bootstrap.get("catalog", {})
            if status != 200 or not isinstance(catalog, dict) or catalog.get("catalog_version") != "CB-1.14.0:1.0.0":
                raise G10WebEngineAcceptanceError(f"BOOTSTRAP_INVALID:{status}:{catalog!r}")
            binding = controller.webengine_binding()
            workspace = create_webengine_workspace(None, binding)
            workspace.show()
            view = workspace._tpaa_web_view
            if view is None:
                raise G10WebEngineAcceptanceError("WEBENGINE_VIEW_MISSING")
            for width, height in ((1600, 900), (1280, 720)):
                if width == 1600:
                    g6._resize_and_load(workspace, view, width, height)
                    g4._evaluate(view, "window.dispatchEvent(new Event('resize')); true")
                    g4._wait_for(view, "document.querySelectorAll('[data-module]:disabled').length", lambda v: v == 0, label="authorization")
                    g4._wait_for(view, "document.querySelectorAll('.v29BatchRow').length", lambda v: v >= 3, label="overview")
                else:
                    workspace.resize(width, height)
                    g4._evaluate(view, "window.dispatchEvent(new Event('resize')); true")
                    for _ in range(4):
                        loop = QEventLoop()
                        QTimer.singleShot(150, loop.quit)
                        loop.exec()
                for view_id, label in (("V09", "v09"), ("V11", "v11")):
                    _goto(view, view_id)
                    values = {
                        "panels": g4._evaluate(view, "document.querySelectorAll('#main-content .p').length"),
                        "chips": g4._evaluate(view, "document.querySelectorAll('#main-content .v26Chip').length"),
                        "state_codes": g4._evaluate(view, "document.querySelectorAll('#main-content .state-code').length"),
                    }
                    if values["panels"] != 4:
                        raise G10WebEngineAcceptanceError(f"CONTENT_CHECK_FAILED:{label}:{values!r}")
                    for theme in ("graphite", "tactical", "light"):
                        for collapsed in (False, True):
                            expanded = g4._evaluate(view, "document.getElementById('app')?.classList.contains('ribbon-collapsed') === false")
                            if expanded == collapsed:
                                g4._evaluate(view, "document.querySelector('[data-action=\"toggle-ribbon\"]')?.click(); true")
                            g4._evaluate(view, "document.querySelector('[data-module=\"support\"]')?.click(); true")
                            g4._evaluate(view, "document.querySelector('[data-view=\"V25\"]')?.click(); true")
                            g4._wait_for(view, "document.querySelectorAll('.themeChoice').length", lambda v: v == 3, label="v25")
                            g4._evaluate(view, f"document.querySelector('[data-theme=\"{theme}\"]')?.click(); true")
                            _goto(view, view_id)
                            box = _box_model(view)
                            if box["overlapCount"] != 0 or box["overflow"] is not False:
                                raise G10WebEngineAcceptanceError(f"BOX_MODEL_FAIL:{width}x{height}:{view_id}:{theme}:{box!r}")
                            name = f"g10_{label}_{width}x{height}_{theme}_ribbon_{'collapsed' if collapsed else 'expanded'}.png"
                            target = EVIDENCE_DIR / name
                            _capture(workspace, target)
                            captures.append({
                                "file": target.relative_to(ROOT).as_posix(),
                                "resolution": f"{width}x{height}",
                                "view": view_id,
                                "theme": theme,
                                "ribbon": "collapsed" if collapsed else "expanded",
                                "box_model": box,
                                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                            })
        finally:
            if workspace is not None:
                workspace.close()
            controller.shutdown()
    _ = app
    result: dict[str, object] = {
        "schema": "TPAA_G10_V33_WEBENGINE_ACCEPTANCE_V1",
        "status": "PASS",
        "core_baseline": "CB-1.15.0",
        "views": ["V09", "V11"],
        "captures": captures,
        "box_model_no_overlap": True,
        "exact_origin": binding.origin,
        "release_claim": False,
    }
    EVIDENCE_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    os.environ.setdefault("POLARS_SKIP_CPU_CHECK", "1")
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
    os.environ["QT_SCALE_FACTOR"] = "1"
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-extensions --force-device-scale-factor=1"
    os.environ["TPAA_AUTHORITY_ROOT"] = str(AUTHORITY.resolve())
    try:
        result = run()
    except (OSError, ValueError, KeyError, G10WebEngineAcceptanceError) as exc:
        print(f"G10_WEBENGINE_ACCEPTANCE_FAIL {exc}", file=sys.stderr)
        return 2
    captures = result["captures"]
    assert isinstance(captures, list)
    print(f"G10_WEBENGINE_ACCEPTANCE_PASS captures={len(captures)} box_model_no_overlap=True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
