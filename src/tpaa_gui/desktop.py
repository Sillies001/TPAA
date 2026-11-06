"""Composed Desktop runtime: PySide6 shell plus owned local backend child."""

from __future__ import annotations

from collections.abc import Sequence

from .local_backend import LocalBackendController, LocalBackendError
from .shell import GuiShellConfig, GuiShellMode, run_gui


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
    try:
        try:
            controller.start()
        except LocalBackendError:
            # Fail closed but keep the Desktop shell alive so M0-GUI-003 can
            # display the captured readiness/version diagnostics.
            pass
        shell_config = config or GuiShellConfig()
        binding = None
        if shell_config.mode is GuiShellMode.WEBENGINE_V33:
            try:
                binding = controller.webengine_binding()
            except LocalBackendError:
                binding = None
        return run_gui(
            argv,
            config=shell_config,
            auto_close_ms=auto_close_ms,
            show=show,
            diagnostics_provider=lambda: controller.diagnostics,
            m1_transport=controller,
            product_transport=controller,
            webengine_binding=binding,
        )
    finally:
        controller.shutdown()
