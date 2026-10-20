import sys

from PySide6.QtWidgets import QApplication

from desktop.icons import app_icon
from desktop.theme import apply_theme
from desktop.window import NovelWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Novel")
    app.setWindowIcon(app_icon())
    apply_theme(app)
    window = NovelWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
