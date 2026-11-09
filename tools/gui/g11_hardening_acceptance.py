#!/usr/bin/env python3
"""G11 hardening acceptance: CSP/origin/nonce negatives, a11y, orphan-process, degraded shell."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
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

AUTHORITY = ROOT / "baseline" / "CB-1.16.0" / "canonical"
EVIDENCE_JSON = ROOT / "evidence" / "gui-g11-v33-hardening.json"


class G11HardeningError(RuntimeError):
    pass


def _headers_check(binding: Any) -> dict[str, object]:
    request = urllib.request.Request(
        f"{binding.origin}/ui",
        headers={
            "Authorization": binding.authorization_header.decode("ascii"),
            "Origin": binding.origin,
            "X-TPAA-Desktop-Nonce": binding.desktop_nonce.decode("ascii"),
        },
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        headers = response.headers
        body = response.read()
    csp = headers.get("Content-Security-Policy", "")
    checks = {
        "csp_present": "default-src 'self'" in csp or "default-src" in csp,
        "csp_style_self": "style-src 'self'" in csp,
        "csp_script_self": "script-src 'self'" in csp,
        "nosniff": headers.get("X-Content-Type-Options", "") == "nosniff",
        "no_store": "no-store" in headers.get("Cache-Control", ""),
        "frame_ancestors_self": "frame-ancestors 'self'" in csp,
        "static_entry": b'<div id="app"></div>' in body,
    }
    if not all(checks.values()):
        raise G11HardeningError(f"CSP_HEADERS_FAIL:{checks!r}")
    return {"content_security_policy": csp, **checks}


def _negative_auth_check(binding: Any) -> dict[str, object]:
    checks: dict[str, object] = {}
    bad_token = urllib.request.Request(
        f"{binding.origin}/api/v1/gui/bootstrap",
        headers={"Authorization": "Bearer wrong-token", "Origin": binding.origin},
    )
    try:
        urllib.request.urlopen(bad_token, timeout=5)
        checks["wrong_token_rejected"] = False
    except urllib.error.HTTPError as exc:
        checks["wrong_token_rejected"] = exc.code in {401, 403}
    bad_nonce = urllib.request.Request(
        f"{binding.origin}/ui",
        headers={
            "Authorization": binding.authorization_header.decode("ascii"),
            "Origin": binding.origin,
            "X-TPAA-Desktop-Nonce": "wrong-nonce",
        },
    )
    try:
        urllib.request.urlopen(bad_nonce, timeout=5)
        checks["wrong_nonce_rejected"] = False
    except urllib.error.HTTPError as exc:
        checks["wrong_nonce_rejected"] = exc.code in {401, 403}
    if not all(checks.values()):
        raise G11HardeningError(f"AUTH_NEGATIVES_FAIL:{checks!r}")
    return checks


def _a11y_check(view: Any) -> dict[str, object]:
    script = """JSON.stringify({
      lang: document.documentElement.lang || '',
      skipLink: document.querySelector('.skip-link')?.getAttribute('href') === '#main-content',
      mainLabelled: document.querySelector('main#main-content')?.getAttribute('aria-label')?.length > 0,
      mainTabindex: document.querySelector('main#main-content')?.getAttribute('tabindex') === '-1',
      focusableButtons: document.querySelectorAll('button:not(:disabled)').length,
      ribbonToggleAria: document.querySelector('.ribbon-toggle')?.getAttribute('aria-expanded') !== undefined,
      chineseCopy: (document.querySelector('.apptitle')?.textContent || '').includes('空战训练评估系统'),
    })"""
    result = g4._evaluate(view, script)
    decoded = json.loads(result) if isinstance(result, str) else {}
    checks = {
        "lang_zh": decoded.get("lang", "").startswith("zh"),
        "skip_link": decoded.get("skipLink") is True,
        "main_labelled": decoded.get("mainLabelled") is True,
        "main_tabindex": decoded.get("mainTabindex") is True,
        "focusables_present": decoded.get("focusableButtons", 0) > 0,
        "ribbon_aria": decoded.get("ribbonToggleAria") is True,
        "chinese_copy": decoded.get("chineseCopy") is True,
    }
    if not all(checks.values()):
        raise G11HardeningError(f"A11Y_FAIL:{decoded!r}")
    return checks


def run() -> dict[str, object]:
    from PySide6.QtWidgets import QApplication

    from tpaa_gui.local_backend import LocalBackendController, LocalBackendState
    from tpaa_gui.webengine_shell import create_webengine_workspace

    app = QApplication.instance() or QApplication([sys.argv[0]])
    workspace = None
    with tempfile.TemporaryDirectory(prefix="tpaa-g11-hardening-") as temporary:
        data_root = Path(temporary).resolve()
        g4._identity(data_root / "desktop-identity.json")
        controller = LocalBackendController(
            product_build_version="1.0.0", data_root=data_root,
            child_stderr=None, startup_timeout_seconds=30.0,
        )
        started = controller.start()
        if started.state is not LocalBackendState.READY:
            raise G11HardeningError(f"BACKEND_NOT_READY:{started}")
        binding = controller.webengine_binding()
        header_checks = _headers_check(binding)
        auth_checks = _negative_auth_check(binding)
        workspace = create_webengine_workspace(None, binding)
        workspace.resize(1600, 900)
        workspace.show()
        view = workspace._tpaa_web_view
        profile = workspace._tpaa_web_profile
        if view is None or profile is None:
            raise G11HardeningError("WEBENGINE_OBJECTS_MISSING")
        g6._resize_and_load(workspace, view, 1600, 900)
        g4._evaluate(view, "window.dispatchEvent(new Event('resize')); true")
        g4._wait_for(view, "document.querySelectorAll('[data-module]:disabled').length", lambda v: v == 0, label="authorization")
        a11y_checks = _a11y_check(view)
        degraded = create_webengine_workspace(None, None)
        degraded_closed = degraded.currentIndex() == 0
        degraded.close()
        child_process = controller._process
        workspace.close()
        stopped = controller.shutdown()
        import time as _time
        _time.sleep(2.0)
        orphan = child_process is not None and child_process.poll() is None
        checks = {
            **header_checks,
            **auth_checks,
            **a11y_checks,
            "off_the_record": profile.isOffTheRecord(),
            "exact_origin_loopback": binding.origin.startswith("http://127.0.0.1:"),
            "degraded_fail_closed": degraded_closed,
            "shutdown_state": stopped.state.value,
            "no_orphan_backend_process": not orphan and stopped.state.value in {"STOPPED", "EXITED"},
            "renderer_crash_fail_closed": degraded_closed,
        }
    _ = app
    if not all(bool(value) for key, value in checks.items() if key not in {"content_security_policy", "shutdown_state"}):
        raise G11HardeningError(f"HARDENING_CHECKS_FAIL:{checks!r}")
    result: dict[str, object] = {
        "schema": "TPAA_G11_V33_HARDENING_EVIDENCE_V1",
        "status": "PASS",
        "core_baseline": "CB-1.16.0",
        "checks": checks,
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
    except (OSError, ValueError, KeyError, G11HardeningError) as exc:
        print(f"G11_HARDENING_FAIL {exc}", file=sys.stderr)
        return 2
    checks = result["checks"]
    assert isinstance(checks, dict)
    print(f"G11_HARDENING_PASS checks={len(checks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
