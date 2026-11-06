#!/usr/bin/env python3
"""Capture deterministic G0 WebEngine and QML runtime comparison evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, NamedTuple, TypeVar

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault(
    "QTWEBENGINE_CHROMIUM_FLAGS",
    "--disable-gpu --disable-extensions --force-device-scale-factor=1",
)
os.environ.setdefault("QT_SCALE_FACTOR", "1")
os.environ.setdefault("QT_FONT_DPI", "96")

from PySide6.QtCore import QEventLoop, QSize, QTimer, QUrl
from PySide6.QtGui import QImage
from PySide6.QtQml import QQmlContext
from PySide6.QtQuick import QQuickView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication

T = TypeVar("T")
REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = REPO_ROOT.parents[2]
QML_SOURCE = REPO_ROOT / "tools" / "gui" / "spikes" / "g0_qml_reference.qml"
THEMES = ("tactical", "graphite", "light")


def _v33_demo_path() -> Path:
    workspace_copy = WORKSPACE_ROOT / "TPAA_V33与三份文档更新" / "TPAA_训练复盘交互Demo_v33.html"
    if workspace_copy.is_file():
        return workspace_copy
    return REPO_ROOT / "docs" / "gui" / "demo-v33" / "source" / "TPAA_训练复盘交互Demo_v33.html"


class TargetProfile(NamedTuple):
    baseline_id: str
    demo: Path
    fixture: Path
    expected_sha256: str
    all_views: tuple[str, ...]
    spike_views: tuple[str, ...]
    output: Path


TARGETS = {
    "v19": TargetProfile(
        baseline_id="GUI-DEMO-V19-2026-10-29",
        demo=WORKSPACE_ROOT / "TPAA_训练复盘交互Demo_Ribbon完整版_v19_三主题_默认深色.html",
        fixture=REPO_ROOT / "tests" / "fixtures" / "gui" / "g0_spike_fixture.json",
        expected_sha256="64910eb8b73b8ada44e398ac85568c887a5863d2b8272577e3e09ae857b0a706",
        all_views=tuple(f"V{index:02d}" for index in range(1, 26)),
        spike_views=("V01", "V03", "V24"),
        output=REPO_ROOT / "evidence" / "gui-g0",
    ),
    "v33": TargetProfile(
        baseline_id="GUI-DEMO-V33-2026-11-05",
        demo=_v33_demo_path(),
        fixture=REPO_ROOT / "tests" / "fixtures" / "gui" / "g0_v33_spike_fixture.json",
        expected_sha256="7aa5ff433fcaa49c3a54ac592acb43c42ee98fd944d4fb66de6e75bac2401a9a",
        all_views=tuple(f"V{index:02d}" for index in range(1, 27)),
        spike_views=("V01", "V04", "V08", "V26"),
        output=REPO_ROOT / "evidence" / "gui-g0-v33",
    ),
}


class SpikeError(RuntimeError):
    """The local runtime spike could not produce trustworthy evidence."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _wait_for_signal(
    connect: Callable[[Callable[..., None]], Any],
    trigger: Callable[[], None],
    timeout_ms: int,
) -> tuple[Any, ...]:
    loop = QEventLoop()
    result: list[Any] = []

    def complete(*values: Any) -> None:
        result.extend(values)
        loop.quit()

    connect(complete)
    trigger()
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    if not result:
        raise SpikeError(f"Qt signal timed out after {timeout_ms} ms")
    return tuple(result)


def _settle(milliseconds: int = 220) -> None:
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def _run_javascript(page: QWebEnginePage, script: str, timeout_ms: int = 5000) -> Any:
    loop = QEventLoop()
    completed = False
    value: Any = None

    def receive(result: Any) -> None:
        nonlocal completed, value
        completed = True
        value = result
        loop.quit()

    page.runJavaScript(script, receive)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    if not completed:
        raise SpikeError(f"JavaScript timed out after {timeout_ms} ms")
    return value


def _run_javascript_json(page: QWebEnginePage, expression: str) -> dict[str, Any]:
    raw = _run_javascript(page, f"JSON.stringify({expression})")
    if not isinstance(raw, str):
        raise SpikeError(f"JavaScript did not return JSON text: {raw!r}")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise SpikeError(f"JavaScript JSON result is not an object: {value!r}")
    return value


