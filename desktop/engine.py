"""OpenAI-compatible chat and the manuscript tools. Calls go to the author's provider."""

import json
from pathlib import Path
from typing import Callable

import httpx

from desktop.store import Library, append_html, replace_once
from desktop.wordcount import html_to_plain

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "prompts"
WRITE_TOOLS = {
    "append_to_chapter",
    "replace_in_chapter",
    "append_to_outline",
    "replace_in_outline",
    "append_to_entry",
    "replace_in_entry",
    "create_entry",
    "delete_entry",
}
DIRECT_CHAPTER = {"append_to_chapter", "replace_in_chapter"}
KINDS = {"character", "location", "lore", "plot", "note"}
KIND_ID = {
    "character": "characterId",
    "location": "locationId",
    "lore": "loreId",
    "plot": "plotId",
    "note": "noteId",
}


def read_prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8").strip()


def _prop(description: str) -> dict[str, str]:
    return {"type": "string", "description": description}


def _tool(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    parameters: dict = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        parameters["required"] = required
    return {"type": "function", "function": {"name": name, "description": description, "parameters": parameters}}


def manuscript_tools() -> list[dict]:
    chapter_id = {"chapterId": _prop("Chapter id from list_chapters. Omit for the open chapter.")}
    return [
        _tool("list_chapters", "List this book's chapters in reading order. Does not return chapter text.", {}),
        _tool("read_chapter", "Read one chapter's plain text and stored summary.", chapter_id),
        _tool("list_characters", "List this book's characters by id and name.", {}),
        _tool("read_character", "Read one character.", {"characterId": _prop("Character id.")}, ["characterId"]),
        _tool("list_locations", "List this book's locations by id and name.", {}),
        _tool("read_location", "Read one location.", {"locationId": _prop("Location id.")}, ["locationId"]),
        _tool("list_plots", "List this book's plot threads by id and title.", {}),
        _tool("read_plot", "Read one plot thread.", {"plotId": _prop("Plot id.")}, ["plotId"]),
        _tool("list_lore", "List worldbuilding entries by id and name.", {}),
        _tool("read_lore", "Read one worldbuilding entry.", {"loreId": _prop("Lore id.")}, ["loreId"]),
        _tool("read_outline", "Read this book's outline.", {}),
        _tool("list_notes", "List notes by id and title.", {}),
        _tool("read_note", "Read one note.", {"noteId": _prop("Note id.")}, ["noteId"]),
        _tool("recall", "Find related passages when the wording may differ.", {"query": _prop("What to look for.")}, ["query"]),
        _tool("search_text", "Search chapter text and notes for an exact phrase.", {"query": _prop("Exact phrase.")}, ["query"]),
        _tool(
            "append_to_chapter",
            "Append prose to a chapter. Omit chapterId for the open chapter.",
            {**chapter_id, "text": _prop("Plain prose. Blank lines start paragraphs.")},
            ["text"],
        ),
        _tool("append_to_outline", "Append text to the outline after confirmation.", {"text": _prop("Plain text.")}, ["text"]),
        _tool(
            "replace_in_outline",
            "Replace one unique phrase in the outline after confirmation.",
            {"find": _prop("Exact phrase that occurs once."), "replace": _prop("Replacement.")},
            ["find", "replace"],
        ),
        _tool(
            "append_to_entry",
            "Append text to one character, location, lore entry, plot thread, or note.",
            {
                "kind": _prop("character, location, lore, plot, or note."),
                "id": _prop("Id from the matching list tool."),
                "text": _prop("Plain text to append."),
            },
            ["kind", "id", "text"],
        ),
        _tool(
            "replace_in_entry",
            "Replace one unique phrase in an entry after confirmation.",
            {
                "kind": _prop("character, location, lore, plot, or note."),
                "id": _prop("Id from the matching list tool."),
                "find": _prop("Exact phrase that occurs once."),
                "replace": _prop("Replacement."),
            },
            ["kind", "id", "find", "replace"],
        ),
        _tool(
            "create_entry",
            "Create an entry after confirmation.",
            {
                "kind": _prop("character, location, lore, plot, or note."),
                "name": _prop("Name or title."),
                "text": _prop("Description. May be empty."),
            },
            ["kind", "name"],
        ),
        _tool(
            "delete_entry",
            "Delete an entry after confirmation.",
            {"kind": _prop("character, location, lore, plot, or note."), "id": _prop("Id from the matching list tool.")},
            ["kind", "id"],
        ),
        _tool(
            "replace_in_chapter",
            "Replace one unique phrase in a chapter.",
            {**chapter_id, "find": _prop("Exact phrase that occurs once."), "replace": _prop("Replacement prose.")},
            ["find", "replace"],
        ),
    ]


def _clip(text: str, limit: int = 12_000) -> str:
    body = text.strip()
    if len(body) <= limit:
        return body
    return body[:limit] + "\n…"


def surface(store: Library, project_id: str, focus: str, focus_id: str | None) -> str:
    project = store.project(project_id)
    title = project["title"] if project else "未命名"
    if focus == "outline":
        return f"BOOK: {title}\n\nOPEN DOCUMENT: outline\n{_clip(store.document(project_id, 'outline'))}"
    if focus == "style":
        return f"BOOK: {title}\n\nOPEN DOCUMENT: style\n{_clip(store.document(project_id, 'style'))}"
    if focus in KINDS and focus_id:
        row = store.entry(focus_id)
        if row is None:
            return f"BOOK: {title}"
        return f"BOOK: {title}\n\nOPEN DOCUMENT: {row['kind']} {row['name']}\n{_clip(row['body'])}"
    if focus != "chapter" or not focus_id:
        return f"BOOK: {title}"
    chapter = store.chapter(focus_id)
    if chapter is None:
        return f"BOOK: {title}"
    blocks = [f"BOOK: {title}", f"CURRENT CHAPTER: {chapter['title']}", _clip(html_to_plain(chapter["content"]))]
    style = store.document(project_id, "style").strip()
    if style:
        blocks.append(f"STYLE\n{_clip(style, 4000)}")
    beats = [
        ("Goal", chapter["beat_goal"]),
        ("Conflict", chapter["beat_conflict"]),
        ("Outcome", chapter["beat_outcome"]),
    ]
    beat_lines = [f"{label}: {value.strip()}" for label, value in beats if value and value.strip()]
    if beat_lines:
        blocks.append("CHAPTER BEAT\n" + "\n".join(beat_lines))
    outline = store.document(project_id, "outline").strip()
    if outline:
        blocks.append(f"OUTLINE\n{_clip(outline, 6000)}")
    bound = set(store.bindings(focus_id))
    for kind, label in (
        ("character", "CHARACTERS"),
        ("location", "LOCATIONS"),
        ("plot", "PLOT THREADS"),
    ):
        lines = []
        for row in store.entries(project_id, kind):
            if row["id"] in bound:
                lines.append(f"{row['name']}\n{_clip(row['body'], 1500)}")
        if lines:
            blocks.append(label + "\n" + "\n\n".join(lines))
    lore_lines = []
    for row in store.entries(project_id, "lore")[:40]:
        lore_lines.append(f"{row['name']}\n{_clip(row['body'], 800)}")
    if lore_lines:
        blocks.append("WORLD\n" + "\n\n".join(lore_lines))
    summaries = []
    for row in store.chapters(project_id):
        if row["id"] == focus_id or not row["summary"]:
            continue
        summaries.append(f"{row['title']}: {row['summary']}")
    if summaries:
        blocks.append("CHAPTER SUMMARIES\n" + "\n".join(summaries[:40]))
    return "\n\n".join(blocks)


def _list(store: Library, project_id: str, kind: str) -> str:
    rows = store.entries(project_id, kind)
    if not rows:
        return "(none)"
    return "\n".join(f"{row['id']}  {row['name']}" for row in rows)


def _read_entry(store: Library, entry_id: str) -> str:
    row = store.entry(entry_id)
    if row is None:
        return "Not found."
    return f"{row['name']}\n{row['body']}"


def _chapter_id(store: Library, project_id: str, args: dict, open_id: str | None) -> str | None:
    chapter_id = str(args.get("chapterId") or open_id or "")
    row = store.chapter(chapter_id) if chapter_id else None
    if row is None or row["project_id"] != project_id:
        return None
    return chapter_id


def run_tool(
    store: Library,
    project_id: str,
    open_chapter_id: str | None,
    name: str,
    args: dict,
    approve: Callable[[str], bool],
) -> tuple[str, str | None]:
    """Return tool text and the chapter id to reload, if the open chapter changed."""
    if name == "list_chapters":
        rows = store.chapters(project_id)
        if not rows:
            return "(none)", None
        return "\n".join(f"{row['id']}  {row['volume_title']} / {row['title']}" for row in rows), None
    if name == "read_chapter":
        chapter_id = _chapter_id(store, project_id, args, open_chapter_id)
        if not chapter_id:
            return "Chapter not found.", None
        row = store.chapter(chapter_id)
        summary = row["summary"] or "(no summary)"
        return f"{row['title']}\nSummary: {summary}\n\n{html_to_plain(row['content'])}", None
    if name == "list_characters":
        return _list(store, project_id, "character"), None
    if name == "read_character":
        return _read_entry(store, str(args.get("characterId") or "")), None
    if name == "list_locations":
        return _list(store, project_id, "location"), None
    if name == "read_location":
        return _read_entry(store, str(args.get("locationId") or "")), None
    if name == "list_plots":
        return _list(store, project_id, "plot"), None
    if name == "read_plot":
        return _read_entry(store, str(args.get("plotId") or "")), None
    if name == "list_lore":
        return _list(store, project_id, "lore"), None
    if name == "read_lore":
        return _read_entry(store, str(args.get("loreId") or "")), None
    if name == "read_outline":
        return store.document(project_id, "outline") or "(empty)", None
    if name == "list_notes":
        return _list(store, project_id, "note"), None
    if name == "read_note":
        return _read_entry(store, str(args.get("noteId") or "")), None
    if name == "recall":
        passages = store.recall(project_id, str(args.get("query") or ""), open_chapter_id)
        if not passages:
            return "No related passage.", None
        return "\n\n".join(f"{item['title']}\n{item['excerpt']}" for item in passages), None
    if name == "search_text":
        hits = store.search_text(project_id, str(args.get("query") or ""))
        return "\n".join(hits) if hits else "No exact match.", None
    if name not in WRITE_TOOLS:
        return "Unknown tool.", None

    direct = name in DIRECT_CHAPTER and _chapter_id(store, project_id, args, open_chapter_id) == open_chapter_id
    if name in {"create_entry", "delete_entry"} or not direct:
        if not approve(f"{name}: {json.dumps(args, ensure_ascii=False)[:500]}"):
            return "The writer declined. Leave the book unchanged.", None

    if name == "append_to_chapter":
        chapter_id = _chapter_id(store, project_id, args, open_chapter_id)
        if not chapter_id:
            return "Chapter not found.", None
        row = store.chapter(chapter_id)
        store.save_chapter_content(chapter_id, append_html(row["content"], str(args.get("text") or "")), "ai")
        return "Appended.", chapter_id if chapter_id == open_chapter_id else None
    if name == "replace_in_chapter":
        chapter_id = _chapter_id(store, project_id, args, open_chapter_id)
        if not chapter_id:
            return "Chapter not found.", None
        plain = store.chapter_plain(chapter_id)
        replaced = replace_once(plain, str(args.get("find") or ""), str(args.get("replace") or ""))
        if replaced is None:
            return "The phrase was not unique, so nothing was saved.", None
        from desktop.wordcount import plain_to_html

        store.save_chapter_content(chapter_id, plain_to_html(replaced), "ai")
        return "Replaced.", chapter_id if chapter_id == open_chapter_id else None
    if name == "append_to_outline":
        store.append_document(project_id, "outline", str(args.get("text") or ""))
        return "Appended.", None
    if name == "replace_in_outline":
        current = store.document(project_id, "outline")
        replaced = replace_once(current, str(args.get("find") or ""), str(args.get("replace") or ""))
        if replaced is None:
            return "The phrase was not unique, so nothing was saved.", None
        store.save_document(project_id, "outline", replaced)
        return "Replaced.", None
    kind = str(args.get("kind") or "")
    if kind not in KINDS and name in {"append_to_entry", "replace_in_entry", "create_entry", "delete_entry"}:
        return "Unknown kind.", None
    if name == "create_entry":
        store.create_entry(project_id, kind, str(args.get("name") or ""), str(args.get("text") or ""))
        return "Created.", None
    entry_id = str(args.get("id") or "")
    row = store.entry(entry_id)
    if row is None or row["project_id"] != project_id or row["kind"] != kind:
        return "Entry not found.", None
    if name == "delete_entry":
        store.delete_entry(entry_id)
        return "Deleted.", None
    if name == "append_to_entry":
        store.append_entry(entry_id, str(args.get("text") or ""))
        return "Appended.", None
    replaced = replace_once(row["body"], str(args.get("find") or ""), str(args.get("replace") or ""))
    if replaced is None:
        return "The phrase was not unique, so nothing was saved.", None
    store.save_entry(entry_id, row["name"], replaced)
    return "Replaced.", None


def endpoint(base_url: str) -> str:
    url = base_url.strip().rstrip("/")
    if url.endswith("/chat/completions"):
        return url
    return f"{url}/chat/completions"


def complete(base_url: str, api_key: str, model: str, messages: list[dict], tools: list[dict] | None = None) -> dict:
    payload: dict = {"model": model, "messages": messages, "temperature": 0.7}
    if tools:
        payload["tools"] = tools
    response = httpx.post(
        endpoint(base_url),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    choice = data["choices"][0]["message"]
    return choice


def chat_turn(
    store: Library,
    project_id: str,
    focus: str,
    focus_id: str | None,
    history: list[dict[str, str]],
    base_url: str,
    api_key: str,
    model: str,
    approve: Callable[[str], bool],
) -> tuple[str, str | None]:
    messages: list[dict] = [
        {"role": "system", "content": read_prompt("chat-system") + "\n\n" + read_prompt("chat-tools")},
        {"role": "system", "content": "CONTEXT UPDATE\n" + surface(store, project_id, focus, focus_id)},
    ]
    messages.extend(folded_history(store, project_id, history, base_url, api_key, model))
    tools = manuscript_tools()
    reload_id = None
    for _ in range(6):
        message = complete(base_url, api_key, model, messages, tools)
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            return str(message.get("content") or "").strip(), reload_id
        messages.append(message)
        for call in tool_calls:
            fn = call.get("function") or {}
            name = str(fn.get("name") or "")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            text, changed = run_tool(store, project_id, focus_id if focus == "chapter" else None, name, args, approve)
            if changed:
                reload_id = changed
            messages.append({"role": "tool", "tool_call_id": call.get("id"), "content": text})
    return "这一轮工具调用已经够多了，先停在这里。", reload_id


def folded_history(
    store: Library,
    project_id: str,
    history: list[dict[str, str]],
    base_url: str,
    api_key: str,
    model: str,
) -> list[dict[str, str]]:
    if len(history) <= 16:
        return history
    saved_count = 0
    saved_text = ""
    raw = store.document(project_id, "chat_fold")
    if raw.startswith("{"):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}
        if isinstance(data, dict):
            saved_count = int(data.get("count") or 0)
            saved_text = str(data.get("text") or "")
    head = history[:-8]
    if saved_count < len(head):
        chunk = head[saved_count:]
        material = saved_text + "\n" + "\n".join(f"{item['role']}: {item['content']}" for item in chunk)
        saved_text = plain_complete(
            base_url, api_key, model, read_prompt("conversation-summary"), material[:12_000]
        )
        saved_count = len(head)
        store.save_document(
            project_id,
            "chat_fold",
            json.dumps({"count": saved_count, "text": saved_text}, ensure_ascii=False),
        )
    folded: list[dict[str, str]] = []
    if saved_text:
        folded.append({"role": "user", "content": "Earlier conversation, compressed:\n" + saved_text})
    folded.extend(history[-8:])
    return folded


def plain_complete(base_url: str, api_key: str, model: str, system: str, user: str) -> str:
    message = complete(
        base_url,
        api_key,
        model,
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return str(message.get("content") or "").strip()
