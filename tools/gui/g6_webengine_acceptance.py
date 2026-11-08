#!/usr/bin/env python3
"""G6 V01 WebEngine visual acceptance: demo-fidelity screenshot matrix over CB-1.11.0.

Captures the real V01 historical-overview page (v29 markup, real gui.overview data)
at 1600x900 and 1280x720 across graphite/tactical/light themes and both Ribbon states,
and verifies the box model has no overlapping panels/cards.  The backend child runs with
TPAA_AUTHORITY_ROOT pointed at the CB-1.11.0 canonical directory (local activation).
"""

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

AUTHORITY = ROOT / "baseline" / "CB-1.11.0" / "canonical"
EVIDENCE_DIR = ROOT / "evidence" / "gui-g6-v33-webengine"
EVIDENCE_JSON = ROOT / "evidence" / "gui-g6-v33-webengine.json"

SESSION_ID = "e6200000-0000-4000-8000-000000000001"
JOB_ID = "e6200000-0000-4000-8000-0000000000j1"
RELEASE_ID = "e6200000-0000-4000-8000-0000000000r1"
EPISODE_ID = "e6200000-0000-4000-8000-0000000000p1"
SHOOTER_ID = "e6200000-0000-4000-8000-0000000000s1"
TARGET_ID = "e6200000-0000-4000-8000-0000000000t1"

BATCHES = (
    ("e6200000-0000-4000-8000-0000000000b1", "2026-09-14", "SIMPLE_OPPOSITION"),
    ("e6200000-0000-4000-8000-0000000000b2", "2026-10-08", "MIXED_OPPOSITION"),
    ("e6200000-0000-4000-8000-0000000000b3", "2026-10-22", "COMPREHENSIVE_OPPOSITION"),
)
WEAPON_EVENTS = (
    ("e6200000-0000-4000-8000-0000000000e1", BATCHES[0][0], "ADJUDICATED"),
    ("e6200000-0000-4000-8000-0000000000e2", BATCHES[0][0], "ADJUDICATION_PENDING"),
    ("e6200000-0000-4000-8000-0000000000e3", BATCHES[1][0], "ADJUDICATED"),
    ("e6200000-0000-4000-8000-0000000000e4", BATCHES[2][0], "ADJUDICATED"),
    ("e6200000-0000-4000-8000-0000000000e5", BATCHES[2][0], "ADJUDICATED"),
)

OVERLAP_SCRIPT = """(() => {
  const selectors = ['.v29Kpi', '.v29Panel'];
  const rects = [];
  document.querySelectorAll(selectors.join(',')).forEach((e) => rects.push(e.getBoundingClientRect()));
  let overlaps = [];
  for (let i = 0; i < rects.length; i++) {
    for (let j = i + 1; j < rects.length; j++) {
      const a = rects[i], b = rects[j];
      const ix = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      const iy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (ix > 0.5 && iy > 0.5) overlaps.push([i, j]);
    }
  }
  const view = document.querySelector('.v29Overview')?.getBoundingClientRect();
  const overflow = view ? (view.left < -0.5 || view.top < -0.5 ||
    view.right > window.innerWidth + 0.5 || view.bottom > window.innerHeight + 0.5) : true;
  const themeAttr = document.documentElement.getAttribute('data-tpaa-theme') || '';
  return JSON.stringify({ overlapCount: overlaps.length, overflow: overflow, themeAttr: themeAttr });
})()"""


class G6WebEngineAcceptanceError(RuntimeError):
    """A mandatory G6 visual acceptance check failed."""


