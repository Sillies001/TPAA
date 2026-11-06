#!/usr/bin/env python3
"""Run authenticated G2 WebEngine theme, keyboard, focus and DPI acceptance."""

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
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class G2WebEngineAcceptanceError(RuntimeError):
    """One authenticated product-shell acceptance assertion failed."""


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _identity(path: Path) -> None:
    from tpaa_security import ASSIGNMENT_SCHEMA, sign_assignment

    key_name = "TPAA_G2_WEBENGINE_ACCEPTANCE_KEY"
    key = "g2-webengine-local-acceptance-only"
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "schema": ASSIGNMENT_SCHEMA,
        "key_id": key_name,
        "account_id": getpass.getuser(),
        "device_id": platform.node(),
        "subject": "g2-webengine-local-administrator",
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
        raise G2WebEngineAcceptanceError("JAVASCRIPT_EVALUATION_TIMEOUT")
    return result[0]


def _wait_for(
    view: Any,
    script: str,
    predicate: Callable[[Any], bool],
    *,
    label: str,
    timeout_seconds: float = 10.0,
) -> Any:
    deadline = time.monotonic() + timeout_seconds
    last: Any = None
    while time.monotonic() < deadline:
        last = _evaluate(view, script)
        if predicate(last):
            return last
        time.sleep(0.05)
    raise G2WebEngineAcceptanceError(
        f"JAVASCRIPT_CONDITION_TIMEOUT:{label}:{last!r}"
    )


