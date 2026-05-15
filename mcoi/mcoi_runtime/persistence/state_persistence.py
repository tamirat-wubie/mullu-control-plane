"""Phase 211D - State Persistence.

Purpose: Save and restore runtime state (conversations, workflows,
    config) across server restarts. JSON-based file persistence
    for development, with interface for production backends.
Governance scope: state serialization only.
Dependencies: none (pure file I/O).
Invariants:
  - State files are atomic (write to temp, then rename).
  - Restore never corrupts in-memory state on failure.
  - State format is versioned for migration.
  - All state is JSON-serializable.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable

from .errors import CorruptedDataError, PathTraversalError, PersistenceError, PersistenceWriteError


def _bounded_store_error(summary: str, exc: BaseException) -> str:
    return f"{summary} ({type(exc).__name__})"


def _require_non_empty_text(field_name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersistenceError(f"{field_name} must be a non-empty string")
    return value


def _freeze_state_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip():
                raise PersistenceError("state data keys must be non-empty strings")
            frozen[key] = _freeze_state_value(item)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_state_value(item) for item in value)
    return value


def _thaw_state_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_state_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_state_value(item) for item in value]
    if isinstance(value, list):
        return [_thaw_state_value(item) for item in value]
    return value


def thaw_state_data(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return a JSON-compatible copy of snapshot data."""
    thawed = _thaw_state_value(data)
    if not isinstance(thawed, dict):
        raise PersistenceError("data must be a dict")
    return thawed


def _copy_state_data(data: object) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise PersistenceError("data must be a dict")
    return thaw_state_data(_freeze_state_value(data))


def _deterministic_json(data: Any) -> str:
    try:
        return json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise PersistenceError(_bounded_store_error("state data is not JSON serializable", exc)) from exc


def _state_hash(data: Mapping[str, Any]) -> str:
    return sha256(_deterministic_json(_thaw_state_value(data)).encode("ascii")).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent), suffix=".tmp", prefix="mullu_state_",
        )
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
        raise PersistenceWriteError(_bounded_store_error("state write failed", exc)) from exc


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    """Serializable state snapshot."""

    version: str
    state_type: str  # "conversations", "config", "workflows", etc.
    data: Mapping[str, Any]
    state_hash: str
    saved_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "version", _require_non_empty_text("version", self.version))
        object.__setattr__(self, "state_type", _require_non_empty_text("state_type", self.state_type))
        object.__setattr__(self, "state_hash", _require_non_empty_text("state_hash", self.state_hash))
        object.__setattr__(self, "saved_at", _require_non_empty_text("saved_at", self.saved_at))
        if not isinstance(self.data, Mapping):
            raise PersistenceError("data must be a dict")
        object.__setattr__(self, "data", _freeze_state_value(self.data))


class StatePersistence:
    """File-based state persistence with atomic writes."""

    def __init__(self, *, clock: Callable[[], str], base_dir: str | Path = "") -> None:
        if not callable(clock):
            raise PersistenceError("clock must be callable")
        if not isinstance(base_dir, (str, Path)):
            raise PersistenceError("base_dir must be a path string or Path")
        self._clock = clock
        self._base_dir = Path(base_dir or tempfile.gettempdir()).resolve()
        self._snapshots: dict[str, StateSnapshot] = {}

    def _safe_path(self, state_type: str) -> Path:
        """Construct a validated state file path within the configured base directory."""
        if not isinstance(state_type, str) or not state_type.strip():
            raise PathTraversalError("state_type must be a non-empty string")
        if "\0" in state_type:
            raise PathTraversalError("state_type contains null byte")
        if "/" in state_type or "\\" in state_type or ".." in state_type:
            raise PathTraversalError("state_type contains forbidden characters")
        candidate = (self._base_dir / f"mullu_state_{state_type}.json").resolve()
        if not candidate.is_relative_to(self._base_dir):
            raise PathTraversalError("state path escapes base directory")
        return candidate

    def save(self, state_type: str, data: dict[str, Any]) -> StateSnapshot:
        """Save state to file (atomic write)."""
        file_path = self._safe_path(state_type)
        copied_data = _copy_state_data(data)
        state_hash = _state_hash(copied_data)

        snapshot = StateSnapshot(
            version="1.0.0",
            state_type=state_type,
            data=copied_data,
            state_hash=state_hash,
            saved_at=self._clock(),
        )

        wrapper = {
            "version": snapshot.version,
            "state_type": snapshot.state_type,
            "state_hash": state_hash,
            "saved_at": snapshot.saved_at,
            "data": _thaw_state_value(snapshot.data),
        }

        _atomic_write(file_path, _deterministic_json(wrapper))

        self._snapshots[snapshot.state_type] = snapshot
        return snapshot

    def load(self, state_type: str) -> StateSnapshot | None:
        """Load state from file."""
        file_path = self._safe_path(state_type)
        if not file_path.exists():
            return None

        try:
            wrapper = json.loads(file_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise CorruptedDataError(_bounded_store_error("malformed state file", exc)) from exc

        if not isinstance(wrapper, dict):
            raise CorruptedDataError("state file must be a JSON object")

        try:
            persisted_state_type = wrapper["state_type"]
            data = wrapper["data"]
            expected_hash = wrapper["state_hash"]
            version = wrapper["version"]
            saved_at = wrapper["saved_at"]
        except KeyError as exc:
            raise CorruptedDataError(_bounded_store_error("state file missing required field", exc)) from exc

        if persisted_state_type != state_type:
            raise CorruptedDataError("state type mismatch")
        if not isinstance(data, dict):
            raise CorruptedDataError("state data must be a JSON object")
        if not isinstance(expected_hash, str) or expected_hash != _state_hash(data):
            raise CorruptedDataError("state hash mismatch")

        try:
            snapshot = StateSnapshot(
                version=version,
                state_type=state_type,
                data=data,
                state_hash=expected_hash,
                saved_at=saved_at,
            )
        except PersistenceError as exc:
            raise CorruptedDataError(_bounded_store_error("invalid state snapshot", exc)) from exc

        self._snapshots[state_type] = snapshot
        return snapshot

    def exists(self, state_type: str) -> bool:
        file_path = self._safe_path(state_type)
        return file_path.exists()

    def delete(self, state_type: str) -> bool:
        file_path = self._safe_path(state_type)
        if file_path.exists():
            try:
                file_path.unlink()
            except OSError as exc:
                raise PersistenceWriteError(_bounded_store_error("state delete failed", exc)) from exc
            self._snapshots.pop(state_type, None)
            return True
        return False

    def list_states(self) -> list[str]:
        """List all saved state types."""
        if not self._base_dir.exists():
            return []
        states = []
        for filename in os.listdir(self._base_dir):
            if filename.startswith("mullu_state_") and filename.endswith(".json"):
                state_type = filename[len("mullu_state_"):-len(".json")]
                try:
                    self._safe_path(state_type)
                except PathTraversalError as exc:
                    raise CorruptedDataError("state filename is invalid") from exc
                states.append(state_type)
        return sorted(states)

    def summary(self) -> dict[str, Any]:
        return {
            "saved_states": len(self._snapshots),
            "state_types": sorted(self._snapshots.keys()),
            "base_dir": str(self._base_dir),
        }