def _seed_database(data_root: Path) -> None:
    from tpaa_storage import SQLiteDesktopUnitOfWork, bootstrap_sqlite

    database = data_root / "tpaa.sqlite3"
    bootstrap_sqlite(database, authority_root=AUTHORITY)
    with SQLiteDesktopUnitOfWork(database, write=True, authority_root=AUTHORITY) as uow:
        uow.canonical_rows.insert(
            "registry.training_session",
            {
                "session_id": SESSION_ID,
                "session_code": "G6-WEB-001",
                "session_type": "LIVE",
                "start_session_time_us": 0,
                "end_session_time_us": 10_000_000,
                "training_type_set": (),
                "data_status": "IMPORTED",
                "source_count": 1,
                "schema_version": "1.10.0",
            },
            field_kinds={"training_type_set": "text_array"},
        )
        uow.canonical_rows.insert(
            "registry.compute_job",
            {
                "job_id": JOB_ID,
                "job_type": "EPISODE_DETECTION",
                "session_id": SESSION_ID,
                "job_key": "g6-webengine-acceptance",
                "status": "SUCCEEDED",
                "component_version": "G6-WEB-1.0.0",
                "input_hash": "b" * 64,
            },
        )
        uow.canonical_rows.insert(
            "registry.analysis_release",
            {
                "release_id": RELEASE_ID,
                "scope_type": "SESSION",
                "scope_key": SESSION_ID,
                "session_id": SESSION_ID,
                "release_no": 1,
                "compute_job_id": JOB_ID,
                "catalog_version": "G6-WEB-ACCEPTANCE",
                "catalog_hash": "c" * 64,
                "context_binding_hash": "d" * 64,
                "status": "PUBLISHED",
                "manifest_hash": "e" * 64,
                "created_at": "2026-10-22T00:00:00+00:00",
            },
        )
        uow.canonical_rows.insert(
            "episode.training_episode",
            {
                "episode_id": EPISODE_ID,
                "session_id": SESSION_ID,
                "episode_type": "BVR_ENGAGEMENT",
                "start_session_time_us": 0,
                "end_session_time_us": 10_000_000,
                "subject_scope": "SESSION",
                "world_capability_code": "BVR_ENGAGEMENT",
                "episode_status": "DETECTED",
                "detector_version": "G6-WEB-1.0.0",
                "coverage": 1.0,
                "confidence": 0.9,
            },
        )
        for batch_id, _date, training_type in BATCHES:
            uow.canonical_rows.insert(
                "registry.batch_registration",
                {
                    "batch_id": batch_id,
                    "session_id": SESSION_ID,
                    "batch_date": _date,
                    "batch_training_type": training_type,
                    "training_type_confirmed": True,
                    "qualification_status": "QUALIFIED",
                    "source_manifest_sha256": "a" * 64,
                    "revision_no": 1,
                    "created_by": "g6-webengine-acceptance",
                },
            )
        for index, (relation_id, batch_id, adjudication_state) in enumerate(WEAPON_EVENTS):
            uow.canonical_rows.insert(
                "world.world_relation",
                {
                    "relation_id": relation_id,
                    "release_id": RELEASE_ID,
                    "episode_id": EPISODE_ID,
                    "relation_type": "WEAPON_EVENT",
                    "subject_ref": SHOOTER_ID,
                    "object_ref": TARGET_ID,
                    "start_session_time_us": 1_000_000 + index * 500_000,
                    "properties": {
                        "batch_id": batch_id,
                        "category": "BVR",
                        "adjudication_state": adjudication_state,
                    },
                    "confidence": 0.9,
                    "relation_source": "DERIVED",
                    "method_version": "G6-WEB-1.0.0",
                },
                field_kinds={"properties": "json"},
            )
        uow.commit()


def _capture(workspace: Any, path: Path) -> None:
    from PySide6.QtCore import QEventLoop, QTimer

    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(6):
        loop = QEventLoop()
        QTimer.singleShot(120, loop.quit)
        loop.exec()
    if not workspace.grab().save(str(path), "PNG"):
        raise G6WebEngineAcceptanceError(f"SCREENSHOT_FAILED:{path}")


def _set_theme(view: Any, theme: str) -> None:
    """经应用自身 V25 主题管理通路切换主题（状态一致，页脚标签同步）。"""
    g4._evaluate(view, "document.querySelector('[data-module=\"support\"]')?.click(); true")
    g4._evaluate(view, "document.querySelector('[data-view=\"V25\"]')?.click(); true")
    g4._wait_for(
        view,
        "document.querySelectorAll('.themeChoice').length",
        lambda value: value == 3,
        label="v25-themes",
    )
    g4._evaluate(
        view,
        f"document.querySelector('[data-theme=\"{theme}\"]')?.click(); true",
    )
    g4._evaluate(view, "document.querySelector('[data-module=\"overview\"]')?.click(); true")
    g4._wait_for(
        view,
        "document.querySelectorAll('.v29BatchRow').length",
        lambda value: value == len(BATCHES),
        label="v01-return",
    )


