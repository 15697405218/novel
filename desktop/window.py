"""Login, the shelf, and the writing desk."""

import os
import sys
import ctypes
import re
from pathlib import Path

from PySide6.QtCore import QPoint, QSettings, Qt, QSize, QTimer
from PySide6.QtGui import QCursor, QFont, QTextBlockFormat, QTextCharFormat, QTextCursor, QTextListFormat
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from desktop import auth_client
from desktop.dialogs import FormDialog, alert, ask, confirm, prompt
from desktop.i18n import set_locale, tr
from desktop.icons import app_icon, icon
from desktop.providers_ui import AiPage
from desktop.engine import plain_complete, read_prompt
from desktop.extract import parse_extract
from desktop.export import markdown, web_novel
from desktop.jobs import ChatWorker, Job
from desktop.store import Library
from desktop.theme import enable_glass
from desktop.wordcount import count_words, count_words_in_html, html_to_plain, plain_to_html

CHAPTER_SPLIT = re.compile(r"(?m)^(第[0-9一二三四五六七八九十百千零两]+章[^\n]*|#{1,3} .+)$")
NAV = (
    ("write", "nav_write"),
    ("map", "nav_map"),
    ("outline", "nav_outline"),
    ("style", "nav_style"),
)
CODEX = (
    ("character", "codex_character"),
    ("location", "codex_location"),
    ("lore", "codex_lore"),
    ("plot", "codex_plot"),
    ("note", "codex_note"),
)
GENRES = ("玄幻", "仙侠", "都市", "言情", "悬疑", "科幻", "历史", "武侠", "现实")
KINDS = (
    ("novel", "长篇"),
    ("trilogy", "三部曲"),
    ("series", "系列"),
    ("short_story_collection", "短篇集"),
    ("screenplay", "剧本"),
)
SUGGESTIONS = (
    "帮我把这个角色写得更立体",
    "给这一场加几个转折",
    "这里的节奏可以再紧一些",
    "让这段对话更像真人在说话",
)
ACTIONS = (
    ("expand", "扩写"),
    ("shorten", "缩写"),
    ("rewrite", "改写"),
    ("dialogue", "对白"),
    ("tone", "语气"),
)


def library_path(user_id: str) -> Path:
    root = Path(os.environ.get("APPDATA") or Path.home())
    return root / "Novel" / "users" / user_id / "library.sqlite"


def _button(text: str, slot, primary: bool = False, kind: str = "") -> QPushButton:
    button = QPushButton(text)
    if kind:
        button.setObjectName(kind)
    elif primary:
        button.setObjectName("primary")
    button.setCursor(Qt.PointingHandCursor)
    button.clicked.connect(slot)
    return button


def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


class ChapterRow(QFrame):
    def __init__(self, title: str, words: int, selected: bool, choose):
        super().__init__()
        self._choose = choose
        self.setObjectName("chapter-on" if selected else "chapter")
        self.setCursor(Qt.PointingHandCursor)
        label = QLabel(title)
        self._count = QLabel(str(words))
        self._count.setObjectName("muted")
        line = QHBoxLayout(self)
        line.setContentsMargins(8, 6, 8, 6)
        line.addWidget(label, 1)
        line.addWidget(self._count)

    def set_words(self, words: int) -> None:
        self._count.setText(str(words))

    def mousePressEvent(self, event) -> None:
        self._choose()
        super().mousePressEvent(event)


class ClickCard(QFrame):
    def __init__(self, on_open):
        super().__init__()
        self._on_open = on_open

    def mousePressEvent(self, event) -> None:
        self._on_open()
        super().mousePressEvent(event)


def _scroll(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.setWidget(widget)
    return area


class LoginPage(QWidget):
    def __init__(self, enter):
        super().__init__()
        self._enter = enter
        self._mode = "login"
        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(360)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 28, 28, 22)
        layout.setSpacing(10)
        badge = QFrame()
        badge.setObjectName("login-mark")
        glyph = QLabel()
        glyph.setPixmap(icon("pencil", "#04241c").pixmap(20, 20))
        badge_row = QHBoxLayout(badge)
        badge_row.setContentsMargins(0, 0, 0, 0)
        badge_row.addWidget(glyph, alignment=Qt.AlignCenter)
        self.card_title = QLabel("Novel")
        self.card_title.setObjectName("brand")
        self.card_title.setAlignment(Qt.AlignCenter)
        self.card_hint = QLabel()
        self.card_hint.setObjectName("muted")
        self.card_hint.setAlignment(Qt.AlignCenter)
        self.name = QLineEdit()
        self.email = QLineEdit()
        self.email.addAction(icon("mail", "#8fb8b0"), QLineEdit.ActionPosition.LeadingPosition)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.addAction(icon("lock", "#8fb8b0"), QLineEdit.ActionPosition.LeadingPosition)
        reveal = self.password.addAction(icon("eye", "#8fb8b0"), QLineEdit.ActionPosition.TrailingPosition)
        reveal.triggered.connect(self._reveal)
        self.error = QLabel("")
        self.error.setObjectName("hint")
        self.error.setWordWrap(True)
        self.error.setAlignment(Qt.AlignCenter)
        self.forgot = _button("", self._forgot, kind="link")
        self.forgot.setFlat(True)
        forgot_row = QHBoxLayout()
        forgot_row.addStretch(1)
        forgot_row.addWidget(self.forgot)
        self.submit = _button("", self._submit, True)
        self.submit.setMinimumHeight(40)
        self.switch = _button("", self._switch, kind="link")
        self.switch.setFlat(True)
        self.server = QLineEdit("http://127.0.0.1:8787")
        self.server.setObjectName("server")
        self.server.setAlignment(Qt.AlignCenter)
        layout.addWidget(badge, alignment=Qt.AlignCenter)
        layout.addWidget(self.card_title)
        layout.addWidget(self.card_hint)
        layout.addSpacing(8)
        layout.addWidget(self.name)
        layout.addWidget(self.email)
        layout.addWidget(self.password)
        layout.addLayout(forgot_row)
        layout.addWidget(self.error)
        layout.addWidget(self.submit)
        layout.addWidget(self.switch, alignment=Qt.AlignCenter)
        layout.addWidget(self.server)
        self.name.hide()
        self.retranslate()
        outer = QVBoxLayout(self)
        outer.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(card)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)

    def _reveal(self) -> None:
        hidden = self.password.echoMode() == QLineEdit.EchoMode.Password
        self.password.setEchoMode(QLineEdit.EchoMode.Normal if hidden else QLineEdit.EchoMode.Password)

    def _forgot(self) -> None:
        alert(self, tr("forgot"), tr("forgot_body"))

    def retranslate(self) -> None:
        registering = self._mode == "register"
        self.name.setVisible(registering)
        self.forgot.setVisible(not registering)
        self.card_title.setText(tr("register_card") if registering else "Novel")
        self.card_hint.setText(tr("register_card_hint") if registering else tr("tagline"))
        self.email.setPlaceholderText(tr("email"))
        self.name.setPlaceholderText(tr("name"))
        self.password.setPlaceholderText(tr("password"))
        self.submit.setText(tr("register_submit") if registering else tr("login_submit"))
        self.switch.setText(tr("to_login") if registering else tr("to_register"))
        self.forgot.setText(tr("forgot"))
        self.server.setPlaceholderText(tr("server_line"))

    def _switch(self) -> None:
        self._mode = "register" if self._mode == "login" else "login"
        self.retranslate()

    def _submit(self) -> None:
        self.error.setText("")
        try:
            if self._mode == "register":
                payload = auth_client.register(
                    self.server.text().strip(),
                    self.email.text().strip(),
                    self.name.text().strip(),
                    self.password.text(),
                )
            else:
                payload = auth_client.login(
                    self.server.text().strip(),
                    self.email.text().strip(),
                    self.password.text(),
                )
        except auth_client.AuthError as exc:
            self.error.setText(exc.message)
            return
        except Exception:
            self.error.setText("连不上账号服务。先在另一个窗口运行 python -m auth")
            return
        user = payload.get("user") or {}
        self._enter(self.server.text().strip(), payload.get("token", ""), user)


