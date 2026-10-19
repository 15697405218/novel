import re

HTML_TAG = re.compile(r"<[^>]*>")
HTML_ENTITY = re.compile(r"&[#a-zA-Z0-9]+;")
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]")
WORD = re.compile(r"[A-Za-z0-9]+(?:['’\-]?[A-Za-z0-9]+)*")


def count_words(text: str | None) -> int:
    if not text:
        return 0
    characters = len(CJK.findall(text))
    words = WORD.findall(CJK.sub(" ", text))
    return characters + len(words)


def count_words_in_html(html: str) -> int:
    plain = HTML_ENTITY.sub(" ", HTML_TAG.sub(" ", html or ""))
    return count_words(plain)


def html_to_plain(html: str) -> str:
    text = html or ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(?:p|div|h[1-6]|li|blockquote)>", "\n", text, flags=re.IGNORECASE)
    text = HTML_TAG.sub("", text)
    text = (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&nbsp;", " ")
    )
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def plain_to_html(text: str) -> str:
    blocks = [block.strip() for block in re.split(r"\n{2,}", text.strip()) if block.strip()]
    if not blocks:
        return "<p></p>"
    parts: list[str] = []
    for block in blocks:
        safe = (
            block.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )
        parts.append(f"<p>{safe}</p>")
    return "".join(parts)
