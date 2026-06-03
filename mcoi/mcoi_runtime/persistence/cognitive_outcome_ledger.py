"""Purpose: durable, tamper-evident append-only ledger for the cognitive
    loop's LEARN-phase outcomes (the "D1 record-and-replay substrate" from
    docs/design/COGNITIVE_OUTCOME_LEDGER.md and the cognitive_loop_live_wiring
    follow-up). One ledger event = one Stage-C CognitiveLearner outcome
    (per-tenant / per-capability succeeded/verified + the confidence transition
    + the caller's unique source_ref).

Governance scope: persistence-layer substrate only. This module:
  - composes persistence/hash_chain.py::HashChainStore for tamper-evident
    chain integrity (file-per-sequence + atomic O_CREAT|O_EXCL append + the
    built-in chain-hash validation),
  - writes the event body to a content-addressed sidecar JSON file (path =
    ``bodies/{content_hash}.json``) so body writes are idempotent and safe to
    perform BEFORE the chain append (a partial body write never leaves an
    orphan chain entry; a partial chain append never leaves a body without an
    integrity record).

This module does NOT itself wire the ledger to ``CognitiveLearner`` or to the
HTTP server runtime; integration slices consume this substrate explicitly. See
``__all__`` for the public surface.

Dependencies:
  - persistence/hash_chain.py for chain primitives,
  - persistence/_serialization.py for deterministic JSON serialisation,
  - persistence/errors.py for the failure taxonomy,
  - core/invariants.py for text validation.

Invariants:
  - Chain is append-only; ``append`` is bounded-retry on concurrent collisions
    (file-locking semantics inherited from HashChainStore.append).
  - Body files are content-addressed under ``bodies/`` so two concurrent
    appenders writing the same body content cannot corrupt each other.
  - Per-tenant isolation: each tenant_id maps to a unique on-disk directory
    (path-traversal-safe via HashChainStore._safe_path), and the event body
    itself carries the same ``tenant_id`` so replay / incident export never
    infer partitioning from path alone.
  - ``validate`` is fail-CLOSED: any broken chain hash, body-hash mismatch,
    tenant mismatch, or missing body file raises CorruptedDataError. Rehydrate
    paths that consume ``replay`` MUST call ``validate`` first and refuse to
    serve on failure (the rehydrate posture chosen in L3 of the design doc).
  - The event body and the chain entry are independently deterministic
    (canonical JSON serialise + SHA-256 content hash + SHA-256 chain hash);
    replay is byte-identical for identical input sequences.
"""

from __future__ import annotations

import os
import re
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Protocol

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, ensure_non_empty_text

from ._serialization import (
    deserialize_record,
    loads_strict_json,
    serialize_record,
)
from .errors import CorruptedDataError, PersistenceError, PersistenceWriteError
from .hash_chain import (
    HashChainStore,
    compute_chain_hash,
    compute_content_hash,
)


# Tenant id sanitisation: HashChainStore._safe_path forbids slashes, null bytes,
# and ".." in id_value. We constrain tenant_id to a conservative subset
# (alnum / dash / underscore) so the on-disk directory name is stable across
# OSes and free of any character HashChainStore would refuse.
_TENANT_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")

# Sidecar directory under the per-tenant chain root.
_BODY_SUBDIR = "bodies"

# Filename length guard for content-addressed body files: 64 hex chars from
# SHA-256 + ".json" = 69 chars; well under any FS limit. Pin defensively.
_BODY_FILENAME_MAX = 80


