"""Purpose: verify env-driven job conversation-thread persistence wiring.
Governance scope: served-runtime WHQR clarification replay persistence only.
Dependencies: app job conversation integration, conversation contracts, persistence store.
Invariants:
  - persistence is disabled unless an explicit store path is configured.
  - configured missing stores restore as empty first-boot indexes.
  - configured malformed stores fail closed before dependency publication.
  - shutdown snapshot persists the current index without replaying thread transitions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.app.job_conversation_integration import (
    JOB_CONVERSATION_THREAD_STORE_PATH_ENV,
    bootstrap_job_conversation_threads,
    record_job_conversation_thread,
    validate_job_conversation_thread_store_path,
)
from mcoi_runtime.contracts.conversation import ConversationThread, ThreadStatus
from mcoi_runtime.persistence.conversation_thread_store import ConversationThreadStore
from mcoi_runtime.persistence.errors import CorruptedDataError


def _thread() -> ConversationThread:
    return ConversationThread(
        thread_id="thread-live",
        subject="WHQR Restart Replay",
        status=ThreadStatus.ACTIVE,
        created_at="2026-03-18T12:00:00+00:00",
        updated_at="2026-03-18T12:00:00+00:00",
    )


def test_job_conversation_bootstrap_disabled_without_store_path() -> None:
    bootstrap = bootstrap_job_conversation_threads({})

    assert bootstrap.store is None
    assert bootstrap.thread_index == {}
    assert bootstrap.save_on_shutdown is None


def test_job_conversation_bootstrap_restores_empty_index_for_first_boot(tmp_path: Path) -> None:
    store_path = tmp_path / "job-conversation-threads.json"

    bootstrap = bootstrap_job_conversation_threads(
        {JOB_CONVERSATION_THREAD_STORE_PATH_ENV: str(store_path)}
    )

    assert bootstrap.store is not None
    assert bootstrap.thread_index == {}
    assert bootstrap.save_on_shutdown is not None
    assert store_path.exists() is False


def test_job_conversation_shutdown_snapshot_persists_current_index(tmp_path: Path) -> None:
    store_path = tmp_path / "job-conversation-threads.json"
    bootstrap = bootstrap_job_conversation_threads(
        {JOB_CONVERSATION_THREAD_STORE_PATH_ENV: str(store_path)}
    )
    assert bootstrap.save_on_shutdown is not None
    bootstrap.thread_index["thread-live"] = _thread()

    result = dict(bootstrap.save_on_shutdown())
    restored = bootstrap_job_conversation_threads(
        {JOB_CONVERSATION_THREAD_STORE_PATH_ENV: str(store_path)}
    )

    assert result["store_configured"] is True
    assert result["thread_count"] == 1
    assert restored.thread_index["thread-live"].subject == "WHQR Restart Replay"
    assert restored.thread_index["thread-live"].status is ThreadStatus.ACTIVE
    assert store_path.exists() is True


def test_record_job_conversation_thread_saves_immediately_when_store_configured(tmp_path: Path) -> None:
    store_path = tmp_path / "job-conversation-threads.json"
    store = ConversationThreadStore(store_path)
    thread_index: dict[str, ConversationThread] = {}

    result = dict(record_job_conversation_thread(thread_index, _thread(), store))
    restored = store.load_index()

    assert result["store_configured"] is True
    assert result["thread_id"] == "thread-live"
    assert result["thread_count"] == 1
    assert restored["thread-live"].subject == "WHQR Restart Replay"
    assert store_path.exists() is True


def test_record_job_conversation_thread_updates_memory_without_store(tmp_path: Path) -> None:
    thread_index: dict[str, ConversationThread] = {}

    result = dict(record_job_conversation_thread(thread_index, _thread(), None))

    assert result["store_configured"] is False
    assert result["thread_count"] == 1
    assert thread_index["thread-live"].status is ThreadStatus.ACTIVE
    assert not (tmp_path / "job-conversation-threads.json").exists()


def test_record_job_conversation_thread_rejects_invalid_inputs(tmp_path: Path) -> None:
    store = ConversationThreadStore(tmp_path / "job-conversation-threads.json")

    with pytest.raises(TypeError, match="thread_index"):
        record_job_conversation_thread((), _thread(), store)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="ConversationThread"):
        record_job_conversation_thread({}, object(), store)  # type: ignore[arg-type]

    assert store.exists() is False


def test_job_conversation_bootstrap_fails_closed_on_malformed_store(tmp_path: Path) -> None:
    store_path = tmp_path / "job-conversation-threads.json"
    store_path.write_text('{"schema_version":1,"threads":NaN}', encoding="utf-8")

    with pytest.raises(CorruptedDataError, match="malformed conversation thread index file"):
        bootstrap_job_conversation_threads(
            {JOB_CONVERSATION_THREAD_STORE_PATH_ENV: str(store_path)}
        )

    assert store_path.exists() is True


def test_job_conversation_store_path_requires_absolute_json_file(tmp_path: Path) -> None:
    valid_path = tmp_path / "job-conversation-threads.json"

    assert validate_job_conversation_thread_store_path(valid_path) == valid_path
    with pytest.raises(RuntimeError, match="absolute file path"):
        validate_job_conversation_thread_store_path("relative.json")
    with pytest.raises(RuntimeError, match=r"\.json file extension"):
        validate_job_conversation_thread_store_path(tmp_path / "threads.txt")
