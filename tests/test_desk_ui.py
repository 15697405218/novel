import os
import tempfile
import unittest
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

import desktop.window as window_module
from desktop.store import Library
from desktop.window import DeskPage, _clip_summary
from desktop.wordcount import count_words


QT_HTML = (
    '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" "http://www.w3.org/TR/REC-html40/strict.dtd">'
    "<html><head><style>p, li { white-space: pre-wrap; }</style></head>"
    "<body><p>你好，世界。</p></body></html>"
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


class DeskFlow(unittest.TestCase):
    def test_summary_stays_out_of_book_count_and_chapter_returns(self) -> None:
        _app()
        with tempfile.TemporaryDirectory() as folder:
            library = Library(Path(folder) / "library.sqlite")
            project_id = library.create_project("测试书", "仙侠", target_words=1000)
            volume_id = library.volumes(project_id)[0]["id"]
            first = library.create_chapter(project_id, volume_id, "第一章")
            second = library.create_chapter(project_id, volume_id, "第二章")
            library.save_chapter_content(first, QT_HTML)
            library.save_chapter_content(second, "<p>第二段正文</p>")
            library.save_summary(first, "第一章摘要")
            library.save_summary(second, "第二章摘要")
            desk = DeskPage(library, project_id, lambda: None)
            try:
                self._exercise(desk, library, project_id, first, second, volume_id)
            finally:
                desk.close()
                desk.deleteLater()
                QApplication.processEvents()
                library.close()

    def _exercise(self, desk: DeskPage, library: Library, project_id: str, first: str, second: str, volume_id: str) -> None:
            desk.resize(1100, 760)
            desk.show()
            QApplication.processEvents()

            self.assertEqual(desk.focus_id, first)
            self.assertFalse(desk.direct.isVisible())
            self.assertFalse(desk.direct.isWindow())
            self.assertLessEqual(desk.summary.height(), 96)
            self.assertGreater(desk.editor.height(), desk.summary.height())
            self.assertEqual(desk.summary.toPlainText(), "第一章摘要")
            self.assertIn("正文 4 字", desk.header_words.text())
            self.assertIn("摘要 5 字", desk.header_words.text())
            self.assertEqual(desk.word_label.text(), "全书 9 字 / 1,000")
            self.assertNotIn("white-space", desk.editor.toPlainText())

            desk.summary.setPlainText("改过的摘要，多了几个字")
            QApplication.processEvents()
            self.assertTrue(desk._summary_dirty)
            self.assertEqual(desk.word_label.text(), "全书 9 字 / 1,000")
            self.assertIn(f"摘要 {count_words('改过的摘要，多了几个字')} 字", desk.header_words.text())
            desk._save_summary()
            self.assertEqual(library.chapter(first)["summary"], "改过的摘要，多了几个字")
            self.assertEqual(library.project_word_count(project_id), 9)
            self.assertFalse(desk._summary_dirty)

            desk._open_chapter(second)
            QApplication.processEvents()
            self.assertEqual(desk.summary.toPlainText(), "第二章摘要")
            self.assertIn("正文 5 字", desk.header_words.text())
            self.assertEqual(desk.word_label.text(), "全书 9 字 / 1,000")
            desk.editor.insertPlainText("新增")
            QApplication.processEvents()
            self.assertIn("正文 7 字", desk.header_words.text())
            self.assertEqual(desk.word_label.text(), "全书 11 字 / 1,000")
            self.assertIn("摘要 5 字", desk.header_words.text())
            desk.editor.undo()
            QApplication.processEvents()
            self.assertEqual(desk.word_label.text(), "全书 9 字 / 1,000")

            desk.show_section("outline")
            desk.show_section("write")
            QApplication.processEvents()
            self.assertEqual(desk.focus_id, second)
            self.assertIn("第二段正文", desk.editor.toPlainText())
            self.assertEqual(desk.summary.toPlainText(), "第二章摘要")

            empty = library.create_chapter(project_id, volume_id, "空章")
            desk._open_chapter(empty)
            before = desk.summary.toPlainText()
            calls: list[str] = []
            notices: list[str] = []
            original = desk.provider
            original_alert = window_module.alert

            def boom() -> tuple[str, str, str] | None:
                calls.append("provider")
                return None

            def notice(_parent, _title, body: str) -> None:
                notices.append(body)

            desk.provider = boom
            window_module.alert = notice
            desk._summary()
            window_module.alert = original_alert
            desk.provider = original
            self.assertEqual(calls, [])
            self.assertTrue(notices)
            self.assertEqual(desk.summary.toPlainText(), before)
            self.assertEqual(library.project_word_count(project_id), 9)

            desk.summary.setPlainText("测" * 400)
            QApplication.processEvents()
            self.assertLessEqual(desk.summary.height(), 96)
            self.assertGreater(desk.editor.height(), 200)


class Clip(unittest.TestCase):
    def test_clip_summary_drops_padding(self) -> None:
        self.assertEqual(_clip_summary("  只有事实  ", 20), "只有事实")
        self.assertEqual(_clip_summary("一二三四五六", 4), "一二三四")


if __name__ == "__main__":
    unittest.main()
