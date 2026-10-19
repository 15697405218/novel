"""Dark writing desk. Qt draws every pixel; nothing is loaded in a browser."""

BG = "#14131c"
SIDEBAR = "#1b1924"
PANEL = "#221f2c"
RAISED = "#2a2736"
LINE = "#343044"
TEXT = "#f3f1f8"
MUTED = "#a39eb4"
ACCENT = "#7c6cf0"
ACCENT_HOVER = "#8d7ef6"
DANGER = "#e06b72"

QSS = f"""
* {{
    font-family: "Microsoft YaHei UI", "Segoe UI";
    font-size: 13px;
    color: {TEXT};
}}
QMainWindow, QWidget#root {{
    background: {BG};
}}
QFrame#sidebar, QFrame#chat {{
    background: {SIDEBAR};
}}
QFrame#card {{
    background: {PANEL};
    border: 1px solid {LINE};
    border-radius: 12px;
}}
QLabel#title {{
    font-size: 28px;
    font-weight: 600;
}}
QLabel#muted, QLabel#hint {{
    color: {MUTED};
}}
QLineEdit, QPlainTextEdit, QTextEdit, QListWidget, QTreeWidget, QComboBox {{
    background: {BG};
    border: 1px solid {LINE};
    border-radius: 8px;
    padding: 6px 8px;
    selection-background-color: {ACCENT};
}}
QTextEdit#editor {{
    background: #191722;
    border: none;
    padding: 28px 36px;
    font-size: 16px;
    line-height: 1.7;
}}
QPushButton {{
    background: {RAISED};
    border: 1px solid {LINE};
    border-radius: 8px;
    padding: 6px 12px;
}}
QPushButton:hover {{
    background: #342f46;
}}
QPushButton#primary {{
    background: {ACCENT};
    border: none;
    color: white;
    padding: 8px 16px;
}}
QPushButton#primary:hover {{
    background: {ACCENT_HOVER};
}}
QPushButton#quiet {{
    background: transparent;
    border: none;
    text-align: left;
    padding: 8px 12px;
    color: {MUTED};
}}
QPushButton#quiet:checked {{
    background: #2c2840;
    color: {TEXT};
    border-radius: 8px;
}}
QStatusBar {{
    background: {SIDEBAR};
    color: {MUTED};
}}
QSplitter::handle {{
    background: {LINE};
}}
QMenu {{
    background: {PANEL};
    border: 1px solid {LINE};
}}
QMenu::item:selected {{
    background: {ACCENT};
}}
"""
