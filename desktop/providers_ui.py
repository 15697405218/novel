"""Local model connections. Keys never leave this computer."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from desktop.dialogs import FormDialog, confirm
from desktop.i18n import tr
from desktop.icons import icon
from desktop.store import Library

CATALOG = (
    ("openrouter", "OpenRouter", "https://openrouter.ai/api/v1", "z-ai/glm-5.2:free", True),
    ("openai", "OpenAI", "https://api.openai.com/v1", "gpt-4o-mini", False),
    ("anthropic", "Anthropic", "https://api.anthropic.com", "claude-haiku-4-5", False),
    ("groq", "Groq", "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile", False),
    ("gemini", "Google Gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.0-flash", False),
    ("cohere", "Cohere", "https://api.cohere.ai/compatibility/v1", "command-r-08-2024", False),
    ("ollama", "Ollama", "http://127.0.0.1:11434/v1", "llama3.2", False),
    ("custom", "", "", "", False),
)

MARKS = {
    "openrouter": ("R", "#1de9b6"),
    "openai": ("OA", "#ececec"),
    "anthropic": ("A", "#d97757"),
    "groq": ("G", "#f55036"),
    "gemini": ("Ge", "#4b8bff"),
    "cohere": ("C", "#ff7759"),
    "ollama": ("O", "#d7dde2"),
    "custom": ("+", "#8fb8b0"),
}

ABOUT = {
    "openrouter": "desc_openrouter",
    "openai": "desc_openai",
    "anthropic": "desc_anthropic",
    "groq": "desc_groq",
    "gemini": "desc_gemini",
    "cohere": "desc_cohere",
    "ollama": "desc_ollama",
    "custom": "desc_custom",
}


def mark(kind: str) -> QLabel:
    letter, color = MARKS.get(kind, ("?", "#8fb8b0"))
    ink = "#04241c" if kind in {"openrouter", "custom"} else "#102028"
    badge = QLabel(letter)
    badge.setAlignment(Qt.AlignCenter)
    badge.setFixedSize(22, 22)
    badge.setStyleSheet(
        f"background:{color}; color:{ink}; border-radius:11px; font-size:10px; font-weight:600;"
    )
    return badge


def catalog_name(kind: str) -> str:
    if kind == "custom":
        return tr("name_custom")
    for key, name, *_rest in CATALOG:
        if key == kind:
            return name
    return kind


class AiPage(QWidget):
    def __init__(self, library: Library):
        super().__init__()
        self.library = library
        self.title = QLabel()
        self.title.setObjectName("welcome")
        self.subtitle = QLabel()
        self.subtitle.setObjectName("muted")
        self.subtitle.setWordWrap(True)
        self.connected_title = QLabel()
        self.connected_title.setObjectName("logo")
        self.available_title = QLabel()
        self.available_title.setObjectName("logo")
        self.connected_box = QVBoxLayout()
        self.available_box = QVBoxLayout()
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 28)
        root.setSpacing(12)
        root.addWidget(self.title)
        root.addWidget(self.subtitle)
        root.addWidget(self.connected_title)
        root.addLayout(self.connected_box)
        root.addSpacing(8)
        root.addWidget(self.available_title)
        root.addLayout(self.available_box)
        root.addStretch(1)
        self.retranslate()

    def retranslate(self) -> None:
        self.title.setText(tr("models_title"))
        self.subtitle.setText(tr("models_sub"))
        self.connected_title.setText(tr("connected"))
        self.available_title.setText(tr("available"))
        self.reload()

    def reload(self) -> None:
        self._clear(self.connected_box)
        self._clear(self.available_box)
        rows = self.library.connections()
        connected_kinds = {row["kind"] for row in rows}
        if not rows:
            empty = QLabel(tr("none_connected"))
            empty.setObjectName("muted")
            self.connected_box.addWidget(empty)
        else:
            for row in rows:
                self.connected_box.addWidget(self._connected(row))
        for kind, _name, _url, _model, recommended in CATALOG:
            if kind in connected_kinds:
                continue
            self.available_box.addWidget(self._available(kind, recommended))

    def _head(self) -> QWidget:
        row = QHBoxLayout()
        for key, stretch in (("col_service", 2), ("col_about", 4), ("col_status", 1), ("col_action", 1)):
            label = QLabel(tr(key))
            label.setObjectName("muted")
            row.addWidget(label, stretch)
        holder = QWidget()
        holder.setLayout(row)
        return holder

    def _connected(self, row) -> QWidget:
        line = QHBoxLayout()
        name = QLabel(row["label"] or catalog_name(row["kind"]))
        name.setObjectName("logo")
        about = QLabel(tr(ABOUT.get(row["kind"], "desc_custom")))
        about.setObjectName("muted")
        badge = QLabel(tr("in_use") if row["active"] else tr("badge_on"))
        badge.setObjectName("badge")
        remove = QPushButton()
        remove.setObjectName("icon")
        remove.setIcon(icon("close"))
        remove.setToolTip(tr("disconnect_title"))
        remove.clicked.connect(lambda _checked=False, connection_id=row["id"]: self._disconnect(connection_id))
        use = QPushButton(tr("switch"))
        use.setObjectName("outline")
        if row["active"]:
            use.hide()
        use.clicked.connect(lambda _checked=False, connection_id=row["id"]: self._activate(connection_id))
        line.addWidget(mark(row["kind"]))
        line.addWidget(name)
        line.addWidget(badge)
        line.addWidget(about, 1)
        line.addWidget(use)
        line.addWidget(remove)
        holder = QFrame()
        holder.setObjectName("issue")
        holder.setLayout(line)
        return holder

    def _available(self, kind: str, recommended: bool) -> QWidget:
        line = QHBoxLayout()
        name = QLabel(f"{catalog_name(kind)}   ·   {tr(ABOUT[kind])}")
        badge = QLabel(tr("recommended"))
        badge.setObjectName("badge")
        if not recommended:
            badge.hide()
        button = QPushButton(tr("connect"))
        button.setObjectName("outline")
        button.setIcon(icon("plus", "#1de9b6"))
        button.clicked.connect(lambda _checked=False, name=kind: self._connect(name))
        line.addWidget(mark(kind))
        line.addWidget(name, 1)
        line.addWidget(badge)
        line.addWidget(button)
        holder = QFrame()
        holder.setObjectName("issue")
        holder.setLayout(line)
        return holder

    def _connect(self, kind: str) -> None:
        preset = next(item for item in CATALOG if item[0] == kind)
        dialog = FormDialog(f"{tr('connect_title')} {catalog_name(kind)}", tr("connect_hint"), self)
        base = QLineEdit(preset[2])
        model = QLineEdit(preset[3])
        key = QLineEdit()
        key.setEchoMode(QLineEdit.Password)
        key.setPlaceholderText(tr("key_optional") if kind == "ollama" else "sk-…")
        reveal = key.addAction(icon("eye"), QLineEdit.ActionPosition.TrailingPosition)

        def flip() -> None:
            hidden = key.echoMode() == QLineEdit.EchoMode.Password
            key.setEchoMode(QLineEdit.EchoMode.Normal if hidden else QLineEdit.EchoMode.Password)

        reveal.triggered.connect(flip)
        dialog.label(tr("field_url"))
        dialog.add(base)
        dialog.label(tr("model_name"))
        dialog.add(model)
        dialog.label(tr("api_key"))
        dialog.add(key)
        dialog.cancel(tr("cancel"))

        def save() -> None:
            if not base.text().strip() or not model.text().strip():
                return
            if kind != "ollama" and not key.text().strip():
                return
            self.library.connect_provider(kind, catalog_name(kind), base.text(), model.text(), key.text())
            dialog.accept()
            self.reload()

        dialog.primary(tr("save"), save)
        dialog.exec()

    def _disconnect(self, connection_id: str) -> None:
        if not confirm(self, tr("disconnect_title"), tr("disconnect_body")):
            return
        self.library.disconnect_provider(connection_id)
        self.reload()

    def _activate(self, connection_id: str) -> None:
        self.library.activate_provider(connection_id)
        self.reload()

    def _clear(self, layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