def _set_ribbon(view: Any, *, collapsed: bool) -> None:
    script = """(() => {
      const expanded = document.getElementById('app')?.classList.contains('ribbon-collapsed') === false;
      return expanded;
    })()"""
    expanded = g4._evaluate(view, script)
    if expanded == collapsed:
        g4._evaluate(view, "document.querySelector('[data-action=\"toggle-ribbon\"]')?.click(); true")


def _box_model(view: Any) -> dict[str, Any]:
    result = g4._evaluate(view, OVERLAP_SCRIPT)
    if not isinstance(result, str) or not result:
        raise G6WebEngineAcceptanceError(f"BOX_MODEL_EVAL_INVALID:{result!r}")
    try:
        decoded = json.loads(result)
    except json.JSONDecodeError as exc:
        raise G6WebEngineAcceptanceError(f"BOX_MODEL_JSON_INVALID:{result!r}") from exc
    if not isinstance(decoded, dict):
        raise G6WebEngineAcceptanceError(f"BOX_MODEL_EVAL_INVALID:{decoded!r}")
    return decoded


def _content_checks(view: Any) -> dict[str, Any]:
    checks = {
        "kpi_cards": "document.querySelectorAll('.v29Kpi').length",
        "batch_rows": "document.querySelectorAll('.v29BatchRow').length",
        "activity_polylines": "document.querySelectorAll('.v29Activity polyline').length",
        "outcome_bars": "document.querySelectorAll('.v29Outcome rect').length",
        "selected_panel": "document.querySelectorAll('.v29SelectedBatch').length",
        "footer": "document.querySelectorAll('.v29Footer').length",
        "title": "document.querySelector('.v29Title h1')?.textContent || ''",
    }
    values: dict[str, Any] = {}
    for name, script in checks.items():
        values[name] = g4._evaluate(view, script)
    expected = {
        "kpi_cards": 6,
        "batch_rows": len(BATCHES),
        "activity_polylines": 2,
        "outcome_bars": 2,
        "selected_panel": 1,
        "footer": 1,
    }
    for name, wanted in expected.items():
        if values[name] != wanted:
            raise G6WebEngineAcceptanceError(
                f"CONTENT_CHECK_FAILED:{name} expected={wanted} actual={values[name]!r}"
            )
    if values["title"] != "训练总览":
        raise G6WebEngineAcceptanceError(f"CONTENT_CHECK_FAILED:title {values['title']!r}")
    return values


def _resize_and_load(workspace: Any, view: Any, width: int, height: int) -> None:
    from PySide6.QtCore import QEventLoop, QTimer

    workspace.resize(width, height)
    loop = QEventLoop()
    loaded: list[bool] = []

    def finish_loading(ok: bool, sink: list[bool] = loaded) -> None:
        sink.append(ok)
        loop.quit()

    view.loadFinished.connect(finish_loading)
    QTimer.singleShot(20_000, loop.quit)
    loop.exec()
    if loaded and loaded[-1] is not True:
        raise G6WebEngineAcceptanceError(f"WEBENGINE_LOAD_FAILED:{loaded}")


