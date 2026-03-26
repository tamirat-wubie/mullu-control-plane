"""Phase 208C — Conversation memory tests."""

import pytest
from mcoi_runtime.core.conversation_memory import (
    Conversation, ConversationConfig, ConversationStore,
)

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestConversation:
    def test_add_message(self):
        conv = Conversation("c1", clock=FIXED_CLOCK)
        msg = conv.add_user("hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert conv.message_count == 1

    def test_multi_turn(self):
        conv = Conversation("c1", clock=FIXED_CLOCK)
        conv.add_system("You are helpful")
        conv.add_user("What is 2+2?")
        conv.add_assistant("4")
        assert conv.message_count == 3

    def test_to_chat_messages(self):
        conv = Conversation("c1", clock=FIXED_CLOCK)
        conv.add_user("hi")
        conv.add_assistant("hello")
        msgs = conv.to_chat_messages()
        assert msgs == [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]

    def test_pruning(self):
        conv = Conversation("c1", config=ConversationConfig(max_messages=3), clock=FIXED_CLOCK)
        conv.add_user("1")
        conv.add_assistant("2")
        conv.add_user("3")
        conv.add_assistant("4")  # Should trigger pruning
        assert conv.message_count <= 3

    def test_prune_keeps_system(self):
        conv = Conversation("c1", config=ConversationConfig(max_messages=3), clock=FIXED_CLOCK)
        conv.add_system("System prompt")
        conv.add_user("1")
        conv.add_assistant("2")
        conv.add_user("3")
        conv.add_assistant("4")
        # System message should be kept
        assert any(m.role == "system" for m in conv.messages)

    def test_clear_keeps_system(self):
        conv = Conversation("c1", clock=FIXED_CLOCK)
        conv.add_system("System")
        conv.add_user("hi")
        conv.add_assistant("hello")
        conv.clear()
        assert conv.message_count == 1
        assert conv.messages[0].role == "system"

    def test_state_hash(self):
        conv = Conversation("c1", clock=FIXED_CLOCK)
        conv.add_user("hello")
        h1 = conv.state_hash()
        conv.add_assistant("hi")
        h2 = conv.state_hash()
        assert h1 != h2

    def test_summary(self):
        conv = Conversation("c1", tenant_id="t1", clock=FIXED_CLOCK)
        conv.add_user("a")
        conv.add_assistant("b")
        summary = conv.summary()
        assert summary["message_count"] == 2
        assert summary["tenant_id"] == "t1"


class TestConversationStore:
    def test_get_or_create(self):
        store = ConversationStore(clock=FIXED_CLOCK)
        conv = store.get_or_create("c1", tenant_id="t1")
        assert conv.conversation_id == "c1"
        assert store.count == 1

    def test_get_existing(self):
        store = ConversationStore(clock=FIXED_CLOCK)
        store.get_or_create("c1")
        conv = store.get("c1")
        assert conv is not None

    def test_get_missing(self):
        store = ConversationStore(clock=FIXED_CLOCK)
        assert store.get("nonexistent") is None

    def test_list_by_tenant(self):
        store = ConversationStore(clock=FIXED_CLOCK)
        store.get_or_create("c1", tenant_id="t1")
        store.get_or_create("c2", tenant_id="t2")
        store.get_or_create("c3", tenant_id="t1")
        convs = store.list_conversations(tenant_id="t1")
        assert len(convs) == 2

    def test_delete(self):
        store = ConversationStore(clock=FIXED_CLOCK)
        store.get_or_create("c1")
        assert store.delete("c1") is True
        assert store.count == 0

    def test_summary(self):
        store = ConversationStore(clock=FIXED_CLOCK)
        c = store.get_or_create("c1")
        c.add_user("hi")
        c.add_assistant("hello")
        summary = store.summary()
        assert summary["conversations"] == 1
        assert summary["total_messages"] == 2
