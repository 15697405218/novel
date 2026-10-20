"""Dialogs with the same title, hint, and footer as the original desk."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def _button(text: str, slot, primary: bool = False) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("primary" if primary else "outline")
    button.setCursor(Qt.PointingHandCursor)
    button.clicked.connect(slot)
    return button


class FormDialog(QDialog):
    def __init__(self, title: str, description: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        self._glass = False
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(14)
        heading = QLabel(title)
        heading.setObjectName("dialog-title")
        root.addWidget(heading)
        self._hint = QLabel(description)
        self._hint.setObjectName("muted")
        self._hint.setWordWrap(True)
        if description:
            root.addWidget(self._hint)
        else:
            self._hint.hide()
            root.addWidget(self._hint)
        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        root.addLayout(self.body)
        self.footer = QHBoxLayout()
        self.footer.addStretch(1)
        root.addLayout(self.footer)
    def label(self, text: str) -> QLabel:
        widget = QLabel(text)
        widget.setObjectName("field")
        self.body.addWidget(widget)
        return widget

    def add(self, widget: QWidget) -> None:
        self.body.addWidget(widget)

    def cancel(self, text: str = "取消") -> None:
        self.footer.addWidget(_button(text, self.reject))

    def primary(self, text: str, slot) -> QPushButton:
        button = _button(text, slot, True)
        button.setDefault(True)
        self.footer.addWidget(button)
        return button

    def danger(self, text: str, slot) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("danger")
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(slot)
        self.footer.addWidget(button)
        return button

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._glass:
            self._glass = True
            from desktop.theme import enable_glass

            enable_glass(self)

    def set_description(self, text: str) -> None:
        self._hint.setText(text)
        self._hint.setVisible(bool(text))

def confirm(parent: QWidget, title: str, body: str, **kwargs) -> bool:
    return ask(parent, title, body, **kwargs)


def ask(
    parent: QWidget,
    title: str,
    body: str,
    yes: str = "确认",
    no: str = "取消",
    danger: bool = False,
) -> bool:
    dialog = FormDialog(title, body, parent)
    dialog.cancel(no)
    accepted = {"ok": False}

    def accept() -> None:
        accepted["ok"] = True
        dialog.accept()

    if danger:
        dialog.danger(yes, accept)
    else:
        dialog.primary(yes, accept)
    dialog.exec()
    return accepted["ok"]


def alert(parent: QWidget, title: str, body: str) -> None:
    dialog = FormDialog(title, body, parent)
    dialog.primary("关闭", dialog.accept)
    dialog.exec()


def prompt(parent: QWidget, title: str, label: str, text: str = "") -> str | None:
    dialog = FormDialog(title, "", parent)
    field = QLineEdit(text)
    dialog.label(label)
    dialog.add(field)
    dialog.cancel()
    value: dict[str, str | None] = {"text": None}

    def save() -> None:
        value["text"] = field.text()
        dialog.accept()

    dialog.primary("确定", save)
    dialog.exec()
    return value["text"]
