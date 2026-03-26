"""Phase 211D — State Persistence.

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
from dataclasses import dataclass
from typing import Any, Callable
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    """Serializable state snapshot."""

    version: str
    state_type: str  # "conversations", "config", "workflows", etc.
    data: dict[str, Any]
    state_hash: str
    saved_at: str


class StatePersistence:
    """File-based state persistence with atomic writes."""

    def __init__(self, *, clock: Callable[[], str], base_dir: str = "") -> None:
        self._clock = clock
        self._base_dir = base_dir or tempfile.gettempdir()
        self._snapshots: dict[str, StateSnapshot] = {}

    def save(self, state_type: str, data: dict[str, Any]) -> StateSnapshot:
        """Save state to file (atomic write)."""
        content = json.dumps(data, sort_keys=True, default=str, indent=2)
        state_hash = sha256(content.encode()).hexdigest()

        snapshot = StateSnapshot(
            version="1.0.0",
            state_type=state_type,
            data=data,
            state_hash=state_hash,
            saved_at=self._clock(),
        )

        file_path = os.path.join(self._base_dir, f"mullu_state_{state_type}.json")

        # Atomic write: temp file → rename
        wrapper = {
            "version": snapshot.version,
            "state_type": state_type,
            "state_hash": state_hash,
            "saved_at": snapshot.saved_at,
            "data": data,
        }

        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=self._base_dir, suffix=".tmp", prefix="mullu_state_",
        )
        try:
            with os.fdopen(tmp_fd, "w") as f:
                json.dump(wrapper, f, sort_keys=True, default=str, indent=2)
            # Atomic rename (on same filesystem)
            if os.path.exists(file_path):
                os.replace(tmp_path, file_path)
            else:
                os.rename(tmp_path, file_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        self._snapshots[state_type] = snapshot
        return snapshot

    def load(self, state_type: str) -> StateSnapshot | None:
        """Load state from file."""
        file_path = os.path.join(self._base_dir, f"mullu_state_{state_type}.json")
        if not os.path.exists(file_path):
            return None

        try:
            with open(file_path, "r") as f:
                wrapper = json.load(f)

            snapshot = StateSnapshot(
                version=wrapper.get("version", "1.0.0"),
                state_type=state_type,
                data=wrapper.get("data", {}),
                state_hash=wrapper.get("state_hash", ""),
                saved_at=wrapper.get("saved_at", ""),
            )
            self._snapshots[state_type] = snapshot
            return snapshot
        except (json.JSONDecodeError, KeyError):
            return None

    def exists(self, state_type: str) -> bool:
        file_path = os.path.join(self._base_dir, f"mullu_state_{state_type}.json")
        return os.path.exists(file_path)

    def delete(self, state_type: str) -> bool:
        file_path = os.path.join(self._base_dir, f"mullu_state_{state_type}.json")
        if os.path.exists(file_path):
            os.unlink(file_path)
            self._snapshots.pop(state_type, None)
            return True
        return False

    def list_states(self) -> list[str]:
        """List all saved state types."""
        states = []
        for filename in os.listdir(self._base_dir):
            if filename.startswith("mullu_state_") and filename.endswith(".json"):
                state_type = filename[len("mullu_state_"):-len(".json")]
                states.append(state_type)
        return sorted(states)

    def summary(self) -> dict[str, Any]:
        return {
            "saved_states": len(self._snapshots),
            "state_types": list(self._snapshots.keys()),
            "base_dir": self._base_dir,
        }
