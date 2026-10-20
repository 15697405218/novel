"""Dark teal skin from theme_v2.qss."""

import sys
from pathlib import Path

from PySide6.QtGui import QColor, QPalette

MORE = """
QScrollArea, QStackedWidget { background: transparent; border: none; }
QLineEdit#server { background: transparent; border: none; color: #6b8a84; padding: 0; }
QPushButton#primary, QPushButton#outline, QPushButton#danger { border-radius: 999px; }
QPushButton#danger { background-color: #f0a35e; color: #2a1608; border: none; font-weight: 600; }
QPushButton#danger:hover { background-color: #f6b87a; }
QPushButton#send {
    background-color: #1de9b6; color: #04241c; border: none; border-radius: 18px;
    min-width: 36px; max-width: 36px; min-height: 36px; max-height: 36px; padding: 0;
}
QFrame#cover { background-color: #14685c; border: none; border-radius: 12px; min-height: 128px; }
QLabel#cover-char {
    color: #e7fff8; font-size: 42px; font-family: "Source Han Serif SC", "SimSun", serif; background: transparent;
}
QFrame#empty-card { background: transparent; border: 1px dashed rgba(160, 230, 214, 0.28); border-radius: 12px; }
QFrame#section { background-color: rgba(18, 36, 42, 150); border: 1px solid rgba(160, 230, 214, 0.12); border-radius: 12px; }
QFrame#login-mark { background-color: #1de9b6; border-radius: 22px; min-width: 44px; max-width: 44px; min-height: 44px; max-height: 44px; }
QLabel#brand { font-size: 28px; font-weight: 700; color: #f4fffc; background: transparent; }
QCheckBox#switch::indicator { width: 36px; height: 20px; border-radius: 10px; }
QCheckBox#switch::indicator:checked { background: #1de9b6; border: 1px solid #1de9b6; }
QPlainTextEdit#summary {
    min-height: 72px; max-height: 96px; font-size: 13px; color: #c8d6d2;
    background-color: rgba(16, 28, 34, 180);
}
"""


def apply_theme(app) -> None:
    app.setStyle("Fusion")
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#0a141a"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e8f2ef"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#102028"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#12242c"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#f4fffc"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#143038"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e8fff8"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#1de9b6"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#04241c"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#6b8a84"))
    app.setPalette(palette)
    sheet = (Path(__file__).resolve().parent / "theme_v2.qss").read_text(encoding="utf-8")
    app.setStyleSheet(sheet + MORE)


def enable_glass(window) -> None:
    if sys.platform != "win32":
        return
    from ctypes import byref, c_int, sizeof, windll

    handle = int(window.winId())
    backdrop = c_int(3)
    windll.dwmapi.DwmSetWindowAttribute(handle, 38, byref(backdrop), sizeof(backdrop))
    dark = c_int(1)
    windll.dwmapi.DwmSetWindowAttribute(handle, 20, byref(dark), sizeof(dark))
