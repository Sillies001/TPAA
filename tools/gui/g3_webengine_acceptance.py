#!/usr/bin/env python3
"""Run the real local-backend/WebEngine G3 gateway acceptance."""

from __future__ import annotations

import argparse
import getpass
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


class G3WebEngineAcceptanceError(RuntimeError):
    """The authenticated G3 desktop acceptance failed."""


def _identity(path: Path) -> None:
    from tpaa_security import ASSIGNMENT_SCHEMA, sign_assignment

    key_name = "TPAA_G3_WEBENGINE_ACCEPTANCE_KEY"
    key = "g3-webengine-local-acceptance-only"
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "schema": ASSIGNMENT_SCHEMA,
        "key_id": key_name,
        "account_id": getpass.getuser(),
        "device_id": platform.node(),
        "subject": "g3-webengine-local-administrator",
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
        raise G3WebEngineAcceptanceError("JAVASCRIPT_EVALUATION_TIMEOUT")
    return result[0]


def _wait_for(
    view: Any,
    script: str,
    predicate: Callable[[Any], bool],
    *,
    label: str,
    timeout_seconds: float = 15.0,
) -> Any:
    deadline = time.monotonic() + timeout_seconds
    last: Any = None
    while time.monotonic() < deadline:
        last = _evaluate(view, script)
        if predicate(last):
            return last
        time.sleep(0.05)
    raise G3WebEngineAcceptanceError(f"JAVASCRIPT_CONDITION_TIMEOUT:{label}:{last!r}")


