#!/usr/bin/env python3
"""Deterministic M0-GUI-001 PySide6 startup/exit smoke."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tpaa_gui import GuiShellError, run_gui  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args(argv)

    if args.headless:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        exit_code = run_gui(["tpaa-gui-smoke"], auto_close_ms=0, show=not args.headless)
    except GuiShellError as exc:
        print(json.dumps({"m0_gui_001": {"startup_exit": "FAIL", "error": str(exc)}, "status": "FAIL"}, indent=2))
        return 2

    passed = exit_code == 0
    print(
        json.dumps(
            {
                "m0_gui_001": {
                    "startup_exit": "PASS" if passed else "FAIL",
                    "exit_code": exit_code,
                    "headless": args.headless,
                },
                "status": "PASS" if passed else "FAIL",
            },
            indent=2,
        )
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
