"""Composed Desktop runtime: PySide6 shell plus owned local backend child."""

from __future__ import annotations

from collections.abc import Sequence

from .local_backend import LocalBackendController
from .shell import GuiShellConfig, run_gui


def run_desktop(
    argv: Sequence[str] | None = None,
    *,
    config: GuiShellConfig | None = None,
    auto_close_ms: int | None = None,
    show: bool = True,
    backend: LocalBackendController | None = None,
) -> int:
    """Run the GUI while owning exactly one authenticated local backend lifecycle."""

    controller = backend or LocalBackendController()
    controller.start()
    try:
        return run_gui(argv, config=config, auto_close_ms=auto_close_ms, show=show)
    finally:
        controller.shutdown()
