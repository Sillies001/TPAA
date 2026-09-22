#!/usr/bin/env python3
"""Real local-backend lifecycle smoke for M0-GUI-002."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tpaa_gui import LocalBackendController, LocalBackendState


def _unauthenticated_status(port: int) -> int:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1.0)
    except urllib.error.HTTPError as exc:
        return exc.code
    return 200


def run_smoke() -> dict[str, object]:
    controller = LocalBackendController(product_build_version="0.0.0", startup_timeout_seconds=10)
    ready = controller.start()
    if not ready.ready or ready.state is not LocalBackendState.READY or ready.port is None:
        raise RuntimeError(f"local backend did not enter READY: {ready}")
    unauthenticated = _unauthenticated_status(ready.port)
    exited = controller.shutdown()
    checks = {
        "owned_child_ready": "PASS" if ready.ready and ready.pid is not None else "FAIL",
        "ephemeral_loopback_http": "PASS" if ready.port is not None and ready.port > 0 else "FAIL",
        "bearer_required": "PASS" if unauthenticated == 401 else "FAIL",
        "graceful_shutdown": "PASS" if exited.state is LocalBackendState.EXITED and not exited.ready else "FAIL",
        "cleanup": "PASS" if exited.port is None else "FAIL",
    }
    if any(value != "PASS" for value in checks.values()):
        raise RuntimeError(f"M0-GUI-002 smoke failed: {checks}")
    return {"m0_gui_002": checks, "status": "PASS"}


def main() -> int:
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
