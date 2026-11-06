"""Cross-platform semantic icons backed by the active Qt platform style."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class IconName(StrEnum):
    OPEN = "OPEN"
    REFRESH = "REFRESH"
    INFORMATION = "INFORMATION"
    WARNING = "WARNING"
    ERROR = "ERROR"
    PLAY = "PLAY"
    PAUSE = "PAUSE"


_STANDARD_PIXMAP = {
    IconName.OPEN: "SP_DialogOpenButton",
    IconName.REFRESH: "SP_BrowserReload",
    IconName.INFORMATION: "SP_MessageBoxInformation",
    IconName.WARNING: "SP_MessageBoxWarning",
    IconName.ERROR: "SP_MessageBoxCritical",
    IconName.PLAY: "SP_MediaPlay",
    IconName.PAUSE: "SP_MediaPause",
}


def standard_icon(qt_widgets: Any, widget: Any, name: IconName) -> Any:
    """Resolve a semantic icon through QStyle for native DPI/theme rendering."""

    pixmap_name = _STANDARD_PIXMAP[name]
    pixmap = getattr(qt_widgets.QStyle.StandardPixmap, pixmap_name)
    return widget.style().standardIcon(pixmap)


__all__ = ["IconName", "standard_icon"]