def run() -> dict[str, object]:
    from PySide6.QtWidgets import QApplication

    from tpaa_gui.local_backend import LocalBackendController, LocalBackendState
    from tpaa_gui.webengine_shell import create_webengine_workspace

    app = QApplication.instance() or QApplication([sys.argv[0]])
    workspace = None
    captures: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="tpaa-g6-webengine-") as temporary:
        data_root = Path(temporary).resolve()
        g4._identity(data_root / "desktop-identity.json")
        _seed_database(data_root)
        controller = LocalBackendController(
            product_build_version="1.0.0",
            data_root=data_root,
            child_stderr=None,
            startup_timeout_seconds=30.0,
        )
        try:
            started = controller.start()
            if started.state is not LocalBackendState.READY:
                raise G6WebEngineAcceptanceError(f"BACKEND_NOT_READY:{started}")
            status, bootstrap = controller.product_request_json("GET", "/api/v1/gui/bootstrap")
            provenance = bootstrap.get("provenance")
            if (
                status != 200
                or not isinstance(provenance, dict)
                or provenance.get("core_baseline") != "CB-1.11.0"
            ):
                raise G6WebEngineAcceptanceError(f"BOOTSTRAP_INVALID:{status}:{bootstrap!r}")
            overview_status, overview = controller.product_request_json(
                "GET", "/api/v1/gui/historical-overview"
            )
            if (
                overview_status != 200
                or overview.get("schema") != "TPAA_G6_HISTORICAL_OVERVIEW_V1"
                or overview.get("kpi", {}).get("batch_count") != len(BATCHES)
                or overview.get("kpi", {}).get("weapon_event_count") != len(WEAPON_EVENTS)
            ):
                raise G6WebEngineAcceptanceError(
                    f"OVERVIEW_INVALID:{overview_status}:{overview!r}"
                )
            binding = controller.webengine_binding()
            workspace = create_webengine_workspace(None, binding)
            workspace.show()
            view = workspace._tpaa_web_view
            if view is None:
                raise G6WebEngineAcceptanceError("WEBENGINE_VIEW_MISSING")
            for width, height in ((1600, 900), (1280, 720)):
                _resize_and_load(workspace, view, width, height)
                g4._evaluate(view, "window.dispatchEvent(new Event('resize')); true")
                g4._wait_for(
                    view,
                    "document.querySelectorAll('[data-module]:disabled').length",
                    lambda value: value == 0,
                    label="authorization",
                )
                g4._wait_for(
                    view,
                    "document.querySelectorAll('.v29BatchRow').length",
                    lambda value: value == len(BATCHES),
                    label="v01-overview",
                )
                _set_ribbon(view, collapsed=False)
                _content_checks(view)
                for theme in ("graphite", "tactical", "light"):
                    for collapsed in (False, True):
                        # 先切 Ribbon（会触发 render 并重置主题为会话主题），再设主题，
                        # 之后到抓图前不得再有 render，保证截图主题为所设主题。
                        _set_ribbon(view, collapsed=collapsed)
                        _set_theme(view, theme)
                        box = _box_model(view)
                        if box["overlapCount"] != 0 or box["overflow"] is not False:
                            raise G6WebEngineAcceptanceError(
                                f"BOX_MODEL_FAIL:{width}x{height}:{theme}:"
                                f"collapsed={collapsed}:{box!r}"
                            )
                        name = (
                            f"g6_v01_{width}x{height}_{theme}"
                            f"_ribbon_{'collapsed' if collapsed else 'expanded'}.png"
                        )
                        target = EVIDENCE_DIR / name
                        _capture(workspace, target)
                        captures.append(
                            {
                                "file": target.relative_to(ROOT).as_posix(),
                                "resolution": f"{width}x{height}",
                                "theme": theme,
                                "ribbon": "collapsed" if collapsed else "expanded",
                                "box_model": box,
                                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                            }
                        )
                _set_theme(view, "graphite")
                _set_ribbon(view, collapsed=False)
        finally:
            if workspace is not None:
                workspace.close()
            controller.shutdown()
    _ = app
    result: dict[str, object] = {
        "schema": "TPAA_G6_V33_WEBENGINE_ACCEPTANCE_V1",
        "status": "PASS",
        "core_baseline": "CB-1.11.0",
        "parent_core_baseline": "CB-1.10.0",
        "view": "V01",
        "workset": {
            "batch_count": len(BATCHES),
            "weapon_event_count": len(WEAPON_EVENTS),
        },
        "captures": captures,
        "box_model_no_overlap": True,
        "exact_origin": binding.origin,
        "release_claim": False,
    }
    EVIDENCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_JSON.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    os.environ.setdefault("POLARS_SKIP_CPU_CHECK", "1")
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
    os.environ["QT_SCALE_FACTOR"] = "1"
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        "--disable-extensions --force-device-scale-factor=1"
    )
    os.environ["TPAA_AUTHORITY_ROOT"] = str(AUTHORITY.resolve())
    try:
        result = run()
    except (OSError, ValueError, KeyError, G6WebEngineAcceptanceError) as exc:
        print(f"G6_WEBENGINE_ACCEPTANCE_FAIL {exc}", file=sys.stderr)
        return 2
    captures = result["captures"]
    assert isinstance(captures, list)
    print(
        "G6_WEBENGINE_ACCEPTANCE_PASS "
        f"captures={len(captures)} box_model_no_overlap=True"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
