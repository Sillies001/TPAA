#!/usr/bin/env python3
"""Run the feature-gated v33 WebEngine empty-shell lifecycle smoke."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

os.environ.setdefault("POLARS_SKIP_CPU_CHECK", "1")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault(
    "QTWEBENGINE_CHROMIUM_FLAGS",
    "--disable-gpu --disable-extensions --force-device-scale-factor=1",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tpaa_gui.local_backend import LocalBackendController, LocalBackendState  # noqa: E402
from tpaa_gui.webengine_shell import create_webengine_workspace  # noqa: E402

OUTPUT = REPO_ROOT / "evidence" / "gui-g1-v33-webengine-smoke.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    _app = QApplication.instance() or QApplication([sys.argv[0]])
    with tempfile.TemporaryDirectory(prefix="tpaa-g1-web-") as temporary:
        controller = LocalBackendController(
            product_build_version="1.0.0",
            data_root=Path(temporary).resolve(),
            child_stderr=None,
        )
        try:
            started = controller.start()
            if started.state is not LocalBackendState.READY:
                raise RuntimeError(f"backend not ready: {started}")
            binding = controller.webengine_binding()
            request = urllib.request.Request(
                f"{binding.origin}/ui",
                headers={
                    "Authorization": binding.authorization_header.decode("ascii"),
                    "Origin": binding.origin,
                    "X-TPAA-Desktop-Nonce": binding.desktop_nonce.decode("ascii"),
                },
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                if response.status != 200 or b'<div id="app"></div>' not in response.read():
                    raise RuntimeError("authenticated /ui preflight failed")
            workspace = create_webengine_workspace(None, binding)
            workspace.resize(1280, 720)
            workspace.show()
            view = workspace._tpaa_web_view
            profile = workspace._tpaa_web_profile
            if view is None or profile is None:
                raise RuntimeError("WebEngine workspace did not retain native objects")
            page = workspace._tpaa_web_page
            if page is None:
                raise RuntimeError("WebEngine workspace did not retain its page")
            loop = QEventLoop()
            loaded: list[bool] = []
            loading_diagnostics: list[dict[str, object]] = []
            navigation_blocked: list[str] = []

            def capture_loading(info: Any) -> None:
                loading_diagnostics.append(
                    {
                        "status": str(info.status()),
                        "url": info.url().toString(),
                        "error_code": int(info.errorCode()),
                        "error": info.errorString(),
                    }
                )

            def finish_loading(ok: bool) -> None:
                loaded.append(ok)
                loop.quit()

            view.loadFinished.connect(finish_loading)
            view.page().loadingChanged.connect(capture_loading)
            page.navigation_blocked.connect(navigation_blocked.append)
            QTimer.singleShot(15_000, loop.quit)
            loop.exec()
            if loaded != [True]:
                raise RuntimeError(
                    "WebEngine load failed or timed out: "
                    f"{loaded} {loading_diagnostics} blocked={navigation_blocked}"
                )
            if view.url().toString() != f"{binding.origin}/ui":
                raise RuntimeError("WebEngine exact origin drift")
            if not profile.isOffTheRecord():
                raise RuntimeError("WebEngine profile is persistent")
            degraded = create_webengine_workspace(None, None)
            if degraded.currentIndex() != 0:
                raise RuntimeError("backend-unavailable state is not fail-closed")
            result = {
                "schema": "TPAA_G1_V33_WEBENGINE_SMOKE_V1",
                "status": "PASS",
                "exact_origin": binding.origin,
                "off_the_record": True,
                "static_entry": "/ui",
                "backend_degraded_state": "PASS",
                "shutdown_state": None,
                "release_claim": False,
            }
            degraded.close()
            workspace.close()
        finally:
            stopped = controller.shutdown()
        result["shutdown_state"] = stopped.state.value
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
