"""Purpose: deterministic persistence for job conversation-thread indexes.
Governance scope: conversation thread read-model persistence only.
Dependencies: conversation contracts, deterministic JSON helpers, persistence errors.
Invariants:
  - Thread serialization is deterministic and identifier-stable.
  - Load fails closed on malformed content, duplicate thread identifiers, or schema drift.
  - Restore returns exact persisted thread records without replaying conversation transitions.
  - Persistence never mutates ConversationEngine state or executes side effects beyond file writes.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from mcoi_runtime.contracts.conversation import ConversationThread

from ._serialization import deserialize_record, loads_strict_json, serialize_record
from .errors import CorruptedDataError, PersistenceError, PersistenceWriteError

_SCHEMA_VERSION = 1


def _deterministic_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def _bounded_store_error(summary: str, exc: BaseException) -> str:
    return f"{summary} ({type(exc).__name__})"


def _atomic_write(path: Path, content: str) -> None:
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(parent), suffix=".tmp")
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            fd = -1
            os.replace(tmp_path, str(path))
        except BaseException:
            if fd >= 0:
                os.close(fd)
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    except OSError as exc:
        raise PersistenceWriteError(_bounded_store_error("conversation thread store write failed", exc)) from exc


def _record_payload(record: ConversationThread) -> dict[str, object]:
    payload = loads_strict_json(serialize_record(record))
    if not isinstance(payload, dict):
        raise PersistenceError("serialized conversation thread must be a JSON object")
    return payload


@dataclass(frozen=True, slots=True)
class ConversationThreadIndexState:
    """Explicit snapshot of persisted job conversation threads."""

    threads: tuple[ConversationThread, ...]

    def __post_init__(self) -> None:
        if any(not isinstance(thread, ConversationThread) for thread in self.threads):
            raise PersistenceError("threads must contain ConversationThread instances only")


class ConversationThreadStore:
    """Persist a thread-id keyed conversation index as a deterministic JSON witness."""

    def __init__(self, store_path: Path) -> None:
        if not isinstance(store_path, Path):
            raise PersistenceError("store_path must be a Path instance")
        self._store_path = store_path

    @property
    def store_path(self) -> Path:
        return self._store_path

    def save_index(self, thread_index: Mapping[str, ConversationThread]) -> str:
        if not isinstance(thread_index, Mapping):
            raise PersistenceError("thread_index must be a mapping")
        self._validate_index(thread_index)
        payload = {
            "schema_version": _SCHEMA_VERSION,
            "threads": [
                _record_payload(thread)
                for thread in sorted(thread_index.values(), key=lambda item: item.thread_id)
            ],
        }
        content = _deterministic_json(payload)
        _atomic_write(self._store_path, content)
        return content

    def load_state(self, *, allow_missing: bool = False) -> ConversationThreadIndexState:
        if not self._store_path.exists():
            if allow_missing:
                return ConversationThreadIndexState(threads=())
            raise CorruptedDataError("conversation thread index file not found")
        try:
            payload = loads_strict_json(self._store_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            raise CorruptedDataError(
                _bounded_store_error("malformed conversation thread index file", exc)
            ) from exc
        if not isinstance(payload, dict):
            raise CorruptedDataError("conversation thread index payload must be a JSON object")
        if payload.get("schema_version") != _SCHEMA_VERSION:
            raise CorruptedDataError("conversation thread index schema_version is unsupported")
        threads_raw = payload.get("threads")
        if not isinstance(threads_raw, list):
            raise CorruptedDataError("conversation thread index threads must be a JSON array")
        threads = tuple(self._deserialize_thread(raw) for raw in threads_raw)
        self._require_unique(tuple(thread.thread_id for thread in threads))
        return ConversationThreadIndexState(threads=threads)

    def load_index(self, *, allow_missing: bool = False) -> dict[str, ConversationThread]:
        state = self.load_state(allow_missing=allow_missing)
        return {thread.thread_id: thread for thread in state.threads}

    def exists(self) -> bool:
        return self._store_path.exists()

    @staticmethod
    def _deserialize_thread(raw: object) -> ConversationThread:
        if not isinstance(raw, dict):
            raise CorruptedDataError("conversation thread entry must be a JSON object")
        return deserialize_record(_deterministic_json(raw), ConversationThread)

    @staticmethod
    def _validate_index(thread_index: Mapping[str, ConversationThread]) -> None:
        for thread_id, thread in thread_index.items():
            if not isinstance(thread_id, str) or not thread_id.strip():
                raise PersistenceError("thread_index keys must be non-empty strings")
            if not isinstance(thread, ConversationThread):
                raise PersistenceError("thread_index values must be ConversationThread instances")
            if thread_id != thread.thread_id:
                raise PersistenceError("thread_index key must match ConversationThread.thread_id")
        ConversationThreadStore._require_unique(tuple(thread_index.keys()))

    @staticmethod
    def _require_unique(thread_ids: tuple[str, ...]) -> None:
        if len(thread_ids) != len(set(thread_ids)):
            raise CorruptedDataError("duplicate thread identifier in conversation thread index payload")