def run(output: Path, *, scale: float) -> dict[str, object]:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication

    from tpaa_gui.local_backend import LocalBackendController, LocalBackendState
    from tpaa_gui.webengine_shell import create_webengine_workspace

    app = QApplication.instance() or QApplication([sys.argv[0]])
    workspace = None
    result: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="tpaa-g3-webengine-") as temporary:
        data_root = Path(temporary).resolve()
        _identity(data_root / "desktop-identity.json")
        controller = LocalBackendController(
            product_build_version="1.0.0",
            data_root=data_root,
            child_stderr=None,
            startup_timeout_seconds=30.0,
        )
        try:
            started = controller.start()
            if started.state is not LocalBackendState.READY:
                raise G3WebEngineAcceptanceError(f"BACKEND_NOT_READY:{started}")
            status, bootstrap = controller.product_request_json("GET", "/api/v1/gui/bootstrap")
            if status != 200 or bootstrap.get("schema") != "TPAA_GUI_BOOTSTRAP_V1":
                raise G3WebEngineAcceptanceError(f"BOOTSTRAP_FAILED:{status}:{bootstrap!r}")
            provenance = bootstrap.get("provenance")
            if not isinstance(provenance, dict) or provenance.get("core_baseline") != "CB-1.8.0":
                raise G3WebEngineAcceptanceError(f"BOOTSTRAP_PROVENANCE_INVALID:{provenance!r}")
            principal = bootstrap.get("principal")
            if not isinstance(principal, dict) or principal.get("roles") != ["ADMINISTRATOR"]:
                raise G3WebEngineAcceptanceError(f"BOOTSTRAP_PRINCIPAL_INVALID:{principal!r}")
            catalog = bootstrap.get("catalog")
            if not isinstance(catalog, dict) or len(catalog.get("views", [])) != 26:
                raise G3WebEngineAcceptanceError("BOOTSTRAP_CATALOG_INVALID")

            page_status, page_one = controller.product_request_json(
                "GET", "/api/v1/gui/selectors/views?limit=7"
            )
            cursor = page_one.get("next_cursor")
            if (
                page_status != 200
                or len(page_one.get("items", [])) != 7
                or not isinstance(cursor, str)
            ):
                raise G3WebEngineAcceptanceError(f"SELECTOR_PAGE_ONE_INVALID:{page_one!r}")
            next_status, page_two = controller.product_request_json(
                "GET", f"/api/v1/gui/selectors/views?limit=7&cursor={cursor}"
            )
            if next_status != 200 or page_one.get("items") == page_two.get("items"):
                raise G3WebEngineAcceptanceError(f"SELECTOR_PAGE_TWO_INVALID:{page_two!r}")
            empty_status, empty = controller.product_request_json(
                "GET", "/api/v1/gui/selectors/batches"
            )
            if (
                empty_status != 200
                or empty.get("items") != []
                or empty.get("reason_code") != "CONTEXT_REQUIRED"
            ):
                raise G3WebEngineAcceptanceError(f"DYNAMIC_SELECTOR_TRUTH_INVALID:{empty!r}")

            binding = controller.webengine_binding()
            workspace = create_webengine_workspace(None, binding)
            workspace.resize(1280, 720)
            workspace.show()
            view = workspace._tpaa_web_view
            if view is None:
                raise G3WebEngineAcceptanceError("WEB_VIEW_MISSING")
            loop = QEventLoop()
            loaded: list[bool] = []

            def finish_loading(ok: bool) -> None:
                loaded.append(ok)
                loop.quit()

            view.loadFinished.connect(finish_loading)
            QTimer.singleShot(15_000, loop.quit)
            loop.exec()
            if loaded != [True]:
                raise G3WebEngineAcceptanceError(f"WEBENGINE_LOAD_FAILED:{loaded}")
            _wait_for(
                view,
                "document.querySelectorAll('[data-module]:disabled').length",
                lambda value: value == 0,
                label="bootstrap-authorization-ready",
            )
            _evaluate(
                view,
                """
                window.__tpaaG3Probe = null;
                (async () => {
                  try {
                    const response = await fetch('/api/v1/gui/bootstrap', {
                      credentials: 'same-origin', cache: 'no-store', headers: {Accept: 'application/json'}
                    });
                    const body = await response.json();
                    window.__tpaaG3Probe = {status: response.status, body};
                  } catch (error) {
                    window.__tpaaG3Probe = {status: 0, error: String(error)};
                  }
                })();
                true;
                """,
            )
            probe_json = _wait_for(
                view,
                "window.__tpaaG3Probe ? JSON.stringify(window.__tpaaG3Probe) : ''",
                lambda value: isinstance(value, str) and bool(value),
                label="webengine-gateway-probe",
            )
            probe = json.loads(probe_json)
            if (
                probe.get("status") != 200
                or probe.get("body", {}).get("schema") != "TPAA_GUI_BOOTSTRAP_V1"
            ):
                raise G3WebEngineAcceptanceError(f"WEBENGINE_GATEWAY_PROBE_FAILED:{probe!r}")
            snapshot_json = _evaluate(
                view,
                """
                JSON.stringify({
                  view: document.querySelector('[data-view][aria-current="page"]')?.getAttribute('data-view') || '',
                  module: document.querySelector('[data-module][aria-current="page"]')?.getAttribute('data-module') || '',
                  theme: document.documentElement.dataset.tpaaTheme || '',
                  disabledModules: document.querySelectorAll('[data-module]:disabled').length,
                  overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
                  dpr: window.devicePixelRatio
                })
                """,
            )
            snapshot = json.loads(snapshot_json)
            if (
                snapshot.get("view") != "V01"
                or snapshot.get("module") != "overview"
                or snapshot.get("theme") != "graphite"
                or snapshot.get("disabledModules") != 0
                or snapshot.get("overflow") is not False
                or float(snapshot.get("dpr", 0)) + 0.05 < scale
            ):
                raise G3WebEngineAcceptanceError(f"WEBENGINE_SHELL_INVALID:{snapshot!r}")
            profile = workspace._tpaa_web_profile
            if profile is None or not profile.isOffTheRecord():
                raise G3WebEngineAcceptanceError("WEBENGINE_PROFILE_NOT_EPHEMERAL")
            result = {
                "schema": "TPAA_G3_V33_WEBENGINE_ACCEPTANCE_V1",
                "status": "PASS",
                "scale": scale,
                "exact_origin": binding.origin,
                "off_the_record": True,
                "bootstrap": {
                    "core_baseline": provenance.get("core_baseline"),
                    "authority_id": provenance.get("authority_id"),
                    "view_count": len(catalog.get("views", [])),
                    "cache_partition_key_redacted": True,
                },
                "pagination": {
                    "page_one_count": len(page_one.get("items", [])),
                    "page_two_count": len(page_two.get("items", [])),
                    "overlap": page_one.get("items") == page_two.get("items"),
                },
                "dynamic_selector": {
                    "items": empty.get("items"),
                    "reason_code": empty.get("reason_code"),
                },
                "webengine_probe": {
                    "status": probe.get("status"),
                    "schema": probe.get("body", {}).get("schema"),
                },
                "shell": snapshot,
                "release_claim": False,
            }
        finally:
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
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
    os.environ["QT_SCALE_FACTOR"] = f"{args.scale:g}"
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        f"--disable-gpu --disable-extensions --force-device-scale-factor={args.scale:g}"
    )
    try:
        run(args.output, scale=args.scale)
    except (OSError, ValueError, KeyError, G3WebEngineAcceptanceError) as exc:
        print(f"G3_WEBENGINE_ACCEPTANCE_FAIL {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
