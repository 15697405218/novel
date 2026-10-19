"""Background model calls. The window thread only draws and asks for approval."""

import threading

from PySide6.QtCore import QThread, Signal

from desktop.engine import chat_turn
from desktop.store import Library


class Job(QThread):
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, work):
        super().__init__()
        self._work = work

    def run(self) -> None:
        try:
            self.done.emit(self._work())
        except Exception as exc:
            self.failed.emit(str(exc))


class ChatWorker(QThread):
    reply = Signal(str)
    failed = Signal(str)
    ask = Signal(str)
    changed = Signal(str)

    def __init__(self, path, project_id: str, focus: str, focus_id: str | None, base: str, key: str, model: str):
        super().__init__()
        self._path = path
        self._project_id = project_id
        self._focus = focus
        self._focus_id = focus_id
        self._base = base
        self._key = key
        self._model = model
        self._ready = threading.Event()
        self._decision = False

    def decide(self, accepted: bool) -> None:
        self._decision = accepted
        self._ready.set()

    def _approve(self, summary: str) -> bool:
        self._decision = False
        self._ready.clear()
        self.ask.emit(summary)
        self._ready.wait()
        return self._decision

    def run(self) -> None:
        library = Library(self._path)
        try:
            history = [
                {"role": row["role"], "content": row["content"]}
                for row in library.messages(self._project_id)
                if row["role"] in {"user", "assistant"}
            ]
            text, reload_id = chat_turn(
                library,
                self._project_id,
                self._focus,
                self._focus_id,
                history,
                self._base,
                self._key,
                self._model,
                self._approve,
            )
            library.add_message(self._project_id, "assistant", text or "（没有回复）")
            self.reply.emit(text or "（没有回复）")
            if reload_id:
                self.changed.emit(reload_id)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            library.close()
