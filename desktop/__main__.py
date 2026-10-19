import sys

from PySide6.QtWidgets import QApplication

from desktop.theme import QSS
from desktop.window import NovelWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Novel")
    app.setStyleSheet(QSS)
    window = NovelWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