def _direct_v24_status(binding: Any) -> tuple[int, str]:
    request = urllib.request.Request(
        f"{binding.origin}/ui?view=V24",
        headers={
            "Authorization": binding.authorization_header.decode("ascii"),
            "Origin": binding.origin,
            "X-TPAA-Desktop-Nonce": binding.desktop_nonce.decode("ascii"),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def _settle_rendering(milliseconds: int = 500) -> None:
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def _snapshot(view: Any) -> dict[str, Any]:
    value = _evaluate(
        view,
        """
        JSON.stringify((() => {
          const main = document.querySelector('#main-content');
          const mainRect = main?.getBoundingClientRect();
          const clipped = [...document.querySelectorAll('button')]
            .filter((item) => item instanceof HTMLElement && item.offsetParent !== null)
            .filter((item) => item.scrollWidth > item.clientWidth + 1)
            .map((item) => item.textContent?.trim() || item.getAttribute('aria-label') || 'button');
          return {
            session: document.querySelector('.session-indicator')?.textContent?.trim() || '',
            view: document.querySelector('.page-heading .eyebrow')?.textContent?.trim() || '',
            currentView: document.querySelector('[data-view][aria-current="page"]')?.getAttribute('data-view') || '',
            currentModule: document.querySelector('[data-module][aria-current="page"]')?.getAttribute('data-module') || '',
            title: document.querySelector('.page-heading h2')?.textContent?.trim() || '',
            theme: document.documentElement.dataset.tpaaTheme || '',
            state: document.querySelector('.state-panel')?.className || '',
            disabledModules: document.querySelectorAll('[data-module]:disabled').length,
            ribbonExpanded: document.querySelector('[data-action="toggle-ribbon"]')?.getAttribute('aria-expanded'),
            subnavHidden: document.querySelector('.subnav')?.classList.contains('is-hidden') || false,
            activeModule: document.activeElement?.getAttribute('data-module'),
            activeView: document.activeElement?.getAttribute('data-view'),
            activeClass: document.activeElement?.className || '',
            viewport: [window.innerWidth, window.innerHeight],
            dpr: window.devicePixelRatio,
            horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
            mainWithinViewport: Boolean(mainRect && mainRect.left >= -1 && mainRect.right <= window.innerWidth + 1),
            clippedButtons: clipped,
          };
        })())
        """,
    )
    if not isinstance(value, str):
        raise G2WebEngineAcceptanceError(f"INVALID_DOM_SNAPSHOT:{type(value).__name__}")
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise G2WebEngineAcceptanceError("INVALID_DOM_SNAPSHOT_JSON")
    return parsed


def run(output: Path, screenshot_dir: Path, *, scale: float) -> dict[str, object]:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication

    from tpaa_gui.local_backend import LocalBackendController, LocalBackendState
    from tpaa_gui.webengine_shell import create_webengine_workspace

    output = output.resolve()
    screenshot_dir = screenshot_dir.resolve()
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([sys.argv[0]])
    screenshots: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="tpaa-g2-webengine-") as temporary:
        data_root = Path(temporary).resolve()
        identity_path = data_root / "desktop-identity.json"
        _identity(identity_path)
        controller = LocalBackendController(
            product_build_version="1.0.0",
            data_root=data_root,
            child_stderr=None,
            startup_timeout_seconds=30.0,
        )
        workspace = None
        try:
            started = controller.start()
            if started.state is not LocalBackendState.READY:
                raise G2WebEngineAcceptanceError(f"BACKEND_NOT_READY:{started}")
            status, session = controller.security_request_json("GET", "/security/session")
            if status != 200 or session.get("gui_permission_activation_status") != "ACTIVE":
                raise G2WebEngineAcceptanceError(f"ACTIVE_SESSION_REQUIRED:{status}:{session!r}")
            if session.get("roles") != ["ADMINISTRATOR"]:
                raise G2WebEngineAcceptanceError(f"ADMIN_SESSION_REQUIRED:{session!r}")
            binding = controller.webengine_binding()
            direct_status, direct_body = _direct_v24_status(binding)
            if direct_status != 403 or "V24_REQUIRES_V08_CONTEXT" not in direct_body:
                raise G2WebEngineAcceptanceError(
                    f"V24_DIRECT_GUARD_FAILED:{direct_status}:{direct_body}"
                )
            workspace = create_webengine_workspace(None, binding)
            workspace.resize(1280, 720)
            workspace.show()
            view = workspace._tpaa_web_view
            if view is None:
                raise G2WebEngineAcceptanceError("WEB_VIEW_MISSING")
            loop = QEventLoop()
            loaded: list[bool] = []

            def finish_loading(ok: bool) -> None:
                loaded.append(ok)
                loop.quit()

            view.loadFinished.connect(finish_loading)
            QTimer.singleShot(15_000, loop.quit)
            loop.exec()
            if loaded != [True]:
                raise G2WebEngineAcceptanceError(f"WEBENGINE_LOAD_FAILED:{loaded}")
            _wait_for(
                view,
                "document.querySelector('.session-indicator')?.textContent?.includes('会话已核验') || false",
                lambda value: value is True,
                label="authorization-ready",
            )
            _settle_rendering()
            initial = _snapshot(view)
            if initial["currentView"] != "V01" or initial["disabledModules"] != 0:
                raise G2WebEngineAcceptanceError(f"INITIAL_NAVIGATION_INVALID:{initial!r}")
            if initial["theme"] != "graphite":
                raise G2WebEngineAcceptanceError(f"DEFAULT_THEME_INVALID:{initial!r}")

            _evaluate(view, "document.querySelector('[data-view=\"V25\"]')?.click(); true")
            _wait_for(
                view,
                "document.querySelector('.page-heading .eyebrow')?.textContent?.endsWith('V25') || false",
                lambda value: value is True,
                label="navigate-v25",
            )
            theme_records: list[dict[str, object]] = []
            for theme in ("tactical", "graphite", "light"):
                _evaluate(
                    view,
                    f"document.querySelector('[data-theme=\"{theme}\"]')?.click(); true",
                )
                def theme_selected(value: Any, expected: str = theme) -> bool:
                    return bool(value == expected)

                _wait_for(
                    view,
                    "document.documentElement.dataset.tpaaTheme",
                    theme_selected,
                    label=f"theme-{theme}",
                )
                app.processEvents()
                _settle_rendering()
                image = screenshot_dir / f"g2_{theme}_{int(scale * 100)}pct.png"
                if not view.grab().save(str(image), "PNG"):
                    raise G2WebEngineAcceptanceError(f"SCREENSHOT_FAILED:{image}")
                record: dict[str, object] = {
                    "theme": theme,
                    "path": image.relative_to(ROOT).as_posix(),
                    "sha256": _digest(image),
                    "bytes": image.stat().st_size,
                }
                screenshots.append(record)
                theme_records.append(record)

            _evaluate(
                view,
                "document.querySelector('[data-action=\"toggle-ribbon\"]')?.click(); true",
            )
            collapsed = _snapshot(view)
            if collapsed["ribbonExpanded"] != "false" or collapsed["subnavHidden"] is not True:
                raise G2WebEngineAcceptanceError(f"RIBBON_COLLAPSE_FAILED:{collapsed!r}")

            _evaluate(
                view,
                "window.dispatchEvent(new KeyboardEvent('keydown',{key:'2',altKey:true,bubbles:true})); true",
            )
            _wait_for(
                view,
                "document.querySelector('.page-heading .eyebrow')?.textContent?.endsWith('V26') || false",
                lambda value: value is True,
                label="keyboard-v26",
            )
            keyboard_landing = _snapshot(view)

            _evaluate(
                view,
                "window.dispatchEvent(new KeyboardEvent('keydown',{key:'1',altKey:true,bubbles:true})); true",
            )
            _wait_for(
                view,
                "document.querySelector('[data-view][aria-current=\"page\"]')?.getAttribute('data-view') === 'V01'",
                lambda value: value is True,
                label="keyboard-v01",
            )
            focus_result = _evaluate(
                view,
                """
                JSON.stringify((() => {
                  const button = document.querySelector('[data-module="overview"]');
                  button?.focus();
                  const before = document.activeElement?.getAttribute('data-module');
                  button?.click();
                  return {
                    before,
                    after: document.activeElement?.getAttribute('data-module'),
                    currentView: document.querySelector('[data-view][aria-current="page"]')?.getAttribute('data-view'),
                  };
                })())
                """,
            )
            if not isinstance(focus_result, str):
                raise G2WebEngineAcceptanceError("FOCUS_RESULT_INVALID")
            focus_transaction = json.loads(focus_result)
            if focus_transaction != {
                "before": "overview",
                "after": "overview",
                "currentView": "V01",
            }:
                raise G2WebEngineAcceptanceError(
                    f"FOCUS_RESTORE_FAILED:{focus_transaction!r}"
                )
            focus_snapshot = _snapshot(view)
            if focus_snapshot["currentView"] != "V01":
                raise G2WebEngineAcceptanceError(f"ALT_NAVIGATION_FAILED:{focus_snapshot!r}")

            _evaluate(
                view,
                "window.dispatchEvent(new KeyboardEvent('keydown',{key:'2',altKey:true,bubbles:true})); true",
            )
            _wait_for(
                view,
                "document.querySelector('[data-module][aria-current=\"page\"]')?.getAttribute('data-module') === 'training'",
                lambda value: value is True,
                label="return-training-module",
            )
            _evaluate(view, "document.querySelector('[data-view=\"V08\"]')?.click(); true")
            _wait_for(
                view,
                "document.querySelector('.page-heading .eyebrow')?.textContent?.endsWith('V08') || false",
                lambda value: value is True,
                label="navigate-v08",
            )
            v24 = _evaluate(
                view,
                """
                JSON.stringify((() => {
                  const button = document.querySelector('[data-action="enter-v24"]');
                  return {
                    disabled: button?.hasAttribute('disabled') || false,
                    ariaDisabled: button?.getAttribute('aria-disabled'),
                    directNavPresent: Boolean(document.querySelector('[data-view="V24"]')),
                    currentView: document.querySelector('[data-view][aria-current="page"]')?.getAttribute('data-view') || '',
                  };
                })())
                """,
            )
            if not isinstance(v24, str):
                raise G2WebEngineAcceptanceError("V24_UI_GUARD_RESULT_INVALID")
            v24_value = json.loads(v24)
            if not isinstance(v24_value, dict) or v24_value != {
                "disabled": True,
                "ariaDisabled": "true",
                "directNavPresent": False,
                "currentView": "V08",
            }:
                raise G2WebEngineAcceptanceError(
                    f"V24_UI_GUARD_FAILED:{v24_value!r}"
                )

            final_snapshot = _snapshot(view)
            dpr = float(final_snapshot["dpr"])
            if dpr + 0.05 < scale:
                raise G2WebEngineAcceptanceError(f"DEVICE_SCALE_FACTOR_INVALID:{dpr}:{scale}")
            if final_snapshot["horizontalOverflow"] is True:
                raise G2WebEngineAcceptanceError(f"HORIZONTAL_OVERFLOW:{final_snapshot!r}")
            if final_snapshot["mainWithinViewport"] is not True:
                raise G2WebEngineAcceptanceError(f"MAIN_CLIPPED:{final_snapshot!r}")
            if final_snapshot["clippedButtons"]:
                raise G2WebEngineAcceptanceError(f"BUTTON_TEXT_CLIPPED:{final_snapshot!r}")
            profile = workspace._tpaa_web_profile
            if profile is None:
                raise G2WebEngineAcceptanceError("WEB_PROFILE_MISSING")
            result: dict[str, object] = {
                "schema": "TPAA_G2_V33_WEBENGINE_ACCEPTANCE_V1",
                "status": "PASS",
                "scale": scale,
                "device_pixel_ratio": dpr,
                "session_authority": {
                    "id": session.get("gui_permission_authority_id"),
                    "version": session.get("gui_permission_authority_version"),
                    "activation": session.get("gui_permission_activation_status"),
                    "role": "ADMINISTRATOR",
                    "gui_permission_count": len(session.get("gui_permissions", [])),
                },
                "exact_origin": binding.origin,
                "off_the_record": bool(profile.isOffTheRecord()),
                "direct_v24_http_status": direct_status,
                "initial": initial,
                "themes": theme_records,
                "ribbon_collapsed": collapsed,
                "keyboard_training_landing": keyboard_landing,
                "focus_restored": focus_snapshot,
                "focus_transaction": focus_transaction,
                "v24_ui_guard": v24_value,
                "final_geometry": final_snapshot,
                "release_claim": False,
            }
        finally:
            if workspace is not None:
                workspace.close()
                app.processEvents()
            stopped = controller.shutdown()
        result["shutdown_state"] = stopped.state.value
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "PASS", "output": str(output)}, ensure_ascii=False))
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--screenshot-dir", type=Path, required=True)
    parser.add_argument("--scale", type=float, choices=(1.0, 1.5), required=True)
    args = parser.parse_args(argv)
    os.environ.setdefault("POLARS_SKIP_CPU_CHECK", "1")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
    os.environ["QT_SCALE_FACTOR"] = f"{args.scale:g}"
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        "--disable-gpu --disable-extensions "
        f"--force-device-scale-factor={args.scale:g}"
    )
    try:
        run(args.output, args.screenshot_dir, scale=args.scale)
    except (OSError, ValueError, KeyError, G2WebEngineAcceptanceError) as exc:
        print(f"G2_WEBENGINE_ACCEPTANCE_FAIL {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
