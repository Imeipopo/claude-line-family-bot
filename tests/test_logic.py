import json
import unittest
from types import SimpleNamespace as NS

import _setup  # noqa: F401  先設好測試用環境變數與暫存資料夾

import tools_memory
import tools_notes
import usage
from config import USAGE_LOG
from mention import is_mentioned, session_key, strip_mention

BOT = "Ubot"


def text_message(mentionees=None, quoted=None):
    mention = NS(mentionees=mentionees) if mentionees is not None else None
    return NS(mention=mention, quoted_message_id=quoted)


class MentionTest(unittest.TestCase):
    def test_private_chat_always_answers(self):
        self.assertTrue(is_mentioned(text_message(), "user", BOT, []))

    def test_group_needs_mention(self):
        self.assertFalse(is_mentioned(text_message(), "group", BOT, []))
        self.assertTrue(is_mentioned(text_message([NS(user_id=BOT)]), "group", BOT, []))

    def test_mention_all_does_not_crash(self):
        # @All 的 mentionee 沒有 user_id 屬性
        self.assertFalse(is_mentioned(text_message([NS(type="all")]), "group", BOT, []))

    def test_reply_to_bot_counts_as_mention(self):
        self.assertTrue(is_mentioned(text_message(quoted="m1"), "group", BOT, ["m1"]))
        self.assertFalse(is_mentioned(text_message(quoted="m2"), "group", BOT, ["m1"]))

    def test_strip_mention(self):
        self.assertEqual(strip_mention("@小欣 明天會下雨嗎"), "明天會下雨嗎")
        self.assertEqual(strip_mention("明天會下雨嗎"), "明天會下雨嗎")

    def test_session_key(self):
        self.assertEqual(session_key(NS(type="group", group_id="C1")), "group:C1")
        self.assertEqual(session_key(NS(type="user", user_id="U1")), "user:U1")


class NotesTest(unittest.TestCase):
    def test_write_then_read(self):
        tools_notes.run("write_note", {"filename": "todo.md", "content": "買牛奶"}, {})
        self.assertEqual(tools_notes.run("read_note", {"filename": "todo.md"}, {}), "買牛奶")
        self.assertIn("todo.md", tools_notes.run("list_notes", {}, {}))

    def test_path_traversal_blocked(self):
        for bad in ("../.env", "/etc/passwd.md", "../../x.md"):
            with self.assertRaises(ValueError):
                tools_notes.resolve_note_path(bad)

    def test_only_text_files(self):
        with self.assertRaises(ValueError):
            tools_notes.resolve_note_path("run.sh")


class MemoryCleanTest(unittest.TestCase):
    def test_none_means_no_update(self):
        self.assertIsNone(tools_memory.clean_review_output("NONE"))

    def test_keeps_only_heading_and_bullets(self):
        raw = "好的，以下是更新：\n# 自動累積的家裡知識\n- 妹妹對花生過敏\n說明：新增一條\n- 爸爸住台中"
        self.assertEqual(
            tools_memory.clean_review_output(raw),
            "# 自動累積的家裡知識\n\n- 妹妹對花生過敏\n- 爸爸住台中\n",
        )


class CostTest(unittest.TestCase):
    def test_cost_includes_tokens_and_search(self):
        entry = {"model": "claude-sonnet-5", "input": 1_000_000, "output": 100_000,
                 "cache_read": 0, "cache_write": 0, "web_search": 2}
        self.assertAlmostEqual(usage.entry_cost(entry), 2.0 + 1.0 + 0.02)

    def test_total_cost_by_prefix(self):
        lines = [
            {"ts": "2026-11-10T10:00:00+08:00", "model": "claude-sonnet-5", "input": 1_000_000,
             "output": 0, "cache_read": 0, "cache_write": 0},
            {"ts": "2026-10-31T10:00:00+08:00", "model": "claude-sonnet-5", "input": 1_000_000,
             "output": 0, "cache_read": 0, "cache_write": 0},
        ]
        USAGE_LOG.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
        self.assertAlmostEqual(usage.total_cost("2026-11"), 2.0)
        USAGE_LOG.unlink()


if __name__ == "__main__":
    unittest.main()
