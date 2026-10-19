import re

WHITESPACE = re.compile(r"\s+")
WINDOW = 480
STEP = 320
CHAPTER_CAP = 20_000
MIN_SCORE = 3
LIMIT = 4
STOPS = set("的了是在有和与或及被把")


def _compact(text: str) -> str:
    return WHITESPACE.sub("", text)[:CHAPTER_CAP]


def _grams(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    source = _compact(text)
    for index in range(len(source) - 1):
        gram = source[index : index + 2]
        if gram[0] in STOPS or gram[1] in STOPS:
            continue
        counts[gram] = counts.get(gram, 0) + 1
    return counts


def _score(window: str, wanted: dict[str, int], needle: str) -> int:
    have = _grams(window)
    shared = 0
    for gram, count in wanted.items():
        shared += min(count, have.get(gram, 0))
    if len(needle) >= 2 and needle in _compact(window):
        shared += len(needle)
    return shared


def _best_window(text: str, wanted: dict[str, int], needle: str) -> str | None:
    source = text[:CHAPTER_CAP]
    if not source.strip():
        return None
    best_score = 0
    excerpt = ""
    start = 0
    while start < len(source):
        window = source[start : start + WINDOW]
        score = _score(window, wanted, needle)
        if score > best_score:
            best_score = score
            excerpt = window.strip()
        if start + WINDOW >= len(source):
            break
        start += STEP
    if best_score < MIN_SCORE or not excerpt:
        return None
    return excerpt


def recall_passages(
    chapters: list[dict[str, str]], query: str, exclude_chapter_id: str | None = None
) -> list[dict[str, str]]:
    needle = _compact(query.strip())
    if len(needle) < 2:
        return []
    wanted = _grams(needle)
    ranked: list[tuple[int, dict[str, str]]] = []
    for chapter in chapters:
        if chapter["id"] == exclude_chapter_id:
            continue
        excerpt = _best_window(chapter["text"], wanted, needle)
        if not excerpt:
            continue
        ranked.append(
            (
                _score(excerpt, wanted, needle),
                {"chapterId": chapter["id"], "title": chapter["title"], "excerpt": excerpt},
            )
        )
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in ranked[:LIMIT]]