def _save_image(image: QImage, destination: Path) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if image.isNull() or not image.save(str(destination), b"PNG"):
        raise SpikeError(f"failed to save screenshot: {destination}")
    return {
        "path": destination.relative_to(REPO_ROOT).as_posix(),
        "sha256": _sha256(destination),
        "bytes": destination.stat().st_size,
        "width": image.width(),
        "height": image.height(),
    }


def _configure_demo_page(profile: QWebEngineProfile, page: QWebEnginePage) -> None:
    if not profile.isOffTheRecord():
        raise SpikeError("G0 WebEngine profile must be off-the-record")
    settings = page.settings()
    settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, False)


def capture_webengine(
    app: QApplication,
    demo: Path,
    fixture: dict[str, Any],
    output_root: Path,
    views: Sequence[str],
    themes: Sequence[str],
    viewport: tuple[int, int],
) -> dict[str, Any]:
    del app
    profile = QWebEngineProfile()
    page = QWebEnginePage(profile)
    view = QWebEngineView()
    view.setPage(page)
    view.resize(QSize(*viewport))
    view.move(-2400, -1200)
    view.show()
    _configure_demo_page(profile, page)

    started = time.perf_counter()
    demo_html = demo.read_text(encoding="utf-8")
    # The frozen Demo is a single-file artifact with no external resources.
    # An ASCII synthetic base avoids platform-specific non-ASCII file URL issues.
    base_url = QUrl("http://127.0.0.1/tpaa-g0-demo/")
    loaded = _wait_for_signal(
        view.loadFinished.connect,
        lambda: page.setHtml(demo_html, base_url),
        30_000,
    )
    probe = _run_javascript_json(
        page,
        "({title: document.title, hasState: typeof st === 'object', "
        "hasDraw: typeof draw === 'function'})",
    )
    if not isinstance(probe, dict) or not probe.get("hasState") or not probe.get("hasDraw"):
        raise SpikeError(f"Demo load failed: signal={loaded!r} probe={probe!r} source={demo}")
    initial_load_ms = round((time.perf_counter() - started) * 1000, 3)
    outputs: list[dict[str, Any]] = []
    fixture_json = json.dumps(fixture, ensure_ascii=False).replace("</", "<\\/")
    for theme in themes:
        for view_id in views:
            expression = f"""
                (() => {{
                  window.__TPAA_G0_CONTRACT_FIXTURE__ = {fixture_json};
                  st.uiTheme = {json.dumps(theme)};
                  st.v = {json.dumps(view_id)};
                  st.h = {json.dumps(["V08"] if view_id == "V24" else (["V01"] if view_id == "V26" else []))};
                  if (typeof applyTheme === 'function') applyTheme();
                  draw();
                  if (typeof fit === 'function') fit();
                  return {{view: st.v, theme: document.documentElement.dataset.tpaaTheme,
                           title: document.title, width: innerWidth, height: innerHeight}};
                }})()
            """
            state = _run_javascript_json(page, expression)
            if state.get("view") != view_id:
                raise SpikeError(f"Demo state switch failed for {theme}/{view_id}: {state!r}")
            _settle()
            geometry = None
            if view_id == "V01":
                geometry = _run_javascript_json(page, _V01_GEOMETRY_EXPRESSION)
                if geometry.get("issues"):
                    raise SpikeError(
                        f"V01 geometry gate failed for {theme} at "
                        f"{viewport[0]}x{viewport[1]}: {geometry['issues']!r}"
                    )
            destination = output_root / "webengine" / theme / f"{view_id}.png"
            item = _save_image(view.grab().toImage(), destination)
            item.update({"engine": "webengine", "theme": theme, "view": view_id})
            if geometry is not None:
                item["geometry"] = geometry
            outputs.append(item)
    view.close()
    page.deleteLater()
    profile.deleteLater()
    return {
        "engine": "webengine",
        "off_the_record": True,
        "load_finished_signal": bool(loaded[0]),
        "source_sha256": _sha256(demo),
        "initial_load_ms": initial_load_ms,
        "viewport": {"width": viewport[0], "height": viewport[1]},
        "outputs": outputs,
    }


