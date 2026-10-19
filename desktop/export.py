from desktop.wordcount import html_to_plain


def markdown(title: str, chapters: list[dict[str, str]]) -> str:
    parts = [f"# {title}", ""]
    for chapter in chapters:
        parts.append(f"## {chapter['volume']}")
        parts.append("")
        parts.append(f"### {chapter['title']}")
        parts.append("")
        parts.append(html_to_plain(chapter["content"]))
        parts.append("")
    return "\n".join(parts).strip() + "\n"


def web_novel(title: str, chapters: list[dict[str, str]]) -> str:
    parts = [title, ""]
    last_volume = ""
    for chapter in chapters:
        if chapter["volume"] != last_volume:
            parts.append(chapter["volume"])
            parts.append("")
            last_volume = chapter["volume"]
        parts.append(chapter["title"])
        parts.append("")
        parts.append(html_to_plain(chapter["content"]))
        parts.append("")
    return "\n".join(parts).strip() + "\n"
