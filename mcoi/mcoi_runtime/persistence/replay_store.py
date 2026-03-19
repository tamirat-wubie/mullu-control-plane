"""Purpose: append-only replay record persistence.
Governance scope: persistence layer replay storage only.
Dependencies: persistence errors, serialization helpers, replay engine types.
Invariants: one file per replay record, append-only, fail closed on malformed data.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import fields as dc_fields
from pathlib import Path
from typing import Any

from mcoi_runtime.contracts._base import thaw_value
from mcoi_runtime.core.replay_engine import (
    EffectControl,
    ReplayArtifact,
    ReplayEffect,
    ReplayMode,
    ReplayRecord,
)

from .errors import (
    CorruptedDataError,
    PersistenceError,
    PersistenceWriteError,
)


def _deterministic_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


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
        raise PersistenceWriteError(f"failed to write {path}: {exc}") from exc


def _serialize_replay_record(record: ReplayRecord) -> str:
    """Serialize a ReplayRecord to deterministic JSON."""
    data: dict[str, Any] = {
        "replay_id": record.replay_id,
        "trace_id": record.trace_id,
        "source_hash": record.source_hash,
        "approved_effects": [
            {"effect_id": e.effect_id, "control": str(e.control), "artifact_id": e.artifact_id}
            for e in record.approved_effects
        ],
        "blocked_effects": [
            {"effect_id": e.effect_id, "control": str(e.control), "artifact_id": e.artifact_id}
            for e in record.blocked_effects
        ],
        "mode": str(record.mode),
        "recorded_at": record.recorded_at,
        "artifacts": [
            {"artifact_id": a.artifact_id, "payload_digest": a.payload_digest}
            for a in record.artifacts
        ],
        "state_hash": record.state_hash,
        "environment_digest": record.environment_digest,
    }
    return _deterministic_json(data)


def _deserialize_replay_record(raw: dict[str, Any]) -> ReplayRecord:
    """Reconstruct a ReplayRecord from a parsed dict."""
    try:
        approved = tuple(
            ReplayEffect(
                effect_id=e["effect_id"],
                control=EffectControl(e["control"]),
                artifact_id=e.get("artifact_id"),
            )
            for e in raw.get("approved_effects", [])
        )
        blocked = tuple(
            ReplayEffect(
                effect_id=e["effect_id"],
                control=EffectControl(e["control"]),
                artifact_id=e.get("artifact_id"),
            )
            for e in raw.get("blocked_effects", [])
        )
        artifacts = tuple(
            ReplayArtifact(
                artifact_id=a["artifact_id"],
                payload_digest=a["payload_digest"],
            )
            for a in raw.get("artifacts", [])
        )
        return ReplayRecord(
            replay_id=raw["replay_id"],
            trace_id=raw["trace_id"],
            source_hash=raw["source_hash"],
            approved_effects=approved,
            blocked_effects=blocked,
            mode=ReplayMode(raw["mode"]),
            recorded_at=raw["recorded_at"],
            artifacts=artifacts,
            state_hash=raw.get("state_hash"),
            environment_digest=raw.get("environment_digest"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CorruptedDataError(f"invalid replay record: {exc}") from exc


class ReplayStore:
    """Append-only persistence for ReplayRecord instances.

    Each replay record is stored as a single JSON file named {replay_id}.json
    under base_path.
    """

    def __init__(self, base_path: Path) -> None:
        if not isinstance(base_path, Path):
            raise PersistenceError("base_path must be a Path instance")
        self._base_path = base_path

    def _replay_path(self, replay_id: str) -> Path:
        return self._base_path / f"{replay_id}.json"

    def save(self, record: ReplayRecord) -> None:
        if not isinstance(record, ReplayRecord):
            raise PersistenceError("record must be a ReplayRecord instance")
        content = _serialize_replay_record(record)
        _atomic_write(self._replay_path(record.replay_id), content)

    def load(self, replay_id: str) -> ReplayRecord:
        if not isinstance(replay_id, str) or not replay_id.strip():
            raise PersistenceError("replay_id must be a non-empty string")

        path = self._replay_path(replay_id)
        if not path.exists():
            raise PersistenceError(f"replay record not found: {replay_id}")

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise CorruptedDataError(f"malformed replay file {replay_id}: {exc}") from exc

        if not isinstance(raw, dict):
            raise CorruptedDataError(f"replay file {replay_id} is not a JSON object")

        return _deserialize_replay_record(raw)

    def list_replays(self) -> tuple[str, ...]:
        if not self._base_path.exists():
            return ()
        return tuple(
            entry.stem
            for entry in sorted(self._base_path.iterdir())
            if entry.is_file() and entry.suffix == ".json"
        )

    def load_all(self) -> tuple[ReplayRecord, ...]:
        if not self._base_path.exists():
            return ()
        results: list[ReplayRecord] = []
        for file_path in sorted(self._base_path.iterdir()):
            if file_path.is_file() and file_path.suffix == ".json":
                try:
                    raw = json.loads(file_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError) as exc:
                    raise CorruptedDataError(f"malformed replay file {file_path.name}: {exc}") from exc
                if not isinstance(raw, dict):
                    raise CorruptedDataError(f"replay file {file_path.name} is not a JSON object")
                results.append(_deserialize_replay_record(raw))
        return tuple(results)
