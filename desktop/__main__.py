import sys

from PySide6.QtWidgets import QApplication

from desktop.account import ensure_account_service
from desktop.icons import app_icon
from desktop.theme import apply_theme
from desktop.window import NovelWindow


def main() -> None:
    ensure_account_service()
    app = QApplication(sys.argv)
    app.setApplicationName("Novel")
    app.setWindowIcon(app_icon())
    apply_theme(app)
    window = NovelWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
