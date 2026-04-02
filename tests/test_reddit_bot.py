"""Tests for config loading and bot comment-handling logic.

These tests do not require a live Reddit connection — they mock PRAW objects.
Run with:  python -m pytest tests/ -v
"""

import unittest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Helpers — build lightweight mock PRAW objects
# ---------------------------------------------------------------------------

def _make_author(name: str):
    author = MagicMock()
    author.name = name
    return author


def _make_reply(author_name: str):
    reply = MagicMock()
    reply.author = _make_author(author_name)
    return reply


def _make_comment(body: str, author_name: str = "some_user", replies=None):
    comment = MagicMock()
    comment.id = "abc123"
    comment.body = body
    comment.author = _make_author(author_name)
    comment.subreddit = "testingground4bots"
    comment.replies = replies if replies is not None else []
    comment.refresh = MagicMock()
    return comment


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAlreadyReplied(unittest.TestCase):
    """Unit tests for reddit_bot.already_replied."""

    def setUp(self):
        import reddit_bot
        self.already_replied = reddit_bot.already_replied

    def test_returns_false_when_no_replies(self):
        comment = _make_comment("!hello", replies=[])
        self.assertFalse(self.already_replied(comment, "mybot"))

    def test_returns_true_when_bot_already_replied(self):
        bot_reply = _make_reply("mybot")
        comment = _make_comment("!hello", replies=[bot_reply])
        self.assertTrue(self.already_replied(comment, "mybot"))

    def test_case_insensitive_bot_username(self):
        bot_reply = _make_reply("MyBot")
        comment = _make_comment("!hello", replies=[bot_reply])
        self.assertTrue(self.already_replied(comment, "mybot"))

    def test_returns_false_when_other_user_replied(self):
        other_reply = _make_reply("other_user")
        comment = _make_comment("!hello", replies=[other_reply])
        self.assertFalse(self.already_replied(comment, "mybot"))


class TestHandleComment(unittest.TestCase):
    """Unit tests for reddit_bot.handle_comment."""

    def setUp(self):
        import reddit_bot
        self.handle_comment = reddit_bot.handle_comment

    def test_replies_when_trigger_found(self):
        comment = _make_comment("hey !hello there", replies=[])
        self.handle_comment(comment, "mybot")
        comment.reply.assert_called_once()

    def test_no_reply_when_trigger_absent(self):
        comment = _make_comment("just a normal comment", replies=[])
        self.handle_comment(comment, "mybot")
        comment.reply.assert_not_called()

    def test_no_reply_to_own_comment(self):
        comment = _make_comment("!hello", author_name="mybot", replies=[])
        self.handle_comment(comment, "mybot")
        comment.reply.assert_not_called()

    def test_no_double_reply(self):
        bot_reply = _make_reply("mybot")
        comment = _make_comment("!hello", replies=[bot_reply])
        self.handle_comment(comment, "mybot")
        comment.reply.assert_not_called()

    def test_trigger_is_case_insensitive(self):
        comment = _make_comment("!HELLO world", replies=[])
        self.handle_comment(comment, "mybot")
        comment.reply.assert_called_once()


if __name__ == "__main__":
    unittest.main()
