"""Purpose: runtime snapshot persistence with atomic writes.
Governance scope: persistence layer snapshot storage only.
Dependencies: persistence errors, contracts _base (thaw_value, freeze_value).
Invariants: no partial writes, fail closed on malformed data, deterministic hashing.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable

from mcoi_runtime.contracts._base import freeze_value, thaw_value

from .errors import (
    CorruptedDataError,
    PathTraversalError,
    PersistenceError,
    PersistenceWriteError,
    SnapshotNotFoundError,
)


@dataclass(frozen=True, slots=True)
class SnapshotMetadata:
    snapshot_id: str
    created_at: str
    description: str
    content_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot_id, str) or not self.snapshot_id.strip():
            raise PersistenceError("snapshot_id must be a non-empty string")
        if not isinstance(self.created_at, str) or not self.created_at.strip():
            raise PersistenceError("created_at must be a non-empty string")
        if not isinstance(self.content_hash, str) or not self.content_hash.strip():
            raise PersistenceError("content_hash must be a non-empty string")
        if not isinstance(self.description, str):
            raise PersistenceError("description must be a string")


def _bounded_store_error(summary: str, exc: BaseException) -> str:
    return f"{summary} ({type(exc).__name__})"


def _deterministic_json(data: Any) -> str:
    """Produce deterministic JSON for hashing and storage."""
    return json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _content_hash(json_str: str) -> str:
    return sha256(json_str.encode("ascii", "ignore")).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    """Write content to a file atomically via temp-file-then-rename."""
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(parent), suffix=".tmp")
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            fd = -1
            # On Windows, the target must not exist for os.rename to succeed
            # in all cases, so we use os.replace which handles this.
            os.replace(tmp_path, str(path))
        except BaseException:
            if fd >= 0:
                os.close(fd)
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    except OSError as exc:
        raise PersistenceWriteError(_bounded_store_error("snapshot store write failed", exc)) from exc


class SnapshotStore:
    """Persists runtime snapshots as directory-per-snapshot under base_path.

    Each snapshot directory contains:
      - metadata.json: SnapshotMetadata fields
      - data.json: the snapshot payload
    """

    def __init__(self, base_path: Path, *, clock: Callable[[], str] | None = None) -> None:
        if not isinstance(base_path, Path):
            raise PersistenceError("base_path must be a Path instance")
        self._base_path = base_path
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())

    def _safe_path(self, id_value: str, suffix: str = "") -> Path:
        """Construct a path from *id_value* and validate it stays inside _base_path.

        Raises PathTraversalError if the ID contains path-separator characters,
        parent-directory references, or null bytes, or if the resolved path
        escapes the base directory.
        """
        if "\0" in id_value:
            raise PathTraversalError("identifier contains null byte")
        if "/" in id_value or "\\" in id_value or ".." in id_value:
            raise PathTraversalError("identifier contains forbidden characters")
        candidate = (self._base_path / f"{id_value}{suffix}").resolve()
        base_resolved = self._base_path.resolve()
        if not candidate.is_relative_to(base_resolved):
            raise PathTraversalError("path escapes base directory")
        return candidate

    def _snapshot_dir(self, snapshot_id: str) -> Path:
        return self._safe_path(snapshot_id)

    def save_snapshot(
        self,
        snapshot_id: str,
        data: dict[str, Any],
        description: str = "",
    ) -> SnapshotMetadata:
        if not isinstance(snapshot_id, str) or not snapshot_id.strip():
            raise PersistenceError("snapshot_id must be a non-empty string")
        if not isinstance(data, dict):
            raise PersistenceError("data must be a dict")

        thawed = thaw_value(data)
        data_json = _deterministic_json(thawed)
        content_hash = _content_hash(data_json)
        created_at = self._clock()

        metadata = SnapshotMetadata(
            snapshot_id=snapshot_id,
            created_at=created_at,
            description=description,
            content_hash=content_hash,
        )

        snap_dir = self._snapshot_dir(snapshot_id)
        metadata_dict = {
            "snapshot_id": metadata.snapshot_id,
            "created_at": metadata.created_at,
            "description": metadata.description,
            "content_hash": metadata.content_hash,
        }
        _atomic_write(snap_dir / "metadata.json", _deterministic_json(metadata_dict))
        _atomic_write(snap_dir / "data.json", data_json)

        return metadata

    def load_snapshot(self, snapshot_id: str) -> tuple[SnapshotMetadata, dict[str, Any]]:
        if not isinstance(snapshot_id, str) or not snapshot_id.strip():
            raise PersistenceError("snapshot_id must be a non-empty string")

        snap_dir = self._snapshot_dir(snapshot_id)
        meta_path = snap_dir / "metadata.json"
        data_path = snap_dir / "data.json"

        if not meta_path.exists() or not data_path.exists():
            raise SnapshotNotFoundError("snapshot not found")

        try:
            meta_raw = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise CorruptedDataError(_bounded_store_error("malformed snapshot metadata", exc)) from exc

        if not isinstance(meta_raw, dict):
            raise CorruptedDataError("snapshot metadata must be a JSON object")

        try:
            metadata = SnapshotMetadata(
                snapshot_id=meta_raw["snapshot_id"],
                created_at=meta_raw["created_at"],
                description=meta_raw["description"],
                content_hash=meta_raw["content_hash"],
            )
        except (KeyError, TypeError, PersistenceError) as exc:
            raise CorruptedDataError(_bounded_store_error("invalid snapshot metadata", exc)) from exc

        try:
            data_raw = json.loads(data_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise CorruptedDataError(_bounded_store_error("malformed snapshot data", exc)) from exc

        if not isinstance(data_raw, dict):
            raise CorruptedDataError("snapshot data must be a JSON object")

        # Verify content hash to detect corruption
        actual_hash = _content_hash(_deterministic_json(data_raw))
        if actual_hash != metadata.content_hash:
            raise CorruptedDataError("snapshot content hash mismatch")

        return metadata, data_raw

    def list_snapshots(self) -> tuple[SnapshotMetadata, ...]:
        if not self._base_path.exists():
            return ()

        results: list[SnapshotMetadata] = []
        for entry in sorted(self._base_path.iterdir()):
            if not entry.is_dir():
                continue
            meta_path = entry / "metadata.json"
            if not meta_path.exists():
                continue
            try:
                meta_raw = json.loads(meta_path.read_text(encoding="utf-8"))
                results.append(
                    SnapshotMetadata(
                        snapshot_id=meta_raw["snapshot_id"],
                        created_at=meta_raw["created_at"],
                        description=meta_raw["description"],
                        content_hash=meta_raw["content_hash"],
                    )
                )
            except (json.JSONDecodeError, KeyError, TypeError, OSError, PersistenceError):
                raise CorruptedDataError("malformed snapshot metadata")

        return tuple(results)

    def snapshot_exists(self, snapshot_id: str) -> bool:
        if not isinstance(snapshot_id, str) or not snapshot_id.strip():
            raise PersistenceError("snapshot_id must be a non-empty string")
        snap_dir = self._snapshot_dir(snapshot_id)
        return (snap_dir / "metadata.json").exists() and (snap_dir / "data.json").exists()
