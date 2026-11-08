#!/usr/bin/env python3
"""Run the real Windows WebEngine G4 V23-to-V01 acceptance loop."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import platform
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

SESSION_ID = "d4400000-0000-4000-8000-000000000001"
AIRCRAFT_ID = "d4400000-0000-4000-8000-000000000002"
CONTEXT_ID = "d4400000-0000-4000-8000-000000000003"


class G4WebEngineAcceptanceError(RuntimeError):
    """A mandatory G4 desktop loop failed."""


def _identity(path: Path) -> None:
    from tpaa_security import ASSIGNMENT_SCHEMA, sign_assignment

    key_name = "TPAA_G4_WEBENGINE_ACCEPTANCE_KEY"
    key = "g4-webengine-local-acceptance-only"
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "schema": ASSIGNMENT_SCHEMA,
        "key_id": key_name,
        "account_id": getpass.getuser(),
        "device_id": platform.node(),
        "subject": "g4-webengine-local-administrator",
        "roles": ["ADMINISTRATOR"],
        "scopes": ["*"],
        "issued_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
    }
    path.write_text(
        json.dumps(
            {**payload, "signature": sign_assignment(payload, key.encode("utf-8"))},
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    os.environ[key_name] = key
    os.environ["TPAA_DESKTOP_IDENTITY_FILE"] = str(path)
    os.environ["TPAA_DESKTOP_IDENTITY_KEY_REF"] = f"env://{key_name}"


def _seed_database(data_root: Path) -> None:
    from tpaa_storage import SQLiteDesktopUnitOfWork, bootstrap_sqlite

    authority = ROOT / "baseline" / "CB-1.9.0" / "canonical"
    database = data_root / "tpaa.sqlite3"
    bootstrap_sqlite(database, authority_root=authority)
    with SQLiteDesktopUnitOfWork(database, write=True, authority_root=authority) as uow:
        uow.canonical_rows.insert(
            "registry.training_session",
            {
                "session_id": SESSION_ID,
                "session_code": "G4-WEB-001",
                "session_type": "LIVE",
                "start_session_time_us": 0,
                "end_session_time_us": 1_000_000,
                "training_type_set": (),
                "data_status": "IMPORTED",
                "source_count": 1,
                "schema_version": "1.10.0",
            },
            field_kinds={"training_type_set": "text_array"},
        )
        uow.commit()


def _csv() -> bytes:
    return (
        b"source_time_us,session_time_us,p_deg_s,nz_g,heading_deg_true,"
        b"tas_kt,mach,quality_mask\n"
        b"0,0,0,1.0,0,200,0.60,0\n"
        b"100000,100000,5,1.1,10,201,0.61,0\n"
    )


def _evaluate(view: Any, script: str, *, timeout_ms: int = 5_000) -> Any:
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    result: list[Any] = []

    def completed(value: Any) -> None:
        result.append(value)
        loop.quit()

    view.page().runJavaScript(script, completed)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    if not result:
        raise G4WebEngineAcceptanceError("JAVASCRIPT_EVALUATION_TIMEOUT")
    return result[0]


def _wait_for(
    view: Any,
    script: str,
    predicate: Callable[[Any], bool],
    *,
    label: str,
    timeout_seconds: float = 20.0,
) -> Any:
    deadline = time.monotonic() + timeout_seconds
    last: Any = None
    while time.monotonic() < deadline:
        last = _evaluate(view, script)
        if predicate(last):
            return last
        time.sleep(0.05)
    raise G4WebEngineAcceptanceError(f"CONDITION_TIMEOUT:{label}:{last!r}")


def _fill(view: Any, selector: str, value: str) -> None:
    selector_json = json.dumps(selector)
    value_json = json.dumps(value)
    result = _evaluate(
        view,
        f"""(() => {{
          const element = document.querySelector({selector_json});
          if (!element) return false;
          element.value = {value_json};
          element.dispatchEvent(new Event('input', {{bubbles:true}}));
          element.dispatchEvent(new Event('change', {{bubbles:true}}));
          return true;
        }})()""",
    )
    if result is not True:
        raise G4WebEngineAcceptanceError(f"FORM_CONTROL_MISSING:{selector}")


def run(output: Path, *, scale: float) -> dict[str, object]:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication, QFileDialog

    from tpaa_gui.local_backend import LocalBackendController, LocalBackendState
    from tpaa_gui.webengine_shell import create_webengine_workspace

    app = QApplication.instance() or QApplication([sys.argv[0]])
    workspace = None
    result: dict[str, object] = {}
    original_picker = QFileDialog.getOpenFileName
    with tempfile.TemporaryDirectory(prefix="tpaa-g4-webengine-") as temporary:
        data_root = Path(temporary).resolve()
        _identity(data_root / "desktop-identity.json")
        _seed_database(data_root)
        source = data_root / "flight.csv"
        source.write_bytes(_csv())
        QFileDialog.getOpenFileName = staticmethod(  # type: ignore[method-assign]
            lambda *_args, **_kwargs: (str(source), "CSV 文件 (*.csv)")
        )
        controller = LocalBackendController(
            product_build_version="1.0.0",
            data_root=data_root,
            child_stderr=None,
            startup_timeout_seconds=30.0,
        )
        try:
            started = controller.start()
            if started.state is not LocalBackendState.READY:
                raise G4WebEngineAcceptanceError(f"BACKEND_NOT_READY:{started}")
            status, bootstrap = controller.product_request_json("GET", "/api/v1/gui/bootstrap")
            provenance = bootstrap.get("provenance")
            if (
                status != 200
                or not isinstance(provenance, dict)
                or provenance.get("core_baseline") != "CB-1.9.0"
            ):
                raise G4WebEngineAcceptanceError(f"BOOTSTRAP_INVALID:{status}:{bootstrap!r}")
            binding = controller.webengine_binding()
            workspace = create_webengine_workspace(None, binding)
            workspace.resize(1440, 900)
            workspace.show()
            view = workspace._tpaa_web_view
            profile = workspace._tpaa_web_profile
            if view is None or profile is None:
                raise G4WebEngineAcceptanceError("WEBENGINE_OBJECTS_MISSING")
            loop = QEventLoop()
            loaded: list[bool] = []

            def finish_loading(ok: bool) -> None:
                loaded.append(ok)
                loop.quit()

            view.loadFinished.connect(finish_loading)
            QTimer.singleShot(20_000, loop.quit)
            loop.exec()
            if loaded != [True]:
                raise G4WebEngineAcceptanceError(f"WEBENGINE_LOAD_FAILED:{loaded}")
            _wait_for(
                view,
                "document.querySelectorAll('[data-module]:disabled').length",
                lambda value: value == 0,
                label="authorization",
            )
            _evaluate(view, "document.querySelector('[data-module=\"support\"]')?.click(); true")
            _evaluate(view, "document.querySelector('[data-view=\"V23\"]')?.click(); true")
            _wait_for(
                view,
                "document.querySelector('#batch-registration-form') !== null",
                lambda value: value is True,
                label="v23",
            )
            _evaluate(view, "document.querySelector('[data-action=\"select-file\"]')?.click(); true")
            _wait_for(
                view,
                "document.querySelector('.ticket-card')?.textContent || ''",
                lambda value: isinstance(value, str) and "flight.csv" not in value and len(value) > 20,
                label="native-ticket",
            )
            values = {
                "session_id": SESSION_ID,
                "aircraft_id": AIRCRAFT_ID,
                "batch_date": "2026-11-07",
                "batch_training_type": "COMPREHENSIVE_OPPOSITION",
                "producer_system": "RECORDER_EXPORT",
                "session_code": "G4-WEB-001",
                "session_type": "LIVE",
                "context_id": CONTEXT_ID,
            }
            for name, value in values.items():
                _fill(view, f'[name="{name}"]', value)
            _evaluate(
                view,
                "document.querySelector('[name=\"training_type_confirmed\"]')?.click(); true",
            )
            _evaluate(view, "document.querySelector('#batch-registration-form')?.requestSubmit(); true")
            batch_id = _wait_for(
                view,
                "document.querySelector('[data-batch-id]')?.getAttribute('data-batch-id') || ''",
                lambda value: isinstance(value, str) and len(value) == 36,
                label="qualified-v01",
            )
            _evaluate(view, "document.querySelector('[data-module=\"support\"]')?.click(); true")
            _evaluate(view, "document.querySelector('[data-view=\"V23\"]')?.click(); true")
            _wait_for(
                view,
                "document.querySelector('#training-type-revision-form') !== null",
                lambda value: value is True,
                label="revision-panel",
            )
            _fill(view, '#training-type-revision-form [name="batch_training_type"]', "MIXED_OPPOSITION")
            _fill(view, '#training-type-revision-form [name="reason"]', "G4 Windows WebEngine 复核")
            _evaluate(view, "document.querySelector('#training-type-revision-form')?.requestSubmit(); true")
            _wait_for(
                view,
                "document.querySelector('.revision-panel .state-pill')?.textContent || ''",
                lambda value: isinstance(value, str) and "2" in value,
                label="training-revision",
            )
            context_values = {
                "valid_from_session_time_us": "0",
                "valid_to_session_time_us": "1000000",
                "source": "MANUAL_REVIEWED",
                "reason": "G4 Windows WebEngine 编队复核",
                "member_aircraft_id": AIRCRAFT_ID,
                "formation_id": "BLUE-1",
                "side": "BLUE",
                "member_role": "LEAD",
            }
            for name, value in context_values.items():
                _fill(view, f'#force-formation-form [name="{name}"]', value)
            _evaluate(view, "document.querySelector('#force-formation-form')?.requestSubmit(); true")
            _wait_for(
                view,
                "document.querySelectorAll('.revision-panel .state-ready').length",
                lambda value: isinstance(value, (int, float)) and value >= 2,
                label="context-revision",
            )
            list_status, batches = controller.product_request_json("GET", "/api/v1/gui/batches")
            items = batches.get("items")
            if list_status != 200 or not isinstance(items, list) or len(items) != 1:
                raise G4WebEngineAcceptanceError(f"BATCH_LIST_INVALID:{batches!r}")
            screenshot = output.with_suffix(".png").resolve()
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            if not workspace.grab().save(str(screenshot), "PNG"):
                raise G4WebEngineAcceptanceError("SCREENSHOT_FAILED")
            result = {
                "schema": "TPAA_G4_V33_WEBENGINE_ACCEPTANCE_V1",
                "status": "PASS",
                "scale": scale,
                "exact_origin": binding.origin,
                "off_the_record": profile.isOffTheRecord(),
                "core_baseline": provenance.get("core_baseline"),
                "batch_id": batch_id,
                "batch_status": items[0].get("qualification_status"),
                "training_type_revision": items[0].get("revision_no"),
                "native_path_exposed": False,
                "v23_to_v01_loop": "PASS",
                "force_formation_revision": "PASS",
                "screenshot": screenshot.relative_to(ROOT).as_posix(),
                "screenshot_sha256": hashlib.sha256(screenshot.read_bytes()).hexdigest(),
                "release_claim": False,
            }
        finally:
            QFileDialog.getOpenFileName = original_picker  # type: ignore[method-assign]
            if workspace is not None:
                workspace.close()
                app.processEvents()
            stopped = controller.shutdown()
        result["shutdown_state"] = stopped.state.value
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "output": str(output)}, ensure_ascii=False))
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scale", type=float, choices=(1.0, 1.5), required=True)
    args = parser.parse_args(argv)
    os.environ.setdefault("POLARS_SKIP_CPU_CHECK", "1")
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
    os.environ["QT_SCALE_FACTOR"] = f"{args.scale:g}"
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        f"--disable-extensions --force-device-scale-factor={args.scale:g}"
    )
    os.environ["TPAA_AUTHORITY_ROOT"] = str(
        (ROOT / "baseline" / "CB-1.9.0" / "canonical").resolve()
    )
    try:
        run(args.output, scale=args.scale)
    except (OSError, ValueError, KeyError, G4WebEngineAcceptanceError) as exc:
        print(f"G4_WEBENGINE_ACCEPTANCE_FAIL {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
