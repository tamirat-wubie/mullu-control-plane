"""Purpose: SHA-256 hash-chain store for tamper-evident append-only audit trails.
Governance scope: persistence layer integrity verification only.
Dependencies: persistence errors, serialization helpers, integrity contracts.
Invariants: chain is append-only; hash computation is deterministic; validation fails closed.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from mcoi_runtime.contracts.integrity import HashChainEntry, HashChainValidationResult

from ._serialization import deserialize_record, serialize_record
from .errors import (
    CorruptedDataError,
    PathTraversalError,
    PersistenceError,
    PersistenceWriteError,
)

GENESIS_PREVIOUS_HASH = "0" * 64  # 64 hex zeros for the genesis entry


def _bounded_store_error(summary: str, exc: BaseException) -> str:
    return f"{summary} ({type(exc).__name__})"


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
            os.replace(tmp_path, str(path))
        except BaseException:
            if fd >= 0:
                os.close(fd)
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    except OSError as exc:
        raise PersistenceWriteError(_bounded_store_error("hash chain write failed", exc)) from exc


def _atomic_write_exclusive(path: Path, content: str) -> bool:
    """Write content atomically, failing if the destination already exists.

    Uses ``O_CREAT | O_EXCL`` so the OS rejects pre-existing files at the
    syscall level — closes the F15 TOCTOU between ``HashChainStore.latest``
    and the write. Returns ``True`` on successful write, ``False`` if the
    file already exists (collision — caller may retry with a new sequence).

    A partial-write window exists if the process dies mid-``os.write``;
    the resulting file would fail to deserialize (caught by the existing
    ``CorruptedDataError`` path in ``_load_entry``). Same recovery
    semantics as a corrupted entry.
    """
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(path), flags, 0o644)
    except FileExistsError:
        return False
    except OSError as exc:
        raise PersistenceWriteError(_bounded_store_error("hash chain write failed", exc)) from exc
    try:
        os.write(fd, content.encode("utf-8"))
    except OSError as exc:
        os.close(fd)
        # Best-effort cleanup of the partially-written file.
        try:
            os.unlink(str(path))
        except OSError:
            pass
        raise PersistenceWriteError(_bounded_store_error("hash chain write failed", exc)) from exc
    os.close(fd)
    return True


def compute_chain_hash(sequence_number: int, content_hash: str, previous_hash: str) -> str:
    """Compute SHA-256 chain hash from sequence number, content hash, and previous hash.

    The canonical input format is "{sequence_number}:{content_hash}:{previous_hash}".
    """
    payload = f"{sequence_number}:{content_hash}:{previous_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of arbitrary string content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class HashChainStore:
    """Append-only SHA-256 hash chain for tamper-evident audit trails.

    Each entry links to its predecessor, forming an ordered chain. Entries are
    stored as individual JSON files named by zero-padded sequence number.
    """

    def __init__(self, base_path: Path, chain_id: str = "default") -> None:
        if not isinstance(base_path, Path):
            raise PersistenceError("base_path must be a Path instance")
        if not isinstance(chain_id, str) or not chain_id.strip():
            raise PersistenceError("chain_id must be a non-empty string")
        self._base_path = base_path
        self._chain_id = chain_id

    @property
    def chain_id(self) -> str:
        return self._chain_id

    def _safe_path(self, id_value: str, suffix: str = "") -> Path:
        """Construct a path from *id_value* and validate it stays inside _base_path."""
        if "\0" in id_value:
            raise PathTraversalError("identifier contains null byte")
        if "/" in id_value or "\\" in id_value or ".." in id_value:
            raise PathTraversalError("identifier contains forbidden characters")
        candidate = (self._base_path / f"{id_value}{suffix}").resolve()
        base_resolved = self._base_path.resolve()
        if not candidate.is_relative_to(base_resolved):
            raise PathTraversalError("path escapes base directory")
        return candidate

    def _entry_path(self, sequence_number: int) -> Path:
        return self._safe_path(f"{sequence_number:012d}", suffix=".json")

    def latest(self) -> HashChainEntry | None:
        """Return the most recent chain entry, or None if the chain is empty."""
        if not self._base_path.exists():
            return None

        files = sorted(
            (f for f in self._base_path.iterdir() if f.is_file() and f.suffix == ".json"),
            reverse=True,
        )
        if not files:
            return None

        return self._load_entry(files[0])

    def try_append(self, content_hash: str) -> HashChainEntry | None:
        """Atomic append primitive (audit F15).

        Reads the latest entry, computes the next entry, and writes it
        with ``O_CREAT | O_EXCL``. Returns the written entry on
        success, or ``None`` if another writer claimed the same
        sequence (the OS rejected the destination). Callers either
        retry (see ``append``) or surface the conflict.

        Single-atomic-attempt by design — separating the primitive
        from the retry strategy keeps the contract testable: tests
        can simulate a collision by writing to the entry path
        directly, then verify ``try_append`` returns ``None``.
        """
        if not isinstance(content_hash, str) or not content_hash.strip():
            raise PersistenceError("content_hash must be a non-empty string")

        prev = self.latest()
        if prev is None:
            seq = 0
            prev_hash = GENESIS_PREVIOUS_HASH
        else:
            seq = prev.sequence_number + 1
            prev_hash = prev.chain_hash

        chain_hash = compute_chain_hash(seq, content_hash, prev_hash)
        now = datetime.now(timezone.utc).isoformat()
        entry_id = uuid.uuid4().hex

        entry = HashChainEntry(
            entry_id=entry_id,
            sequence_number=seq,
            content_hash=content_hash,
            previous_hash=prev_hash,
            chain_hash=chain_hash,
            recorded_at=now,
        )

        content = serialize_record(entry)
        if not _atomic_write_exclusive(self._entry_path(seq), content):
            return None
        return entry

    def append(self, content_hash: str) -> HashChainEntry:
        """Append a new entry to the chain and return it.

        Calls ``try_append`` in a bounded retry loop — on collision,
        re-reads ``latest`` and tries again with the next sequence.
        Closes the F15 TOCTOU: pre-v4.30 two concurrent writers could
        both arrive at the same sequence and both succeed (the
        ``os.replace`` in the original write helper overwrote rather
        than rejected). Now the OS rejects the second write at the
        ``O_EXCL`` syscall, the loser re-reads, and the chain stays
        linear.
        """
        max_attempts = 64
        last_exc: Exception | None = None
        for _attempt in range(max_attempts):
            try:
                entry = self.try_append(content_hash)
            except PersistenceWriteError as exc:
                # Non-collision write failure (disk full, permissions,
                # etc.) — surface immediately. Do not retry.
                raise exc
            except (CorruptedDataError, PathTraversalError) as exc:
                last_exc = exc
                raise
            if entry is not None:
                return entry
            # Collision: another writer claimed this sequence. Loop.
        raise PersistenceWriteError(
            f"hash chain append failed after {max_attempts} contention retries"
        )

    def load_all(self) -> tuple[HashChainEntry, ...]:
        """Load all chain entries in sequence order."""
        if not self._base_path.exists():
            return ()

        entries: list[HashChainEntry] = []
        for file_path in sorted(self._base_path.iterdir()):
            if file_path.is_file() and file_path.suffix == ".json":
                entries.append(self._load_entry(file_path))
        return tuple(entries)

    def validate(self) -> HashChainValidationResult:
        """Validate the entire chain and return a result contract.

        Checks that:
        - Sequence numbers are contiguous starting from 0.
        - Each entry's chain_hash matches the recomputed hash.
        - Each entry's previous_hash matches the prior entry's chain_hash.
        """
        entries = self.load_all()

        if not entries:
            return HashChainValidationResult(
                chain_id=self._chain_id,
                entries_checked=0,
                valid=True,
                first_broken_sequence=None,
                detail="empty chain",
            )

        for i, entry in enumerate(entries):
            # Check sequence continuity
            if entry.sequence_number != i:
                return HashChainValidationResult(
                    chain_id=self._chain_id,
                    entries_checked=i + 1,
                    valid=False,
                    first_broken_sequence=i,
                    detail="sequence continuity failure",
                )

            # Check previous_hash linkage
            if i == 0:
                expected_prev = GENESIS_PREVIOUS_HASH
            else:
                expected_prev = entries[i - 1].chain_hash

            if entry.previous_hash != expected_prev:
                return HashChainValidationResult(
                    chain_id=self._chain_id,
                    entries_checked=i + 1,
                    valid=False,
                    first_broken_sequence=i,
                    detail="previous hash mismatch",
                )

            # Recompute and verify chain_hash
            expected_chain = compute_chain_hash(
                entry.sequence_number, entry.content_hash, entry.previous_hash
            )
            if entry.chain_hash != expected_chain:
                return HashChainValidationResult(
                    chain_id=self._chain_id,
                    entries_checked=i + 1,
                    valid=False,
                    first_broken_sequence=i,
                    detail="chain hash mismatch",
                )

        return HashChainValidationResult(
            chain_id=self._chain_id,
            entries_checked=len(entries),
            valid=True,
            first_broken_sequence=None,
            detail="chain valid",
        )

    def _load_entry(self, path: Path) -> HashChainEntry:
        """Load and validate a single chain entry JSON file."""
        try:
            raw_text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise CorruptedDataError(_bounded_store_error("hash chain read failed", exc)) from exc

        try:
            return deserialize_record(raw_text, HashChainEntry)
        except (CorruptedDataError, TypeError, ValueError) as exc:
            raise CorruptedDataError(_bounded_store_error("invalid hash chain entry", exc)) from exc
