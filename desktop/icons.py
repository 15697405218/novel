"""Line icons drawn from the same shapes as the original toolbar."""

from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_PATHS = {
    "undo": (
        '<path d="M9 14 4 9l5-5"/>'
        '<path d="M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5a5.5 5.5 0 0 1-5.5 5.5H11"/>'
    ),
    "redo": (
        '<path d="m15 14 5-5-5-5"/>'
        '<path d="M20 9H9.5A5.5 5.5 0 0 0 4 14.5A5.5 5.5 0 0 0 9.5 20H13"/>'
    ),
    "paragraph": (
        '<path d="M13 4v16"/>'
        '<path d="M17 4v16"/>'
        '<path d="M19 4H9.5a4.5 4.5 0 0 0 0 9H13"/>'
    ),
    "bold": (
        '<path d="M6 12h9a4 4 0 0 0 0-8H6z"/>'
        '<path d="M6 12h11a4 4 0 0 1 0 8H6z"/>'
    ),
    "italic": (
        '<line x1="19" x2="10" y1="4" y2="4"/>'
        '<line x1="14" x2="5" y1="20" y2="20"/>'
        '<line x1="15" x2="9" y1="4" y2="20"/>'
    ),
    "underline": (
        '<path d="M6 4v6a6 6 0 0 0 12 0V4"/>'
        '<line x1="4" x2="20" y1="20" y2="20"/>'
    ),
    "strike": (
        '<path d="M16 4H9a3 3 0 0 0-2.83 4"/>'
        '<path d="M14 12a4 4 0 0 1 0 8H6"/>'
        '<line x1="4" x2="20" y1="12" y2="12"/>'
    ),
    "code": (
        '<polyline points="16 18 22 12 16 6"/>'
        '<polyline points="8 6 2 12 8 18"/>'
    ),
    "highlight": (
        '<path d="m9 11-6 6v3h9l3-3"/>'
        '<path d="m22 12-4.6 4.6a2 2 0 0 1-2.8 0l-5.2-5.2a2 2 0 0 1 0-2.8L14 4"/>'
    ),
    "align-left": (
        '<line x1="21" x2="3" y1="6" y2="6"/>'
        '<line x1="15" x2="3" y1="12" y2="12"/>'
        '<line x1="17" x2="3" y1="18" y2="18"/>'
    ),
    "align-center": (
        '<line x1="18" x2="6" y1="6" y2="6"/>'
        '<line x1="21" x2="3" y1="12" y2="12"/>'
        '<line x1="18" x2="6" y1="18" y2="18"/>'
    ),
    "align-right": (
        '<line x1="21" x2="3" y1="6" y2="6"/>'
        '<line x1="21" x2="9" y1="12" y2="12"/>'
        '<line x1="21" x2="7" y1="18" y2="18"/>'
    ),
    "align-justify": (
        '<line x1="3" x2="21" y1="6" y2="6"/>'
        '<line x1="3" x2="21" y1="12" y2="12"/>'
        '<line x1="3" x2="21" y1="18" y2="18"/>'
    ),
    "list": (
        '<line x1="8" x2="21" y1="6" y2="6"/>'
        '<line x1="8" x2="21" y1="12" y2="12"/>'
        '<line x1="8" x2="21" y1="18" y2="18"/>'
        '<line x1="3" x2="3.01" y1="6" y2="6"/>'
        '<line x1="3" x2="3.01" y1="12" y2="12"/>'
        '<line x1="3" x2="3.01" y1="18" y2="18"/>'
    ),
    "list-ordered": (
        '<line x1="10" x2="21" y1="6" y2="6"/>'
        '<line x1="10" x2="21" y1="12" y2="12"/>'
        '<line x1="10" x2="21" y1="18" y2="18"/>'
        '<path d="M4 6h1v4"/>'
        '<path d="M4 10h2"/>'
        '<path d="M6 18H4c0-1 2-2 2-3s-1-1.5-2-1"/>'
    ),
    "list-todo": (
        '<rect x="3" y="5" width="6" height="6" rx="1"/>'
        '<path d="m3 17 2 2 4-4"/>'
        '<path d="M13 6h8"/>'
        '<path d="M13 12h8"/>'
        '<path d="M13 18h8"/>'
    ),
    "quote": (
        '<path d="M16 3a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2 1 1 0 0 1 1 1v1a2 2 0 0 1-2 2 1 1 0 0 0-1 1v2a1 1 0 0 0 1 1 6 6 0 0 0 6-6V5a2 2 0 0 0-2-2z"/>'
        '<path d="M5 3a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2 1 1 0 0 1 1 1v1a2 2 0 0 1-2 2 1 1 0 0 0-1 1v2a1 1 0 0 0 1 1 6 6 0 0 0 6-6V5a2 2 0 0 0-2-2z"/>'
    ),
    "code-block": (
        '<rect width="18" height="18" x="3" y="3" rx="2"/>'
        '<path d="m10 10-2 2 2 2"/>'
        '<path d="m14 14 2-2-2-2"/>'
    ),
    "link": (
        '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
        '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>'
    ),
    "book": (
        '<path d="M12 7v14"/>'
        '<path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>'
    ),
    "pencil": (
        '<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/>'
        '<path d="m15 5 4 4"/>'
    ),
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "bell": (
        '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/>'
        '<path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>'
    ),
    "plus": '<path d="M5 12h14"/><path d="M12 5v14"/>',
    "minimize": '<path d="M5 12h14"/>',
    "maximize": '<rect width="14" height="14" x="5" y="5" rx="2"/>',
    "close": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "mail": (
        '<rect width="20" height="16" x="2" y="4" rx="2"/>'
        '<path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>'
    ),
    "lock": (
        '<rect width="18" height="11" x="3" y="11" rx="2"/>'
        '<path d="M7 11V7a5 5 0 0 1 10 0v4"/>'
    ),
    "eye": (
        '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/>'
        '<circle cx="12" cy="12" r="3"/>'
    ),
    "trash": (
        '<path d="M3 6h18"/><path d="M8 6V4h8v2"/>'
        '<path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/>'
    ),
    "globe": (
        '<circle cx="12" cy="12" r="10"/>'
        '<path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>'
    ),
    "clock": (
        '<circle cx="12" cy="12" r="10"/>'
        '<path d="M12 6v6l4 2"/>'
    ),
    "cpu": (
        '<rect width="16" height="16" x="4" y="4" rx="2"/>'
        '<rect width="6" height="6" x="9" y="9" rx="1"/>'
        '<path d="M9 2v2"/><path d="M15 2v2"/><path d="M9 20v2"/><path d="M15 20v2"/>'
        '<path d="M2 9h2"/><path d="M2 15h2"/><path d="M20 9h2"/><path d="M20 15h2"/>'
    ),
    "upload": (
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
        '<polyline points="17 8 12 3 7 8"/>'
        '<line x1="12" x2="12" y1="3" y2="15"/>'
    ),
    "users": (
        '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>'
        '<circle cx="9" cy="7" r="4"/>'
        '<path d="M22 21v-2a4 4 0 0 0-3-3.87"/>'
        '<path d="M16 3.13a4 4 0 0 1 0 7.75"/>'
    ),
    "settings": (
        '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>'
        '<circle cx="12" cy="12" r="3"/>'
    ),
    "brain": (
        '<path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/>'
        '<path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z"/>'
        '<path d="M15 13a4.5 4.5 0 0 1-3-4 4.5 4.5 0 0 1-3 4"/>'
        '<path d="M17.599 6.5a3 3 0 0 0 .399-1.375"/>'
        '<path d="M6.003 5.125A3 3 0 0 0 6.401 6.5"/>'
        '<path d="M3.477 10.896a4 4 0 0 1 .585-.396"/>'
        '<path d="M19.938 10.5a4 4 0 0 1 .585.396"/>'
        '<path d="M6 18a4 4 0 0 1-1.967-.516"/>'
        '<path d="M19.967 17.484A4 4 0 0 1 18 18"/>'
    ),
}


def icon(name: str, color: str = "#e0ddef") -> QIcon:
    body = _PATHS.get(name, _PATHS["paragraph"])
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" '
        f'stroke-linejoin="round">{body}</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def app_icon() -> QIcon:
    path = Path(__file__).resolve().parent / "assets" / "novel.svg"
    renderer = QSvgRenderer(str(path))
    mark = QIcon()
    for size in (16, 20, 24, 32, 48, 64, 128, 256):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        mark.addPixmap(pixmap)
    return mark
