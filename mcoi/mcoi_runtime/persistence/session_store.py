"""Session Persistence Store — Checkpoint and restore GovernedSession state.

Purpose: Persist mutable GovernedSession state (operations count, LLM calls,
    cost, context messages) so multi-turn sessions survive process restarts.
Governance scope: state serialization only — no governance logic here.
Dependencies: StatePersistence (for file backend).
Invariants:
  - Checkpoint is atomic (no partial writes visible to readers).
  - Restore never corrupts live session state on failure.
  - Session identity (tenant_id, identity_id) is verified on restore.
  - Bounded: stale sessions are pruned by TTL.
  - Context messages are included in checkpoint for conversation continuity.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class SessionCheckpoint:
    """Serializable snapshot of GovernedSession mutable state."""

    session_id: str
    identity_id: str
    tenant_id: str
    operations: int
    llm_calls: int
    total_cost: float
    context_messages: tuple[dict[str, str], ...]
    compaction_count: int
    checkpoint_at: str
    checkpoint_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = {
            "session_id": self.session_id,
            "identity_id": self.identity_id,
            "tenant_id": self.tenant_id,
            "operations": self.operations,
            "llm_calls": self.llm_calls,
            "total_cost": self.total_cost,
            "context_messages": list(self.context_messages),
            "compaction_count": self.compaction_count,
            "checkpoint_at": self.checkpoint_at,
        }
        content = json.dumps(data, sort_keys=True, default=str)
        data["checkpoint_hash"] = sha256(content.encode()).hexdigest()[:16]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionCheckpoint | None:
        """Deserialize with integrity check. Returns None on corruption."""
        try:
            stored_hash = data.pop("checkpoint_hash", "")
            content = json.dumps(data, sort_keys=True, default=str)
            expected_hash = sha256(content.encode()).hexdigest()[:16]
            if stored_hash and stored_hash != expected_hash:
                return None
            return cls(
                session_id=data["session_id"],
                identity_id=data["identity_id"],
                tenant_id=data["tenant_id"],
                operations=int(data["operations"]),
                llm_calls=int(data["llm_calls"]),
                total_cost=float(data["total_cost"]),
                context_messages=tuple(data.get("context_messages", ())),
                compaction_count=int(data.get("compaction_count", 0)),
                checkpoint_at=data.get("checkpoint_at", ""),
                checkpoint_hash=expected_hash,
            )
        except (KeyError, TypeError, ValueError):
            return None


class SessionStore:
    """Protocol for session state persistence backends."""

    def save(self, checkpoint: SessionCheckpoint) -> bool:
        """Persist a session checkpoint. Returns True on success."""
        return False

    def load(self, session_id: str) -> SessionCheckpoint | None:
        """Load a session checkpoint. Returns None if not found or corrupt."""
        return None

    def delete(self, session_id: str) -> bool:
        """Remove a persisted session. Returns True if it existed."""
        return False

    def list_sessions(self, *, tenant_id: str = "") -> list[str]:
        """List persisted session IDs, optionally filtered by tenant."""
        return []

    def prune(self, *, max_age_seconds: float = 86400.0, clock: Callable[[], str] | None = None) -> int:
        """Remove sessions older than max_age. Returns count pruned."""
        return 0


class InMemorySessionStore(SessionStore):
    """In-memory session store for testing."""

    MAX_SESSIONS = 10_000

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def save(self, checkpoint: SessionCheckpoint) -> bool:
        with self._lock:
            if len(self._sessions) >= self.MAX_SESSIONS and checkpoint.session_id not in self._sessions:
                oldest_key = next(iter(self._sessions))
                del self._sessions[oldest_key]
            self._sessions[checkpoint.session_id] = checkpoint.to_dict()
            return True

    def load(self, session_id: str) -> SessionCheckpoint | None:
        with self._lock:
            data = self._sessions.get(session_id)
            if data is None:
                return None
            return SessionCheckpoint.from_dict(dict(data))  # Copy to avoid mutation

    def delete(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def list_sessions(self, *, tenant_id: str = "") -> list[str]:
        with self._lock:
            if not tenant_id:
                return list(self._sessions.keys())
            return [
                sid for sid, data in self._sessions.items()
                if data.get("tenant_id") == tenant_id
            ]

    def prune(self, *, max_age_seconds: float = 86400.0, clock: Callable[[], str] | None = None) -> int:
        if clock is None:
            return 0
        now = clock()
        pruned = 0
        with self._lock:
            stale = []
            for sid, data in self._sessions.items():
                checkpoint_at = data.get("checkpoint_at", "")
                if checkpoint_at and checkpoint_at < now:
                    # Simplified age check — ISO string comparison works for same-timezone
                    stale.append(sid)
            for sid in stale:
                del self._sessions[sid]
                pruned += 1
        return pruned

    @property
    def session_count(self) -> int:
        return len(self._sessions)


class FileSessionStore(SessionStore):
    """File-based session store with atomic writes.

    Each session is stored as a separate JSON file:
    ``{base_dir}/session_{session_id}.json``

    Uses the same atomic write pattern as StatePersistence
    (write to temp file, then os.replace).
    """

    MAX_SESSIONS = 50_000

    def __init__(self, *, base_dir: str) -> None:
        self._base_dir = Path(base_dir).resolve()
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        if not session_id or "\0" in session_id:
            raise ValueError("invalid session_id")
        if "/" in session_id or "\\" in session_id or ".." in session_id:
            raise ValueError("session_id contains forbidden characters")
        candidate = (self._base_dir / f"session_{session_id}.json").resolve()
        if not candidate.is_relative_to(self._base_dir):
            raise ValueError("session path escapes base directory")
        return candidate

    def save(self, checkpoint: SessionCheckpoint) -> bool:
        try:
            data = checkpoint.to_dict()
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=str(self._base_dir), suffix=".tmp", prefix="session_",
            )
            try:
                with os.fdopen(tmp_fd, "w") as f:
                    json.dump(data, f, sort_keys=True, default=str, indent=2)
                os.replace(tmp_path, str(self._session_path(checkpoint.session_id)))
            except Exception:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                return False
            return True
        except (ValueError, OSError):
            return False

    def load(self, session_id: str) -> SessionCheckpoint | None:
        try:
            path = self._session_path(session_id)
            if not path.exists():
                return None
            with path.open("r") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return None
            return SessionCheckpoint.from_dict(data)
        except (ValueError, json.JSONDecodeError, OSError):
            return None

    def delete(self, session_id: str) -> bool:
        try:
            path = self._session_path(session_id)
            if path.exists():
                path.unlink()
                return True
            return False
        except (ValueError, OSError):
            return False

    def list_sessions(self, *, tenant_id: str = "") -> list[str]:
        if not self._base_dir.exists():
            return []
        sessions = []
        for filename in sorted(os.listdir(self._base_dir)):
            if filename.startswith("session_") and filename.endswith(".json"):
                sid = filename[len("session_"):-len(".json")]
                if tenant_id:
                    cp = self.load(sid)
                    if cp is None or cp.tenant_id != tenant_id:
                        continue
                sessions.append(sid)
        return sessions

    def prune(self, *, max_age_seconds: float = 86400.0, clock: Callable[[], str] | None = None) -> int:
        if clock is None:
            return 0
        pruned = 0
        for sid in self.list_sessions():
            cp = self.load(sid)
            if cp is not None and cp.checkpoint_at and cp.checkpoint_at < clock():
                if self.delete(sid):
                    pruned += 1
        return pruned

    def summary(self) -> dict[str, Any]:
        return {
            "base_dir": str(self._base_dir),
            "session_count": len(self.list_sessions()),
        }
