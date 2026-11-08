#!/usr/bin/env python3
"""G12 full visual matrix: 26 views x 3 themes x Ribbon two states over CB-1.17.0."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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
import g6_webengine_acceptance as g6  # type: ignore[import-not-found]  # noqa: E402
import g7_webengine_acceptance as g7  # type: ignore[import-not-found]  # noqa: E402
import g8_webengine_acceptance as g8  # type: ignore[import-not-found]  # noqa: E402

AUTHORITY = ROOT / "baseline" / "CB-1.17.0" / "canonical"
EVIDENCE_DIR = ROOT / "evidence" / "gui-g12-v33-visual-matrix"
EVIDENCE_JSON = ROOT / "evidence" / "gui-g12-v33-visual-matrix.json"
REGISTRY = ROOT / "docs" / "gui" / "demo-v33" / "V33_FINAL_VIEW_REGISTRY.json"


def _registry_views() -> tuple[tuple[str, str, str], ...]:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = payload.get("views")
    if not isinstance(rows, list) or len(rows) != 26:
        raise G12VisualMatrixError("VIEW_REGISTRY_INVALID")
    result: list[tuple[str, str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise G12VisualMatrixError("VIEW_REGISTRY_ROW_INVALID")
        result.append((str(row["module"]), str(row["id"]), str(row["title"])))
    return tuple(result)

BOX_SCRIPT = """(() => {
  const rects = [];
  document.querySelectorAll('#main-content .p, #main-content .v29Overview').forEach((e) => rects.push(e.getBoundingClientRect()));
  let overlaps = 0;
  for (let i = 0; i < rects.length; i++) for (let j = i + 1; j < rects.length; j++) {
    const a = rects[i], b = rects[j];
    const ix = Math.min(a.right, b.right) - Math.max(a.left, b.left);
    const iy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
    if (ix > 0.5 && iy > 0.5) overlaps++;
  }
  const controls = Array.from(document.querySelectorAll('#main-content button, #main-content select, #main-content input'));
  const clippedControls = controls.filter((e) => {
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && (e.scrollWidth > e.clientWidth + 1 || e.scrollHeight > e.clientHeight + 1);
  }).length;
  const mainElement = document.getElementById('main-content');
  const main = mainElement?.getBoundingClientRect();
  const overflow = main ? (main.right > window.innerWidth + 0.5 || main.bottom > window.innerHeight + 0.5) : true;
  return JSON.stringify({
    currentView: document.getElementById('app')?.dataset.currentView || null,
    title: mainElement?.getAttribute('aria-label') || null,
    overlapCount: overlaps,
    clippedControls: clippedControls,
    overflow: overflow
  });
})()"""


class G12VisualMatrixError(RuntimeError):
    pass


def _capture(workspace: Any, path: Path) -> None:
    from PySide6.QtCore import QEventLoop, QTimer

    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(3):
        loop = QEventLoop()
        QTimer.singleShot(90, loop.quit)
        loop.exec()
    if not workspace.grab().save(str(path), "PNG"):
        raise G12VisualMatrixError(f"SCREENSHOT_FAILED:{path}")


def _box(view: Any) -> dict[str, Any]:
    result = g4._evaluate(view, BOX_SCRIPT)
    if not isinstance(result, str) or not result:
        raise G12VisualMatrixError(f"BOX_MODEL_EVAL_INVALID:{result!r}")
    decoded = json.loads(result)
    if not isinstance(decoded, dict):
        raise G12VisualMatrixError(f"BOX_MODEL_EVAL_INVALID:{decoded!r}")
    return decoded


def _goto(view: Any, module: str, view_id: str) -> None:
    if view_id == "V24":
        g4._evaluate(view, "document.querySelector('[data-module=\"training\"]')?.click(); true")
        g4._evaluate(view, "document.querySelector('[data-view=\"V08\"]')?.click(); true")
        g4._wait_for(view, "document.querySelectorAll('[data-wp-event]').length", lambda v: v >= 2, label="v08")
        g4._evaluate(view, "document.querySelector('[data-wp-event][data-cluster=\"true\"]')?.click(); true")
        try:
            g4._wait_for(
                view,
                "document.querySelector('[data-wp-event].selected')?.dataset.cluster || null",
                lambda v: v == "true",
                label="v24-cluster-selection",
            )
            g4._wait_for(view, "document.querySelector('[data-wp-coattack]') !== null", lambda v: v is True, label="v24-entry")
        except Exception as exc:
            diagnostics = g4._evaluate(
                view,
                "JSON.stringify({current:document.getElementById('app')?.dataset.currentView,"
                "events:Array.from(document.querySelectorAll('[data-wp-event]')).map((b)=>({id:b.dataset.wpEvent,cluster:b.dataset.cluster,mark:b.querySelector('strong')?.textContent,selected:b.classList.contains('selected')})),"
                "text:document.getElementById('main-content')?.innerText?.slice(-1800)})",
            )
            raise G12VisualMatrixError(f"V24_CONTROLLED_ENTRY_MISSING:{diagnostics}") from exc
        g4._evaluate(view, "document.querySelector('[data-wp-coattack]')?.click(); true")
        g4._wait_for(view, "document.getElementById('app')?.dataset.currentView", lambda v: v == "V24", label="v24")
        return
    g4._evaluate(view, f"document.querySelector('[data-module=\"{module}\"]')?.click(); true")
    g4._evaluate(view, f"document.querySelector('[data-view=\"{view_id}\"]')?.click(); true")
    g4._wait_for(view, "document.getElementById('app')?.dataset.currentView", lambda v: v == view_id, label=view_id)


def run() -> dict[str, object]:
    from PySide6.QtWidgets import QApplication

    from tpaa_gui.local_backend import LocalBackendController, LocalBackendState
    from tpaa_gui.webengine_shell import create_webengine_workspace

    app = QApplication.instance() or QApplication([sys.argv[0]])
    workspace = None
    captures: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="tpaa-g12-visual-") as temporary:
        data_root = Path(temporary).resolve()
        g4._identity(data_root / "desktop-identity.json")
        g7.AUTHORITY = AUTHORITY
        g8.AUTHORITY = AUTHORITY
        g7._seed_database(data_root)
        g8._seed_database(data_root)
        controller = LocalBackendController(
            product_build_version="1.0.0", data_root=data_root,
            child_stderr=None, startup_timeout_seconds=30.0,
        )
        try:
            started = controller.start()
            if started.state is not LocalBackendState.READY:
                raise G12VisualMatrixError(f"BACKEND_NOT_READY:{started}")
            binding = controller.webengine_binding()
            workspace = create_webengine_workspace(None, binding)
            workspace.resize(1600, 900)
            workspace.show()
            view = workspace._tpaa_web_view
            if view is None:
                raise G12VisualMatrixError("WEBENGINE_VIEW_MISSING")
            g6._resize_and_load(workspace, view, 1600, 900)
            g4._evaluate(view, "window.dispatchEvent(new Event('resize')); true")
            g4._wait_for(view, "document.querySelectorAll('[data-module]:disabled').length", lambda v: v == 0, label="authorization")
            g4._wait_for(view, "document.querySelectorAll('.v29BatchRow').length", lambda v: v >= 3, label="overview")
            views = _registry_views()
            view_filter = os.environ.get("TPAA_G12_VIEW_FILTER")
            if view_filter:
                requested = {value.strip() for value in view_filter.split(",") if value.strip()}
                views = tuple(row for row in views if row[1] in requested)
                if {row[1] for row in views} != requested:
                    raise G12VisualMatrixError(f"VIEW_FILTER_INVALID:{sorted(requested)}")
            for module, view_id, title in views:
                for theme in ("graphite", "tactical", "light"):
                    for collapsed in (False, True):
                        expanded = g4._evaluate(view, "document.getElementById('app')?.classList.contains('ribbon-collapsed') === false")
                        if expanded == collapsed:
                            g4._evaluate(view, "document.querySelector('[data-action=\"toggle-ribbon\"]')?.click(); true")
                        g4._evaluate(view, "document.querySelector('[data-module=\"support\"]')?.click(); true")
                        g4._evaluate(view, "document.querySelector('[data-view=\"V25\"]')?.click(); true")
                        g4._wait_for(view, "document.querySelectorAll('.themeChoice').length", lambda v: v == 3, label="v25")
                        g4._evaluate(view, f"document.querySelector('[data-theme=\"{theme}\"]')?.click(); true")
                        _goto(view, module, view_id)
                        box = _box(view)
                        if box.get("currentView") != view_id or box.get("title") != title:
                            raise G12VisualMatrixError(
                                f"VIEW_IDENTITY_FAIL:{view_id}:{box.get('currentView')}:{box.get('title')!r}"
                            )
                        if box["overlapCount"] != 0 or box["clippedControls"] != 0 or box["overflow"] is not False:
                            raise G12VisualMatrixError(
                                f"BOX_MODEL_FAIL:{view_id}:{theme}:collapsed={collapsed}:{box!r}"
                            )
                        name = f"g12_{view_id}_{theme}_ribbon_{'collapsed' if collapsed else 'expanded'}.png"
                        target = EVIDENCE_DIR / name
                        _capture(workspace, target)
                        captures.append({
                            "file": target.relative_to(ROOT).as_posix(),
                            "view": view_id,
                            "title": title,
                            "theme": theme,
                            "ribbon": "collapsed" if collapsed else "expanded",
                            "box_model": box,
                            "navigation_asserted": True,
                            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                        })
        finally:
            if workspace is not None:
                workspace.close()
            controller.shutdown()
    _ = app
    duplicate_groups: dict[tuple[str, str, str], list[str]] = {}
    for capture in captures:
        key = (str(capture["theme"]), str(capture["ribbon"]), str(capture["sha256"]))
        duplicate_groups.setdefault(key, []).append(str(capture["view"]))
    duplicates = [views for views in duplicate_groups.values() if len(set(views)) > 1]
    if duplicates:
        raise G12VisualMatrixError(f"CROSS_VIEW_DUPLICATE_SCREENSHOTS:{duplicates!r}")
    full_matrix = len(views) == 26
    result: dict[str, object] = {
        "schema": "TPAA_G12_V33_VISUAL_MATRIX_V2",
        "status": "AUTOMATED_STRUCTURAL_PASS" if full_matrix else "DIAGNOSTIC_PASS",
        "core_baseline": "CB-1.17.0",
        "view_count": len({view for _module, view, _title in views}),
        "captures": captures,
        "box_model_no_overlap": True,
        "navigation_identity_asserted": True,
        "cross_view_duplicate_hashes": [],
        "scope": "view identity, title, theme, ribbon, top-level overlap, control clipping, viewport overflow, screenshot uniqueness",
        "does_not_prove": [
            "Demo v33 pixel/region fidelity",
            "complete business capability admission",
            "real-role task acceptance",
            "product completeness or release readiness",
        ],
        "release_claim": False,
    }
    if full_matrix:
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
    except (OSError, ValueError, KeyError, G12VisualMatrixError) as exc:
        print(f"G12_VISUAL_MATRIX_FAIL {exc}", file=sys.stderr)
        return 2
    captures = result["captures"]
    assert isinstance(captures, list)
    print(f"G12_VISUAL_MATRIX_PASS captures={len(captures)} views={result['view_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
