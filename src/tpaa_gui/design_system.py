"""W4 design tokens, themes, and DPI-safe metrics for the Qt presentation layer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Theme(StrEnum):
    LIGHT = "LIGHT"
    DARK = "DARK"
    HIGH_CONTRAST = "HIGH_CONTRAST"


@dataclass(frozen=True, slots=True)
class ScaledMetrics:
    space_xs: int
    space_sm: int
    space_md: int
    space_lg: int
    control_height: int
    table_row_height: int
    navigation_width: int
    drawer_width: int
    radius: int


def scaled_metrics(logical_dpi: float = 96.0) -> ScaledMetrics:
    if logical_dpi <= 0:
        raise ValueError("logical_dpi must be positive")
    factor = min(2.0, max(1.0, logical_dpi / 96.0))

    def px(value: int) -> int:
        return max(1, round(value * factor))

    return ScaledMetrics(
        space_xs=px(4),
        space_sm=px(8),
        space_md=px(12),
        space_lg=px(18),
        control_height=px(34),
        table_row_height=px(32),
        navigation_width=min(px(248), 320),
        drawer_width=min(px(320), 400),
        radius=px(6),
    )


_COLORS = {
    Theme.LIGHT: {
        "window": "#f3f6fa",
        "surface": "#ffffff",
        "surface_alt": "#eaf0f6",
        "text": "#182230",
        "muted": "#526174",
        "border": "#c7d2df",
        "accent": "#1769aa",
        "accent_soft": "#dbeeff",
        "focus": "#e07a00",
        "danger": "#b42318",
        "success": "#087a43",
    },
    Theme.DARK: {
        "window": "#111821",
        "surface": "#182330",
        "surface_alt": "#223142",
        "text": "#f2f6fb",
        "muted": "#b5c2d1",
        "border": "#415268",
        "accent": "#58a6e7",
        "accent_soft": "#173a57",
        "focus": "#ffb454",
        "danger": "#ff7b72",
        "success": "#56d59a",
    },
    Theme.HIGH_CONTRAST: {
        "window": "#000000",
        "surface": "#000000",
        "surface_alt": "#111111",
        "text": "#ffffff",
        "muted": "#ffffff",
        "border": "#ffffff",
        "accent": "#00ffff",
        "accent_soft": "#002f2f",
        "focus": "#ffff00",
        "danger": "#ff6666",
        "success": "#66ff99",
    },
}


def theme_stylesheet(theme: Theme = Theme.LIGHT, logical_dpi: float = 96.0) -> str:
    metrics = scaled_metrics(logical_dpi)
    color = _COLORS[theme]
    return f"""
QWidget {{
  color: {color['text']}; background: {color['window']}; font-size: 10pt;
  font-family: "Segoe UI", "Microsoft YaHei UI", "Noto Sans CJK SC", sans-serif;
}}
QMainWindow, QWidget#tpaaShellCentralWidget {{ background: {color['window']}; }}
QFrame[tpaaSurface="true"], QGroupBox {{
  background: {color['surface']}; border: 1px solid {color['border']};
  border-radius: {metrics.radius}px; margin-top: {metrics.space_sm}px;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: {metrics.space_md}px; padding: 0 4px; }}
QLabel[tpaaMuted="true"] {{ color: {color['muted']}; }}
QLabel[tpaaHeading="true"] {{ font-size: 15pt; font-weight: 650; }}
QPushButton, QComboBox, QLineEdit {{
  min-height: {metrics.control_height}px; background: {color['surface']};
  border: 1px solid {color['border']}; border-radius: {metrics.radius}px;
  padding: 0 {metrics.space_sm}px;
}}
QPushButton:hover, QComboBox:hover, QLineEdit:hover {{ border-color: {color['accent']}; }}
QPushButton:focus, QComboBox:focus, QLineEdit:focus, QListWidget:focus, QTableView:focus {{
  border: 2px solid {color['focus']};
}}
QListWidget, QTableView, QPlainTextEdit {{
  background: {color['surface']}; alternate-background-color: {color['surface_alt']};
  border: 1px solid {color['border']}; selection-background-color: {color['accent_soft']};
  selection-color: {color['text']};
}}
QListWidget::item {{ min-height: {metrics.control_height}px; padding: 0 {metrics.space_sm}px; }}
QListWidget::item:selected {{ border-left: 4px solid {color['accent']}; font-weight: 650; }}
QHeaderView::section {{
  background: {color['surface_alt']}; border: 0; border-right: 1px solid {color['border']};
  border-bottom: 1px solid {color['border']}; padding: {metrics.space_sm}px;
}}
QStatusBar, QFrame#tpaaShellStatusBar {{
  background: {color['surface']}; border-top: 1px solid {color['border']};
}}
QLabel[tpaaState="error"] {{ color: {color['danger']}; font-weight: 650; }}
QLabel[tpaaState="success"] {{ color: {color['success']}; font-weight: 650; }}
""".strip()


__all__ = ["ScaledMetrics", "Theme", "scaled_metrics", "theme_stylesheet"]
