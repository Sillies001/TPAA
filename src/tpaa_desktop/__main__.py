"""Run the public TPAA Desktop profile."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from tpaa_gui.desktop import run_desktop
from tpaa_gui.local_backend import LocalBackendController
from tpaa_gui.shell import GuiShellConfig, GuiShellMode
from tpaa_runtime import project_version


def main(
    argv: Sequence[str] | None = None,
    *,
    app_root: Path | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="tpaa-desktop")
    parser.add_argument("--data-root", type=Path)
    parser.add_argument(
        "--gui-shell",
        choices=("legacy", "v33"),
        default="legacy",
        help="Select the legacy diagnostic shell or the feature-gated v33 WebEngine shell.",
    )
    args, qt_args = parser.parse_known_args(argv)
    if args.data_root is not None and not args.data_root.is_absolute():
        parser.error("--data-root must be an absolute path")
    backend = LocalBackendController(
        product_build_version=project_version(app_root),
        data_root=args.data_root,
    )
    mode = GuiShellMode.WEBENGINE_V33 if args.gui_shell == "v33" else GuiShellMode.LEGACY_WIDGETS
    return run_desktop(qt_args, backend=backend, config=GuiShellConfig(mode=mode))


if __name__ == "__main__":
    raise SystemExit(main())
