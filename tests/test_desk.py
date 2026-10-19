import tempfile
import unittest
from pathlib import Path

from auth.security import hash_password, issue_token, read_token, verify_password
from desktop.engine import run_tool
from desktop.export import markdown, web_novel
from desktop.extract import parse_extract
from desktop.recall import recall_passages
from desktop.store import Library, replace_once
from desktop.wordcount import count_words, count_words_in_html, html_to_plain


class Words(unittest.TestCase):
    def test_cjk_and_latin(self) -> None:
        self.assertEqual(count_words("县试将至"), 4)
        self.assertEqual(count_words("hello world"), 2)
        self.assertEqual(count_words("赵阳 said"), 3)
        self.assertEqual(count_words_in_html("<p>县试将至</p>"), 4)

    def test_plain(self) -> None:
        self.assertEqual(html_to_plain("<p>甲</p><p>乙</p>"), "甲\n乙")


class Recall(unittest.TestCase):
    def test_related_passage(self) -> None:
        chapters = [
            {"id": "a", "title": "一", "text": "县试前夜，赵阳还在灯下抄书。"},
            {"id": "b", "title": "二", "text": "山路很静，只有风。"},
        ]
        found = recall_passages(chapters, "灯下抄书", "b")
        self.assertEqual(found[0]["chapterId"], "a")

    def test_skips_open_chapter(self) -> None:
        chapters = [{"id": "a", "title": "一", "text": "县试前夜，赵阳还在灯下抄书。"}]
        self.assertEqual(recall_passages(chapters, "灯下抄书", "a"), [])


class Tokens(unittest.TestCase):
    def test_round_trip(self) -> None:
        salt, digest = hash_password("12345678")
        self.assertTrue(verify_password("12345678", salt, digest))
        self.assertFalse(verify_password("nope", salt, digest))
        token = issue_token("user-1", "secret", ttl_seconds=60)
        self.assertEqual(read_token(token, "secret"), "user-1")
        self.assertIsNone(read_token(token, "other"))
        self.assertIsNone(read_token("not-a-token", "secret"))


class Books(unittest.TestCase):
    def test_chapter_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            library = Library(Path(folder) / "library.sqlite")
            project_id = library.create_project("天命", "仙侠")
            volume_id = library.volumes(project_id)[0]["id"]
            chapter_id = library.create_chapter(project_id, volume_id, "第一章")
            library.save_chapter_content(chapter_id, "<p>县试将至</p>")
            self.assertTrue(library.snapshot(chapter_id, "manual"))
            self.assertEqual(len(library.revisions(chapter_id)), 1)
            self.assertTrue(library.snapshot(chapter_id, "manual"))
            self.assertEqual(len(library.revisions(chapter_id)), 1)
            library.save_chapter_content(chapter_id, "<p>改了</p>", "ai")
            restored = library.restore(chapter_id, library.revisions(chapter_id)[0]["id"])
            self.assertIn("县试将至", restored or "")
            library.close()

    def test_replace_needs_one_match(self) -> None:
        self.assertEqual(replace_once("甲乙甲", "甲", "丙"), None)
        self.assertEqual(replace_once("甲乙", "甲", "丙"), "丙乙")

    def test_direct_write_skips_approval_and_other_writes_ask(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            library = Library(Path(folder) / "library.sqlite")
            project_id = library.create_project("书", "")
            volume_id = library.volumes(project_id)[0]["id"]
            chapter_id = library.create_chapter(project_id, volume_id, "第一章")
            asked: list[str] = []

            def approve(summary: str) -> bool:
                asked.append(summary)
                return False

            text, _reload = run_tool(
                library,
                project_id,
                chapter_id,
                "append_to_chapter",
                {"text": "下一句。"},
                approve,
            )
            self.assertEqual(text, "Appended.")
            self.assertEqual(asked, [])
            self.assertIn("下一句", library.chapter_plain(chapter_id))
            declined, _reload = run_tool(
                library,
                project_id,
                chapter_id,
                "create_entry",
                {"kind": "character", "name": "赵阳"},
                approve,
            )
            self.assertIn("declined", declined)
            self.assertEqual(library.entries(project_id, "character"), [])
            library.close()


class Export(unittest.TestCase):
    def test_shapes(self) -> None:
        chapters = [
            {"volume": "卷一", "title": "第一章", "content": "<p>甲</p>"},
            {"volume": "卷二", "title": "第二章", "content": "<p>乙</p>"},
        ]
        md = markdown("天命", chapters)
        plain = web_novel("天命", chapters)
        self.assertIn("## 卷一", md)
        self.assertIn("### 第一章", md)
        self.assertTrue(plain.startswith("天命"))
        self.assertEqual(plain.count("卷一"), 1)


class Extract(unittest.TestCase):
    def test_fenced_json(self) -> None:
        data = parse_extract('```json\n{"issues":[]}\n```')
        self.assertEqual(data, {"issues": []})
        self.assertIsNone(parse_extract("没有"))


if __name__ == "__main__":
    unittest.main()
