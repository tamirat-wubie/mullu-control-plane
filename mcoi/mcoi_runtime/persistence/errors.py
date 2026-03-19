"""Purpose: persistence-specific error hierarchy for the MCOI runtime.
Governance scope: persistence layer error signaling only.
Dependencies: runtime-core invariant error base.
Invariants: all persistence errors are explicit and fail-closed.
"""

from __future__ import annotations

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


class PersistenceError(RuntimeCoreInvariantError):
    """Base error for all persistence operations."""


class SnapshotNotFoundError(PersistenceError):
    """Raised when a requested snapshot does not exist."""


class TraceNotFoundError(PersistenceError):
    """Raised when a requested trace entry does not exist."""


class CorruptedDataError(PersistenceError):
    """Raised when a persisted file contains malformed or unreadable data."""


class PersistenceWriteError(PersistenceError):
    """Raised when a write operation to disk fails."""
