"""Login, the shelf, and the writing desk."""

import os
import re
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from desktop import auth_client
from desktop.engine import plain_complete, read_prompt
from desktop.extract import parse_extract
from desktop.export import markdown, web_novel
from desktop.jobs import ChatWorker, Job
from desktop.store import Library
from desktop.wordcount import count_words_in_html, html_to_plain, plain_to_html

CHAPTER_SPLIT = re.compile(r"(?m)^(第[0-9一二三四五六七八九十百千零两]+章[^\n]*|#{1,3} .+)$")
NAV = (
    ("write", "章节"),
    ("outline", "大纲"),
    ("style", "文风"),
    ("character", "人物"),
    ("location", "地点"),
    ("lore", "设定"),
    ("plot", "情节"),
    ("note", "笔记"),
    ("map", "故事地图"),
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


def _button(text: str, slot, primary: bool = False) -> QPushButton:
    button = QPushButton(text)
    if primary:
        button.setObjectName("primary")
    button.clicked.connect(slot)
    return button


class LoginPage(QWidget):
    def __init__(self, enter):
        super().__init__()
        self._enter = enter
        self._mode = "login"
        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(420)
        layout = QVBoxLayout(card)
        title = QLabel("Novel")
        title.setObjectName("title")
        hint = QLabel("登录之后，书留在这台电脑上。")
        hint.setObjectName("hint")
        self.server = QLineEdit("http://127.0.0.1:8787")
        self.email = QLineEdit()
        self.email.setPlaceholderText("邮箱")
        self.name = QLineEdit()
        self.name.setPlaceholderText("怎么称呼你")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("密码，至少 8 位")
        self.error = QLabel("")
        self.error.setObjectName("hint")
        self.submit = _button("登录", self._submit, True)
        switch = _button("没有账号？去注册", self._switch)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(QLabel("账号服务"))
        layout.addWidget(self.server)
        layout.addWidget(self.email)
        layout.addWidget(self.name)
        layout.addWidget(self.password)
        layout.addWidget(self.error)
        layout.addWidget(self.submit)
        layout.addWidget(switch)
        self.name.hide()
        outer = QVBoxLayout(self)
        outer.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(card)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)

    def _switch(self) -> None:
        self._mode = "register" if self._mode == "login" else "login"
        self.name.setVisible(self._mode == "register")
        self.submit.setText("注册并进入" if self._mode == "register" else "登录")

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
    def __init__(self, open_project, logout, library: Library):
        super().__init__()
        self._open = open_project
        self._logout = logout
        self.library = library
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self._open_current)
        bar = QHBoxLayout()
        title = QLabel("书")
        title.setObjectName("title")
        bar.addWidget(title)
        bar.addStretch(1)
        bar.addWidget(_button("模型", self._provider))
        bar.addWidget(_button("新建", self._create, True))
        bar.addWidget(_button("重命名", self._rename))
        bar.addWidget(_button("删除", self._delete))
        bar.addWidget(_button("退出", self._logout))
        layout = QVBoxLayout(self)
        layout.addLayout(bar)
        layout.addWidget(self.list)
        self.reload()

    def reload(self) -> None:
        self.list.clear()
        for row in self.library.projects():
            words = self.library.project_word_count(row["id"])
            item = QListWidgetItem(f"{row['title']}    {words} 字")
            item.setData(Qt.UserRole, row["id"])
            self.list.addItem(item)

    def _selected(self) -> str | None:
        item = self.list.currentItem()
        if item is None:
            return None
        return str(item.data(Qt.UserRole))

    def _create(self) -> None:
        title, ok = QInputDialog.getText(self, "新建", "书名")
        if not ok:
            return
        genre, genre_ok = QInputDialog.getText(self, "新建", "类型，可以留空")
        if not genre_ok:
            genre = ""
        project_id = self.library.create_project(title, genre)
        self._open(project_id)

    def _rename(self) -> None:
        project_id = self._selected()
        if not project_id:
            return
        title, ok = QInputDialog.getText(self, "重命名", "书名")
        if ok and title.strip():
            self.library.rename_project(project_id, title)
            self.reload()

    def _delete(self) -> None:
        project_id = self._selected()
        if not project_id:
            return
        if QMessageBox.question(self, "删除", "这本书会从这台电脑上删掉。") != QMessageBox.Yes:
            return
        self.library.delete_project(project_id)
        self.reload()

    def _open_current(self) -> None:
        project_id = self._selected()
        if project_id:
            self._open(project_id)

    def _provider(self) -> None:
        row = self.library.provider()
        dialog = QDialog(self)
        dialog.setWindowTitle("模型")
        form = QVBoxLayout(dialog)
        base = QLineEdit(row["base_url"])
        model = QLineEdit(row["model"])
        key = QLineEdit(row["api_key"])
        key.setEchoMode(QLineEdit.Password)
        form.addWidget(QLabel("接口地址"))
        form.addWidget(base)
        form.addWidget(QLabel("模型名"))
        form.addWidget(model)
        form.addWidget(QLabel("密钥只保存在本机"))
        form.addWidget(key)
        form.addWidget(_button("保存", dialog.accept, True))
        if dialog.exec() == QDialog.Accepted:
            self.library.save_provider(base.text(), model.text(), key.text())


