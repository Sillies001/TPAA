#!/usr/bin/env python3
"""G8 V24 WebEngine visual acceptance over CB-1.13.0.

Navigates the controlled V08 -> V24 entry with exact cluster/context grant and captures
the co-attack analysis page across resolutions/themes/Ribbon states.
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
import g6_webengine_acceptance as g6  # type: ignore[import-not-found]  # noqa: E402
import g7_webengine_acceptance as g7  # type: ignore[import-not-found]  # noqa: E402

AUTHORITY = ROOT / "baseline" / "CB-1.13.0" / "canonical"
EVIDENCE_DIR = ROOT / "evidence" / "gui-g8-v33-webengine"
EVIDENCE_JSON = ROOT / "evidence" / "gui-g8-v33-webengine.json"
CONTEXT_ID = "e6200000-0000-4000-8000-0000000000x1"
G8_CLUSTER_ID = "e6200000-0000-4000-8000-0000000000c9"
G8_WE = ("e6200000-0000-4000-8000-0000000000g1", "e6200000-0000-4000-8000-0000000000g2")
WORK_BATCH = g6.BATCHES[2][0]

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


class G8WebEngineAcceptanceError(RuntimeError):
    pass


def _seed_database(data_root: Path) -> None:
    from tpaa_storage import SQLiteDesktopUnitOfWork

    database = data_root / "tpaa.sqlite3"
    with SQLiteDesktopUnitOfWork(database, write=True, authority_root=AUTHORITY) as uow:
        uow.canonical_rows.insert(
            "world.world_relation",
            {
                "relation_id": G8_CLUSTER_ID,
                "release_id": g6.RELEASE_ID,
                "episode_id": g6.EPISODE_ID,
                "relation_type": "ATTACK_CLUSTER",
                "subject_ref": g6.SHOOTER_ID,
                "object_ref": g6.TARGET_ID,
                "start_session_time_us": 13_000_000,
                "properties": {"batch_id": WORK_BATCH, "weapon_event_ids": list(G8_WE)},
                "confidence": 0.9,
                "relation_source": "DERIVED",
                "method_version": "G8-WEB-1.0.0",
            },
            field_kinds={"properties": "json"},
        )
        for index, relation_id in enumerate(G8_WE):
            uow.canonical_rows.insert(
                "world.world_relation",
                {
                    "relation_id": relation_id,
                    "release_id": g6.RELEASE_ID,
                    "episode_id": g6.EPISODE_ID,
                    "relation_type": "WEAPON_EVENT",
                    "subject_ref": g6.SHOOTER_ID if index == 0 else "e6200000-0000-4000-8000-0000000000s9",
                    "object_ref": g6.TARGET_ID,
                    "start_session_time_us": 14_000_000 + index * 500_000,
                    "properties": {
                        "batch_id": WORK_BATCH,
                        "context_id": CONTEXT_ID,
                        "category": "BVR",
                        "category_rule_version": "WE-CAT-1.0.0",
                        "classification_exception": False,
                        "target_entity_id": g6.TARGET_ID,
                        "weapon_terminal_state": "TERMINAL_KNOWN",
                        "adjudication_state": "ADJUDICATED",
                        "observation_window_state": "WINDOW_CLOSED",
                        "identity_material": f"{WORK_BATCH}|G{index}|shooter|{14_000_000 + index * 500_000}|IR",
                        "revision_no": 1,
                    },
                    "confidence": 0.9,
                    "relation_source": "DERIVED",
                    "method_version": "G8-WEB-1.0.0",
                },
                field_kinds={"properties": "json"},
            )
        uow.canonical_rows.insert(
            "context.force_formation_context_revision",
            {
                "context_revision_id": "e6200000-0000-4000-8000-0000000000x2",
                "context_id": CONTEXT_ID,
                "revision_no": 1,
                "valid_from_session_time_us": 0,
                "valid_to_session_time_us": None,
                "source": "MANUAL_REVIEWED",
                "reason": "G8 WebEngine acceptance formation",
                "changed_by": "g8-webengine-acceptance",
            },
        )
        for aircraft, role in (("e6200000-0000-4000-8000-0000000000s1", "LEAD"), ("e6200000-0000-4000-8000-0000000000s9", "WING")):
            uow.canonical_rows.insert(
                "context.force_formation_member",
                {
                    "context_revision_id": "e6200000-0000-4000-8000-0000000000x2",
                    "aircraft_id": aircraft,
                    "formation_id": "BLUE-1",
                    "side": "BLUE",
                    "member_role": role,
                    "independent_target": False,
                },
            )
        uow.canonical_rows.update_exact(
            "registry.batch_registration",
            where={"batch_id": WORK_BATCH},
            values={"context_id": CONTEXT_ID},
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
        raise G8WebEngineAcceptanceError(f"SCREENSHOT_FAILED:{path}")


def _box_model(view: Any) -> dict[str, Any]:
    result = g4._evaluate(view, OVERLAP_SCRIPT)
    if not isinstance(result, str) or not result:
        raise G8WebEngineAcceptanceError(f"BOX_MODEL_EVAL_INVALID:{result!r}")
    decoded = json.loads(result)
    if not isinstance(decoded, dict):
        raise G8WebEngineAcceptanceError(f"BOX_MODEL_EVAL_INVALID:{decoded!r}")
    return decoded


def run() -> dict[str, object]:
    from PySide6.QtWidgets import QApplication

    from tpaa_gui.local_backend import LocalBackendController, LocalBackendState
    from tpaa_gui.webengine_shell import create_webengine_workspace

    app = QApplication.instance() or QApplication([sys.argv[0]])
    workspace = None
    captures: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="tpaa-g8-webengine-") as temporary:
        data_root = Path(temporary).resolve()
        g4._identity(data_root / "desktop-identity.json")
        g7._seed_database(data_root)
        _seed_database(data_root)
        controller = LocalBackendController(
            product_build_version="1.0.0", data_root=data_root,
            child_stderr=None, startup_timeout_seconds=30.0,
        )
        try:
            started = controller.start()
            if started.state is not LocalBackendState.READY:
                raise G8WebEngineAcceptanceError(f"BACKEND_NOT_READY:{started}")
            status, bootstrap = controller.product_request_json("GET", "/api/v1/gui/bootstrap")
            provenance = bootstrap.get("provenance")
            if status != 200 or not isinstance(provenance, dict) or provenance.get("core_baseline") != "CB-1.13.0":
                raise G8WebEngineAcceptanceError(f"BOOTSTRAP_INVALID:{status}:{bootstrap!r}")
            api_status, analysis = controller.product_request_json(
                "GET",
                f"/api/v1/gui/attack-clusters/{G8_CLUSTER_ID}/co-attack-analysis?context_id={CONTEXT_ID}",
            )
            if (
                api_status != 200
                or analysis.get("schema") != "TPAA_G8_CO_ATTACK_ANALYSIS_V1"
                or len(analysis.get("weapon_events", [])) != len(G8_WE)
                or len(analysis.get("formation", {}).get("members", [])) != 2
            ):
                raise G8WebEngineAcceptanceError(f"CO_ATTACK_INVALID:{api_status}:{analysis!r}")
            binding = controller.webengine_binding()
            workspace = create_webengine_workspace(None, binding)
            workspace.show()
            view = workspace._tpaa_web_view
            if view is None:
                raise G8WebEngineAcceptanceError("WEBENGINE_VIEW_MISSING")
            for width, height in ((1600, 900), (1280, 720)):
                if width == 1600:
                    g6._resize_and_load(workspace, view, width, height)
                    g4._evaluate(view, "window.dispatchEvent(new Event('resize')); true")
                    g4._wait_for(view, "document.querySelectorAll('[data-module]:disabled').length", lambda v: v == 0, label="authorization")
                    g4._wait_for(view, "document.querySelectorAll('.v29BatchRow').length", lambda v: v >= 3, label="overview")
                else:
                    workspace.resize(width, height)
                    g4._evaluate(view, "window.dispatchEvent(new Event('resize')); true")
                    from PySide6.QtCore import QEventLoop, QTimer
                    for _ in range(4):
                        loop = QEventLoop()
                        QTimer.singleShot(150, loop.quit)
                        loop.exec()
                g4._evaluate(view, "document.querySelector('[data-module=\"training\"]')?.click(); true")
                g4._evaluate(view, "document.querySelector('[data-view=\"V08\"]')?.click(); true")
                g4._wait_for(view, "document.querySelectorAll('[data-wp-event]').length", lambda v: v >= 2, label="v08")
                g4._evaluate(view, "document.querySelector('[data-wp-event][data-cluster=\"true\"]')?.click(); true")
                g4._wait_for(view, "document.querySelector('[data-wp-coattack]') !== null", lambda v: v is True, label="coattack-entry")
                import time
                time.sleep(1.0)
                g4._evaluate(view, "document.querySelector('[data-wp-coattack]')?.click(); true")
                g4._wait_for(view, "document.querySelectorAll('.v26TrackRow').length", lambda v: v >= 2, label="v24")
                values = {
                    "panels": g4._evaluate(view, "document.querySelectorAll('#main-content .p').length"),
                    "members": g4._evaluate(view, "document.querySelectorAll('.batch-table tbody tr').length"),
                    "dims": g4._evaluate(view, "document.querySelectorAll('.g8Dims .v26Chip').length"),
                }
                if values["panels"] != 4 or values["members"] != 2 or values["dims"] != 5:
                    raise G8WebEngineAcceptanceError(f"CONTENT_CHECK_FAILED:{values!r}")
                for theme in ("graphite", "tactical", "light"):
                    for collapsed in (False, True):
                        expanded = g4._evaluate(view, "document.getElementById('app')?.classList.contains('ribbon-collapsed') === false")
                        if expanded == collapsed:
                            g4._evaluate(view, "document.querySelector('[data-action=\"toggle-ribbon\"]')?.click(); true")
                        g4._evaluate(view, "document.querySelector('[data-module=\"support\"]')?.click(); true")
                        g4._evaluate(view, "document.querySelector('[data-view=\"V25\"]')?.click(); true")
                        g4._wait_for(view, "document.querySelectorAll('.themeChoice').length", lambda v: v == 3, label="v25")
                        g4._evaluate(view, f"document.querySelector('[data-theme=\"{theme}\"]')?.click(); true")
                        g4._evaluate(view, "document.querySelector('[data-module=\"training\"]')?.click(); true")
                        g4._evaluate(view, "document.querySelector('[data-view=\"V08\"]')?.click(); true")
                        g4._wait_for(view, "document.querySelectorAll('[data-wp-event]').length", lambda v: v >= 2, label="v08-return")
                        g4._evaluate(view, "document.querySelector('[data-wp-event][data-cluster=\"true\"]')?.click(); true")
                        g4._evaluate(view, "document.querySelector('[data-wp-coattack]')?.click(); true")
                        g4._wait_for(view, "document.querySelectorAll('.v26TrackRow').length", lambda v: v >= 2, label="v24-return")
                        box = _box_model(view)
                        if box["overlapCount"] != 0 or box["overflow"] is not False:
                            raise G8WebEngineAcceptanceError(f"BOX_MODEL_FAIL:{width}x{height}:{theme}:{box!r}")
                        name = f"g8_v24_{width}x{height}_{theme}_ribbon_{'collapsed' if collapsed else 'expanded'}.png"
                        target = EVIDENCE_DIR / name
                        _capture(workspace, target)
                        captures.append({
                            "file": target.relative_to(ROOT).as_posix(),
                            "resolution": f"{width}x{height}",
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
        "schema": "TPAA_G8_V33_WEBENGINE_ACCEPTANCE_V1",
        "status": "PASS",
        "core_baseline": "CB-1.13.0",
        "view": "V24",
        "entry": "V08 controlled grant (cluster + context + formation)",
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
    except (OSError, ValueError, KeyError, G8WebEngineAcceptanceError) as exc:
        print(f"G8_WEBENGINE_ACCEPTANCE_FAIL {exc}", file=sys.stderr)
        return 2
    captures = result["captures"]
    assert isinstance(captures, list)
    print(f"G8_WEBENGINE_ACCEPTANCE_PASS captures={len(captures)} box_model_no_overlap=True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