@dataclass(frozen=True, slots=True)
class CognitiveOutcomeEvent:
    """One Stage-C LEARN event recorded in the cognitive outcome ledger.

    Fields mirror ``core.cognitive_live.LearnRecord`` plus:
      - ``tenant_id`` as the explicit replay / audit partition key;
      - ``prior_confidence`` / ``next_confidence`` transition, so replay can
        detect corrupted-state restart; and
      - ``source_ref`` (the caller's unique workflow_id / chain_id, used by
        Stage-C for episodic admission idempotency).
    """

    tenant_id: str
    capability_id: str
    succeeded: bool
    verified: bool
    admitted_entry_id: str | None
    source_ref: str
    learned_at: str
    prior_confidence: float
    next_confidence: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tenant_id",
            ensure_non_empty_text("tenant_id", self.tenant_id),
        )
        object.__setattr__(
            self,
            "capability_id",
            ensure_non_empty_text("capability_id", self.capability_id),
        )
        object.__setattr__(
            self,
            "source_ref",
            ensure_non_empty_text("source_ref", self.source_ref),
        )
        object.__setattr__(
            self,
            "learned_at",
            ensure_non_empty_text("learned_at", self.learned_at),
        )
        if not isinstance(self.succeeded, bool):
            raise RuntimeCoreInvariantError("succeeded must be a bool")
        if not isinstance(self.verified, bool):
            raise RuntimeCoreInvariantError("verified must be a bool")
        if self.admitted_entry_id is not None and not isinstance(self.admitted_entry_id, str):
            raise RuntimeCoreInvariantError("admitted_entry_id must be str or None")
        if not isinstance(self.prior_confidence, (int, float)):
            raise RuntimeCoreInvariantError("prior_confidence must be a number")
        if not isinstance(self.next_confidence, (int, float)):
            raise RuntimeCoreInvariantError("next_confidence must be a number")
        if not (0.0 <= float(self.prior_confidence) <= 1.0):
            raise RuntimeCoreInvariantError("prior_confidence must be in [0.0, 1.0]")
        if not (0.0 <= float(self.next_confidence) <= 1.0):
            raise RuntimeCoreInvariantError("next_confidence must be in [0.0, 1.0]")


@dataclass(frozen=True, slots=True)
class CognitiveOutcomeEntry:
    """A persisted ledger entry: event body + chain metadata."""

    sequence: int
    event: CognitiveOutcomeEvent
    content_hash: str
    chain_hash: str
    previous_chain_hash: str
    recorded_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.sequence, int) or self.sequence < 0:
            raise RuntimeCoreInvariantError("sequence must be a non-negative int")
        if not isinstance(self.event, CognitiveOutcomeEvent):
            raise RuntimeCoreInvariantError("event must be a CognitiveOutcomeEvent")
        for field_name in ("content_hash", "chain_hash", "previous_chain_hash", "recorded_at"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError("chain-meta fields must be non-empty strings")


class CognitiveOutcomeLedger(Protocol):
    """The cognitive outcome ledger Protocol.

    File and Postgres backings (and any future implementation) MUST honour:
    - ``append`` is durable + appends a strictly monotone sequence per chain;
    - ``replay`` yields entries in original-sequence order;
    - ``validate`` is fail-CLOSED on any integrity violation;
    - ``latest_sequence`` reflects the durable last sequence (None if empty).
    """

    def append(self, event: CognitiveOutcomeEvent) -> CognitiveOutcomeEntry: ...

    def replay(self) -> Iterator[CognitiveOutcomeEntry]: ...

    def validate(self) -> None: ...

    def latest_sequence(self) -> int | None: ...


def _normalise_tenant_id(tenant_id: str) -> str:
    cleaned = ensure_non_empty_text("tenant_id", tenant_id)
    if not _TENANT_ID_RE.match(cleaned):
        raise PersistenceError(
            "tenant_id must match [A-Za-z0-9_-]{1,64} for on-disk safety"
        )
    return cleaned


def _atomic_write(path: Path, content: str) -> None:
    """Mirror persistence/hash_chain.py::_atomic_write semantics.

    Write via temp-file-then-rename so a crash mid-write never leaves a
    partial body file at the final path. This is the same pattern the
    chain entry writer uses, so the two halves (body + chain entry) share
    identical durability guarantees.
    """
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    fd = -1
    tmp_path: str | None = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(parent), suffix=".tmp")
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        fd = -1
        os.replace(tmp_path, str(path))
        tmp_path = None
    except OSError as exc:
        raise PersistenceWriteError(
            f"atomic write failed for ledger body ({type(exc).__name__})"
        ) from exc
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