def _qml_context(view: QQuickView) -> QQmlContext:
    return view.rootContext()


def capture_qml(
    app: QApplication,
    fixture: dict[str, Any],
    output_root: Path,
    views: Sequence[str],
    themes: Sequence[str],
    viewport: tuple[int, int],
) -> dict[str, Any]:
    del app
    outputs: list[dict[str, Any]] = []
    load_times: list[float] = []
    for theme in themes:
        for view_id in views:
            view = QQuickView()
            view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
            view.resize(QSize(*viewport))
            view.setPosition(-2400, -1200)
            context = _qml_context(view)
            context.setContextProperty("g0ViewId", view_id)
            context.setContextProperty("g0ThemeName", theme)
            context.setContextProperty("g0FixtureJson", json.dumps(fixture, ensure_ascii=False))
            started = time.perf_counter()
            view.setSource(QUrl.fromLocalFile(str(QML_SOURCE)))
            view.show()
            _settle(120)
            load_times.append((time.perf_counter() - started) * 1000)
            if view.status() != QQuickView.Status.Ready:
                errors = "; ".join(error.toString() for error in view.errors())
                raise SpikeError(f"QML load failed for {view_id}: {errors}")
            destination = output_root / "qml" / theme / f"{view_id}.png"
            item = _save_image(view.grabWindow(), destination)
            item.update({"engine": "qml", "theme": theme, "view": view_id})
            outputs.append(item)
            view.close()
    return {
        "engine": "qml",
        "source_sha256": _sha256(QML_SOURCE),
        "mean_load_ms": round(sum(load_times) / len(load_times), 3),
        "viewport": {"width": viewport[0], "height": viewport[1]},
        "outputs": outputs,
    }


_V01_GEOMETRY_EXPRESSION = r"""
(() => {
  const round = value => Math.round(value * 1000) / 1000;
  const rect = element => {
    const r = element.getBoundingClientRect();
    return {left: round(r.left), top: round(r.top), right: round(r.right),
            bottom: round(r.bottom), width: round(r.width), height: round(r.height)};
  };
  const select = selector => Array.from(document.querySelectorAll(selector));
  const named = [
    ['overview', '.v29Overview'], ['header', '.v29Header'],
    ['kpis', '.v29Kpis'], ['row_first', '.v29RowFirst'],
    ['row_second', '.v29RowSecond'], ['row_bottom', '.v29RowBottom'],
    ['footer', '.v29Footer']
  ];
  const boxes = {};
  const issues = [];
  for (const [name, selector] of named) {
    const element = document.querySelector(selector);
    if (!element) issues.push(`missing:${selector}`); else boxes[name] = rect(element);
  }
  const contains = (outer, inner, tolerance = 1) =>
    inner.left >= outer.left - tolerance && inner.right <= outer.right + tolerance &&
    inner.top >= outer.top - tolerance && inner.bottom <= outer.bottom + tolerance;
  const overlaps = (a, b, tolerance = 0.5) =>
    Math.min(a.right, b.right) - Math.max(a.left, b.left) > tolerance &&
    Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > tolerance;
  const majorNames = ['header', 'kpis', 'row_first', 'row_second', 'row_bottom', 'footer'];
  if (boxes.overview) {
    for (const name of majorNames) {
      if (boxes[name] && !contains(boxes.overview, boxes[name])) issues.push(`outside:overview>${name}`);
    }
    for (let i = 0; i < majorNames.length; i++) {
      for (let j = i + 1; j < majorNames.length; j++) {
        const a = boxes[majorNames[i]], b = boxes[majorNames[j]];
        if (a && b && overlaps(a, b)) issues.push(`overlap:${majorNames[i]}>${majorNames[j]}`);
      }
    }
  }
  const groups = [
    ['kpi', '.v29Kpis', '.v29Kpi', 6],
    ['row_first_panel', '.v29RowFirst', ':scope > .v29Panel', 2],
    ['row_second_panel', '.v29RowSecond', ':scope > .v29Panel', 3],
    ['row_bottom_panel', '.v29RowBottom', ':scope > .v29Panel', 2]
  ];
  const children = {};
  for (const [name, parentSelector, childSelector, expected] of groups) {
    const parent = document.querySelector(parentSelector);
    const elements = parent ? Array.from(parent.querySelectorAll(childSelector)) : [];
    children[name] = elements.map(rect);
    if (elements.length !== expected) issues.push(`count:${name}:${elements.length}/${expected}`);
    if (parent) {
      const parentRect = rect(parent);
      children[name].forEach((child, index) => {
        if (!contains(parentRect, child)) issues.push(`outside:${name}:${index}`);
        if (child.width <= 0 || child.height <= 0) issues.push(`zero:${name}:${index}`);
      });
      for (let i = 0; i < children[name].length; i++) {
        for (let j = i + 1; j < children[name].length; j++) {
          if (overlaps(children[name][i], children[name][j])) issues.push(`overlap:${name}:${i}>${j}`);
        }
      }
    }
  }
  const scale = boxes.overview ? round(boxes.overview.width / 1540) : null;
  return {
    schema: 'TPAA_V01_ELEMENT_GEOMETRY_V1',
    viewport: {width: innerWidth, height: innerHeight, device_pixel_ratio: devicePixelRatio},
    scale,
    boxes,
    children,
    issues
  };
})()
"""


