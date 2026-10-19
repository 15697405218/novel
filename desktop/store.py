import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from desktop.wordcount import count_words_in_html, html_to_plain, plain_to_html

SCHEMA = """
CREATE TABLE IF NOT EXISTS project (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    genre TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS volume (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    position INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chapter (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    volume_id TEXT NOT NULL REFERENCES volume(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    summary TEXT,
    word_count INTEGER NOT NULL DEFAULT 0,
    position INTEGER NOT NULL,
    beat_goal TEXT,
    beat_conflict TEXT,
    beat_outcome TEXT,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chapter_revision (
    id TEXT PRIMARY KEY,
    chapter_id TEXT NOT NULL REFERENCES chapter(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entry (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    position INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS binding (
    chapter_id TEXT NOT NULL REFERENCES chapter(id) ON DELETE CASCADE,
    entry_id TEXT NOT NULL REFERENCES entry(id) ON DELETE CASCADE,
    PRIMARY KEY (chapter_id, entry_id)
);
CREATE TABLE IF NOT EXISTS document (
    project_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (project_id, kind)
);
CREATE TABLE IF NOT EXISTS chat_message (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS provider (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    base_url TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    api_key TEXT NOT NULL DEFAULT ''
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return str(uuid.uuid4())


class Library:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA busy_timeout = 5000")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def _one(self, sql: str, args: tuple = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, args).fetchone()

    def _all(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        return list(self.conn.execute(sql, args).fetchall())

    def projects(self) -> list[sqlite3.Row]:
        return self._all("SELECT * FROM project ORDER BY updated_at DESC")

    def project(self, project_id: str) -> sqlite3.Row | None:
        return self._one("SELECT * FROM project WHERE id = ?", (project_id,))

    def create_project(self, title: str, genre: str) -> str:
        project_id = new_id()
        stamp = now()
        volume_id = new_id()
        self.conn.execute(
            "INSERT INTO project (id, title, genre, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (project_id, title.strip() or "未命名", genre.strip(), stamp, stamp),
        )
        self.conn.execute(
            "INSERT INTO volume (id, project_id, title, position, created_at) VALUES (?, ?, ?, 1, ?)",
            (volume_id, project_id, "第一卷", stamp),
        )
        self.conn.execute(
            "INSERT INTO document (project_id, kind, body, updated_at) VALUES (?, 'outline', '', ?), (?, 'style', '', ?)",
            (project_id, stamp, project_id, stamp),
        )
        self.conn.commit()
        return project_id

    def rename_project(self, project_id: str, title: str) -> None:
        self.conn.execute(
            "UPDATE project SET title = ?, updated_at = ? WHERE id = ?",
            (title.strip() or "未命名", now(), project_id),
        )
        self.conn.commit()

    def delete_project(self, project_id: str) -> None:
        self.conn.execute("DELETE FROM project WHERE id = ?", (project_id,))
        self.conn.commit()

    def volumes(self, project_id: str) -> list[sqlite3.Row]:
        return self._all(
            "SELECT * FROM volume WHERE project_id = ? ORDER BY position", (project_id,)
        )

    def create_volume(self, project_id: str, title: str) -> str:
        position = self._one(
            "SELECT COALESCE(MAX(position), 0) + 1 AS n FROM volume WHERE project_id = ?",
            (project_id,),
        )
        volume_id = new_id()
        self.conn.execute(
            "INSERT INTO volume (id, project_id, title, position, created_at) VALUES (?, ?, ?, ?, ?)",
            (volume_id, project_id, title.strip() or f"第{position['n']}卷", position["n"], now()),
        )
        self.conn.commit()
        return volume_id

    def chapters(self, project_id: str) -> list[sqlite3.Row]:
        return self._all(
            """
            SELECT chapter.*, volume.title AS volume_title, volume.position AS volume_position
            FROM chapter JOIN volume ON volume.id = chapter.volume_id
            WHERE chapter.project_id = ?
            ORDER BY volume.position, chapter.position
            """,
            (project_id,),
        )

    def chapter(self, chapter_id: str) -> sqlite3.Row | None:
        return self._one("SELECT * FROM chapter WHERE id = ?", (chapter_id,))

    def create_chapter(self, project_id: str, volume_id: str, title: str) -> str:
        position = self._one(
            "SELECT COALESCE(MAX(position), 0) + 1 AS n FROM chapter WHERE volume_id = ?",
            (volume_id,),
        )
        chapter_id = new_id()
        label = title.strip() or f"第{position['n']}章"
        self.conn.execute(
            """
            INSERT INTO chapter (
                id, project_id, volume_id, title, content, word_count, position, updated_at
            ) VALUES (?, ?, ?, ?, '', 0, ?, ?)
            """,
            (chapter_id, project_id, volume_id, label, position["n"], now()),
        )
        self.conn.commit()
        return chapter_id

    def save_chapter_content(self, chapter_id: str, html: str, source: str | None = None) -> None:
        if source:
            self.snapshot(chapter_id, source)
        words = count_words_in_html(html)
        self.conn.execute(
            "UPDATE chapter SET content = ?, word_count = ?, updated_at = ? WHERE id = ?",
            (html, words, now(), chapter_id),
        )
        self._refresh_project_words(chapter_id)
        self.conn.commit()

    def _refresh_project_words(self, chapter_id: str) -> None:
        row = self.chapter(chapter_id)
        if row is None:
            return
        self.conn.execute(
            "UPDATE project SET updated_at = ? WHERE id = ?",
            (now(), row["project_id"]),
        )

    def project_word_count(self, project_id: str) -> int:
        row = self._one(
            "SELECT COALESCE(SUM(word_count), 0) AS n FROM chapter WHERE project_id = ?",
            (project_id,),
        )
        return int(row["n"]) if row else 0

    def save_summary(self, chapter_id: str, summary: str) -> None:
        self.conn.execute(
            "UPDATE chapter SET summary = ?, updated_at = ? WHERE id = ?",
            (summary.strip(), now(), chapter_id),
        )
        self.conn.commit()

    def save_beats(self, chapter_id: str, goal: str, conflict: str, outcome: str) -> None:
        self.conn.execute(
            """
            UPDATE chapter
            SET beat_goal = ?, beat_conflict = ?, beat_outcome = ?
            WHERE id = ?
            """,
            (goal, conflict, outcome, chapter_id),
        )
        self.conn.commit()

    def snapshot(self, chapter_id: str, source: str) -> bool:
        row = self.chapter(chapter_id)
        if row is None:
            return False
        latest = self._one(
            "SELECT content FROM chapter_revision WHERE chapter_id = ? ORDER BY created_at DESC LIMIT 1",
            (chapter_id,),
        )
        if latest is not None and latest["content"] == row["content"]:
            return True
        self.conn.execute(
            """
            INSERT INTO chapter_revision (id, chapter_id, title, content, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (new_id(), chapter_id, row["title"], row["content"], source, now()),
        )
        stale = self._all(
            "SELECT id FROM chapter_revision WHERE chapter_id = ? ORDER BY created_at DESC",
            (chapter_id,),
        )
        extra = [item["id"] for item in stale[30:]]
        if extra:
            marks = ",".join("?" for _ in extra)
            self.conn.execute(f"DELETE FROM chapter_revision WHERE id IN ({marks})", extra)
        self.conn.commit()
        return True

    def revisions(self, chapter_id: str) -> list[sqlite3.Row]:
        return self._all(
            "SELECT id, title, source, created_at FROM chapter_revision WHERE chapter_id = ? ORDER BY created_at DESC",
            (chapter_id,),
        )

    def restore(self, chapter_id: str, revision_id: str) -> str | None:
        revision = self._one(
            "SELECT content FROM chapter_revision WHERE id = ? AND chapter_id = ?",
            (revision_id, chapter_id),
        )
        if revision is None:
            return None
        self.snapshot(chapter_id, "restore")
        self.save_chapter_content(chapter_id, revision["content"])
        return revision["content"]

    def entries(self, project_id: str, kind: str) -> list[sqlite3.Row]:
        return self._all(
            "SELECT * FROM entry WHERE project_id = ? AND kind = ? ORDER BY position, name",
            (project_id, kind),
        )

    def entry(self, entry_id: str) -> sqlite3.Row | None:
        return self._one("SELECT * FROM entry WHERE id = ?", (entry_id,))

    def create_entry(self, project_id: str, kind: str, name: str, body: str = "") -> str:
        position = self._one(
            "SELECT COALESCE(MAX(position), 0) + 1 AS n FROM entry WHERE project_id = ? AND kind = ?",
            (project_id, kind),
        )
        entry_id = new_id()
        self.conn.execute(
            """
            INSERT INTO entry (id, project_id, kind, name, body, position, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (entry_id, project_id, kind, name.strip() or "未命名", body, position["n"], now()),
        )
        self.conn.commit()
        return entry_id

    def save_entry(self, entry_id: str, name: str, body: str) -> None:
        self.conn.execute(
            "UPDATE entry SET name = ?, body = ?, updated_at = ? WHERE id = ?",
            (name.strip() or "未命名", body, now(), entry_id),
        )
        self.conn.commit()

    def delete_entry(self, entry_id: str) -> None:
        self.conn.execute("DELETE FROM entry WHERE id = ?", (entry_id,))
        self.conn.commit()

    def append_entry(self, entry_id: str, text: str) -> None:
        row = self.entry(entry_id)
        if row is None:
            return
        body = row["body"].rstrip()
        addition = text.strip()
        joined = f"{body}\n\n{addition}".strip() if body else addition
        self.save_entry(entry_id, row["name"], joined)

    def bindings(self, chapter_id: str) -> list[str]:
        rows = self._all("SELECT entry_id FROM binding WHERE chapter_id = ?", (chapter_id,))
        return [row["entry_id"] for row in rows]

    def set_bindings(self, chapter_id: str, entry_ids: list[str]) -> None:
        self.conn.execute("DELETE FROM binding WHERE chapter_id = ?", (chapter_id,))
        for entry_id in entry_ids:
            self.conn.execute(
                "INSERT OR IGNORE INTO binding (chapter_id, entry_id) VALUES (?, ?)",
                (chapter_id, entry_id),
            )
        self.conn.commit()

    def document(self, project_id: str, kind: str) -> str:
        row = self._one(
            "SELECT body FROM document WHERE project_id = ? AND kind = ?", (project_id, kind)
        )
        return row["body"] if row else ""

    def save_document(self, project_id: str, kind: str, body: str) -> None:
        self.conn.execute(
            """
            INSERT INTO document (project_id, kind, body, updated_at) VALUES (?, ?, ?, ?)
            ON CONFLICT(project_id, kind) DO UPDATE SET body = excluded.body, updated_at = excluded.updated_at
            """,
            (project_id, kind, body, now()),
        )
        self.conn.commit()

    def append_document(self, project_id: str, kind: str, text: str) -> None:
        current = self.document(project_id, kind).rstrip()
        addition = text.strip()
        joined = f"{current}\n\n{addition}".strip() if current else addition
        self.save_document(project_id, kind, joined)

    def messages(self, project_id: str) -> list[sqlite3.Row]:
        return self._all(
            "SELECT * FROM chat_message WHERE project_id = ? ORDER BY created_at", (project_id,)
        )

    def add_message(self, project_id: str, role: str, content: str) -> None:
        self.conn.execute(
            "INSERT INTO chat_message (id, project_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (new_id(), project_id, role, content, now()),
        )
        self.conn.commit()

    def provider(self) -> sqlite3.Row:
        row = self._one("SELECT * FROM provider WHERE id = 1")
        if row is None:
            self.conn.execute(
                "INSERT INTO provider (id, base_url, model, api_key) VALUES (1, 'https://api.deepseek.com', 'deepseek-chat', '')"
            )
            self.conn.commit()
            row = self._one("SELECT * FROM provider WHERE id = 1")
        return row

    def save_provider(self, base_url: str, model: str, api_key: str) -> None:
        self.provider()
        self.conn.execute(
            "UPDATE provider SET base_url = ?, model = ?, api_key = ? WHERE id = 1",
            (base_url.strip(), model.strip(), api_key.strip()),
        )
        self.conn.commit()

    def chapter_plain(self, chapter_id: str) -> str:
        row = self.chapter(chapter_id)
        if row is None:
            return ""
        return html_to_plain(row["content"])

    def search_text(self, project_id: str, query: str) -> list[str]:
        needle = query.strip()
        if not needle:
            return []
        hits: list[str] = []
        for chapter in self.chapters(project_id):
            plain = html_to_plain(chapter["content"])
            index = plain.find(needle)
            if index >= 0:
                start = max(0, index - 40)
                hits.append(f"{chapter['title']}: {plain[start:index + len(needle) + 80]}")
        for note in self.entries(project_id, "note"):
            index = note["body"].find(needle)
            if index >= 0:
                hits.append(f"笔记 {note['name']}: {note['body'][max(0, index - 40):index + 80]}")
        return hits[:8]

    def recall(self, project_id: str, query: str, exclude: str | None) -> list[dict[str, str]]:
        from desktop.recall import recall_passages

        chapters = [
            {"id": row["id"], "title": row["title"], "text": html_to_plain(row["content"])}
            for row in self.chapters(project_id)
        ]
        return recall_passages(chapters, query, exclude)

    def manuscript(self, project_id: str) -> tuple[str, list[dict[str, str]]]:
        project = self.project(project_id)
        title = project["title"] if project else "文稿"
        chapters = []
        for row in self.chapters(project_id):
            chapters.append(
                {
                    "title": row["title"],
                    "volume": row["volume_title"],
                    "content": row["content"],
                }
            )
        return title, chapters


def replace_once(text: str, find: str, replace: str) -> str | None:
    if not find or text.count(find) != 1:
        return None
    return text.replace(find, replace, 1)


def append_html(html: str, prose: str) -> str:
    return (html or "") + plain_to_html(prose)