class FileBackedCognitiveOutcomeLedger:
    """Per-tenant file-backed cognitive outcome ledger.

    Layout (rooted at ``base_path / tenant_id /``):

      ``000000000000.json``       -- HashChainEntry from HashChainStore
      ``000000000000.body.json``  -- (NOT used; body lives content-addressed)
      ``bodies/{content_hash}.json``
                                  -- CognitiveOutcomeEvent body, idempotent
                                     by content_hash (same event content
                                     always writes to the same path so a
                                     partial-then-retry append is safe).

    Append order: body FIRST (idempotent content-addressed write) then chain
    entry. A partial body write never produces an orphan chain entry. A
    partial chain append only leaves the body, which the next successful
    append can reuse (no harm). Concurrent appenders are serialised inside
    the process by ``_lock`` and across processes by HashChainStore's
    bounded-retry O_CREAT|O_EXCL chain append.
    """

    def __init__(self, *, base_path: Path, tenant_id: str) -> None:
        if not isinstance(base_path, Path):
            raise PersistenceError("base_path must be a Path instance")
        normalised = _normalise_tenant_id(tenant_id)
        self._tenant_id = normalised
        self._tenant_dir = (base_path / normalised).resolve()
        # Ensure base + tenant dir exist (HashChainStore will mkdir its own
        # files inside but does not create the base directory itself).
        self._tenant_dir.mkdir(parents=True, exist_ok=True)
        (self._tenant_dir / _BODY_SUBDIR).mkdir(parents=True, exist_ok=True)
        self._chain = HashChainStore(self._tenant_dir, chain_id=normalised)
        # FastAPI runs sync handlers in a threadpool; in-process serialisation
        # of append matches the canonical lock fix used across the runtime
        # (memory.py, ConversationStore, NotificationDispatcher, ...).
        self._lock = threading.Lock()

    # ----- Protocol methods -----

    def append(self, event: CognitiveOutcomeEvent) -> CognitiveOutcomeEntry:
        if not isinstance(event, CognitiveOutcomeEvent):
            raise PersistenceError("append requires a CognitiveOutcomeEvent")
        if event.tenant_id != self._tenant_id:
            raise PersistenceError("event.tenant_id does not match ledger tenant_id")
        body_str = serialize_record(event)
        content_hash = compute_content_hash(body_str)
        body_path = self._body_path(content_hash)
        with self._lock:
            # Idempotent content-addressed body write (write first; safe to
            # repeat if the chain append later fails).
            if not body_path.exists():
                _atomic_write(body_path, body_str)
            # Chain append (atomic, bounded-retry on contention).
            chain_entry = self._chain.append(content_hash)
        return CognitiveOutcomeEntry(
            sequence=chain_entry.sequence_number,
            event=event,
            content_hash=chain_entry.content_hash,
            chain_hash=chain_entry.chain_hash,
            previous_chain_hash=chain_entry.previous_hash,
            recorded_at=chain_entry.recorded_at,
        )

    def replay(self) -> Iterator[CognitiveOutcomeEntry]:
        """Yield entries in original-sequence order.

        Each yield re-reads the body file by content_hash and validates the
        body's SHA-256 matches the chain entry's content_hash (raising
        CorruptedDataError on mismatch -- fail-CLOSED). The hash-chain
        integrity itself (each chain_hash linking to the prior) is checked
        once via ``validate`` before consuming ``replay``; callers MUST call
        validate FIRST. See the docstring on validate for the rehydrate
        contract.
        """
        chain_entries = self._chain.load_all()
        for chain_entry in chain_entries:
            yield self._load_outcome_entry(chain_entry)

    def validate(self) -> None:
        """Fail-CLOSED integrity check across the whole chain + bodies.

        Raises ``CorruptedDataError`` on any of:
          * a chain hash mismatch (HashChainStore.validate -> not-valid),
          * a body file missing for a chain entry's content_hash,
          * a body file's actual SHA-256 not matching the recorded content_hash,
          * an event body carrying a tenant_id different from this ledger.

        This is the rehydrate gate: a worker MUST call this before serving
        the first request. A failure aborts startup (the L3 hard-cap +
        fail-CLOSED posture chosen in the design doc).
        """
        chain_result = self._chain.validate()
        if not chain_result.valid:
            raise CorruptedDataError(
                f"cognitive outcome ledger chain invalid: {chain_result.detail}"
            )
        for chain_entry in self._chain.load_all():
            body_path = self._body_path(chain_entry.content_hash)
            if not body_path.exists():
                raise CorruptedDataError(
                    "cognitive outcome ledger body missing for chain entry"
                )
            body_str = body_path.read_text(encoding="utf-8")
            actual_hash = compute_content_hash(body_str)
            if actual_hash != chain_entry.content_hash:
                raise CorruptedDataError(
                    "cognitive outcome ledger body hash mismatch"
                )
            try:
                event = deserialize_record(body_str, CognitiveOutcomeEvent)
            except (CorruptedDataError, TypeError, ValueError) as exc:
                raise CorruptedDataError(
                    f"cognitive outcome ledger body invalid ({type(exc).__name__})"
                ) from exc
            if event.tenant_id != self._tenant_id:
                raise CorruptedDataError("cognitive outcome ledger tenant mismatch")
            # Cross-check by recomputing the chain hash from canonical primitives.
            expected_chain = compute_chain_hash(
                chain_entry.sequence_number,
                actual_hash,
                chain_entry.previous_hash,
            )
            if expected_chain != chain_entry.chain_hash:
                raise CorruptedDataError(
                    "cognitive outcome ledger chain hash recompute mismatch"
                )

    def latest_sequence(self) -> int | None:
        latest = self._chain.latest()
        if latest is None:
            return None
        return int(latest.sequence_number)

    # ----- Internal helpers -----

    def _body_path(self, content_hash: str) -> Path:
        if not isinstance(content_hash, str) or len(content_hash) != 64:
            raise PersistenceError("content_hash must be a 64-character hex string")
        filename = f"{content_hash}.json"
        if len(filename) > _BODY_FILENAME_MAX:
            raise PersistenceError("body filename exceeds length guard")
        return self._tenant_dir / _BODY_SUBDIR / filename

    def _load_outcome_entry(self, chain_entry) -> CognitiveOutcomeEntry:
        body_path = self._body_path(chain_entry.content_hash)
        if not body_path.exists():
            raise CorruptedDataError(
                "cognitive outcome ledger body missing for chain entry"
            )
        body_str = body_path.read_text(encoding="utf-8")
        # Cross-check the body's hash matches the chain's content_hash even on
        # a replay-only path (validate() is the bigger gate but a single
        # mismatched body must never be silently fed back into the organs).
        actual_hash = compute_content_hash(body_str)
        if actual_hash != chain_entry.content_hash:
            raise CorruptedDataError(
                "cognitive outcome ledger body hash mismatch on replay"
            )
        # Parse + reconstruct as CognitiveOutcomeEvent.
        try:
            event = deserialize_record(body_str, CognitiveOutcomeEvent)
        except (CorruptedDataError, TypeError, ValueError) as exc:
            raise CorruptedDataError(
                f"cognitive outcome ledger body invalid ({type(exc).__name__})"
            ) from exc
        # Sanity: confirm we got back the expected shape (deserialize_record
        # already enforces this, but this is the user-visible boundary).
        if not isinstance(event, CognitiveOutcomeEvent):
            raise CorruptedDataError("cognitive outcome ledger body deserialise drift")
        if event.tenant_id != self._tenant_id:
            raise CorruptedDataError("cognitive outcome ledger tenant mismatch on replay")
        # Also guard against an upstream JSON change introducing a non-dict
        # body shape that deserialize_record permits.
        try:
            parsed = loads_strict_json(body_str)
        except ValueError as exc:
            raise CorruptedDataError(
                f"cognitive outcome ledger body not strict-JSON ({type(exc).__name__})"
            ) from exc
        if not isinstance(parsed, dict):
            raise CorruptedDataError("cognitive outcome ledger body must be a JSON object")
        return CognitiveOutcomeEntry(
            sequence=int(chain_entry.sequence_number),
            event=event,
            content_hash=chain_entry.content_hash,
            chain_hash=chain_entry.chain_hash,
            previous_chain_hash=chain_entry.previous_hash,
            recorded_at=chain_entry.recorded_at,
        )


__all__ = [
    "CognitiveOutcomeEntry",
    "CognitiveOutcomeEvent",
    "CognitiveOutcomeLedger",
    "FileBackedCognitiveOutcomeLedger",
]