class SelectionDialog(QDialog):
    def __init__(self, parent, run):
        super().__init__(parent)
        self.setWindowTitle("改这一段")
        self._run = run
        self.action = "rewrite"
        self.draft = QPlainTextEdit()
        self.note = QPlainTextEdit()
        self.note.setPlaceholderText("想怎么改，写在这里。留空也会按原来的要求再来一次。")
        self.note.setFixedHeight(72)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.draft)
        self.layout().addWidget(QLabel("你的看法"))
        self.layout().addWidget(self.note)
        row = QHBoxLayout()
        row.addWidget(_button("重来", self._again))
        row.addWidget(_button("替换选区", self.accept, True))
        self.layout().addLayout(row)

    def _again(self) -> None:
        self._run(self.action, self.note.toPlainText(), True)


class DeskPage(QWidget):
    def __init__(self, library: Library, project_id: str, back):
        super().__init__()
        self.library = library
        self.project_id = project_id
        self.focus = "write"
        self.focus_id: str | None = None
        self._jobs: list[Job | ChatWorker] = []
        self._passage = ""
        self._range = (0, 0)
        self._selection_dialog: SelectionDialog | None = None
        project = library.project(project_id)
        self._title = project["title"] if project else "未命名"

        self.nav_buttons: dict[str, QPushButton] = {}
        nav = QVBoxLayout()
        for key, label in NAV:
            button = QPushButton(label)
            button.setObjectName("quiet")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, name=key: self.show_section(name))
            self.nav_buttons[key] = button
            nav.addWidget(button)
        nav.addStretch(1)
        nav.addWidget(_button("返回书架", back))
        side = QFrame()
        side.setObjectName("sidebar")
        side.setLayout(nav)
        side.setFixedWidth(168)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemClicked.connect(self._tree_clicked)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_menu)
        self.entry_list = QListWidget()
        self.entry_list.itemClicked.connect(self._entry_clicked)
        self.browser = QStackedWidget()
        self.browser.addWidget(self.tree)
        self.browser.addWidget(self.entry_list)

        self.editor = QTextEdit()
        self.editor.setObjectName("editor")
        self.editor.setAcceptRichText(True)
        self.editor.selectionChanged.connect(self._on_selection)
        self.editor.textChanged.connect(self._dirty)
        self.doc_editor = QPlainTextEdit()
        self.doc_editor.textChanged.connect(self._dirty)
        self.map_label = QLabel("故事地图还留着空位。")
        self.map_label.setAlignment(Qt.AlignCenter)
        self.map_label.setObjectName("muted")
        self.stage = QStackedWidget()
        self.stage.addWidget(self.editor)
        self.stage.addWidget(self.doc_editor)
        self.stage.addWidget(self.map_label)

        self.goal = QPlainTextEdit()
        self.conflict = QPlainTextEdit()
        self.outcome = QPlainTextEdit()
        for box, name in ((self.goal, "这一章想写成什么"), (self.conflict, "冲突"), (self.outcome, "结尾落在哪")):
            box.setPlaceholderText(name)
            box.setFixedHeight(64)
            box.textChanged.connect(self._save_beats_later)
        beats = QWidget()
        beat_layout = QVBoxLayout(beats)
        beat_layout.setContentsMargins(12, 8, 12, 8)
        beat_layout.addWidget(QLabel("节拍"))
        beat_layout.addWidget(self.goal)
        beat_layout.addWidget(self.conflict)
        beat_layout.addWidget(self.outcome)
        self.beats = beats
        self.beats.hide()

        tools = QHBoxLayout()
        tools.addWidget(_button("节拍", self._toggle_beats))
        tools.addWidget(_button("检查", self._check))
        tools.addWidget(_button("版本", self._revisions))
        tools.addWidget(_button("导出", self._export))
        tools.addWidget(_button("绑定", self._bindings))
        tools.addWidget(_button("摘要", self._summary))
        tools.addWidget(_button("续写", self._continue))
        tools.addWidget(_button("导入", self._import))
        tools.addStretch(1)
        self.tool_row = QWidget()
        self.tool_row.setLayout(tools)

        self.selection_bar = QHBoxLayout()
        for key, label in ACTIONS:
            self.selection_bar.addWidget(_button(label, lambda _checked=False, name=key: self._selection(name)))
        self.selection_bar.addStretch(1)
        self.selection_wrap = QWidget()
        self.selection_wrap.setLayout(self.selection_bar)
        self.selection_wrap.hide()

        center = QVBoxLayout()
        self.heading = QLabel(self._title)
        self.heading.setObjectName("title")
        center.addWidget(self.heading)
        center.addWidget(self.tool_row)
        center.addWidget(self.beats)
        center.addWidget(self.selection_wrap)
        center.addWidget(self.stage, 1)
        center_wrap = QWidget()
        center_wrap.setLayout(center)

        self.chat_log = QTextEdit()
        self.chat_log.setReadOnly(True)
        self.chat_input = QPlainTextEdit()
        self.chat_input.setPlaceholderText("跟这本书说话")
        self.chat_input.setFixedHeight(90)
        chat_box = QVBoxLayout()
        chat_title = QLabel("对话")
        chat_title.setObjectName("title")
        chat_box.addWidget(chat_title)
        chat_box.addWidget(self.chat_log, 1)
        chat_box.addWidget(self.chat_input)
        chat_box.addWidget(_button("发送", self._send, True))
        chat = QFrame()
        chat.setObjectName("chat")
        chat.setLayout(chat_box)

        split = QSplitter()
        browser_wrap = QWidget()
        browser_layout = QVBoxLayout(browser_wrap)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        browser_layout.addWidget(self.browser)
        split.addWidget(browser_wrap)
        split.addWidget(center_wrap)
        split.addWidget(chat)
        split.setSizes([220, 640, 300])

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(side)
        root.addWidget(split, 1)

        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.flush)
        self.beat_timer = QTimer(self)
        self.beat_timer.setSingleShot(True)
        self.beat_timer.timeout.connect(self._save_beats)
        self._loading = False
        self.show_section("write")
        self._load_chat()

    def provider(self) -> tuple[str, str, str] | None:
        row = self.library.provider()
        if not row["base_url"].strip() or not row["model"].strip() or not row["api_key"].strip():
            QMessageBox.information(self, "模型", "先在书架的「模型」里写上地址、模型名和密钥。")
            return None
        return row["base_url"], row["api_key"], row["model"]

    def show_section(self, name: str) -> None:
        self.flush()
        self.focus = name
        self.focus_id = None
        for key, button in self.nav_buttons.items():
            button.setChecked(key == name)
        writing = name == "write"
        self.tool_row.setVisible(writing)
        self.beats.hide()
        self.selection_wrap.hide()
        if name == "map":
            self.browser.hide()
            self.stage.setCurrentWidget(self.map_label)
            self.heading.setText("故事地图")
            return
        self.browser.show()
        if writing:
            self.browser.setCurrentWidget(self.tree)
            self.stage.setCurrentWidget(self.editor)
            self._load_tree()
            return
        if name in {"outline", "style"}:
            self.browser.hide()
            self.stage.setCurrentWidget(self.doc_editor)
            self.heading.setText("大纲" if name == "outline" else "文风")
            self._loading = True
            self.doc_editor.setPlainText(self.library.document(self.project_id, name))
            self._loading = False
            return
        self.browser.setCurrentWidget(self.entry_list)
        self.stage.setCurrentWidget(self.doc_editor)
        self._load_entries(name)

    def _load_tree(self) -> None:
        self.tree.clear()
        chapters = self.library.chapters(self.project_id)
        nodes: dict[str, QTreeWidgetItem] = {}
        for volume in self.library.volumes(self.project_id):
            node = QTreeWidgetItem([volume["title"]])
            node.setData(0, Qt.UserRole, ("volume", volume["id"]))
            self.tree.addTopLevelItem(node)
            nodes[volume["id"]] = node
        first = None
        for chapter in chapters:
            parent = nodes.get(chapter["volume_id"])
            if parent is None:
                continue
            node = QTreeWidgetItem([chapter["title"]])
            node.setData(0, Qt.UserRole, ("chapter", chapter["id"]))
            parent.addChild(node)
            if first is None:
                first = node
        self.tree.expandAll()
        if first is not None:
            self.tree.setCurrentItem(first)
            self._open_chapter(str(first.data(0, Qt.UserRole)[1]))
        else:
            self.heading.setText(self._title)

    def _load_entries(self, kind: str) -> None:
        labels = {"character": "人物", "location": "地点", "lore": "设定", "plot": "情节", "note": "笔记"}
        self.heading.setText(labels.get(kind, kind))
        self.entry_list.clear()
        add = QListWidgetItem("＋ 新建")
        add.setData(Qt.UserRole, "")
        self.entry_list.addItem(add)
        for row in self.library.entries(self.project_id, kind):
            item = QListWidgetItem(row["name"])
            item.setData(Qt.UserRole, row["id"])
            self.entry_list.addItem(item)
        self._loading = True
        self.doc_editor.setPlainText("")
        self._loading = False

    def _tree_clicked(self, item: QTreeWidgetItem) -> None:
        data = item.data(0, Qt.UserRole)
        if data and data[0] == "chapter":
            self.flush()
            self._open_chapter(str(data[1]))

    def _open_chapter(self, chapter_id: str) -> None:
        row = self.library.chapter(chapter_id)
        if row is None:
            return
        self.focus = "write"
        self.focus_id = chapter_id
        self.heading.setText(row["title"])
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
            name, ok = QInputDialog.getText(self, "新建", "名字")
            if ok and name.strip():
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
        self.heading.setText(row["name"])
        self._loading = True
        self.doc_editor.setPlainText(row["body"])
        self._loading = False

    def _dirty(self) -> None:
        if self._loading:
            return
        self.save_timer.start(900)
        window = self.window()
        if isinstance(window, QMainWindow):
            window.statusBar().showMessage("未保存")

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
        window = self.window()
        if not isinstance(window, QMainWindow):
            return
        if self.focus == "write" and self.focus_id:
            words = count_words_in_html(self.editor.toHtml())
            window.statusBar().showMessage(f"已保存 · 本章 {words} 字")
            return
        window.statusBar().showMessage("已保存")

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
        menu.addAction("新章", self._add_chapter)
        item = self.tree.itemAt(pos)
        if item is not None:
            data = item.data(0, Qt.UserRole)
            if data and data[0] == "chapter":
                menu.addAction("删掉这一章", lambda: self._delete_chapter(str(data[1])))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _add_volume(self) -> None:
        title, ok = QInputDialog.getText(self, "新卷", "卷名")
        if ok:
            self.library.create_volume(self.project_id, title)
            self._load_tree()

    def _add_chapter(self) -> None:
        item = self.tree.currentItem()
        volume_id = None
        if item is not None:
            data = item.data(0, Qt.UserRole)
            if data and data[0] == "volume":
                volume_id = str(data[1])
            elif data and data[0] == "chapter":
                row = self.library.chapter(str(data[1]))
                volume_id = row["volume_id"] if row else None
        if volume_id is None:
            volumes = self.library.volumes(self.project_id)
            volume_id = volumes[0]["id"] if volumes else self.library.create_volume(self.project_id, "第一卷")
        title, ok = QInputDialog.getText(self, "新章", "章名")
        if not ok:
            return
        chapter_id = self.library.create_chapter(self.project_id, volume_id, title)
        self._load_tree()
        self._open_chapter(chapter_id)

    def _delete_chapter(self, chapter_id: str) -> None:
        if QMessageBox.question(self, "删除", "这一章会从本机删掉。") != QMessageBox.Yes:
            return
        self.library.conn.execute("DELETE FROM chapter WHERE id = ?", (chapter_id,))
        self.library.conn.commit()
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
            QMessageBox.warning(self, "改写", message)

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
            QMessageBox.information(self, "检查", shown)

        self._start(Job(work), ok, lambda message: QMessageBox.warning(self, "检查", message))

    def _revisions(self) -> None:
        if not self.focus_id:
            return
        rows = self.library.revisions(self.focus_id)
        dialog = QDialog(self)
        dialog.setWindowTitle("更早的版本")
        listing = QListWidget()
        labels = {"ai": "AI 写入前", "manual": "你保存的", "restore": "恢复前"}
        for row in rows:
            item = QListWidgetItem(f"{labels.get(row['source'], row['source'])}  {row['created_at']}")
            item.setData(Qt.UserRole, row["id"])
            listing.addItem(item)
        if not rows:
            listing.addItem("还没有保存过版本")
        layout = QVBoxLayout(dialog)

        def restore() -> None:
            item = listing.currentItem()
            if item is None or not item.data(Qt.UserRole) or not self.focus_id:
                return
            html = self.library.restore(self.focus_id, str(item.data(Qt.UserRole)))
            if html is not None:
                self._loading = True
                self.editor.setHtml(html)
                self._loading = False
                dialog.accept()

        def remember() -> None:
            if not self.focus_id:
                return
            self.flush()
            self.library.snapshot(self.focus_id, "manual")
            listing.clear()
            for row in self.library.revisions(self.focus_id):
                item = QListWidgetItem(f"{labels.get(row['source'], row['source'])}  {row['created_at']}")
                item.setData(Qt.UserRole, row["id"])
                listing.addItem(item)

        layout.addWidget(listing)
        layout.addWidget(_button("记下这一版", remember))
        layout.addWidget(_button("恢复这一版", restore, True))
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
        dialog = QDialog(self)
        dialog.setWindowTitle("绑定")
        listing = QListWidget()
        for kind, label in (("character", "人物"), ("location", "地点"), ("plot", "情节")):
            for row in self.library.entries(self.project_id, kind):
                item = QListWidgetItem(f"{label} · {row['name']}")
                item.setData(Qt.UserRole, row["id"])
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if row["id"] in chosen else Qt.Unchecked)
                listing.addItem(item)
        layout = QVBoxLayout(dialog)
        layout.addWidget(listing)

        def save() -> None:
            ids = []
            for index in range(listing.count()):
                item = listing.item(index)
                if item.checkState() == Qt.Checked:
                    ids.append(str(item.data(Qt.UserRole)))
            if self.focus_id:
                self.library.set_bindings(self.focus_id, ids)
            dialog.accept()

        layout.addWidget(_button("保存", save, True))
        dialog.exec()

    def _summary(self) -> None:
        if not self.focus_id:
            return
        provider = self.provider()
        if not provider:
            return
        self.flush()
        base, key, model = provider
        plain = self.library.chapter_plain(self.focus_id)
        system = read_prompt("chapter-summary")

        def work() -> str:
            return plain_complete(base, key, model, system, plain)

        def ok(text: str) -> None:
            if self.focus_id:
                self.library.save_summary(self.focus_id, text)
            QMessageBox.information(self, "摘要", text)

        self._start(Job(work), ok, lambda message: QMessageBox.warning(self, "摘要", message))

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
            dialog = QMessageBox(self)
            dialog.setWindowTitle("续写")
            dialog.setText(text[:500] or "没有续上。")
            dialog.setDetailedText(text)
            dialog.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            dialog.button(QMessageBox.Ok).setText("接到章末")
            if dialog.exec() == QMessageBox.Ok and text.strip() and self.focus_id:
                self.library.snapshot(self.focus_id, "ai")
                self.editor.moveCursor(QTextCursor.MoveOperation.End)
                self.editor.insertHtml(plain_to_html(text.strip()))
                self.flush()

        self._start(Job(work), ok, lambda message: QMessageBox.warning(self, "续写", message))

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
        if QMessageBox.question(self, "导入", "要让模型从正文里抽出人物、地点和设定吗？") != QMessageBox.Yes:
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
                QMessageBox.warning(self, "导入", "模型没有返回可用的条目。")
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

        self._start(Job(work), ok, lambda message: QMessageBox.warning(self, "导入", message))

    def _load_chat(self) -> None:
        self.chat_log.clear()
        for row in self.library.messages(self.project_id):
            who = "你" if row["role"] == "user" else "Novel"
            self.chat_log.append(f"{who}\n{row['content']}\n")

    def _send(self) -> None:
        text = self.chat_input.toPlainText().strip()
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
        )
        worker.ask.connect(self._approve)
        worker.reply.connect(self._chat_done)
        worker.failed.connect(self._chat_failed)
        worker.changed.connect(self._open_chapter)
        self._jobs.append(worker)
        worker.start()

    def _approve(self, summary: str) -> None:
        worker = self.sender()
        accepted = QMessageBox.question(self, "写入前确认", summary) == QMessageBox.Yes
        if isinstance(worker, ChatWorker):
            worker.decide(accepted)

    def _chat_failed(self, message: str) -> None:
        self.editor.setReadOnly(False)
        QMessageBox.warning(self, "对话", message)

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


class NovelWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Novel")
        self.resize(1280, 800)
        self.settings = QApplication.instance()
        from PySide6.QtCore import QSettings

        self.store = QSettings("Novel", "Novel")
        self.library: Library | None = None
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.setStatusBar(QStatusBar())
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

    def _enter(self, base: str, token: str, user: dict) -> None:
        user_id = str(user.get("id") or "")
        if not user_id or not token:
            return
        self.store.setValue("auth_url", base)
        self.store.setValue("token", token)
        self.store.setValue("user_id", user_id)
        if self.library:
            self.library.close()
        self.library = Library(library_path(user_id))
        self.projects = ProjectPage(self._open_project, self._logout, self.library)
        self.stack.addWidget(self.projects)
        self.stack.setCurrentWidget(self.projects)
        name = str(user.get("name") or "")
        self.statusBar().showMessage(name)

    def _open_project(self, project_id: str) -> None:
        if self.library is None:
            return
        self.desk = DeskPage(self.library, project_id, self._back)
        self.stack.addWidget(self.desk)
        self.stack.setCurrentWidget(self.desk)

    def _back(self) -> None:
        if hasattr(self, "desk"):
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

    def closeEvent(self, event) -> None:
        if hasattr(self, "desk"):
            self.desk.flush()
        if self.library:
            self.library.close()
        super().closeEvent(event)