class ProjectPage(QWidget):
    def __init__(self, open_project, logout, library: Library, user_name: str = "", on_locale=None):
        super().__init__()
        self._open = open_project
        self._logout = logout
        self.library = library
        self._on_locale = on_locale
        self._picked: str | None = None
        self._query = ""
        self.prefs = QSettings("Novel", "Novel")
        self._user_name = user_name
        side = QVBoxLayout()
        side.setContentsMargins(14, 18, 10, 14)
        side.setSpacing(2)
        brand = QHBoxLayout()
        mark = QLabel()
        mark.setPixmap(app_icon().pixmap(22, 22))
        self.brand = QLabel("Novel")
        self.brand.setObjectName("logo")
        brand.addWidget(mark)
        brand.addWidget(self.brand)
        brand.addStretch(1)
        side.addLayout(brand)
        side.addSpacing(12)
        self.group_labels: list[QLabel] = []
        self.side_nav: dict[str, QPushButton] = {}
        sections = (
            ("writing", (("shelf", "book", self.reload), ("trash", "trash", self._trash))),
            (
                "org",
                (
                    ("org", "users", self._org),
                    ("settings", "settings", self._settings),
                ),
            ),
            ("tools", (("models", "cpu", self._ai),)),
        )
        for group, items in sections:
            label = QLabel()
            label.setObjectName("group")
            self.group_labels.append(label)
            side.addWidget(label)
            for key, mark_name, slot in items:
                button = QPushButton()
                button.setObjectName("nav")
                button.setCheckable(True)
                button.setIcon(icon(mark_name))
                button.setIconSize(QSize(16, 16))
                button.setCursor(Qt.PointingHandCursor)
                button.clicked.connect(slot)
                self.side_nav[key] = button
                side.addWidget(button)
            side.addSpacing(8)
        self.projects_nav = self.side_nav["shelf"]
        side.addStretch(1)
        foot = QHBoxLayout()
        initial = (user_name or tr("author"))[:1]
        avatar = QLabel(initial)
        avatar.setObjectName("avatar")
        avatar.setAlignment(Qt.AlignCenter)
        self.who = QLabel(user_name or tr("author"))
        self.who.setObjectName("muted")
        foot.addWidget(avatar)
        foot.addWidget(self.who, 1)
        side.addLayout(foot)
        rail = QFrame()
        rail.setObjectName("sidebar")
        rail.setFixedWidth(212)
        rail.setLayout(side)

        self.view_label = QLabel()
        self.view_label.setObjectName("logo")
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setFixedWidth(220)
        self.search.addAction(icon("search", "#8fb8b0"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self._filter)
        self.bell = QPushButton()
        self.bell.setObjectName("icon")
        self.bell.setIcon(icon("bell"))
        self.bell.setIconSize(QSize(16, 16))
        top = QHBoxLayout()
        top.setContentsMargins(22, 8, 16, 8)
        top.addWidget(self.view_label)
        top.addStretch(1)
        top.addWidget(self.search)
        top.addWidget(self.bell)
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(56)
        header.setLayout(top)

        self.heading = QLabel()
        self.heading.setObjectName("display")
        self.hint = QLabel()
        self.hint.setObjectName("muted")
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(self.heading)
        titles.addWidget(self.hint)
        self.create_button = _button("", self._create, kind="outline")
        self.create_button.setIcon(icon("plus", "#1de9b6"))
        self.create_button.setIconSize(QSize(16, 16))
        head_row = QHBoxLayout()
        head_row.addLayout(titles, 1)
        head_row.addWidget(self.create_button)
        self.grid = QGridLayout()
        self.grid.setSpacing(16)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        holder = QWidget()
        holder.setLayout(self.grid)
        shelf = QVBoxLayout()
        shelf.setContentsMargins(28, 18, 28, 28)
        shelf.addLayout(head_row)
        shelf.addSpacing(14)
        shelf.addWidget(_scroll(holder), 1)
        shelf_page = QWidget()
        shelf_page.setLayout(shelf)
        self.catalog_title = QLabel()
        self.catalog_title.setObjectName("display")
        self.catalog_hint = QLabel()
        self.catalog_hint.setObjectName("muted")
        self.catalog_hint.setWordWrap(True)
        self.catalog_list = QVBoxLayout()
        catalog = QVBoxLayout()
        catalog.setContentsMargins(28, 22, 28, 28)
        catalog.setSpacing(10)
        catalog.addWidget(self.catalog_title)
        catalog.addWidget(self.catalog_hint)
        catalog.addLayout(self.catalog_list)
        catalog.addStretch(1)
        self.note = QWidget()
        self.note.setLayout(catalog)
        self.settings_page = self._build_settings()
        self.ai_page = AiPage(library)
        self.stack = QStackedWidget()
        self.stack.addWidget(shelf_page)
        self.stack.addWidget(self.note)
        self.stack.addWidget(self.settings_page)
        self.stack.addWidget(self.ai_page)

        main = QVBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        main.addWidget(header)
        main.addWidget(self.stack, 1)
        body = QWidget()
        body.setLayout(main)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(rail)
        root.addWidget(body, 1)
        self.setMinimumSize(0, 0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        root.setSizeConstraint(QHBoxLayout.SizeConstraint.SetNoConstraint)
        self.retranslate()

    def reload(self) -> None:
        self._select("shelf")
        self.stack.setCurrentIndex(0)
        self.heading.setText(tr("shelf"))
        self.view_label.setText(tr("shelf"))
        _clear(self.grid)
        needle = self._query.strip()
        projects = []
        for row in self.library.projects():
            blob = f"{row['title']} {row['genre'] or ''} {row['description'] or ''}"
            if needle and needle not in blob:
                names = [
                    entry["name"]
                    for kind, _label in CODEX
                    for entry in self.library.entries(row["id"], kind)
                ]
                if needle not in " ".join(names):
                    continue
            projects.append(row)
        self.hint.setText(tr("shelf_count").format(n=len(projects)))
        if not projects and needle:
            empty = QLabel(tr("no_match"))
            empty.setObjectName("muted")
            self.grid.addWidget(empty, 0, 0)
            return
        cells = list(projects)
        extra = 3 if len(projects) % 3 == 0 else 3 - (len(projects) % 3)
        for _slot in range(extra):
            cells.append(None)
        for index, row in enumerate(cells):
            widget = self._empty_card() if row is None else self._card(row)
            self.grid.addWidget(widget, index // 3, index % 3, Qt.AlignTop | Qt.AlignLeft)
        self.grid.setRowStretch((len(cells) - 1) // 3 + 1, 1)

    def _filter(self, text: str) -> None:
        self._query = text
        self.reload()

    def retranslate(self) -> None:
        for label, key in zip(self.group_labels, ("writing", "org", "ai_tools"), strict=True):
            label.setText(tr(key))
        names = {
            "shelf": tr("shelf"),
            "trash": tr("trash"),
            "org": tr("org"),
            "settings": tr("settings"),
            "models": tr("models"),
        }
        for key, button in self.side_nav.items():
            button.setText(names[key])
        self.search.setPlaceholderText(tr("search"))
        self.bell.setToolTip(tr("bell"))
        self.create_button.setText(tr("new_work"))
        self.settings_title.setText(tr("settings_title"))
        self.settings_hint.setText(tr("settings_sub"))
        self.language_label.setText(tr("ui_language"))
        self.open_label.setText(tr("open_on_start"))
        self.font_label.setText(tr("body_font"))
        self.size_label.setText(tr("font_size"))
        self.focus_check.setText("")
        self.focus_caption.setText(tr("focus_mode"))
        self.polish_caption.setText(tr("polish_compare"))
        self.confirm_caption.setText(tr("confirm_write"))
        self.section_general.setText(tr("general"))
        self.section_editor.setText(tr("editor"))
        self.section_ai.setText(tr("assistant"))
        self.section_about.setText(tr("about"))
        self.version_label.setText(tr("version"))
        self.update_label.setText(tr("check_update"))
        self.update_button.setText(tr("check"))
        self.logout_button.setText(tr("logout"))
        self.who.setText(self._user_name or tr("author"))
        self.ai_page.retranslate()
        if self.stack.currentIndex() == 0:
            self.reload()

    def _select(self, key: str) -> None:
        for name, button in self.side_nav.items():
            button.setChecked(name == key)

    def _choose_locale(self, code: str) -> None:
        self.prefs.setValue("locale", code)
        if self._on_locale is not None:
            self._on_locale(code)

    def _trash(self) -> None:
        self._select("trash")
        self.heading.setText(tr("trash"))
        self.view_label.setText(tr("trash"))
        self._fill_catalog(tr("trash"), tr("trash_empty"), [])

    def _org(self) -> None:
        self._select("org")
        self.heading.setText(tr("org"))
        self.view_label.setText(tr("org"))
        self._fill_catalog(tr("org"), tr("team_body"), [])

    def _fill_catalog(self, title: str, hint: str, rows: list[str]) -> None:
        self.catalog_title.setText(title)
        self.catalog_hint.setText(hint)
        self.catalog_hint.setVisible(bool(hint))
        _clear(self.catalog_list)
        for text in rows:
            line = QLabel(text)
            line.setObjectName("logo")
            self.catalog_list.addWidget(line)
        self.stack.setCurrentWidget(self.note)

    def _settings(self) -> None:
        self._select("settings")
        self.heading.setText(tr("settings_title"))
        self.view_label.setText(tr("settings"))
        self.stack.setCurrentWidget(self.settings_page)

    def _ai(self) -> None:
        self._select("models")
        self.heading.setText(tr("models_title"))
        self.view_label.setText(tr("models"))
        self.ai_page.retranslate()
        self.stack.setCurrentWidget(self.ai_page)

    def _build_settings(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(28, 22, 28, 28)
        root.setSpacing(14)
        self.settings_title = QLabel()
        self.settings_title.setObjectName("display")
        self.settings_hint = QLabel()
        self.settings_hint.setObjectName("muted")
        root.addWidget(self.settings_title)
        root.addWidget(self.settings_hint)

        def section(title_attr: str) -> QVBoxLayout:
            frame = QFrame()
            frame.setObjectName("section")
            box = QVBoxLayout(frame)
            box.setContentsMargins(16, 14, 16, 14)
            box.setSpacing(10)
            title = QLabel()
            title.setObjectName("logo")
            setattr(self, title_attr, title)
            box.addWidget(title)
            root.addWidget(frame)
            return box

        def row(caption_attr: str, control: QWidget) -> QHBoxLayout:
            line = QHBoxLayout()
            caption = QLabel()
            caption.setObjectName("field")
            setattr(self, caption_attr, caption)
            line.addWidget(caption, 1)
            line.addWidget(control)
            return line

        general = section("section_general")
        self.language_box = QComboBox()
        self.language_box.addItem("简体中文", "zh")
        self.language_box.addItem("English", "en")
        self.language_box.setMinimumWidth(160)
        current = "en" if str(self.prefs.value("locale", "zh")) == "en" else "zh"
        self.language_box.setCurrentIndex(1 if current == "en" else 0)
        self.language_box.currentIndexChanged.connect(
            lambda _index: self._choose_locale(str(self.language_box.currentData()))
        )
        general.addLayout(row("language_label", self.language_box))
        self.open_box = QComboBox()
        self.open_box.addItem(tr("open_last"), "last")
        self.open_box.addItem(tr("open_shelf"), "shelf")
        self.open_box.setCurrentIndex(0 if str(self.prefs.value("open_on_start", "last")) != "shelf" else 1)
        self.open_box.currentIndexChanged.connect(
            lambda _index: self.prefs.setValue("open_on_start", self.open_box.currentData())
        )
        general.addLayout(row("open_label", self.open_box))

        editor = section("section_editor")
        self.font_box = QComboBox()
        for name in ("思源宋体", "黑体", "楷体"):
            self.font_box.addItem(name)
        self.font_box.setCurrentText(str(self.prefs.value("editor_font", "思源宋体")))
        self.font_box.currentTextChanged.connect(lambda text: self.prefs.setValue("editor_font", text))
        editor.addLayout(row("font_label", self.font_box))
        self.size_box = QComboBox()
        for size in ("14 px", "16 px", "18 px", "20 px"):
            self.size_box.addItem(size)
        self.size_box.setCurrentText(str(self.prefs.value("editor_size", "16 px")))
        self.size_box.currentTextChanged.connect(lambda text: self.prefs.setValue("editor_size", text))
        editor.addLayout(row("size_label", self.size_box))
        self.focus_check = QCheckBox()
        self.focus_check.setObjectName("switch")
        self.focus_check.setChecked(str(self.prefs.value("focus_mode", "false")) == "true")
        self.focus_check.toggled.connect(lambda on: self.prefs.setValue("focus_mode", "true" if on else "false"))
        self.focus_caption = QLabel()
        focus_line = QHBoxLayout()
        focus_line.addWidget(self.focus_caption, 1)
        focus_line.addWidget(self.focus_check)
        editor.addLayout(focus_line)

        assistant = section("section_ai")
        self.polish_check = QCheckBox()
        self.polish_check.setObjectName("switch")
        self.polish_check.setChecked(str(self.prefs.value("polish_compare", "true")) != "false")
        self.polish_check.toggled.connect(lambda on: self.prefs.setValue("polish_compare", "true" if on else "false"))
        self.polish_caption = QLabel()
        polish_line = QHBoxLayout()
        polish_line.addWidget(self.polish_caption, 1)
        polish_line.addWidget(self.polish_check)
        assistant.addLayout(polish_line)
        self.confirm_check = QCheckBox()
        self.confirm_check.setObjectName("switch")
        self.confirm_check.setChecked(str(self.prefs.value("confirm_write", "true")) != "false")
        self.confirm_check.toggled.connect(lambda on: self.prefs.setValue("confirm_write", "true" if on else "false"))
        self.confirm_caption = QLabel()
        confirm_line = QHBoxLayout()
        confirm_line.addWidget(self.confirm_caption, 1)
        confirm_line.addWidget(self.confirm_check)
        assistant.addLayout(confirm_line)

        about = section("section_about")
        self.version_label = QLabel()
        self.version_label.setObjectName("field")
        version = QLabel("Novel 0.1.0")
        version_line = QHBoxLayout()
        version_line.addWidget(self.version_label, 1)
        version_line.addWidget(version)
        about.addLayout(version_line)
        self.update_label = QLabel()
        self.update_label.setObjectName("field")
        self.update_button = _button("", lambda: alert(self, tr("check_update"), tr("up_to_date")), kind="outline")
        update_line = QHBoxLayout()
        update_line.addWidget(self.update_label, 1)
        update_line.addWidget(self.update_button)
        about.addLayout(update_line)
        self.logout_button = _button("", self._logout, kind="outline")
        root.addWidget(self.logout_button, alignment=Qt.AlignLeft)
        root.addStretch(1)
        return page

    def _empty_card(self) -> QFrame:
        card = ClickCard(self._create)
        card.setObjectName("empty-card")
        card.setFixedSize(280, 250)
        card.setCursor(Qt.PointingHandCursor)
        plus = QLabel("+")
        plus.setObjectName("muted")
        plus.setAlignment(Qt.AlignCenter)
        label = QLabel(tr("new_work"))
        label.setObjectName("muted")
        label.setAlignment(Qt.AlignCenter)
        box = QVBoxLayout(card)
        box.addStretch(1)
        box.addWidget(plus)
        box.addWidget(label)
        box.addStretch(1)
        return card

    def _card(self, row) -> QFrame:
        card = ClickCard(lambda chosen=row["id"]: self._open(chosen))
        card.setObjectName("project-card")
        card.setFixedWidth(280)
        card.setCursor(Qt.PointingHandCursor)
        cover = QFrame()
        cover.setObjectName("cover")
        glyph = QLabel((row["title"] or "书")[:1])
        glyph.setObjectName("cover-char")
        glyph.setAlignment(Qt.AlignCenter)
        pencil = QPushButton()
        pencil.setObjectName("icon")
        pencil.setIcon(icon("pencil", "#e7fff8"))
        pencil.setIconSize(QSize(16, 16))
        pencil.setToolTip(tr("edit"))
        pencil.clicked.connect(lambda _checked=False, project_id=row["id"]: self._edit(project_id))
        cover_box = QGridLayout(cover)
        cover_box.addWidget(glyph, 0, 0, Qt.AlignCenter)
        cover_box.addWidget(pencil, 0, 0, Qt.AlignTop | Qt.AlignRight)
        title = QLabel(row["title"])
        title.setObjectName("card-title")
        words = self.library.project_word_count(row["id"])
        count = QLabel(self._words(words))
        count.setObjectName("muted")
        body = QVBoxLayout(card)
        body.setContentsMargins(12, 12, 12, 12)
        body.setSpacing(8)
        body.addWidget(cover)
        body.addWidget(title)
        blurb = QLabel(row["description"] or row["genre"] or "")
        blurb.setObjectName("muted")
        blurb.setWordWrap(True)
        blurb.setMaximumHeight(36)
        body.addWidget(blurb)
        body.addWidget(count, alignment=Qt.AlignRight)
        return card

    def _words(self, words: int) -> str:
        if words >= 10000:
            return f"{words / 10000:.1f} 万字"
        return f"{words} 字"

    def _selected(self) -> str | None:
        return self._picked

    def _project_form(self, dialog: FormDialog, current: dict[str, str] | None = None) -> dict[str, QWidget]:
        title = QLineEdit((current or {}).get("title", ""))
        title.setPlaceholderText(tr("book_name_hint"))
        description = QPlainTextEdit((current or {}).get("description", ""))
        description.setPlaceholderText(tr("blurb_hint"))
        description.setFixedHeight(72)
        kind = QComboBox()
        for _key, label in KINDS:
            kind.addItem(label)
        kind.setCurrentText((current or {}).get("kind", "长篇"))
        genre = QComboBox()
        for name in GENRES:
            genre.addItem(name)
        genre.setCurrentText((current or {}).get("genre") or "玄幻")
        target = QLineEdit((current or {}).get("target") or "100000")
        dialog.label(tr("book_name"))
        dialog.add(title)
        dialog.label(tr("blurb"))
        dialog.add(description)
        dialog.label(tr("genre"))
        dialog.add(genre)
        dialog.label(tr("target_words"))
        dialog.add(target)
        return {"title": title, "description": description, "kind": kind, "genre": genre, "target": target}

    def _read_form(self, fields: dict[str, QWidget]) -> tuple[str, str, str, str, int] | None:
        title_box = fields["title"]
        title = title_box.text().strip() if isinstance(title_box, QLineEdit) else ""
        if not title:
            return None
        kind_box = fields["kind"]
        kind_label = kind_box.currentText().strip() if isinstance(kind_box, QComboBox) else "长篇"
        kind = "novel"
        for key, label in KINDS:
            if kind_label in {key, label}:
                kind = key
        genre_box = fields["genre"]
        genre = genre_box.currentText().strip() if isinstance(genre_box, QComboBox) else ""
        target_box = fields["target"]
        raw_target = target_box.text().replace(",", "").strip() if isinstance(target_box, QLineEdit) else ""
        target = int(raw_target) if raw_target.isdigit() else 0
        return title, genre, fields["description"].toPlainText(), kind, target

    def _create(self) -> None:
        dialog = FormDialog(tr("new_work"), tr("new_work_hint"), self)
        fields = self._project_form(dialog)
        dialog.cancel(tr("cancel"))

        def save() -> None:
            values = self._read_form(fields)
            if values is None:
                return
            project_id = self.library.create_project(*values)
            dialog.accept()
            self._open(project_id)

        dialog.primary(tr("create"), save)
        dialog.exec()

    def _edit(self, project_id: str) -> None:
        row = self.library.project(project_id)
        if row is None:
            return
        dialog = FormDialog("编辑项目", "", self)
        fields = self._project_form(
            dialog,
            {
                "title": row["title"],
                "description": row["description"] or "",
                "kind": dict(KINDS).get(row["kind"] or "novel", "长篇"),
                "genre": row["genre"] or "",
                "target": str(row["target_words"] or ""),
            },
        )
        dialog.cancel()

        def save() -> None:
            values = self._read_form(fields)
            if values is None:
                return
            self.library.update_project(project_id, *values)
            dialog.accept()
            self.reload()

        dialog.primary("保存修改", save)
        remove = _button("删除", lambda: self._delete(project_id, dialog), kind="ghost")
        dialog.footer.insertWidget(0, remove)
        dialog.exec()

    def _rename(self, project_id: str | None = None) -> None:
        if project_id:
            self._edit(project_id)

    def _delete(self, project_id: str | None = None, dialog: QDialog | None = None) -> None:
        project_id = project_id or self._selected()
        if not project_id:
            return
        row = self.library.project(project_id)
        title = row["title"] if row else ""
        if not confirm(
            self,
            tr("delete_work"),
            tr("delete_body").format(title=title),
            yes=tr("delete_yes"),
            no=tr("cancel"),
            danger=True,
        ):
            return
        self.library.delete_project(project_id)
        if dialog is not None:
            dialog.reject()
        self.reload()

    def _import_book(self) -> None:
        path, _chosen = QFileDialog.getOpenFileName(self, "导入本地书籍", "", "文本 (*.txt *.md)")
        if not path:
            return
        raw = Path(path).read_text(encoding="utf-8")
        project_id = self.library.create_project(Path(path).stem, "")
        volumes = self.library.volumes(project_id)
        volume_id = volumes[0]["id"]
        parts = CHAPTER_SPLIT.split(raw)
        if len(parts) <= 1:
            chapter_id = self.library.create_chapter(project_id, volume_id, Path(path).stem)
            self.library.save_chapter_content(chapter_id, plain_to_html(raw.strip()))
        else:
            index = 1
            while index < len(parts):
                title = parts[index].strip().lstrip("# ").strip()
                body = parts[index + 1] if index + 1 < len(parts) else ""
                chapter_id = self.library.create_chapter(project_id, volume_id, title)
                self.library.save_chapter_content(chapter_id, plain_to_html(body.strip()))
                index += 2
        self._open(project_id)

    def _open_current(self) -> None:
        project_id = self._selected()
        if project_id:
            self._open(project_id)

    def _provider(self) -> None:
        row = self.library.provider()
        dialog = FormDialog("AI 模型", "密钥只保存在本机，请求直接发给供应商。", self)
        base = QLineEdit(row["base_url"])
        model = QLineEdit(row["model"])
        key = QLineEdit(row["api_key"])
        key.setEchoMode(QLineEdit.Password)
        dialog.label("接口地址")
        dialog.add(base)
        dialog.label("模型名")
        dialog.add(model)
        dialog.label("密钥")
        dialog.add(key)
        dialog.cancel()

        def save() -> None:
            self.library.save_provider(base.text(), model.text(), key.text())
            dialog.accept()

        dialog.primary("保存", save)
        dialog.exec()


class SelectionDialog(FormDialog):
    def __init__(self, parent, run):
        super().__init__(tr("polish_title"), "", parent)
        self.setMinimumWidth(680)
        self._run = run
        self.action = "rewrite"
        self.source = QPlainTextEdit()
        self.source.setReadOnly(True)
        self.source.setMinimumHeight(140)
        self.draft = QPlainTextEdit()
        self.draft.setMinimumHeight(140)
        self.note = QPlainTextEdit()
        self.note.setPlaceholderText(tr("beat_goal"))
        self.note.setFixedHeight(56)
        columns = QHBoxLayout()
        left = QVBoxLayout()
        right = QVBoxLayout()
        self.original_label = QLabel(tr("original"))
        self.original_label.setObjectName("field")
        self.polished_label = QLabel(tr("polished"))
        self.polished_label.setObjectName("field")
        left.addWidget(self.original_label)
        left.addWidget(self.source)
        right.addWidget(self.polished_label)
        right.addWidget(self.draft)
        columns.addLayout(left)
        columns.addLayout(right)
        holder = QWidget()
        holder.setLayout(columns)
        self.add(holder)
        self.add(self.note)
        self.footer.insertWidget(0, _button(tr("regenerate"), self._again, kind="outline"))
        self.cancel(tr("ignore"))
        self.primary(tr("accept_polish"), self.accept)

    def show_passage(self, passage: str) -> None:
        self.source.setPlainText(passage)
        self.set_description(tr("polish_meta").format(n=len(passage)))

    def _again(self) -> None:
        self._run(self.action, self.note.toPlainText(), True)


def _clip_summary(text: str, limit: int) -> str:
    clean = " ".join(text.strip().split())
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip("，。；、,; ")


class DeskPage(QWidget):
    def __init__(self, library: Library, project_id: str, back, user_name: str = ""):
        super().__init__()
        self.library = library
        self.project_id = project_id
        self.focus = "write"
        self.focus_id: str | None = None
        self._chapter_id: str | None = None
        self._chapter_counts: dict[str, ChapterRow] = {}
        self._jobs: list[Job | ChatWorker] = []
        self._passage = ""
        self._range = (0, 0)
        self._selection_dialog: SelectionDialog | None = None
        project = library.project(project_id)
        self._title = project["title"] if project else tr("untitled")

        self.nav_buttons: dict[str, QPushButton] = {}
        side_layout = QVBoxLayout()
        side_layout.setContentsMargins(10, 14, 10, 12)
        side_layout.setSpacing(2)
        brand = QHBoxLayout()
        mark = QLabel()
        mark.setPixmap(app_icon().pixmap(22, 22))
        self.brand = QLabel("Novel")
        self.brand.setObjectName("logo")
        brand.addWidget(mark)
        brand.addWidget(self.brand)
        brand.addStretch(1)
        side_layout.addLayout(brand)
        self.structure = QLabel()
        self.structure.setObjectName("group")
        side_layout.addWidget(self.structure)
        for key, label in NAV:
            button = QPushButton()
            button.setObjectName("nav")
            button.setCheckable(True)
            button.setIcon(icon({"write": "book", "map": "globe", "outline": "paragraph", "style": "pencil"}[key]))
            button.setIconSize(QSize(18, 18))
            button.setToolTip(tr(label))
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, name=key: self.show_section(name))
            self.nav_buttons[key] = button
            side_layout.addWidget(button)
        self.codex_label = QLabel()
        self.codex_label.setObjectName("group")
        side_layout.addWidget(self.codex_label)
        self.codex_layouts: dict[str, QVBoxLayout] = {}
        self.codex_counts: dict[str, QLabel] = {}
        self.codex_panels: dict[str, QWidget] = {}
        self.codex_toggles: dict[str, QPushButton] = {}
        for key, label in CODEX:
            header = QHBoxLayout()
            toggle = _button("", lambda _checked=False, name=key: self.show_section(name), kind="nav")
            toggle.setIcon(icon({"character": "users", "location": "globe", "lore": "book", "plot": "clock", "note": "pencil"}[key]))
            toggle.setIconSize(QSize(18, 18))
            toggle.setToolTip(tr(label))
            self.codex_toggles[key] = toggle
            toggle.setCheckable(True)
            count = QLabel("0")
            count.setObjectName("count")
            self.codex_counts[key] = count
            header.addWidget(toggle, 1)
            header.addWidget(count)
            side_layout.addLayout(header)
            panel = QWidget()
            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(12, 0, 0, 4)
            panel_layout.setSpacing(0)
            panel.hide()
            self.codex_layouts[key] = panel_layout
            self.codex_panels[key] = panel
            side_layout.addWidget(panel)
        side_layout.addStretch(1)
        back_row = QHBoxLayout()
        self.user_label = QLabel(user_name or tr("author"))
        self.user_label.setObjectName("muted")
        back_row.addWidget(self.user_label, 1)
        self.back_button = _button(tr("back_projects"), back, kind="ghost")
        back_row.addWidget(self.back_button)
        side_layout.addLayout(back_row)
        side = QFrame()
        side.setObjectName("sidebar")
        side.setLayout(side_layout)
        side.setFixedWidth(72)
        self.sidebar = side

        chapter_head = QHBoxLayout()
        self.chapter_title = QLabel()
        self.chapter_title.setObjectName("logo")
        chapter_head.addWidget(self.chapter_title)
        chapter_head.addStretch(1)
        self.volume_button = _button("", self._add_volume, kind="ghost")
        self.import_button = _button("", self._import, kind="ghost")
        chapter_head.addWidget(self.volume_button)
        chapter_head.addWidget(self.import_button)
        self.chapter_layout = QVBoxLayout()
        self.chapter_layout.setContentsMargins(8, 8, 8, 8)
        self.chapter_layout.setSpacing(2)
        chapter_holder = QWidget()
        chapter_holder.setLayout(self.chapter_layout)
        chapter_foot = QFrame()
        chapter_foot.setObjectName("chapter-foot")
        foot_layout = QHBoxLayout(chapter_foot)
        self.map_button = _button("", lambda: self.show_section("map"), kind="ghost")
        foot_layout.addWidget(self.map_button)
        chapter_col = QFrame()
        chapter_col.setObjectName("chapter-col")
        chapter_col.setFixedWidth(240)
        chapter_col.setContextMenuPolicy(Qt.CustomContextMenu)
        chapter_col.customContextMenuRequested.connect(self._tree_menu)
        chapter_box = QVBoxLayout(chapter_col)
        chapter_box.setContentsMargins(0, 0, 0, 0)
        chapter_box.setSpacing(0)
        head_wrap = QWidget()
        head_wrap.setLayout(chapter_head)
        chapter_head.setContentsMargins(12, 10, 8, 8)
        chapter_box.addWidget(head_wrap)
        chapter_box.addWidget(_scroll(chapter_holder), 1)
        chapter_box.addWidget(chapter_foot)
        self.chapter_col = chapter_col

        self.editor = QTextEdit()
        self.editor.setObjectName("editor")
        self.editor.setAcceptRichText(True)
        self.editor.setFrameShape(QFrame.NoFrame)
        chosen = str(QSettings("Novel", "Novel").value("editor_font", "思源宋体"))
        families = {
            "黑体": ["Microsoft YaHei", "SimHei", "sans-serif"],
            "楷体": ["KaiTi", "STKaiti", "serif"],
        }.get(chosen, ["Source Han Serif SC", "Noto Serif SC", "SimSun"])
        size_text = str(QSettings("Novel", "Novel").value("editor_size", "16 px"))
        point_size = int(size_text.split()[0]) if size_text[:2].isdigit() else 16
        body_font = QFont()
        body_font.setFamilies(families)
        body_font.setPointSize(point_size)
        self.editor.setFont(body_font)
        self.editor.document().setDocumentMargin(36)
        self.editor.selectionChanged.connect(self._on_selection)
        self.editor.textChanged.connect(self._dirty)
        self.doc_editor = QPlainTextEdit()
        self.doc_editor.setObjectName("doc")
        self.doc_editor.setFrameShape(QFrame.NoFrame)
        self.doc_editor.textChanged.connect(self._dirty)
        self.map_label = QLabel("故事地图还留着空位。")
        self.map_label.setAlignment(Qt.AlignCenter)
        self.map_label.setObjectName("muted")
        self.stage = QStackedWidget()
        self.stage.addWidget(self.editor)
        self.stage.addWidget(self.doc_editor)
        self.stage.addWidget(self.map_label)
        self.editor.setMinimumHeight(0)
        self.doc_editor.setMinimumHeight(0)
        self.stage.setMinimumHeight(0)

        self.goal = QPlainTextEdit()
        self.conflict = QPlainTextEdit()
        self.outcome = QPlainTextEdit()
        for box, name in ((self.goal, "beat_goal"), (self.conflict, "beat_conflict"), (self.outcome, "beat_outcome")):
            box.setPlaceholderText(tr(name))
            box.setFixedHeight(64)
            box.textChanged.connect(self._save_beats_later)
        beats = QWidget()
        beat_layout = QVBoxLayout(beats)
        beat_layout.setContentsMargins(16, 8, 16, 8)
        beat_layout.addWidget(self.goal)
        beat_layout.addWidget(self.conflict)
        beat_layout.addWidget(self.outcome)
        self.beats = beats
        self.beats.hide()

        self.summary = QPlainTextEdit()
        self.summary.setObjectName("summary")
        self.summary.setFixedHeight(96)
        self.summary.setPlaceholderText(tr("summary_placeholder"))
        self.summary.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._summary_saved = ""
        self._summary_dirty = False
        self.summary.textChanged.connect(self._summary_edited)
        tools = QHBoxLayout()
        tools.setContentsMargins(16, 8, 12, 8)
        self.tool_buttons: dict[str, QPushButton] = {}
        for key, slot in (
            ("beat", self._toggle_beats),
            ("check", self._check),
            ("versions", self._revisions),
            ("export", self._export),
            ("bind", self._bindings),
            ("summarize", self._summary),
            ("summary_save", self._save_summary),
        ):
            button = _button(tr(key), slot, kind="outline")
            self.tool_buttons[key] = button
            tools.addWidget(button)
        self.tool_row = QWidget()
        self.tool_row.setLayout(tools)

        format_row = QHBoxLayout()
        format_row.setContentsMargins(8, 4, 8, 4)
        format_row.setSpacing(2)
        groups = (
            ("undo", "撤销", "undo"),
            ("redo", "重做", "redo"),
            ("|", "", ""),
            ("paragraph", "正文", "paragraph"),
            ("|", "", ""),
            ("bold", "加粗", "bold"),
            ("italic", "斜体", "italic"),
            ("underline", "下划线", "underline"),
            ("strike", "删除线", "strike"),
            ("code", "行内代码", "code"),
            ("highlight", "高亮", "highlight"),
            ("|", "", ""),
            ("align-left", "左对齐", "align-left"),
            ("align-center", "居中", "align-center"),
            ("align-right", "右对齐", "align-right"),
            ("align-justify", "两端对齐", "align-justify"),
            ("|", "", ""),
            ("list", "无序列表", "list"),
            ("list-ordered", "有序列表", "numbered"),
            ("list-todo", "待办", "todo"),
            ("quote", "引用", "quote"),
            ("code-block", "代码块", "code-block"),
            ("|", "", ""),
            ("link", "链接", "link"),
        )
        for mark, tip, action in groups:
            if mark == "|":
                line = QFrame()
                line.setFixedSize(1, 16)
                line.setStyleSheet("background: #302c40;")
                format_row.addWidget(line)
                continue
            button = QPushButton()
            button.setObjectName("icon")
            button.setIcon(icon(mark))
            button.setIconSize(QSize(16, 16))
            button.setFixedSize(32, 32)
            button.setToolTip(tip)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, name=action: self._format(name))
            format_row.addWidget(button)
        format_row.addStretch(1)
        self.format_bar = QFrame()
        self.format_bar.setObjectName("toolbar")
        self.format_bar.setLayout(format_row)

        self.selection_bar = QHBoxLayout()
        self.selection_bar.setContentsMargins(12, 6, 12, 6)
        for key, label in ACTIONS:
            self.selection_bar.addWidget(
                _button(label, lambda _checked=False, name=key: self._selection(name), kind="outline")
            )
        self.selection_bar.addStretch(1)
        self.selection_wrap = QWidget()
        self.selection_wrap.setLayout(self.selection_bar)
        self.selection_wrap.hide()

        self.page_title = QLabel("")
        self.page_title.setObjectName("logo")
        self.page_title.setContentsMargins(20, 12, 20, 0)
        self.page_title.hide()
        self.word_label = QLabel()
        self.word_label.setObjectName("muted")
        self.save_label = QLabel()
        self.save_label.setObjectName("muted")
        self.clock = QLabel("")
        self.clock.setObjectName("muted")
        status = QHBoxLayout()
        status.setContentsMargins(16, 6, 16, 6)
        status.addWidget(self.word_label)
        status.addWidget(self.save_label)
        status.addStretch(1)
        status.addWidget(self.clock)
        self.continue_button = _button("", self._continue, kind="ghost")
        status.addWidget(self.continue_button)
        self.status_row = QFrame()
        self.status_row.setObjectName("status")
        self.status_row.setLayout(status)

        editor_col = QVBoxLayout()
        editor_col.setContentsMargins(0, 0, 0, 0)
        editor_col.setSpacing(0)
        editor_col.addWidget(self.page_title)
        editor_col.addWidget(self.tool_row)
        editor_col.addWidget(self.summary)
        editor_col.addWidget(self.beats)
        editor_col.addWidget(self.format_bar)
        editor_col.addWidget(self.selection_wrap)
        editor_col.addWidget(self.stage, 1)
        editor_col.addWidget(self.status_row)
        editor_wrap = QWidget()
        editor_wrap.setLayout(editor_col)

        self.heading = QLabel(self._title)
        self.heading.setObjectName("logo")
        self.header_words = QLabel()
        self.header_words.setObjectName("muted")
        self.header_saved = QLabel()
        self.header_saved.setObjectName("muted")
        header = QHBoxLayout()
        header.setContentsMargins(16, 0, 16, 0)
        header.setSpacing(12)
        header.addWidget(self.heading, 1)
        header.addWidget(self.header_words)
        header.addWidget(self.header_saved)
        header_bar = QFrame()
        header_bar.setObjectName("header")
        header_bar.setFixedHeight(56)
        header_bar.setLayout(header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self.chapter_col)
        body.addWidget(editor_wrap, 1)
        center = QVBoxLayout()
        center.setContentsMargins(0, 0, 0, 0)
        center.setSpacing(0)
        center.addWidget(header_bar)
        center.addLayout(body, 1)
        center_wrap = QWidget()
        center_wrap.setLayout(center)

        self.chat_layout = QVBoxLayout()
        self.chat_layout.setContentsMargins(12, 16, 12, 12)
        self.chat_layout.setSpacing(12)
        chat_holder = QWidget()
        chat_holder.setLayout(self.chat_layout)
        self.chat_input = QLineEdit()
        self.chat_input.setObjectName("chat-input")
        self.chat_input.returnPressed.connect(self._send)
        self.direct = QCheckBox(self)
        self.direct.hide()
        send = QPushButton("↑")
        send.setObjectName("send")
        send.setCursor(Qt.PointingHandCursor)
        send.clicked.connect(self._send)
        send_row = QHBoxLayout()
        send_row.addWidget(self.chat_input, 1)
        send_row.addWidget(send)
        self.chat_title = QLabel()
        self.chat_title.setObjectName("logo")
        hide_chat = QPushButton()
        hide_chat.setObjectName("icon")
        hide_chat.setIcon(icon("close"))
        hide_chat.clicked.connect(self._toggle_chat)
        chat_head = QHBoxLayout()
        chat_head.setContentsMargins(14, 10, 8, 0)
        chat_head.addWidget(self.chat_title, 1)
        chat_head.addWidget(hide_chat)
        chat_box = QVBoxLayout()
        chat_box.setContentsMargins(0, 0, 0, 10)
        chat_box.setSpacing(0)
        chat_box.addLayout(chat_head)
        chat_box.addWidget(_scroll(chat_holder), 1)
        direct_wrap = QWidget()
        direct_layout = QVBoxLayout(direct_wrap)
        direct_layout.setContentsMargins(12, 8, 12, 0)
        self.direct.hide()
        direct_layout.addLayout(send_row)
        chat_box.addWidget(direct_wrap)
        chat = QFrame()
        chat.setObjectName("chat")
        chat.setFixedWidth(320)
        chat.setLayout(chat_box)
        self.chat = chat

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(side)
        root.addWidget(center_wrap, 1)
        root.addWidget(chat)
        self.setMinimumSize(0, 0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        root.setSizeConstraint(QHBoxLayout.SizeConstraint.SetNoConstraint)

        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.flush)
        self.beat_timer = QTimer(self)
        self.beat_timer.setSingleShot(True)
        self.beat_timer.timeout.connect(self._save_beats)
        self._loading = False
        self.retranslate()
        self.show_section("write")
        self._load_chat()
        if str(QSettings("Novel", "Novel").value("focus_mode", "false")) == "true":
            self.chapter_col.hide()
            self.chat.hide()

    def retranslate(self) -> None:
        self.structure.setText(tr("group_structure"))
        self.codex_label.setText(tr("group_codex"))
        for key, label in NAV:
            self.nav_buttons[key].setText("")
            self.nav_buttons[key].setToolTip(tr(label))
        for key, label in CODEX:
            self.codex_toggles[key].setText("")
            self.codex_toggles[key].setToolTip(tr(label))
        self.structure.hide()
        self.codex_label.hide()
        self.user_label.hide()
        self.brand.hide()
        for count in self.codex_counts.values():
            count.hide()
        self.back_button.setText("")
        self.back_button.setIcon(icon("book"))
        self.back_button.setToolTip(tr("back_projects"))
        self.chapter_title.setText(tr("chapters"))
        self.volume_button.setText(tr("new_volume"))
        self.import_button.setText(tr("import_text"))
        self.map_button.setText(tr("open_map"))
        self.map_label.setText(tr("map_empty"))
        self.goal.setPlaceholderText(tr("beat_goal"))
        self.conflict.setPlaceholderText(tr("beat_conflict"))
        self.outcome.setPlaceholderText(tr("beat_outcome"))
        for key, button in self.tool_buttons.items():
            button.setText(tr(key))
        self.direct.setText(tr("direct"))
        self.continue_button.setText(tr("continue"))
        self._status()
        self.chat_input.setPlaceholderText(tr("chat_placeholder"))
        self.chat_title.setText(tr("assistant"))
        if self.focus == "outline":
            self.page_title.setText(tr("nav_outline"))
        elif self.focus == "style":
            self.page_title.setText(tr("nav_style"))
        self.summary.setPlaceholderText(tr("summary_placeholder"))

    def _show_summary(self, text: str) -> None:
        clean = text.strip()
        self._summary_saved = clean
        self._summary_dirty = False
        self.summary.blockSignals(True)
        self.summary.setPlainText(clean)
        self.summary.blockSignals(False)

    def _summary_edited(self) -> None:
        if self._loading:
            return
        self._summary_dirty = self.summary.toPlainText().strip() != self._summary_saved
        if self._summary_dirty:
            self.header_saved.setText(tr("unsaved"))
        self._counts()

    def _save_summary(self) -> None:
        if not self.focus_id or self.focus != "write":
            return
        clean = self.summary.toPlainText().strip()
        self.library.save_summary(self.focus_id, clean)
        self._summary_saved = clean
        self._summary_dirty = False
        self.header_saved.setText(tr("summary_saved"))

    def _ask_summary(self) -> None:
        if not (self._summary_dirty and self.focus_id and self.focus == "write"):
            return
        if ask(self, tr("summary_title"), tr("summary_unsaved"), tr("summary_save"), tr("summary_discard")):
            self._save_summary()
            return
        self._summary_dirty = False

    def provider(self) -> tuple[str, str, str] | None:
        row = self.library.provider()
        url = row["base_url"].strip()
        model = row["model"].strip()
        key = row["api_key"].strip()
        local = "11434" in url or "127.0.0.1" in url or "localhost" in url
        if not url or not model or (not key and not local):
            alert(self, tr("ai_nav"), tr("provider_missing"))
            return None
        return url, key, model

    def show_section(self, name: str) -> None:
        if name != self.focus:
            self._ask_summary()
        self.flush()
        self.focus = name
        if name in {"map", "outline", "style"}:
            self.focus_id = None
        for key, button in self.nav_buttons.items():
            button.setChecked(key == name)
        for key, button in self.codex_toggles.items():
            button.setChecked(key == name)
        writing = name == "write"
        self.summary.setVisible(writing)
        self.chapter_col.setVisible(writing)
        self.tool_row.setVisible(writing)
        self.format_bar.setVisible(writing)
        self.status_row.setVisible(writing)
        self.direct.hide()
        self.beats.hide()
        self.selection_wrap.hide()
        self.page_title.setVisible(name in {"outline", "style"})
        if name == "map":
            self.stage.setCurrentWidget(self.map_label)
            return
        if writing:
            self.stage.setCurrentWidget(self.editor)
            self._load_tree()
            return
        if name in {"outline", "style"}:
            self.page_title.setText(tr("nav_outline") if name == "outline" else tr("nav_style"))
            self.stage.setCurrentWidget(self.doc_editor)
            self._loading = True
            self.doc_editor.setPlainText(self.library.document(self.project_id, name))
            self._loading = False
            return
        self.page_title.show()
        self.stage.setCurrentWidget(self.doc_editor)
        self._load_entries(name)

    def _toggle_sidebar(self) -> None:
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def _toggle_chat(self) -> None:
        self.chat.setVisible(not self.chat.isVisible())

    def _toggle_codex(self, kind: str) -> None:
        panel = self.codex_panels[kind]
        panel.setVisible(not panel.isVisible())
        if panel.isVisible():
            self._fill_codex(kind)

    def _fill_codex(self, kind: str) -> None:
        layout = self.codex_layouts[kind]
        _clear(layout)
        rows = self.library.entries(self.project_id, kind)
        self.codex_counts[kind].setText(str(len(rows)))
        layout.addWidget(_button("＋ 新建", lambda _checked=False, name=kind: self._new_entry(name), kind="ghost"))
        for row in rows:
            layout.addWidget(
                _button(
                    row["name"],
                    lambda _checked=False, entry_id=row["id"], name=kind: self._pick_entry(name, entry_id),
                    kind="ghost",
                )
            )

    def _new_entry(self, kind: str) -> None:
        name = prompt(self, "新建", "名字")
        if not name or not name.strip():
            return
        created = self.library.create_entry(self.project_id, kind, name.strip())
        self._fill_codex(kind)
        self._pick_entry(kind, created)

    def _pick_entry(self, kind: str, entry_id: str) -> None:
        self.flush()
        self.focus = kind
        for button in self.nav_buttons.values():
            button.setChecked(False)
        self.chapter_col.hide()
        self.tool_row.hide()
        self.format_bar.hide()
        self.status_row.hide()
        self.beats.hide()
        self.selection_wrap.hide()
        self.page_title.show()
        self.stage.setCurrentWidget(self.doc_editor)
        self._open_entry(entry_id)

    def _load_tree(self) -> None:
        self._chapter_counts = {}
        _clear(self.chapter_layout)
        chapters = list(self.library.chapters(self.project_id))
        for kind, _label in CODEX:
            self.codex_counts[kind].setText(str(len(self.library.entries(self.project_id, kind))))
        if not chapters and not self.library.volumes(self.project_id):
            empty = QLabel("还没有章节。")
            empty.setObjectName("muted")
            self.chapter_layout.addWidget(empty)
            self.chapter_layout.addStretch(1)
            return
        for volume in self.library.volumes(self.project_id):
            owned = [row for row in chapters if row["volume_id"] == volume["id"]]
            header = QLabel(f"{volume['title']}    {len(owned)}")
            header.setObjectName("muted")
            self.chapter_layout.addWidget(header)
            add = _button("＋", lambda _checked=False, volume_id=volume["id"]: self._add_chapter(volume_id), kind="ghost")
            self.chapter_layout.addWidget(add)
            for chapter in owned:
                row = self._chapter_row(chapter)
                self._chapter_counts[chapter["id"]] = row
                self.chapter_layout.addWidget(row)
        self.chapter_layout.addStretch(1)
        ids = [row["id"] for row in chapters]
        if self.focus == "write" and self.focus_id not in ids and ids:
            restore = self._chapter_id if self._chapter_id in ids else ids[0]
            self._open_chapter(restore)
            self._load_tree()

    def _chapter_row(self, chapter) -> QFrame:
        chapter_id = chapter["id"]

        def choose(chosen=chapter_id) -> None:
            self.flush()
            self._open_chapter(chosen)
            self._load_tree()

        words = count_words_in_html(chapter["content"] or "")
        return ChapterRow(chapter["title"], words, chapter_id == self.focus_id, choose)

    def _load_entries(self, kind: str) -> None:
        labels = {key: tr(label) for key, label in CODEX}
        title = labels.get(kind, kind)
        self.page_title.setText(title)
        self.chapter_title.setText(title)
        self.chapter_col.show()
        _clear(self.chapter_layout)
        self.chapter_layout.addWidget(
            _button("＋", lambda _checked=False, name=kind: self._new_entry(name), kind="ghost")
        )
        for row in self.library.entries(self.project_id, kind):
            self.chapter_layout.addWidget(
                _button(
                    row["name"],
                    lambda _checked=False, entry_id=row["id"], name=kind: self._pick_entry(name, entry_id),
                    kind="ghost",
                )
            )
        self.chapter_layout.addStretch(1)
        self._loading = True
        self.doc_editor.setPlainText("")
        self._loading = False

    def _open_chapter(self, chapter_id: str) -> None:
        row = self.library.chapter(chapter_id)
        if row is None:
            return
        if chapter_id != self.focus_id:
            self._ask_summary()
        self.focus = "write"
        self.focus_id = chapter_id
        self._chapter_id = chapter_id
        self.nav_buttons["write"].setChecked(True)
        self.chapter_col.show()
        self.tool_row.show()
        self.summary.show()
        self.format_bar.show()
        self.status_row.show()
        self.stage.setCurrentWidget(self.editor)
        self._show_summary(row["summary"] or "")
        self.page_title.hide()
        self._loading = True
        self.editor.setHtml(row["content"] or "")
        self.goal.setPlainText(row["beat_goal"] or "")
        self.conflict.setPlainText(row["beat_conflict"] or "")
        self.outcome.setPlainText(row["beat_outcome"] or "")
        self._loading = False
        self._status()

    def _entry_clicked(self, item: QListWidgetItem) -> None:
        self.flush()
        entry_id = str(item.data(Qt.UserRole) or "")
        if not entry_id:
            name = prompt(self, "新建", "名字")
            if name and name.strip():
                created = self.library.create_entry(self.project_id, self.focus, name.strip())
                self._load_entries(self.focus)
                self._open_entry(created)
            return
        self.flush()
        self._open_entry(entry_id)

    def _open_entry(self, entry_id: str) -> None:
        row = self.library.entry(entry_id)
        if row is None:
            return
        self.focus_id = entry_id
        self.page_title.setText(row["name"])
        self.page_title.show()
        self._loading = True
        self.doc_editor.setPlainText(row["body"])
        self._loading = False

    def _dirty(self) -> None:
        if self._loading:
            return
        self.save_timer.start(900)
        self.save_label.setText(tr("unsaved"))
        self.header_saved.setText(tr("unsaved"))
        self._counts()

    def flush(self) -> None:
        self.save_timer.stop()
        if self.focus == "write" and self.focus_id:
            self.library.save_chapter_content(self.focus_id, self.editor.toHtml())
        elif self.focus in {"outline", "style"}:
            self.library.save_document(self.project_id, self.focus, self.doc_editor.toPlainText())
        elif self.focus_id and self.focus in {"character", "location", "lore", "plot", "note"}:
            row = self.library.entry(self.focus_id)
            if row is not None:
                self.library.save_entry(self.focus_id, row["name"], self.doc_editor.toPlainText())
        self._status()

    def _status(self) -> None:
        from datetime import datetime

        state = tr("unsaved") if self._summary_dirty else tr("saved")
        self.save_label.setText(state)
        self.header_saved.setText(state)
        self._counts()
        self.clock.setText(datetime.now().strftime("%H:%M"))
        chapter_name = ""
        volume_name = ""
        if self.focus == "write" and self.focus_id:
            chapter = self.library.chapter(self.focus_id)
            if chapter is not None:
                chapter_name = chapter["title"]
                volume = self.library._one("SELECT title FROM volume WHERE id = ?", (chapter["volume_id"],))
                volume_name = volume["title"] if volume else ""
        parts = [part for part in (self._title, volume_name, chapter_name) if part]
        self.heading.setText("   /   ".join(parts))

    def _goal(self) -> str:
        project = self.library.project(self.project_id)
        target = int(project["target_words"] or 0) if project is not None else 0
        if target:
            return f"{target:,}"
        return "—"

    def _counts(self) -> None:
        writing = self.focus == "write" and self.focus_id is not None
        body = count_words(self.editor.toPlainText()) if writing else 0
        summary = count_words(self.summary.toPlainText()) if writing else 0
        book = self.library.project_word_count(self.project_id)
        if writing:
            chapter = self.library.chapter(self.focus_id or "")
            stored = count_words_in_html(chapter["content"] or "") if chapter is not None else 0
            book += body - stored
            row = self._chapter_counts.get(self.focus_id or "")
            if row is not None:
                row.set_words(body)
            self.header_words.setText(tr("chapter_counts").format(body=f"{body:,}", summary=f"{summary:,}"))
        else:
            self.header_words.setText(tr("book_progress").format(n=f"{book:,}", goal=self._goal()))
        self.word_label.setText(tr("book_progress").format(n=f"{book:,}", goal=self._goal()))

    def _toggle_beats(self) -> None:
        self.beats.setVisible(not self.beats.isVisible())

    def _save_beats_later(self) -> None:
        if not self._loading:
            self.beat_timer.start(500)

    def _save_beats(self) -> None:
        if self.focus_id and self.focus == "write":
            self.library.save_beats(
                self.focus_id,
                self.goal.toPlainText(),
                self.conflict.toPlainText(),
                self.outcome.toPlainText(),
            )

    def _tree_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.addAction("新卷", self._add_volume)
        menu.addAction("新章", lambda: self._add_chapter(None))
        if self.focus == "write" and self.focus_id:
            chapter_id = self.focus_id
            menu.addAction(tr("rename_chapter"), lambda: self._rename_chapter(chapter_id))
            menu.addAction("删除这一章", lambda: self._delete_chapter(chapter_id))
        menu.exec(self.chapter_col.mapToGlobal(pos))

    def _rename_chapter(self, chapter_id: str) -> None:
        row = self.library.chapter(chapter_id)
        if row is None:
            return
        dialog = FormDialog(tr("rename_chapter"), tr("rename_hint"), self)
        field = QLineEdit(row["title"])
        dialog.label(tr("chapter_name"))
        dialog.add(field)
        dialog.cancel(tr("cancel"))

        def save() -> None:
            title = field.text().strip()
            if not title:
                return
            self.library.rename_chapter(chapter_id, title)
            dialog.accept()
            self._load_tree()
            self._status()

        dialog.primary(tr("ok"), save)
        dialog.exec()

    def _add_volume(self) -> None:
        title = prompt(self, "新卷", "卷名")
        if title:
            self.library.create_volume(self.project_id, title)
            self._load_tree()

    def _add_chapter(self, volume_id: str | None = None) -> None:
        if volume_id is None and self.focus_id:
            row = self.library.chapter(self.focus_id)
            volume_id = row["volume_id"] if row else None
        if volume_id is None:
            volumes = self.library.volumes(self.project_id)
            volume_id = volumes[0]["id"] if volumes else self.library.create_volume(self.project_id, "第一卷")
        title = prompt(self, "新章", "章名")
        if not title:
            return
        chapter_id = self.library.create_chapter(self.project_id, volume_id, title)
        self._open_chapter(chapter_id)
        self._load_tree()

    def _delete_chapter(self, chapter_id: str) -> None:
        if not confirm(self, "删除这一章", "这一章会从本机删掉。"):
            return
        self.library.conn.execute("DELETE FROM chapter WHERE id = ?", (chapter_id,))
        self.library.conn.commit()
        if self._chapter_id == chapter_id:
            self._chapter_id = None
        self.focus_id = None
        self._load_tree()

    def _on_selection(self) -> None:
        text = self.editor.textCursor().selectedText().replace("\u2029", "\n").strip()
        self.selection_wrap.setVisible(self.focus == "write" and bool(text))

    def _selection(self, action: str) -> None:
        cursor = self.editor.textCursor()
        passage = cursor.selectedText().replace("\u2029", "\n").strip()
        if not passage:
            passage = self._passage
        else:
            self._passage = passage
            self._range = (cursor.selectionStart(), cursor.selectionEnd())
        if not passage:
            return
        if self.provider() is None:
            return
        if self._selection_dialog is None:
            self._selection_dialog = SelectionDialog(self, self._rerun)
            self._selection_dialog.accepted.connect(self._accept_selection)
        dialog = self._selection_dialog
        dialog.note.clear()
        dialog.action = action
        dialog.show_passage(passage)
        dialog.draft.setPlainText("正在写…")
        dialog.show()
        self._rerun(action, "", False)

    def _rerun(self, action: str, note: str, again: bool) -> None:
        source = self._passage
        if not source:
            return
        provider = self.provider()
        if not provider:
            return
        base, key, model = provider
        system = read_prompt("selection")
        extra = f"Author's note:\n{note.strip()}\n\n" if note.strip() else ""
        user = f"Action: {action}\n\n{extra}Passage:\n{source}"
        style = self.library.document(self.project_id, "style").strip()
        if style:
            system += f"\n\nSTYLE\n{style[:4000]}"
        previous = ""
        if self._selection_dialog is not None:
            previous = self._selection_dialog.draft.toPlainText()
            if again:
                self._selection_dialog.draft.setPlainText("正在写…")

        def work() -> str:
            return plain_complete(base, key, model, system, user)

        def ok(text: str) -> None:
            if self._selection_dialog:
                self._selection_dialog.draft.setPlainText(text)

        def fail(message: str) -> None:
            dialog = self._selection_dialog
            if again and dialog is not None:
                dialog.draft.setPlainText(previous)
            elif dialog is not None:
                dialog.hide()
            alert(self, "改写", message)

        self._start(Job(work), ok, fail)

    def _accept_selection(self) -> None:
        dialog = self._selection_dialog
        if dialog is None or not self.focus_id:
            return
        draft = dialog.draft.toPlainText().strip()
        if not draft or draft == "正在写…":
            return
        self.flush()
        self.library.snapshot(self.focus_id, "ai")
        cursor = self.editor.textCursor()
        cursor.setPosition(self._range[0])
        cursor.setPosition(self._range[1], QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(draft)
        self.editor.setTextCursor(cursor)
        self.flush()

    def _check(self) -> None:
        if not self.focus_id:
            return
        provider = self.provider()
        if not provider:
            return
        self.flush()
        base, key, model = provider
        chapter = self.library.chapter(self.focus_id)
        if chapter is None:
            return
        bound = set(self.library.bindings(self.focus_id))
        blocks = [f"{chapter['title']}\n{html_to_plain(chapter['content'])}"]
        for kind in ("character", "location", "plot"):
            for row in self.library.entries(self.project_id, kind):
                if row["id"] in bound:
                    blocks.append(f"{kind} {row['name']}\n{row['body']}")
        for row in self.library.entries(self.project_id, "lore")[:40]:
            blocks.append(f"lore {row['name']}\n{row['body']}")
        style = self.library.document(self.project_id, "style").strip()
        if style:
            blocks.append(f"STYLE\n{style}")
        user = "\n\n".join(blocks)
        system = read_prompt("chapter-check")

        def work() -> str:
            return plain_complete(base, key, model, system, user)

        def ok(text: str) -> None:
            parsed = parse_extract(text)
            issues = parsed.get("issues") if isinstance(parsed, dict) else None
            if not isinstance(issues, list) or not issues:
                shown = "没有发现和设定冲突的地方。" if isinstance(issues, list) else text
            else:
                lines = []
                for issue in issues:
                    if isinstance(issue, dict):
                        lines.append(f"{issue.get('quote', '')}\n{issue.get('detail', '')}")
                shown = "\n\n".join(lines) or text
            dialog = FormDialog("对照设定检查这一章", shown if isinstance(issues, list) and not issues else "只列出正文和设定都写明、又对不上的地方。", self)
            if isinstance(issues, list):
                for issue in issues:
                    if not isinstance(issue, dict):
                        continue
                    card = QFrame()
                    card.setObjectName("issue")
                    column = QVBoxLayout(card)
                    quote = QLabel(str(issue.get("quote") or ""))
                    quote.setWordWrap(True)
                    detail = QLabel(str(issue.get("detail") or ""))
                    detail.setObjectName("muted")
                    detail.setWordWrap(True)
                    column.addWidget(quote)
                    column.addWidget(detail)
                    dialog.add(card)
            else:
                raw = QLabel(shown)
                raw.setWordWrap(True)
                dialog.add(raw)
            dialog.primary("关闭", dialog.accept)
            dialog.exec()

        self._start(Job(work), ok, lambda message: alert(self, "检查", message))

    def _revisions(self) -> None:
        if not self.focus_id:
            return
        labels = {"ai": "AI 写入前", "manual": "你保存的", "restore": "恢复前"}
        dialog = FormDialog("更早的版本", "还没有保存过版本" if not self.library.revisions(self.focus_id) else "恢复后，现在这一版会先被记下来。", self)
        listing = QVBoxLayout()

        def fill() -> None:
            _clear(listing)
            rows = self.library.revisions(self.focus_id or "")
            title = dialog.findChild(QLabel)
            if title is not None:
                title.setText("更早的版本")
            if not rows:
                empty = QLabel("还没有保存过版本")
                empty.setObjectName("muted")
                listing.addWidget(empty)
                return
            for row in rows:
                line = QHBoxLayout()
                text = QLabel(f"{labels.get(row['source'], row['source'])}    {row['created_at']}")
                revision_id = row["id"]
                line.addWidget(text, 1)
                line.addWidget(_button("恢复", lambda _checked=False, chosen=revision_id: restore(chosen), kind="outline"))
                holder = QWidget()
                holder.setLayout(line)
                listing.addWidget(holder)

        def restore(revision_id: str) -> None:
            if not self.focus_id:
                return
            html = self.library.restore(self.focus_id, revision_id)
            if html is None:
                return
            self._loading = True
            self.editor.setHtml(html)
            self._loading = False
            dialog.accept()

        def remember() -> None:
            if not self.focus_id:
                return
            self.flush()
            self.library.snapshot(self.focus_id, "manual")
            fill()

        dialog.body.addLayout(listing)
        dialog.footer.addWidget(_button("记下这一版", remember, kind="outline"))
        fill()
        dialog.exec()

    def _export(self) -> None:
        menu = QMenu(self)
        menu.addAction("Markdown", lambda: self._save_export(False))
        menu.addAction("适合贴到平台的纯文本", lambda: self._save_export(True))
        menu.exec(self.mapToGlobal(self.tool_row.pos()))

    def _save_export(self, plain: bool) -> None:
        self.flush()
        title, chapters = self.library.manuscript(self.project_id)
        text = web_novel(title, chapters) if plain else markdown(title, chapters)
        suffix = "txt" if plain else "md"
        path, _chosen = QFileDialog.getSaveFileName(self, "导出", f"{title}.{suffix}", f"*.{suffix}")
        if path:
            Path(path).write_text(text, encoding="utf-8")

    def _bindings(self) -> None:
        if not self.focus_id or self.focus != "write":
            return
        chosen = set(self.library.bindings(self.focus_id))
        dialog = FormDialog("这一章的绑定", "勾选这一章对话时要带上的角色、地点和情节线。", self)
        boxes: list[tuple[QCheckBox, str]] = []
        for kind, label in (("character", "角色"), ("location", "地点"), ("plot", "情节线")):
            for row in self.library.entries(self.project_id, kind):
                box = QCheckBox(f"{label} · {row['name']}")
                box.setChecked(row["id"] in chosen)
                boxes.append((box, row["id"]))
                dialog.add(box)
        if not boxes:
            dialog.label("还没有可以绑定的条目。")
        dialog.cancel()

        def save() -> None:
            if self.focus_id:
                self.library.set_bindings(self.focus_id, [entry_id for box, entry_id in boxes if box.isChecked()])
            dialog.accept()

        dialog.primary("保存", save)
        dialog.exec()

    def _summary(self) -> None:
        if not self.focus_id:
            return
        self.flush()
        plain = self.library.chapter_plain(self.focus_id).strip()
        if not plain:
            alert(self, tr("summary_title"), tr("summary_empty"))
            return
        provider = self.provider()
        if not provider:
            return
        base, key, model = provider
        chapter = self.library.chapter(self.focus_id)
        title = chapter["title"] if chapter else ""
        limit = min(120, len(plain))
        system = read_prompt("chapter-summary")
        system += (
            f"\nThe chapter is {len(plain)} characters. "
            f"Reply in at most {limit} characters. "
            "If a fact is not in the chapter, leave it out."
        )
        user = f"Chapter title: {title}\n\n{plain[:12_000]}"

        def work() -> str:
            return plain_complete(base, key, model, system, user, temperature=0.2, max_tokens=256)

        def ok(text: str) -> None:
            clean = _clip_summary(text, limit)
            if not clean:
                alert(self, tr("summary_title"), tr("summary_empty"))
                return
            self.summary.setPlainText(clean)
            self.header_saved.setText(tr("unsaved"))

        self._start(Job(work), ok, lambda message: alert(self, tr("summary_title"), message))

    def _continue(self) -> None:
        if not self.focus_id:
            return
        provider = self.provider()
        if not provider:
            return
        self.flush()
        base, key, model = provider
        plain = self.library.chapter_plain(self.focus_id)
        tail = plain[-2000:]
        system = read_prompt("completion")
        style = self.library.document(self.project_id, "style").strip()
        if style:
            system += f"\n\nSTYLE\n{style[:4000]}"

        def work() -> str:
            return plain_complete(base, key, model, system, tail)

        def ok(text: str) -> None:
            dialog = FormDialog("续写", "接到章末后，这一段会写在当前章的最后。", self)
            preview = QPlainTextEdit(text or "没有续上。")
            preview.setReadOnly(True)
            preview.setMinimumHeight(180)
            dialog.add(preview)
            dialog.cancel("留下")

            def take() -> None:
                if text.strip() and self.focus_id:
                    self.library.snapshot(self.focus_id, "ai")
                    self.editor.moveCursor(QTextCursor.MoveOperation.End)
                    self.editor.insertHtml(plain_to_html(text.strip()))
                    self.flush()
                dialog.accept()

            dialog.primary("接到章末", take)
            dialog.exec()

        self._start(Job(work), ok, lambda message: alert(self, "续写", message))

    def _import(self) -> None:
        path, _chosen = QFileDialog.getOpenFileName(self, "导入", "", "文本 (*.txt *.md)")
        if not path:
            return
        raw = Path(path).read_text(encoding="utf-8")
        parts = CHAPTER_SPLIT.split(raw)
        volumes = self.library.volumes(self.project_id)
        volume_id = volumes[0]["id"] if volumes else self.library.create_volume(self.project_id, "第一卷")
        if len(parts) <= 1:
            self.library.create_chapter(self.project_id, volume_id, Path(path).stem)
            chapter_id = self.library.chapters(self.project_id)[-1]["id"]
            self.library.save_chapter_content(chapter_id, plain_to_html(raw.strip()))
        else:
            index = 1
            while index < len(parts):
                title = parts[index].strip()
                body = parts[index + 1] if index + 1 < len(parts) else ""
                chapter_id = self.library.create_chapter(self.project_id, volume_id, title.lstrip("# ").strip())
                self.library.save_chapter_content(chapter_id, plain_to_html(body.strip()))
                index += 2
        self._load_tree()
        if not ask(self, "导入", "要让模型从正文里抽出人物、地点和设定吗？", "抽取", "先不抽"):
            return
        provider = self.provider()
        if not provider:
            return
        base, key, model = provider
        known = []
        for kind in ("character", "location", "lore", "plot"):
            known.extend(row["name"] for row in self.library.entries(self.project_id, kind))
        system = read_prompt("import-extract")
        user = "knownNames: " + "、".join(known) + "\n\n" + raw[:12_000]

        def work() -> str:
            return plain_complete(base, key, model, system, user)

        def ok(text: str) -> None:
            data = parse_extract(text)
            if not isinstance(data, dict):
                alert(self, "导入", "模型没有返回可用的条目。")
                return
            for kind, key_name in (
                ("character", "characters"),
                ("location", "locations"),
                ("lore", "lore"),
                ("plot", "plot"),
            ):
                rows = data.get(key_name)
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    name = str(row.get("name") or row.get("title") or "").strip()
                    description = str(row.get("description") or "").strip()
                    if name:
                        self.library.create_entry(self.project_id, kind, name, description)
            self._load_tree()

        self._start(Job(work), ok, lambda message: alert(self, "导入", message))

    def _bubble(self, role: str, content: str) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        text = QLabel(content)
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        text.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        if role == "user":
            text.setObjectName("bubble-user")
            row.addStretch(1)
            row.addWidget(text)
            return wrap
        text.setObjectName("bubble-bot")
        mark = QLabel("N")
        mark.setObjectName("avatar")
        mark.setFixedSize(28, 28)
        mark.setAlignment(Qt.AlignCenter)
        column = QVBoxLayout()
        column.setSpacing(2)
        column.addWidget(text)
        insert = _button("Insert into editor", lambda _checked=False, body=content: self._insert_chat(body), kind="link")
        column.addWidget(insert, alignment=Qt.AlignLeft)
        row.addWidget(mark, alignment=Qt.AlignTop)
        row.addLayout(column, 1)
        return wrap

    def _insert_chat(self, content: str) -> None:
        if self.focus != "write" or not self.focus_id:
            return
        self.editor.moveCursor(QTextCursor.MoveOperation.End)
        self.editor.insertHtml(plain_to_html(content))
        self.flush()

    def _load_chat(self) -> None:
        _clear(self.chat_layout)
        rows = list(self.library.messages(self.project_id))
        if not rows:
            hello = QLabel("我可以帮你写。可以问角色、情节、文风或叙事。")
            hello.setObjectName("muted")
            hello.setWordWrap(True)
            hello.setAlignment(Qt.AlignCenter)
            self.chat_layout.addWidget(hello)
            ask = QLabel("可以试试：")
            ask.setObjectName("muted")
            ask.setAlignment(Qt.AlignCenter)
            self.chat_layout.addWidget(ask)
            for suggestion in SUGGESTIONS:
                chip = _button(suggestion, lambda _checked=False, text=suggestion: self.chat_input.setText(text), kind="chip")
                chip.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
                self.chat_layout.addWidget(chip, alignment=Qt.AlignHCenter)
        for row in rows:
            if row["role"] in {"user", "assistant"}:
                self.chat_layout.addWidget(self._bubble(row["role"], row["content"]))
        self.chat_layout.addStretch(1)

    def _format(self, action: str) -> None:
        cursor = self.editor.textCursor()
        if action == "undo":
            self.editor.undo()
            return
        if action == "redo":
            self.editor.redo()
            return
        char = cursor.charFormat()
        if action == "bold":
            heavy = char.fontWeight() >= QFont.Weight.Bold
            char.setFontWeight(QFont.Weight.Normal if heavy else QFont.Weight.Bold)
        elif action == "italic":
            char.setFontItalic(not char.fontItalic())
        elif action == "underline":
            char.setFontUnderline(not char.fontUnderline())
        elif action == "strike":
            char.setFontStrikeOut(not char.fontStrikeOut())
        elif action == "paragraph":
            char.setFontPointSize(15)
            char.setFontItalic(False)
        elif action == "heading":
            char.setFontPointSize(22 if char.fontPointSize() < 20 else 15)
        elif action == "code":
            char.setFontFamilies(["Cascadia Mono", "Consolas"])
        elif action == "highlight":
            char.setBackground(Qt.transparent if char.background().color().alpha() else Qt.yellow)
        elif action in {"align-left", "align-center", "align-right", "align-justify"}:
            block = cursor.blockFormat()
            alignments = {
                "align-left": Qt.AlignLeft,
                "align-center": Qt.AlignCenter,
                "align-right": Qt.AlignRight,
                "align-justify": Qt.AlignJustify,
            }
            block.setAlignment(alignments[action])
            cursor.mergeBlockFormat(block)
            return
        elif action == "list":
            cursor.createList(QTextListFormat.Style.ListDisc)
            return
        elif action == "numbered":
            cursor.createList(QTextListFormat.Style.ListDecimal)
            return
        elif action == "todo":
            cursor.insertText("☐ ")
            return
        elif action == "quote":
            block = cursor.blockFormat()
            block.setLeftMargin(0 if block.leftMargin() > 8 else 18)
            cursor.mergeBlockFormat(block)
            return
        elif action == "code-block":
            block = cursor.blockFormat()
            block.setLeftMargin(12)
            cursor.mergeBlockFormat(block)
            char.setFontFamilies(["Cascadia Mono", "Consolas"])
        elif action == "link":
            dialog = FormDialog("添加链接", "", self)
            url = QLineEdit()
            url.setPlaceholderText("https://")
            dialog.label("地址")
            dialog.add(url)
            dialog.cancel()

            def apply() -> None:
                if url.text().strip():
                    linked = self.editor.textCursor().charFormat()
                    linked.setAnchor(True)
                    linked.setAnchorHref(url.text().strip())
                    linked.setFontUnderline(True)
                    self.editor.textCursor().mergeCharFormat(linked)
                dialog.accept()

            dialog.primary("添加链接", apply)
            dialog.exec()
            return
        cursor.mergeCharFormat(char)
        self.editor.mergeCurrentCharFormat(char)

    def _send(self) -> None:
        text = self.chat_input.text().strip()
        if not text:
            return
        provider = self.provider()
        if not provider:
            return
        self.flush()
        base, key, model = provider
        self.library.add_message(self.project_id, "user", text)
        self.chat_input.clear()
        self.editor.setReadOnly(True)
        self._load_chat()
        focus = "chapter" if self.focus == "write" else self.focus
        worker = ChatWorker(
            self.library.path,
            self.project_id,
            focus,
            self.focus_id,
            base,
            key,
            model,
            str(QSettings("Novel", "Novel").value("confirm_write", "true")) == "false",
        )
        worker.ask.connect(self._approve)
        worker.reply.connect(self._chat_done)
        worker.failed.connect(self._chat_failed)
        worker.changed.connect(self._open_chapter)
        self._jobs.append(worker)
        worker.start()

    def _approve(self, summary: str) -> None:
        worker = self.sender()
        accepted = ask(self, "写入前确认", summary, "写入", "留下")
        if isinstance(worker, ChatWorker):
            worker.decide(accepted)

    def _chat_failed(self, message: str) -> None:
        self.editor.setReadOnly(False)
        alert(self, "对话", message)

    def _chat_done(self, _text: str) -> None:
        self.editor.setReadOnly(False)
        self._load_chat()
        if self.focus in {"outline", "style"}:
            self._loading = True
            self.doc_editor.setPlainText(self.library.document(self.project_id, self.focus))
            self._loading = False
        elif self.focus_id and self.focus in {"character", "location", "lore", "plot", "note"}:
            self._open_entry(self.focus_id)

    def _start(self, job: Job, ok, fail) -> None:
        job.done.connect(ok)
        job.failed.connect(fail)
        self._jobs.append(job)
        job.start()


class TitleBar(QWidget):
    def __init__(self, window: QWidget):
        super().__init__(window)
        self._window = window
        self.setObjectName("header")
        self.setFixedHeight(40)
        mark = QLabel()
        mark.setPixmap(app_icon().pixmap(18, 18))
        self.caption = QLabel("Novel")
        self.caption.setObjectName("logo")
        self.min_button = QPushButton()
        self.min_button.setObjectName("icon")
        self.min_button.setIcon(icon("minimize"))
        self.min_button.clicked.connect(window.showMinimized)
        self.max_button = QPushButton()
        self.max_button.setObjectName("icon")
        self.max_button.setIcon(icon("maximize"))
        self.max_button.clicked.connect(self._toggle)
        self.close_button = QPushButton()
        self.close_button.setObjectName("icon")
        self.close_button.setIcon(icon("close"))
        self.close_button.clicked.connect(window.close)
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 6, 0)
        row.setSpacing(2)
        row.addWidget(mark)
        row.addWidget(self.caption)
        row.addStretch(1)
        row.addWidget(self.min_button)
        row.addWidget(self.max_button)
        row.addWidget(self.close_button)
        self.retranslate()

    def retranslate(self) -> None:
        self.min_button.setToolTip(tr("window_min"))
        self.max_button.setToolTip(tr("window_max"))
        self.close_button.setToolTip(tr("window_close"))

    def _toggle(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
            return
        self._window.showMaximized()

    def mouseDoubleClickEvent(self, event) -> None:
        self._toggle()
        super().mouseDoubleClickEvent(event)


class _Rect(ctypes.Structure):
    _fields_ = (
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    )


class _MonitorInfo(ctypes.Structure):
    _fields_ = (
        ("cbSize", ctypes.c_ulong),
        ("rcMonitor", _Rect),
        ("rcWork", _Rect),
        ("dwFlags", ctypes.c_ulong),
    )


class _NcCalcSize(ctypes.Structure):
    _fields_ = (("rgrc", _Rect * 3), ("lppos", ctypes.c_void_p))


class _Point(ctypes.Structure):
    _fields_ = (("x", ctypes.c_long), ("y", ctypes.c_long))


class _MinMaxInfo(ctypes.Structure):
    _fields_ = (
        ("reserved", _Point),
        ("max_size", _Point),
        ("max_position", _Point),
        ("min_track", _Point),
        ("max_track", _Point),
    )


class NovelWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Novel")
        self.setWindowIcon(app_icon())
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.resize(1280, 800)
        from PySide6.QtCore import QSettings

        self.store = QSettings("Novel", "Novel")
        set_locale(str(self.store.value("locale", "zh") or "zh"))
        self.library: Library | None = None
        self.title_bar = TitleBar(self)
        self.stack = QStackedWidget()
        shell = QWidget()
        column = QVBoxLayout(shell)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.setSizeConstraint(QVBoxLayout.SizeConstraint.SetNoConstraint)
        column.addWidget(self.title_bar)
        column.addWidget(self.stack, 1)
        shell.setMinimumSize(0, 0)
        shell.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.stack.setMinimumSize(0, 0)
        self.stack.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setCentralWidget(shell)
        self.setMinimumSize(0, 0)
        self.statusBar().hide()
        self._glass = False
        self.login = LoginPage(self._enter)
        saved = self.store.value("auth_url", "http://127.0.0.1:8787")
        self.login.server.setText(str(saved))
        self.stack.addWidget(self.login)
        token = str(self.store.value("token", "") or "")
        if token:
            try:
                payload = auth_client.me(str(saved), token)
            except Exception:
                payload = None
            if payload and payload.get("user"):
                self._enter(str(saved), token, payload["user"])

    def minimumSizeHint(self) -> QSize:
        return QSize(0, 0)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._glass:
            self._glass = True
            enable_glass(self)
            self._enable_resize()

    def _enable_resize(self) -> None:
        if sys.platform != "win32":
            return
        hwnd = int(self.winId())
        get_long = ctypes.windll.user32.GetWindowLongPtrW
        set_long = ctypes.windll.user32.SetWindowLongPtrW
        get_long.restype = ctypes.c_ssize_t
        get_long.argtypes = [ctypes.c_void_p, ctypes.c_int]
        set_long.restype = ctypes.c_ssize_t
        set_long.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
        style = get_long(hwnd, -16)
        style |= 0x00040000 | 0x00010000 | 0x00020000
        set_long(hwnd, -16, style)
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0020 | 0x0002 | 0x0001 | 0x0004)

    def _enter(self, base: str, token: str, user: dict) -> None:
        user_id = str(user.get("id") or "")
        if not user_id or not token:
            return
        self.store.setValue("auth_url", base)
        self.store.setValue("token", token)
        self.store.setValue("user_id", user_id)
        self.store.setValue("user_name", str(user.get("name") or ""))
        if self.library:
            self.library.close()
        self.library = Library(library_path(user_id))
        self.projects = ProjectPage(
            self._open_project,
            self._logout,
            self.library,
            str(self.store.value("user_name", "") or ""),
            self._set_locale,
        )
        self.stack.addWidget(self.projects)
        self.stack.setCurrentWidget(self.projects)
        name = str(user.get("name") or "")
        self.statusBar().showMessage(name)
        if str(self.store.value("open_on_start", "last")) != "shelf":
            last = str(self.store.value("last_project", "") or "")
            if last and self.library.project(last) is not None:
                self._open_project(last)

    def _open_project(self, project_id: str) -> None:
        if self.library is None:
            return
        self.store.setValue("last_project", project_id)
        self.desk = DeskPage(self.library, project_id, self._back, str(self.store.value("user_name", "") or ""))
        self.statusBar().hide()
        self.stack.addWidget(self.desk)
        self.stack.setCurrentWidget(self.desk)

    def _back(self) -> None:
        if hasattr(self, "desk"):
            self.desk._ask_summary()
            self.desk.flush()
            self.stack.removeWidget(self.desk)
            self.desk.deleteLater()
        self.projects.reload()
        self.stack.setCurrentWidget(self.projects)

    def _logout(self) -> None:
        self.store.setValue("token", "")
        if self.library:
            self.library.close()
            self.library = None
        self.stack.setCurrentWidget(self.login)

    def _set_locale(self, code: str) -> None:
        set_locale(code)
        self.store.setValue("locale", "en" if code == "en" else "zh")
        self.login.retranslate()
        self.title_bar.retranslate()
        if hasattr(self, "projects"):
            self.projects.retranslate()
        if hasattr(self, "desk"):
            self.desk.retranslate()

    def nativeEvent(self, event_type, message):
        kind = bytes(event_type)
        if sys.platform == "win32" and kind == b"windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == 0x0024:
                limits = ctypes.cast(msg.lParam, ctypes.POINTER(_MinMaxInfo)).contents
                limits.min_track.x = 0
                limits.min_track.y = 0
                return True, 0
            if msg.message == 0x0083 and msg.wParam:
                if self.isMaximized():
                    params = ctypes.cast(msg.lParam, ctypes.POINTER(_NcCalcSize)).contents
                    monitor = ctypes.windll.user32.MonitorFromWindow(int(self.winId()), 2)
                    info = _MonitorInfo()
                    info.cbSize = ctypes.sizeof(info)
                    ctypes.windll.user32.GetMonitorInfoW(monitor, ctypes.byref(info))
                    params.rgrc[0].left = info.rcWork.left
                    params.rgrc[0].top = info.rcWork.top
                    params.rgrc[0].right = info.rcWork.right
                    params.rgrc[0].bottom = info.rcWork.bottom
                return True, 0
            if msg.message == 0x0084 and not self.isMaximized():
                screen_x = ctypes.c_short(msg.lParam & 0xFFFF).value
                screen_y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
                pos = self.mapFromGlobal(QPoint(screen_x, screen_y))
                border = 8
                width = self.width()
                height = self.height()
                left = pos.x() <= border
                right = pos.x() >= width - border
                top = pos.y() <= border
                bottom = pos.y() >= height - border
                if top and left:
                    return True, 13
                if top and right:
                    return True, 14
                if bottom and left:
                    return True, 16
                if bottom and right:
                    return True, 17
                if left:
                    return True, 10
                if right:
                    return True, 11
                if top:
                    return True, 12
                if bottom:
                    return True, 15
                if pos.y() <= 40 and pos.x() < width - 132:
                    return True, 2
        return super().nativeEvent(event_type, message)

    def closeEvent(self, event) -> None:
        if hasattr(self, "desk"):
            self.desk._ask_summary()
            self.desk.flush()
        if self.library:
            self.library.close()
        super().closeEvent(event)
