"""Conversation State Management Tests — Threads, topics, context windows."""

import pytest
from gateway.conversation import (
    ConversationManager,
    ConversationMessage,
    ConversationThread,
    detect_topic_change,
    summarize_messages,
    _extract_keywords,
)


def _mgr(**kw):
    return ConversationManager(
        clock=kw.pop("clock", lambda: "2026-04-07T12:00:00Z"),
        **kw,
    )


# ── Basic message flow ─────────────────────────────────────────

class TestBasicFlow:
    def test_add_message_creates_session(self):
        mgr = _mgr()
        thread = mgr.add_message(
            "whatsapp", "+1234", "t1", "user1",
            role="user", content="Hello",
        )
        assert thread.message_count == 1
        assert mgr.session_count == 1

    def test_messages_accumulate(self):
        mgr = _mgr()
        mgr.add_message("wa", "+1", "t1", "u1", role="user", content="Q1")
        mgr.add_message("wa", "+1", "t1", "u1", role="assistant", content="A1")
        mgr.add_message("wa", "+1", "t1", "u1", role="user", content="Q2")
        ctx = mgr.get_context_messages("wa", "+1", "t1")
        assert len(ctx) == 3
        assert ctx[0]["role"] == "user"
        assert ctx[2]["content"] == "Q2"

    def test_context_messages_format(self):
        mgr = _mgr()
        mgr.add_message("wa", "+1", "t1", "u1", role="user", content="Hi")
        ctx = mgr.get_context_messages("wa", "+1", "t1")
        assert isinstance(ctx, list)
        assert ctx[0] == {"role": "user", "content": "Hi"}

    def test_empty_context(self):
        mgr = _mgr()
        ctx = mgr.get_context_messages("wa", "+1", "t1")
        assert ctx == []


# ── Thread isolation ───────────────────────────────────────────

class TestThreadIsolation:
    def test_separate_threads(self):
        mgr = _mgr()
        mgr.add_message("wa", "+1", "t1", "u1", role="user", content="Main topic", thread_id="main")
        mgr.add_message("wa", "+1", "t1", "u1", role="user", content="Side topic", thread_id="thread-2")
        main_ctx = mgr.get_context_messages("wa", "+1", "t1", thread_id="main")
        side_ctx = mgr.get_context_messages("wa", "+1", "t1", thread_id="thread-2")
        assert len(main_ctx) == 1
        assert len(side_ctx) == 1
        assert main_ctx[0]["content"] == "Main topic"
        assert side_ctx[0]["content"] == "Side topic"

    def test_start_thread(self):
        mgr = _mgr()
        mgr.add_message("wa", "+1", "t1", "u1", role="user", content="Hello")
        thread = mgr.start_thread("wa", "+1", "t1", thread_id="new-thread", topic="billing")
        assert thread is not None
        assert thread.topic == "billing"
        session = mgr.get_session("wa", "+1", "t1")
        assert session.active_thread_id == "new-thread"

    def test_start_thread_no_session(self):
        mgr = _mgr()
        assert mgr.start_thread("wa", "+1", "t1", thread_id="t") is None

    def test_thread_count(self):
        mgr = _mgr()
        mgr.add_message("wa", "+1", "t1", "u1", role="user", content="A", thread_id="t1")
        mgr.add_message("wa", "+1", "t1", "u1", role="user", content="B", thread_id="t2")
        mgr.add_message("wa", "+1", "t1", "u1", role="user", content="C", thread_id="t3")
        session = mgr.get_session("wa", "+1", "t1")
        assert session.thread_count == 3

    def test_max_threads_eviction(self):
        mgr = _mgr()
        mgr.MAX_THREADS_PER_SESSION = 3
        for i in range(5):
            mgr.add_message("wa", "+1", "t1", "u1", role="user", content=f"T{i}", thread_id=f"t-{i}")
        session = mgr.get_session("wa", "+1", "t1")
        assert session.thread_count <= 3


# ── Context compaction ─────────────────────────────────────────

class TestContextCompaction:
    def test_messages_compacted_at_limit(self):
        mgr = _mgr(max_messages_per_thread=5)
        for i in range(10):
            mgr.add_message("wa", "+1", "t1", "u1", role="user", content=f"Message {i}")
        ctx = mgr.get_context_messages("wa", "+1", "t1")
        # Should have summary + 5 recent messages
        assert len(ctx) <= 6
        assert ctx[0]["role"] == "system"  # Summary
        assert "Previous conversation summary" in ctx[0]["content"]

    def test_summary_preserved_in_context(self):
        mgr = _mgr(max_messages_per_thread=3)
        mgr.add_message("wa", "+1", "t1", "u1", role="user", content="What is machine learning?")
        mgr.add_message("wa", "+1", "t1", "u1", role="assistant", content="ML is a subset of AI")
        mgr.add_message("wa", "+1", "t1", "u1", role="user", content="Tell me more about neural networks")
        mgr.add_message("wa", "+1", "t1", "u1", role="assistant", content="Neural networks are...")
        mgr.add_message("wa", "+1", "t1", "u1", role="user", content="How do transformers work?")
        ctx = mgr.get_context_messages("wa", "+1", "t1")
        summary_msg = [m for m in ctx if m["role"] == "system"]
        assert len(summary_msg) <= 1


