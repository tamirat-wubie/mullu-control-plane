"""Purpose: verify deterministic persistence for job conversation-thread indexes.
Governance scope: conversation-thread persistence witness tests only.
Dependencies: conversation contracts, conversation thread store, persistence errors.
Invariants:
  - save/load preserves thread identifiers, statuses, messages, and replay metadata.
  - malformed persisted payloads fail closed before restore.
  - store errors are bounded and do not leak filesystem paths or raw malformed values.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.contracts.conversation import (
    ConversationThread,
    MessageDirection,
    MessageType,
    ThreadMessage,
    ThreadStatus,
)
from mcoi_runtime.persistence.conversation_thread_store import ConversationThreadStore
from mcoi_runtime.persistence.errors import CorruptedDataError, PersistenceError


def _thread(thread_id: str = "thread-1") -> ConversationThread:
    return ConversationThread(
        thread_id=thread_id,
        subject="WHQR Vendor Binding",
        status=ThreadStatus.WAITING,
        messages=(
            ThreadMessage(
                message_id="msg-1",
                thread_id=thread_id,
                direction=MessageDirection.OUTBOUND,
                message_type=MessageType.CLARIFICATION_REQUEST,
                content="Which vendor entity reference binds WHQR target 'vendor'?",
                sender_id="system",
                recipient_id="operator",
                sent_at="2026-03-18T12:01:00+00:00",
                metadata={
                    "whqr_binding": True,
                    "clarification_request_id": "whqr-binding:1:vendor-node",
                    "clarification_context": "whqr_binding_gap target=vendor node_id=vendor-node",
                },
            ),
        ),
        goal_id="goal-1",
        created_at="2026-03-18T12:00:00+00:00",
        updated_at="2026-03-18T12:01:00+00:00",
    )


def test_conversation_thread_store_round_trip_preserves_replay_metadata(tmp_path: Path) -> None:
    store = ConversationThreadStore(tmp_path / "job-conversation-threads.json")
    thread = _thread()

    content = store.save_index({thread.thread_id: thread})
    restored = store.load_index()

    assert "\"schema_version\":1" in content
    assert tuple(restored) == ("thread-1",)
    assert restored["thread-1"].status is ThreadStatus.WAITING
    assert restored["thread-1"].messages[0].metadata["whqr_binding"] is True
    assert restored["thread-1"].messages[0].metadata["clarification_request_id"] == "whqr-binding:1:vendor-node"


def test_conversation_thread_store_rejects_key_thread_id_mismatch(tmp_path: Path) -> None:
    store = ConversationThreadStore(tmp_path / "job-conversation-threads.json")
    thread = _thread("thread-real")

    with pytest.raises(PersistenceError, match="key must match"):
        store.save_index({"thread-other": thread})

    assert store.exists() is False
    assert not (tmp_path / "job-conversation-threads.json").exists()


def test_conversation_thread_store_fails_closed_on_duplicate_thread_ids(tmp_path: Path) -> None:
    store = ConversationThreadStore(tmp_path / "job-conversation-threads.json")
    payload_path = tmp_path / "job-conversation-threads.json"
    first = json.loads(ConversationThreadStore(payload_path).save_index({"thread-1": _thread("thread-1")}))
    first["threads"].append(first["threads"][0])
    payload_path.write_text(
        json.dumps(first, sort_keys=True, ensure_ascii=True, separators=(",", ":")),
        encoding="utf-8",
    )

    with pytest.raises(CorruptedDataError, match="duplicate thread identifier"):
        store.load_index()

    assert store.exists() is True
    assert payload_path.exists() is True


def test_conversation_thread_store_rejects_non_standard_json_constants(tmp_path: Path) -> None:
    store = ConversationThreadStore(tmp_path / "job-conversation-threads.json")
    payload_path = tmp_path / "job-conversation-threads.json"
    payload_path.write_text(
        '{"schema_version":1,"threads":[],"secret_metric":NaN}',
        encoding="utf-8",
    )

    with pytest.raises(
        CorruptedDataError,
        match=r"^malformed conversation thread index file \(ValueError\)$",
    ) as excinfo:
        store.load_index()

    assert "secret_metric" not in str(excinfo.value)
    assert "NaN" not in str(excinfo.value)


def test_conversation_thread_store_missing_file_can_restore_empty_first_boot(tmp_path: Path) -> None:
    store = ConversationThreadStore(tmp_path / "job-conversation-threads.json")

    restored = store.load_index(allow_missing=True)

    assert restored == {}
    assert store.exists() is False


def test_conversation_thread_store_missing_file_error_is_bounded(tmp_path: Path) -> None:
    store = ConversationThreadStore(tmp_path / "job-conversation-threads.json")

    with pytest.raises(CorruptedDataError, match=r"^conversation thread index file not found$") as excinfo:
        store.load_index()

    assert str(tmp_path) not in str(excinfo.value)