def _parse_viewport(value: str) -> tuple[int, int]:
    try:
        width_text, height_text = value.lower().split("x", 1)
        width, height = int(width_text), int(height_text)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("viewport must be WIDTHxHEIGHT") from exc
    if width < 640 or height < 480:
        raise argparse.ArgumentTypeError("viewport must be at least 640x480")
    return width, height


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", choices=tuple(TARGETS), default="v33")
    parser.add_argument("--engine", choices=("webengine", "qml", "both"), default="both")
    parser.add_argument("--demo", type=Path)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--all-demo", action="store_true", help="Capture all target views")
    parser.add_argument("--views", nargs="+", help="Capture an explicit subset of target views")
    parser.add_argument("--viewport", type=_parse_viewport, default=(1600, 900))
    parser.add_argument("--themes", nargs="+", choices=THEMES, default=list(THEMES))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    target = TARGETS[args.baseline]
    demo = (args.demo or target.demo).resolve()
    fixture_path = (args.fixture or target.fixture).resolve()
    output_root = (args.output or target.output).resolve()
    if not demo.is_file() or _sha256(demo) != target.expected_sha256:
        raise SpikeError(f"Demo is missing or does not match {target.baseline_id}: {demo}")
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    if fixture.get("fixture_kind") != "CONTRACT_SHAPED_NON_RANDOM":
        raise SpikeError("G0 spike fixture is not contract-shaped")

    existing_app = QApplication.instance()
    app = existing_app if isinstance(existing_app, QApplication) else QApplication([sys.argv[0]])
    results: list[dict[str, Any]] = []
    requested_views = tuple(args.views or ())
    unknown_views = sorted(set(requested_views) - set(target.all_views))
    if unknown_views:
        raise SpikeError(f"views are outside {target.baseline_id}: {unknown_views}")
    if args.engine in {"webengine", "both"}:
        web_views = requested_views or (target.all_views if args.all_demo else target.spike_views)
        results.append(
            capture_webengine(
                app, demo, fixture, output_root, web_views, args.themes, args.viewport
            )
        )
    if args.engine in {"qml", "both"}:
        qml_views = requested_views or target.spike_views
        results.append(capture_qml(app, fixture, output_root, qml_views, args.themes, args.viewport))

    manifest = {
        "schema": "TPAA_G0_RUNTIME_SPIKE_EVIDENCE_V2",
        "status": "PASS",
        "baseline_id": target.baseline_id,
        "demo_sha256": _sha256(demo),
        "fixture_sha256": _sha256(fixture_path),
        "viewport": {"width": args.viewport[0], "height": args.viewport[1]},
        "captured_views": list(requested_views),
        "results": results,
        "decision": "WEBENGINE_PREFERRED_QML_FALLBACK_PENDING_TARGET_GATES",
        "release_claim": False,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / "g0-runtime-spike.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "PASS", "manifest": str(manifest_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