# ── Topic detection ────────────────────────────────────────────

class TestTopicDetection:
    def test_same_topic_not_detected(self):
        msgs = [
            ConversationMessage(role="user", content="What is my account balance today?", timestamp="t1"),
            ConversationMessage(role="assistant", content="Your account balance is $100 today", timestamp="t2"),
        ]
        assert detect_topic_change(msgs, "Can you show my account balance history?") is False

    def test_topic_change_detected(self):
        msgs = [
            ConversationMessage(role="user", content="What is my account balance?", timestamp="t1"),
            ConversationMessage(role="assistant", content="Your balance is $100", timestamp="t2"),
        ]
        assert detect_topic_change(msgs, "What is the weather in Tokyo today?") is True

    def test_first_message_no_topic_change(self):
        assert detect_topic_change([], "Hello world") is False

    def test_topic_change_increments_counter(self):
        mgr = _mgr()
        # Build context about finance
        mgr.add_message("wa", "+1", "t1", "u1", role="user", content="What is my account balance?")
        mgr.add_message("wa", "+1", "t1", "u1", role="assistant", content="Your balance is $100")
        mgr.add_message("wa", "+1", "t1", "u1", role="user", content="Show me recent transactions")
        mgr.add_message("wa", "+1", "t1", "u1", role="assistant", content="Here are your transactions")
        # Shift to completely different topic
        mgr.add_message("wa", "+1", "t1", "u1", role="user", content="What is the weather forecast for Tokyo Japan tomorrow?")
        session = mgr.get_session("wa", "+1", "t1")
        assert session.topic_changes >= 1


# ── Keyword extraction ─────────────────────────────────────────

class TestKeywordExtraction:
    def test_extracts_significant_words(self):
        keywords = _extract_keywords("What is machine learning and deep neural networks?")
        assert "machine" in keywords
        assert "learning" in keywords
        assert "what" not in keywords  # stop word
        assert "is" not in keywords  # stop word

    def test_short_words_excluded(self):
        keywords = _extract_keywords("a I am ok")
        assert len(keywords) == 0

    def test_empty_text(self):
        assert _extract_keywords("") == set()


# ── Message summarization ──────────────────────────────────────

class TestSummarization:
    def test_summarize_messages(self):
        msgs = [
            ConversationMessage(role="user", content="What is my balance?", timestamp="t1"),
            ConversationMessage(role="assistant", content="Your balance is $100.", timestamp="t2"),
        ]
        summary = summarize_messages(msgs)
        assert "[Q]:" in summary
        assert "[A]:" in summary

    def test_summarize_empty(self):
        assert summarize_messages([]) == ""

    def test_summarize_bounded(self):
        msgs = [
            ConversationMessage(role="user", content="x" * 200, timestamp=f"t{i}")
            for i in range(100)
        ]
        summary = summarize_messages(msgs, max_chars=500)
        assert len(summary) <= 600  # Some tolerance for line breaks


# ── Session management ─────────────────────────────────────────

class TestSessionManagement:
    def test_tenant_isolation(self):
        mgr = _mgr()
        mgr.add_message("wa", "+1", "t1", "u1", role="user", content="T1 message")
        mgr.add_message("wa", "+1", "t2", "u2", role="user", content="T2 message")
        ctx1 = mgr.get_context_messages("wa", "+1", "t1")
        ctx2 = mgr.get_context_messages("wa", "+1", "t2")
        assert len(ctx1) == 1
        assert len(ctx2) == 1
        assert ctx1[0]["content"] == "T1 message"

    def test_clear_session(self):
        mgr = _mgr()
        mgr.add_message("wa", "+1", "t1", "u1", role="user", content="Hello")
        assert mgr.clear_session("wa", "+1", "t1") is True
        assert mgr.get_context_messages("wa", "+1", "t1") == []

    def test_clear_nonexistent(self):
        mgr = _mgr()
        assert mgr.clear_session("wa", "+1", "t1") is False

    def test_session_capacity(self):
        mgr = _mgr()
        mgr.MAX_SESSIONS = 5
        for i in range(10):
            mgr.add_message("wa", f"+{i}", "t1", f"u{i}", role="user", content=f"Msg {i}")
        assert mgr.session_count <= 5

    def test_export_session(self):
        mgr = _mgr()
        mgr.add_message("wa", "+1", "t1", "u1", role="user", content="Hello")
        mgr.add_message("wa", "+1", "t1", "u1", role="assistant", content="Hi there")
        data = mgr.export_session("wa", "+1", "t1")
        assert data is not None
        assert data["total_messages"] == 2
        assert "thread_messages" in data
        assert len(data["thread_messages"]["main"]) == 2

    def test_export_nonexistent(self):
        mgr = _mgr()
        assert mgr.export_session("wa", "+1", "t1") is None


# ── Summary ────────────────────────────────────────────────────

class TestSummaryEndpoint:
    def test_summary_fields(self):
        mgr = _mgr()
        mgr.add_message("wa", "+1", "t1", "u1", role="user", content="Hi")
        s = mgr.summary()
        assert s["active_sessions"] == 1
        assert s["total_threads"] >= 1
        assert s["total_messages"] == 1
        assert "auto_detect_topics" in s
