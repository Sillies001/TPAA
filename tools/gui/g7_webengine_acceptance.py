#!/usr/bin/env python3
"""G7 V26 WebEngine visual acceptance: screenshot matrix over CB-1.12.0.

Captures the real V26 batch-events workbench (real gui.batch.events data with a salvo
cluster) at 1600x900 and 1280x720 across graphite/tactical/light themes and both Ribbon
states, and verifies the box model has no overlapping panels.  The backend child runs
with TPAA_AUTHORITY_ROOT pointed at the CB-1.12.0 canonical directory (local activation).
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

AUTHORITY = ROOT / "baseline" / "CB-1.12.0" / "canonical"
EVIDENCE_DIR = ROOT / "evidence" / "gui-g7-v33-webengine"
EVIDENCE_JSON = ROOT / "evidence" / "gui-g7-v33-webengine.json"

CLUSTER_ID = "e6200000-0000-4000-8000-0000000000c1"
WEAPON_EVENT_ROWS = (
    # (relation_id, batch, t1, category, adjudication, exception)
    ("e6200000-0000-4000-8000-0000000000f1", 6, "BVR", "ADJUDICATION_PENDING", False),
    ("e6200000-0000-4000-8000-0000000000f2", 7, "BVR", "ADJUDICATED", False),
    ("e6200000-0000-4000-8000-0000000000f3", 8, "WVR", "ADJUDICATED", False),
    ("e6200000-0000-4000-8000-0000000000f4", 9, "STRIKE", "ADJUDICATION_PENDING", True),
    ("e6200000-0000-4000-8000-0000000000f5", 10, "WVR", "ADJUDICATED", False),
    ("e6200000-0000-4000-8000-0000000000f6", 11, "STRIKE", "ADJUDICATED", False),
)

OVERLAP_SCRIPT = """(() => {
  const rects = [];
  document.querySelectorAll('#main-content .p').forEach((e) => rects.push(e.getBoundingClientRect()));
  let overlaps = 0;
  for (let i = 0; i < rects.length; i++) {
    for (let j = i + 1; j < rects.length; j++) {
      const a = rects[i], b = rects[j];
      const ix = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      const iy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (ix > 0.5 && iy > 0.5) overlaps++;
    }
  }
  const main = document.getElementById('main-content')?.getBoundingClientRect();
  const overflow = main ? (main.right > window.innerWidth + 0.5 || main.bottom > window.innerHeight + 0.5) : true;
  const themeAttr = document.documentElement.getAttribute('data-tpaa-theme') || '';
  return JSON.stringify({ overlapCount: overlaps, overflow: overflow, themeAttr: themeAttr });
})()"""


class G7WebEngineAcceptanceError(RuntimeError):
    """A mandatory G7 visual acceptance check failed."""


def _seed_database(data_root: Path) -> None:
    from tpaa_storage import SQLiteDesktopUnitOfWork, bootstrap_sqlite

    database = data_root / "tpaa.sqlite3"
    bootstrap_sqlite(database, authority_root=AUTHORITY)
    with SQLiteDesktopUnitOfWork(database, write=True, authority_root=AUTHORITY) as uow:
        uow.canonical_rows.insert(
            "registry.training_session",
            {
                "session_id": g6.SESSION_ID,
                "session_code": "G7-WEB-001",
                "session_type": "LIVE",
                "start_session_time_us": 0,
                "end_session_time_us": 20_000_000,
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
                "job_id": g6.JOB_ID,
                "job_type": "EPISODE_DETECTION",
                "session_id": g6.SESSION_ID,
                "job_key": "g7-webengine-acceptance",
                "status": "SUCCEEDED",
                "component_version": "G7-WEB-1.0.0",
                "input_hash": "b" * 64,
            },
        )
        uow.canonical_rows.insert(
            "registry.analysis_release",
            {
                "release_id": g6.RELEASE_ID,
                "scope_type": "SESSION",
                "scope_key": g6.SESSION_ID,
                "session_id": g6.SESSION_ID,
                "release_no": 1,
                "compute_job_id": g6.JOB_ID,
                "catalog_version": "G7-WEB-ACCEPTANCE",
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
                "episode_id": g6.EPISODE_ID,
                "session_id": g6.SESSION_ID,
                "episode_type": "BVR_ENGAGEMENT",
                "start_session_time_us": 0,
                "end_session_time_us": 20_000_000,
                "subject_scope": "SESSION",
                "world_capability_code": "BVR_ENGAGEMENT",
                "episode_status": "DETECTED",
                "detector_version": "G7-WEB-1.0.0",
                "coverage": 1.0,
                "confidence": 0.9,
            },
        )
        for batch_id, batch_date, training_type in g6.BATCHES:
            uow.canonical_rows.insert(
                "registry.batch_registration",
                {
                    "batch_id": batch_id,
                    "session_id": g6.SESSION_ID,
                    "batch_date": batch_date,
                    "batch_training_type": training_type,
                    "training_type_confirmed": True,
                    "qualification_status": "QUALIFIED",
                    "source_manifest_sha256": "a" * 64,
                    "revision_no": 1,
                    "created_by": "g7-webengine-acceptance",
                },
            )
        uow.canonical_rows.insert(
            "world.world_relation",
            {
                "relation_id": CLUSTER_ID,
                "release_id": g6.RELEASE_ID,
                "episode_id": g6.EPISODE_ID,
                "relation_type": "ATTACK_CLUSTER",
                "subject_ref": g6.SHOOTER_ID,
                "object_ref": g6.TARGET_ID,
                "start_session_time_us": 13_000_000,
                "properties": {
                    "batch_id": g6.BATCHES[2][0],
                    "weapon_event_ids": [
                        "e6200000-0000-4000-8000-0000000000f5",
                        "e6200000-0000-4000-8000-0000000000f6",
                    ],
                },
                "confidence": 0.9,
                "relation_source": "DERIVED",
                "method_version": "G7-WEB-1.0.0",
            },
            field_kinds={"properties": "json"},
        )
        for index, (relation_id, _t1, _cat, _adj, _exc) in enumerate(WEAPON_EVENT_ROWS):
            uow.canonical_rows.insert(
                "world.world_relation",
                {
                    "relation_id": relation_id,
                    "release_id": g6.RELEASE_ID,
                    "episode_id": g6.EPISODE_ID,
                    "relation_type": "WEAPON_EVENT",
                    "subject_ref": g6.SHOOTER_ID,
                    "object_ref": g6.TARGET_ID,
                    "start_session_time_us": index * 1_000_000 + 6_000_000,
                    "properties": {
                        "batch_id": g6.BATCHES[2][0],
                        "category": _cat,
                        "category_rule_version": "WE-CAT-1.0.0",
                        "classification_exception": _exc,
                        "target_entity_id": g6.TARGET_ID,
                        "weapon_terminal_state": "TERMINAL_KNOWN",
                        "adjudication_state": _adj,
                        "observation_window_state": "WINDOW_CLOSED",
                        "identity_material": f"{g6.BATCHES[2][0]}|L{index}|{g6.SHOOTER_ID}|{index * 1_000_000 + 6_000_000}|IR",
                        "revision_no": 1,
                    },
                    "confidence": 0.9,
                    "relation_source": "DERIVED",
                    "method_version": "G7-WEB-1.0.0",
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
        raise G7WebEngineAcceptanceError(f"SCREENSHOT_FAILED:{path}")


def _set_theme(view: Any, theme: str) -> None:
    g4._evaluate(view, "document.querySelector('[data-module=\"support\"]')?.click(); true")
    g4._evaluate(view, "document.querySelector('[data-view=\"V25\"]')?.click(); true")
    g4._wait_for(
        view,
        "document.querySelectorAll('.themeChoice').length",
        lambda value: value == 3,
        label="v25-themes",
    )
    g4._evaluate(view, f"document.querySelector('[data-theme=\"{theme}\"]')?.click(); true")
    g4._evaluate(view, "document.querySelector('[data-module=\"training\"]')?.click(); true")
    g4._wait_for(
        view,
        "document.querySelectorAll('.v26Table tbody tr').length",
        lambda value: value >= 6,
        label="v26-return",
    )


def _set_ribbon(view: Any, *, collapsed: bool) -> None:
    expanded = g4._evaluate(
        view,
        "document.getElementById('app')?.classList.contains('ribbon-collapsed') === false",
    )
    if expanded == collapsed:
        g4._evaluate(view, "document.querySelector('[data-action=\"toggle-ribbon\"]')?.click(); true")


def _box_model(view: Any) -> dict[str, Any]:
    result = g4._evaluate(view, OVERLAP_SCRIPT)
    if not isinstance(result, str) or not result:
        raise G7WebEngineAcceptanceError(f"BOX_MODEL_EVAL_INVALID:{result!r}")
    decoded = json.loads(result)
    if not isinstance(decoded, dict):
        raise G7WebEngineAcceptanceError(f"BOX_MODEL_EVAL_INVALID:{decoded!r}")
    return decoded


def run() -> dict[str, object]:
    from PySide6.QtWidgets import QApplication

    from tpaa_gui.local_backend import LocalBackendController, LocalBackendState
    from tpaa_gui.webengine_shell import create_webengine_workspace

    app = QApplication.instance() or QApplication([sys.argv[0]])
    workspace = None
    captures: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="tpaa-g7-webengine-") as temporary:
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
                raise G7WebEngineAcceptanceError(f"BACKEND_NOT_READY:{started}")
            status, bootstrap = controller.product_request_json("GET", "/api/v1/gui/bootstrap")
            provenance = bootstrap.get("provenance")
            if (
                status != 200
                or not isinstance(provenance, dict)
                or provenance.get("core_baseline") != "CB-1.12.0"
            ):
                raise G7WebEngineAcceptanceError(f"BOOTSTRAP_INVALID:{status}:{bootstrap!r}")
            events_status, events = controller.product_request_json(
                "GET",
                f"/api/v1/gui/batches/{g6.BATCHES[2][0]}/weapon-events",
            )
            if (
                events_status != 200
                or events.get("schema") != "TPAA_G7_BATCH_EVENT_WORKBENCH_V1"
                or events.get("total_count") != len(WEAPON_EVENT_ROWS)
                or events.get("summary", {}).get("cluster_count") != 1
            ):
                raise G7WebEngineAcceptanceError(f"EVENTS_INVALID:{events_status}:{events!r}")
            binding = controller.webengine_binding()
            workspace = create_webengine_workspace(None, binding)
            workspace.show()
            view = workspace._tpaa_web_view
            if view is None:
                raise G7WebEngineAcceptanceError("WEBENGINE_VIEW_MISSING")
            for width, height in ((1600, 900), (1280, 720)):
                g6._resize_and_load(workspace, view, width, height)
                g4._evaluate(view, "window.dispatchEvent(new Event('resize')); true")
                g4._wait_for(
                    view,
                    "document.querySelectorAll('[data-module]:disabled').length",
                    lambda value: value == 0,
                    label="authorization",
                )
                g4._evaluate(
                    view, "document.querySelector('[data-module=\"training\"]')?.click(); true"
                )
                g4._wait_for(
                    view,
                    "document.querySelectorAll('.v26Table tbody tr').length",
                    lambda value: value >= 6,
                    label="v26-workbench",
                )
                _set_ribbon(view, collapsed=False)
                checks = {
                    "panels": "document.querySelectorAll('#main-content .p').length",
                    "rows": "document.querySelectorAll('.v26Table tbody tr').length",
                    "stats": "document.querySelectorAll('.v26Stats > div').length",
                    "tracks": "document.querySelectorAll('.v26TrackRow').length",
                    "cluster_badges": "Array.from(document.querySelectorAll('.v26Table .pill')).filter((e) => e.textContent.includes('簇')).length",
                }
                values = {name: g4._evaluate(view, script) for name, script in checks.items()}
                if values["panels"] != 4 or values["rows"] < 6 or values["stats"] != 3:
                    raise G7WebEngineAcceptanceError(f"CONTENT_CHECK_FAILED:{values!r}")
                if values["tracks"] < 6 or values["cluster_badges"] < 2:
                    raise G7WebEngineAcceptanceError(f"CONTENT_CHECK_FAILED:{values!r}")
                for theme in ("graphite", "tactical", "light"):
                    for collapsed in (False, True):
                        _set_ribbon(view, collapsed=collapsed)
                        _set_theme(view, theme)
                        box = _box_model(view)
                        if box["overlapCount"] != 0 or box["overflow"] is not False:
                            raise G7WebEngineAcceptanceError(
                                f"BOX_MODEL_FAIL:{width}x{height}:{theme}:"
                                f"collapsed={collapsed}:{box!r}"
                            )
                        name = (
                            f"g7_v26_{width}x{height}_{theme}"
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
        "schema": "TPAA_G7_V33_WEBENGINE_ACCEPTANCE_V1",
        "status": "PASS",
        "core_baseline": "CB-1.12.0",
        "parent_core_baseline": "CB-1.11.0",
        "view": "V26",
        "workset": {
            "batch_id": g6.BATCHES[2][0],
            "weapon_event_count": len(WEAPON_EVENT_ROWS),
            "cluster_count": 1,
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
    except (OSError, ValueError, KeyError, G7WebEngineAcceptanceError) as exc:
        print(f"G7_WEBENGINE_ACCEPTANCE_FAIL {exc}", file=sys.stderr)
        return 2
    captures = result["captures"]
    assert isinstance(captures, list)
    print(
        "G7_WEBENGINE_ACCEPTANCE_PASS "
        f"captures={len(captures)} box_model_no_overlap=True"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
